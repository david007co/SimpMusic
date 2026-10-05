package com.maxrave.simpmusic

/** In-memory capability: a restored route or an external deep link cannot authorize playback. */
object TaskerAutoplay {
    data class Request(val playlistId: String, val requestId: String)
    private var pending: Request? = null

    fun arm(request: Request) { pending = request }
    fun cancel() { pending = null }
    fun cancel(requestId: String) {
        if (pending?.requestId == requestId) pending = null
    }

    fun consume(requestId: String?, routeId: String, loadedId: String?, ready: Boolean): Boolean {
        val request = pending ?: return false
        if (!ready || requestId != request.requestId ||
            routeId.removePrefix("VL") != request.playlistId.removePrefix("VL") ||
            loadedId?.removePrefix("VL") != request.playlistId.removePrefix("VL")
        ) return false
        pending = null
        return true
    }
}
