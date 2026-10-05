package com.maxrave.simpmusic

import android.Manifest
import android.content.ComponentName
import android.content.Intent
import android.content.ServiceConnection
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.core.net.toUri
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.lifecycleScope
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.eygraber.uri.toKmpUriOrNull
import com.maxrave.common.FIRST_TIME_MIGRATION
import com.maxrave.common.SELECTED_LANGUAGE
import com.maxrave.common.STATUS_DONE
import com.maxrave.common.SUPPORTED_LANGUAGE
import com.maxrave.common.SUPPORTED_LOCATION
import com.maxrave.domain.data.model.intent.GenericIntent
import com.maxrave.domain.manager.DataStoreManager
import com.maxrave.domain.repository.PlaylistRepository
import com.maxrave.domain.mediaservice.handler.MediaPlayerHandler
import com.maxrave.domain.mediaservice.handler.ToastType
import com.maxrave.logger.Logger
import com.maxrave.media3.di.setServiceActivitySession
import com.maxrave.simpmusic.di.viewModelModule
import com.maxrave.simpmusic.service.rss.RssFeedNotifyWork
import com.maxrave.simpmusic.service.test.notification.NotifyWork
import com.maxrave.simpmusic.utils.ComposeResUtils
import com.maxrave.simpmusic.utils.VersionManager
import com.maxrave.simpmusic.viewModel.SharedViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.runBlocking
import org.koin.android.ext.android.inject
import org.koin.core.context.loadKoinModules
import org.koin.core.context.unloadKoinModules
import org.koin.dsl.module
import org.simpmusic.crashlytics.pushPlayerError
import pub.devrel.easypermissions.EasyPermissions
import java.util.Locale
import java.util.concurrent.TimeUnit

@Suppress("DEPRECATION")
class MainActivity : AppCompatActivity() {
    val viewModel: SharedViewModel by inject()
    val mediaPlayerHandler by inject<MediaPlayerHandler>()
    val dataStoreManager: DataStoreManager by inject()

    private val playlistRepository: PlaylistRepository by inject()
    private var playlistRequestJob: Job? = null
    private var pendingPlaylistName by mutableStateOf<String?>(null)
    private var confirmDisablePlaylistIntents by mutableStateOf(false)
    private var pendingRequestId: String? = null

    private var mBound = false
    private var shouldUnbind = false
    private val serviceConnection =
        object : ServiceConnection {
            override fun onServiceConnected(
                name: ComponentName?,
                service: IBinder?,
            ) {
//                mediaPlayerHandler.setActivitySession(this@MainActivity, MainActivity::class.java, service)
                setServiceActivitySession(this@MainActivity, MainActivity::class.java, service)
                Logger.w("MainActivity", "onServiceConnected: ")
                mBound = true
            }

            override fun onServiceDisconnected(name: ComponentName?) {
                Logger.w("MainActivity", "onServiceDisconnected: ")
                mBound = false
            }
        }

    override fun onStart() {
        super.onStart()
        startMusicService()
    }

    override fun onStop() {
        super.onStop()
        TaskerAutoplay.cancel()
        playlistRequestJob?.cancel()
        pendingPlaylistName = null
        confirmDisablePlaylistIntents = false
        if (shouldUnbind) {
            unbindService(serviceConnection)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (handlePlaylistIntent(intent)) return
        TaskerAutoplay.cancel()
        playlistRequestJob?.cancel()
        pendingPlaylistName = null
        confirmDisablePlaylistIntents = false
        Logger.d("MainActivity", "onNewIntent: $intent")
        viewModel.setIntent(
            GenericIntent(
                action = intent.action,
                data = (intent.data ?: intent.getStringExtra(Intent.EXTRA_TEXT)?.toUri())?.toKmpUriOrNull(),
                type = intent.type,
            ),
        )
    }

    @ExperimentalFoundationApi
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        loadKoinModules(
            module {
                single<AppCompatActivity> { this@MainActivity }
            },
        )
        // Recreate view model to fix the issue of view model not getting data from the service
        unloadKoinModules(viewModelModule)
        loadKoinModules(viewModelModule)
        VersionManager.initialize()
        if (BuildConfig.IS_TASKER_FORK) {
            viewModel.configureTaskerFork(TaskerForkIdentity.isValid(packageName, signingCertSha256()))
        }
        checkForUpdate()
        if (viewModel.recreateActivity.value || viewModel.isServiceRunning) {
            viewModel.activityRecreateDone()
        } else {
            startMusicService()
        }
        Logger.d("MainActivity", "onCreate: ")
        val isDisableRequest = intent.action == "$packageName.action.DISABLE_PLAYLIST_INTENTS"
        val isPlaylistRequest = intent.action == "$packageName.action.OPEN_PLAYLIST"
        if (isDisableRequest) {
            intent.action = null
            confirmDisablePlaylistIntents = true
        }
        if (isPlaylistRequest) {
            // The MVP deliberately requires an already initialized foreground activity.
            intent.action = null
            viewModel.makeToast("Open SimpMusic first, then send the playlist intent again.")
        }
        val data = if (isPlaylistRequest || isDisableRequest) null else (intent?.data ?: intent?.getStringExtra(Intent.EXTRA_TEXT)?.toUri())?.toKmpUriOrNull()
        if (data != null) {
            viewModel.setIntent(
                GenericIntent(
                    action = intent.action,
                    data = data,
                    type = intent.type,
                ),
            )
        }
        Logger.d("Italy", "Key: ${Locale.ITALY.toLanguageTag()}")

        // Check if the migration has already been done or not
        if (getString(FIRST_TIME_MIGRATION) != STATUS_DONE) {
            Logger.d("Locale Key", "onCreate: ${Locale.getDefault().toLanguageTag()}")
            if (SUPPORTED_LANGUAGE.codes.contains(Locale.getDefault().toLanguageTag())) {
                Logger.d(
                    "Contains",
                    "onCreate: ${
                        SUPPORTED_LANGUAGE.codes.contains(
                            Locale.getDefault().toLanguageTag(),
                        )
                    }",
                )
                putString(SELECTED_LANGUAGE, Locale.getDefault().toLanguageTag())
                if (SUPPORTED_LOCATION.items.contains(Locale.getDefault().country)) {
                    putString("location", Locale.getDefault().country)
                } else {
                    putString("location", "US")
                }
            } else {
                putString(SELECTED_LANGUAGE, "en-US")
            }
            // Fetch the selected language from wherever it was stored. In this case its SharedPref
            getString(SELECTED_LANGUAGE)?.let {
                Logger.d("Locale Key", "getString: $it")
                // Set this locale using the AndroidX library that will handle the storage itself
                val localeList = LocaleListCompat.forLanguageTags(it)
                AppCompatDelegate.setApplicationLocales(localeList)
                // Set the migration flag to ensure that this is executed only once
                putString(FIRST_TIME_MIGRATION, STATUS_DONE)
            }
        }
        if (AppCompatDelegate.getApplicationLocales().toLanguageTags() !=
            getString(
                SELECTED_LANGUAGE,
            )
        ) {
            Logger.d(
                "Locale Key",
                "onCreate: ${AppCompatDelegate.getApplicationLocales().toLanguageTags()}",
            )
            putString(SELECTED_LANGUAGE, AppCompatDelegate.getApplicationLocales().toLanguageTags())
        }

        enableEdgeToEdge(
            navigationBarStyle =
                SystemBarStyle.dark(
                    scrim = Color.Transparent.toArgb(),
                ),
            statusBarStyle =
                SystemBarStyle.dark(
                    scrim = Color.Transparent.toArgb(),
                ),
        )
        viewModel.checkIsRestoring()
        val request =
            PeriodicWorkRequestBuilder<NotifyWork>(
                12L,
                TimeUnit.HOURS,
            ).addTag("Worker Test")
                .setConstraints(
                    Constraints
                        .Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build(),
                ).build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "Artist Worker",
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
        lifecycleScope.launch {
            dataStoreManager.blogNotificationEnabled.collect { enabled ->
                if (enabled == DataStoreManager.TRUE) {
                    val rssRequest =
                        PeriodicWorkRequestBuilder<RssFeedNotifyWork>(
                            24L,
                            TimeUnit.HOURS,
                        ).addTag("Blog RSS Worker")
                            .setConstraints(
                                Constraints
                                    .Builder()
                                    .setRequiredNetworkType(NetworkType.CONNECTED)
                                    .build(),
                            ).build()
                    WorkManager.getInstance(this@MainActivity).enqueueUniquePeriodicWork(
                        "Blog RSS Worker",
                        ExistingPeriodicWorkPolicy.KEEP,
                        rssRequest,
                    )
                } else {
                    WorkManager.getInstance(this@MainActivity).cancelUniqueWork("Blog RSS Worker")
                }
            }
        }

        if (!EasyPermissions.hasPermissions(this, Manifest.permission.POST_NOTIFICATIONS)) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                val doNotAsk = getString("notification_permission_do_not_ask")
                if (doNotAsk != "true") {
                    val wasAsked = getString("notification_permission_asked")
                    if (wasAsked != "true") {
                        // First time: request system permission
                        EasyPermissions.requestPermissions(
                            this,
                            runBlocking { ComposeResUtils.getResString(ComposeResUtils.StringType.NOTIFICATION_REQUEST) },
                            1,
                            Manifest.permission.POST_NOTIFICATIONS,
                        )
                        putString("notification_permission_asked", "true")
                    } else {
                        // Already asked before: show custom dialog with "Don't show again"
                        viewModel.showNotificationPermissionDialog()
                    }
                }
            }
        }
        viewModel.getLocation()

        if (!BuildConfig.DEBUG && !BuildConfig.IS_TASKER_FORK) viewModel.checkOfficialBuild(packageName, signingCertSha256())
        setContent {
            App(viewModel)
            if (confirmDisablePlaylistIntents) {
                AlertDialog(
                    onDismissRequest = { confirmDisablePlaylistIntents = false },
                    title = { Text("Disable playlist-name intents?") },
                    text = { Text("Future playlist-name requests will ask permission again.") },
                    confirmButton = {
                        TextButton(onClick = {
                            TaskerAutoplay.cancel()
                            playlistRequestJob?.cancel()
                            pendingPlaylistName = null
                            putString("tasker_playlist_intents_enabled", "false")
                            confirmDisablePlaylistIntents = false
                        }) { Text("Disable") }
                    },
                    dismissButton = {
                        TextButton(onClick = { confirmDisablePlaylistIntents = false }) { Text("Cancel") }
                    },
                )
            }
            pendingPlaylistName?.let { name ->
                AlertDialog(
                    onDismissRequest = { pendingPlaylistName = null },
                    title = { Text("Allow playlist-name intents?") },
                    text = {
                        Text("Allow installed apps to open and automatically play Mix for you playlists by name? First request: $name")
                    },
                    confirmButton = {
                        TextButton(onClick = {
                            putString("tasker_playlist_intents_enabled", "autoplay_v1")
                            pendingPlaylistName = null
                            pendingRequestId?.let { openNamedPlaylist(name, it) }
                        }) { Text("Allow") }
                    },
                    dismissButton = {
                        TextButton(onClick = { pendingPlaylistName = null }) { Text("Cancel") }
                    },
                )
            }
        }
    }

    override fun onDestroy() {
        TaskerAutoplay.cancel()
        val shouldStopMusicService = viewModel.shouldStopMusicService()
        Logger.w("MainActivity", "onDestroy: Should stop service $shouldStopMusicService")

        // Always unbind service if it was bound to prevent MusicBinder leak
        if (shouldStopMusicService && shouldUnbind && isFinishing) {
            viewModel.isServiceRunning = false
        }
        unloadKoinModules(viewModelModule)
        super.onDestroy()
        Logger.d("MainActivity", "onDestroy: ")
    }

    override fun onRestart() {
        super.onRestart()
        viewModel.activityRecreate()
    }

    private fun startMusicService() {
//        mediaPlayerHandler.startMediaService(this, serviceConnection)
        com.maxrave.media3.di
            .startService(this@MainActivity, serviceConnection)
        mediaPlayerHandler.pushPlayerError = { it ->
            pushPlayerError(it)
        }
        mediaPlayerHandler.showToast = { type ->
            viewModel.makeToast(
                when (type) {
                    is ToastType.ExplicitContent -> {
                        runBlocking { ComposeResUtils.getResString(ComposeResUtils.StringType.EXPLICIT_CONTENT_BLOCKED) }
                    }

                    is ToastType.PlayerError -> {
                        runBlocking { ComposeResUtils.getResString(ComposeResUtils.StringType.TIME_OUT_ERROR, type.error) }
                    }

                    is ToastType.SponsorBlockSkip -> {
                        runBlocking { ComposeResUtils.getResString(ComposeResUtils.StringType.SPONSOR_BLOCK_SKIP, type.category) }
                    }
                },
            )
        }
        viewModel.isServiceRunning = true
        shouldUnbind = true
        Logger.d("Service", "Service started")
    }

    private fun handlePlaylistIntent(request: Intent): Boolean {
        if (request.action == "$packageName.action.DISABLE_PLAYLIST_INTENTS") {
            request.action = null
            TaskerAutoplay.cancel()
            playlistRequestJob?.cancel()
            pendingPlaylistName = null
            confirmDisablePlaylistIntents = true
            return true
        }
        if (request.action != "$packageName.action.OPEN_PLAYLIST") return false
        request.action = null
        if (!lifecycle.currentState.isAtLeast(androidx.lifecycle.Lifecycle.State.STARTED)) {
            viewModel.makeToast("Open SimpMusic first, then send the playlist intent again.")
            return true
        }
        val name = try {
            @Suppress("DEPRECATION")
            TaskerPlaylistRequest.validatedName(request.extras?.get(TaskerPlaylistRequest.EXTRA_NAME))
        } catch (_: RuntimeException) {
            null
        }
        val requestId = try {
            @Suppress("DEPRECATION")
            TaskerPlaylistRequest.validatedRequestId(request.extras?.get("request_id"))
        } catch (_: RuntimeException) { null }
        val sequence = requestId?.toLongOrNull()?.takeIf { it > 0 }
        val previous = getString("tasker_last_request_id")?.toLongOrNull() ?: 0
        if (sequence == null || sequence > System.currentTimeMillis() + 60_000) {
            viewModel.makeToast("Invalid request_id: use request_id:%TIMEMS (positive timestamp, String or integer).")
            return true
        }
        if (!TaskerPlaylistRequest.newRequestId(requestId, previous, System.currentTimeMillis())) return true
        if (name == null) {
            viewModel.makeToast("playlist_name must be a nonblank String of at most 256 characters.")
        } else if (playlistRequestJob?.isActive == true || pendingPlaylistName != null || confirmDisablePlaylistIntents) {
            viewModel.makeToast("A playlist request is already pending. Try again when it finishes.")
        } else if (getString("tasker_playlist_intents_enabled") != "autoplay_v1") {
            pendingRequestId = requestId
            pendingPlaylistName = name
        } else {
            openNamedPlaylist(name, requestId)
        }
        return true
    }

    private fun openNamedPlaylist(name: String, requestId: String) {
        // Persistent monotonic identity survives Activity/process recreation; no replay after commit.
        putString("tasker_last_request_id", requestId)
        TaskerAutoplay.cancel()
        playlistRequestJob = lifecycleScope.launch {
            try {
                withTimeout(30_000) {
                    if (dataStoreManager.loggedIn.first() != DataStoreManager.TRUE || dataStoreManager.cookie.first().isBlank()) {
                        viewModel.makeToast("Sign in to YouTube before requesting a playlist.")
                        return@withTimeout
                    }
                    val mixes = playlistRepository.getMixedForYou().firstOrNull()
                    if (mixes.isNullOrEmpty()) {
                        viewModel.makeToast("Mix for you is unavailable. Open it manually and try again.")
                        return@withTimeout
                    }
                    val match = TaskerPlaylistRequest.match(
                        name,
                        mixes.map { TaskerPlaylistRequest.Candidate(it.browseId, it.title) },
                    )
                    if (match == null || match.id.isBlank()) {
                        viewModel.makeToast("No unique playlist-name match in Mix for you. Check the displayed title.")
                        return@withTimeout
                    }
                    // Reuse the normal deep-link navigation; the existing playlist screen owns loading and Play.
                    val uri = android.net.Uri.Builder()
                        .scheme("simpmusic")
                        .authority("playlist")
                        .appendQueryParameter("list", match.id)
                        .appendQueryParameter("tasker_request_id", requestId)
                        .build()
                    if (lifecycle.currentState.isAtLeast(androidx.lifecycle.Lifecycle.State.RESUMED) &&
                        getString("tasker_playlist_intents_enabled") == "autoplay_v1"
                    ) {
                        TaskerAutoplay.arm(TaskerAutoplay.Request(match.id, requestId))
                        viewModel.setIntent(GenericIntent(data = uri.toKmpUriOrNull()))
                    }
                }
            } catch (_: TimeoutCancellationException) {
                viewModel.makeToast("Playlist lookup timed out. Try Mix for you manually.")
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                viewModel.makeToast("Playlist lookup failed. Check your connection and account.")
            }
        }
    }

    private fun checkForUpdate() {
        if (viewModel.shouldCheckForUpdate()) {
            viewModel.checkForUpdate()
        }
    }

    private fun putString(
        key: String,
        value: String,
    ) {
        viewModel.putString(key, value)
    }

    private fun getString(key: String): String? = viewModel.getString(key)

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        viewModel.activityRecreate()
    }
}