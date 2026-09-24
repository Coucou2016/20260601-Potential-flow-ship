# -*- coding: utf-8 -*-
"""Import PDFs from user-provided 文献.zip into early_stage_materials."""
import json
import os
import re
import shutil
from pathlib import Path

BASE = Path(r"d:\Projects\20260601-Potential-flow-ship\early_stage_materials")
IMPORT_ROOT = BASE / "_import_literature_zip"

# (substring in source filename, relative dest under BASE)
MAPPING = [
    ("Time domain ship motions", "literature/textbooks_surveys/Kring_1994_MIT.pdf"),
    ("comprehensive study on the seakeeping", "literature/high_speed_displacement/Strip_theory_HSC_review_2018.pdf"),
    ("An efficient numerical method", "literature/high_speed_displacement/Ma_2005_2.5D.pdf"),
    ("Strip theories applied", "literature/semi_displacement/Arribas_2006.pdf"),
    ("IMPLEMENTATION OF FORWARD SPEED", "literature/textbooks_surveys/Donatini_2022_Capytaine_forward_speed.pdf"),
    ("resistance-of-a-systematic-series-of-semiplaning", "literature/planing_craft/Compton_1986_MTSN.pdf"),
    ("Savitsky_pre_planning", "literature/planing_craft/Savitsky_preplaning_AIP.pdf"),
    ("Hydrodynamic_Design_of_Planing", "literature/planing_craft/Savitsky_1964_planing.pdf"),
    ("Numerical study of planing vessels", "literature/planing_craft/Sun_Faltinsen_2010_planing.pdf"),
    ("hydrodynamics of planing hulls", "literature/planing_craft/Planing_hull_review_2024.pdf"),
    ("HOW TO INCORPORATE WIND", "literature/wind_waves_maneuvering/Fossen_2012_wind_waves.pdf"),
    ("Sea_Loads_on_Ships", "literature/textbooks_surveys/Faltinsen_Sea_Loads_BOOK.pdf"),
    ("Fatinsen_Sea_Loads", "literature/textbooks_surveys/Faltinsen_Sea_Loads_BOOK.pdf"),
    ("High Speed Displacement Vessels", "data/npl_series/Bailey_1976_NPL_series.pdf"),
    ("SHIP_RESISTANCE_AND_PROPULSION", "literature/textbooks_surveys/Molland_Ship_Resistance_Propulsion_BOOK.pdf"),
    ("Duman_Bal_OE_2022", "data/delft_372/Delft372_manoeuvring_CFD_paper.pdf"),
    ("comprehensive study on the seakeeping", "literature/high_speed_displacement/Strip_theory_HSC_review_2018.pdf"),
    ("Savitsky_Brown_76", "literature/planing_craft/Savitsky_Brown_1976.pdf"),
    ("ship-motions-and-sea-loads", "literature/textbooks_surveys/STF_1970.pdf"),
]

# Files to delete (fake/duplicate)
DELETE_REL = [
    "literature/textbooks_surveys/2022_Capytaine_forward_speed.pdf",
    "literature/textbooks_surveys/Kring_1994_MIT_test.pdf",
    "literature/textbooks_surveys/1994_MIT.pdf",
]

# Unmatched PDFs -> supplementary
SUPPLEMENTARY = BASE / "literature" / "supplementary_from_user_zip"

STATE_IDS = {
    "literature/textbooks_surveys/Kring_1994_MIT.pdf": "lit_kring_1994",
    "literature/high_speed_displacement/Ma_2005_2.5D.pdf": "lit_ma_2005",
    "literature/semi_displacement/Arribas_2006.pdf": "lit_arribas_2006",
    "literature/textbooks_surveys/Donatini_2022_Capytaine_forward_speed.pdf": "lit_donatini_2022",
    "literature/planing_craft/Compton_1986_MTSN.pdf": "lit_compton_1986",
    "literature/planing_craft/Savitsky_preplaning_AIP.pdf": "lit_savitsky_preplaning",
    "literature/planing_craft/Savitsky_1964_planing.pdf": "lit_savitsky_1964",
    "literature/planing_craft/Sun_Faltinsen_2010_planing.pdf": "lit_sun_faltinsen_2010",
    "literature/planing_craft/Planing_hull_review_2024.pdf": "lit_planing_review_2024",
    "literature/wind_waves_maneuvering/Fossen_2012_wind_waves.pdf": "lit_fossen_2012",
    "literature/textbooks_surveys/Faltinsen_Sea_Loads_BOOK.pdf": "lit_faltinsen_sea_loads_book",
    "data/npl_series/Bailey_1976_NPL_series.pdf": "lit_bailey_npl_pdf",
    "literature/textbooks_surveys/Molland_Ship_Resistance_Propulsion_BOOK.pdf": "lit_molland_book",
    "data/delft_372/Delft372_manoeuvring_CFD_paper.pdf": "data_delft372_strath",
    "literature/high_speed_displacement/Strip_theory_HSC_review_2018.pdf": "lit_strip_hsc_2018",
    "literature/planing_craft/Savitsky_Brown_1976.pdf": "lit_savitsky_brown_1976",
    "literature/textbooks_surveys/STF_1970.pdf": "lit_stf_1970_pdf",
}


def is_pdf(path) -> bool:
    p = str(path)
    if not p.lower().endswith(".pdf"):
        return False
    with open(p, "rb") as f:
        return f.read(5).startswith(b"%PDF")


def find_pdfs():
    pdfs = []
    root = str(IMPORT_ROOT)
    for dirpath, _, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".pdf"):
                pdfs.append(os.path.join(dirpath, name))
    return pdfs


def match_dest(name: str):
    for key, rel in MAPPING:
        if key.lower() in name.lower():
            return rel
    return None


def main():
    log = []
    for rel in DELETE_REL:
        p = os.path.join(BASE, rel)
        if os.path.isfile(p):
            os.remove(p)
            log.append(f"DELETED fake/duplicate: {rel}")

    pdfs = find_pdfs()
    used = set()
    copied = []

    for src in pdfs:
        name = os.path.basename(src)
        if not is_pdf(src):
            log.append(f"SKIP not PDF: {name}")
            continue
        rel = match_dest(name)
        if rel and rel in used:
            log.append(f"SKIP duplicate mapping: {name} -> {rel}")
            continue
        if rel:
            dest = os.path.join(BASE, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            used.add(rel)
            copied.append((name, rel, os.path.getsize(dest)))
            log.append(f"OK {name} -> {rel}")
        else:
            os.makedirs(SUPPLEMENTARY, exist_ok=True)
            dest = os.path.join(SUPPLEMENTARY, name)
            shutil.copy2(src, dest)
            log.append(f"SUPP {name}")

    # xlsx catalog
    for dirpath, _, files in os.walk(str(IMPORT_ROOT)):
        for name in files:
            if name.endswith(".xlsx"):
                dest = os.path.join(BASE, "literature", "textbooks_surveys", name)
                shutil.copy2(os.path.join(dirpath, name), dest)
                log.append(f"OK catalog {name}")

    # Update state file
    state_path = BASE / "_download_state.json"
    if state_path.exists():
        with state_path.open(encoding="utf-8-sig") as f:
            state = json.load(f)
        by_id = {i["id"]: i for i in state["items"]}
        for rel, item_id in STATE_IDS.items():
            dest = os.path.join(BASE, rel)
            if not os.path.isfile(dest) or not is_pdf(dest):
                continue
            sz = os.path.getsize(dest)
            if item_id in by_id:
                it = by_id[item_id]
                it["status"] = "ok"
                it["local_path"] = str(dest)
                it["bytes"] = sz
                it["last_error"] = ""
            else:
                state["items"].append({
                    "id": item_id,
                    "url": "user_zip_import",
                    "local_path": str(dest),
                    "status": "ok",
                    "bytes": sz,
                    "attempts": 0,
                    "last_error": "",
                    "alternates_tried": [],
                    "sha256": "",
                    "category": "import",
                })
        # Fix existing ids
        fixes = {
            "lit_kring_1994": "literature/textbooks_surveys/Kring_1994_MIT.pdf",
            "lit_ma_2005": "literature/high_speed_displacement/Ma_2005_2.5D.pdf",
            "lit_arribas_2006": "literature/semi_displacement/Arribas_2006.pdf",
            "lit_donatini_2022": "literature/textbooks_surveys/Donatini_2022_Capytaine_forward_speed.pdf",
            "lit_compton_1986": "literature/planing_craft/Compton_1986_MTSN.pdf",
            "lit_savitsky_preplaning": "literature/planing_craft/Savitsky_preplaning_AIP.pdf",
            "lit_sun_faltinsen_2010": "literature/planing_craft/Sun_Faltinsen_2010_planing.pdf",
            "lit_planing_review_2024": "literature/planing_craft/Planing_hull_review_2024.pdf",
            "lit_fossen_2012": "literature/wind_waves_maneuvering/Fossen_2012_wind_waves.pdf",
            "data_delft372_strath": "data/delft_372/Delft372_manoeuvring_CFD_paper.pdf",
            "lit_savitsky_brown_1976": "literature/planing_craft/Savitsky_Brown_1976.pdf",
        }
        for iid, rel in fixes.items():
            if iid in by_id:
                dest = os.path.join(BASE, rel)
                if os.path.isfile(dest) and is_pdf(dest):
                    by_id[iid]["status"] = "ok"
                    by_id[iid]["local_path"] = dest
                    by_id[iid]["bytes"] = os.path.getsize(dest)
                    by_id[iid]["last_error"] = ""
        if "lit_savitsky_1964" in by_id:
            p = os.path.join(BASE, "literature/planing_craft/Savitsky_1964_planing.pdf")
            if os.path.isfile(p) and is_pdf(p):
                by_id["lit_savitsky_1964"]["status"] = "ok"
                by_id["lit_savitsky_1964"]["local_path"] = p
                by_id["lit_savitsky_1964"]["bytes"] = os.path.getsize(p)
        with state_path.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)

    report = BASE / "import_literature_report.txt"
    report.write_text("\n".join(log), encoding="utf-8")
    print("\n".join(log))
    print(f"\nCopied {len(copied)} mapped PDFs. Report: {report}")


if __name__ == "__main__":
    main()
