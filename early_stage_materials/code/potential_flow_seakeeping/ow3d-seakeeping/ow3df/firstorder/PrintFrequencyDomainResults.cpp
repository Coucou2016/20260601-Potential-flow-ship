// This public member function belongs to the FirstOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"
#include <iomanip>
#include "Grid.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::PrintFrequencyDomainResults()
{
    if (hydroCalc_)
    {
        unsigned int freqs_size = omegao_.size() - allKsAndOmegas_.out_start_index;
        ofstream fout;
        int wdt = OW3DSeakeeping::print_width;
        fout.setf(ios_base::scientific);
        fout.precision(OW3DSeakeeping::print_precision);
        string filename = results_folder_ + '/' + UserInput.project_name + hydro_coefficients_file_extention;
        fout.open(filename, ios::out);
        fout << "Hydrodynamic coefficients" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        fout << '\t' << print_freq_line << freqs_size << endl;
        fout << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
        // --------------------------------------------------------------------------------------------------------
        // IMPORTANT NOTE : The hydrodynamic coefficients are multiplied
        // by the "HYDSGN" variable in order to have the final results
        // printed in accordance with the coordinate system whoes z-axis
        // is upward.
        // --------------------------------------------------------------------------------------------------------
        for (unsigned int e = 0; e < radiation_runs_.size(); e++)
        {
            MODE_NAMES exci = radiation_runs_[e].mode;
            string j = ModePrintTags.at(UserInput.rad_runs[e].mode);
            unsigned int i_counter = 1;
            unsigned int j_counter = 1;
            if (j == ModePrintTags.at(GMODE))
            {
                j = to_string(total_number_of_rigid_modes + j_counter);
                j_counter++;
            }
            for (unsigned int r = 0; r < UserInput.responses.size(); r++)
            {
                string i = ModePrintTags.at(UserInput.responses[r]);
                if (i == ModePrintTags.at(GMODE))
                {
                    i = to_string(total_number_of_rigid_modes + i_counter);
                    i_counter++;
                }

                MODE_NAMES resp = UserInput.responses[r];
                int HYDSGN = 1;
                if (
                    ((exci == MODE_NAMES::SURGE || exci == MODE_NAMES::HEAVE || exci == MODE_NAMES::ROLL || exci == MODE_NAMES::YAW || exci == MODE_NAMES::GMODE) &&
                     (resp == MODE_NAMES::SWAY || resp == MODE_NAMES::PITCH)) ||
                    ((resp == MODE_NAMES::SURGE || resp == MODE_NAMES::HEAVE || resp == MODE_NAMES::ROLL || resp == MODE_NAMES::YAW || resp == MODE_NAMES::GMODE) &&
                     (exci == MODE_NAMES::SWAY || exci == MODE_NAMES::PITCH)))
                    HYDSGN = -1;

                for (unsigned int f = allKsAndOmegas_.out_start_index; f < omegaeAll_.size(); f++)
                {
                    fout << omegao_[f] << setw(wdt) << omegaeAll_[f] << '\t' << i << '\t' << j << '\t' << setw(wdt) << addedMass_[e](r, f) * HYDSGN;
                    fout << setw(wdt) << damping_[e](r, f) * HYDSGN << endl;
                }
            }

        } // End of radiations run loop

        for (unsigned int e = 0; e < gmodes_runs_.size(); e++)
        {
            string j = ModePrintTags.at(UserInput.gmd_runs[e].mode);
            j = (j == ModePrintTags.at(GMODE)) ? to_string(total_number_of_rigid_modes + e + 1) : j;

            unsigned int i_counter = 1;
            for (unsigned int r = 0; r < UserInput.responses.size(); r++)
            {
                string i = ModePrintTags.at(UserInput.responses[r]);
                if (i == ModePrintTags.at(GMODE))
                {
                    i = to_string(total_number_of_rigid_modes + i_counter);
                    i_counter++;
                }

                for (unsigned int f = allKsAndOmegas_.out_start_index; f < omegaeAll_.size(); f++)
                {
                    fout << omegao_[f] << setw(wdt) << omegaeAll_[f] << '\t' << i << '\t' << j << '\t' << setw(wdt) << addedMass_[radiation_runs_.size() + e](r, f);
                    fout << setw(wdt) << damping_[radiation_runs_.size() + e](r, f) << endl;
                }
            }

        } // End of gmodes run loop

        fout.close();

    } // End of hydroCalc_ check

    if (diffraction_runs_.size() != 0 && FroudeKrylov_.size() != 0 && scattering_force_.size() != 0 && excitation_force_.size() != 0)
    {
        unsigned int freqs_size = omegao_.size() - allKsAndOmegas_.out_start_index;
        int wdt = OW3DSeakeeping::print_width;
        // --------------------------------------------------------------------------------------------------------
        // IMPORTANT NOTE : The forces and rao's are multiplied by the
        // variable "FRCSGN" in order to have the final results printed
        // in accordance with the coordinate system whoes z-axis is
        // upward.
        // --------------------------------------------------------------------------------------------------------
        ofstream fout_sc;
        fout_sc.setf(ios_base::scientific);
        fout_sc.precision(OW3DSeakeeping::print_precision);
        string filename_sc = results_folder_ + '/' + UserInput.project_name + fdomain_scattering_file_extention;
        fout_sc.open(filename_sc, ios::out);
        fout_sc << "Wave scattering forces" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        fout_sc << '\t' << print_freq_line << freqs_size << endl;
        fout_sc << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
        fout_sc << '\t' << print_beta_line << UserInput.beta << endl;

        ofstream fout_ex;
        fout_ex.setf(ios_base::scientific);
        fout_ex.precision(OW3DSeakeeping::print_precision);
        string filename_ex = results_folder_ + '/' + UserInput.project_name + fdomain_excitation_file_extention;
        fout_ex.open(filename_ex, ios::out);
        fout_ex << "Wave excitation forces" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        fout_ex << '\t' << print_freq_line << freqs_size << endl;
        fout_ex << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
        fout_ex << '\t' << print_beta_line << UserInput.beta << endl;

        ofstream fout_fk;
        fout_fk.setf(ios_base::scientific);
        fout_fk.precision(OW3DSeakeeping::print_precision);
        string filename_fk = results_folder_ + '/' + UserInput.project_name + fdomain_froude_krylov_file_extention;
        fout_fk.open(filename_fk, ios::out);
        fout_fk << "Froude-Krylov forces" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        fout_fk << '\t' << print_freq_line << freqs_size << endl;
        fout_fk << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
        fout_fk << '\t' << print_beta_line << UserInput.beta << endl;

        ofstream fout_rao;
        if (RAO_.size() != 0)
        {
            fout_rao.setf(ios_base::scientific);
            fout_rao.precision(OW3DSeakeeping::print_precision);
            string filename_rao = results_folder_ + '/' + UserInput.project_name + fdomain_rao_file_extention;
            fout_rao.open(filename_rao, ios::out);
            fout_rao << "Response amplitude operators" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            fout_rao << '\t' << print_freq_line << freqs_size << endl;
            fout_rao << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
            fout_rao << '\t' << print_beta_line << UserInput.beta << endl;
        }

        unsigned int i_counter = 1;
        for (unsigned int s = 0; s < UserInput.responses.size(); s++)
        {
            string i = ModePrintTags.at(UserInput.responses[s]);
            i = (i == ModePrintTags.at(GMODE)) ? to_string(total_number_of_rigid_modes + i_counter++) : i;
            int FRCSGN = UserInput.responses[s] == MODE_NAMES::PITCH ? -1 : 1;

            for (unsigned int f = allKsAndOmegas_.out_start_index; f < omegaeAll_.size(); f++)
            {
                vector<double> disp_g;
                disp_g.resize(UserInput.responses.size());

                double real_fk = FroudeKrylov_[s](0, f);
                double imag_fk = FroudeKrylov_[s](1, f);
                double mag_fk = sqrt(real_fk * real_fk + imag_fk * imag_fk);
                fout_fk << omegao_[f] << setw(wdt) << omegaeAll_[f] << '\t' << i << '\t' << setw(wdt) << real_fk * FRCSGN << setw(wdt) << imag_fk * FRCSGN << setw(wdt) << mag_fk << endl;

                double real_sc = scattering_force_[s](0, f);
                double imag_sc = scattering_force_[s](1, f);
                double mag_sc = sqrt(real_sc * real_sc + imag_sc * imag_sc);
                fout_sc << omegao_[f] << setw(wdt) << omegaeAll_[f] << '\t' << i << '\t' << setw(wdt) << real_sc * FRCSGN << setw(wdt) << imag_sc * FRCSGN << setw(wdt) << mag_sc << endl;

                double real_ex = excitation_force_[s](0, f);
                double imag_ex = excitation_force_[s](1, f);
                double mag_ex = sqrt(real_ex * real_ex + imag_ex * imag_ex);
                fout_ex << omegao_[f] << setw(wdt) << omegaeAll_[f] << '\t' << i << '\t' << setw(wdt) << real_ex * FRCSGN << setw(wdt) << imag_ex * FRCSGN << setw(wdt) << mag_ex << endl;

                if (RAO_.size() != 0 and UserInput.solve_motion)
                {
                    double real_rao = RAO_[s](0, f);
                    double imag_rao = RAO_[s](1, f);
                    double mag_rao = sqrt(real_rao * real_rao + imag_rao * imag_rao);
                    fout_rao << omegao_[f] << setw(wdt) << omegaeAll_[f] << '\t' << i << '\t' << setw(wdt) << real_rao * FRCSGN << setw(wdt) << imag_rao * FRCSGN << setw(wdt) << mag_rao << endl;
                }
            }
        }

        fout_ex.close();
        fout_fk.close();
        fout_sc.close();
        fout_rao.close();

        if (UserInput.number_of_gmodes != 0)
        {
            ofstream fout_gm_disp;
            fout_gm_disp.setf(ios_base::scientific);
            fout_gm_disp.precision(OW3DSeakeeping::print_precision);
            string filename_disp = results_folder_ + '/' + UserInput.project_name + fdomain_disp_file_extention;
            fout_gm_disp.open(filename_disp, ios::out);
            fout_gm_disp << "Verticcal displacement for flexible modes" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
            fout_gm_disp << '\t' << print_freq_line << freqs_size << endl;
            fout_gm_disp << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
            fout_gm_disp << '\t' << print_beta_line << UserInput.beta << endl;

            for (unsigned int f = allKsAndOmegas_.out_start_index; f < omegaeAll_.size(); f++)
            {
                if (GMDISP_.size() != 0)
                {
                    fout_gm_disp << omegao_[f] << setw(wdt) << omegaeAll_[f] << setw(wdt) << GMDISP_[f - allKsAndOmegas_.out_start_index] << endl;
                }
            }
            fout_gm_disp.close();
        }

        ofstream fout_freqs;
        fout_freqs.setf(ios_base::scientific);
        fout_freqs.precision(OW3DSeakeeping::print_precision);
        string filename_freqs = results_folder_ + '/' + UserInput.project_name + frequency_vectors_file;
        fout_freqs.open(filename_freqs, ios::out);
        fout_freqs << "Frequencies and wave numbers" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        fout_freqs << '\t' << print_freq_line << freqs_size << endl;
        fout_freqs << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
        fout_freqs << '\t' << print_beta_line << UserInput.beta << endl;
        for (unsigned int f = allKsAndOmegas_.out_start_index; f < omegaeAll_.size(); f++)
        {
            if (omegaeAll_[f] > simulationData_.minimum_frequency)
                fout_freqs << omegao_[f] << setw(wdt) << ko_[f] << setw(wdt) << omegaeAll_[f] << endl;
        }
        fout_freqs.close();
    }
}