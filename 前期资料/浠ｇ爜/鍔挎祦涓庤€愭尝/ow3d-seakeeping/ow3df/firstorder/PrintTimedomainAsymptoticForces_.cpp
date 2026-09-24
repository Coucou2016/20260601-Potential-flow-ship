#include "FirstOrder.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::FirstOrder::PrintTimedomainAsymptoticForces_() const
{
    ofstream fout;
    int wdt = OW3DSeakeeping::print_width;
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);
    double omegac = transformData_.omegac; // make shorter name
    unsigned int multiple = 10;
    double dt = simulationData_.print_time_step; // make shorter name
    int exponent = 1;

    if (UserInput.dif_runs.size() == 1)
    {
        for (unsigned int resp = 0; resp < UserInput.responses.size(); resp++)
        {
            string j = ModePrintTags.at(UserInput.responses[resp]);
            string filename = results_folder_ + '/' + UserInput.project_name + scattering_impulse_force_file_extension + j + 'a';
            fout.open(filename, ios::out);
            fout << "Time-domain scattering asymptotic forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            for (unsigned int i = 0; i < multiple * transformData_.fitting_length; i++)
            {
                double t = i * dt + transformData_.fitting_start_time;
                double force;
                force = 1.0 / pow(t, exponent) * (ls_fit_coeffs_scat_[0][resp][0] * sin(omegac * t) + ls_fit_coeffs_scat_[0][resp][1] * cos(omegac * t));
                fout << t << setw(wdt) << force << endl;
            }
            fout.close();
        }
    }
    else if (UserInput.dif_runs.size() > 1)
    {
        for (unsigned int resp = 0; resp < UserInput.responses.size(); resp++)
        {
            string j = ModePrintTags.at(UserInput.responses[resp]);
            string filename = results_folder_ + '/' + UserInput.project_name + scattering_impulse_force_file_extension + j + 'a';
            fout.open(filename, ios::out);
            fout << "Time-domain scattering asymptotic forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            for (unsigned int i = 0; i < multiple * transformData_.fitting_length; i++)
            {
                double t = i * dt + transformData_.fitting_start_time;
                fout << t;
                for (unsigned int mode_index = 0; mode_index < UserInput.dif_runs.size() - 1; mode_index += 2)
                {
                    double force;
                    force = 1.0 / pow(t, exponent) * (ls_fit_coeffs_scat_[mode_index][resp][0] * sin(omegac * t) + ls_fit_coeffs_scat_[mode_index][resp][1] * cos(omegac * t));
                    force += 1.0 / pow(t, exponent) * (ls_fit_coeffs_scat_[mode_index + 1][resp][0] * sin(omegac * t) + ls_fit_coeffs_scat_[mode_index + 1][resp][1] * cos(omegac * t));
                    fout << setw(wdt) << force;
                }
                fout << endl;
            }
            fout.close();
        }
    }

    if (UserInput.rad_runs.size() != 0)
    {
        for (unsigned int mode_index = 0; mode_index < UserInput.rad_runs.size(); mode_index++) // Print radiation forces
        {
            for (unsigned int resp = 0; resp < UserInput.responses.size(); resp++)
            {
                string ij = ModePrintTags.at(UserInput.responses[resp]) + ModePrintTags.at(UserInput.rad_runs[mode_index].mode);
                string filename = results_folder_ + '/' + UserInput.project_name + radiation_impulse_force_file_extension + ij + 'a';
                fout.open(filename, ios::out);
                fout << "Time-domain radiation asymptotic forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
                for (unsigned int i = 0; i < multiple * transformData_.fitting_length; i++)
                {
                    double t = i * dt + transformData_.fitting_start_time;
                    double force;
                    force = 1.0 / pow(t, exponent) * (ls_fit_coeffs_rad_[mode_index][resp][0] * sin(omegac * t) + ls_fit_coeffs_rad_[mode_index][resp][1] * cos(omegac * t));
                    fout << t << setw(wdt) << force << endl;
                }
                fout.close();
            }
        }
    }
    if (UserInput.res_runs.size() != 0)
    {
        for (unsigned int resp = 0; resp < UserInput.responses.size(); resp++)
        {
            string j = ModePrintTags.at(UserInput.responses[resp]);
            string filename = results_folder_ + '/' + UserInput.project_name + resistance_impulse_force_file_extension + j + 'a';
            fout.open(filename, ios::out);
            fout << "Time-domain resistance asymptotic forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            for (unsigned int i = 0; i < multiple * transformData_.fitting_length; i++)
            {
                double t = i * dt + transformData_.fitting_start_time;
                double force;
                force = 1.0 / pow(t, exponent) * (ls_fit_coeffs_res_[0][resp][0] * sin(omegac * t) + ls_fit_coeffs_res_[0][resp][1] * cos(omegac * t)) + ls_fit_coeffs_res_[0][resp][2];
                fout << t << setw(wdt) << force << endl;
            }
            fout.close();
        }
    }
}