#!/usr/bin/env python3
"""Trusted, candidate-only orchestration. Never check out or execute candidate files."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
from urllib.parse import quote

from release_version import allocate

OFFICIAL = "maxrave-dev/SimpMusic"
FORK = "david007co/SimpMusic"
BASE = "feature/tasker-playlist-intent"
CORE = "https://github.com/maxrave-dev/core.git"
SHA = re.compile(r"[0-9a-f]{40}\Z")


class Stop(RuntimeError):
    pass


def sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise Stop("Expected an exact 40-character commit SHA")
    return value


def sensitive(path):
    """Conservative gate, not a claim that other source is safe to execute."""
    return (path in {".gitmodules", ".gitattributes", "core"} or
            path.startswith(("gradle/", "buildSrc/", "build-logic/", "scripts/", ".github/")) or
            Path(path).name in {"gradlew", "gradlew.bat", "gradle.properties"} or
            path.endswith((".gradle", ".gradle.kts")))


class Commands:
    def __init__(self, home):
        # No inherited Git config, credentials, SSH, external diff/filter/merge drivers,
        # templates, signing config or candidate-controlled executable on PATH.
        self.env = {k: os.environ[k] for k in
                    ("PATH", "SYSTEMROOT", "WINDIR", "TMP", "TEMP") if k in os.environ}
        self.env.update(HOME=str(home), XDG_CONFIG_HOME=str(home),
                        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1",
                        GIT_ATTR_NOSYSTEM="1",
                        GIT_AUTHOR_NAME="SimpMusic maintenance",
                        GIT_AUTHOR_EMAIL="maintenance@users.noreply.github.com",
                        GIT_COMMITTER_NAME="SimpMusic maintenance",
                        GIT_COMMITTER_EMAIL="maintenance@users.noreply.github.com",
                        GIT_AUTHOR_DATE="2000-01-01T00:00:00Z",
                        GIT_COMMITTER_DATE="2000-01-01T00:00:00Z")

    def run(self, args, cwd=None, data=None, check=True, env=None):
        result = subprocess.run(args, cwd=cwd, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env or self.env, timeout=180)
        if check and result.returncode:
            # Do not echo stderr: authenticated Git may include credential material.
            raise Stop(f"{args[0]} {args[1]} failed (exit {result.returncode})")
        return result

    def git(self, repo, *args, data=None, check=True, write=False):
        env = self.env.copy()
        if write:
            token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
            if not token:
                raise Stop("--apply requires GH_TOKEN (or GITHUB_TOKEN)")
            header = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            # Process-local config only; neither token nor header is persisted to disk.
            env.update(GIT_CONFIG_COUNT="1",
                       GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                       GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {header}")
        return self.run(["git", "--no-pager", "-c", f"core.hooksPath={os.devnull}",
                         "-c", "credential.helper=", "-c", "protocol.file.allow=never",
                         "-c", "protocol.ext.allow=never", "-c", "core.attributesFile=" + os.devnull,
                         *args], repo, data, check, env)

    def gh(self, *args):
        env = self.env.copy()
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            env["GH_TOKEN"] = token
        env["GH_PROMPT_DISABLED"] = "1"
        env["GH_HOST"] = "github.com"
        raw = self.run(["gh", *args], env=env).stdout
        return json.loads(raw) if raw.strip() else None

    def api(self, endpoint):
        return self.gh("api", endpoint)


def latest(commands):
    release = commands.api(f"repos/{OFFICIAL}/releases/latest")
    if (release.get("draft") or release.get("prerelease") or
            type(release.get("id")) is not int or release["id"] <= 0):
        raise Stop("Latest release is not a stable published release")
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not tag or any(ord(c) < 32 for c in tag):
        raise Stop("Invalid release tag")
    commit = sha(commands.api(f"repos/{OFFICIAL}/commits/{quote(tag, safe='')}")["sha"])
    return release, commit


def text(commands, repo, *args, data=None):
    return commands.git(repo, *args, data=data).stdout.decode().strip()


def paths(commands, repo, before, after):
    return commands.git(repo, "diff", "--name-only", "-z", before, after).stdout.decode().split("\0")[:-1]


def core_pin(commands, repo, revision):
    entries = commands.git(repo, "ls-tree", revision, "--", "core").stdout.decode().strip().split()
    if len(entries) != 4 or entries[:2] != ["160000", "commit"] or entries[3] != "core":
        raise Stop("Expected core to be an exact gitlink")
    return sha(entries[2])


def quarantine(commands, repo, tree, base):
    """Replace the entire workflows subtree in an isolated index, without checkout."""
    commands.git(repo, "read-tree", tree)
    entries = commands.git(repo, "ls-files", "-z", "--", ".github/workflows").stdout
    if entries:
        removals = b"".join(b"0 " + b"0" * 40 + b"\t" + path + b"\0"
                            for path in entries.split(b"\0") if path)
        commands.git(repo, "update-index", "-z", "--index-info", data=removals)
    trusted = commands.git(repo, "ls-tree", "-r", "-z", base, "--", ".github/workflows").stdout
    if trusted:
        commands.git(repo, "update-index", "-z", "--index-info", data=trusted)
    result = text(commands, repo, "write-tree")
    if paths(commands, repo, base, result) and any(
            p == ".github/workflows" or p.startswith(".github/workflows/")
            for p in paths(commands, repo, base, result)):
        raise Stop("Workflow quarantine verification failed")
    return result


def issue(commands, body, marker):
    found = commands.gh("issue", "list", "--repo", FORK, "--state", "all",
                        "--search", marker, "--json", "number,body")
    if not any(marker in item["body"] for item in found):
        commands.gh("api", f"repos/{FORK}/issues", "--method", "POST",
                    "-f", "title=Upstream integration conflict requires review",
                    "-f", "body=" + body)


def allocate_candidate_version(commands, repo, tree, base, tag, output):
    """Use trusted base state only; release workflow revalidates published APKs.

    No release API history is inferred here. The tracked state is the allocation
    floor, not a reservation or proof that this code/name has never been used.
    """
    try:
        if not re.fullmatch(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", tag):
            raise ValueError("Official release tag must be canonical vX.Y.Z")
        def source(revision, path):
            entry = text(commands, repo, "ls-tree", revision, "--", path).split()
            if len(entry) != 4 or entry[:2] != ["100644", "blob"] or entry[3] != path:
                raise ValueError(f"Missing or non-regular source file: {path}")
            return text(commands, repo, "show", f"{revision}:{path}")

        state = json.loads(source(base, "fork-release.json"))
        catalog = tomllib.loads(source(tree, "gradle/libs.versions.toml"))
        version = catalog.get("versions", {}).get("version-name")
        if version != tag[1:]:
            raise ValueError(f"Merged source version {version!r} differs from official tag {tag}; no downgrade")
        # The state is authoritative for this candidate. External APK/history
        # scans belong to the release workflow, which must reject stale/reused codes.
        allocated = allocate(state, tag, maximum_code=0)
    except (ValueError, TypeError, AttributeError, Stop) as error:
        output.update(status="review_required", review_required="true")
        raise Stop(f"Version allocation requires review: {error}") from error
    blob = sha(text(commands, repo, "hash-object", "-w", "--stdin",
                    data=(json.dumps(allocated, indent=2) + "\n").encode()))
    commands.git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},fork-release.json")
    output.update(version_code=str(allocated["version_code"]), version_name=allocated["version_name"])
    return text(commands, repo, "write-tree")


def prepare(commands, repo, release, upstream, base, output):
    output.update(base_sha=base, release_sha=upstream, release_id=str(release["id"]),
                  release_tag=release["tag_name"], release_core_sha=core_pin(commands, repo, upstream))
    common = text(commands, repo, "merge-base", base, upstream)
    output["merge_base_sha"] = common
    # The official v2.2.0 has different history but no missing tree content.
    if not paths(commands, repo, common, upstream):
        output["status"] = "no_upstream_tree_changes"
        return None
    branch = f"automation/upstream-{release['id']}-{upstream[:12]}"
    output["candidate_branch"] = branch
    merge = commands.git(repo, "merge-tree", "--write-tree", base, upstream, check=False)
    if merge.returncode == 1:
        output.update(status="conflict", review_required="true")
        # NUL parsing is unnecessary here: JSON/PR bodies treat this as evidence,
        # never as commands. Limit evidence and escape it via JSON rendering.
        output["conflict_evidence"] = merge.stdout.decode(errors="replace")[:24000]
        return None
    if merge.returncode:
        raise Stop("git merge-tree failed; no candidate prepared")
    tree = sha(merge.stdout.decode().splitlines()[0])
    workflow_changes = [p for p in paths(commands, repo, common, upstream)
                        if p == ".github/workflows" or p.startswith(".github/workflows/")]
    # Include merged workflow changes as well, for a complete quarantine audit.
    workflow_changes = sorted(set(workflow_changes + [p for p in paths(commands, repo, base, tree)
                               if p == ".github/workflows" or p.startswith(".github/workflows/")]))
    output["quarantined_workflows"] = workflow_changes
    tree = quarantine(commands, repo, tree, base)
    tree = allocate_candidate_version(commands, repo, tree, base, release["tag_name"], output)
    candidate = text(commands, repo, "commit-tree", tree, "-p", base, "-p", upstream,
                     data=f"Prepare official release {release['id']} ({upstream})\n".encode())
    output.update(candidate_sha=sha(candidate), candidate_core_sha=core_pin(commands, repo, candidate))
    # Changes introduced upstream still need review even if Git retained a newer
    # fork-side build file/core pin and the final candidate diff is empty there.
    changes = set(paths(commands, repo, common, upstream) + paths(commands, repo, base, candidate))
    output["sensitive_changes"] = sorted(p for p in changes if sensitive(p))
    review = bool(output["sensitive_changes"])
    output.update(status="review_required" if review else "ready", ready="true",
                  review_required=str(review).lower(), build_allowed=str(not review).lower())
    return candidate


def evidence(output):
    return ("Candidate only: no build, signing, publication or automatic merge.\n"
                "Version allocation uses the tracked base-state floor only; the release workflow must reject stale/reused codes and names.\n"
            "Workflow changes were quarantined to the exact trusted base subtree.\n"
            "Review Tasker behavior, identity and playback even when build_allowed=true.\n\n"
            "```json\n" + json.dumps(output, indent=2, ensure_ascii=True) + "\n```\n")


def publish(commands, repo, output, release, upstream, base):
    # Recheck public inputs immediately before writing; serialization is required
    # in the caller. The API cannot eliminate a race after this check.
    current_release, current_upstream = latest(commands)
    current_base = sha(commands.api(f"repos/{FORK}/commits/{quote(BASE, safe='')}")["sha"])
    if (current_release["id"], current_upstream, current_base) != (release["id"], upstream, base):
        raise Stop("Base or official release changed; rerun from fresh pins")
    if output["status"] == "conflict":
        marker = f"upstream-conflict-{release['id']}-{upstream}-{base}"
        issue(commands, marker + "\n\n" + evidence(output) +
              "\nResolve manually on a separate reviewed branch; no conflict tree was pushed.", marker)
        raise Stop("Merge conflicts: review issue recorded, no push")
    branch = output["candidate_branch"]
    ref = "refs/heads/" + branch
    url = f"https://github.com/{FORK}.git"
    remote = text(commands, repo, "ls-remote", "--heads", url, ref)
    if remote:
        existing = sha(remote.split()[0])
        commands.git(repo, "fetch", "--no-tags", url, ref)
        for ancestor in (base, upstream):
            if commands.git(repo, "merge-base", "--is-ancestor", ancestor, existing, check=False).returncode:
                raise Stop("Existing candidate has mismatching base/upstream ancestry")
        if existing != output["candidate_sha"]:
            raise Stop("Existing branch is not the exact deterministic candidate; manual review required")
    else:
        # Ordinary push, never forced. Another creator must not be overwritten.
        commands.git(repo, "push", url, output["candidate_sha"] + ":" + ref, write=True)
    prs = commands.gh("pr", "list", "--repo", FORK, "--base", BASE, "--head", branch,
                      "--state", "all", "--json", "number,state,headRefOid")
    if prs:
        if len(prs) != 1 or prs[0]["state"] != "OPEN" or prs[0]["headRefOid"] != output["candidate_sha"]:
            raise Stop("Existing PR is closed, merged or has a different candidate")
        output["pr_number"] = str(prs[0]["number"])
    else:
        pr = commands.gh("api", f"repos/{FORK}/pulls", "--method", "POST",
                         "-f", "base=" + BASE, "-f", "head=" + branch,
                         "-f", f"title=Integrate official release {release['id']}",
                         "-f", "body=" + evidence(output))
        output["pr_number"] = str(pr["number"])


def orchestrate(commands, directory, apply=False):
    output = {"status": "failed", "ready": "false", "build_allowed": "false",
              "review_required": "false", "candidate_sha": "", "base_sha": "",
              "release_sha": "", "release_core_sha": "", "candidate_core_sha": ""}
    try:
        release, upstream = latest(commands)
        base = sha(commands.api(f"repos/{FORK}/commits/{quote(BASE, safe='')}")["sha"])
        trusted = os.environ.get("GITHUB_SHA")
        if trusted and sha(trusted) != base:
            raise Stop("Trusted workflow revision differs from current base; start a fresh run")
        repo = Path(directory) / "app.git"
        commands.git(None, "init", "--bare", "--template=", str(repo))
        # Highest-precedence attributes: a candidate cannot choose an executable
        # merge driver or silently resolve conflicts using the built-in union driver.
        (repo / "info").mkdir(exist_ok=True)
        (repo / "info" / "attributes").write_text("* merge\n", encoding="utf-8")
        commands.git(repo, "fetch", "--no-tags", f"https://github.com/{FORK}.git", base)
        commands.git(repo, "fetch", "--no-tags", f"https://github.com/{OFFICIAL}.git",
                     "refs/tags/" + release["tag_name"])
        fetched = text(commands, repo, "rev-parse", "FETCH_HEAD^{commit}")
        if fetched != upstream:
            raise Stop("Official tag moved or API/fetch commit mismatch")
        candidate = prepare(commands, repo, release, upstream, base, output)
        # Verify exact official and final Core objects using a fixed public URL;
        # never follow candidate .gitmodules URLs or execute recursive submodules.
        if candidate:
            core = Path(directory) / "core.git"
            commands.git(None, "init", "--bare", "--template=", str(core))
            for pin in sorted({output["release_core_sha"], output["candidate_core_sha"]}):
                commands.git(core, "fetch", "--no-tags", CORE, pin)
                if text(commands, core, "rev-parse", "FETCH_HEAD^{commit}") != pin:
                    raise Stop("Core fetch did not match exact gitlink")
        if apply and (candidate or output["status"] == "conflict"):
            publish(commands, repo, output, release, upstream, base)
        if output["status"] == "conflict":
            raise Stop("Merge conflicts; no candidate pushed (--apply records an issue)")
    except (Stop, OSError, subprocess.TimeoutExpired, ValueError, KeyError) as error:
        output.update(ready="false", build_allowed="false", error=str(error))
        if output["status"] not in {"conflict", "review_required"}:
            output["status"] = "failed"
    return output


def emit(output, output_file=None):
    print(json.dumps(output, indent=2, ensure_ascii=True))
    if output_file:
        # One-line JSON for structured fields prevents output-command injection.
        with open(output_file, "a", encoding="utf-8") as handle:
            for key, value in output.items():
                if isinstance(value, (list, dict)) or "\n" in str(value) or "\r" in str(value):
                    value = json.dumps(value, ensure_ascii=True)
                handle.write(f"{key}={value}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Authorize fork branch/PR or conflict issue writes")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="simpmusic-upstream-") as directory:
        commands = Commands(directory)
        output = orchestrate(commands, directory, args.apply)
        emit(output, os.environ.get("GITHUB_OUTPUT"))
    return 1 if "error" in output or output["status"] in {"failed", "conflict"} else 0


if __name__ == "__main__":
    sys.exit(main())
