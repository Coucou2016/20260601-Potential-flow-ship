// This file exports the data objects and member functions for the Input class
// which used for the definition and extraction of the input data from the user
// provided input file. An object of the class  contains all required input data.
// The input data are grouped based  on their relevance, for example there is a
// type for all file names.
// All data (as-input by the user and as-read by the program) are written
// to "userInputFile". The provided values for excitation and response
// modes are checked (with respect to the grid dimension
// and possible excitation and response modes)by "extract_run_data" private member
// function in the Grid class and the final valid simulation data is stored
// in a Run variable defined in the Grid class.

#ifndef __INPUT_H__
#define __INPUT_H__

#include <string>
#include <vector>
#include "OW3DUtilFunctions.h"

namespace OW3DSeakeeping
{
  class Input
  {
  public:
    typedef struct
    {
      aString gridFileName;
      double courant;
      double run_time;
      double g;    // gravitational acceleration m/s^2
      double U;    // forward speed m/s
      double beta; // heading degree
      BASE_FLOW_TYPES base_flow_type;
      unsigned int zero_padding_multiple;
      bool wave_drift;
      SOLVER_TYPES solver_type;
      vector<double> rotation_centre;
      vector<double> gravitation_centre;
      vector<vector<double>> hydrostatic_matrix;
      vector<vector<double>> mass_matrix;
      vector<vector<double>> stiffness_matrix;
      vector<vector<double>> shear_stiffness_matrix;
      unsigned int postRate;
      unsigned int symx;
      double ulen;
      bool user_hydro;
      bool user_mass;
      bool user_stiff;
      bool user_shear_stiff;
      string project_name;
      vector<unsigned int> user_modes;
      unsigned int gdim;
      unsigned int irad;
      unsigned int ires;
      unsigned int idif;
      vector<OW3DSeakeeping::HydrodynamicProblem> rad_runs;
      vector<OW3DSeakeeping::HydrodynamicProblem> dif_runs;
      vector<OW3DSeakeeping::HydrodynamicProblem> res_runs;
      vector<OW3DSeakeeping::HydrodynamicProblem> gmd_runs;
      vector<OW3DSeakeeping::HydrodynamicProblem> all_runs;
      vector<MODE_NAMES> responses;
      unsigned int number_of_gmodes;
      unsigned int number_of_rigid_modes;
      bool solve_motion;

    } INPUT;

    Input();
    ~Input();
    INPUT getInputData() const;

  private:
    INPUT inputData_;
    string solver_type_string_;
    string base_type_string_;
    string hydrostatic_string_;
    void PrintUserData_() const;
    void ExtractRunPacks_();
  };

}

#endif
