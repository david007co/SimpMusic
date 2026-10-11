"""Offline tests: real Git objects in temporary repos, all GitHub operations mocked."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import upstream_integration as integration


class LocalCommands(integration.Commands):
    def __init__(self, home, app, core, base, upstream):
        super().__init__(home)
        self.app, self.core = app, core
        self.base, self.upstream = base, upstream
        self.release = {"id": 42, "tag_name": "v2.2.0", "draft": False, "prerelease": False}
        self.calls = []
        self.remote = ""
        self.prs = []
        self.issues = []
        self.moved = False
        self.release_reads = 0

    def api(self, endpoint):
        self.calls.append(("api", endpoint))
        if endpoint.endswith("releases/latest"):
            self.release_reads += 1
            if self.moved and self.release_reads > 1:
                return dict(self.release, id=43)
            return self.release
        if integration.FORK in endpoint:
            return {"sha": self.base}
        return {"sha": self.upstream}

    def git(self, repo, *args, data=None, check=True, write=False):
        if args[0] == "push":
            self.calls.append(("push", *args))
            return subprocess.CompletedProcess(args, 0, b"", b"")
        if args[0] == "ls-remote":
            return subprocess.CompletedProcess(args, 0, self.remote.encode(), b"")
        if args[0] == "fetch":
            source = self.core if args[2] == integration.CORE else self.app
            # Only this test adapter enables local transport, never production.
            return self.run(["git", "-c", f"core.hooksPath={os.devnull}",
                             "fetch", "--no-tags", str(source), args[3]], repo, data, check)
        return super().git(repo, *args, data=data, check=check, write=write)

    def gh(self, *args):
        self.calls.append(("gh", *args))
        if args[0:2] == ("pr", "list"):
            return self.prs
        if args[0:2] == ("issue", "list"):
            return self.issues
        return {"number": 7}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("GITHUB_SHA", None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "source"
        self.core = self.root / "core-source"
        self.work = self.root / "work"
        self.work.mkdir()
        self.env = integration.Commands(self.root).env
        for repo in (self.app, self.core):
            self.git(repo.parent, "init", "--template=", str(repo))
        self.put(self.core, "core.txt", "one\n")
        self.core_one = self.commit(self.core, "core one")
        self.put(self.core, "core.txt", "two\n")
        self.core_two = self.commit(self.core, "core two")
        self.put(self.app, "plain.txt", "original\n")
        self.put(self.app, ".github/workflows/trusted.yml.disabled", "trusted\n")
        self.put(self.app, "build.gradle.kts", "trusted build\n")
        self.put(self.app, "gradle/libs.versions.toml", "[versions]\nversion-name = '2.2.0'\n")
        self.git(self.app, "add", ".")
        self.git(self.app, "update-index", "--add", "--cacheinfo", "160000," + self.core_one + ",core")
        self.common = self.commit(self.app, "common")
        self.put(self.app, "fork.txt", "Tasker preserved\n")
        self.put(self.app, "fork-release.json", json.dumps({
            "version_code": 3, "version_name": "2.2.0-tasker.2"
        }))
        self.base = self.commit(self.app, "fork")
        self.git(self.app, "checkout", "--detach", self.common)

    def git(self, repo, *args):
        result = subprocess.run(["git", "--no-pager", "-c", f"core.hooksPath={os.devnull}",
                                 *args], cwd=repo, env=self.env, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        return result.stdout.decode().strip()

    def put(self, repo, name, contents):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def commit(self, repo, message):
        # Preserve the intentionally unpopulated gitlink in the fixture index.
        core_entry = self.git(repo, "ls-files", "--stage", "--", "core")
        self.git(repo, "add", ".")
        if core_entry:
            pin = core_entry.split()[1]
            self.git(repo, "update-index", "--add", "--cacheinfo", "160000," + pin + ",core")
        self.git(repo, "commit", "-m", message)
        return self.git(repo, "rev-parse", "HEAD")

    def commands(self, upstream, tag="v2.2.0"):
        self.git(self.app, "tag", tag, upstream)
        commands = LocalCommands(self.root, self.app, self.core, self.base, upstream)
        commands.release["tag_name"] = tag
        return commands

    def changed(self):
        self.put(self.app, "plain.txt", "official update\n")
        return self.commit(self.app, "official")

    def test_normal_candidate_pins_and_preserves_fork(self):
        commands = self.commands(self.changed())
        out = integration.orchestrate(commands, self.work)
        self.assertEqual((out["status"], out["ready"], out["build_allowed"]), ("ready", "true", "true"))
        repo = self.work / "app.git"
        self.assertEqual(self.git(repo, "show", out["candidate_sha"] + ":fork.txt"), "Tasker preserved")
        self.assertEqual(out["candidate_core_sha"], self.core_one)
        self.assertEqual((out["version_code"], out["version_name"]), ("4", "2.2.0-tasker.3"))
        state = json.loads(self.git(repo, "show", out["candidate_sha"] + ":fork-release.json"))
        self.assertEqual(state, {"version_code": 4, "version_name": "2.2.0-tasker.3"})
        self.assertEqual(json.loads(self.git(repo, "show", self.base + ":fork-release.json"))["version_code"], 3)
        self.assertNotIn("fork-release.json", out["sensitive_changes"])
        self.assertFalse(any(c[0] == "push" or c[0] == "gh" for c in commands.calls))
        self.assertEqual(self.git(self.app, "rev-parse", "HEAD"), commands.upstream)

    def test_equal_merge_base_tree_skips_divergent_history(self):
        self.git(self.app, "commit", "--allow-empty", "-m", "official history only")
        upstream = self.git(self.app, "rev-parse", "HEAD")
        self.assertNotEqual(upstream, self.common)
        out = integration.orchestrate(self.commands(upstream), self.work, apply=True)
        self.assertEqual(out["status"], "no_upstream_tree_changes")
        self.assertNotIn("version_code", out)
        self.assertEqual(out["candidate_sha"], "")
        self.assertEqual(out["build_allowed"], "false")

    def test_workflows_restored_before_push_and_gate(self):
        (self.app / ".github/workflows/trusted.yml.disabled").unlink()
        self.put(self.app, ".github/workflows/evil.yml", "on: push\n")
        commands = self.commands(self.changed())
        out = integration.orchestrate(commands, self.work, apply=True)
        self.assertEqual(out["status"], "review_required")
        self.assertIn(".github/workflows/evil.yml", out["quarantined_workflows"])
        candidate = out["candidate_sha"]
        self.assertEqual(self.git(self.work / "app.git", "diff", "--name-only", self.base,
                                  candidate, "--", ".github/workflows"), "")
        self.assertTrue(any(c[0] == "push" for c in commands.calls))
        pr = next(c for c in commands.calls if c[:3] == ("gh", "api", f"repos/{integration.FORK}/pulls"))
        self.assertIn("base=" + integration.BASE, pr)
        self.assertIn("head=" + out["candidate_branch"], pr)
        self.assertFalse(any("--force" in str(c) for c in commands.calls))

    def test_sensitive_build_and_core_block_execution(self):
        self.put(self.app, "build.gradle.kts", "changed build\n")
        self.git(self.app, "update-index", "--cacheinfo", "160000," + self.core_two + ",core")
        out = integration.orchestrate(self.commands(self.changed()), self.work)
        self.assertEqual(out["build_allowed"], "false")
        self.assertEqual(out["candidate_core_sha"], self.core_two)
        self.assertIn("build.gradle.kts", out["sensitive_changes"])
        self.assertIn("core", out["sensitive_changes"])

    def test_conflict_no_push_actionable_issue_and_fail_closed(self):
        upstream = self.changed()
        self.git(self.app, "checkout", "--detach", self.base)
        self.put(self.app, "plain.txt", "fork edit\n")
        self.base = self.commit(self.app, "conflicting fork")
        commands = self.commands(upstream)
        out = integration.orchestrate(commands, self.work, apply=True)
        self.assertEqual(out["status"], "conflict")
        self.assertEqual(out["ready"], "false")
        self.assertEqual(out["candidate_sha"], "")
        self.assertIn("plain.txt", out["conflict_evidence"])
        self.assertFalse(any(c[0] == "push" for c in commands.calls))
        self.assertTrue(any(c[:3] == ("gh", "api", f"repos/{integration.FORK}/issues") for c in commands.calls))

    def test_candidate_union_merge_attribute_cannot_hide_conflict(self):
        self.put(self.app, ".gitattributes", "plain.txt merge=union\n")
        upstream = self.changed()
        self.git(self.app, "checkout", "--detach", self.base)
        self.put(self.app, "plain.txt", "fork edit\n")
        self.base = self.commit(self.app, "fork conflict")
        commands = self.commands(upstream)
        out = integration.orchestrate(commands, self.work)
        self.assertEqual(out["status"], "conflict")
        self.assertEqual(out["candidate_sha"], "")

    def test_conflict_issue_deduplicated(self):
        commands = self.commands(self.changed())
        marker = "upstream-conflict-42"
        commands.issues = [{"body": marker, "number": 1}]
        integration.issue(commands, "details", marker)
        self.assertFalse(any("POST" in c for c in commands.calls))

    def test_duplicate_exact_candidate_reused(self):
        commands = self.commands(self.changed())
        first = integration.orchestrate(commands, self.work)
        candidate = first["candidate_sha"]
        # Make candidate reachable in the mocked remote source for ancestry reads.
        self.git(self.app, "fetch", str(self.work / "app.git"), candidate)
        self.git(self.app, "update-ref", "refs/heads/" + first["candidate_branch"], candidate)
        commands.remote = candidate + "\trefs/heads/" + first["candidate_branch"]
        commands.prs = [{"number": 8, "state": "OPEN", "headRefOid": candidate}]
        second_work = self.root / "second"
        second_work.mkdir()
        out = integration.orchestrate(commands, second_work, apply=True)
        self.assertEqual(out["candidate_sha"], candidate)
        self.assertEqual(out["pr_number"], "8")
        self.assertEqual(out["status"], "ready")
        self.assertFalse(any(c[0] == "push" for c in commands.calls))

    def test_duplicate_wrong_ancestry_stops(self):
        commands = self.commands(self.changed())
        branch = f"automation/upstream-42-{commands.upstream[:12]}"
        self.git(self.app, "update-ref", "refs/heads/" + branch, self.base)
        commands.remote = self.base + "\trefs/heads/" + branch
        out = integration.orchestrate(commands, self.work, apply=True)
        self.assertEqual(out["status"], "failed")
        self.assertIn("ancestry", out["error"])
        self.assertEqual(out["build_allowed"], "false")
        self.assertFalse(any(c[0] == "push" for c in commands.calls))

    def test_duplicate_extra_commit_stops_even_with_matching_ancestry(self):
        commands = self.commands(self.changed())
        first = integration.orchestrate(commands, self.work)
        self.git(self.app, "fetch", str(self.work / "app.git"), first["candidate_sha"])
        self.git(self.app, "checkout", "--detach", first["candidate_sha"])
        self.put(self.app, "unreviewed.txt", "extra\n")
        extra = self.commit(self.app, "unreviewed")
        self.git(self.app, "update-ref", "refs/heads/" + first["candidate_branch"], extra)
        commands.remote = extra + "\trefs/heads/" + first["candidate_branch"]
        second = self.root / "second"
        second.mkdir()
        out = integration.orchestrate(commands, second, apply=True)
        self.assertIn("exact deterministic", out["error"])
        self.assertFalse(any(c[0] == "push" for c in commands.calls))

    def test_changed_release_prevents_write(self):
        commands = self.commands(self.changed())
        commands.moved = True
        out = integration.orchestrate(commands, self.work, apply=True)
        self.assertEqual(out["status"], "failed")
        self.assertIn("changed", out["error"])
        self.assertFalse(any(c[0] == "push" for c in commands.calls))

    def test_api_fetch_mismatch_stops(self):
        commands = self.commands(self.changed())
        commands.upstream = self.base
        out = integration.orchestrate(commands, self.work)
        self.assertIn("mismatch", out["error"])
        self.assertEqual(out["ready"], "false")

    def test_invalid_metadata_and_sensitive_classifier(self):
        commands = self.commands(self.changed())
        commands.release["prerelease"] = True
        out = integration.orchestrate(commands, self.work)
        self.assertEqual(out["status"], "failed")
        for path in (".gitmodules", "gradlew", "gradle/wrapper/gradle-wrapper.jar",
                     "module/build.gradle.kts", "settings.gradle.kts", "scripts/tool.py", "core"):
            self.assertTrue(integration.sensitive(path), path)
        self.assertFalse(integration.sensitive("composeApp/src/Playlist.kt"))

    def test_git_environment_scrubs_secrets_hooks_and_config(self):
        with patch.dict(os.environ, {"GH_TOKEN": "do-not-leak", "GIT_CONFIG_COUNT": "99",
                                     "GIT_SSH_COMMAND": "malicious", "JAVA_TOOL_OPTIONS": "bad"}):
            commands = integration.Commands(self.root)
        self.assertNotIn("GH_TOKEN", commands.env)
        self.assertNotIn("GIT_SSH_COMMAND", commands.env)
        self.assertNotIn("GIT_CONFIG_COUNT", commands.env)
        self.assertEqual(commands.env["GIT_CONFIG_GLOBAL"], os.devnull)
        with patch.object(commands, "run") as run:
            commands.git(self.app, "merge-tree", "--write-tree", self.base, self.common)
        self.assertIn("core.hooksPath=" + os.devnull, run.call_args.args[0])

    def test_new_official_version_resets_suffix_and_increments_state_code(self):
        self.put(self.app, "gradle/libs.versions.toml", '[versions]\nversion-name = "2.3.0"\n')
        out = integration.orchestrate(self.commands(self.changed(), "v2.3.0"), self.work)
        self.assertEqual((out["version_code"], out["version_name"]), ("4", "2.3.0-tasker.1"))
        self.assertEqual(out["ready"], "true")
        self.assertEqual(out["build_allowed"], "false")

    def test_version_allocation_stops_on_invalid_source_or_tag(self):
        upstream = self.changed()
        for case in ("missing-state", "invalid-state", "invalid-catalog", "missing-catalog",
                     "later-source", "older-source", "invalid-tag", "noncanonical-tag"):
            with self.subTest(case=case):
                self.git(self.app, "checkout", "--detach", self.base)
                tag = "v2.2.0"
                if case == "missing-state":
                    (self.app / "fork-release.json").unlink()
                elif case == "invalid-state":
                    self.put(self.app, "fork-release.json", '{"version_code": true}')
                elif case == "missing-catalog":
                    (self.app / "gradle/libs.versions.toml").unlink()
                elif case == "invalid-catalog":
                    self.put(self.app, "gradle/libs.versions.toml", "[versions\n")
                elif case in {"later-source", "older-source"}:
                    version = "2.3.0" if case == "later-source" else "2.1.0"
                    self.put(self.app, "gradle/libs.versions.toml", f"[versions]\nversion-name = '{version}'\n")
                elif case == "invalid-tag":
                    tag = "2.2.0"
                else:
                    tag = "v02.2.0"
                base = self.commit(self.app, case) if case not in {"invalid-tag", "noncanonical-tag"} else self.base
                # Keep each mock remote tag separate while testing metadata policy.
                self.git(self.app, "tag", "--force", tag, upstream)
                commands = LocalCommands(self.root, self.app, self.core, base, upstream)
                commands.release["tag_name"] = tag
                work = self.root / case
                work.mkdir()
                out = integration.orchestrate(commands, work, apply=True)
                self.assertEqual(out["status"], "review_required")
                self.assertEqual((out["ready"], out["build_allowed"]), ("false", "false"))
                self.assertEqual(out["candidate_sha"], "")
                self.assertIn("Version allocation requires review", out["error"])
                self.assertFalse(any(c[0] in {"push", "gh"} for c in commands.calls))

    def test_allocation_uses_pinned_base_not_candidate_state(self):
        commands = self.commands(self.changed())
        out = integration.orchestrate(commands, self.work)
        repo = self.work / "app.git"
        commands.git(repo, "read-tree", out["candidate_sha"])
        blob = integration.text(commands, repo, "hash-object", "-w", "--stdin",
                                data=json.dumps({"version_code": 999,
                                                 "version_name": "2.2.0-tasker.998"}).encode())
        commands.git(repo, "update-index", "--cacheinfo", f"100644,{blob},fork-release.json")
        tree = integration.text(commands, repo, "write-tree")
        allocated_tree = integration.allocate_candidate_version(
            commands, repo, tree, self.base, "v2.2.0", out)
        state = json.loads(self.git(repo, "show", allocated_tree + ":fork-release.json"))
        self.assertEqual(state, {"version_code": 4, "version_name": "2.2.0-tasker.3"})
        self.assertEqual((out["version_code"], out["version_name"]), ("4", "2.2.0-tasker.3"))
        self.assertFalse(integration.sensitive("fork-release.json"))
        self.assertIn("tracked base-state floor", integration.evidence(out))

    def test_trusted_workflow_revision_guard(self):
        commands = self.commands(self.changed())
        with patch.dict(os.environ, {"GITHUB_SHA": self.common}):
            out = integration.orchestrate(commands, self.work, apply=True)
        self.assertEqual(out["status"], "failed")
        self.assertIn("Trusted workflow revision", out["error"])
        self.assertFalse(any(c[0] in {"push", "gh"} for c in commands.calls))

    def test_output_newline_injection_is_encoded(self):
        output = self.root / "output"
        with contextlib.redirect_stdout(io.StringIO()):
            integration.emit({"ready": "false", "error": "failure\nready=true", "paths": ["a\nb"]}, output)
        lines = output.read_text().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(json.loads(lines[1].split("=", 1)[1]), "failure\nready=true")


if __name__ == "__main__":
    unittest.main()
