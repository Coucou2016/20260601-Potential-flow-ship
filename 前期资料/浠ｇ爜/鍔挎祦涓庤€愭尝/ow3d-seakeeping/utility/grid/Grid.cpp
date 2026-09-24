// This file implemets the Grid class

#include "Grid.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Grid::Grid()
{
  runs_ = OW3DSeakeeping::UserInput.all_runs;
  radiation_runs_ = OW3DSeakeeping::UserInput.rad_runs;
  diffraction_runs_ = OW3DSeakeeping::UserInput.dif_runs;
  resistance_runs_ = OW3DSeakeeping::UserInput.res_runs;
  resultsDirectory_ = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;

  // Assign the output file names
  grid_data_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::grid_data_file;
  grid_wline_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::grid_wline_file;
  grid_bdata_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::grid_bdata_file;
  grid_wabcor_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::grid_wabcor_file;
  grid_symcof_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::grid_symcof_file;
  grid_hydro_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::grid_hydrostatic_file;
  grid_disk_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::grid_disk_file;
  //
  gridData_.boundaryTypes.third_periodic = -3;
  gridData_.boundaryTypes.second_periodic = -2;
  gridData_.boundaryTypes.first_periodic = -1;
  gridData_.boundaryTypes.interpolation = 0;
  gridData_.boundaryTypes.free = 1;
  gridData_.boundaryTypes.impermeable = 2;
  gridData_.boundaryTypes.exciting = 3;
  gridData_.boundaryTypes.absorbing = 4;
  gridData_.boundaryTypes.symmetry = 5;

  aString grid_name = OW3DSeakeeping::UserInput.gridFileName;
  getFromADataBase(cg_, grid_name);

  // -------------------------------------------------------------------------------
  // Note :Update is called with arguments specifying which geometric data is needed.
  // It is used to ensure that the grid data have been computed before the use.
  // -------------------------------------------------------------------------------

  cg_.update(MappedGrid::THEmask | MappedGrid::THEvertex | MappedGrid::THEcenter | MappedGrid::THEvertexBoundaryNormal | MappedGrid::THEinverseVertexDerivative);

  gridData_.nog = cg_.numberOfComponentGrids();
  gridData_.nod = cg_.numberOfDimensions();
  if (gridData_.nod != 2 && gridData_.nod != 3)
    throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::Grid.cpp.\n\t Number of dimensions is not recognised.", 0));

  ExtractBoundariesData_();
  ExtractGridData_();

  symMemory_ = false; // It gets true after calculateSymmetryCoefficients_ is called.
  ComputeSymmetryCoefficients_();

  // ------------------------------------
  // Find the type of the free surfaces
  // ------------------------------------

  for (unsigned int surface = 0; surface < gridData_.boundariesData.free.size(); surface++)
  {
    const Single_boundary_data &bf = gridData_.boundariesData.free[surface];

    gridData_.freeSurfaceTypes.push_back(FindFreeSurfaceType_(bf));
  }

  FindWallAndBodyCoordinates_(OW3DSeakeeping::sponge_length); // Used by FreeSurface class to define sponge layer.

  // -----------------------------------
  // Find the type of the body surfaces
  // -----------------------------------

  for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
  {
    const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];

    gridData_.bodySurfaceTypes.push_back(FindBodySurfaceType_(be));
  }

  // -----------------------------------
  // Initialise the hydrostatic data
  // -----------------------------------

  gridData_.hrs.volx = gridData_.hrs.voly = gridData_.hrs.volz = 0.;
  gridData_.hrs.VOLM = gridData_.hrs.MASS = 0.;
  gridData_.hrs.xb = gridData_.hrs.yb = gridData_.hrs.zb = 0.;
  gridData_.hrs.xg = gridData_.hrs.yg = gridData_.hrs.zg = 0.;
  totalNumberOfModes_ = total_number_of_rigid_modes + UserInput.number_of_gmodes;
  gridData_.hrs.complete_hydro_matrix.resize(totalNumberOfModes_, std::vector<double>(totalNumberOfModes_, 0));

  ExtractWaterlineData_();

  // -------------------------------------------------------
  // Compute kMax ann Nyquist spacing
  // -------------------------------------------------------

  int gridSizeFactor = 1; // These are
  double NyqSpacing;      // defined just
  double maxSpacing;      // for the far-field calculations.

  if (gridData_.wlData.size() == 0) // No water line (Submerged bodies)
  {
    NyqSpacing = 0.5 * (gridData_.minimum_spacing_body + gridData_.maximum_spacing_body);
    maxSpacing = gridSizeFactor * NyqSpacing;
  }
  else
  {
    NyqSpacing = gridData_.avgWl_spacing;
    maxSpacing = gridSizeFactor * NyqSpacing;
  }

  gridData_.kMax = Pi / maxSpacing;

  // -------------------------------------------------------------
  // Find the vertical coordinate of the lowest point on the body.
  // -------------------------------------------------------------

  gridData_.draft = abs(gridData_.maximum_depth);

  for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
  {
    const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
    const vector<Index> &Is = be.surface_indices;

    MappedGrid &mg = (cg_)[be.grid];
    const RealArray &v = mg.vertex();

    RealArray y(Is[0], Is[1], Is[2]);
    y = v(Is[0], Is[1], Is[2], axis2);

    double tempMin = min(y);

    if (tempMin < gridData_.draft)
      gridData_.draft = tempMin;
  }

  gridData_.draft = abs(gridData_.draft);

  ExtractLiftedVerticalCoordinates_();

  if (OW3DSeakeeping::ow3d_surface_derivative && gridData_.nod == 3)
  {
    ExtractDiscRanges_();
    ExtractSurfaceFundamentals_();
    if (print_ow3d_derivatives_verification)
      PrintOW3DDerivatives();
  }

  ComputeGModeShape_();

  BuildTriangulationData_();

  if (print_laplacian_erros)
    SetManufacturedSolution_();

} // End of the constructor

OW3DSeakeeping::Grid::~Grid()
{
  // Deallocate the memory for symmetry coefficients

  if (symMemory_)
  {
    for (unsigned int i = 0; i < runs_.size(); i++)
    {
      delete[] gridData_.symmetryCoefficients[i];
    }
    delete[] gridData_.symmetryCoefficients;
  }
  for (unsigned int i = 0; i < gridData_.triangulation.patches.size(); i++)
    delete gridData_.triangulation.patches[i].interp_object;
}

// public member functions ***

CompositeGrid *OW3DSeakeeping::Grid::GetTheGrid()
{
  return &cg_;
}

OW3DSeakeeping::Grid::GridData OW3DSeakeeping::Grid::GetGridData()
{
  return gridData_;
}

realCompositeGridFunction &OW3DSeakeeping::Grid::GetManSolMatrix()
{
  return man_system_matrix_;
}

realCompositeGridFunction &OW3DSeakeeping::Grid::GetManSolRHS()
{
  return man_system_right_;
}

realCompositeGridFunction &OW3DSeakeeping::Grid::GetManSolComp()
{
  return man_sol_comp_;
}