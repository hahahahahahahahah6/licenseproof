"""Read license-relevant data from wheels, sdists, and installed distributions.

Stdlib only: zipfile, tarfile, email.parser, fnmatch, importlib.metadata.
"""
from __future__ import annotations

import fnmatch
import os
import re
import tarfile
import zipfile
from email.message import Message
from email.parser import Parser


class DistReadError(Exception):
    """The artifact could not be read (not a verdict -- an error, exit 2)."""


def parse_metadata(text: str) -> Message:
    return Parser().parsestr(text)


def _is_sdist_name(path: str) -> bool:
    low = path.lower()
    return low.endswith((".tar.gz", ".tgz", ".tar.bz2", ".zip"))


def read_wheel(path: str) -> tuple[Message, list[str]]:
    """Return (METADATA message, list of archive member names)."""
    if not os.path.isfile(path):
        raise DistReadError(f"wheel not found: {path}")
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise DistReadError(f"not a valid wheel zip: {path}: {exc}")
    with zf:
        names = zf.namelist()
        meta_name = next(
            (n for n in names if n.endswith(".dist-info/METADATA")), None
        )
        if meta_name is None:
            raise DistReadError(f"no .dist-info/METADATA in wheel: {path}")
        text = zf.read(meta_name).decode("utf-8", "replace")
    return parse_metadata(text), names


def _sdist_pkg_info_member(names: list[str]) -> str | None:
    # Prefer top-level PKG-INFO, else <name>-<version>/PKG-INFO.
    if "PKG-INFO" in names:
        return "PKG-INFO"
    for n in names:
        if re.fullmatch(r"[^/]+/PKG-INFO", n):
            return n
    return None


def read_sdist(path: str) -> tuple[Message, list[str]]:
    """Return (PKG-INFO message, list of archive member names)."""
    if not os.path.isfile(path):
        raise DistReadError(f"sdist not found: {path}")
    if not _is_sdist_name(path):
        raise DistReadError(f"not a recognized sdist filename: {path}")
    try:
        if path.lower().endswith(".zip"):
            zf = zipfile.ZipFile(path)
            with zf:
                names = zf.namelist()
                member = _sdist_pkg_info_member(names)
                if member is None:
                    raise DistReadError(f"no PKG-INFO in sdist: {path}")
                text = zf.read(member).decode("utf-8", "replace")
        else:
            tf = tarfile.open(path, "r:*")
            with tf:
                names = tf.getnames()
                member = _sdist_pkg_info_member(names)
                if member is None:
                    raise DistReadError(f"no PKG-INFO in sdist: {path}")
                fobj = tf.extractfile(member)
                if fobj is None:
                    raise DistReadError(f"cannot read PKG-INFO in sdist: {path}")
                text = fobj.read().decode("utf-8", "replace")
    except (tarfile.TarError, zipfile.BadZipFile, OSError) as exc:
        raise DistReadError(f"cannot read sdist {path}: {exc}")
    return parse_metadata(text), names


def read_installed(name: str) -> tuple[Message, list[str]]:
    """Return (METADATA message, list of installed file paths) for an installed dist."""
    try:
        import importlib.metadata as md
    except ImportError:  # pragma: no cover - Python 3.9 always has it
        raise DistReadError("importlib.metadata unavailable")
    try:
        dist = md.distribution(name)
    except md.PackageNotFoundError:
        raise DistReadError(f"no installed distribution named {name!r}")
    text = dist.read_text("METADATA")
    if text is None:
        # Egg-style installs expose PKG-INFO instead.
        text = dist.read_text("PKG-INFO")
    if text is None:
        raise DistReadError(f"installed distribution {name!r} has no METADATA/PKG-INFO")
    files = [str(f) for f in (dist.files or [])]
    return parse_metadata(text), files


# Basename patterns that look like license texts. Matched case-insensitively
# against each archive member's basename.
LICENSE_BASENAMES = (
    "LICENSE*",
    "LICENCE*",
    "COPYING*",
    "COPYRIGHT*",
    "NOTICE*",
    "NOTICE-*",
    "EULA*",
    "PATENTS*",
    "AGREEMENT*",
)


def find_license_files(names: list[str]) -> list[str]:
    """Return archive members whose basename looks like a license text file."""
    found = []
    for n in names:
        base = n.rsplit("/", 1)[-1]
        if not base:
            continue
        low = base.lower()
        if any(fnmatch.fnmatch(low, pat.lower()) for pat in LICENSE_BASENAMES):
            found.append(n)
    return found
