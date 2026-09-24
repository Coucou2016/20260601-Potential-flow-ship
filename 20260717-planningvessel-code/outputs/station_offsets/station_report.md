# Station 2.5D Prototype Report

- Station hull: `D:\Projects\20260601-Potential-flow-ship\20260717-planningvessel-code\configs\example_station_offsets.yml`
- Status: `experimental_2d_free_surface_source_panel_not_validated`
- Radiation model: `section_bem`
- Method: hard-chine station hydrostatics plus development strip/BEM added-mass/damping/excitation.
- This is not the validated boundary-integral 2.5D solver required for Ma 2005 acceptance.

## Hydrostatics

- Displacement volume: 0.0994 m^3
- Estimated/used mass: 101.885 kg
- Waterplane area: 1.126 m^2
- LCB from transom: 1.74173 m
- VCB below waterline: 0.0607351 m

## Outputs

- `added_mass_6dof.csv`
- `damping_6dof.csv`
- `restoring_6dof.csv`
- `station_rao.csv`
- `section_bem_diagnostics.csv` when `--radiation-model section_bem` is used
- `section_bem_excitation_diagnostics.csv` when `--radiation-model section_bem` is used
