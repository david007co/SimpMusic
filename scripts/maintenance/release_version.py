"""Pure, offline allocation from the accepted source release high-water mark.

The caller must supply complete external release history (including drafts and
reserved versions), persist the returned state, and serialize allocations.
This module neither discovers history nor reserves a version or edits source.
"""
from collections.abc import Mapping
import re


MAX_VERSION_CODE = 2_100_000_000
_NUMERIC_VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
_UPSTREAM_TAG = re.compile(rf"v?({_NUMERIC_VERSION})")
_FORK_VERSION = re.compile(rf"({_NUMERIC_VERSION})-tasker\.([1-9][0-9]*)")
_USED_VERSION = re.compile(rf"v?({_NUMERIC_VERSION})-tasker\.([1-9][0-9]*)")


def _code(value, field, minimum):
    if type(value) is not int or not minimum <= value <= MAX_VERSION_CODE:
        raise ValueError(
            f"{field} must be an integer from {minimum} to {MAX_VERSION_CODE}"
        )
    return value


def allocate(state, upstream_tag, maximum_code=3, used_versions=()):
    """Return a new {version_code, version_name} dict without mutating inputs.

    state is a mapping containing a positive integer version_code and a canonical
    x.y.z-tasker.N version_name. upstream_tag accepts x.y.z or vx.y.z only;
    numeric components have no leading zeros. maximum_code is the caller's
    external code high-water mark (zero is allowed for empty history).
    used_versions is an iterable of fork version names or tags with optional v.
    Invalid inputs or exhausted Android version codes raise ValueError.

    A matching upstream base starts at the source suffix plus one; a different
    base starts at one. Already-used names are skipped, never used to lower the
    source high-water mark. No upstream ordering/downgrade policy is imposed.
    """
    if not isinstance(state, Mapping):
        raise ValueError("state must be a mapping")
    if "version_code" not in state or "version_name" not in state:
        raise ValueError("state requires version_code and version_name")
    source_code = _code(state["version_code"], "state.version_code", 1)
    history_code = _code(maximum_code, "maximum_code", 0)
    name = state["version_name"]
    source = _FORK_VERSION.fullmatch(name) if isinstance(name, str) else None
    if source is None:
        raise ValueError("state.version_name must be canonical x.y.z-tasker.N")
    upstream = (
        _UPSTREAM_TAG.fullmatch(upstream_tag)
        if isinstance(upstream_tag, str) else None
    )
    if upstream is None:
        raise ValueError("upstream_tag must be x.y.z with an optional leading v")

    if isinstance(used_versions, (str, bytes, Mapping)):
        raise ValueError("used_versions must be an iterable of fork names or tags")
    try:
        history = iter(used_versions)
    except TypeError as exc:
        raise ValueError("used_versions must be iterable") from exc
    used = set()
    for version in history:
        match = _USED_VERSION.fullmatch(version) if isinstance(version, str) else None
        if match is None:
            raise ValueError("used_versions entries must be x.y.z-tasker.N or vx.y.z-tasker.N")
        used.add(f"{match[1]}-tasker.{match[2]}")

    code = max(source_code, history_code) + 1
    if code > MAX_VERSION_CODE:
        raise ValueError("Android version_code range exhausted")
    base = upstream[1]
    suffix = int(source[2]) + 1 if source[1] == base else 1
    while f"{base}-tasker.{suffix}" in used:
        suffix += 1
    return {"version_code": code, "version_name": f"{base}-tasker.{suffix}"}
