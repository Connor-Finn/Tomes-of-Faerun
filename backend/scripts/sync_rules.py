"""Refresh the bundled SRD rules data.

    python backend/scripts/sync_rules.py              # latest from the main branch
    python backend/scripts/sync_rules.py --ref v4.2.0 # a pinned release

Downloads the 5e-bits/5e-database JSON files (the source of the free D&D 5e
API at https://www.dnd5eapi.co) into backend/tof/rules/data/. Downloading the
raw files takes 25 requests, where crawling the API one entry at a time would
take thousands.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tof.rules import DATA_DIR, KINDS  # noqa: E402

SOURCE = "https://raw.githubusercontent.com/5e-bits/5e-database/{ref}/src/2014/en/5e-SRD-{name}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="main", help="git branch or tag of 5e-bits/5e-database (default: main)")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for kind, name in KINDS.items():
        url = SOURCE.format(ref=args.ref, name=name)
        with urllib.request.urlopen(url, timeout=60) as response:
            data = json.load(response)
        if not isinstance(data, list) or not data:
            print(f"!! {kind}: unexpected content from {url}", file=sys.stderr)
            return 1
        (DATA_DIR / f"5e-SRD-{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                       encoding="utf-8")
        print(f"{kind:22} {len(data):4} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
