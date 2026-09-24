// This file contains the implementation of the FreeSurface class.

#include "FreeSurface.h"
#include "OW3DConstants.h"

OW3DSeakeeping::FreeSurface::FreeSurface(
    const OW3DSeakeeping::Grid::GridData &gridData,
    const OW3DSeakeeping::Baseflow::baseFlowData *baseFlowData,
    CompositeGridOperators &operators,
    Interpolant &interpolant) : gridData_(&gridData),
                                boundariesData_(&gridData.boundariesData), boundaryTypes_(&gridData.boundaryTypes)
{
  showfile_ = (OW3DSeakeeping::create_showfile != 0) ? true : false;
  elevfile_ = (OW3DSeakeeping::print_elevation != 0) ? true : false;
  gx_wu_bcs_tag_ = (OW3DSeakeeping::GX_WU_BCS) ? 0 : 1;

  baseFlowData_ = baseFlowData;
  resultsDirectory_ = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;
  wlinesFileName_ = resultsDirectory_ + '/' + OW3DSeakeeping::tdomain_waterline_elevation_binary_file;

  cg_ = baseFlowData->potential.getCompositeGrid();
  freeSurface_.solution_start.elevation.updateToMatchGrid(*cg_);
  freeSurface_.solution_start.potential.updateToMatchGrid(*cg_);
  freeSurface_.solution_stage.elevation.updateToMatchGrid(*cg_);
  freeSurface_.solution_stage.potential.updateToMatchGrid(*cg_);

  for (int stage = 0; stage < OW3DSeakeeping::rk_stage_count; stage++)
  {
    freeSurface_.slope.push_back(freeSurface_.solution_start);
  }

  // ----------------------------------------------------------------------------------
  // Apply operator to the free surface (necessary for differentiation of free surface)
  // ----------------------------------------------------------------------------------

  freeSurface_.solution_start.elevation.setOperators(operators);
  freeSurface_.solution_start.potential.setOperators(operators);
  freeSurface_.solution_stage.elevation.setOperators(operators);
  freeSurface_.solution_stage.potential.setOperators(operators);

  // ------------------
  // Assign interpolant
  // ------------------

  interpolant_ = interpolant;

  // ----------------------------------------
  // Extract indices (used for extrapolation)
  // ----------------------------------------

  ExtractFreeSurfaceIndices_();

  // ----------------------------------------
  // Filter or biased scheme is decided here
  // ----------------------------------------

  int a = 2;
  int b = 2;

  filter_on_ = false;

  if (filter_on_)
  {
    filt_params params;
    params.width = 11;
    params.order = 9;
    params.sigma = 0.15;
    filter_ = Filter(*cg_, gridData.boundariesData.free, params);
  }

  else if (OW3DSeakeeping::UserInput.U != 0) // (Just forward-speed problems)
  {
    a = 4; // This makes the scheme biased by two points in the upwind direction
  }

  upwind_object_ = Upwind(*cg_, baseFlowData_->fs_derivatives.dx, baseFlowData_->fs_derivatives.dz, gridData, a, b);

  d_phi_dx_.updateToMatchGrid(*cg_);
  d_eta_dx_.updateToMatchGrid(*cg_);
  d_phi_dx_ = 0.0;
  d_eta_dx_ = 0.0;

  d_phi_dz_.updateToMatchGrid(*cg_);
  d_eta_dz_.updateToMatchGrid(*cg_);
  d_phi_dz_ = 0.0;
  d_eta_dz_ = 0.0;

  if (print_ow3d_upwind_verification)
    PrintUpwindVerifications();
  if (filter_on_ && print_ow3d_filter_verification)
    PrintFilterVerifications();

  // ------------
  // Sponge layer
  // ------------

  sponge_.resize(gridData.boundariesData.free.size());

  BuildSpongLayer_(gridData.wallCoordinates, gridData.freeSurfaceTypes, OW3DSeakeeping::sponge_length);

  hom_frc_.updateToMatchGrid(*cg_);
  hom_frc_ = 0.;
} // End of the constructor

OW3DSeakeeping::FreeSurface::~FreeSurface()
{
  if (showfile_)
  {
    show_.close();
  }
}

void OW3DSeakeeping::FreeSurface::Initialise(MODE_NAMES mode_name)
{
  mode_name_ = mode_name;

  doubleBodyTag_ = 0;
  if (mode_name_ == MODE_NAMES::RESISTANCE and OW3DSeakeeping::UserInput.base_flow_type == BASE_FLOW_TYPES::DB)
    doubleBodyTag_ = 1;

  freeSurface_.solution_start.elevation = 0.0;
  freeSurface_.solution_start.potential = 0.0;
  freeSurface_.solution_stage.elevation = 0.0;
  freeSurface_.solution_stage.potential = 0.0;

  for (unsigned int stage = 0; stage < freeSurface_.slope.size(); stage++)
  {
    freeSurface_.slope[stage].elevation = 0.0;
    freeSurface_.slope[stage].potential = 0.0;
  }

  d_phi_dx_ = 0.0;
  d_eta_dx_ = 0.0;

  d_phi_dz_ = 0.0;
  d_eta_dz_ = 0.0;

  // open show file

  if (showfile_)
  {
    string filename = resultsDirectory_ + "/" + OW3DSeakeeping::ModeStrings.at(mode_name_) + '_' + OW3DSeakeeping::elevation_show_file;
    show_.open(filename.c_str());
  }
  if (elevfile_)
  {
    string create_elev_folder = "mkdir -p " + resultsDirectory_ + "/" + OW3DSeakeeping::ModeStrings.at(mode_name_);
    system(create_elev_folder.c_str());
  }
}

const realCompositeGridFunction &OW3DSeakeeping::FreeSurface::GetStagePotential()
{
  return freeSurface_.solution_stage.potential;
}

realCompositeGridFunction &OW3DSeakeeping::FreeSurface::GetElevationStart()
{
  return freeSurface_.solution_start.elevation;
}

realCompositeGridFunction &OW3DSeakeeping::FreeSurface::GetPotentialStart()
{
  return freeSurface_.solution_start.potential;
}