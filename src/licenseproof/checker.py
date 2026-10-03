"""Core check logic: does the artifact carry usable license information?

Narrow scope, deliberately: this is NOT a generic license scanner and does
not interpret license compatibility. It answers one question: can a
compliance tool find machine-usable license metadata *and* the license text
it points at inside this wheel/sdist/installed distribution?
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from email.message import Message

from .dist import find_license_files

# Verdicts
LICENSE_OK = "LICENSE_OK"
LEGACY_LICENSE = "LEGACY_LICENSE"
MISSING_LICENSE = "MISSING_LICENSE"
LICENSE_FILE_MISSING = "LICENSE_FILE_MISSING"


@dataclass
class LicenseCheck:
    source: str
    license_expression: str | None = None
    license_text: str | None = None  # legacy License: free-text field
    license_classifiers: list[str] = field(default_factory=list)
    license_file_refs: list[str] = field(default_factory=list)  # License-File entries
    license_files_found: list[str] = field(default_factory=list)
    missing_refs: list[str] = field(default_factory=list)
    verdict: str = MISSING_LICENSE
    detail: str = ""


def _present(value: str | None) -> str | None:
    """Normalize a metadata field: empty/whitespace/'UNKNOWN' counts as absent."""
    if value is None:
        return None
    v = value.strip()
    if not v or v.upper() == "UNKNOWN":
        return None
    return v


def _ref_matches(pattern: str, names: list[str], flavor: str) -> bool:
    """Does a PEP 639 License-File value resolve to an archive member?

    Values are project-root-relative. Wheels store them under
    ``<dist>.dist-info/licenses/`` (PEP 639) or, legacy-style, directly under
    ``<dist>.dist-info/``; sdists keep them project-root-relative under the
    top-level ``<name>-<version>/`` directory. Matching is explicit --
    no basename-only fallbacks that could match an unrelated file.
    """
    raw = pattern.strip()
    if not raw or raw.startswith("/") or ".." in raw.split("/"):
        return False
    pat = raw.lstrip("./")
    if not pat:
        return False
    if flavor == "sdist":
        tops = {n.split("/", 1)[0] for n in names if "/" in n}
        candidates = [f"{t}/{pat}" for t in tops] if tops else [pat]
    else:  # wheel or installed: dist-info layout
        candidates = [f"*.dist-info/licenses/{pat}", f"*.dist-info/{pat}"]
    return any(fnmatch.fnmatchcase(n, c) for n in names for c in candidates)


def check_dist(source: str, meta: Message, names: list[str],
               flavor: str = "wheel") -> LicenseCheck:
    """Evaluate one artifact's license metadata and files. Pure function.

    flavor is "wheel", "sdist", or "installed" -- it controls where
    License-File references are expected to resolve.
    """
    check = LicenseCheck(source=source)
    check.license_expression = _present(meta.get("License-Expression"))
    check.license_text = _present(meta.get("License"))
    check.license_classifiers = [
        c for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")
    ]
    check.license_file_refs = [
        r.strip() for r in (meta.get_all("License-File") or []) if r.strip()
    ]
    check.license_files_found = find_license_files(names)
    check.missing_refs = [
        r for r in check.license_file_refs if not _ref_matches(r, names, flavor)
    ]

    if check.missing_refs:
        # Metadata points at license files that are not in the artifact.
        # This fails regardless of License-Expression: the reference is broken.
        check.verdict = LICENSE_FILE_MISSING
        check.detail = (
            "License-File reference(s) not found in the distribution: "
            + ", ".join(repr(r) for r in check.missing_refs)
        )
    elif check.license_expression:
        # NOTE: presence only -- the expression is NOT semantically validated
        # against the SPDX license list. LICENSE_OK means "a License-Expression
        # field exists", not "the expression is valid SPDX".
        check.verdict = LICENSE_OK
        if check.license_file_refs:
            check.detail = (
                f"License-Expression: {check.license_expression}; "
                f"{len(check.license_file_refs)} License-File reference(s) present"
            )
        else:
            check.detail = (
                f"License-Expression: {check.license_expression}; "
                "no License-File references"
            )
    elif check.license_text or check.license_classifiers or check.license_files_found:
        # Old-style license info only: free-text License field, trove
        # classifiers, and/or undeclared license text files -- none of it is
        # an SPDX License-Expression a tool can evaluate mechanically.
        check.verdict = LEGACY_LICENSE
        parts = []
        if check.license_text:
            parts.append(f"License: {check.license_text!r} (free text, not SPDX)")
        if check.license_classifiers:
            parts.append(
                "license classifier(s): " + ", ".join(check.license_classifiers)
            )
        if check.license_files_found:
            parts.append(
                f"license text file(s) present but undeclared: "
                + ", ".join(check.license_files_found[:3])
                + ("..." if len(check.license_files_found) > 3 else "")
            )
        parts.append("no License-Expression (PEP 639)")
        check.detail = "; ".join(parts)
    else:
        check.verdict = MISSING_LICENSE
        check.detail = (
            "no License, License-Expression, or License-File metadata, "
            "and no license text files in the distribution"
        )
    return check


def is_problem(check: LicenseCheck, require_spdx: bool = False) -> bool:
    """Does this result fail the check? LEGACY_LICENSE fails only with --require-spdx."""
    if check.verdict in (MISSING_LICENSE, LICENSE_FILE_MISSING):
        return True
    if check.verdict == LEGACY_LICENSE and require_spdx:
        return True
    return False
