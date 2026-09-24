# Digitization Notes

Source:

- Odd M. Faltinsen, Hydrodynamics of High-Speed Marine Vehicles, Figures 9.34 and 9.35.
- The local Markdown extraction links to Mathpix-cropped images:
  - Fig. 9.34: `https://cdn.mathpix.com/cropped/425baa0a-eab6-4584-a37e-072cea045b9b-402.jpg?height=575&width=838&top_left_y=1716&top_left_x=136`
  - Fig. 9.35: `https://cdn.mathpix.com/cropped/425baa0a-eab6-4584-a37e-072cea045b9b-403.jpg?height=556&width=830&top_left_y=185&top_left_x=682`

Digitized curve:

- Solid `Theory` curve only.
- Fig. 9.34 ordinate: `|eta3| / zeta_a`.
- Fig. 9.35 ordinate: `|eta5| / (k zeta_a)`, not `|eta5| / zeta_a`.
- Abscissa: `lambda / L`, where `L` is the average wetted length.

Method:

- The cropped images were inspected from `outputs/digitization`.
- Axis limits were read from the published axes: `lambda/L = 0..12` and ordinate `0..8`.
- Points were sampled along the solid theory curve with denser sampling near the resonance peak.

Expected uncertainty:

- Manual image digitization uncertainty is roughly a few percent in the low-gradient regions and can approach 5-10% around the sharp resonance peak.
- The validation tolerance for digitized peak amplitude is intentionally set to 20%.
