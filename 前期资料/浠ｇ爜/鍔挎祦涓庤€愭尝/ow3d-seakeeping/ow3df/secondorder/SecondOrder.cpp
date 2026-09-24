// this file contains the implementation of the "SecondOrderClass".

#include "SecondOrder.h"
#include "OW3DConstants.h"

OW3DSeakeeping::SecondOrder::SecondOrder(
    const OW3DSeakeeping::Grid::GridData &gridData,
    CompositeGrid &cg,
    const OW3DSeakeeping::FirstOrder::KsAndOmegas &allKsAndOmegas,
    const vector<ComplexNumbers> &RAO) : gridData_(&gridData),
                                         cg_(&cg),
                                         boundariesData_(&gridData.boundariesData),
                                         allKsAndOmegas_(allKsAndOmegas)
{
  results_folder_ = UserInput.project_name + '_' + program_name;
  time_domain_folder_ = UserInput.project_name + '_' + OW3DSeakeeping::time_domain_program;
  radiation_runs_ = UserInput.rad_runs;
  diffraction_runs_ = UserInput.dif_runs;

  NPOTENS_ = 10;  // NUMBER OF VELOCITY POTENTIAL TYPE READ AS THE BINARY.
  FarPots_ = 4;   // NUMBER OF VELOCITY POTENTIAL TYPE USED IN THE  FAR-FIELD CALCULATION.
  NTHETA_ = 100;  // NUMBER OF DESIRED POINTS FOR THE LINE INTEGRATION IN THE FAR-FIELD METHOD
  OrderLine_ = 4; // ORDER OF THE LINE INTEGRATION IN THE FAR-FIELD METHOD
  if (gridData_->triangulation.patches.size() == 0)
    integrator_ = OW3DSeakeeping::GetIntegratorOverBody(cg, gridData.boundariesData);
  NES_ = boundariesData_->exciting.size();
  flength_ = allKsAndOmegas_.omegae.size();

  rCenter_.resize(3);

  rCenter_[0] = UserInput.rotation_centre[0];
  rCenter_[1] = UserInput.rotation_centre[1];
  rCenter_[2] = UserInput.rotation_centre[2];

  numberOFIntegrations_ = 1;

  if (gridData_->halfSymmetry)
  {
    numberOFIntegrations_ = 2;
  }

  RAOs_ = RAO;
  wlData_ = gridData.wlData;

  // ---------------------------------------------
  // Initialize the data structures
  // ---------------------------------------------

  nDrfNer_ = 6;
  nDrfFar_ = 6;

  forces_nearField_.resize(nDrfNer_, flength_);
  forces_farField_.resize(nDrfFar_, flength_);
  forces_salvesen_.resize(nDrfFar_, flength_);

  for (unsigned int f = 0; f < flength_; f++)
  {
    for (unsigned int i = 0; i < nDrfNer_; i++)
      forces_nearField_(i, f) = 0.;
    for (unsigned int i = 0; i < nDrfFar_; i++)
      forces_farField_(i, f) = 0.;
    for (unsigned int i = 0; i < nDrfFar_; i++)
      forces_salvesen_(i, f) = 0.;
  }

  xi1_re_ = xi1_im_ = 0.;
  xi2_re_ = xi2_im_ = 0.;
  xi3_re_ = xi3_im_ = 0.;

  alpha1_re_ = alpha1_im_ = 0.;
  alpha2_re_ = alpha2_im_ = 0.;
  alpha3_re_ = alpha3_im_ = 0.;

  phi_.resize(*boundariesData_);
  d_phi_dx_.resize(*boundariesData_);
  d_phi_dy_.resize(*boundariesData_);
  d_phi_dz_.resize(*boundariesData_);
  d_phi_dxx_.resize(*boundariesData_);
  d_phi_dyy_.resize(*boundariesData_);
  d_phi_dzz_.resize(*boundariesData_);
  d_phi_dxy_.resize(*boundariesData_);
  d_phi_dxz_.resize(*boundariesData_);
  d_phi_dyz_.resize(*boundariesData_);
  d_phi_dn_.resize(*boundariesData_);

  sym_phi_.resize(*boundariesData_);
  sym_d_phi_dz_.resize(*boundariesData_);
  sym_d_phi_dxz_.resize(*boundariesData_);
  sym_d_phi_dyz_.resize(*boundariesData_);
  asm_phi_.resize(*boundariesData_);
  asm_d_phi_dz_.resize(*boundariesData_);
  asm_d_phi_dxz_.resize(*boundariesData_);
  asm_d_phi_dyz_.resize(*boundariesData_);

  phi_rd_.resize(*boundariesData_);
  d_phi_dx_rd_.resize(*boundariesData_);
  d_phi_dy_rd_.resize(*boundariesData_);
  d_phi_dz_rd_.resize(*boundariesData_);

  phi_sc_.resize(*boundariesData_);
  d_phi_dx_sc_.resize(*boundariesData_);
  d_phi_dy_sc_.resize(*boundariesData_);
  d_phi_dz_sc_.resize(*boundariesData_);

  // -----------------------------------------------------------
  //
  // ALLOCATE AND OBTAIN THE FDCOEFFICIENTS FOR LINE INTEGRATION
  //
  // -----------------------------------------------------------

  fdC_ = FdAllCoefficients(OrderLine_ / 2, OrderLine_ / 2);

  fdCleft_.resize(OrderLine_);
  fdCright_.resize(OrderLine_);

  for (unsigned int i = 0; i < OrderLine_; i++)
  {
    fdCleft_[i] = FdAllCoefficients(i, OrderLine_ - i);
    fdCright_[i] = FdAllCoefficients(OrderLine_ - i, i);
  }

  // -----------------------------------------------------------------
  // Get the base flow derivatives and mterms from hdf database file
  // -----------------------------------------------------------------

  string dbFile = time_domain_folder_ + '/' + base_database_file;
  HDF_DataBase db;
  db.mount(dbFile, "R");

  base_dx_.updateToMatchGrid(*cg_), base_dx_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBX));
  base_dy_.updateToMatchGrid(*cg_), base_dy_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBY));
  base_dz_.updateToMatchGrid(*cg_), base_dz_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBZ));
  base_dxx_.updateToMatchGrid(*cg_), base_dxx_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBXX));
  base_dyy_.updateToMatchGrid(*cg_), base_dyy_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBYY));
  base_dzz_.updateToMatchGrid(*cg_), base_dzz_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBZZ));
  base_dxy_.updateToMatchGrid(*cg_), base_dxy_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBXY));
  base_dxz_.updateToMatchGrid(*cg_), base_dxz_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBXZ));
  base_dyz_.updateToMatchGrid(*cg_), base_dyz_.get(db, OW3DSeakeeping::BaseflowStrings.at(PHIBYZ));

  realCompositeGridFunction m1(*cg_), m2(*cg_), m3(*cg_), m4(*cg_), m5(*cg_), m6(*cg_);

  m1.get(db, OW3DSeakeeping::BaseflowStrings.at(M1));
  m2.get(db, OW3DSeakeeping::BaseflowStrings.at(M2));
  m3.get(db, OW3DSeakeeping::BaseflowStrings.at(M3));
  m4.get(db, OW3DSeakeeping::BaseflowStrings.at(M4));
  m5.get(db, OW3DSeakeeping::BaseflowStrings.at(M5));
  m6.get(db, OW3DSeakeeping::BaseflowStrings.at(M6));

  for (unsigned int surface = 0; surface < NES_; surface++)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const vector<Index> &Is = be.surface_indices;

    mterms_.m1.push_back(m1[be.grid](Is[0], Is[1], Is[2]));
    mterms_.m2.push_back(m2[be.grid](Is[0], Is[1], Is[2]));
    mterms_.m3.push_back(m3[be.grid](Is[0], Is[1], Is[2]));
    mterms_.m4.push_back(m4[be.grid](Is[0], Is[1], Is[2]));
    mterms_.m5.push_back(m5[be.grid](Is[0], Is[1], Is[2]));
    mterms_.m6.push_back(m6[be.grid](Is[0], Is[1], Is[2]));
  }

  // -------------------------------------------------------------------------
  // REAL AND IMAGINARY PARTS OF THE COMPLEX INTEGRAND OF THE KOCHINS FUNCTION
  // -------------------------------------------------------------------------

  KOCHIN_INTEGRAND_REAL_.updateToMatchGrid(*cg_);
  KOCHIN_INTEGRAND_IMAG_.updateToMatchGrid(*cg_);
  KOCHIN_INTEGRAND_REAL_ = 0.;
  KOCHIN_INTEGRAND_IMAG_ = 0.;

  // --------------------------------------------
  // Some shorter names
  // --------------------------------------------

  rho_ = OW3DSeakeeping::rho;
  U_ = UserInput.U;
  g_ = UserInput.g;
  betar_ = UserInput.beta * Pi / 180;
  h_ = gridData_->maximum_depth;
  sin_betar_ = sin(betar_);
  cos_betar_ = cos(betar_);

  // Turn the following on if
  // the BCs in the Kochin function
  // should be calculated based on
  // their exact closed-form relation.

  bcsExact_ = 1;

  //  The gwlc_ variable

  gwlc_.resize(wlData_.size());
  for (unsigned int i = 0; i < wlData_.size(); i++)
    gwlc_[i].resize(wlData_[i].n1.size());

  // -----------------------------------------------------
  // Open the frequency-domain files for wave drift force
  // -----------------------------------------------------

  if (OW3DSeakeeping::UserInput.wave_drift)
  {
    if (transform_only_pots_for_drift)
    {
      body_radi_pot_file_ = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_radiation_binary_file;
      body_scat_pot_file_ = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_scattering_binary_file;
      waterline_elev_file_ = results_folder_ + '/' + OW3DSeakeeping::fdomain_waterline_binary_file;
      body_radi_fin_.open(body_radi_pot_file_, ios_base::in | ios_base::binary);
      body_scat_fin_.open(body_scat_pot_file_, ios_base::in | ios_base::binary);
      wline_fin_.open(waterline_elev_file_, ios_base::in | ios_base::binary);

      if (!wline_fin_.is_open() || !body_scat_fin_.is_open() || !body_radi_fin_.is_open())
        throw runtime_error(GetColoredMessage("\n\t Error (OW3D), SecondOrder::SecondOrder.cpp.\n\t No frequency-domain data found for computing wave drift force.", 0));
    }
    else
    {
      body_pot_file_ = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_binary_file;
      waterline_elev_file_ = results_folder_ + '/' + OW3DSeakeeping::fdomain_waterline_binary_file;
      body_fin_.open(body_pot_file_, ios_base::in | ios_base::binary);
      wline_fin_.open(waterline_elev_file_, ios_base::in | ios_base::binary);

      if (!wline_fin_.is_open() || !body_fin_.is_open())
        throw runtime_error(GetColoredMessage("\n\t Error (OW3D), SecondOrder::SecondOrder.cpp.\n\t No frequency-domain data found for computing wave drift force.", 0));
    }
  }

  phi0_.resize(radiation_runs_.size());
  phi0x_.resize(radiation_runs_.size());
  phi0y_.resize(radiation_runs_.size());
  phi0z_.resize(radiation_runs_.size());
  phi0xx_.resize(radiation_runs_.size());
  phi0yy_.resize(radiation_runs_.size());
  phi0zz_.resize(radiation_runs_.size());
  phi0xy_.resize(radiation_runs_.size());
  phi0xz_.resize(radiation_runs_.size());
  phi0yz_.resize(radiation_runs_.size());
  for (unsigned int run = 0; run < radiation_runs_.size(); run++)
  {
    for (unsigned int surface = 0; surface < NES_; surface++)
    {
      const Single_boundary_data &be = boundariesData_->exciting[surface];
      const vector<Index> &Is = be.surface_indices;

      realArray temp(Is[0], Is[1], Is[2]);
      temp = 0.;
      phi0_[run].push_back(temp);
      phi0x_[run].push_back(temp);
      phi0y_[run].push_back(temp);
      phi0z_[run].push_back(temp);
      phi0xx_[run].push_back(temp);
      phi0yy_[run].push_back(temp);
      phi0zz_[run].push_back(temp);
      phi0xy_[run].push_back(temp);
      phi0xz_[run].push_back(temp);
      phi0yz_[run].push_back(temp);
    }
  }

} // End of the constructor

OW3DSeakeeping::SecondOrder::~SecondOrder()
{
  body_fin_.close();
  wline_fin_.close();
}