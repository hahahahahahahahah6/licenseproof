# licenseproof

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![No dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](pyproject.toml)

**Your package has a license. Your wheel doesn't say so.**

Real case, still reproducible today:
[protocolbuffers/protobuf#29440](https://github.com/protocolbuffers/protobuf/issues/29440).
The `protobuf-7.36.0` wheel's METADATA says `License: 3-Clause BSD License` —
free text, not an SPDX expression — and carries no `License-Expression` field
at all (Metadata-Version 2.1). To be precise: the wheel *does* ship a
`dist-info/LICENSE` file, so this is "missing License-Expression (PEP 639)",
not "no license at all". A previous fix attempt (#9441) didn't fully fix it;
the issue is still open. Any compliance tooling that keys on SPDX expressions
sees this wheel as unparseable.

A sharper flavor of the same disease:
[ag-ui-protocol/ag-ui#1927](https://github.com/ag-ui-protocol/ag-ui/issues/1927) —
the `ag_ui_strands-0.1.9` wheel has `License: None`, no `License-Expression`,
no `License-File`, and zero license files anywhere in the archive. The
monorepo root is MIT-licensed, but the published artifact inherits none of it
(the hatch wheel config only includes `src/`). Compliance scanners flag it
"unknown license", which blocks enterprise adoption outright.

licenseproof checks that a published Python artifact actually carries usable
license information — the release-integrity question nobody's CI asks.

This is deliberately *not* a generic license scanner (pip-licenses, ScanCode
already cover that). It answers one narrow question: does this wheel/sdist
contain license metadata *and* license text a compliance tool can use?

Part of the release-integrity series:
[readmeta](https://github.com/hahahahahahahahah6/readmeta) (did your README
render?), [wheeltruth](https://github.com/hahahahahahahahah6/wheeltruth) (did
your wheel ship complete?), [casecrash](https://github.com/hahahahahahahahah6/casecrash)
(will your filenames survive checkout?),
[tagtruth](https://github.com/hahahahahahahahah6/tagtruth) (does the tag match
the release?),
[wheelreach](https://github.com/hahahahahahahahah6/wheelreach) (can your Python
actually install it?),
[entryprobe](https://github.com/hahahahahahahahah6/entryprobe) (does the
installed CLI actually start?), licenseproof (does the artifact say what
license it's under?).

## Quickstart

```bash
pip install licenseproof
licenseproof check --wheel dist/mypackage-1.0-py3-none-any.whl
```

```
source:  dist/mypackage-1.0-py3-none-any.whl
verdict: LEGACY_LICENSE
detail:  License: 'MIT' (free text, not SPDX); no License-Expression (PEP 639)

clean (legacy license info is a warning; use --require-spdx to fail)
```

```bash
licenseproof check --sdist dist/mypackage-1.0.tar.gz
licenseproof check --package mypackage          # installed distribution
licenseproof check --wheel dist/x.whl --require-spdx
licenseproof check --wheel dist/x.whl --format json
```

Exit codes: `0` clean, `1` problems found, `2` errors (unreadable artifact, bad args).

## Verdicts

| Verdict | Meaning | Fails? |
|---|---|---|
| `LICENSE_OK` | SPDX `License-Expression` present; any `License-File` references exist in the dist | no |
| `LEGACY_LICENSE` | only old-style license info — free-text `License:` field, trove classifiers, and/or undeclared license text files; no `License-Expression` | only with `--require-spdx` |
| `MISSING_LICENSE` | no license metadata *and* no license text files in the dist | yes |
| `LICENSE_FILE_MISSING` | `License-File` metadata references files absent from the dist | yes |

Design notes:

- `LEGACY_LICENSE` is a warning by default, not a failure. Most of PyPI
  predates PEP 639; failing every one of them would be noise, not signal.
  `--require-spdx` is the strict mode for projects that have decided to move.
- A `License:` field containing `UNKNOWN` (or blank) counts as absent —
  that's setuptools' default, not information.
- `License-File` globs are matched leniently (full path, basename, trailing
  suffix): PEP 639 values are project-root-relative while wheels store files
  under `*.dist-info/licenses/`.
- An unparseable situation is never a silent pass: a `License-File`
  reference that matches nothing is its own failing verdict, not ignored.

## What licenseproof does not verify

It checks the *presence and machine-readability* of license information, not
its meaning. It does not interpret license compatibility (can MIT depend on
GPL?), validate that an SPDX expression is a real SPDX identifier, or offer
any legal interpretation. For "what does this license obligate me to do",
use a real compliance tool — licenseproof just makes sure the artifact gives
that tool something to work with.
