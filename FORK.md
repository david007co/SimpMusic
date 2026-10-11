# SimpMusic Tasker

Unofficial Android-only fork of [SimpMusic](https://github.com/maxrave-dev/SimpMusic), maintained at https://github.com/david007co/SimpMusic. Upstream attribution and license are retained. Desktop sources remain for upstream compatibility but are not a supported fork target.

## Supported feature

Tasker can open a personalized **Mix for you** playlist by its displayed name and start that exact playlist through the existing playlist Play All path. Normal manual navigation does not autoplay. A fresh accepted request intentionally replaces the active queue. Local/library playlists are not supported by this name lookup.

In Tasker, use Launch App → optionally Wait 5 seconds for startup → Send Intent. The wait is a convenience, not an app readiness guarantee.

| Send Intent field | Release value |
|---|---|
| Action | `io.github.david007co.simpmusic.action.OPEN_PLAYLIST` |
| Package | `io.github.david007co.simpmusic` |
| Class | `com.maxrave.simpmusic.MainActivity` |
| Target | **Activity**, not Broadcast Receiver |
| Extra | `playlist_name:My Supermix` |
| Extra | `request_id:%TIMEMS` |

Keep the app foreground/resumed. Accept the app's opt-in prompt. Each new invocation needs a fresh request ID; duplicate/stale IDs are rejected. Lookup failures and cancelled requests must not replace existing playback. The release app is separate from SimpMusic Dev, with separate account/settings/consent. Debug uses package/action prefix `com.maxrave.simpmusic.dev`.

Screen-off/headless operation is **not supported**. Activity recreation, cold-start saved-queue restore overlap and continuation timing have not been fully device-validated. Lookup uniqueness is limited to candidates returned by the existing Mix for you repository; pagination completeness is not guaranteed.

## Windows build

Use a short recursive checkout, Windows JDK 21, Android command-line SDK tools and the Gradle wrapper. Android Studio/emulator are optional. This baseline uses compile SDK 37 (`platforms;android-37.0`) and Build Tools 36.0.0. Accept Google's SDK licenses locally. Configure ignored `local.properties` with your SDK path, for example `sdk.dir=C:/Android/Sdk`.

From the checkout in PowerShell, with JDK 21 selected:

```powershell
.\gradlew.bat :androidApp:testDebugUnitTest :androidApp:assembleRelease -PisFullBuild=false -PforkVersionCode=3 --console=plain --max-workers=1 -Dorg.gradle.jvmargs=-Xmx4096m
```

`fork-release.json` records the accepted source version/code, currently `2.2.0-tasker.2` / 3; Gradle reads these defaults. `-PforkVersionCode=N` remains an override for explicit local candidates. Never publish an old/reused code. Integration automation allocates the next tracked version in the PR; release checks reject codes already present in GitHub release APKs. Preserve distributed-version history. Release R8 required a 4GiB heap on the development machine.

Unsigned universal output: `androidApp/build/outputs/apk/release/androidApp-universal-release-unsigned.apk`.

## Signing and updates

The fork release package is `io.github.david007co.simpmusic`. The app requires exactly one signer with certificate SHA-256:

```text
22aad284a1b3eb1aaf6494238eb61a2cf74bacecbd3f63b89721718db12820b3
```

The fingerprint is public; the private key/password must never enter Git, logs or chat. Only the maintainer's existing permanent key can create updates for this identity. A different distributor must deliberately choose their own identity/certificate rather than bypass verification. Debug remains separately installable.

Maintainer local signing command (PowerShell):

```powershell
.\scripts\windows\sign-tasker-release.ps1 -UnsignedApk .\androidApp\build\outputs\apk\release\androidApp-universal-release-unsigned.apk
```

Default keystore location is under the current user's `.android-signing\SimpMusicTasker`; `-Keystore` and `-BuildTools` can override paths. Alias: `simpmusic-tasker`. The script prompts privately, checks package/version/ABIs, alignment and expected certificate, and produces `SimpMusic-Tasker-universal-release.apk`. Do not distribute after any verification failure. Archive accepted APKs **outside build directories**, which Gradle may clean.

Nine focused Android unit tests and minified release build passed. On the test device, foreground exact-playlist autoplay and a same-key code 1 → 2 update were user-confirmed, including retained login/settings and existing Tasker task. Actual Obtainium update to tasker.2/code 3 was also user-confirmed. Release-specific failure/cancel/manual-navigation retests remain incomplete; these were checked in debug.

## Upstream releases and Obtainium

Planned flow: detect a new official release → prepare a pinned upstream integration PR, including its Core gitlink → preserve fork customizations → review/test/build → assign increasing code → sign with the same key → publish one universal APK on **this fork's** Releases → Obtainium updates from this fork.

No blind conflict resolution or publication from unchecked merges. Upstream's built-in updater is disabled for the fork so it cannot substitute an official APK. Obtainium delivery is user-validated. The notification watcher is live. Integration/checks, accepted-version release dispatch and isolated signing workflows are locally prepared but not activated/live-tested. See UPSTREAM_MAINTENANCE.md for activation gates. Signing remains local until cloud custody is separately approved.

Inherited workflows are preserved as `.yml.disabled` and will not execute from this revision. Replace them deliberately with Android FOSS-only fork workflows before enabling automation. Workflow disabling is branch-specific; other inherited branches on GitHub still contain upstream workflow files. Only reviewed fork workflows should be enabled; inherited workflow IDs on other branches require separate disabling.

## Source baseline

- App: `62e0073ba818d899b22c75909deb9b034516d5db`
- Core (unchanged submodule): `d90b53fbad07ab73cecbfe89b33b533fb9ca78ed`
- Working branch: `feature/tasker-playlist-intent`

A fresh GitHub fork may contain newer upstream branches; do not silently merge them into this tested baseline. Source publication and release tags must identify the actual tested fork commit.
