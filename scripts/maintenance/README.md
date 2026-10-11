# Phase 1: candidate-only upstream orchestration

Local implementation, not activated. All changes for this step live in this directory.
Existing uncommitted maintenance docs and `tasker-release.yml` are untouched.

## Run

Requires Python 3.9+, Git 2.38+ (`merge-tree --write-tree`), and GitHub CLI `gh`.
Designed for an ephemeral GitHub-hosted Linux runner; offline tests also pass on
Windows with Git 2.55. No third-party Python dependencies.

```sh
python3 -B -m unittest discover -s scripts/maintenance -p 'test_*.py' -v
python3 -B scripts/maintenance/upstream_integration.py
```

Default mode reads GitHub/public Git, prepares temporary objects, prints JSON and
appends statuses/pins to `GITHUB_OUTPUT` when set. It performs **no remote writes**.
Do not point `GITHUB_OUTPUT` at a file you do not intend to append to.

`--apply` explicitly enables ordinary fork branch push, PR creation, or a conflict
issue. Run it only after separately authorized deployment. Supply a narrowly scoped
`GH_TOKEN` (fallback `GITHUB_TOKEN`) to the trusted orchestrator process only. GitHub
CLI is invoked with explicit fork repository/base/head (PR creation uses the fork
REST endpoint with explicit base/head). No auto-merge, production push, force push,
signing, release, tool installation, version change or candidate execution occurs.

## Trusted caller requirements

- Load this script from reviewed trusted source, never from a candidate checkout.
- Serialize all integration jobs using one workflow concurrency group, without
  cancelling an in-progress write. No workflow is added in this scoped change.
- Restrict writes to `david007co/SimpMusic` and PR base
  `feature/tasker-playlist-intent`; official source is `maxrave-dev/SimpMusic`.
- Grant contents/PR/issues writes only to orchestration. Default GitHub token PR
  creation may require a separately authorized repository setting. No broad PAT
  is needed just to bypass GitHub's event suppression.
- Any future build must use a **separate fresh secret-free runner/job**, exact
  `candidate_sha`, no write token/signing secrets/persisted checkout credentials,
  and the trusted workflow. Do not run candidate code inside this process/job.
- Only consider a build when both `ready=true` and `build_allowed=true` and the
  orchestrator job succeeded. These flags indicate preparation/policy eligibility,
  **not tests passed, release-ready or a security certification**.
- Build execution and its trigger/event-suppression handling are not implemented.
  A `GITHUB_TOKEN`-created PR usually does not trigger other workflows.

## Pins, merge and quarantine

Reads latest published stable metadata using `gh api`, resolves the tag to an
exact commit, fetches the tag anonymously and requires API/fetch agreement. Uses
the current fork base SHA, records merge-base and exact official Core gitlink.
If merge-base and official release have identical trees, skips integration even
when release history is not an ancestor (the inspected v2.2.0 case). No release
reset or Core downgrade is performed for that no-op case.

Preparation is in disposable bare repos. No worktree/candidate scripts, Git hooks,
filters, recursive submodule commands, external merge driver, signing commands or
GitHub actions execute. Git environment/config is isolated, templates empty,
hooks disabled (`/dev/null` on Linux), and highest-priority attributes force normal
text merge instead of candidate-selected custom/union merge drivers. No custom
conflict resolution is attempted. Conflicts fail with false readiness/build flags;
`--apply` records a deduplicated actionable issue, never pushes a conflict tree.

After the merge, replaces the entire `.github/workflows` subtree using the exact
trusted base, including removal of upstream additions and restoration of deleted
files. Verifies workflow diff is empty **before pushing**. PR evidence lists upstream
and merged workflow changes even though they were quarantined. Workflow changes,
`.gitmodules`, Core gitlink, attributes, Gradle files/catalog/wrapper/build logic,
and maintenance scripts conservatively require review and block automatic build.
Both merge-base→release and base→candidate diffs inform the gate.

Fetches official and candidate Core pins from fixed public `maxrave-dev/core`,
without following candidate `.gitmodules` URLs or fetching submodule descendants.
Future builds must revalidate Core/submodule URL policy and nested modules; this
script only proves exact top-level Core commit availability. Candidate source may
still contain malicious code/dependencies even if no sensitive path was changed.

Branch: `automation/upstream-<releaseID>-<officialSHA12>`. Commit has ordered exact
base/release parents, stable message and fixed author/timestamp, making reruns
identical for identical inputs under the same Git merge implementation. No remote
ref or credentials are written to disk. Existing branch requires both pinned base
and upstream ancestry **and exact candidate SHA**; extra commits/stale bases stop
for review. Closed/merged/mismatching existing PRs stop. Fresh base/latest release
are checked before writes, but no API can eliminate a subsequent manual-write race;
serialization and no competing publishers remain caller requirements.

Git fetch/ls-remote use fixed public HTTPS URLs and scrubbed environment. Only the
push subprocess receives a process-local authentication header; no token in URLs,
arguments, repository config, candidate environment or output. `gh` receives the
token for its own API process. Errors intentionally do not echo child stderr to
avoid accidental credential logging. Temporary objects are removed on normal exit;
abrupt termination relies on ephemeral runner disposal.

## Outputs and exits

JSON stdout plus one-line safe `GITHUB_OUTPUT` fields:

- `status`: `no_upstream_tree_changes`, `ready`, `review_required`, `conflict`, `failed`
- `ready`, `build_allowed`, `review_required`: lowercase booleans
- `base_sha`, `release_sha`, `release_id`, `release_tag`, `merge_base_sha`
- `release_core_sha`, `candidate_sha`, `candidate_core_sha`, `candidate_branch`
- structured JSON `quarantined_workflows`, `sensitive_changes`, conflict evidence
- `pr_number` after successful apply; `error` on failure

No-op has no candidate and both readiness/build flags false. A prepared candidate
requiring review has `ready=true`, `build_allowed=false`. Conflicts and errors exit
1; no-op/successful preparation exit 0. Any failed write/recheck also clears flags.
Structured/multiline data is JSON escaped to prevent output-command injection.

## Version policy deliberately deferred

No `fork-release.json` is invented or edited and no version code/name is allocated.
Candidates must not be published with default code 1 or a reused accepted version.
Parent/orchestrator coordination must first approve an authoritative tracked
high-water mark (last accepted code/name and official baseline), reconcile every
previously distributed APK code including non-GitHub/deleted releases, and define
serialized reservation/acceptance semantics. Current release evidence says code 3
was accepted, but that is not an authoritative future maximum. Allocating versions
or enabling accepted-source release flow is a separate step.

## Validation record

Offline unittest suite uses real temporary Git repos plus mocked GitHub metadata,
fetch remapping, pushes, PRs and issues. Covers divergent-history/tree-equivalence
skip, source pins, clean merge, Core/build gates, exact workflow quarantine,
conflicts/issues/dedup, malicious union attributes, deterministic reruns, existing
branch ancestry/exact SHA, stale release, API/tag mismatch and output/environment
hardening. No maintained Git metadata mutation, real push or GitHub write API call
is used in tests. Hosted-runner/live read/write integration remains unvalidated.
