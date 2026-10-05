param(
    [Parameter(Mandatory = $true)][string]$UnsignedApk,
    [string]$Keystore = (Join-Path $env:USERPROFILE '.android-signing\SimpMusicTasker\release.p12'),
    [string]$BuildTools = 'C:\Android\Sdk\build-tools\36.0.0'
)
$ErrorActionPreference = 'Stop'
$inputApk = (Resolve-Path -LiteralPath $UnsignedApk).Path
$directory = Split-Path -Parent $inputApk
$output = Join-Path $directory 'SimpMusic-Tasker-universal-release.apk'
$aligned = Join-Path $directory 'SimpMusic-Tasker-aligned.apk'
$expectedCertificate = '22aad284a1b3eb1aaf6494238eb61a2cf74bacecbd3f63b89721718db12820b3'
if ($expectedCertificate -notmatch '^[0-9a-f]{64}$') { throw 'Invalid pinned SHA-256 fingerprint.' }
if (!(Test-Path -LiteralPath $Keystore)) { throw 'Permanent signing keystore not found.' }
if ($inputApk -eq $output) { throw 'Input must be the unsigned Gradle output, not the signed artifact.' }
if ((Test-Path -LiteralPath $output) -or (Test-Path -LiteralPath $aligned)) {
    throw 'Signing output already exists. Archive/remove that generated output deliberately before rerunning.'
}
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-21.0.6.7-hotspot'
$badging = & (Join-Path $BuildTools 'aapt.exe') dump badging $inputApk 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect input APK.' }
$metadata = $badging -join "`n"
if ($metadata -notmatch "package: name='io.github.david007co.simpmusic' versionCode='([1-9][0-9]*)'" -or
    $metadata.Contains('application-debuggable') -or
    !$metadata.Contains("application-label:'SimpMusic Tasker'") -or
    !$metadata.Contains("native-code: 'arm64-v8a' 'armeabi-v7a' 'x86_64'")) {
    throw 'Input must be the non-debuggable SimpMusic Tasker universal release with a positive version code.'
}
Write-Host ($badging | Select-Object -First 1)
& (Join-Path $BuildTools 'zipalign.exe') -P 16 -f 4 $inputApk $aligned
if ($LASTEXITCODE -ne 0) { throw 'APK alignment failed.' }
Write-Host 'Enter the keystore password only at the apksigner prompt. It is not stored by this script.'
& (Join-Path $BuildTools 'apksigner.bat') sign --ks $Keystore --ks-type PKCS12 --ks-key-alias simpmusic-tasker --out $output $aligned
if ($LASTEXITCODE -ne 0) { throw 'APK signing failed; do not distribute the output.' }
$verification = & (Join-Path $BuildTools 'apksigner.bat') verify --verbose --print-certs $output 2>&1
if ($LASTEXITCODE -ne 0) { throw 'APK signature verification failed.' }
$verification | Write-Host
if (!(($verification -join "`n").ToLowerInvariant().Contains("certificate sha-256 digest: $expectedCertificate"))) {
    throw 'Unexpected signer. Do not install/distribute this output.'
}
& (Join-Path $BuildTools 'zipalign.exe') -c -P 16 4 $output
if ($LASTEXITCODE -ne 0) { throw 'Signed APK alignment verification failed.' }
$signedBadging = & (Join-Path $BuildTools 'aapt.exe') dump badging $output 2>&1
if ($LASTEXITCODE -ne 0 -or ($signedBadging -join "`n") -ne $metadata) {
    throw 'Signed APK metadata differs from the validated input. Do not distribute.'
}
Remove-Item -LiteralPath $aligned
Get-FileHash -LiteralPath $output -Algorithm SHA256 | Format-List
Write-Host "Verified signed APK: $output"
