package com.maxrave.simpmusic

/** Narrow name matching for account mixes; never falls back to public search. */
internal object TaskerPlaylistRequest {
    const val EXTRA_NAME = "playlist_name"

    data class Candidate(val id: String, val title: String)

    fun validatedName(value: Any?): String? =
        (value as? String)?.trim()?.takeIf { it.isNotEmpty() && it.length <= 256 }

    fun validatedRequestId(value: Any?): String? {
        val id = when (value) {
            is String -> value.toLongOrNull()
            is Long -> value
            is Int -> value.toLong()
            else -> null
        } ?: return null
        return id.takeIf { it > 0 }?.toString()
    }

    fun newRequestId(value: String?, previous: Long, now: Long): Boolean {
        val id = value?.toLongOrNull() ?: return false
        return id > previous && id > 0 && id <= now + 60_000
    }

    fun match(name: String, candidates: List<Candidate>): Candidate? {
        val exact = candidates.filter { it.title.trim() == name }
        val matches = exact.ifEmpty { candidates.filter { it.title.trim().equals(name, ignoreCase = true) } }
        return matches.distinctBy { it.id.removePrefix("VL") }.singleOrNull()
    }
}
