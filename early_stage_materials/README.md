# Early-stage materials (potential-flow / seakeeping / planing)

Local mirror of references, open-source tools, and benchmark data for high-speed displacement, semi-displacement, and planing craft work. Downloads are resumable via `_download_state.json`.

## Layout

| Path | Contents |
|------|----------|
| `literature/high_speed_displacement` | 2.5D, water entry, high-speed displacement papers |
| `literature/semi_displacement` | Semi-displacement / transitional regime |
| `literature/planing_craft` | Savitsky, Fridsma, planing reviews |
| `literature/wind_waves_maneuvering` | Environmental loads, maneuvering |
| `literature/textbooks_surveys` | STF, Faltinsen, Kring, textbook metadata |
| `code/potential_flow_seakeeping` | Nemoh, Capytaine, pdstrip, HAMS, BEMRosetta, OW3D |
| `code/planing_semiempirical` | python-openplaning, binder-openplaning |
| `code/maneuvering_gnc` | MMG, ShipMMG, MSS, PythonVehicleSimulator |
| `data/kcs_benchmark`, `data/delft_372`, `data/npl_series`, `data/other_benchmarks` | Hull benchmarks |

## Excluded (not downloaded)

- OpenFOAM / waves2Foam / olaFlow / REEF3D / maneuveringLib
- DualSPHysics / PySPH / Capasso 2023 SPH planing paper

## Resume downloads

```powershell
cd d:\Projects\20260601-Potential-flow-ship
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
powershell -ExecutionPolicy Bypass -File early_stage_materials\scripts\download_all.ps1
```

- Skips items with `status=ok` and matching file size
- Uses `curl -C -` for HTTP; shallow `git clone` for repos
- DOI items: Unpaywall + Semantic Scholar OA fallbacks
- Exponential backoff on failures

## 中文说明

本目录由原 `前期资料` 迁移为全英文路径，避免 Windows 控制台与工具链中文路径乱码。状态文件 `_download_state.json` 与日志 `download.log` 位于本目录根下。付费墙文献标记为 `paywall`，可手动放入对应 `literature/` 子目录后将该条 `status` 改为 `ok` 再运行脚本校验。
