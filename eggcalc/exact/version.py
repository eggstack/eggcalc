"""
Version constraint checking for semver and cargo schemes.

Provides deterministic version parsing and constraint satisfaction
without external dependencies.
"""

from __future__ import annotations

import re
from typing import TypedDict


class ParsedVersion(TypedDict):
    """Parsed version components."""

    major: int
    minor: int
    patch: int
    pre_release: list[str]
    build: str
    raw: str


class ParsedConstraintComponent(TypedDict):
    """A single parsed constraint component."""

    operator: str
    version: ParsedVersion


class ParsedConstraint(TypedDict):
    """Parsed constraint components."""

    raw: str
    scheme: str
    components: list[ParsedConstraintComponent]
    type: str


class VersionConstraintResult(TypedDict, total=False):
    """Result of a version constraint check."""

    satisfies: bool
    parsed_version: ParsedVersion | None
    parsed_constraint: ParsedConstraint | None
    scheme: str
    explanation: str
    findings: list[str]


# Pre-release identifier priority (lower = earlier release)
_PRE_RELEASE_ORDER: dict[str, int] = {
    "alpha": 0,
    "beta": 1,
    "rc": 2,
    "dev": -1,
    "snapshot": -1,
    "pre": -1,
    "a": 0,
    "b": 1,
    "c": 2,
}

_NUMERIC_IDENTIFIER = r'(?:0|[1-9]\d*)'
_PRE_RELEASE_IDENTIFIER = (
    r'(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)'
)
_PRE_RELEASE = rf'(?:{_PRE_RELEASE_IDENTIFIER})(?:\.(?:{_PRE_RELEASE_IDENTIFIER}))*'
_BUILD = r'(?:[0-9A-Za-z-]+)(?:\.(?:[0-9A-Za-z-]+))*'

_SEMVER_RE = re.compile(
    rf'^({_NUMERIC_IDENTIFIER})\.({_NUMERIC_IDENTIFIER})\.({_NUMERIC_IDENTIFIER})'
    rf'(?:-({_PRE_RELEASE}))?'
    rf'(?:\+({_BUILD}))?$'
)

_SEMVER_LAX_RE = re.compile(
    rf'^({_NUMERIC_IDENTIFIER})(?:\.({_NUMERIC_IDENTIFIER}))?(?:\.({_NUMERIC_IDENTIFIER}))?'
    rf'(?:-({_PRE_RELEASE}))?'
    rf'(?:\+({_BUILD}))?$'
)


def _make_version(
    major: int,
    minor: int = 0,
    patch: int = 0,
    pre_release: list[str] | None = None,
    build: str = "",
    raw: str = "",
) -> ParsedVersion:
    """Build a ParsedVersion with copied mutable fields."""
    return ParsedVersion(
        major=major,
        minor=minor,
        patch=patch,
        pre_release=list(pre_release or []),
        build=build,
        raw=raw,
    )


def _parse_pre_release_identifiers(ident: str) -> list[str]:
    """Split a semver pre-release string into dot-separated identifiers."""
    return ident.split(".")


def _compare_pre_release(a: list[str], b: list[str]) -> int:
    """Compare two pre-release identifier lists.

    Pre-release versions without identifiers sort lower than those with.
    Numeric identifiers compare numerically; alphanumeric compare lexically.
    A shorter list that is a prefix of a longer list sorts lower.
    """
    if not a and not b:
        return 0
    if not a:
        return 1  # no pre-release > has pre-release
    if not b:
        return -1  # has pre-release < no pre-release

    for i in range(min(len(a), len(b))):
        ai, bi = a[i], b[i]
        ai_int = ai.isdigit()
        bi_int = bi.isdigit()
        if ai_int and bi_int:
            diff = int(ai) - int(bi)
            if diff != 0:
                return -1 if diff < 0 else 1
        elif ai_int:
            return -1
        elif bi_int:
            return 1
        else:
            if ai < bi:
                return -1
            elif ai > bi:
                return 1

    if len(a) < len(b):
        return -1
    elif len(a) > len(b):
        return 1
    return 0


def _sort_pre_release_key(ident: str) -> tuple[int, str]:
    """Generate a sort key for a pre-release identifier."""
    lower = ident.lower()
    if ident.isdigit():
        return (1, ident)
    if lower in _PRE_RELEASE_ORDER:
        return (0, str(_PRE_RELEASE_ORDER[lower]))
    return (2, ident)


def version_less_than(a: ParsedVersion, b: ParsedVersion) -> bool:
    """Check if version a < version b under semver rules."""
    for k in ("major", "minor", "patch"):
        if a[k] < b[k]:
            return True
        if a[k] > b[k]:
            return False
    return _compare_pre_release(a["pre_release"], b["pre_release"]) < 0


def version_equal(a: ParsedVersion, b: ParsedVersion) -> bool:
    """Check if version a == version b under semver rules."""
    return (
        a["major"] == b["major"]
        and a["minor"] == b["minor"]
        and a["patch"] == b["patch"]
        and a["pre_release"] == b["pre_release"]
    )


def version_lte(a: ParsedVersion, b: ParsedVersion) -> bool:
    """Check if version a <= version b."""
    return version_less_than(a, b) or version_equal(a, b)


def version_gte(a: ParsedVersion, b: ParsedVersion) -> bool:
    """Check if version a >= version b."""
    return not version_less_than(a, b)


def version_gt(a: ParsedVersion, b: ParsedVersion) -> bool:
    """Check if version a > version b."""
    return not version_lte(a, b)


def parse_version(version: str) -> ParsedVersion | None:
    """Parse a semver version string.

    Args:
        version: Version string like "1.2.3", "1.2.3-alpha.1+build.42"

    Returns:
        ParsedVersion dict or None if invalid.
    """
    version = version.strip()
    m = _SEMVER_RE.match(version)
    if not m:
        return None
    pre_release = _parse_pre_release_identifiers(m.group(4)) if m.group(4) else []
    build = m.group(5) or ""
    return _make_version(
        int(m.group(1)),
        int(m.group(2)),
        int(m.group(3)),
        pre_release=pre_release,
        build=build,
        raw=version,
    )


def _parse_version_lax(version: str) -> ParsedVersion | None:
    """Parse a version string allowing missing patch/minor.

    E.g., "1.2" -> 1.2.0, "1" -> 1.0.0
    """
    version = version.strip()
    m = _SEMVER_LAX_RE.match(version)
    if not m:
        return None
    pre_release = _parse_pre_release_identifiers(m.group(4)) if m.group(4) else []
    build = m.group(5) or ""
    return _make_version(
        int(m.group(1)),
        int(m.group(2) or 0),
        int(m.group(3) or 0),
        pre_release=pre_release,
        build=build,
        raw=version,
    )


def _parse_comparison_constraint(constraint: str) -> tuple[str, str]:
    """Extract operator and version from a comparison constraint.

    Supports: >=, <=, >, <, =, ==, !=

    Returns:
        Tuple of (operator, version_string)
    """
    constraint = constraint.strip()
    for op in (">=", "<=", "!=", ">", "<", "==", "="):
        if constraint.startswith(op):
            ver = constraint[len(op) :].strip()
            actual_op = "==" if op in ("=", "==") else op
            return actual_op, ver
    return "=", constraint


def _cargo_caret_range(version: ParsedVersion) -> tuple[ParsedVersion, ParsedVersion]:
    """Compute the caret (^) range for a version.

    Rules:
    - ^1.2.3 => >=1.2.3, <2.0.0
    - ^0.2.3 => >=0.2.3, <0.3.0
    - ^0.0.3 => >=0.0.3, <0.0.4
    - ^0.0.0 is invalid per cargo semver rules

    When the constraint version has pre-release identifiers (e.g., ^1.2.3-alpha.1),
    the lower bound includes those identifiers so that the same pre-release satisfies.
    """
    if version["major"] != 0:
        upper = _make_version(version["major"] + 1)
    elif version["minor"] != 0:
        upper = _make_version(0, version["minor"] + 1)
    elif version["patch"] != 0:
        upper = _make_version(0, 0, version["patch"] + 1)
    else:
        upper = _make_version(0, 0, 1)
    lower = _make_version(
        version["major"],
        version["minor"],
        version["patch"],
        pre_release=list(version["pre_release"]),
    )
    return lower, upper


def _cargo_tilde_range(version: ParsedVersion) -> tuple[ParsedVersion, ParsedVersion]:
    """Compute the tilde (~) range for a version.

    Rules:
    - ~1.2.3 => >=1.2.3, <1.3.0
    - ~1.2 => >=1.2.0, <1.3.0
    - ~1 => >=1.0.0, <2.0.0
    """
    if version["minor"] == 0 and version["patch"] == 0 and version["pre_release"]:
        upper = _make_version(version["major"], version["minor"] + 1)
    elif version["minor"] == 0 and version["patch"] == 0:
        upper = _make_version(version["major"] + 1)
    elif version["patch"] == 0:
        upper = _make_version(version["major"], version["minor"] + 1)
    else:
        upper = _make_version(version["major"], version["minor"] + 1)
    return version, upper


def _cargo_wildcard_range(constraint: str) -> tuple[ParsedVersion | None, ParsedVersion | None]:
    """Compute the wildcard range.

    1.* => >=1.0.0, <2.0.0
    1.2.* => >=1.2.0, <1.3.0
    """
    parts = constraint.strip().rstrip(".*").split(".")
    nums = [int(p) for p in parts if p]
    if len(nums) == 1:
        lower = _make_version(nums[0], raw=constraint)
        upper = _make_version(nums[0] + 1)
    elif len(nums) == 2:
        lower = _make_version(nums[0], nums[1], raw=constraint)
        upper = _make_version(nums[0], nums[1] + 1)
    else:
        return None, None
    return lower, upper


def _evaluate_component(ver: ParsedVersion, op: str, bound: ParsedVersion) -> bool:
    """Evaluate a single constraint component against a version."""
    if op == ">=":
        return version_gte(ver, bound)
    elif op == ">":
        return version_gt(ver, bound)
    elif op == "<=":
        return version_lte(ver, bound)
    elif op == "<":
        return version_less_than(ver, bound)
    elif op in ("==", "="):
        return version_equal(ver, bound)
    elif op == "!=":
        return not version_equal(ver, bound)
    return False


def _range_constraint_result(
    version: str,
    constraint: str,
    parsed_ver: ParsedVersion,
    lower: ParsedVersion,
    upper: ParsedVersion,
    scheme: str,
    constraint_type: str,
    findings: list[str],
) -> VersionConstraintResult:
    """Build a standard >= lower, < upper constraint result."""
    satisfies = version_gte(parsed_ver, lower) and version_less_than(parsed_ver, upper)
    pc: ParsedConstraint = {
        "raw": constraint,
        "scheme": scheme,
        "components": [
            {"operator": ">=", "version": lower},
            {"operator": "<", "version": upper},
        ],
        "type": constraint_type,
    }
    return VersionConstraintResult(
        satisfies=satisfies,
        parsed_version=parsed_ver,
        parsed_constraint=pc,
        scheme=scheme,
        explanation=(
            f"{version} satisfies {constraint}"
            if satisfies
            else f"{version} does not satisfy {constraint}"
        ),
        findings=findings,
    )


def check_version_constraint(
    version: str,
    constraint: str,
    scheme: str = "semver",
) -> VersionConstraintResult:
    """Check whether a version satisfies a constraint under a given scheme.

    Args:
        version: The version string to check.
        constraint: The version constraint string.
        scheme: Versioning scheme ("semver" or "cargo").

    Returns:
        VersionConstraintResult with satisfies, parsed_version,
        parsed_constraint, scheme, explanation, and findings.
    """
    findings: list[str] = []
    parsed_ver = parse_version(version)

    if parsed_ver is None:
        return VersionConstraintResult(
            satisfies=False,
            parsed_version=None,
            parsed_constraint=None,
            scheme=scheme,
            explanation=f"Invalid version: '{version}'",
            findings=[f"Could not parse version string '{version}' as semver"],
        )

    if scheme not in ("semver", "cargo"):
        return VersionConstraintResult(
            satisfies=False,
            parsed_version=parsed_ver,
            parsed_constraint=None,
            scheme=scheme,
            explanation=f"Unsupported scheme: '{scheme}'",
            findings=[f"Scheme '{scheme}' is not supported; use 'semver' or 'cargo'"],
        )

    constraint = constraint.strip()

    # Handle wildcard constraints (cargo scheme)
    if "*" in constraint:
        if scheme != "cargo":
            findings.append("Wildcard constraints are only supported with cargo scheme")
        lower, upper = _cargo_wildcard_range(constraint)
        if lower is None or upper is None:
            return VersionConstraintResult(
                satisfies=False,
                parsed_version=parsed_ver,
                parsed_constraint=None,
                scheme=scheme,
                explanation=f"Invalid wildcard constraint: '{constraint}'",
                findings=findings,
            )
        return _range_constraint_result(
            version, constraint, parsed_ver, lower, upper, scheme, "wildcard", findings
        )

    # Handle caret constraints (cargo scheme)
    if constraint.startswith("^"):
        ver_str = constraint[1:].strip()
        parsed_bound = parse_version(ver_str)
        if parsed_bound is None:
            return VersionConstraintResult(
                satisfies=False,
                parsed_version=parsed_ver,
                parsed_constraint=None,
                scheme=scheme,
                explanation=f"Invalid version in caret constraint: '{ver_str}'",
                findings=[f"Could not parse version '{ver_str}' in caret constraint"],
            )
        if parsed_bound["major"] == 0 and parsed_bound["minor"] == 0 and parsed_bound["patch"] == 0:
            findings.append("Caret constraint ^0.0.0 matches only 0.0.0")
        lower, upper = _cargo_caret_range(parsed_bound)
        return _range_constraint_result(
            version, constraint, parsed_ver, lower, upper, "cargo", "caret", findings
        )

    # Handle tilde constraints (cargo scheme)
    if constraint.startswith("~"):
        ver_str = constraint[1:].strip()
        parsed_bound = _parse_version_lax(ver_str)
        if parsed_bound is None:
            return VersionConstraintResult(
                satisfies=False,
                parsed_version=parsed_ver,
                parsed_constraint=None,
                scheme=scheme,
                explanation=f"Invalid version in tilde constraint: '{ver_str}'",
                findings=[f"Could not parse version '{ver_str}' in tilde constraint"],
            )
        lower, upper = _cargo_tilde_range(parsed_bound)
        return _range_constraint_result(
            version, constraint, parsed_ver, lower, upper, "cargo", "tilde", findings
        )

    # Handle comma-separated constraints
    if "," in constraint:
        parts = [p.strip() for p in constraint.split(",") if p.strip()]
        all_satisfy = True
        components: list[ParsedConstraintComponent] = []
        for part in parts:
            op, ver_str = _parse_comparison_constraint(part)
            parsed_bound = parse_version(ver_str)
            if parsed_bound is None:
                parsed_bound = _parse_version_lax(ver_str)
            if parsed_bound is None:
                return VersionConstraintResult(
                    satisfies=False,
                    parsed_version=parsed_ver,
                    parsed_constraint=None,
                    scheme=scheme,
                    explanation=f"Invalid version in constraint part: '{ver_str}'",
                    findings=[f"Could not parse version '{ver_str}' in constraint '{part}'"],
                )
            components.append({"operator": op, "version": parsed_bound})
            if not _evaluate_component(parsed_ver, op, parsed_bound):
                all_satisfy = False

        range_constraint: ParsedConstraint = {
            "raw": constraint,
            "scheme": scheme,
            "components": components,
            "type": "range",
        }
        return VersionConstraintResult(
            satisfies=all_satisfy,
            parsed_version=parsed_ver,
            parsed_constraint=range_constraint,
            scheme=scheme,
            explanation=(
                f"{version} satisfies {constraint}"
                if all_satisfy
                else f"{version} does not satisfy {constraint}"
            ),
            findings=findings,
        )

    # Single comparison or exact constraint
    op, ver_str = _parse_comparison_constraint(constraint)
    parsed_bound = parse_version(ver_str)
    if parsed_bound is None:
        parsed_bound = _parse_version_lax(ver_str)
    if parsed_bound is None:
        return VersionConstraintResult(
            satisfies=False,
            parsed_version=parsed_ver,
            parsed_constraint=None,
            scheme=scheme,
            explanation=f"Invalid version in constraint: '{ver_str}'",
            findings=[f"Could not parse version '{ver_str}' in constraint"],
        )

    satisfies = _evaluate_component(parsed_ver, op, parsed_bound)
    comparison_constraint: ParsedConstraint = {
        "raw": constraint,
        "scheme": scheme,
        "components": [{"operator": op, "version": parsed_bound}],
        "type": "comparison",
    }
    return VersionConstraintResult(
        satisfies=satisfies,
        parsed_version=parsed_ver,
        parsed_constraint=comparison_constraint,
        scheme=scheme,
        explanation=(
            f"{version} satisfies {constraint}"
            if satisfies
            else f"{version} does not satisfy {constraint}"
        ),
        findings=findings,
    )
