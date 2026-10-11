"""Standard-library, offline tests for source-authoritative release allocation."""
import copy
import unittest
from types import MappingProxyType

from release_version import MAX_VERSION_CODE, allocate


class ReleaseVersionTests(unittest.TestCase):
    def setUp(self):
        self.state = {"version_code": 3, "version_name": "2.2.0-tasker.2"}

    def test_default_allocation_and_optional_upstream_v(self):
        for tag in ("2.2.0", "v2.2.0"):
            with self.subTest(tag=tag):
                self.assertEqual(allocate(self.state, tag), {
                    "version_code": 4, "version_name": "2.2.0-tasker.3"
                })

    def test_different_upstream_resets_suffix_not_code(self):
        for tag in ("v2.3.0", "3.0.0", "2.1.0", "0.0.0"):
            with self.subTest(tag=tag):
                result = allocate(self.state, tag)
                self.assertEqual(result["version_code"], 4)
                self.assertEqual(result["version_name"], tag.removeprefix("v") + "-tasker.1")

    def test_highest_source_or_external_code_wins(self):
        for source, maximum, expected in ((3, 0, 4), (3, 3, 4), (3, 59, 60),
                                           (100, 3, 101), (100, 100, 101)):
            with self.subTest(source=source, maximum=maximum):
                state = dict(self.state, version_code=source)
                self.assertEqual(allocate(state, "2.2.0", maximum)["version_code"], expected)

    def test_skip_consecutive_used_names_and_optional_tag_v(self):
        history = ("2.2.0-tasker.3", "v2.2.0-tasker.4", "2.2.0-tasker.4",
                   "2.2.0-tasker.6", "2.3.0-tasker.5")
        self.assertEqual(allocate(self.state, "v2.2.0", 7, history), {
            "version_code": 8, "version_name": "2.2.0-tasker.5"
        })

    def test_new_base_skips_used_names(self):
        self.assertEqual(allocate(self.state, "2.3.0", used_versions=(
            "v2.3.0-tasker.1", "2.3.0-tasker.2", "2.2.0-tasker.3"
        )), {"version_code": 4, "version_name": "2.3.0-tasker.3"})

    def test_missing_history_is_not_inferred(self):
        self.assertEqual(allocate(self.state, "2.3.0")["version_name"], "2.3.0-tasker.1")

    def test_no_mutation_and_repeatable_allocation(self):
        state = dict(self.state, metadata={"keep": [1, 2]})
        history = ["2.2.0-tasker.3"]
        original_state, original_history = copy.deepcopy(state), list(history)
        first = allocate(state, "2.2.0", used_versions=history)
        self.assertEqual(first, allocate(state, "2.2.0", used_versions=history))
        self.assertEqual(state, original_state)
        self.assertEqual(history, original_history)
        first["version_code"] = 99
        self.assertEqual(state, original_state)

    def test_mapping_and_generator_supported(self):
        result = allocate(MappingProxyType(self.state), "2.2.0", used_versions=(
            name for name in ("2.2.0-tasker.3", "2.2.0-tasker.4")
        ))
        self.assertEqual(result["version_name"], "2.2.0-tasker.5")

    def test_repeated_persisted_allocations_are_monotonic(self):
        state = self.state
        for expected in range(4, 15):
            state = allocate(state, "2.2.0")
            self.assertEqual(state["version_code"], expected)
            self.assertEqual(state["version_name"], f"2.2.0-tasker.{expected - 1}")

    def test_last_allowed_code(self):
        for source, maximum in ((MAX_VERSION_CODE - 1, 3),
                                (3, MAX_VERSION_CODE - 1)):
            with self.subTest(source=source, maximum=maximum):
                self.assertEqual(allocate(dict(self.state, version_code=source),
                                          "2.2.0", maximum)["version_code"],
                                 MAX_VERSION_CODE)

    def test_exhausted_code_rejected(self):
        for source, maximum in ((MAX_VERSION_CODE, 3), (3, MAX_VERSION_CODE)):
            with self.subTest(source=source, maximum=maximum):
                with self.assertRaisesRegex(ValueError, "exhausted"):
                    allocate(dict(self.state, version_code=source), "2.2.0", maximum)

    def test_invalid_source_codes(self):
        for code in (True, False, None, "3", 3.0, 0, -1, MAX_VERSION_CODE + 1):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    allocate(dict(self.state, version_code=code), "2.2.0")

    def test_invalid_maximum_codes(self):
        for code in (True, False, None, "3", 3.0, -1, MAX_VERSION_CODE + 1):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    allocate(self.state, "2.2.0", code)

    def test_invalid_states(self):
        for state in (None, [], "state", {}, {"version_code": 3},
                      {"version_name": "2.2.0-tasker.2"}):
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    allocate(state, "2.2.0")

    def test_invalid_source_names(self):
        for name in (None, True, 3, "", "2.2.0", "v2.2.0-tasker.2",
                     "2.2.0-tasker.0", "2.2.0-tasker.-1", "2.2.0-tasker.02",
                     "02.2.0-tasker.2", "2.2.0-tasker.2\n", "2.2.0-tasker.2+build"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    allocate(dict(self.state, version_name=name), "2.2.0")

    def test_invalid_upstream_tags(self):
        for tag in (None, True, 3, "", "2", "2.2", "2.2.0.1", "V2.2.0",
                    "vv2.2.0", "2.2.0-rc.1", "2.2.0+build", " 2.2.0",
                    "2.2.0 ", "2.2.0\n", "02.2.0", "2.02.0", "2.2.00",
                    "-2.2.0", "+2.2.0", "٢.2.0", "refs/tags/v2.2.0"):
            with self.subTest(tag=tag):
                with self.assertRaises(ValueError):
                    allocate(self.state, tag)

    def test_invalid_history_container(self):
        for history in (None, True, 3, "2.2.0-tasker.3", b"2.2.0-tasker.3", {}):
            with self.subTest(history=history):
                with self.assertRaises(ValueError):
                    allocate(self.state, "2.2.0", used_versions=history)

    def test_invalid_history_entries_even_for_other_bases(self):
        for name in (None, True, 3, "", "2.2.0", "v2.2.0", "2.3.0-tasker.0",
                     "2.3.0-tasker.01", "02.3.0-tasker.1", "2.3.0-tasker.1\n",
                     "2.3.0-tasker.1+build", "V2.3.0-tasker.1"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    allocate(self.state, "2.2.0", used_versions=[name])


if __name__ == "__main__":
    unittest.main()
