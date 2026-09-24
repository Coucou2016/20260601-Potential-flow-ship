#include "FirstOrder.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::FirstOrder::PrintTimedomainResults() const
{
    ofstream fout;
    int wdt = OW3DSeakeeping::print_width;
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);

    if (UserInput.dif_runs.size() == 1) // Print scattering forces
    {
        unsigned int j_counter = 1;
        for (unsigned int r = 0; r < UserInput.responses.size(); r++)
        {
            string j = ModePrintTags.at(UserInput.responses[r]);
            j = (j == ModePrintTags.at(GMODE)) ? to_string(total_number_of_rigid_modes + j_counter++) : j;
            string filename = results_folder_ + '/' + UserInput.project_name + scattering_impulse_force_file_extension + j;
            fout.open(filename, ios::out);
            fout << "Time-domain scattering forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            fout << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
            for (int t = 0; t < time_.getLength(1); t++)
                fout << setw(wdt) << time_(0, t) << setw(wdt) << diffractionBodyForces_[0](r, t) << endl;
            fout.close();
        }
    }
    else if (UserInput.dif_runs.size() > 1) // Print scattering forces
    {
        unsigned int j_counter = 1;
        for (unsigned int r = 0; r < UserInput.responses.size(); r++)
        {
            string j = ModePrintTags.at(UserInput.responses[r]);
            j = (j == ModePrintTags.at(GMODE)) ? to_string(total_number_of_rigid_modes + j_counter++) : j;
            string filename = results_folder_ + '/' + UserInput.project_name + scattering_impulse_force_file_extension + j;
            fout.open(filename, ios::out);
            fout << "Time-domain scattering forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            fout << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
            for (int t = 0; t < time_.getLength(1); t++)
            {
                fout << time_(0, t) << setw(wdt);
                for (unsigned int m = 0; m < UserInput.dif_runs.size(); m++)
                    fout << setw(wdt) << diffractionBodyForces_[m](r, t);
                fout << endl;
            }
            fout.close();
        }
    }

    for (unsigned int m = 0; m < UserInput.rad_runs.size(); m++) // Print radiation forces
    {
        unsigned int i_counter = 1;
        string j = ModePrintTags.at(UserInput.rad_runs[m].mode);
        for (unsigned int r = 0; r < UserInput.responses.size(); r++)
        {
            string i = ModePrintTags.at(UserInput.responses[r]);
            if (i == ModePrintTags.at(GMODE))
            {
                i = to_string(total_number_of_rigid_modes + i_counter);
                i_counter++;
            }
            AddDotsForTwoDigitsModes(i, j);
            string filename = results_folder_ + '/' + UserInput.project_name + radiation_impulse_force_file_extension + i + j;
            fout.open(filename, ios::out);
            fout << "Time-domain radiation forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            fout << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
            for (int t = 0; t < time_.getLength(1); t++)
                fout << setw(wdt) << time_(0, t) << setw(wdt) << radiationBodyForces_[m](r, t) << endl;
            fout.close();
        }
    }

    for (unsigned int m = 0; m < UserInput.gmd_runs.size(); m++) // Print generalized-modes forces
    {
        unsigned int i_counter = 1;
        string j = ModePrintTags.at(UserInput.gmd_runs[m].mode);
        j = (j == ModePrintTags.at(GMODE)) ? to_string(total_number_of_rigid_modes + m + 1) : j;
        for (unsigned int r = 0; r < UserInput.responses.size(); r++)
        {
            string i = ModePrintTags.at(UserInput.responses[r]);
            if (i == ModePrintTags.at(GMODE))
            {
                i = to_string(total_number_of_rigid_modes + i_counter);
                i_counter++;
            }
            AddDotsForTwoDigitsModes(i, j);
            string filename = results_folder_ + '/' + UserInput.project_name + radiation_impulse_force_file_extension + i + j;
            fout.open(filename, ios::out);
            fout << "Time-domain radiation forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            fout << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
            for (int t = 0; t < time_.getLength(1); t++)
                fout << setw(wdt) << time_(0, t) << setw(wdt) << gmodesBodyForces_[m](r, t) << endl;
            fout.close();
        }
    }

    for (unsigned int m = 0; m < UserInput.res_runs.size(); m++) // Print wave-resistance forces
    {
        for (unsigned int r = 0; r < UserInput.responses.size(); r++)
        {
            string j = ModePrintTags.at(UserInput.responses[r]);
            string filename = results_folder_ + '/' + UserInput.project_name + resistance_impulse_force_file_extension + j;
            fout.open(filename, ios::out);
            fout << "Time-domain resistance forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            fout << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
            for (int t = 0; t < time_.getLength(1); t++)
                fout << setw(wdt) << time_(0, t) << setw(wdt) << resistanceBodyForces_[m](r, t) << endl;
            fout.close();
        }
    }

    PrintPseudoImpulses_();

    if (OW3DSeakeeping::long_print && UserInput.U != 0)
        PrintTimedomainAsymptoticForces_();
}