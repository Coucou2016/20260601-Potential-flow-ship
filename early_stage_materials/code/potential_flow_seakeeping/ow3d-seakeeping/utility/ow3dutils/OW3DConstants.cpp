#include "OW3DConstants.h"

namespace OW3DSeakeeping
{
    // ---------------------------------------------------------------------------
    // * Input file constants
    // ---------------------------------------------------------------------------
    const string print_logo = " ----- File created by OW3D-Seakeeping ----- ";
    const unsigned int print_width = 15;
    const unsigned int print_precision = 6;
    const string ow3d_input_file_name = "ow3d.in";
    const string ow3d_mass_file_name = "ow3d.ms";
    const string ow3d_hydrostatic_file_name = "ow3d.hs";
    const string ow3d_stiffness_file_name = "ow3d.sf";
    const string ow3d_shear_stiffness_file_name = "ow3d.ssf";
    const unsigned int number_of_user_input_lines = 21;
    const unsigned int input_colon_index = 4;
    const string user_input_check_file = "ow3d.ck";
    const unsigned int total_number_of_rigid_modes = 6;
    const Input input;
    const Input::INPUT UserInput = input.getInputData();
    // ---------------------------------------------------------------------------
    // * Output files constants
    // ---------------------------------------------------------------------------
    const string print_freq_line = "Number of frequencies:";
    const string print_froude_line = "Froude number:";
    const string print_beta_line = "Beta:";
    const bool long_print = false;
    const string time_domain_program = "ow3dt";
    const string freq_domain_program = "ow3df";
    const unsigned int max_freq_divisor = 2;
    const unsigned int min_freq_print_index_option = 0;
    const string base_m_terms_file = "base.o1";
    const string base_free_dervs_file = "base.o2";
    const string base_body_dervs_file = "base.o3";
    const string base_elev_file = "base.o4";
    const string base_force_file = "base.o5";
    const string base_bccheck_file = "base.o6";
    const string base_database_file = "base.hdf";
    const string base_show_file = "base.show";
    const string base_error_file = "base.err";
    const string base_pressure_show_file = "pbase.show";
    const string abase_m_terms_file = "abase.o1";
    const string abase_free_dervs_file = "abase.o2";
    const string abase_elev_file = "abase.o4";
    const string abase_show_file = "abase.show";
    const string grid_data_file = "grid.o1";
    const string grid_wline_file = "grid.o2";
    const string grid_bdata_file = "grid.o3";
    const string grid_wabcor_file = "grid.o4";
    const string grid_symcof_file = "grid.o5";
    const string grid_hydrostatic_file = "grid.o6";
    const string grid_disk_file = "grid.o7";
    const string simulation_data_binary_file = "simula.b1";
    const string simulation_data_ascii_file = "simula.o1";
    const string time_binary_file = "time.b1";
    const string impulse_body_displacement_binary_file = "impulse.b1";
    const string impulse_body_velocity_binary_file = "impulse.b2";
    const string impulse_wave_elevation_binary_file = "impulse.b3";
    const string tdomain_body_integrals_binary_file = "tpotent.b1";
    const string tdomain_body_potentials_binary_file = "tpotent.b2";
    const string tdomain_waterline_elevation_binary_file = "tpotent.b3";
    const string fdomain_potentials_binary_file = "fpotent.b01";
    const string fdomain_potentials_no_incident_binary_file = "fpotent.b02";
    const string fdomain_potentials_radiation_binary_file = "fpotent.b03";
    const string fdomain_potentials_scattering_binary_file = "fpotent.b04";
    const string fdomain_potentials_diffraction_binary_file = "fpotent.b05";
    const string fdomain_waterline_binary_file = "fpotent.b06";
    const string fdomain_waterline_no_incident_binary_file = "fpotent.b07";
    const string fdomain_waterline_radiation_binary_file = "fpotent.b08";
    const string fdomain_waterline_scattering_binary_file = "fpotent.b09";
    const string fdomain_waterline_diffraction_binary_file = "fpotent.b10";
    const string elevation_show_file = "elevation.show";
    const string impulses_ascii_file = ".imps";
    const string radiation_impulse_force_file_extension = ".rimp";
    const string scattering_impulse_force_file_extension = ".simp";
    const string resistance_impulse_force_file_extension = ".wimp";
    const string hydro_coefficients_file_extention = ".o1";
    const string fdomain_excitation_file_extention = ".o2";
    const string fdomain_rao_file_extention = ".o3";
    const string fdomain_scattering_file_extention = ".o4";
    const string fdomain_froude_krylov_file_extention = ".o5";
    const string drift_forces_file_extention = ".o6";
    const string frequency_vectors_file = ".o7";
    const string fdomain_disp_file_extention = ".o8";
    const string least_square_status_file_extension = ".lsq";
    const string upwind_x_coefficients_file = "xUpCofs.o";
    const string upwind_z_coefficients_file = "zUpCofs.o";
    const bool create_showfile = false;
    const bool print_elevation = false;
    // ---------------------------------------------------------------------------
    // * Computations constants
    // ---------------------------------------------------------------------------
    const int rk_stage_count = 4;
    const vector<double> rk_b = {1.0 / 6.0, 1.0 / 3.0, 1.0 / 3.0, 1.0 / 6.0}; // weightings
    const vector<double> rk_c = {0.0, 0.5, 0.5, 1.0};                         // evaluation points
    const int time_order = 4;
    const double rho = 1000;
    const double frequency_cutoff = 1.0e-4;
    const double sponge_length = 0.0;
    const bool GX_WU_BCS = false;
    const bool ow3d_surface_derivative = true;
    const char *path_to_triangulations = "./patches";
    const unsigned int patch_interpolation_width = 4;
    const bool print_ow3d_derivatives_verification = false;
    const bool print_ow3d_upwind_verification = false;
    const bool print_ow3d_filter_verification = false;
    const bool print_laplacian_erros = false;
    const GMODE_TYPES gmode_type = GMODE_TYPES::EULERBERNOULLI;
    const GMODES_HYDROSTATICS gmode_hydrostatics = GMODES_HYDROSTATICS::NG;
    const double gamma_Timo = 0.00; // 0.005372616;
    const RealArray C4 = CalculateFirstCoefficients(4);
    const RealArray C4_right_neumann = CalculateFirstCoefficients(4, "right-nm");
    const RealArray C4_left_neumann = CalculateFirstCoefficients(4, "left-nm");
    const RealArray C4_right_dirichlet = CalculateFirstCoefficients(4, "right-dr");
    const RealArray C4_left_dirichlet = CalculateFirstCoefficients(4, "left-dr");
    const RealArray C2 = CalculateFirstCoefficients(2);
    const RealArray C2_right_neumann = CalculateFirstCoefficients(2, "right-nm");
    const RealArray C2_left_neumann = CalculateFirstCoefficients(2, "left-nm");
    const RealArray C2_right_dirichlet = CalculateFirstCoefficients(2, "right-dr");
    const RealArray C2_left_dirichlet = CalculateFirstCoefficients(2, "left-dr");
    const bool transform_only_pots_for_drift = false;
    const bool use_grid_symmetry_for_derivatives = true;
    const bool compute_speed_hydrostatics = false;
    // ---------------------------------------------------------------------------
    // * Constant maps
    // ---------------------------------------------------------------------------
    const map<OW3DSeakeeping::BASE_FLOW_TAGS, std::string> BaseflowStrings =
        {
            {PHIBX, "phibx"},
            {PHIBY, "phiby"},
            {PHIBZ, "phibz"},
            {PHIBXX, "phibxx"},
            {PHIBYY, "phibyy"},
            {PHIBZZ, "phibzz"},
            {PHIBXY, "phibxy"},
            {PHIBXZ, "phibxz"},
            {PHIBYZ, "phibyz"},
            {M1, "m1"},
            {M2, "m2"},
            {M3, "m3"},
            {M4, "m4"},
            {M5, "m5"},
            {M6, "m6"},
            {MF, "mf"}};
    const map<OW3DSeakeeping::MODE_NAMES, std::string> ModeStrings =
        {
            {RESISTANCE, "resistance"},
            {SURGE, "surge"},
            {HEAVE, "heave"},
            {SWAY, "sway"},
            {ROLL, "roll"},
            {YAW, "yaw"},
            {PITCH, "pitch"},
            {DIFFRACTION, "diffraction"},
            {GMODE, "gmode"}};
    const map<MODE_NAMES, string> ModePrintTags =
        {
            {SURGE, "1"},
            {SWAY, "2"},
            {HEAVE, "3"},
            {ROLL, "4"},
            {PITCH, "5"},
            {YAW, "6"},
            {GMODE, "0"}};
    const map<UPWIND_STENCIL_TYPES, string> UpwindStencilsPrintTags =
        {
            {NEUTRAL, "neu."},
            {CENTRAL, "cen."},
            {DECREM, "dec."},
            {INCREM, "inc."}};
}