package com.maxrave.simpmusic

/** Independent fork identity, not an assertion that this is an official upstream build. */
internal object TaskerForkIdentity {
    const val APPLICATION_ID = "io.github.david007co.simpmusic"
    const val CERTIFICATE_SHA256 = "22aad284a1b3eb1aaf6494238eb61a2cf74bacecbd3f63b89721718db12820b3"

    fun isValid(packageName: String, certificates: List<String>): Boolean =
        packageName == APPLICATION_ID && certificates.size == 1 &&
            certificates.single().equals(CERTIFICATE_SHA256, ignoreCase = true)
}
