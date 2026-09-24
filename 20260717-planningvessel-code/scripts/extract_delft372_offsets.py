from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.datasets import extract_delft372_offsets_from_markdown, write_delft372_offsets_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Delft 372 demihull offsets from B2 Markdown.")
    parser.add_argument("markdown", help="Path to B2.md.")
    parser.add_argument("--out", required=True, help="Output directory for offsets/raw/audit CSV files.")
    args = parser.parse_args()

    extraction = extract_delft372_offsets_from_markdown(Path(args.markdown))
    paths = write_delft372_offsets_dataset(extraction, Path(args.out))
    for name, path in paths.items():
        print(f"{name}: {path}")
    print(f"stations: {len(extraction.stations)}")
    print(extraction.note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
