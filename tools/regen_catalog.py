#!/usr/bin/env python3

# Copyright © 2025-2026 Wenze Wei. All Rights Reserved.
#
# This file is part of Encre.
# The Encre project belongs to the Dunimd Team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# DISCLAIMER: Users must comply with applicable AI regulations.
# Non-compliance may result in service termination or legal liability.

"""Registry-repo tooling: merge ``catalog.d/*.json`` into ``catalog.json``.

Runs in the plugin registry repository (this directory is its seed).  It is
deliberately stdlib-only — plus the repo's own ``ea_cwh`` reader module — so
both CI workflows (the PR gate and the publish-on-merge index release) can
execute it without installing anything.

Modes:
    python tools/regen_catalog.py                # merge + validate (PR gate)
    python tools/regen_catalog.py --check-pypi   # also verify every pinned
                                                 # artifact is on PyPI with
                                                 # the exact promised digest
    python tools/regen_catalog.py --out F        # write catalog.json at F
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ea_cwh import SCHEMA_VERSION, validate_catalog  # noqa: E402


def merge(entries_dir: Path) -> dict:
    """Merge per-plugin entry files into one catalog document.

    Sorting by plugin name keeps regenerated documents diff-stable, so CI
    commits show real content changes only.
    """
    entries = []
    for path in sorted(entries_dir.glob("*.json")):
        entries.append(json.loads(path.read_text(encoding="utf-8-sig")))
    entries.sort(key=lambda e: str(e.get("name", "")))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "registry": "https://pypi.org",
        "plugins": entries,
    }


def check_pypi(doc: dict) -> list[str]:
    """Verify each catalogued artifact is actually on PyPI, byte-identical.

    The plugin author uploads to PyPI BEFORE opening the registry PR
    (``encre-plugin publish``); this is the gate that makes a merge mean
    "the pinned wheel with this exact digest is downloadable".  A squatted
    or tampered distribution file fails here, not on the user's machine.
    """
    problems: list[str] = []
    for entry in doc.get("plugins", []):
        pkg = str(entry.get("pypi_package", ""))
        version = str(entry.get("version", ""))
        url = f"https://pypi.org/pypi/{pkg}/{version}/json"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.load(resp)
        except Exception as exc:
            problems.append(f"{pkg}=={version}: not reachable on PyPI ({exc})")
            continue
        digests = {
            str(f.get("filename")): str((f.get("digests") or {}).get("sha256"))
            for f in data.get("urls", [])
        }
        for fname, meta in (entry.get("artifacts") or {}).items():
            expected = str((meta or {}).get("sha256", ""))
            if fname not in digests:
                problems.append(f"{pkg}=={version}: {fname} is not on PyPI")
            elif digests[fname] != expected:
                problems.append(
                    f"{pkg}=={version}: {fname} digest mismatch "
                    f"(index {expected} != PyPI {digests[fname]})")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entries", default=str(ROOT / "catalog.d"),
                    help="directory of per-plugin entry JSON files")
    ap.add_argument("--out", help="write the merged catalog to this path")
    ap.add_argument("--check-pypi", action="store_true",
                    help="cross-verify pinned artifacts and digests on PyPI")
    args = ap.parse_args(argv)

    doc = merge(Path(args.entries))
    violations = validate_catalog(doc)
    if violations:
        print("catalog validation FAILED:", file=sys.stderr)
        for line in violations:
            print(f"  - {line}", file=sys.stderr)
        return 1
    if args.check_pypi:
        problems = check_pypi(doc)
        if problems:
            print("PyPI cross-check FAILED:", file=sys.stderr)
            for line in problems:
                print(f"  - {line}", file=sys.stderr)
            return 1
    payload = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    print(f"catalog OK — {len(doc['plugins'])} plugins", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
