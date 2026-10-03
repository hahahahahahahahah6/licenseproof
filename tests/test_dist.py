"""Tests for the dist readers (wheel / sdist / installed)."""
import io
import os
import tarfile
import zipfile

import pytest

from licenseproof.dist import (
    DistReadError,
    find_license_files,
    read_installed,
    read_sdist,
    read_wheel,
)

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
PROTOBUF_WHEEL = os.path.join(
    FIX, "protobuf-7.36.0-cp310-abi3-manylinux2014_x86_64.whl"
)


def make_wheel(path, metadata_lines, extra_files=()):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "demo-1.0.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: demo\nVersion: 1.0\n"
            + "".join(l + "\n" for l in metadata_lines),
        )
        zf.writestr("demo-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\n")
        for name, content in extra_files:
            zf.writestr(name, content)


def test_read_wheel_fixture():
    meta, names = read_wheel(PROTOBUF_WHEEL)
    assert meta.get("License") == "3-Clause BSD License"
    assert any(n.endswith(".dist-info/METADATA") for n in names)


def test_read_wheel_synthetic():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "demo-1.0-py3-none-any.whl")
        make_wheel(p, ["License-Expression: MIT"],
                   [("demo-1.0.dist-info/licenses/LICENSE", "text")])
        meta, names = read_wheel(p)
        assert meta.get("License-Expression") == "MIT"
        assert "demo-1.0.dist-info/licenses/LICENSE" in names


def test_read_wheel_missing_file():
    with pytest.raises(DistReadError):
        read_wheel("/nonexistent/demo-1.0-py3-none-any.whl")


def test_read_wheel_bad_zip(tmp_path):
    p = str(tmp_path / "bad.whl")
    with open(p, "w") as fh:
        fh.write("not a zip")
    with pytest.raises(DistReadError):
        read_wheel(p)


def test_read_wheel_no_metadata(tmp_path):
    p = str(tmp_path / "nometa.whl")
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("demo/__init__.py", "")
    with pytest.raises(DistReadError):
        read_wheel(p)


def make_sdist_tgz(path, pkg_info_lines, extra_files=()):
    with tarfile.open(path, "w:gz") as tf:
        info_blob = (
            "Metadata-Version: 2.4\nName: demo\nVersion: 1.0\n"
            + "".join(l + "\n" for l in pkg_info_lines)
        ).encode()
        ti = tarfile.TarInfo("demo-1.0/PKG-INFO")
        ti.size = len(info_blob)
        tf.addfile(ti, io.BytesIO(info_blob))
        for name, content in extra_files:
            blob = content.encode()
            ti2 = tarfile.TarInfo(name)
            ti2.size = len(blob)
            tf.addfile(ti2, io.BytesIO(blob))


def test_read_sdist_tgz(tmp_path):
    p = str(tmp_path / "demo-1.0.tar.gz")
    make_sdist_tgz(p, ["License-Expression: Apache-2.0"],
                   [("demo-1.0/LICENSE", "text")])
    meta, names = read_sdist(p)
    assert meta.get("License-Expression") == "Apache-2.0"
    assert "demo-1.0/PKG-INFO" in names
    assert "demo-1.0/LICENSE" in names


def test_read_sdist_zip(tmp_path):
    p = str(tmp_path / "demo-1.0.zip")
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("demo-1.0/PKG-INFO",
                    "Metadata-Version: 2.4\nName: demo\nVersion: 1.0\nLicense: MIT\n")
    meta, names = read_sdist(p)
    assert meta.get("License") == "MIT"


def test_read_sdist_no_pkg_info(tmp_path):
    p = str(tmp_path / "demo-1.0.tar.gz")
    with tarfile.open(p, "w:gz") as tf:
        ti = tarfile.TarInfo("demo-1.0/setup.py")
        blob = b""
        ti.size = 0
        tf.addfile(ti, io.BytesIO(blob))
    with pytest.raises(DistReadError):
        read_sdist(p)


def test_read_sdist_missing_file():
    with pytest.raises(DistReadError):
        read_sdist("/nonexistent/demo-1.0.tar.gz")


def test_read_sdist_bad_extension(tmp_path):
    p = str(tmp_path / "demo.txt")
    with open(p, "w") as fh:
        fh.write("hello")
    with pytest.raises(DistReadError):
        read_sdist(p)


def test_read_installed_pip():
    meta, names = read_installed("pip")
    assert meta.get("Name").lower() == "pip"
    assert names  # file list non-empty


def test_read_installed_missing():
    with pytest.raises(DistReadError):
        read_installed("no-such-distribution-xyz-123")


def test_find_license_files():
    names = [
        "demo-1.0.dist-info/METADATA",
        "demo-1.0.dist-info/LICENSE",
        "demo-1.0/COPYING.txt",
        "demo-1.0/NOTICE",
        "demo-1.0/src/mod.py",
        "demo-1.0/README.md",
    ]
    found = find_license_files(names)
    assert "demo-1.0.dist-info/LICENSE" in found
    assert "demo-1.0/COPYING.txt" in found
    assert "demo-1.0/NOTICE" in found
    assert "demo-1.0/src/mod.py" not in found
    assert "demo-1.0/README.md" not in found


def test_find_license_files_case_insensitive():
    assert find_license_files(["x/Licence.md"]) == ["x/Licence.md"]
    assert find_license_files(["x/license"]) == ["x/license"]
