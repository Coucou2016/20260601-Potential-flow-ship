// This public member function belongs to the FisrtOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::TransformPotentialAndDerivatives()
{
	// An outline of the function
	//
	// Data preparation
	//
	//  for(surface)
	//   |
	//   |  for(i)
	//   |    | for(j)
	//   |    |   | for(k)
	//   |    |   |   |  for(type)
	//   |    |   |   |   |
	//   |    |   |   |   |   for(radiation)
	//   |    |   |   |   |    |
	//   |    |   |   |   |    |  calculate
	//   |    |   |   |   |    |  radiation
	//   |    |   |   |   |    |  phasors
	//   |    |   |   |   |    |
	//   |    |   |   |   |   end for(radiation)
	//   |    |   |   |   |
	//   |    |   |   |   |   for(diffraction)
	//   |    |   |   |   |    |
	//   |    |   |   |   |    | calculate
	//   |    |   |   |   |    | diffraction phasors
	//   |    |   |   |   |    | (scattering + incident wave)
	//   |    |   |   |   |    |
	//   |    |   |   |   |   end for(diffraction)
	//   |    |   |   |   |
	//   |    |   |   |   |   for(frequency)
	//   |    |   |   |   |    |
	//   |    |   |   |   |    | add all phasors
	//   |    |   |   |   |    | and print them out
	//   |    |   |   |   |    | to the binary file
	//   |    |   |   |   |    |
	//   |    |   |   |   |   end for(frequency)
	//   |    |   |   |   |
	//   |    |   |   |  end for(type)
	//   |    |   |  end for(k)
	//   |    |  end for(j)
	//   |   end for(i)
	//   |
	//  end for(surface)

	if (OW3DSeakeeping::UserInput.wave_drift)
	{
		const unsigned int fftsize = transformData_.size_of_fft; // The size of fft
		const unsigned int flength = omegae_.size();			 // The desired frequency length
		// const double dt = simulationData_.print_time_step;			 // Time step
		// const double te = steps_ * dt;							 // The end time of the original signal (needed for asymptotic business!)
		// const double omegac = transformData_.omegac;			 // Critical frequency                  (needed for asymptotic business!)

		const double sinBeta = sin(betar_);
		const double cosBeta = cos(betar_);

		double dat; // The data for the binary files are read in to this variable

		struct comp
		{
			double sym_real;
			double sym_imag;
			double asm_real;
			double asm_imag;

		} cp, cp_ni, cp_rd, cp_sc, cp_df; // The frequency domain data is stored in this variable. (cp: all, cp_ni: no incidets wave , cp_rd : only radiations, cp_sc: Only scattering, cp_df : Only diffraction)

		// Note : The time domain signals will be padded either
		// with 0 or with the asymptotic values in the case of radiation runs.

		// ---------------------------------------------------------------------------------------------------------------------------------------
		//
		// Declare and initialize data structures
		//
		// ---------------------------------------------------------------------------------------------------------------------------------------

		double *radi_tifq = new double[fftsize]; // For both the time- and the frequency-domain data - to be given to gsl fft
		double *scat_tifq = new double[fftsize];

		double *sym_radi_freq_re = new double[flength]; // Just for the frequency-domain data ( is assigned after radi_tifq has been transfomred )
		double *sym_radi_freq_im = new double[flength];
		double *asm_radi_freq_re = new double[flength];
		double *asm_radi_freq_im = new double[flength];

		double *sym_difc_freq_re = new double[flength]; // Just for the frequency-domain data ( is assigned after radi_tifq has been transfomred )
		double *sym_difc_freq_im = new double[flength]; // NOTE : These containers are used for the case
		double *asm_difc_freq_re = new double[flength]; // the contributions from the incident wave are
		double *asm_difc_freq_im = new double[flength]; // going to be stored in the final phasor "cp".

		double *sym_scat_freq_re = new double[flength]; // Just for the frequency-domain data ( is assigned after radi_tifq has been transfomred )
		double *sym_scat_freq_im = new double[flength]; // NOTE : These containers are used for the case
		double *asm_scat_freq_re = new double[flength]; // the contributions from the incident wave are
		double *asm_scat_freq_im = new double[flength]; // NOT going to be stored in the final phasor "cp_ni".

		double *ana_re = new double[flength]; // To store the analytical transforms
		double *ana_im = new double[flength];

		for (unsigned int i = 0; i < fftsize; i++) // The data is initially padded with 0
		{
			radi_tifq[i] = 0.;
			scat_tifq[i] = 0.;
		}

		for (unsigned int f = 0; f < flength; f++) // NOTE : The containers must be initialized to zero.
		{
			ana_re[f] = 0.;
			ana_im[f] = 0.;

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

		vector<double> asymp_data; // Needed to save the data for the asymptotic continuation

		// Note : In gsl real mixed-radix transform the frequency domain data (return values)
		// are stored in the input time domain array. The real and imaginary parts
		// are adjacent to each other. Note also that we always keep the transform radix to be
		// a power of 2.

		gsl_fft_real_wavetable *table = gsl_fft_real_wavetable_alloc(fftsize);
		gsl_fft_real_workspace *space = gsl_fft_real_workspace_alloc(fftsize);

		// -------------------------------------------------------------------------------
		//
		// File for storing the potentials in frequency domain
		//
		// -------------------------------------------------------------------------------

		string freq_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_binary_file; // The file for the phasors including the contributions
		ofstream freq_out(freq_file, ios_base::out | ios_base::app | ios_base::binary);			   // from the incident wave. (Both radiation and diffraction)

		string freq_ni_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_no_incident_binary_file; // The file for the phasors excluding the contributions
		ofstream freq_ni_out(freq_ni_file, ios_base::out | ios_base::app | ios_base::binary);					  // from the incident wave. (Both radiation and scattering)

		string freq_rd_file = results_folder_ + '/' + fdomain_potentials_radiation_binary_file; // The file for the phasors including the contributions only
		ofstream freq_rd_out(freq_rd_file, ios_base::out | ios_base::app | ios_base::binary);	// from the radiation problems.

		string freq_sc_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_scattering_binary_file; // The file for the phasors including the contributions only
		ofstream freq_sc_out(freq_sc_file, ios_base::out | ios_base::app | ios_base::binary);					 // from the scattering problem.

		string freq_df_file = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_diffraction_binary_file; // The file for the phasors including the contributions only
		ofstream freq_df_out(freq_df_file, ios_base::out | ios_base::app | ios_base::binary);					  // from the diffraction problem.

		// Open the binary file for the potentials

		string time_file = time_domain_folder_ + '/' + OW3DSeakeeping::tdomain_body_potentials_binary_file;
		ifstream time_in(time_file, ios_base::in | ios_base::binary);

		if (!time_in.is_open())
		{
			throw runtime_error("Error, OW3DSeakeeping::FirstOrder::transformBodyPotentials.cpp: File for the time-domain potentials can not be opened.");
		}

		// ---------------------------------------------------------------------------------------
		//
		// 1th loop : Over the body surfaces.
		// 2nd loop : Over the points on the surface along axis 0
		// 3rd loop : Over the points on the surface along axis 1
		// 4th loop : Over the points on the surface along axis 2
		// 5th loop : Over the types of the data (phi and grad phi which amounts to npots_)
		//
		// ---------------------------------------------------------------------------------------

		for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
		{
			const Single_boundary_data &be = boundariesData_->exciting[surface];
			const vector<Index> &Is = be.surface_indices;
			MappedGrid &mg = (*cg_)[be.grid];
			const RealArray &v = mg.vertex();
			RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
			x = v(Is[0], Is[1], Is[2], axis1);
			y = v(Is[0], Is[1], Is[2], axis2);
			z = 0.0;

			if (gridData_->nod == 3)
			{
				z = v(Is[0], Is[1], Is[2], axis3);
			}

			const int l1 = Is[1].getLength();
			const int l2 = Is[2].getLength();

			// ---------------------------------------------
			//
			// The shift due to the previous surfaces
			//
			// ---------------------------------------------

			int surface_shift = 0;

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
						// for this point on the surface, we open the files for all runs and read the data for all types of potentials

						for (unsigned int pot = 0; pot < npots_; pot++) // the type of data to be read (potential or gradient)
						{
							// Next we loop over the radiation runs. The type of the data
							// that needs to be transformed ( potential or its gradients) is specified by
							// the variable "h". After each iteration of "h" loop the "radi_tifq" container
							// will be filled with the time-domain data for the point specified by "i" ,"j" and "k"
							// on the body surface identified with "surface" in the surface loop.
							//
							// Note: In the case of forward-speed problem, the asymptotic continuation will be done
							// inside this function using two pointers "ana_re" and "ana_im" which are for storing the
							// real and imaginary part of the analytical transform. In order to store the time-domain
							// data for finding the coefficients of the least-square fitting, a vector of
							// double called "asymp_data" will be used. The vector then is supplied to the
							// private member function called "calculatePotentialsAsymptoticCoefficients_" which
							// calculates the desired coefficients. The asymptotic continuation can be printed out for
							// the point specified by oti_, otj_, otk_, on the surface identified by ots_.
							// The analytical transform then will be calculated by the private member function
							// called " calculatePotentialsAnalyticalTransform_" . The time-domain data for the
							// numerical transform will be padded with zero or the least-quare model function values.
							//
							// Afterwards the numerical transform will be carried out and the frequency-domain results
							// are stored in the same container "radi_tifq". The final step is to loop over the frequencies.
							// In the frequency loop we carry out the following tasks:
							//
							// 1. Add the analytical (if any) and the numerical transforms for each frequecny.
							//
							// 2. Divide the results by the transform of the displacement to get the complex phasor for
							//    unint motion for each frequency.
							//
							// 3. Multiply the result by the RAO to get the complex phasor due to the motion caused by
							//    the unit wave amplitude for each frequency. Note that up to this point we manipulated the
							//    frequency-domain data which is stored in "radi_tifq" container.
							//
							// 4. Put the frequency-domain radiation data abtained above in to the "sym_radi_freq_re", "sym_radi_freq_im"
							//    and "asm_radi_freq_re" and "asm_radi_freq_im" which will be finally added to the diffraction phasors.
							//	Note that the radiation phasors are divided in to the symmetric and anti-symmetric components.
							//
							// 5. Up to this point we have calculated and stored the phasors for this radiation run, note
							//    that we are still inside the radiation runs loop. The phasors for the desired frequency
							//    range for this radiation runs are stored in "sym_radi_freq_re", "sym_radi_freq_im" and
							//    asm_radi_freq_re", "asm_radi_freq_im". The phasors for the next radiation run which have been obtained
							//    for the desired frequency range up to step 4 from the next run, will be added to the phasors of
							//    the previous radiation runs.

							// ---------------------------------------------------------------------
							//
							//  Calculate radiation phasors
							//
							// ---------------------------------------------------------------------

							for (unsigned int run = 0; run < radiation_runs_.size(); run++)
							{
								MODE_NAMES mode_name = radiation_runs_[run].mode;

								asymp_data.resize(0);

								// Note : The transform of the radiation runs first will be multipled by
								// the corresponding response amplitude operator. Finally all frequency-domain
								// radiation potentials will be added inside this loop

								int runs_shift = (run + diffraction_runs_.size()) * p_one_run_shift_;

								for (unsigned int t = 0; t < steps_; t++)
								{
									unsigned int steps_shift = t * p_one_step_shift_;

									// Linear indexing in to the binary files [run][time][surface][i][j][k][pot] ( h denotes the index for the type of the data )

									int shift = runs_shift + steps_shift + surface_shift + i * l1 * l2 * npots_ + j * l2 * npots_ + k * npots_ + pot;

									time_in.seekg(shift * (sizeof dat), ios_base::beg);
									time_in.read((char *)&dat, sizeof dat);

									radi_tifq[t] = dat;

									if (U_ != 0) // Save the data for the asymptotic continuation for this point
									{
										// asymp_data.push_back(dat);
									}

								} // End of time loop for this point

								// Zero pad the time-domain signal

								for (unsigned int zpad = steps_; zpad < fftsize; zpad++)
								{
									radi_tifq[zpad] = 0.;
								}

								// Asymptotic business! for this run at this point ( calculate "a" and "b" )

								if (U_ != 0)
								{
									// double cofs [2] = {0.0 , 0.0};

									// calculatePotentialsAsymptoticCoefficients_(asymp_data, cofs);

									// if(i==oti_ and j==otj_ and k==otk_ and surface==ots_)
									//   {
									//     outputAsymptoticPotentials_(excitation, pot, cofs);
									//   }

									// calculatePotentialsAnalyticalTransform_( ana_re, ana_im, cofs );  // For all frequencies.

									// // Pad the time domain signal with asymptotic values for this run (if any), otherwise it has been already padded by 0

									// for(int asypad=steps_; asypad<fftsize; asypad++)
									//   {
									//     double t = te + (asypad - steps_) * dt;

									//     radi_tifq[asypad] = ( cofs[0] * sin(omegac*t) + cofs[1] * cos(omegac*t) )/t;
									//   }

								} // End of asymptotic business!, radiation data is ready to be transformed

								// Note : in the following lines we do :
								//
								// 1. Transform the radiation potential
								// 2. Add the analytical and the numerical transforms
								// 3. Divide by the transform of the displacement to get the complex phasor for unint motion
								// 4. Multiply the result by the RAOs to get the complex phasor for the motion caused by the unit wave amplitude.
								// 5. Transfer the frequency-domain radiation data from "radi_tifq" in to
								//    the "sym_radi_freq_re", "sym_radi_freq_im" and "asm_radi_freq_re", "asm_radi_freq_im".
								// 6. Add the complex phasors for symmetric and anti-symmetric radiation runs respectively.

								gsl_fft_real_transform(radi_tifq, 1, fftsize, table, space);

								unsigned int increment = 1;
								unsigned int index = 0; // This index will increase to : (flength)

								// Note: f in the following loop "f" will never reach close to fftsize, see "buildFrequenciesAndWaveNumbers", line 33

								for (unsigned int f = 0; f < fftsize; f += increment) // Transfer from gsl (radi_tifq)
								{
									double radi_re = 0.;
									double radi_im = 0.;

									if (f == 0) // The imaginary part is zero
									{
										// Add analytical with numerical transform

										radi_tifq[0] += ana_re[0];

										// Divide by the complex displacement to get the unit phasor. (a+ib)/(c+id) = [ (ac+bd) + i(bc-ad) ] / (c^2+d^2)

										radi_tifq[0] = radi_tifq[0] / freq_pseudo_disp_(0, index);

										// Multiply by RAO (a+ib)*(c+id) = (ac-bd) + i(ad+bc) where a+ib is the RAO

										radi_re = radi_tifq[0] * RAO_[run](0, 0);
									}
									else
									{
										index = (f + 1) / 2; // The correct index

										// Add analytical with numerical transform

										double npa_re = radi_tifq[f] + ana_re[index];
										double npa_im = radi_tifq[f + 1] + ana_im[index];

										// Divide by the complex displacement to get the unit phasor. (a+ib)/(c+id) = [ (ac+bd) + i(bc-ad) ] / (c^2+d^2)

										double denomd = pow(freq_pseudo_disp_(0, index), 2) + pow(freq_pseudo_disp_(1, index), 2);

										double unit_radi_re = (npa_re * freq_pseudo_disp_(0, index) + npa_im * freq_pseudo_disp_(1, index)) / denomd;
										double unit_radi_im = (npa_im * freq_pseudo_disp_(0, index) - npa_re * freq_pseudo_disp_(1, index)) / denomd;

										// Multiply by RAO (a+ib)*(c+id) = (ac-bd) + i(ad+bc) where a+ib is the RAO

										radi_re = RAO_[run](0, index) * unit_radi_re - RAO_[run](1, index) * unit_radi_im;
										radi_im = RAO_[run](0, index) * unit_radi_im + RAO_[run](1, index) * unit_radi_re;
									}

									// Transfer and add to "sym_radi_freq_re", "sym_radi_freq_im" and "asm_radi_freq_re" , "asm_radi_fre_im".
									//
									// Note : All radiation complex phasors are added here

									if (
										mode_name == MODE_NAMES::HEAVE or
										mode_name == MODE_NAMES::SURGE or
										mode_name == MODE_NAMES::PITCH)
									{
										if (
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZ ||
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXZ ||
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIYZ) // NOTE : for the symmetric modes, phi_z, phi_xz and phi_yz are anti-symmetric.
										{
											asm_radi_freq_re[index] += radi_re;
											asm_radi_freq_im[index] += radi_im;
										}
										else
										{
											sym_radi_freq_re[index] += radi_re;
											sym_radi_freq_im[index] += radi_im;
										}
									}
									else
									{
										if (
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZ ||
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXZ ||
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIYZ) // NOTE : for the anti-symmetric modes, phi_z, phi_xz and phi_yz are symmetric.
										{
											sym_radi_freq_re[index] += radi_re;
											sym_radi_freq_im[index] += radi_im;
										}
										else
										{
											asm_radi_freq_re[index] += radi_re;
											asm_radi_freq_im[index] += radi_im;
										}
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

							// ---------------------------------------------------------------------
							//
							//  Calculate diffraction ( scattering + incident wave ) phasors
							//
							// ---------------------------------------------------------------------

							for (unsigned int run = 0; run < diffraction_runs_.size(); run++) // Calculate the diffraction phasors
							{
								// Note : The transform for diffraction runs will be divided to symmetric and anti-symmetric componnets

								DIFF_TYPES diftype = diffraction_runs_[run].diff_type;

								int runs_shift = run * p_one_run_shift_;

								for (unsigned int t = 0; t < steps_; t++)
								{
									int steps_shift = t * p_one_step_shift_;

									// Linear indexing in to the binary files [run][time][surface][i][j][k][h] ( h denotes the index for the type of the data )

									int shift = runs_shift + steps_shift + surface_shift + i * l1 * l2 * npots_ + j * l2 * npots_ + k * npots_ + pot;

									time_in.seekg(shift * (sizeof dat), ios_base::beg);
									time_in.read((char *)&dat, sizeof dat);

									scat_tifq[t] = dat;

								} // End of time loop for this point (ready for transform)

								// Zero pad the time-domain signal

								for (unsigned int zpad = steps_; zpad < fftsize; zpad++)
								{
									scat_tifq[zpad] = 0.;
								}

								// Note : In the following lines we do :
								//
								// 1. Transform the scattering potentials
								// 2. Divide the transform by the transform of the pseudo-impulse elevation
								// 3. Add the incident wave complex phasors to the scattering phasor.
								//
								// Note that the complex phasors for the diffraction problem
								// are decomposed in to the symmetric and anti-symmetric parts (similar to the radiation problrms).
								// This is ture for both the scattering and the incident wave phasors. If the grid is not
								// symmetric, still there are symmetric and anti-symmetric phasors. This happens for the radiation
								// phasors and the incident wave phasors. The symmetry has no meaning in this case, and the total
								// solution can be obtained by just adding symmetric and anti-symmetric components.
								//

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

									double sym_incid_re = 0.;
									double sym_incid_im = 0.;

									double asm_incid_re = 0.;
									double asm_incid_im = 0.;

									double wnb = ko_[index];	   // Wave number.
									double omega = omegao_[index]; // Angular frequency (absolute).

									// Use the follwoing identities:
									//
									// cosh(k(h+z)) / cosh(kh) = [exp(kz) + exp(-k(z+2h))] / [1 + exp(-2kh)]
									//
									// sinh(k(h+z)) / cosh(kh) = [exp(kz) - exp(-k(z+2h))] / [1 + exp(-2kh)]

									double chyp = (exp(wnb * y(i, j, k)) + exp(-wnb * (y(i, j, k) + 2 * h_))) / (1. + exp(-2 * wnb * h_));
									double shyp = (exp(wnb * y(i, j, k)) - exp(-wnb * (y(i, j, k) + 2 * h_))) / (1. + exp(-2 * wnb * h_));

									if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHI) // phi0
									{
										if (omega == 0)
										{
											sym_incid_re = g_ * x(i, j, k) * cosBeta / sqrt(g_ * h_); // NOTE : These are the limiting values in the
											sym_incid_im = 0;										  // case of omega = 0. Actually we do not need
																									  // the results at this frequency. Note that
											asm_incid_re = g_ * z(i, j, k) * sinBeta / sqrt(g_ * h_); // sym_incid_im -> infinity in this limit, but
											asm_incid_im = 0;										  // we instead used zero here. Other limits are correct.
										}
										else
										{
											sym_incid_re = g_ / (omega)*chyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = g_ / (omega)*chyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = g_ / (omega)*chyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = -g_ / (omega)*chyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIX) // phi0x
									{
										if (omega == 0)
										{
											sym_incid_re = g_ * cosBeta / sqrt(g_ * h_); // NOTE : These are the limiting values in the
											sym_incid_im = 0.;							 // case of omega = 0. Actually we do not need
																						 // the results at this frequency.
											asm_incid_re = 0.;							 //
											asm_incid_im = 0.;							 //
										}
										else
										{
											sym_incid_re = (g_ * wnb * cosBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = -(g_ * wnb * cosBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = -(g_ * wnb * cosBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = -(g_ * wnb * cosBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIY) // phi0y
									{
										if (omega == 0)
										{
											sym_incid_re = 0.; // NOTE : These are the limiting values in the
											sym_incid_im = 0.; // case of omega = 0. Actually we do not need
															   // the results at this frequency.
											asm_incid_re = 0.; //
											asm_incid_im = 0.; //
										}
										else
										{
											sym_incid_re = (g_ * wnb) / omega * shyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = (g_ * wnb) / omega * shyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = (g_ * wnb) / omega * shyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = -(g_ * wnb) / omega * shyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZ) // phi0z
									{
										if (omega == 0)
										{
											sym_incid_re = 0.; // NOTE : These are the limiting values in the
											sym_incid_im = 0.; // case of omega = 0. Actually we do not need
															   // the results at this frequency.
											asm_incid_re = 0.; //
											asm_incid_im = 0.; //
										}
										else
										{
											sym_incid_re = (g_ * wnb * sinBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = -(g_ * wnb * sinBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = -(g_ * wnb * sinBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = -(g_ * wnb * sinBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXX) // phi0xx
									{
										if (omega == 0)
										{
											sym_incid_re = 0.; // NOTE : These are the limiting values in the
											sym_incid_im = 0.; // case of omega = 0. Actually we do not need
															   // the results at this frequency.
											asm_incid_re = 0.; //
											asm_incid_im = 0.; //
										}
										else
										{
											sym_incid_re = -(g_ * wnb * wnb * cosBeta * cosBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = -(g_ * wnb * wnb * cosBeta * cosBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = -(g_ * wnb * wnb * cosBeta * cosBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = (g_ * wnb * wnb * cosBeta * cosBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIYY) // phi0yy
									{
										if (omega == 0)
										{
											sym_incid_re = 0.; // NOTE : These are the limiting values in the
											sym_incid_im = 0.; // case of omega = 0. Actually we do not need
															   // the results at this frequency.
											asm_incid_re = 0.; //
											asm_incid_im = 0.; //
										}
										else
										{
											sym_incid_re = (g_ * wnb * wnb) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = (g_ * wnb * wnb) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = (g_ * wnb * wnb) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = -(g_ * wnb * wnb) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZZ) // phi0zz
									{
										if (omega == 0)
										{
											sym_incid_re = 0.; // NOTE : These are the limiting values in the
											sym_incid_im = 0.; // case of omega = 0. Actually we do not need
															   // the results at this frequency.
											asm_incid_re = 0.; //
											asm_incid_im = 0.; //
										}
										else
										{
											sym_incid_re = -(g_ * wnb * wnb * sinBeta * sinBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = -(g_ * wnb * wnb * sinBeta * sinBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = -(g_ * wnb * wnb * sinBeta * sinBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = (g_ * wnb * wnb * sinBeta * sinBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXY) // phi0xy
									{
										if (omega == 0)
										{
											sym_incid_re = 0.; // NOTE : These are the limiting values in the
											sym_incid_im = 0.; // case of omega = 0. Actually we do not need
															   // the results at this frequency.
											asm_incid_re = 0.; //
											asm_incid_im = 0.; //
										}
										else
										{
											sym_incid_re = (g_ * wnb * wnb * cosBeta) / omega * shyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = -(g_ * wnb * wnb * cosBeta) / omega * shyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = -(g_ * wnb * wnb * cosBeta) / omega * shyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = -(g_ * wnb * wnb * cosBeta) / omega * shyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXZ) // phi0xz
									{
										if (omega == 0)
										{
											sym_incid_re = 0.; // NOTE : These are the limiting values in the
											sym_incid_im = 0.; // case of omega = 0. Actually we do not need
															   // the results at this frequency.
											asm_incid_re = 0.; //
											asm_incid_im = 0.; //
										}
										else
										{
											sym_incid_re = -(g_ * wnb * wnb * cosBeta * sinBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = -(g_ * wnb * wnb * cosBeta * sinBeta) / omega * chyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = -(g_ * wnb * wnb * cosBeta * sinBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = (g_ * wnb * wnb * cosBeta * sinBeta) / omega * chyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
										}
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIYZ) // phi0yz
									{
										if (omega == 0)
										{
											sym_incid_re = 0.; // NOTE : These are the limiting values in the
											sym_incid_im = 0.; // case of omega = 0. Actually we do not need
															   // the results at this frequency.
											asm_incid_re = 0.; //
											asm_incid_im = 0.; //
										}
										else
										{
											sym_incid_re = (g_ * wnb * wnb * sinBeta) / omega * shyp * cos(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
											sym_incid_im = -(g_ * wnb * wnb * sinBeta) / omega * shyp * cos(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);

											asm_incid_re = -(g_ * wnb * wnb * sinBeta) / omega * shyp * sin(wnb * z(i, j, k) * sinBeta) * sin(wnb * x(i, j, k) * cosBeta);
											asm_incid_im = -(g_ * wnb * wnb * sinBeta) / omega * shyp * sin(wnb * z(i, j, k) * sinBeta) * cos(wnb * x(i, j, k) * cosBeta);
										}
									}

									// ----------------------------------------------------------------------------
									// Calculate the symmetric and anti-symmetric components of diffraction phasors
									// ----------------------------------------------------------------------------

									// NOTE : THIS IS A SYMMETRIC DIFFRACTION RUN (JUST FOR SYMMETRIC GRIDS).

									if (diftype == DIFF_TYPES::SYM or diftype == DIFF_TYPES::HEAD)
									{
										if (
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZ ||
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXZ ||
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIYZ) // NOTE : for the symmetric modes, phi_z, phi_xz and phi_yz are anti-symmetric.
										{
											asm_difc_freq_re[index] = asm_incid_re + scat_re;
											asm_difc_freq_im[index] = asm_incid_im + scat_im;

											asm_scat_freq_re[index] = scat_re;
											asm_scat_freq_im[index] = scat_im;
										}
										else
										{
											sym_difc_freq_re[index] = sym_incid_re + scat_re;
											sym_difc_freq_im[index] = sym_incid_im + scat_im;

											sym_scat_freq_re[index] = scat_re;
											sym_scat_freq_im[index] = scat_im;
										}
									}

									// NOTE : THIS IS AN ANTI-SYMMETRIC DIFFRACTION RUN (JUST FOR SYMMETRIC GRIDS).

									else if (diftype == DIFF_TYPES::ASM) // An anti-Symmetric diffraction run (Just for symmetric grids).
									{
										if (
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZ ||
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXZ ||
											pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIYZ) // NOTE : for the anti-symmetric modes, phi_z, phi_xz and phi_yz are symmetric.
										{
											sym_difc_freq_re[index] = sym_incid_re + scat_re;
											sym_difc_freq_im[index] = sym_incid_im + scat_im;

											sym_scat_freq_re[index] = scat_re;
											sym_scat_freq_im[index] = scat_im;
										}
										else
										{
											asm_difc_freq_re[index] = asm_incid_re + scat_re;
											asm_difc_freq_im[index] = asm_incid_im + scat_im;

											asm_scat_freq_re[index] = scat_re;
											asm_scat_freq_im[index] = scat_im;
										}
									}

									// NOTE : THIS IS A GENERAL DIFFRACTION RUN (FOR NON-SYMMETRIC GRIDS).

									else // Non-symmetric grid
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

							} // End of diffraction runs loop

							// --------------------------------------------------------------------------
							//
							// Add the diffraction and the radiation phasors. Then print the results
							//
							// --------------------------------------------------------------------------

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

								cp.sym_real = sym_phasor_re; // NOTE : ALL PHASORS ( RADIATION + SCATTERING + INCIDENT )
								cp.sym_imag = sym_phasor_im; // NOTE : ALL PHAOSRS ( RADIATION + SCATTERING + INCIDENT )

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

								cp_rd.asm_real = asm_radi_freq_re[f]; // NOTE : ONLY THE RADIATION PHASOR
								cp_rd.asm_imag = asm_radi_freq_im[f]; // NOTE : ONLY THE RADIATION PHASOR

								cp_sc.asm_real = asm_scat_freq_re[f]; // NOTE : ONLY THE SCATTERING PHASOR
								cp_sc.asm_imag = asm_scat_freq_im[f]; // NOTE : ONLY THE SCATTERING PHASOR

								cp_df.asm_real = asm_difc_freq_re[f]; // NOTE : ONLY THE DIFFRACTION PHASOR
								cp_df.asm_imag = asm_difc_freq_im[f]; // NOTE : ONLY THE DIFFRACTION PHASOR

								// PUT IN THE FILES

								freq_out.write((char *)&cp, sizeof cp);			 // Print to hard drive as binary
								freq_ni_out.write((char *)&cp_ni, sizeof cp_ni); // Print to hard drive as binary ( NO INCIDENT WAVE IN THE FINAL PHASOR )
								freq_rd_out.write((char *)&cp_rd, sizeof cp_rd); // Print to hard drive as binary ( ONLY THE RADIATION   PHASORS )
								freq_sc_out.write((char *)&cp_sc, sizeof cp_sc); // Print to hard drive as binary ( ONLY THE SCATTERING  PHASORS )
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

								// ( Data in frequency domain are saved as: [surface][i][j][k][f][h] )

								// Note : The real and imaginary parts of the frequency domain data in
								// the binary file are stored in the struct "comp" defined at the top of this function.
								//
								//                                               surface                          ...
								// -------------------------------------------------------------------------------------------------------
								//                                              (i, j ,k)                         ...
								// -------------------------------------------------------------------------------------------------------
								//  f(0) f(1) f(2) f(3) ...
								// -------------------------------------------------------------------------------------------------------
								//       C[0]                     C[1]                      C[2]             ...       C[npots_-1]

							} // End of frequency loop

						} // End of loop over the type of the data ( phi or grad(phi) )

						// Note: At this point in the function, the complex phasors for all
						// data types ( phi or grad(phi) ) have been calculated and printed out
						// for the point located at i,j,k on the surface indicated by "surface"
						// in the loop.

					} // k

				} // j

			} // i

			// Note: At this point in the function, the complex phasors for all types
			// of data have been calculated and printed out for all grid points located
			// at the "surface" on the body. The same will be carried out in the next
			// iteration of the surface loop.

		} // End of loop over body surface

		freq_out.close();
		freq_ni_out.close();
		freq_rd_out.close();
		freq_sc_out.close();
		freq_df_out.close();
		time_in.close();

		delete[] ana_re;
		delete[] ana_im;

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

} // End of the function