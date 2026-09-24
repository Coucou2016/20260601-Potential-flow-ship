# Manual download checklist

**Status (2026-06-02):** User-provided `文献.zip` has been imported. Most rows below are **DONE** — see `import_literature_report.txt`.

Still **pending** (not in zip):

| No. | Title | Save as | URL |
|:---:|-------|---------|-----|
| — | TU Delft 372 — full experimental report (motions, coeffs, wave loads) | `data/delft_372/Delft372_experimental_report.pdf` | https://research.tudelft.nl/en/publications/experimental-results-of-motions-hydrodynamic-coefficients-and-wav/ |
| — | KCS geometry (verify) | `data/kcs_benchmark/KCS_geometry.dat` | https://t2015.nmri.go.jp/kcs.html |

**Extra from zip** (not in original plan): `literature/supplementary_from_user_zip/`

---

## Full reference table (import mapping)

| No. | Type | Title | Save as | Status |
|:---:|------|-------|---------|--------|
| 1–10 | FAKE_PDF | Kring, Ma, Arribas, Donatini, Compton, Savitsky AIP, Savitsky 1964, Sun, Review 2024, Fossen | see paths in import report | **DONE** |
| 14–19 | NEW | Faltinsen Sea Loads book, Bailey NPL, Molland book, Delft CFD paper, Strip review 2018 | see `import_literature_report.txt` | **DONE** |
| 20–21 | OPTIONAL | Savitsky & Brown 1976, STF 1970 PDF | `Savitsky_Brown_1976.pdf`, `STF_1970.pdf` | **DONE** |
| 17 | NEW | Delft 372 experimental report | `Delft372_experimental_report.pdf` | **Pending** |

Resume command: `powershell -File early_stage_materials\scripts\download_all.ps1`
