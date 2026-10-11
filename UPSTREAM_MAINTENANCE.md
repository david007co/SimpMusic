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

## Revised target: useful automation in two phases

User prefers meaningful end-to-end routine automation, not merely moving local signing to GitHub. Temporary local memory pressure is not the motivation. Notification-only watcher is live; the following integration automation is a target, not yet implemented.

### Phase 1 — integrate, test, approve, release

On a new official stable release, trusted automation resolves/pins its app commit and Core gitlink, creates a separate integration branch from the maintained fork, attempts a normal merge and opens a PR. Conflicts stop without automatic resolution and produce actionable evidence. Successful integration gets secret-free tests and Android FOSS build; failed checks stop. Upstream workflow additions must be quarantined/reviewed before the candidate branch is pushed, and candidate code must not receive write credentials or signing secrets.

The maintainer reviews/merges the PR; accepted source triggers the release process. Automate explicit monotonic version allocation and display/tag naming as part of the reviewed change, with serialized release handling rather than trusting defaults. Protected approval gates signing, isolated verification creates a draft, maintainer publishes, Obtainium updates. Routine success should not require a local PC. Exception analysis and phone acceptance remain necessary. A clean merge plus unit tests does not prove Tasker/device behavior.

Implementation must explicitly handle GitHub's rule that events created by GITHUB_TOKEN usually do not trigger other workflows: run candidate checks within the orchestrated workflow or use a deliberately scoped GitHub App if separate PR checks are needed. No broad personal token merely to bypass that rule. Keep write-token orchestration separate from candidate-code execution. Restrict integration to the official source and maintained fork base, detect superseded base/releases and duplicate jobs, and keep workflows/signing policy controlled by trusted source rather than newly merged upstream files.

### Phase 2 — bounded LLM-assisted exception repair

For conflicts/failed checks, optionally send sanitized diff/failure evidence to an explicitly chosen API provider/model for analysis and a proposed branch patch. This is not access to the current Zed conversation: automation needs its own API credentials, instructions, isolated execution and cost limits. Provider choice, billing/data-sharing and activation require separate approval; no API key in chat or source.

Begin advisory-only. Later allow limited low-risk patch attempts on the candidate branch, bounded by file allowlist, attempt/time/token budget and deterministic checks. No production-branch write, workflow/identity/certificate/signing changes, arbitrary dependency or tool installation, credential access, environment approval or publication authority. Treat upstream files, issue bodies and logs as untrusted data, not instructions; prompt-injection defenses and sandboxing are needed. An API/model 'safe' verdict is not a security guarantee.

A successful bounded repair can resume secret-free checks and return to the normal human PR/signing/publication gates. Sensitive changes, uncertainty, failing checks or exhausted budget stop and notify the maintainer. Never weaken tests or bypass gates simply to make an update pass. No LLM decides alone that an APK is safe to sign/publish. Device-only failures may still require human reproduction.

### Current authorization boundary

This revised plan records the agreed direction, not deployment permission. Integration implementation, commits/pushes/settings, cloud-key upload and LLM/API access remain staged. Prepared local signing workflow is still unactivated and may need revision to fit accepted-source triggering/version allocation. Do not introduce signing or API secrets while testing integration orchestration.

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

## Prepared release workflow — not activated

`tasker-release.yml` is locally prepared for review, not committed/activated/tested on Actions. Manual dispatch accepts an explicit new versionCode (>3) and exact versionName already committed in the source. Both jobs are restricted to the maintained fork branch. Source checkout is the dispatch SHA with recursive submodules and no persisted credentials. The build installs the pinned-baseline SDK packages, runs nine focused tests and minified FOSS build, inspects metadata and uploads a run/attempt-specific unsigned APK with SHA256/source/Core evidence.

The fresh signing job has no checkout/Gradle/source scripts/cache. It installs tools and downloads only this run's artifact, then rechecks existing release APK codes and tag availability after approval. It requires environment secrets `TASKER_KEYSTORE_BASE64` and `TASKER_KEYSTORE_PASSWORD`, uses the existing PKCS12 alias, verifies artifact digest/metadata, aligns/signs, verifies single expected signer/v2/v3/alignment and creates a draft prerelease targeting the dispatch commit. Secrets are exposed only to the signing step; child inspection/alignment tools receive a scrubbed environment and only apksigner receives the password variable. Temporary key cleanup handles ordinary errors; abrupt cancellation relies on ephemeral runner disposal, not guaranteed secure erasure.

**Required before activation:** create and verify `tasker-release-signing` with reviewer david007co, exact allowed branch and bypass restrictions; simply referencing its name does NOT enforce approval. No repository signing secrets. An unprotected/missing environment is not an approval gate. Confirm cloud custody separately before privately uploading secrets. No keys/passwords in chat.

Version checks include all existing APK assets and drafts but cannot recover codes from deleted releases/assets or independently distributed APKs. Keep complete canonical release history and never delete previously distributed version evidence. Codes >3 are only the known baseline floor, not an authoritative future high-water mark. Workflow concurrency prevents its own overlaps, not manual publishers. Do not create competing manual releases/tags while a run waits/builds/signs. Check code/tag again when publishing a draft, which may have become stale. Tag checks do not reserve a tag; branch changes after dispatch do not change the selected SHA.

Actions are full-SHA pinned to verified official tag refs. No automatic merge or publication. Live Linux SDK provisioning, runner memory, API asset download behavior, environment gates and draft creation must be tested before claiming support. Next candidate would require a committed new suffix (e.g. tasker.3) and code >3; this preparation does not change app versions.

## Implemented Phase 1 slice — local, not activated

`upstream-integration.yml` orchestrates candidate preparation, optional `tasker-integration-review` approval for sensitive source/build changes, fresh read-only candidate checks and PR-result comment. It runs checks directly rather than relying on PR events generated by GITHUB_TOKEN. The trusted run SHA must equal current base; stale runs stop. Python script prepares merges in temporary bare Git repos, disables hooks/custom merge drivers, verifies fixed official Core pins and restores the exact trusted workflow subtree before pushing any candidate. No upstream workflow can be introduced into a candidate through this process. Conflicts record an issue without pushing conflict files. Duplicate/stale/modified candidates stop rather than force-push.

`fork-release.json` starts at accepted code 3 / tasker.2; Gradle reads it for release defaults. Allocator writes next code/display name into clean candidate PRs, requires official numeric tag/catalog agreement and stops on mismatch rather than downgrading a later dev version. Current v2.2.0 tree-equivalence case is a no-op and allocates nothing. Version state is a tracked floor, not a substitute for retained release history; release workflow rechecks actual APKs/tags and rejects stale state.

`tasker-release-request.yml` reacts to human-accepted branch changes to version state, reads the exact accepted SHA via API (no checkout), and explicitly dispatches the release workflow with that SHA/code/name. Code 3 initial baseline is intentionally ignored. Dispatch uses branch discovery but release run rejects SHA mismatch, preventing a branch-advance race from silently signing different source. No automatic PR merge. Bot acceptance using GITHUB_TOKEN would need explicit dispatch because push events are suppressed.

Integration APKs are unsigned validation-only code 1 and must never be published/installed as releases. PR comments include candidate SHA/run/result but are not enforceable required GitHub checks; review the actual run and matching PR SHA before acceptance. Build packages remain pinned to this baseline SDK; future SDK/nested Core changes stop or require reviewed workflow adaptation.

Activation requires separately authorized commit/push/settings. New automation is opt-in: repository Actions variables `TASKER_INTEGRATION_ENABLED` and `TASKER_RELEASE_ENABLED` must equal the exact string `true`; absent/other values skip entry jobs. Keep both unset until protections and settings are verified. The live notification watcher is independent of these switches. Uploading these workflows alone does not activate candidate preparation or signing. Create protected `tasker-integration-review` (no secrets) and `tasker-release-signing` environments with required reviewer and exact maintained-branch restriction. Missing protection would not enforce review. Repository must permit Actions to create PRs; currently that setting is unchecked. Decide/authorize this setting explicitly; it does not authorize automatic PR approval/merge in our code. No broad PAT needed. Retain read-only default token and job-scoped writes only.

Offline validation: 37 Python tests, workflow YAML/shell/Python syntax checks passed. Gradle :androidApp:testDebugUnitTest :androidApp:tasks passed after JSON version configuration change (1m52s). Full rebuilt release after this change and live hosted workflow behavior remain unvalidated. All workflows/source/docs for this slice remain local/uncommitted; no settings/key upload/device install/publication.

## Sources

- https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
