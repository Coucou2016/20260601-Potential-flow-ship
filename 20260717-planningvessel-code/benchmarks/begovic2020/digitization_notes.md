# Begovic 2020 EFD digitization notes

## Purpose

Fridsma configurations A and B provide useful motion, phase and acceleration
checks, but the predeclared long-wave linear subset contains too few points to
bracket a response peak. Figures 6--8 of Kahramanoglu et al. (2020) contain
eight monohedral experimental points at each of three speeds. This benchmark is
therefore used to decide whether the computed heave and pitch peak frequencies
are physically located, not merely whether a boundary value is largest.

## Source separation

The red filled triangles labelled `EFD` are the experimental results originally
reported by Begovic et al. (2014). Green dashed circles and other lines are
computational results and are excluded. Table 1 and Table 4 values are direct
transcriptions. Only the red-marker ordinates are graph-digitized.

## Coordinate calibration

The six embedded graph rasters are all 607 by 540 pixels. Their common
horizontal axis maps `lambda/L = 0.5 ... 4.5` to pixel centers `79 ... 533`.
The vertical zero and top tick map to rows 479 and 63. Figure-specific ordinate
limits are 1.6, 1.8 and 2.0. The script evaluates the red mask in a 15-pixel
window centered at each Table 4 wavelength ratio.

The plots contain a red EFD legend marker whose horizontal position overlaps
the C7 data window. Both marker candidates are preserved in
`begovic2020_digitization_audit.csv`; the physical data marker is selected by
continuity between the unique C6 and C8 candidates. No model prediction is used
in that selection.

## Uncertainty and use

The assigned absolute ordinate uncertainty is the larger of 0.01 and four
vertical pixels converted with the relevant ordinate scale. It covers marker
thickness, JPEG antialiasing and plausible axis-line-center uncertainty. The
tabulated wave conditions are not assigned graph-reading uncertainty.

The resulting benchmark has five geometrically internal experimental maxima:

- `Fn_B=1.67`: heave;
- `Fn_B=2.26`: heave and pitch;
- `Fn_B=2.82`: heave and pitch.

The `Fn_B=1.67` pitch maximum is at the longest measured wavelength and remains
explicitly unresolved. The broad `Fn_B=2.26` heave maximum is internal, but its
prominence above the adjacent points is smaller than the assigned digitization
uncertainty, so it is also excluded from the hard peak count. The remaining
four peaks cover all three speeds and both motions and form the hard Gate 2
peak-frequency set.
