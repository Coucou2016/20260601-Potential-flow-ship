# Benchmark Data

This directory is for machine-readable reference data used by `python -m planing_seakeeping validate`.

Rules:

- Do not invent curve values. Add only digitized or tabulated values with source metadata.
- Keep one benchmark case per subdirectory.
- Prefer CSV for curves and YAML/Markdown for source notes.
- Record the source figure/table, coordinate definition, units, digitization tool, date, and any conversion applied.

Current benchmark gates:

- `faltinsen_ch9`: Faltinsen Ch. 9 prescribed-state eigenvalues and RAO curves.
- `fridsma`: rough-water planing-craft experiments for motion and acceleration validation.
- `katayama`: high-speed planing-craft regular-wave response and jumping/non-jumping classification.
- `ma2005`: station-based 2.5D added-mass/damping coefficient validation.
