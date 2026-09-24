# -*- coding: utf-8 -*-
"""Audit literature/data files vs parsed markdown outputs."""
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT_ROOT = BASE / "parsed_markdown"
SUPPORTED = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}


def is_real_pdf(p: Path) -> bool:
    with p.open("rb") as f:
        return f.read(5).startswith(b"%PDF")


def find_md(stem: str, parent_rel: Path) -> list[str]:
    hits = []
    for root in (OUT_ROOT / parent_rel, OUT_ROOT / parent_rel / stem):
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            s = p.stem
            if s in (stem, f"{stem}_cloud_vlm", f"{stem}_hybrid_auto") or s.replace("_cloud_vlm", "") == stem:
                hits.append(str(p.relative_to(BASE)))
    return hits


def page_count(p: Path):
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(p)).pages)
    except Exception:
        return None


def main():
    rows = []
    for area in ("literature", "data"):
        d = BASE / area
        if not d.exists():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in SUPPORTED:
                continue
            rel = p.relative_to(BASE)
            real = is_real_pdf(p) if p.suffix.lower() == ".pdf" else True
            hits = find_md(p.stem, rel.parent)
            pages = page_count(p) if p.suffix.lower() == ".pdf" else None
            size_mb = p.stat().st_size / (1024 * 1024)
            if hits:
                status = "OK"
            elif not real:
                status = "FAKE_PDF"
            else:
                status = "MISSING_MD"
            rows.append((status, rel, pages, size_mb, hits))

    print("STATUS     | PAGES |   MB | FILE")
    print("-" * 90)
    for status, rel, pages, size_mb, hits in rows:
        print(f"{status:10} | {pages or 'n/a':>5} | {size_mb:5.1f} | {rel}")
        for h in hits[:2]:
            print(f"             -> {h}")

    c = Counter(r[0] for r in rows)
    print(f"\nSUMMARY: {dict(c)}  total={len(rows)}")
    incomplete = [r for r in rows if r[0] != "OK"]
    if incomplete:
        print("\nINCOMPLETE:")
        for r in incomplete:
            print(f"  [{r[0]}] {r[1]}")


if __name__ == "__main__":
    main()
