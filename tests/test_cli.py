"""Tests for the CLI: exit codes, formats, argument validation."""
import json
import os
import zipfile

import pytest

from licenseproof.cli import main

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
PROTOBUF_WHEEL = os.path.join(
    FIX, "protobuf-7.36.0-cp310-abi3-manylinux2014_x86_64.whl"
)
AG_UI_WHEEL = os.path.join(FIX, "ag_ui_strands-0.1.9-py3-none-any.whl")


def make_wheel(path, metadata_lines):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "demo-1.0.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: demo\nVersion: 1.0\n"
            + "".join(l + "\n" for l in metadata_lines),
        )


def test_wheel_legacy_is_warning_exit_0(capsys):
    assert main(["check", "--wheel", PROTOBUF_WHEEL]) == 0
    out = capsys.readouterr().out
    assert "LEGACY_LICENSE" in out
    assert "--require-spdx" in out


def test_wheel_legacy_require_spdx_exit_1(capsys):
    assert main(["check", "--wheel", PROTOBUF_WHEEL, "--require-spdx"]) == 1
    assert "LEGACY_LICENSE" in capsys.readouterr().out


def test_wheel_missing_license_exit_1(capsys):
    assert main(["check", "--wheel", AG_UI_WHEEL]) == 1
    assert "MISSING_LICENSE" in capsys.readouterr().out


def test_wheel_spdx_ok_exit_0(tmp_path, capsys):
    p = str(tmp_path / "demo-1.0-py3-none-any.whl")
    make_wheel(p, ["License-Expression: MIT"])
    assert main(["check", "--wheel", p]) == 0
    assert "LICENSE_OK" in capsys.readouterr().out


def test_wheel_not_found_exit_2(capsys):
    assert main(["check", "--wheel", "/nonexistent/x.whl"]) == 2
    assert "error" in capsys.readouterr().err


def test_wheel_bad_zip_exit_2(tmp_path, capsys):
    p = str(tmp_path / "bad.whl")
    with open(p, "w") as fh:
        fh.write("junk")
    assert main(["check", "--wheel", p]) == 2


def test_sdist_exit_0(tmp_path, capsys):
    import io
    import tarfile

    p = str(tmp_path / "demo-1.0.tar.gz")
    with tarfile.open(p, "w:gz") as tf:
        blob = b"Metadata-Version: 2.4\nName: demo\nVersion: 1.0\nLicense-Expression: MIT\n"
        ti = tarfile.TarInfo("demo-1.0/PKG-INFO")
        ti.size = len(blob)
        tf.addfile(ti, io.BytesIO(blob))
    assert main(["check", "--sdist", p]) == 0
    assert "LICENSE_OK" in capsys.readouterr().out


def test_package_installed_exit_0(tmp_path, capsys, monkeypatch):
    # Build a synthetic installed dist: hermetic, no reliance on env packages.
    di = tmp_path / "demo-1.0.dist-info"
    di.mkdir()
    (di / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: demo\nVersion: 1.0\nLicense-Expression: MIT\n"
    )
    (di / "RECORD").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert main(["check", "--package", "demo"]) == 0
    out = capsys.readouterr().out
    assert "LICENSE_OK" in out
    assert "installed:demo" in out


def test_package_not_installed_exit_2(capsys):
    assert main(["check", "--package", "no-such-dist-xyz-123"]) == 2
    assert "error" in capsys.readouterr().err


def test_json_format_shape(capsys):
    assert main(["check", "--wheel", AG_UI_WHEEL, "--format", "json"]) == 1
    row = json.loads(capsys.readouterr().out)
    assert row["verdict"] == "MISSING_LICENSE"
    assert row["source"] == AG_UI_WHEEL
    assert "license_expression" in row


def test_no_source_is_argparse_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["check"])
    assert exc.value.code == 2


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "licenseproof" in capsys.readouterr().out
