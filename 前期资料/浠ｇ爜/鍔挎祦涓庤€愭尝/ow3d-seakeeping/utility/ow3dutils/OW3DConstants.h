#ifndef __OW3D_CONSTANTS__
#define __OW3D_CONSTANTS__
#include <vector>
#include "Input.h"

namespace OW3DSeakeeping
{
    // ---------------------------------------------------------------------------
    // * Input file constants
    // ---------------------------------------------------------------------------
    extern const string ow3d_input_file_name;
    extern const string ow3d_mass_file_name;
    extern const string ow3d_hydrostatic_file_name;
    extern const string ow3d_stiffness_file_name;
    extern const string ow3d_shear_stiffness_file_name;
    extern const string user_input_check_file;
    extern const unsigned int number_of_user_input_lines;
    extern const unsigned int input_colon_index;
    extern const unsigned int total_number_of_rigid_modes;
    extern const Input::INPUT UserInput;
    // ---------------------------------------------------------------------------
    // * Output files constants
    // ---------------------------------------------------------------------------
    extern const string print_logo;
    extern const string print_freq_line;
    extern const string print_froude_line;
    extern const string print_beta_line;
    extern const string time_domain_program;
    extern const string freq_domain_program;
    extern const unsigned int max_freq_divisor;
    extern const unsigned int min_freq_print_index_option;
    extern const string program_name;
    extern const string base_m_terms_file;
    extern const string base_body_dervs_file;
    extern const string base_free_dervs_file;
    extern const string base_elev_file;
    extern const string base_show_file;
    extern const string base_force_file;
    extern const string base_database_file;
    extern const string base_error_file;
    extern const string base_bccheck_file;
    extern const string base_pressure_show_file;
    extern const string grid_data_file;
    extern const string grid_wline_file;
    extern const string grid_bdata_file;
    extern const string grid_wabcor_file;
    extern const string grid_symcof_file;
    extern const string grid_hydrostatic_file;
    extern const string grid_disk_file;
    extern const string abase_m_terms_file;
    extern const string abase_elev_file;
    extern const string abase_free_dervs_file;
    extern const string abase_show_file;
    extern const string simulation_data_binary_file;
    extern const string simulation_data_ascii_file;
    extern const string time_binary_file;
    extern const string impulse_body_displacement_binary_file;
    extern const string impulse_body_velocity_binary_file;
    extern const string impulse_wave_elevation_binary_file;
    extern const string tdomain_body_integrals_binary_file;
    extern const string tdomain_body_potentials_binary_file;
    extern const string tdomain_waterline_elevation_binary_file;
    extern const string fdomain_potentials_binary_file;
    extern const string fdomain_potentials_no_incident_binary_file;
    extern const string fdomain_potentials_radiation_binary_file;
    extern const string fdomain_potentials_scattering_binary_file;
    extern const string fdomain_potentials_diffraction_binary_file;
    extern const string fdomain_waterline_binary_file;
    extern const string fdomain_waterline_no_incident_binary_file;
    extern const string fdomain_waterline_radiation_binary_file;
    extern const string fdomain_waterline_scattering_binary_file;
    extern const string fdomain_waterline_diffraction_binary_file;
    extern const string elevation_show_file;
    extern const string impulses_ascii_file;
    extern const string radiation_impulse_force_file_extension;
    extern const string scattering_impulse_force_file_extension;
    extern const string resistance_impulse_force_file_extension;
    extern const string hydro_coefficients_file_extention;
    extern const string fdomain_excitation_file_extention;
    extern const string fdomain_rao_file_extention;
    extern const string fdomain_scattering_file_extention;
    extern const string fdomain_froude_krylov_file_extention;
    extern const string drift_forces_file_extention;
    extern const string frequency_vectors_file;
    extern const string fdomain_disp_file_extention;
    extern const string least_square_status_file_extension;
    extern const string upwind_x_coefficients_file;
    extern const string upwind_z_coefficients_file;
    extern const unsigned int print_width;
    extern const unsigned int print_precision;
    extern const bool long_print;
    extern const bool create_showfile;
    extern const bool print_elevation;
    // ---------------------------------------------------------------------------
    // * Computations constants
    // ---------------------------------------------------------------------------
    extern const int rk_stage_count;
    extern const vector<double> rk_b;
    extern const vector<double> rk_c;
    extern const int time_order;
    extern const double rho;
    extern const double frequency_cutoff;
    extern const double sponge_length;
    extern const double gamma_Timoshenko;
    extern const unsigned int patch_interpolation_width;
    extern const char *path_to_triangulations;
    extern const bool GX_WU_BCS;
    extern const bool ow3d_surface_derivative;
    extern const GMODE_TYPES gmode_type;
    extern const GMODES_HYDROSTATICS gmode_hydrostatics;
    extern const bool print_ow3d_derivatives_verification;
    extern const bool print_ow3d_upwind_verification;
    extern const bool print_ow3d_filter_verification;
    extern const bool print_laplacian_erros;
    extern const double gamma_Timo;                                // gamma which is used in Timoshenko beam
    extern const RealArray C4, C2;                                 // Extrapolations at the boundaries
    extern const RealArray C4_left_neumann, C2_left_neumann;       // Symmetry condition at left
    extern const RealArray C4_right_neumann, C2_right_neumann;     // Symmetry condition at right
    extern const RealArray C4_left_dirichlet, C2_left_dirichlet;   // Anti-symmetry condition at left
    extern const RealArray C4_right_dirichlet, C2_right_dirichlet; // Anti-symmetry condition at right
    extern const bool transform_only_pots_for_drift;               // If yes, only velocity potentails (not derivatives) are Fourier transformed to frequency domain
    extern const bool use_grid_symmetry_for_derivatives;           // True only when the solutions are either symmetric or anti-symmetric
    extern const bool compute_speed_hydrostatics;
    // ---------------------------------------------------------------------------
    // * Constant maps
    // ---------------------------------------------------------------------------
    extern const map<MODE_NAMES, std::string> ModeStrings;
    extern const map<BASE_FLOW_TAGS, std::string> BaseflowStrings;
    extern const map<MODE_NAMES, string> ModePrintTags;
    extern const map<UPWIND_STENCIL_TYPES, string> UpwindStencilsPrintTags;
}

#endif