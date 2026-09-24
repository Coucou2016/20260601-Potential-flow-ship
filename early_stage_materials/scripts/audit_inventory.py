import json
import os
from pathlib import Path

base = Path(r"d:\Projects\20260601-Potential-flow-ship\early_stage_materials")
state_path = base / "_download_state.json"

def check(path: str):
    p = Path(path)
    if not p.exists():
        return "MISSING", 0
    if p.is_dir():
        if (p / ".git").exists():
            return "GIT_OK", 0
        n = sum(1 for _ in p.rglob("*") if _.is_file())
        return "DIR", n
    data = p.read_bytes()[:300]
    sz = p.stat().st_size
    if p.suffix.lower() == ".pdf":
        if data.startswith(b"%PDF"):
            return "PDF_OK", sz
        if b"<html" in data.lower() or b"<!doctype" in data.lower():
            return "PDF_IS_HTML", sz
        return "PDF_BAD", sz
    if p.suffix.lower() == ".zip":
        return "ZIP_OK" if sz > 1024 else "ZIP_SMALL", sz
    if p.name == ".git" or (p / ".git").exists():
        return "GIT_OK", sz
    return "FILE", sz

with state_path.open(encoding="utf-8-sig") as f:
    state = json.load(f)

issues = []
ok_count = 0
print("=" * 80)
print(f"{'ID':<32} {'STATE':<8} {'DISK':<12} {'BYTES':>10}  NOTE")
print("-" * 80)
for i in state["items"]:
    disk, sz = check(i["local_path"])
    note = ""
    if i["status"] == "ok" and disk not in ("PDF_OK", "ZIP_OK", "GIT_OK", "FILE") or (
        i["status"] == "ok" and disk == "FILE" and sz < 500
    ):
        note = "FAKE_OK"
        issues.append((i["id"], "marked ok but invalid", i["local_path"]))
    elif i["status"] in ("paywall", "failed") and disk == "PDF_OK":
        note = "HAS_FILE"
    elif i["status"] in ("paywall", "failed") and disk == "PDF_IS_HTML":
        note = "HTML_STUB"
        issues.append((i["id"], "paywall HTML stub only", i["local_path"]))
    elif i["status"] in ("paywall", "failed") and disk == "MISSING":
        issues.append((i["id"], i["status"], i["local_path"]))
    elif disk == "MISSING" and i["status"] == "ok":
        note = "MISSING"
        issues.append((i["id"], "ok but missing", i["local_path"]))
    if i["status"] == "ok" and not note:
        ok_count += 1
    print(f"{i['id']:<32} {i['status']:<8} {disk:<12} {sz:>10}  {note}")

# Git without state
print("\n--- Git repos on disk ---")
for sub in [
    "code/potential_flow_seakeeping",
    "code/planing_semiempirical",
    "code/maneuvering_gnc",
]:
    d = base / sub
    if d.exists():
        for child in d.iterdir():
            if child.is_dir():
                git = (child / ".git").exists()
                print(f"  {child.name}: git={git}")

# Plan gaps (not in manifest)
print("\n--- Original plan gaps (not in download script) ---")
gaps = [
    "Faltinsen Sea Loads full book PDF (only OSTI catalog page)",
    "Bailey 1976 NPL series full report/data (only Semantic Scholar metadata JSON)",
    "TU Delft 372 experimental report (motions, coeffs) - partial portal HTML only",
    "Molland Ship Resistance and Propulsion full book (metadata page only)",
    "2018 comprehensive strip-theory review (SciDirect) - not in manifest",
    "Excluded by design: OpenFOAM, waves2Foam, olaFlow, REEF3D, maneuveringLib, DualSPHysics, PySPH",
]
for g in gaps:
    print(f"  - {g}")

print(f"\n=== SUMMARY: {ok_count}/{len(state['items'])} truly complete in state ===")
print(f"=== ISSUES TO FIX: {len(issues)} ===")
for x in issues:
    print(f"  [{x[1]}] {x[0]}")
