# Ma 2005 Digitization Notes

## Wigley III

Current file:

- `wigley_iii_coefficients_digitized.csv`
- `journee1992_wigley_iii_forced_coefficients.csv` for external integrated-table cross-audit

Source:

- Ma 2005, Section 4.2, Wigley III at `Fn=0.4`
- Table 1 main particulars: `L=3.0 m`, `B=0.3 m`, `d=0.1875 m`, displacement volume `0.078 m^3`
- Figures 11-18, Matched BIEM theory curves for `A33`, `B33`, `A53`, `B53`, `A35`, `B35`, `A55`, `B55`

Digitization method:

- The original embedded bitonal plot images were extracted from the local Ma 2005 PDF rather than read from OCR text or parsed Markdown tables.
- Figure axes were calibrated in image-pixel coordinates and the Matched BIEM dashed curves were digitized at the frequencies recorded in the CSV.
- Each row records the source figure, journal page, extracted image name, and estimated digitization uncertainty.
- `A33/A53` at `omega_bar=2.00` and `2.23` are the current hard implementation-reproduction rows; the remaining six coefficients at `2.23` are diagnostic references for later closure.

Status:

- Original plot images and coefficient labels have been manually inspected against the PDF.
- These rows are suitable for reproducing Ma's Matched BIEM numerical results within their stated digitization uncertainty.
- They are not experimental truth. `journee1992_wigley_iii_forced_coefficients.csv` remains a separate integrated experimental comparison, and current theory-experiment differences must be reported rather than calibrated away.

## SL-7

Current file:

- `sl7_coefficients_digitized.csv`

Source:

- Ma 2005, Section 4.3, SL-7 containership at `Fn=0.3`
- Table 2 main particulars: `LBP=268.4 m`, `B=32.16 m`, `d=9.94 m`, displacement `48,364 MT`, pitch radius of gyration `0.21 LBP`
- Figures 19-26, experiment markers for `A33`, `B33`, `A53`, `B53`, `A35`, `B35`, `A55`, `B55`

Digitization method:

- Values were transcribed from the parsed Markdown details tables generated for the local Ma 2005 PDF in `early_stage_materials`.
- Parsed values prefixed with `~` were entered as approximate numerical values and flagged in `source_note`.
- The validation CSV uses `length_m=LBP` and converts displacement mass to volume with `rho=1025 kg/m^3`.

Status:

- Good enough to activate a development validation gate.
- Still needs an independent manual audit against the original figure images before treating the values as final benchmark data.
