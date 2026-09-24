# MinerU local conversion (early_stage_materials)

## Environment
| Item | Value |
|------|--------|
| Python env | `early_stage_materials/.conda-mineru` (Python 3.12.13) |
| MinerU | 3.2.2 (`mineru[all]`) |
| Model source | `MINERU_MODEL_SOURCE=modelscope` (local HF/MS weights, no paid LLM API) |
| GPU | NVIDIA GeForce RTX 4090 (CUDA 12.6 driver) |
| PyTorch | 2.5.1 + `pytorch-cuda=12.4` (conda); `torch.cuda.is_available() == True` |
| Backend used | **`hybrid-auto-engine`** (formulas / complex layout) |

## Inventory (under `early_stage_materials/`)
| Type | Count |
|------|------:|
| PDF | 90 |
| Real PDF (`%PDF-` header) | 84 |
| Fake/HTML saved as `.pdf` | 6 |
| DOCX/PPTX/XLSX | 7 |

Stub examples (re-download needed): `literature/high_speed_displacement/Ma_2005_2.5D.pdf`, `literature/textbooks_surveys/Kring_1994_MIT.pdf`, `literature/semi_displacement/Arribas_2006.pdf` (HTML, not PDF).

## Output layout
Mirrored under:

`early_stage_materials/parsed_markdown/<relative-path>/`

MinerU writes e.g. `.../Savitsky_1964_planing/hybrid_auto/Savitsky_1964_planing.md` plus `images/`.

## Scripts
- `scripts/setup_mineru.ps1` — conda env, `pip install mineru[all]`, optional `mineru-models-download`
- `scripts/batch_mineru_convert.ps1` — batch all PDFs/DOCX/PPTX/XLSX; logs to `mineru_convert.log`

## Proof conversions (hybrid-auto-engine)
| File | Result |
|------|--------|
| `literature/planing_craft/Savitsky_1964_planing.pdf` | **OK** — see `parsed_markdown/literature/planing_craft/Savitsky_1964_planing/hybrid_auto/` |
| `data/npl_series/Bailey_1976_NPL_series.pdf` | **OK** |`n| `literature/textbooks_surveys/Faltinsen_Sea_Loads_BOOK.pdf` | **OK** (166 pp) |
| Kring / Ma / Arribas | **Skipped** — not valid PDF bytes |

## Resume full batch
```powershell
cd d:\Projects\20260601-Potential-flow-ship\early_stage_materials
$env:MINERU_MODEL_SOURCE = "modelscope"
.\scripts\batch_mineru_convert.ps1 -Backend hybrid-auto-engine -Resume
```

Run in background (long):
```powershell
Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ".\scripts\batch_mineru_convert.ps1" -Backend hybrid-auto-engine -Resume' -WorkingDirectory (Resolve-Path .)
```

## Logs
- `mineru_install.log` — pip/conda install
- `mineru_convert.log` — per-file conversion
- `mineru_models_download.log` — model weights (if download script finished)

## Blockers / notes
1. Initial `pip` torch was **CPU-only** → hybrid backend failed with `CUDA is not available`; fixed via **conda** `pytorch-cuda=12.4`.
2. Tsinghua PyPI mirror caused **IncompleteRead**; use `PIP_INDEX_URL=https://pypi.org/simple` for installs.
3. Six `.pdf` paths are **HTML stubs** from failed downloads — MinerU reports `No supported documents found`.
4. HTML pages: not converted by MinerU; optional **pandoc** for simple static HTML (not run here).

## Counts (update after batch)
| Metric | Value |
|--------|------:|
| Total PDFs | 90 |
| Converted (proof + batch) | 3 proof OK; batch running — see `parsed_markdown/` | |
| Failed | *see `mineru_convert.log`* |


