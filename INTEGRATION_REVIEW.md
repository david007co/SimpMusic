# Official v2.3.0 integration candidate

## Status — 2026-10-11

Authorized isolated candidate branch: `integration/v2.3.0-review`. Candidate commit/push/PR preparation authorized after local validation. Maintained checkout remains on the base below with its old Core unchanged. This document records pre-publication validation; no production-branch merge, signing, installation or release publication has occurred.

Latest stable official release verified through GitHub releases/latest: v2.3.0, release ID 409100331. Automation already selects the latest published stable release, then pins its app commit and Core gitlink; it does not integrate a moving dev head. Recheck latest release/base before remote acceptance.

- Fork base: `fbc0dec2181d2dbd6ee010e4de8d8822cf27c514`
- Official app: `f037043d714450bac5aaac2f9dbf77e17b019303`
- Official/candidate Core: `b9f4ceac52e7c25cb059ea78141784dc164e0161`
- Previous/maintained Core: `d90b53fbad07ab73cecbfe89b33b533fb9ca78ed`
- Proposed release: `2.3.0-tasker.1`, code `4`. Not reserved; release history must be checked before signing/publication.

## Preservation and resolution

Read-only checks found no unstaged/untracked workflow edits. All four active fork workflows matched trusted base in both working tree and index. Only three inherited disabled workflows had upstream merge changes. User separately approved restoring the entire candidate workflow directory to trusted base and initializing exact Core. Operation succeeded; staged and working-tree workflow comparisons are empty. No maintained-checkout files changed.

Only content conflict: SharedViewModel.checkForUpdate. Retained fork configuration/certificate UI gate, early fork updater toast/return and automatic-updater suppression. Retained upstream pre-coroutine checking flag and completion reset after the fork early return. Conflict marked resolved; no unmerged paths remain.

App review: MainActivity/playlist ViewModel PlayAll unchanged by upstream; PlaylistScreen changes are palette/image transitions, preserving Tasker readiness/resumed/one-shot dispatch. App navigation/UI changed upstream, requiring device acceptance despite successful merge/build. Build changes include Gradle 9.8.1, AGP 9.4.1, dependency updates and new vivo module; build targets only androidApp, not vivo/desktop. Existing release identity, JSON version wiring and tests retained.

Core read-only review found no change to Mix-for-you lookup, personalized mix first-page path or existing reset/set/load contract. Queue shuffle ordering, media-source/offline behavior and logging changed. Saved-queue restore and catalog/continuation ownership remain inherited concurrency hypotheses, not reproduced failures or newly established readiness guarantees. Screen-off support stays deferred; no Core customization made.

## Validation

- Maintenance: `python -B -m unittest discover -s scripts/maintenance -p 'test_*.py'`: 37 passed.
- Windows JDK21: `gradlew.bat :androidApp:testDebugUnitTest :androidApp:assembleRelease -PisFullBuild=false --console=plain --max-workers=1 -Dorg.gradle.jvmargs=-Xmx4096m`: BUILD SUCCESSFUL in 24m39s, 663 tasks executed.
- Fresh Android XML: 9 tests, zero failures/errors/skips.
- R8/minified unsigned release and release vital lint completed.
- APK inspected with SDK aapt: label SimpMusic Tasker, package io.github.david007co.simpmusic, code4/name2.3.0-tasker.1, min26/target36, universal arm64-v8a/armeabi-v7a/x86_64; no application-debuggable flag reported.
- Unsigned universal SHA256: `773b553d608f6611ecfa2cdd98cadf405c719b2c9f4af026117346053400f1f7`.
- Output: `androidApp/build/outputs/apk/release/androidApp-universal-release-unsigned.apk`. Unsigned, do not install/publish.
- Candidate Core clean/exact pin; workflow equality, no unmerged paths and unstaged diff --check passed. Maintained checkout clean at base, Core old pin unchanged.
- Gradle emitted upstream deprecation warnings; no warning-suppression changes made.

## Remaining gates

1. Candidate commit/push/PR preparation authorized; review the resulting exact PR head and do not merge the maintained branch before acceptance.
2. Existing automation rejects branches that differ from its deterministic clean-merge candidate. This manual conflict repair cannot be blindly fed back into the automatic prepare path. Decide a SHA-pinned reviewed-candidate check route rather than weakening verification or force-pushing.
3. Hosted checks/signing flow remains unvalidated; cloud signing custody/environment and release activation remain separate approvals.
4. Device acceptance: warm-foreground exact queue replacement, manual navigation, no-match/consent-cancel/background cancellation; repeat with shuffle/crossfade/continuation where practical. Cold-start restore overlap/recreation remain unaccepted unless separately tested.
5. Sign only accepted source with existing permanent key, verify metadata/certificate/alignment, draft and publish only after approval. Obtainium delivery requires an actual signed update test. Code4/name proposal is not proof of unused release history.
