# SimpMusic Tasker fork — agent instructions

Read `FORK.md` before proposing changes. This file overrides upstream agent guidance where it conflicts. Preserve upstream attribution/license and shared module boundaries.

## Scope and source

- Android-only, minimal foreground Tasker playlist-name intent. Use existing Mix for you lookup and exact `PlaylistUIEvent.PlayAll`; never generic old-queue resume, UI automation or a second player/network stack.
- Normal manual navigation must not autoplay. Preserve opt-in, request-ID deduplication, matching first-page readiness and resumed lifecycle checks. Failed/cancelled requests must leave playback untouched.
- Screen-off/headless support is deferred, not an invitation to expand Core. Do not instantiate UI ViewModels for services.
- Baseline app `62e0073ba818d899b22c75909deb9b034516d5db`, Core `d90b53fbad07ab73cecbfe89b33b533fb9ca78ed`. Verify actual revisions/status before editing; Core is unchanged. Never silently switch to upstream HEAD or update the gitlink.

## Release safety

- Stable release identity: SimpMusic Tasker / `io.github.david007co.simpmusic`; debug identity unchanged. Keep exact single-certificate pin and fork upstream-updater guard.
- Never regenerate the maintainer's signing key. No credentials, cookies, keystores, local.properties, crash logs or generated APKs in Git. Signing password is entered privately, never in arguments/logs/chat.
- Set an explicit increasing `-PforkVersionCode=N` for releases; default code 1 is not safe for future publication. Archive accepted APKs outside Gradle build outputs.
- Nine Android tests/release build passed; foreground release autoplay and same-key 1 → 2 update/data continuity user-confirmed. Obtainium delivery, screen-off, recreation/restore overlap and release-specific safety retests are not all validated.
- Inherited workflows are `.yml.disabled` in this branch. Do not enable them unreviewed. Planned upstream-release integration is review/test-gated; automation/publication and CI signing custody remain unconfigured.

## Working practices

- Use editor search/read tools first; use terminal for Git/build/test/device tasks.
- Prefer short Windows paths, native JDK 21 and Gradle wrapper. FOSS property is `-PisFullBuild=false`; do not invent flavors. Use tasks from FORK.md; release R8 needed 4GiB heap and one worker.
- Preserve user work. Commit/push/branch/remote changes, device install and publication require authorization for the step. Record evidence and outstanding checks honestly; do not claim device behavior from a build alone.
- Upstream CLAUDE.md is retained as architecture guidance, not a substitute for source verification or these fork rules.
