"""licenseproof CLI."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .checker import LicenseCheck, check_dist, is_problem
from .dist import DistReadError, read_installed, read_sdist, read_wheel


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="licenseproof",
        description="Check that a Python artifact carries usable license information.",
    )
    p.add_argument("--version", action="version", version="licenseproof " + __version__)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="check one wheel, sdist, or installed package")
    src = c.add_mutually_exclusive_group(required=True)
    src.add_argument("--wheel", metavar="FILE", help="wheel file to check")
    src.add_argument("--sdist", metavar="FILE", help="sdist file to check")
    src.add_argument(
        "--package", metavar="NAME", help="installed distribution name to check"
    )
    c.add_argument(
        "--require-spdx",
        action="store_true",
        help="treat legacy (non-SPDX) license info as a failure",
    )
    c.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="output format (default text)",
    )
    return p


def check_to_dict(check: LicenseCheck) -> dict:
    return {
        "source": check.source,
        "license_expression": check.license_expression,
        "license_text": check.license_text,
        "license_classifiers": check.license_classifiers,
        "license_file_refs": check.license_file_refs,
        "license_files_found": check.license_files_found,
        "missing_refs": check.missing_refs,
        "verdict": check.verdict,
        "detail": check.detail,
    }


def format_text(check: LicenseCheck, require_spdx: bool) -> str:
    lines = [
        f"source:  {check.source}",
        f"verdict: {check.verdict}",
        f"detail:  {check.detail}",
    ]
    problem = is_problem(check, require_spdx)
    lines.append("")
    lines.append("1 problem" if problem else "clean")
    if check.verdict == "LEGACY_LICENSE" and not require_spdx:
        lines[-1] += " (legacy license info is a warning; use --require-spdx to fail)"
    return "\n".join(lines)


def cmd_check(args: argparse.Namespace) -> int:
    try:
        if args.wheel:
            meta, names = read_wheel(args.wheel)
            source, flavor = args.wheel, "wheel"
        elif args.sdist:
            meta, names = read_sdist(args.sdist)
            source, flavor = args.sdist, "sdist"
        else:
            meta, names = read_installed(args.package)
            source, flavor = f"installed:{args.package}", "installed"
    except DistReadError as exc:
        print(f"licenseproof: error: {exc}", file=sys.stderr)
        return 2

    check = check_dist(source, meta, names, flavor)
    if args.format == "json":
        print(json.dumps(check_to_dict(check), indent=2))
    else:
        print(format_text(check, args.require_spdx))
    return 1 if is_problem(check, args.require_spdx) else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
