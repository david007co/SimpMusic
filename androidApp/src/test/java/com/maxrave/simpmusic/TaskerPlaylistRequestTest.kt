package com.maxrave.simpmusic

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TaskerPlaylistRequestTest {
    @Test
    fun forkIdentityRequiresExactPackageAndSinglePinnedSigner() {
        // Independently normalized from the public certificate's colon-separated keytool output.
        val cert = "22:AA:D2:84:A1:B3:EB:1A:AF:64:94:23:8E:B6:1A:2C:F7:4B:AC:EC:BD:3F:63:B8:97:21:71:8D:B1:28:20:B3"
            .replace(":", "").lowercase()
        assertEquals(64, TaskerForkIdentity.CERTIFICATE_SHA256.length)
        assertEquals(cert, TaskerForkIdentity.CERTIFICATE_SHA256)
        assertEquals(true, TaskerForkIdentity.isValid(TaskerForkIdentity.APPLICATION_ID, listOf(cert)))
        assertEquals(true, TaskerForkIdentity.isValid(TaskerForkIdentity.APPLICATION_ID, listOf(cert.uppercase())))
        assertEquals(false, TaskerForkIdentity.isValid("com.maxrave.simpmusic", listOf(cert)))
        assertEquals(false, TaskerForkIdentity.isValid(TaskerForkIdentity.APPLICATION_ID, emptyList()))
        assertEquals(false, TaskerForkIdentity.isValid(TaskerForkIdentity.APPLICATION_ID, listOf("wrong")))
        assertEquals(false, TaskerForkIdentity.isValid(TaskerForkIdentity.APPLICATION_ID, listOf(cert, "other")))
    }
    @Test
    fun autoplayRequiresResolvedIdentityReadinessAndIsConsumedOnce() {
        TaskerAutoplay.arm(TaskerAutoplay.Request("RDTM-one", "123"))
        assertEquals(false, TaskerAutoplay.consume(null, "RDTM-one", "RDTM-one", true))
        assertEquals(false, TaskerAutoplay.consume("123", "other", "other", true))
        assertEquals(false, TaskerAutoplay.consume("123", "RDTM-one", "old-queue", true))
        assertEquals(false, TaskerAutoplay.consume("123", "RDTM-one", "RDTM-one", false))
        assertEquals(true, TaskerAutoplay.consume("123", "VLRDTM-one", "RDTM-one", true))
        assertEquals(false, TaskerAutoplay.consume("123", "RDTM-one", "RDTM-one", true))
    }

    @Test
    fun cancelledOrRestoredRouteCannotAutoplayAndOldDisposalDoesNotCancelNewRequest() {
        TaskerAutoplay.arm(TaskerAutoplay.Request("one", "2"))
        TaskerAutoplay.cancel("1")
        assertEquals(true, TaskerAutoplay.consume("2", "one", "one", true))
        TaskerAutoplay.arm(TaskerAutoplay.Request("one", "3"))
        TaskerAutoplay.cancel()
        assertEquals(false, TaskerAutoplay.consume("3", "one", "one", true))
    }

    private fun candidate(id: String, title: String) = TaskerPlaylistRequest.Candidate(id, title)

    @Test
    fun acceptsStringAndIntegralIntentIdsWithoutLossyCoercion() {
        assertEquals("1791137806000", TaskerPlaylistRequest.validatedRequestId("1791137806000"))
        assertEquals("1791137806000", TaskerPlaylistRequest.validatedRequestId(1791137806000L))
        assertEquals("123", TaskerPlaylistRequest.validatedRequestId(123))
        assertNull(TaskerPlaylistRequest.validatedRequestId(123.5))
        assertNull(TaskerPlaylistRequest.validatedRequestId(true))
        assertNull(TaskerPlaylistRequest.validatedRequestId("%TIMEMS"))
        assertNull(TaskerPlaylistRequest.validatedRequestId(-1L))
        assertNull(TaskerPlaylistRequest.validatedRequestId(null))
    }

    @Test
    fun requestIdentityRejectsReplayInvalidAndUnboundedFutureValues() {
        assertEquals(true, TaskerPlaylistRequest.newRequestId("101", 100, 101))
        assertEquals(false, TaskerPlaylistRequest.newRequestId("100", 100, 101))
        assertEquals(false, TaskerPlaylistRequest.newRequestId("99", 100, 101))
        assertEquals(false, TaskerPlaylistRequest.newRequestId(null, 0, 101))
        assertEquals(false, TaskerPlaylistRequest.newRequestId("0", 0, 101))
        assertEquals(false, TaskerPlaylistRequest.newRequestId(Long.MAX_VALUE.toString(), 0, 101))
    }

    @Test
    fun validatesTypeAndLengthAndTrimsName() {
        assertNull(TaskerPlaylistRequest.validatedName(null))
        assertNull(TaskerPlaylistRequest.validatedName(12))
        assertNull(TaskerPlaylistRequest.validatedName("  "))
        assertNull(TaskerPlaylistRequest.validatedName("a".repeat(257)))
        assertEquals("a".repeat(256), TaskerPlaylistRequest.validatedName("a".repeat(256)))
        assertEquals("My Supermix", TaskerPlaylistRequest.validatedName(" My Supermix "))
    }

    @Test
    fun matchesCaseInsensitivelyWithoutFuzzyFallback() {
        val mix = candidate("RDTM-account-specific", "My Supermix")
        assertEquals(mix, TaskerPlaylistRequest.match("my supermix", listOf(mix)))
        assertNull(TaskerPlaylistRequest.match("supermix", listOf(mix)))
        assertNull(TaskerPlaylistRequest.match("My  Supermix", listOf(mix)))
        assertNull(TaskerPlaylistRequest.match("my supermix", emptyList()))
    }

    @Test
    fun exactCaseWinsBeforeCaseInsensitiveMatches() {
        val exact = candidate("one", "My Supermix")
        assertEquals(exact, TaskerPlaylistRequest.match("My Supermix", listOf(exact, candidate("two", "MY SUPERMIX"))))
    }

    @Test
    fun rejectsAmbiguousIdentitiesButDeduplicatesBrowsePrefix() {
        assertNull(TaskerPlaylistRequest.match("Mix", listOf(candidate("one", "Mix"), candidate("two", "Mix"))))
        val mix = candidate("RDTM-one", "Mix")
        assertEquals(mix, TaskerPlaylistRequest.match("Mix", listOf(mix, candidate("VLRDTM-one", " Mix "))))
    }
}
