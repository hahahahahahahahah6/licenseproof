"""Tests for the core checker, incl. replays of the two verified real cases.

Fixtures:
- protobuf-7.36.0 wheel: License='3-Clause BSD License' (free text),
  no License-Expression, dist-info/LICENSE present  -> LEGACY_LICENSE
- ag_ui_strands-0.1.9 wheel: no license metadata at all, no license files
  -> MISSING_LICENSE
"""
import os
import zipfile
from email.parser import Parser

from licenseproof.checker import (
    LEGACY_LICENSE,
    LICENSE_FILE_MISSING,
    LICENSE_OK,
    MISSING_LICENSE,
    check_dist,
    is_problem,
)
from licenseproof.dist import parse_metadata

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
PROTOBUF_WHEEL = os.path.join(
    FIX, "protobuf-7.36.0-cp310-abi3-manylinux2014_x86_64.whl"
)
AG_UI_WHEEL = os.path.join(FIX, "ag_ui_strands-0.1.9-py3-none-any.whl")


def wheel_data(path):
    zf = zipfile.ZipFile(path)
    with zf:
        names = zf.namelist()
        meta_name = next(n for n in names if n.endswith(".dist-info/METADATA"))
        meta = Parser().parsestr(zf.read(meta_name).decode("utf-8", "replace"))
    return meta, names


def make_meta(lines):
    return parse_metadata("Metadata-Version: 2.4\nName: demo\nVersion: 1.0\n" + "".join(
        l + "\n" for l in lines
    ))


def test_protobuf_fixture_is_legacy_license():
    meta, names = wheel_data(PROTOBUF_WHEEL)
    check = check_dist(PROTOBUF_WHEEL, meta, names)
    assert check.verdict == LEGACY_LICENSE
    assert check.license_expression is None
    assert check.license_text == "3-Clause BSD License"
    assert any("dist-info/LICENSE" in f for f in check.license_files_found)
    assert "no License-Expression" in check.detail
    assert not is_problem(check)  # warning by default
    assert is_problem(check, require_spdx=True)


def test_ag_ui_strands_fixture_is_missing_license():
    meta, names = wheel_data(AG_UI_WHEEL)
    check = check_dist(AG_UI_WHEEL, meta, names)
    assert check.verdict == MISSING_LICENSE
    assert check.license_expression is None
    assert check.license_text is None
    assert check.license_files_found == []
    assert is_problem(check)


def test_spdx_expression_is_ok():
    meta = make_meta(["License-Expression: MIT"])
    check = check_dist("x", meta, ["demo-1.0.dist-info/METADATA"])
    assert check.verdict == LICENSE_OK
    assert not is_problem(check)
    assert not is_problem(check, require_spdx=True)


def test_expression_with_matching_license_file_refs_is_ok():
    meta = make_meta([
        "License-Expression: Apache-2.0",
        "License-File: LICENSE",
        "License-File: licenses/*",
    ])
    names = [
        "demo-1.0.dist-info/METADATA",
        "demo-1.0.dist-info/licenses/LICENSE",
        "demo-1.0.dist-info/licenses/NOTICE",
    ]
    check = check_dist("x", meta, names)
    assert check.verdict == LICENSE_OK
    assert check.missing_refs == []


def test_missing_referenced_file_fails_even_with_expression():
    meta = make_meta([
        "License-Expression: MIT",
        "License-File: LICENSE",
    ])
    check = check_dist("x", meta, ["demo-1.0.dist-info/METADATA"])
    assert check.verdict == LICENSE_FILE_MISSING
    assert check.missing_refs == ["LICENSE"]
    assert "not found" in check.detail
    assert is_problem(check)


def test_license_file_glob_matching():
    meta = make_meta(["License-Expression: MIT", "License-File: LICENSE*"])
    names = ["demo-1.0.dist-info/METADATA", "demo-1.0.dist-info/LICENSE.txt"]
    check = check_dist("x", meta, names)
    assert check.verdict == LICENSE_OK


def test_classifier_only_is_legacy():
    meta = make_meta(["Classifier: License :: OSI Approved :: MIT License"])
    check = check_dist("x", meta, ["demo-1.0.dist-info/METADATA"])
    assert check.verdict == LEGACY_LICENSE
    assert "classifier" in check.detail
    assert not is_problem(check)
    assert is_problem(check, require_spdx=True)


def test_files_only_no_metadata_is_legacy():
    meta = make_meta([])
    names = ["demo-1.0.dist-info/METADATA", "demo-1.0.dist-info/LICENSE"]
    check = check_dist("x", meta, names)
    assert check.verdict == LEGACY_LICENSE
    assert "undeclared" in check.detail


def test_unknown_license_counts_as_absent():
    meta = make_meta(["License: UNKNOWN"])
    check = check_dist("x", meta, ["demo-1.0.dist-info/METADATA"])
    assert check.verdict == MISSING_LICENSE
    assert is_problem(check)


def test_empty_license_counts_as_absent():
    meta = make_meta(["License:   "])
    check = check_dist("x", meta, ["demo-1.0.dist-info/METADATA"])
    assert check.verdict == MISSING_LICENSE


def test_expression_beats_legacy_text():
    meta = make_meta(["License-Expression: BSD-3-Clause", "License: some old text"])
    check = check_dist("x", meta, ["demo-1.0.dist-info/METADATA"])
    assert check.verdict == LICENSE_OK


def test_missing_ref_beats_expression():
    # A broken License-File reference fails even when an SPDX expression exists.
    meta = make_meta(["License-Expression: MIT", "License-File: missing.txt"])
    check = check_dist("x", meta, ["demo-1.0.dist-info/METADATA"])
    assert check.verdict == LICENSE_FILE_MISSING
    assert is_problem(check, require_spdx=True)
