# Station 2.5D Prototype Report

- Station hull: `D:\Projects\20260601-Potential-flow-ship\20260717-planningvessel-code\configs\example_station_hull.yml`
- Status: `experimental_2d_free_surface_source_panel_not_validated`
- Radiation model: `section_bem`
- Method: hard-chine station hydrostatics plus development strip/BEM added-mass/damping/excitation.
- This is not the validated boundary-integral 2.5D solver required for Ma 2005 acceptance.

## Hydrostatics

- Displacement volume: 2.44927 m^3
- Estimated/used mass: 2510.5 kg
- Waterplane area: 15.7674 m^2
- LCB from transom: 4.09907 m
- VCB below waterline: 0.107267 m

## Outputs

- `added_mass_6dof.csv`
- `damping_6dof.csv`
- `station_geometry_audit.csv`
- `restoring_6dof.csv`
- `station_rao.csv`
- `section_bem_diagnostics.csv` when an experimental section solver is used
- `section_bem_multimode_radiation_diagnostics.csv` for `section_bem` runs
- `section_bem_excitation_diagnostics.csv` when an experimental section solver is used
- `forward_speed_assembly_diagnostics.csv` for `strip_2p5d_forward` and `hybrid_forward_coupling` runs
