// This public member function belongs to the FisrtOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::TransformVelocityPotentials()
{
    if (OW3DSeakeeping::UserInput.wave_drift and (freq_pseudo_elev_.getLength(0) != 0 or freq_pseudo_disp_.getLength(0) != 0))
    {
        const unsigned int fftsize = transformData_.size_of_fft; // The size of fft
        const unsigned int flength = omegae_.size();             // The desired frequency length
        double dt = simulationData_.print_time_step;
        unsigned int number_of_frequencies = omegae_.size();
        RealArray time_domain_potential(1, simulationData_.print_step_count);
        ComplexNumbers freq_domain_potential(fftsize);
        ComplexNumbers unit_potential_phasor(number_of_frequencies);
        time_domain_potential = 0.;
        vector<double> za(2);
        Range frequency_range(0, omegae_.size() - 1);

        double dat; // The data from the binary files are read in to this variable

        struct comp
        {
            double sym_real;
            double sym_imag;
            double asm_real;
            double asm_imag;

        } cp_rd, cp_sc;

        string freq_rd_file = results_folder_ + '/' + fdomain_potentials_radiation_binary_file; // The file for the phasors including the contributions only
        ofstream freq_rd_out(freq_rd_file, ios_base::out | ios_base::app | ios_base::binary);   // from the radiation problems.

        string freq_sc_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_scattering_binary_file; // The file for the phasors including the contributions only
        ofstream freq_sc_out(freq_sc_file, ios_base::out | ios_base::app | ios_base::binary);                    // from the scattering problem.

        // Open the time-domain data

        string time_file = time_domain_folder_ + '/' + OW3DSeakeeping::tdomain_body_potentials_binary_file;
        ifstream time_in(time_file, ios_base::in | ios_base::binary);

        if (!time_in.is_open())
            throw runtime_error("Error, OW3DSeakeeping::FirstOrder::transformBodyPotentials.cpp: File for the time-domain potentials can not be opened.");

        for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
        {
            const Single_boundary_data &be = boundariesData_->exciting[surface];
            const vector<Index> &Is = be.surface_indices;
            MappedGrid &mg = (*cg_)[be.grid];
            const RealArray &v = mg.vertex();
            RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
            x = v(Is[0], Is[1], Is[2], axis1);
            y = v(Is[0], Is[1], Is[2], axis2);
            z = (gridData_->nod == 2) ? 0. * x : v(Is[0], Is[1], Is[2], axis3);

            const int l1 = Is[1].getLength();
            const int l2 = Is[2].getLength();

            int surface_shift = 0; // The shift due to the previous surfaces

            for (int back = surface; back > 0; back--)
            {
                const Single_boundary_data &sbd = boundariesData_->exciting[back - 1];
                const vector<Index> &I = sbd.surface_indices;

                const int bcl0 = I[0].getLength();
                const int bcl1 = I[1].getLength();
                const int bcl2 = I[2].getLength();

                surface_shift += bcl0 * bcl1 * bcl2 * npots_;
            }

            for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
            {
                for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
                {
                    for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
                    {
                        for (unsigned int pot = 0; pot < 1; pot++) // transform only the velocity potentials (not the derivatives)
                        {
                            // ---------------------------------------------------------------------
                            //  Calculate radiation phasors
                            // ---------------------------------------------------------------------

                            for (unsigned int run = 0; run < radiation_runs_.size(); run++)
                            {
                                MODE_NAMES mode_name = radiation_runs_[run].mode;

                                int runs_shift = (run + diffraction_runs_.size()) * p_one_run_shift_;

                                for (unsigned int t = 0; t < steps_; t++)
                                {
                                    unsigned int steps_shift = t * p_one_step_shift_;

                                    // Linear indexing in to the binary files [run][time][surface][i][j][k][pot] ( h denotes the index for the type of the data )

                                    int shift = runs_shift + steps_shift + surface_shift + i * l1 * l2 * npots_ + j * l2 * npots_ + k * npots_ + pot;

                                    time_in.seekg(shift * (sizeof dat), ios_base::beg);
                                    time_in.read((char *)&dat, sizeof dat);
                                    time_domain_potential(0, t) = dat;

                                } // End of time loop for this point

                                Fft_(time_domain_potential, 0, freq_domain_potential, transformData_, dt, za, "");
                                unit_potential_phasor = freq_domain_potential(frequency_range) / freq_pseudo_disp_(frequency_range);

                                for (unsigned int f = 0; f < flength; f++)
                                {
                                    if (mode_name == MODE_NAMES::HEAVE or
                                        mode_name == MODE_NAMES::SURGE or
                                        mode_name == MODE_NAMES::PITCH)
                                    {
                                        cp_rd.sym_real = unit_potential_phasor(0, f);
                                        cp_rd.sym_imag = unit_potential_phasor(1, f);
                                        cp_rd.asm_real = 0.;
                                        cp_rd.asm_imag = 0.;
                                    }
                                    else
                                    {
                                        cp_rd.asm_real = unit_potential_phasor(0, f);
                                        cp_rd.asm_imag = unit_potential_phasor(1, f);
                                        cp_rd.sym_real = 0.;
                                        cp_rd.sym_imag = 0.;
                                    }

                                    freq_rd_out.write((char *)&cp_rd, sizeof cp_rd); // Save as binary in hard drive
                                }

                            } // End of radiation runs loop

                            // ---------------------------------------------------------------------
                            //  Calculate scattering unit phasors
                            // ---------------------------------------------------------------------

                            for (unsigned int run = 0; run < diffraction_runs_.size(); run++)
                            {
                                DIFF_TYPES diftype = diffraction_runs_[run].diff_type;

                                int runs_shift = run * p_one_run_shift_;

                                for (unsigned int t = 0; t < steps_; t++)
                                {
                                    int steps_shift = t * p_one_step_shift_;

                                    // Linear indexing in to the binary files [run][time][surface][i][j][k][h] ( h denotes the index for the type of the data )

                                    int shift = runs_shift + steps_shift + surface_shift + i * l1 * l2 * npots_ + j * l2 * npots_ + k * npots_ + pot;

                                    time_in.seekg(shift * (sizeof dat), ios_base::beg);
                                    time_in.read((char *)&dat, sizeof dat);

                                    time_domain_potential(0, t) = dat;

                                } // End of time loop for this point (ready for transform)

                                Fft_(time_domain_potential, 0, freq_domain_potential, transformData_, dt, za, "");
                                unit_potential_phasor = freq_domain_potential(frequency_range) / freq_pseudo_elev_(frequency_range);

                                for (unsigned int f = 0; f < flength; f++)
                                {
                                    // ----------------------------------------------------------------------------
                                    // Calculate the symmetric and anti-symmetric components of the phasors
                                    // ----------------------------------------------------------------------------

                                    // NOTE : THIS IS A SYMMETRIC DIFFRACTION RUN (JUST FOR SYMMETRIC GRIDS).

                                    if (diftype == DIFF_TYPES::SYM or diftype == DIFF_TYPES::HEAD)
                                    {
                                        cp_sc.sym_real = unit_potential_phasor(0, f);
                                        cp_sc.sym_imag = unit_potential_phasor(1, f);
                                        cp_sc.asm_real = 0.;
                                        cp_sc.asm_imag = 0.;
                                    }

                                    // NOTE : THIS IS AN ANTI-SYMMETRIC DIFFRACTION RUN (JUST FOR SYMMETRIC GRIDS).

                                    else if (diftype == DIFF_TYPES::ASM) // An anti-Symmetric diffraction run (Just for symmetric grids).
                                    {
                                        cp_sc.asm_real = unit_potential_phasor(0, f);
                                        cp_sc.asm_imag = unit_potential_phasor(1, f);
                                        cp_sc.sym_real = 0.;
                                        cp_sc.sym_imag = 0.;
                                    }

                                    // NOTE : THIS IS A GENERAL DIFFRACTION RUN (FOR NON-SYMMETRIC GRIDS).

                                    else // Non-symmetric grid
                                    {
                                        cp_sc.sym_real = unit_potential_phasor(0, f);
                                        cp_sc.sym_imag = unit_potential_phasor(1, f);
                                        cp_sc.asm_real = 0.;
                                        cp_sc.asm_imag = 0.;

                                        // NOTE : For a general grid, we regard the scattering potential
                                        //        to be a symmetric contribution, and we store it in the
                                        //        symmetric containter. Put in other words, as in this case
                                        //        there is just 1 diffraction run, we choose to put the
                                        //        solution in the symmetry container just for convenience.
                                    }

                                    freq_sc_out.write((char *)&cp_sc, sizeof cp_sc); // Print to hard drive as binary ( ONLY THE SCATTERING  PHASORS )

                                } // End of frequency loop

                            } // End of diffraction runs loop

                        } // End of loop over the type of the data

                    } // k

                } // j

            } // i

            // Note: At this point in the function, the complex phasors for all types
            // of data have been calculated and printed out for all grid points located
            // at the "surface" on the body. The same will be carried out in the next
            // iteration of the surface loop.

        } // End of loop over body surface

        freq_rd_out.close();
        freq_sc_out.close();
        time_in.close();

    } // End of wave drift check

} // End of the function