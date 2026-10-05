# Upstream releases and signing policy

## Status

Foreground Tasker behavior and actual Obtainium update to tasker.2/code 3 are user-confirmed. Latest stable official release inspected is v2.2.0; local tag resolves to bdf28a835acdd2cc6310cea4a763abc68640ae24. Do not replace our newer dev-based baseline with the release tree or assume equal display versions mean equal source.

The local `upstream-release-watch.yml` is a daily/manual, secret-free **notification workflow**, not an automatic merger. It checks the latest stable official release, resolves app commit/Core gitlink and checks ancestry against the fork default branch. It creates one review issue per release ID/commit when integration is needed. It never checks out upstream code, changes branches, builds, signs or publishes. API errors fail rather than assuming success. Rewritten tags produce a different marker. It does not enumerate every intermediate release or detect asset-only changes.

## Activation gates

1. Review and separately authorize commit/push of the watcher/docs.
2. Change the fork default branch from inherited dev to **feature/tasker-playlist-intent**, preserving inherited branches (no merge/force push needed). Scheduled/manual workflow discovery requires the default branch to contain the workflow.
3. Enable Issues in repository Settings → General → Features (fork currently has Issues disabled).
4. Review inherited active workflows on OTHER branches before enabling repository Actions. If Actions must be enabled before accessing workflow controls, avoid pushes/PR activity during activation and immediately disable inherited workflow IDs in the GitHub UI; verify only the intended watcher remains enabled. Do not manually dispatch inherited workflows. Our fork branch preserves them as .yml.disabled. Keep Actions token defaults read-only and PR approval/creation disabled; watcher needs only explicit issues:write and contents:read.
5. Enable Actions for the reviewed fork workflows and manually run Watch official releases once. Confirm latest-release ancestry result or issue metadata, then validate daily scheduling. Fork schedules can be disabled after 60 days of repository inactivity; check periodically.

Local ancestry review confirms v2.2.0 is not an ancestor of the current fork HEAD, so the initial run is expected to open a review issue even though our baseline was taken from later dev code. Review that divergence; do not treat it as a downgrade request.

No GitHub settings changed by the local implementation. A successful local check is not proof that Actions is active.

## Reviewed integration procedure

For a reported release, fetch its exact official tag and verify app commit against the issue. Prepare a separate integration branch based on the current fork branch, then merge the resolved commit with no automatic conflict resolution. Retain fork customizations; a Git merge preserves changes only when compatible, not by guarantee. Inspect all changes to Tasker entry points/consent/request IDs, playlist route/readiness/PlayAll, queue/restore, identity/certificate pin and updater guard.

Review build scripts, wrapper, dependencies, .gitmodules and workflow changes **before executing any code**. Newly introduced upstream workflows must not become active by accident. Fetch the exact accepted Core gitlink; do not update Core to a moving head. Test/build without signing secrets or a write token. For an automated build job, use an ephemeral GitHub-hosted runner, read-only token, no signing secrets and no credential-persisting checkout. Initial builds remain local until CI configuration is separately reviewed/tested.

Open a PR to the fork branch, never the official repository by mistake. Require focused tests, minified Android FOSS release build and review of sensitive changes; conflicts or failed checks stop the process. Do not enable auto-merge. Device checks should cover exact playlist replacement, manual navigation, no-match/cancel and update continuity. Review alone cannot guarantee playback compatibility across upstream changes.

After approval, assign an increasing fork versionCode (next >3) and distinct display/tag version. Sign accepted APK with the same permanent key, verify metadata/signature/alignment/hash, publish one predictable universal APK and source commit evidence. Obtainium follows fork Releases, not upstream source directly.

## GitHub signing: benefit and risk

Benefit: no local password prompt/build-PC dependency for each release; consistent post-approval signing and draft-release upload. Risk: key/password must be available in plaintext to the signing process on a runner. Secrets storage/log masking are safeguards, not proof that workflow code cannot steal the key. Base64 is encoding, not encryption. Repository writers, compromised account/workflows/actions and malicious build dependencies are relevant threats.

This is a permanent APK signer, not an easily disposable API token. Exposure can enable malicious updates; rotating the key is not a simple drop-in recovery, especially with the app's single-certificate pin. Keep the recoverable local/Bitwarden backups. Do not generate a replacement key for CI.

Recommended optional design:

- Manual dispatch from the trusted fork default branch only; review upstream integration first.
- Separate secret-free build job and **fresh isolated signing job**. Signing job must never run Gradle, upstream build scripts, or scripts downloaded from the candidate source. Use reviewed workflow-contained signing commands and verified artifact/run/commit/digest linkage.
- Protected `tasker-release-signing` environment; exact allowed fork branch; required reviewer david007co; disallow admin bypass where supported. For a sole maintainer initiating runs, self-review prevention must remain off or a second reviewer is needed. Approval is a gate, not independent two-person review.
- Key/password stored only as environment secrets; no repository-wide signing secrets. GitHub Free supports required reviewers/environment secrets for public repositories per current docs; verify available settings in this account.
- Minimal permissions, full-SHA-pinned actions, no pull_request_target/untrusted workflow_run path, no signing caches, no self-hosted runner. Do not include checkout/build tooling in signing job unless strictly needed and reviewed.
- Verify single expected certificate, package, nondebug universal APK, increasing code, version, alignment and artifact digest. Create a **draft** release first; publication remains a separate reviewed action.
- Never print/decode secrets in logs, pass passwords as literal arguments, or upload temporary key/password files; clean them even on failure. GitHub logs do not reliably mask transformed secret bytes.

**Decision pending:** user is considering CI signing; no authorization to upload signing material, create secret values, configure environments or enable automatic publication has been given. Do not ask for key/password in chat. Implementing notification does not authorize cloud signing.

## Sources

- https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
