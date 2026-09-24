// This file implements the FirstOrder class.

#include "FirstOrder.h"
#include "OW3DConstants.h"
#include "HDF_DataBase.h"

OW3DSeakeeping::FirstOrder::FirstOrder(
    const OW3DSeakeeping::Grid::GridData &gridData,
    const Modes::Simulation &simulationData,
    CompositeGrid &cg) : gridData_(&gridData), boundariesData_(&gridData.boundariesData), cg_(&cg)
{
  npots_ = 10;
  results_folder_ = UserInput.project_name + '_' + program_name;
  time_domain_folder_ = UserInput.project_name + '_' + OW3DSeakeeping::time_domain_program;
  gx_wu_bcs_tag_ = (OW3DSeakeeping::GX_WU_BCS && UserInput.res_runs.size() != 0) ? 1 : 0;

  transformSupplied_ = false;
  motionSupplied_ = false;
  forceCalc_ = false;
  hydroCalc_ = false;
  raoCalc_ = false;
  exciteCalc_ = false;
  if (gridData_->triangulation.patches.size() == 0)
    integrator_ = OW3DSeakeeping::GetIntegratorOverBody(cg, gridData.boundariesData);
  simulationData_ = simulationData;
  paddingMultiple_ = UserInput.zero_padding_multiple;

  allRuns_ = UserInput.all_runs;
  resistance_runs_ = UserInput.res_runs;
  radiation_runs_ = UserInput.rad_runs;
  gmodes_runs_ = UserInput.gmd_runs;
  diffraction_runs_ = UserInput.dif_runs;
  wlData_ = gridData.wlData;

  // -----------------------------------------------
  // Allocate memory for force fitting coefficients
  // -----------------------------------------------

  if (diffraction_runs_.size() != 0) // For scattering problems
    AllocateFitcofsMemeories_(ls_fit_coeffs_scat_, 2, diffraction_runs_.size());
  if (radiation_runs_.size() != 0) // For radiation problems
    AllocateFitcofsMemeories_(ls_fit_coeffs_rad_, 2, radiation_runs_.size());
  if (resistance_runs_.size() != 0) // For wave-resistace problem
    AllocateFitcofsMemeories_(ls_fit_coeffs_res_, 3, resistance_runs_.size());
  if (gmodes_runs_.size() != 0) // For wave-resistace problem
    AllocateFitcofsMemeories_(ls_fit_coeffs_gmod_, 3, gmodes_runs_.size());

  noes_ = boundariesData_->exciting.size();
  steps_ = simulationData_.print_step_count;

  //--------------------------------------------------------
  //
  // The total shift required for each run and each time
  // step. These variables will be used when reading from
  // time domain potential data stored in the binary format.
  //
  // -------------------------------------------------------

  // For potentials file

  p_one_run_shift_ = 0.;
  p_one_step_shift_ = 0.;

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const vector<Index> &Is = be.surface_indices;

    const int l0 = Is[0].getLength();
    const int l1 = Is[1].getLength();
    const int l2 = Is[2].getLength();

    p_one_run_shift_ += l0 * l1 * l2 * npots_ * steps_;
    p_one_step_shift_ += l0 * l1 * l2 * npots_;
  }

  // For water lines file

  w_one_run_shift_ = 0.;
  w_one_step_shift_ = 0.;

  for (unsigned int line = 0; line < wlData_.size(); line++)
  {
    w_one_run_shift_ += gridData.wlData[line].size * steps_;
    w_one_step_shift_ += gridData.wlData[line].size;
  }

  // ---------------------------------------------
  //
  // Get the base flow derivatives
  //
  // ---------------------------------------------

  string dbFile = time_domain_folder_ + '/' + base_database_file;

  HDF_DataBase db;
  db.mount(dbFile, "R");

  realCompositeGridFunction base_dx(*cg_);
  base_dx.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBX));
  realCompositeGridFunction base_dy(*cg_);
  base_dy.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBY));
  realCompositeGridFunction base_dz(*cg_);
  base_dz.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBZ));

  for (unsigned int surface = 0; surface < noes_; surface++)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const vector<Index> &Is = be.surface_indices;

    d_phib_dx_.push_back(base_dx[be.grid](Is[0], Is[1], Is[2]));
    d_phib_dy_.push_back(base_dy[be.grid](Is[0], Is[1], Is[2]));
    d_phib_dz_.push_back(base_dz[be.grid](Is[0], Is[1], Is[2]));
  }

  db.get(speed_hydrostatics_, "speed hydrostatics");

  // Assign some constants just for convenience

  rho_ = OW3DSeakeeping::rho;
  U_ = UserInput.U;
  g_ = UserInput.g;
  betar_ = UserInput.beta * Pi / 180;
  h_ = gridData_->maximum_depth;
  mwl_ = gridData_->avgWl_spacing;

  // -------------------------
  // Find depth-dependent tau
  // -------------------------

  // NOTE : I wrote the following functions based on beta=0.
  //        The beta is irrelevant to the value of tau

  tau_ = 0.;

  if (U_ != 0)
  {
    double depth_k = FindCriticalDepth(0, h_, mwl_, 0, UserInput.U, UserInput.g, 1e10); // The limit wave number

    tau_ = U_ / g_ * (sqrt(g_ * depth_k * tanh(depth_k * h_)) - depth_k * U_);
  }

} // End of the constructor

OW3DSeakeeping::FirstOrder::~FirstOrder()
{
}

void OW3DSeakeeping::FirstOrder::AllocateFitcofsMemeories_(vector<vector<vector<double>>> &fitcofs, unsigned int ncofs, unsigned int runsize)
{
  unsigned int respsize = UserInput.responses.size();

  for (unsigned int i = 0; i < runsize; i++)
  {
    vector<vector<double>> temp_temp;
    fitcofs.push_back(temp_temp);
    for (unsigned int j = 0; j < respsize; j++)
    {
      vector<double> temp;
      fitcofs[i].push_back(temp);
      for (unsigned int n = 0; n < ncofs; n++)
        fitcofs[i][j].push_back(0);
    }
  }
}

const OW3DSeakeeping::FirstOrder::KsAndOmegas &OW3DSeakeeping::FirstOrder::GetAllKsAndOmegas()
{
  return allKsAndOmegas_;
}

const vector<ComplexNumbers> &OW3DSeakeeping::FirstOrder::GetResponseAmplitudeOperators()
{
  return RAO_;
}
