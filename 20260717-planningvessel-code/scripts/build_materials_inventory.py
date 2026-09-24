from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATERIALS = ROOT / "early_stage_materials"
OUT = ROOT / "20260717-planningvessel-code" / "docs" / "materials_inventory.csv"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    ".venv-mineru",
    ".conda",
    ".conda-mineru",
    "site-packages",
    "node_modules",
}
KEEP_EXTS = {
    ".pdf",
    ".md",
    ".txt",
    ".html",
    ".csv",
    ".xlsx",
    ".json",
    ".py",
    ".m",
    ".f90",
    ".f95",
    ".dat",
    ".zip",
    ".inp",
    ".out",
}


def category(path: Path) -> str:
    parts = {p.lower() for p in path.relative_to(MATERIALS).parts}
    if "literature" in parts or "文献" in parts:
        return "literature"
    if "parsed_markdown" in parts:
        return "parsed_markdown"
    if "code" in parts:
        return "code"
    if "data" in parts:
        return "data"
    if "scripts" in parts:
        return "scripts"
    return "other"


def iter_files():
    for path in MATERIALS.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(MATERIALS).parts
        if any(part in SKIP_DIRS or part.startswith(".venv") or part.startswith(".conda") for part in rel_parts):
            continue
        if path.suffix.lower() not in KEEP_EXTS:
            continue
        if path.suffix.lower() == ".log":
            continue
        yield path


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in iter_files():
        rel = path.relative_to(MATERIALS)
        rows.append(
            {
                "category": category(path),
                "extension": path.suffix.lower() or "(none)",
                "size_bytes": path.stat().st_size,
                "relative_path": str(rel).replace("\\", "/"),
            }
        )
    rows.sort(key=lambda r: (r["category"], r["relative_path"]))
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "extension", "size_bytes", "relative_path"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
