// This public member function belongs to the FisrtOrderResults class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::TransformWaterlineElevations()
{
	// An outline of the function
	//
	// Data preparation
	//
	// for(waterline)
	//  |
	//  |  for(i)
	//  |    |
	//  |    |   for(radiation)
	//  |    |     |
	//  |    |     |  calculate
	//  |    |     |  radiation
	//  |    |     |  phasors
	//  |    |     |
	//  |    |    end for(radiation)
	//  |    |
	//  |    |    for(diffraction)
	//  |    |     |
	//  |    |     | calculate
	//  |    |     | diffraction phasors
	//  |    |     | (scattering + incident wave)
	//  |    |     |
	//  |    |    end for(diffraction)
	//  |    |
	//  |    |    for(frequency)
	//  |    |     |
	//  |    |     | add all phasors
	//  |    |     | and print them out
	//  |    |     | to the binary file
	//  |    |     |
	//  |    |    end for(frequency)
	//  |    |
	//  |   end for(i)
	//  |
	// end for(waterline)

	if (OW3DSeakeeping::UserInput.wave_drift)
	{
		const int unsigned fftsize = transformData_.size_of_fft;
		const int unsigned flength = omegae_.size(); // The desired frequency length
		const double sinBeta = sin(betar_);
		const double cosBeta = cos(betar_);

		double dat; // The data from the binary files are read in to this variable

		struct comp
		{
			double sym_real;
			double sym_imag;
			double asm_real;
			double asm_imag;

		} cp, cp_ni, cp_rd, cp_sc, cp_df; // ( cp: all, cp_ni: no incidets wave , cp_rd : only radiations, cp_sc: Only scattering, cp_df : Only diffraction )

		// Note : the time domain signals will be padded with 0

		// ----------------------------------------
		//
		// Declare and initialize data structures
		//
		// ----------------------------------------

		double *radi_tifq = new double[fftsize]; // For both the time- and the frequency-domain data
		double *scat_tifq = new double[fftsize];

		double *sym_radi_freq_re = new double[flength]; // Just for the frequency-domain data ( is assigned after radi_tifq has been transfomred )
		double *sym_radi_freq_im = new double[flength];
		double *asm_radi_freq_re = new double[flength];
		double *asm_radi_freq_im = new double[flength];

		double *sym_difc_freq_re = new double[flength]; // Just for the frequency-domain data ( is assigned after scat_tifq has been transfomred )
		double *sym_difc_freq_im = new double[flength]; // NOTE : These containers are used for the case
		double *asm_difc_freq_re = new double[flength]; // the contributions from the incident wave are
		double *asm_difc_freq_im = new double[flength]; // going to be stored in the final phasor "cp".

		double *sym_scat_freq_re = new double[flength]; // Just for the frequency-domain data ( is assigned after scat_tifq has been transfomred )
		double *sym_scat_freq_im = new double[flength]; // NOTE : These containers are used for the case
		double *asm_scat_freq_re = new double[flength]; // the contributions from the incident wave are
		double *asm_scat_freq_im = new double[flength]; // NOT going to be stored in the final phasor "cp_ni".

		// Initialise

		for (unsigned int i = 0; i < fftsize; i++)
		{
			radi_tifq[i] = 0.;
			scat_tifq[i] = 0.;
		}

		for (unsigned int f = 0; f < flength; f++) // NOTE : The containers must be initialized to zero.
		{
			sym_radi_freq_re[f] = 0.;
			sym_radi_freq_im[f] = 0.;
			asm_radi_freq_re[f] = 0.;
			asm_radi_freq_im[f] = 0.;

			sym_difc_freq_re[f] = 0.;
			sym_difc_freq_im[f] = 0.;
			asm_difc_freq_re[f] = 0.;
			asm_difc_freq_im[f] = 0.;

			sym_scat_freq_re[f] = 0.;
			sym_scat_freq_im[f] = 0.;
			asm_scat_freq_re[f] = 0.;
			asm_scat_freq_im[f] = 0.;
		}

		// Note : In gsl real mixed-radix transform the frequency domain data (return values)
		// are stored in the input time domain array. The real and imaginary parts
		// are adjacent to each other. Note also that we always keep the transform radix to be
		// a power of 2.

		gsl_fft_real_wavetable *table;
		table = gsl_fft_real_wavetable_alloc(fftsize);
		gsl_fft_real_workspace *space;
		space = gsl_fft_real_workspace_alloc(fftsize);

		// ---------------------------------------------------
		//
		// File for storing the potentials in frequency domain
		//
		// ---------------------------------------------------

		string freq_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_waterline_binary_file; // The file for the phasors including the contributions
		ofstream freq_out(freq_file, ios_base::out | ios_base::app | ios_base::binary);			  // from the incident wave. (Both radiation and diffraction)

		string freq_ni_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_waterline_no_incident_binary_file; // The file for the phasors excluding the contributions
		ofstream freq_ni_out(freq_ni_file, ios_base::out | ios_base::app | ios_base::binary);					 // from the incident wave. (Both radiation and scattering)

		string freq_rd_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_waterline_radiation_binary_file; // The file for the phasors including the contributions only
		ofstream freq_rd_out(freq_rd_file, ios_base::out | ios_base::app | ios_base::binary);				   // only from the radiation.

		string freq_sc_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_waterline_scattering_binary_file; // The file for the phasors including the contributions
		ofstream freq_sc_out(freq_sc_file, ios_base::out | ios_base::app | ios_base::binary);					// only from the scattering problem.

		string freq_df_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_waterline_diffraction_binary_file; // The file for the phasors including the contributions only
		ofstream freq_df_out(freq_df_file, ios_base::out | ios_base::app | ios_base::binary);					 // only from the diffraction problem.

		// Open the binary file for the water lines

		string time_file = time_domain_folder_ + '/' + OW3DSeakeeping::tdomain_waterline_elevation_binary_file;
		ifstream time_in(time_file, ios_base::in | ios_base::binary);

		if (!time_in.is_open())
		{
			throw runtime_error("Error, OW3DSeakeeping::FirstOrder::TransformWaterlineElevations.cpp: Time-domain waterline files can not be opened.");
		}

		// ----------------------------------------------------------------
		//
		// 1th loop : Over the number of water lines.
		// 2nd loop : Over the number of points located on each water line
		//
		// ----------------------------------------------------------------

		for (unsigned int line = 0; line < wlData_.size(); line++)
		{
			int noi = wlData_[line].size; // A shorter name

			// --------------------------------------
			//
			// The shift due to previous water lines
			//
			// --------------------------------------

			int lines_shift = 0;

			for (int back = line; back > 0; back--)
			{
				lines_shift += wlData_[back - 1].size;
			}

			for (int i = 0; i < noi; i++) // Do the fft for this point on the water line
			{
				for (unsigned int run = 0; run < radiation_runs_.size(); run++) // Calculate the radiation phasors
				{
					MODE_NAMES mode_name = radiation_runs_[run].mode;

					int runs_shift = (run + diffraction_runs_.size()) * w_one_run_shift_;

					for (unsigned int t = 0; t < steps_; t++)
					{
						int times_shift = t * w_one_step_shift_;

						int shift = runs_shift + times_shift + lines_shift + i; // Linear indexing in to the binary files [run][time][line][i]

						time_in.seekg(shift * (sizeof dat), ios_base::beg);
						time_in.read((char *)&dat, sizeof dat);

						radi_tifq[t] = dat;

					} // End of time loop

					// Zero pad the time-domain signal

					for (unsigned int zpad = steps_; zpad < fftsize; zpad++)
					{
						radi_tifq[zpad] = 0.;
					}

					// Note : In the following lines we do :
					//
					// 1. Transform the radiation elevation
					// 2. Divide by the transform of the displacement to get the complex phasor for unint motion
					// 3. Multiply the result by the RAOs to get the complex phasor for the motion caused by the unit wave amplitude.
					// 4. Transfer the frequency-domain radiation data from "radi_tifq" in to the "radi_freq_re" and "radi_freq_im"
					// 5. Add the complex phasors for all radiation runs

					gsl_fft_real_transform(radi_tifq, 1, fftsize, table, space);

					unsigned int increment = 1;
					unsigned int index = 0; // This index will increase up to : (flength)

					// Note: f in following loop would never reach close to fftsize, see "buildFrequenciesAndWaveNumbers", line 33

					for (unsigned int f = 0; f < fftsize; f += increment)
					{
						double radi_re = 0.;
						double radi_im = 0.;

						if (f == 0) // The imaginary part is zero
						{
							// Divide by the complex displacement to get the unit phasor. (a+ib)/(c+id) = [ (ac+bd) + i(bc-ad) ] / (c^2+d^2)

							radi_tifq[0] = radi_tifq[0] / freq_pseudo_disp_(0, index);

							// Multiply by RAO (a+ib)*(c+id) = (ac-bd) + i(ad+bc) where a+ib is the RAO

							radi_re = radi_tifq[0] * RAO_[run](0, 0);
						}
						else
						{
							index = (f + 1) / 2; // The cottect index

							// Divide by the complex displacement to get the unit phasor. (a+ib)/(c+id) = [ (ac+bd) + i(bc-ad) ] / (c^2+d^2)

							double denomd = pow(freq_pseudo_disp_(0, index), 2) + pow(freq_pseudo_disp_(1, index), 2);

							double unit_radi_re = (radi_tifq[f] * freq_pseudo_disp_(0, index) + radi_tifq[f + 1] * freq_pseudo_disp_(1, index)) / denomd;
							double unit_radi_im = (radi_tifq[f + 1] * freq_pseudo_disp_(0, index) - radi_tifq[f] * freq_pseudo_disp_(1, index)) / denomd;

							// Multiply by RAO (a+ib)*(c+id) = (ac-bd) + i(ad+bc) where a+ib is the RAO

							radi_re = RAO_[run](0, index) * unit_radi_re - RAO_[run](1, index) * unit_radi_im;
							radi_im = RAO_[run](0, index) * unit_radi_im + RAO_[run](1, index) * unit_radi_re;
						}

						// Transfer and add to "radi_freq_re" and "radi_freq_im" both symmetric and anti-symmetric
						//
						// Note : All radiation complex phasors are added here

						if (
							mode_name == MODE_NAMES::HEAVE or
							mode_name == MODE_NAMES::SURGE or
							mode_name == MODE_NAMES::PITCH)
						{
							sym_radi_freq_re[index] += radi_re;
							sym_radi_freq_im[index] += radi_im;
						}
						else
						{
							asm_radi_freq_re[index] += radi_re;
							asm_radi_freq_im[index] += radi_im;
						}

						if (f == 1)
						{
							increment = 2; // Real and imaginary parts in gsl fft are next to each other.
						}

						if (index == flength - 1)
						{
							break; // To make sure that just the correct number of frequencies are assigned
						}

					} // End of frequency loop

				} // End of radiation runs loop

				// --------------------------------------------------------------
				//
				//  Calculate diffraction ( scattering + incident wave ) phasors
				//
				// --------------------------------------------------------------

				for (unsigned int run = 0; run < diffraction_runs_.size(); run++)
				{
					// Note : The transform for diffraction runs will be divided to symmetric and anti-symmetric componnets (if any)

					DIFF_TYPES diftype = diffraction_runs_[run].diff_type;

					int runs_shift = run * w_one_run_shift_;

					for (unsigned int t = 0; t < steps_; t++)
					{
						int times_shift = t * w_one_step_shift_;

						int shift = runs_shift + times_shift + lines_shift + i; // Linear indexing in to the binary files

						time_in.seekg(shift * (sizeof dat), ios_base::beg);
						time_in.read((char *)&dat, sizeof dat);

						scat_tifq[t] = dat;

					} // End of time loop for this point

					// Zero pad the time-domain signal

					for (unsigned int zpad = steps_; zpad < fftsize; zpad++)
					{
						scat_tifq[zpad] = 0.;
					}

					// Note : in the following lines we do :
					//
					// 1. Transform the scattering potentials
					// 2. Divide the transform by the transform of the pseudo-impulse elevation
					// 3. Add the incident wave complex phasors to the scattering phasor.

					gsl_fft_real_transform(scat_tifq, 1, fftsize, table, space);

					unsigned int increment = 1;
					unsigned int index = 0; // This index will increase to : (flength)

					// Note: f in following loop would never reach close to fftsize, see "buildFrequenciesAndWaveNumbers", line 33

					for (unsigned int f = 0; f < fftsize; f += increment)
					{
						// ------------------------
						// Scattering contributions
						// ------------------------

						double scat_re = 0.;
						double scat_im = 0.;

						if (f == 0) // The imaginary part is zero
						{
							// Divide by the complex elevation to get the unit phasor. (a+ib)/(c+id) = [ (ac+bd) + i(bc-ad) ] / (c^2+d^2)

							scat_re = scat_tifq[0] / freq_pseudo_elev_(0, index);
						}
						else
						{
							index = (f + 1) / 2; // The correct index.

							// Divide by the complex elevation to get the unit phasor. (a+ib)/(c+id) = [ (ac+bd) + i(bc-ad) ] / (c^2+d^2)

							double denome = pow(freq_pseudo_elev_(0, index), 2) + pow(freq_pseudo_elev_(1, index), 2);

							scat_re = (scat_tifq[f] * freq_pseudo_elev_(0, index) + scat_tifq[f + 1] * freq_pseudo_elev_(1, index)) / denome;
							scat_im = (scat_tifq[f + 1] * freq_pseudo_elev_(0, index) - scat_tifq[f] * freq_pseudo_elev_(1, index)) / denome;
						}

						// ---------------------------
						// Incident wave contributions
						// ---------------------------

						double wnb = ko_[index]; // Wave number

						double x = wlData_[line].x[i];
						double z = wlData_[line].z[i];

						double sym_incid_re = cos(wnb * z * sinBeta) * cos(wnb * x * cosBeta); // symmetric
						double sym_incid_im = -cos(wnb * z * sinBeta) * sin(wnb * x * cosBeta);

						double asm_incid_re = -sin(wnb * z * sinBeta) * sin(wnb * x * cosBeta); // anti-symmetric
						double asm_incid_im = -sin(wnb * z * sinBeta) * cos(wnb * x * cosBeta);

						// ----------------------------------------------------------------------------
						// Calculate the symmetric and anti-symmetric components of diffraction phasors
						// ----------------------------------------------------------------------------

						// NOTE : THIS IS A SYMMETRIC DIFFRACTION RUN (JUST FOR SYMMETRIC GRIDS).

						if (diftype == DIFF_TYPES::SYM or diftype == DIFF_TYPES::HEAD)
						{
							sym_difc_freq_re[index] = sym_incid_re + scat_re;
							sym_difc_freq_im[index] = sym_incid_im + scat_im;

							sym_scat_freq_re[index] = scat_re;
							sym_scat_freq_im[index] = scat_im;
						}

						// NOTE : THIS IS AN ANTI-SYMMETRIC DIFFRACTION RUN (JUST FOR SYMMETRIC GRIDS).

						else if (diftype == DIFF_TYPES::ASM)
						{
							asm_difc_freq_re[index] = asm_incid_re + scat_re;
							asm_difc_freq_im[index] = asm_incid_im + scat_im;

							asm_scat_freq_re[index] = scat_re;
							asm_scat_freq_im[index] = scat_im;
						}

						// NOTE : THIS IS A GENERAL DIFFRACTION RUN (FOR NON-SYMMETRIC GRIDS).

						else
						{
							sym_difc_freq_re[index] = sym_incid_re + scat_re;
							sym_difc_freq_im[index] = sym_incid_im + scat_im;

							sym_scat_freq_re[index] = scat_re;
							sym_scat_freq_im[index] = scat_im;

							asm_difc_freq_re[index] = asm_incid_re;
							asm_difc_freq_im[index] = asm_incid_im;

							asm_scat_freq_re[index] = 0.;
							asm_scat_freq_im[index] = 0.;

							// NOTE : For a general grid, we regard the scattering potential
							//        to be a symmetric contribution, and we store it in the
							//        symmetric containter. Put in other words, as in this case
							//        there is just 1 diffraction run, we choose to put the
							//        solution in the symmetry container just for convenience.
						}

						if (f == 1)
						{
							increment = 2; // Real and imaginary parts in gsl fft are next to each other.
						}

						if (index == flength - 1)
						{
							break; // To make sure that just the correct number of frequencies are assigned
						}

					} // End of frequency loop

				} // End of diffraction runs

				// ----------------------------------------------------------------------
				//
				// Add the diffraction and the radiation phasors. Then print the results
				//
				// ----------------------------------------------------------------------

				for (unsigned int f = 0; f < flength; f++)
				{
					double sym_phasor_re = sym_difc_freq_re[f] + sym_radi_freq_re[f];
					double sym_phasor_im = sym_difc_freq_im[f] + sym_radi_freq_im[f];

					double sym_phasor_re_ni = sym_scat_freq_re[f] + sym_radi_freq_re[f]; // NOTE : NO INCIDENT WAVE IN THE FINAL PHASOR
					double sym_phasor_im_ni = sym_scat_freq_im[f] + sym_radi_freq_im[f]; // NOTE : NO INCIDENT WAVE IN THE FINAL PHASOR

					double asm_phasor_re = asm_difc_freq_re[f] + asm_radi_freq_re[f];
					double asm_phasor_im = asm_difc_freq_im[f] + asm_radi_freq_im[f];

					double asm_phasor_re_ni = asm_scat_freq_re[f] + asm_radi_freq_re[f]; // NOTE : NO INCIDENT WAVE IN THE FINAL PHASOR
					double asm_phasor_im_ni = asm_scat_freq_im[f] + asm_radi_freq_im[f]; // NOTE : NO INCIDENT WAVE IN THE FINAL PHASOR

					// -- SYM. --

					cp.sym_real = sym_phasor_re;
					cp.sym_imag = sym_phasor_im;

					cp_ni.sym_real = sym_phasor_re_ni; // NOTE : NO INCIDENT WAVE IN THE FINAL PHASOR
					cp_ni.sym_imag = sym_phasor_im_ni; // NOTE : NO INCIDENT WAVE IN THE FINAL PHASOR

					cp_rd.sym_real = sym_radi_freq_re[f]; // NOTE : ONLY THE RADIATION PHASOR
					cp_rd.sym_imag = sym_radi_freq_im[f]; // NOTE : ONLY THE RADIATION PHASOR

					cp_sc.sym_real = sym_scat_freq_re[f]; // NOTE : ONLY THE SCATTERING PHASOR
					cp_sc.sym_imag = sym_scat_freq_im[f]; // NOTE : ONLY THE SCATTERING PHASOR

					cp_df.sym_real = sym_difc_freq_re[f]; // NOTE : ONLY THE DIFFRACTION PHASOR
					cp_df.sym_imag = sym_difc_freq_im[f]; // NOTE : ONLY THE DIFFRACTION PHASOR

					// -- ASYM. --

					cp.asm_real = asm_phasor_re;
					cp.asm_imag = asm_phasor_im;

					cp_ni.asm_real = asm_phasor_re_ni; // NOTE : NO INCIDENT WAVE IN THE FINAL PHASOR
					cp_ni.asm_imag = asm_phasor_im_ni; // NOTE : NO INCIDENT WAVE IN THE FINAL PHASOR

					cp_rd.asm_real = asm_radi_freq_re[f];
					cp_rd.asm_imag = asm_radi_freq_im[f];

					cp_sc.asm_real = asm_scat_freq_re[f];
					cp_sc.asm_imag = asm_scat_freq_im[f];

					cp_df.asm_real = asm_difc_freq_re[f];
					cp_df.asm_imag = asm_difc_freq_im[f];

					freq_out.write((char *)&cp, sizeof cp);			 // Print to hard drive as binary
					freq_ni_out.write((char *)&cp_ni, sizeof cp_ni); // Print to hard drive as binary ( NO INCIDENT WAVE IN THE FINAL PHASOR )
					freq_rd_out.write((char *)&cp_rd, sizeof cp_rd); // Print to hard drive as binary	( ONLY THE RADIATION   PHASORS )
					freq_sc_out.write((char *)&cp_sc, sizeof cp_sc); // Print to hard drive as binary	( ONLY THE SCATTERING  PHASORS )
					freq_df_out.write((char *)&cp_df, sizeof cp_df); // Print to hard drive as binary ( ONLY THE DIFFRACTION PHASORS )

					sym_radi_freq_re[f] = 0.; // Make this container ready for the next point.
					sym_radi_freq_im[f] = 0.; // Note that they should be initialised with 0.
					asm_radi_freq_re[f] = 0.;
					asm_radi_freq_im[f] = 0.;

					sym_difc_freq_re[f] = 0.; // Make this container ready for the next point.
					sym_difc_freq_im[f] = 0.; // Note that they should be initialised with 0.
					asm_difc_freq_re[f] = 0.;
					asm_difc_freq_im[f] = 0.;

					sym_scat_freq_re[f] = 0.; // Make this container ready for the next point.
					sym_scat_freq_im[f] = 0.; // Note that they should be initialised with 0.
					asm_scat_freq_re[f] = 0.;
					asm_scat_freq_im[f] = 0.;

					// ( Data in frequency domain are saved as: [line][i][f] )
					//
					// Note : The real and imaginary parts of the frequency domain data in
					// the binary file are stored in the struct "comp" defined at the top of this function.
					// There are two phasors for each point : the symmetric and the anti-symmetric.
					//
					//             line[0]
					// ------------------------------------ ...
					//              i[0]
					// ------------------------------------ ...
					//   f[0]     f[1]     f[2]      f[3]   ...
					//   C[0]     C[1]     C[2]      C[3]   ...

				} // End of frequency loop

			} // End of loop over water line points i

		} // End of loop over the (lines) or the free surfaces which are connected to the body (making water line)

		freq_out.close();
		freq_ni_out.close();
		freq_rd_out.close();
		freq_sc_out.close();
		freq_df_out.close();
		time_in.close();

		delete[] radi_tifq;
		delete[] scat_tifq;

		delete[] sym_radi_freq_re;
		delete[] sym_radi_freq_im;
		delete[] asm_radi_freq_re;
		delete[] asm_radi_freq_im;

		delete[] sym_difc_freq_re;
		delete[] sym_difc_freq_im;
		delete[] asm_difc_freq_re;
		delete[] asm_difc_freq_im;

		delete[] sym_scat_freq_re;
		delete[] sym_scat_freq_im;
		delete[] asm_scat_freq_re;
		delete[] asm_scat_freq_im;

		gsl_fft_real_workspace_free(space);
		gsl_fft_real_wavetable_free(table);

	} // End of wave drift check
}
