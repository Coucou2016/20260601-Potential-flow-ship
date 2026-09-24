
#include "Input.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Input::PrintUserData_() const
{
    ofstream fout(user_input_check_file);
    int sw = OW3DSeakeeping::print_width;
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);
    fout << "User valid input data" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << endl;
    fout << "name: " << inputData_.project_name << '\n'
         << "sped: " << inputData_.U << '\n'
         << "base: " << base_type_string_ << '\n'
         << "idif: " << inputData_.idif << '\n'
         << "irad: " << inputData_.irad << '\n'
         << "ires: " << inputData_.ires << '\n'
         << "mode: ";
    for (int unsigned i = 0; i < inputData_.user_modes.size(); i++)
        fout << inputData_.user_modes[i] << " ";
    fout << '\n';
    fout << "drif: " << inputData_.wave_drift << '\n'
         << "cour: " << inputData_.courant << '\n'
         << "time: " << inputData_.run_time << '\n'
         << "beta: " << inputData_.beta << '\n'
         << "grid: " << inputData_.gridFileName << '\n'
         << "symx: " << inputData_.symx << '\n'
         << "rotc: ";
    for (int unsigned i = 0; i < inputData_.rotation_centre.size(); i++)
        fout << inputData_.rotation_centre[i] << " ";
    for (int unsigned i = 0; i < inputData_.gravitation_centre.size(); i++)
        fout << inputData_.gravitation_centre[i] << " ";
    fout << '\n';
    fout << "grav: " << inputData_.g << '\n'
         << "ulen: " << inputData_.ulen << '\n'
         << "solv: " << solver_type_string_ << '\n'
         << "fftz: " << inputData_.zero_padding_multiple << '\n'
         << "orat: " << inputData_.postRate << endl;

    if (inputData_.user_mass)
    {
        fout << "user mass matrix: " << '\n';
        for (unsigned int i = 0; i < inputData_.mass_matrix.size(); i++)
        {
            for (unsigned int j = 0; j < inputData_.mass_matrix.size(); j++)
                fout << setw(sw) << inputData_.mass_matrix[i][j] << setw(sw);
            fout << endl;
        }
    }
    if (inputData_.user_hydro)
    {
        fout << "user hydrostatic matrix: " << '\n';

        for (unsigned int i = 0; i < inputData_.hydrostatic_matrix.size(); i++)
        {
            for (unsigned int j = 0; j < inputData_.hydrostatic_matrix.size(); j++)
                fout << setw(sw) << inputData_.hydrostatic_matrix[i][j];
            fout << endl;
        }
    }
    if (inputData_.user_stiff)
    {
        fout << "user stiffness matrix: " << '\n';

        for (unsigned int i = 0; i < inputData_.stiffness_matrix.size(); i++)
        {
            for (unsigned int j = 0; j < inputData_.stiffness_matrix.size(); j++)
                fout << setw(sw) << inputData_.stiffness_matrix[i][j];
            fout << endl;
        }
    }
    fout << "Total number of computations:" << inputData_.all_runs.size() << endl;
    fout << setw(sw) << "Diffraction:" << inputData_.dif_runs.size() << endl;
    fout << setw(sw) << "Radiation:" << inputData_.rad_runs.size() << endl;
    fout << setw(sw) << "Gmode:" << inputData_.gmd_runs.size() << endl;
    fout << setw(sw) << "Resistance:" << inputData_.res_runs.size() << endl;

    fout.close();
}