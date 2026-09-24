//
// Implementation of the Diffraction class
//
// --------------------------------------------------------------------------------------------------------------------------------------------
//
// NOTE : To consider the grid symmetry while solving for the diffraction problem (to get both scattering and Froud-Krylove force),
// 	  first we try to build a body boundary condition that has one symmetric and one anti-symmetric component which is defined basically
//        over the whole grid and not just on the half of it. If such boundary conditions can be found, then the calculation of the forces
//        is straightforward when just half of the grid is modeled. In the case of the scattering problem, this can be done by considering
//        this fact that all functions can be written as a summation of even and odd functions as follows:
//
// 		f(z) = g(z)_e + s(z)_o , where
//
// 		g(z)_e =  1/2 * ( f(z) + f(-z) ) that is an even function
//
// 		s(z)_o =  1/2 * ( f(z) - f(-z) ) that is an odd function
//
//        So whenever half of the grid is modeled, the body boundary condition "f(z)", is defined and calculated for both negative
//        and positive z coordinate, the corresponding even and odd body boundary conditions will be built. This idea has been applied
//        when the boundary conditions are built based on the analytical integrals for the deep-water case. For the arbitrary-depth cases
//        this idea is also valid, but the symmetric and anti-symmetric BCs are built explicitly by inverse Fourier transform of the
//        symmetric and anti-symmetric frequency-domain incident wave potential data. Look in to file "transformIntegrands.cpp" for more
//        details.
//
//        In the case of the Froud-Krylov force, these even and odd components are already in the complex phasor of the
//        incident wave pressure force. In fact we distinguish the cos(z) and sin(z) in the complex phasor and build these
//        even and odd functions.
//
// --------------------------------------------------------------------------------------------------------------------------------------------

#include "Modes.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Diffraction::Diffraction(
	const CompositeGrid &cg,
	const OW3DSeakeeping::Grid::GridData &gridData,
	DIFF_TYPES diff_type) : Modes(gridData),
							gridData_(&gridData),
							boundariesData_(&gridData.boundariesData)
{
	elevFileName_ = _resultsDirectory + '/' + OW3DSeakeeping::impulse_wave_elevation_binary_file;
	timeFileName_ = _resultsDirectory + '/' + OW3DSeakeeping::time_binary_file;
	diff_type_ = diff_type;
	rk_stage_count_ = OW3DSeakeeping::rk_stage_count;
	rk_c_ = OW3DSeakeeping::rk_c;
	noes_ = boundariesData_->exciting.size();
	U_ = OW3DSeakeeping::UserInput.U;
	g_ = OW3DSeakeeping::UserInput.g;
	betar_ = OW3DSeakeeping::UserInput.beta * Pi / 180;
	mwl_ = gridData_->avgWl_spacing;
	h_ = gridData_->maximum_depth;
	s_ = _simulation_data.frequency_deviation;
	a_ = pow(Pi * s_, 2) * 8;
	b_ = _simulation_data.frequency_deviation * sqrt(2 * Pi);

	multx_ = cos(betar_) / (2 * Pi * b_);
	multz_ = sin(betar_) / (2 * Pi * b_);
	multy_ = 1 / (2 * Pi * b_);

	deep_water_ = false; // Both must be false

	deep_check_ = false; // for arbitrary depth
	if (deep_check_)
	{
		double bignumber = 1e5;
		h_ = h_ * bignumber;
	}

	integTol_ = 1e-10;

	// --------------------------------------------------------------
	// Determine type of diffraction problem with regard to symmetry
	// --------------------------------------------------------------

	if (
		diff_type_ == DIFF_TYPES::FULL || //
		diff_type_ == DIFF_TYPES::OM1 ||  // All thses cases are relevant when the user
		diff_type_ == DIFF_TYPES::OM2 ||  // builds the grid for the whole geometry,
		diff_type_ == DIFF_TYPES::OM3	  // regardless of the incident wave angle.
	)
		SymOrAsymOrWhole_ = SymAsymWhole::Whole;

	else if (
		diff_type_ == DIFF_TYPES::SYM ||	 //
		diff_type_ == DIFF_TYPES::HEAD ||	 // All these cases are symmetric diffractions
		diff_type_ == DIFF_TYPES::OM1_HLF || // and the user builds only half of the geometry.
		diff_type_ == DIFF_TYPES::OM2_HLF || //
		diff_type_ == DIFF_TYPES::OM3_HLF || //
		diff_type_ == DIFF_TYPES::OM1_SYM || //
		diff_type_ == DIFF_TYPES::OM2_SYM || //
		diff_type_ == DIFF_TYPES::OM3_SYM)
		SymOrAsymOrWhole_ = SymAsymWhole::Sym;

	else										// All these cases are for the anti-symmetric problems,
		SymOrAsymOrWhole_ = SymAsymWhole::Asym; // when the user builds only half of the geometry.

	// ----------------------------------
	// Resize and VRealArrays for x, y ,z
	// ----------------------------------

	X_.allresize(gridData.boundariesData);
	Y_.allresize(gridData.boundariesData);
	Z_.allresize(gridData.boundariesData);

	// ------------------------------------------
	// Resize the boundary condition time vectors
	// ------------------------------------------

	VRealArrays temp(gridData.boundariesData);

	for (int i = 0; i < OW3DSeakeeping::rk_stage_count * _simulation_data.step_count; i++)
	{
		dphi0dx_.push_back(temp);
		dphi0dz_.push_back(temp);
		dphi0dy_.push_back(temp);
	}

	double *timeVector; // Which is the same for all points on the body
	double *s_ifftData; // Must be a double* to use the gsl library (sym. component)
	double *a_ifftData; // Must be a double* to use the gsl library (anti-sym. component)
	double *flip;		//

	// ----------------------------
	// Build the wave number vector
	// ----------------------------

	double df, dt, HSR;

	// +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	// +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	//
	// * WAVE INCIDENT FROM ABAFT OF THE BEAM (ENTER THIS BLOCK ONLY WHEN U!=0)
	//
	// +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	// +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

	if ((betar_ < Pi / 2 or betar_ > 3 * Pi / 2) and OW3DSeakeeping::UserInput.U != 0)
	{
		FSK0lim_ = GetFSK0lim(0, h_, mwl_, betar_, OW3DSeakeeping::UserInput.U, OW3DSeakeeping::UserInput.g, 1e10); // The limit wave number

		omegaec_ = OW3DSeakeeping::UserInput.g * tanh(FSK0lim_ * h_) / (4 * OW3DSeakeeping::UserInput.U * cos(betar_));

		tauc_ = omegaec_ * OW3DSeakeeping::UserInput.U / OW3DSeakeeping::UserInput.g;

		if (
			diff_type_ == DIFF_TYPES::OM1 ||	 // THE CASE
			diff_type_ == DIFF_TYPES::OM1_HLF || // WHICH ARE
			diff_type_ == DIFF_TYPES::OM1_SYM || // RELATED TO
			diff_type_ == DIFF_TYPES::OM1_ASM	 // OMEGA01
		)
		{
			HSR = omegaec_; // Half of the sampling rate (the highest resolved frequency)

			dt = 0.5 / HSR;

			double expo = log(_simulation_data.step_count * 4) / log(2);
			n_ = pow(2, expo);

			if (n_ % 2 != 0)
			{
				n_ = n_ + 1; // NOTE : THIS WOULD REDUCE THE SPEED OF GSL FFT.
			}

			df = HSR / (n_ - 1);

			timeVector = new double[n_];
			s_ifftData = new double[n_];
			a_ifftData = new double[n_];
			flip = new double[n_];

			for (int i = 0; i < n_; i++)
			{
				timeVector[i] = (-n_ / 2 + i) * dt * 2 * Pi;
			}

			int increment = 1;

			for (int p = 0; p < n_; p += increment)
			{
				double omegae = df * p;

				if (omegae == 0)
				{
					K_.push_back(0);
				}
				else
				{
					K_.push_back(GetFSK01(omegae, h_, FSK0lim_, betar_, OW3DSeakeeping::UserInput.U, OW3DSeakeeping::UserInput.g, 1e10)); // ---> NOTE : WAVE NUMBERS FROM OMEGA01 FUNCTION
				}
				if (p == 1)
					increment = 2;
				if (p == n_ - 2)
					increment = 1;
			}

		} // End of omega01 case

		if (
			diff_type_ == DIFF_TYPES::OM2 ||	 // THE CASE
			diff_type_ == DIFF_TYPES::OM2_HLF || // WHICH ARE
			diff_type_ == DIFF_TYPES::OM2_SYM || // RELATED TO
			diff_type_ == DIFF_TYPES::OM2_ASM	 // OMEGA02
		)
		{
			HSR = omegaec_; // Half of the sampling rate (the highest resolved frequency)

			dt = 0.5 / HSR;

			double expo = log(_simulation_data.step_count * 4) / log(2);
			n_ = pow(2, expo);

			if (n_ % 2 != 0)
			{
				n_ = n_ + 1; // NOTE : THIS WOULD REDUCE THE SPEED OF GSL FFT.
			}

			df = HSR / (n_ - 1);

			timeVector = new double[n_];
			s_ifftData = new double[n_];
			a_ifftData = new double[n_];
			flip = new double[n_];

			for (int i = 0; i < n_; i++)
			{
				timeVector[i] = (-n_ / 2 + i) * dt * 2 * Pi;
			}

			int increment = 1;

			for (int p = 0; p < n_; p += increment)
			{
				double omegae = df * p;

				K_.push_back(GetFSK02(omegae, h_, FSK0lim_, betar_, OW3DSeakeeping::UserInput.U, OW3DSeakeeping::UserInput.g, 1e10)); // ---> NOTE : WAVE NUMBERS FROM OMEGA02 FUNCTION

				if (p == 1)
					increment = 2;
				if (p == n_ - 2)
					increment = 1;
			}

		} // End of omega02 case

		if (
			diff_type_ == DIFF_TYPES::OM3 ||	 // THE CASE
			diff_type_ == DIFF_TYPES::OM3_HLF || // WHICH ARE
			diff_type_ == DIFF_TYPES::OM3_SYM || // RELATED TO
			diff_type_ == DIFF_TYPES::OM3_ASM	 // OMEGA03
		)

		{
			double expo = log(_simulation_data.step_count * 4) / log(2);
			n_ = pow(2, floor(expo));

			if (n_ % 2 != 0)
			{
				n_ = n_ + 1; // NOTE : THIS WOULD REDUCE THE SPEED OF GSL FFT.
			}

			timeVector = new double[n_];
			s_ifftData = new double[n_];
			a_ifftData = new double[n_];
			flip = new double[n_];

			dt = _simulation_data.sample_time / (n_ - 1);

			HSR = 0.5 / dt; // Half of the sampling rate

			df = HSR / (n_ - 1); // Delta_f in the frequency space

			for (int i = 0; i < n_; i++)
			{
				timeVector[i] = (-n_ / 2 + i) * dt * 2 * Pi;
			}

			int increment = 1;

			for (int p = 0; p < n_; p += increment)
			{
				double omegae = df * p;

				K_.push_back(GetFSK03(omegae, h_, FSK0lim_, betar_, OW3DSeakeeping::UserInput.U, OW3DSeakeeping::UserInput.g, 1e10)); // ---> NOTE : WAVE NUMBERS FROM OMEGA03 FUNCTION

				if (p == 1)
					increment = 2;
				if (p == n_ - 2)
					increment = 1;
			}

		} // End of omega03 case
	}

	// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	//
	// * WAVE INCIDENT FROM AHEAD OF THE BEAM (WHEN U!=0), AND FROM ANY ARBITRARY HEADING (WHEN U==0).
	//
	// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

	else
	{
		double expo = log(_simulation_data.step_count * 4) / log(2);
		n_ = pow(2, floor(expo));

		if (n_ % 2 != 0)
		{
			n_ = n_ + 1; // NOTE : THIS WOULD REDUCE THE SPEED OF GSL FFT.
		}

		timeVector = new double[n_];
		s_ifftData = new double[n_];
		a_ifftData = new double[n_];
		flip = new double[n_];

		dt = _simulation_data.sample_time / (n_ - 1);

		HSR = 0.5 / dt; // Half of the sampling rate

		df = HSR / (n_ - 1); // Delta_f in the frequency space

		for (int i = 0; i < n_; i++)
		{
			timeVector[i] = (-n_ / 2 + i) * dt * 2 * Pi;
		}

		int increment = 1;

		for (int p = 0; p < n_; p += increment)
		{
			double omegae = df * p;

			if (omegae == 0) // In both zero and forward-speed cases, when omega or omegae = 0 k is 0
			{
				K_.push_back(0);
			}
			else
			{
				K_.push_back(Wavenumber(omegae, h_, mwl_, betar_, OW3DSeakeeping::UserInput.U, OW3DSeakeeping::UserInput.g, 1e10));
			}

			if (p == 1)
				increment = 2;
			if (p == n_ - 2)
				increment = 1;
		}
	}

	// --------------------------------------------
	// Allocate space for gsl ifft and interpolant
	// --------------------------------------------

	gsl_fft_halfcomplex_wavetable *hc;
	gsl_fft_real_workspace *work;
	work = gsl_fft_real_workspace_alloc(n_);
	hc = gsl_fft_halfcomplex_wavetable_alloc(n_);

	gsl_interp *interpSym;
	gsl_interp *interpAsy;
	interpSym = gsl_interp_alloc(gsl_interp_cspline, n_);
	interpAsy = gsl_interp_alloc(gsl_interp_cspline, n_);
	gsl_interp_accel *interpAccel;
	interpAccel = gsl_interp_accel_alloc();

	// -------------------------------------
	// Parameters for the inverse transform
	// -------------------------------------

	integrandParameters integParams;
	integParams.h = h_;
	integParams.g = OW3DSeakeeping::UserInput.g;
	integParams.betar = betar_;
	integParams.U = OW3DSeakeeping::UserInput.U;
	integParams.a = a_;
	integParams.df = df;
	integParams.shift = deep_check_; // Must be true if one is trying to verify with the deep water analytical equations (Not available for the following-seas cases)

	integParams.isDif3 = false;

	if (
		diff_type_ == DIFF_TYPES::OM3 ||
		diff_type_ == DIFF_TYPES::OM3_HLF ||
		diff_type_ == DIFF_TYPES::OM3_SYM ||
		diff_type_ == DIFF_TYPES::OM3_ASM)

		integParams.isDif3 = true;

	// -----------------------------------
	//
	// Now build the boundary conditions
	//
	// -----------------------------------

	for (int surface = 0; surface < noes_; surface++)
	{
		const Single_boundary_data &be = gridData.boundariesData.exciting[surface];
		const MappedGrid &mg = cg[be.grid];
		const RealArray &v = mg.vertex();
		const vector<Index> &Is = be.surface_indices;

		// Store the body surface coordinates

		X_[surface] = v(Is[0], Is[1], Is[2], axis1);
		Y_[surface] = v(Is[0], Is[1], Is[2], axis2);
		Z_[surface] = 0.0;

		if (gridData.nod == 3)
		{
			Z_[surface] = v(Is[0], Is[1], Is[2], axis3);
		}

		int lnt0 = X_[surface].getLength(0);
		int lnt1 = X_[surface].getLength(1);
		int lnt2 = X_[surface].getLength(2);

		if (!deep_water_)
		{
			for (int i0 = 0; i0 < lnt0; i0++)
			{
				for (int i1 = 0; i1 < lnt1; i1++)
				{
					for (int i2 = 0; i2 < lnt2; i2++)
					{
						// First the boundary conditions in time domain is calculated for this point (i, j, k) using ifft
						// Then the boundary condition is interpolated at the Runge-kutta stages for this point (i, j, k)

						// ----------------------------------------------------------------------------------------------
						//                                       Get x gradient
						// ----------------------------------------------------------------------------------------------

						incidentWave_X_Integrand_(
							s_ifftData,
							a_ifftData,
							n_,
							X_[surface](i0, i1, i2),
							Y_[surface](i0, i1, i2),
							Z_[surface](i0, i1, i2),
							K_,
							&integParams);

						if ((betar_ >= Pi / 2 and betar_ <= 3 * Pi / 2) or OW3DSeakeeping::UserInput.U == 0 or integParams.isDif3)
						{
							if (abs(s_ifftData[n_ - 1]) > integTol_ or abs(a_ifftData[n_ - 1]) > integTol_)
							{
								cout << "x integrand (symmetric) : " << abs(s_ifftData[n_ - 1]) << '\n'
									 << "x integrand (anti-symmetric) : " << abs(a_ifftData[n_ - 1]) << '\n'
									 << "tolerance : " << integTol_ << '\n';
								throw runtime_error(GetColoredMessage("\t Error (OW3D) Diffraction::Diffraction.cpp.\n\t The integrand for the x velocity is larger than the tolerance.", 0));
							}
						}

						if (SymOrAsymOrWhole_ == SymAsymWhole::Whole) // An arbitrary 3d non-symmetric grid or a 2d grid
						{
							ComputeInverseTransform_(s_ifftData, hc, work, n_, dt, flip);
							ComputeInverseTransform_(a_ifftData, hc, work, n_, dt, flip);
						}
						else if (SymOrAsymOrWhole_ == SymAsymWhole::Sym) // A symmetric diffraction
						{
							ComputeInverseTransform_(s_ifftData, hc, work, n_, dt, flip);
						}
						else // An anti-symmetric diffraction
						{
							ComputeInverseTransform_(a_ifftData, hc, work, n_, dt, flip);
						}

						InterpolateDiffractionBCs_(
							s_ifftData,
							a_ifftData,
							timeVector,
							n_,
							dphi0dx_,
							surface,
							i0, i1, i2,
							interpSym,
							interpAsy,
							interpAccel);

						// ----------------------------------------------------------------------------------------------
						//                                       Get z gradient
						// ----------------------------------------------------------------------------------------------

						incidentWave_Z_Integrand_(
							s_ifftData,
							a_ifftData,
							n_,
							X_[surface](i0, i1, i2),
							Y_[surface](i0, i1, i2),
							Z_[surface](i0, i1, i2),
							K_,
							&integParams);
						if ((betar_ >= Pi / 2 and betar_ <= 3 * Pi / 2) or OW3DSeakeeping::UserInput.U == 0 or integParams.isDif3)
						{
							if (abs(s_ifftData[n_ - 1]) > integTol_ or abs(a_ifftData[n_ - 1]) > integTol_)
							{
								cout << "z integrand (symmetric) : " << abs(s_ifftData[n_ - 1]) << '\n'
									 << "z integrand (anti-symmetric) : " << abs(a_ifftData[n_ - 1]) << '\n'
									 << "tolerance : " << integTol_ << '\n';
								throw runtime_error(GetColoredMessage("Error (OW3D), Diffraction::Diffraction.cpp.\n\t The integrand for the z velocity is larger than the tolerance.", 0));
							}
						}

						if (SymOrAsymOrWhole_ == SymAsymWhole::Whole) // An arbitrary 3d non-symmetric grid or a 2d grid
						{
							ComputeInverseTransform_(s_ifftData, hc, work, n_, dt, flip);
							ComputeInverseTransform_(a_ifftData, hc, work, n_, dt, flip);
						}
						else if (SymOrAsymOrWhole_ == SymAsymWhole::Sym) // A symmetric diffraction
						{
							ComputeInverseTransform_(s_ifftData, hc, work, n_, dt, flip);
						}
						else // An anti-symmetric diffraction
						{
							ComputeInverseTransform_(a_ifftData, hc, work, n_, dt, flip);
						}

						InterpolateDiffractionBCs_(
							s_ifftData,
							a_ifftData,
							timeVector,
							n_,
							dphi0dz_,
							surface,
							i0, i1, i2,
							interpSym,
							interpAsy,
							interpAccel);

						// ----------------------------------------------------------------------------------------------
						//                                       Get y gradient
						// ----------------------------------------------------------------------------------------------

						incidentWave_Y_Integrand_(
							s_ifftData,
							a_ifftData,
							n_,
							X_[surface](i0, i1, i2),
							Y_[surface](i0, i1, i2),
							Z_[surface](i0, i1, i2),
							K_,
							&integParams);

						if ((betar_ >= Pi / 2 and betar_ <= 3 * Pi / 2) or OW3DSeakeeping::UserInput.U == 0 or integParams.isDif3)
						{
							if (abs(s_ifftData[n_ - 1]) > integTol_ or abs(a_ifftData[n_ - 1]) > integTol_)
							{
								cout << "y integrand (symmetric) : " << abs(s_ifftData[n_ - 1]) << '\n'
									 << "y integrand (anti-symmetric) : " << abs(a_ifftData[n_ - 1]) << '\n'
									 << "tolerance : " << integTol_ << '\n';
								throw runtime_error(GetColoredMessage("Error (OW3D), Diffraction::Diffraction.cpp.\n\t The integrand for the y velocity is larger than the tolerance.", 0));
							}
						}

						if (SymOrAsymOrWhole_ == SymAsymWhole::Whole) // An arbitrary 3d non-symmetric grid or a 2d grid
						{
							ComputeInverseTransform_(s_ifftData, hc, work, n_, dt, flip);
							ComputeInverseTransform_(a_ifftData, hc, work, n_, dt, flip);
						}
						else if (SymOrAsymOrWhole_ == SymAsymWhole::Sym) // A symmetric diffraction
						{
							ComputeInverseTransform_(s_ifftData, hc, work, n_, dt, flip);
						}
						else // An anti-symmetric diffraction
						{
							ComputeInverseTransform_(a_ifftData, hc, work, n_, dt, flip);
						}

						InterpolateDiffractionBCs_(
							s_ifftData,
							a_ifftData,
							timeVector,
							n_,
							dphi0dy_,
							surface,
							i0, i1, i2,
							interpSym,
							interpAsy,
							interpAccel);
					}
				}
			}

		} // End of arbitrary depth boundary condition

	} // End of loop over the body surface

	if (!deep_water_)
		OW3DSeakeeping::PrintLogMessage("Diffraction BC is computed.");

	if (deep_water_)
	{
		deep_alpha_prime_p_.resize(gridData.boundariesData);
		deep_I0p_.resize(gridData.boundariesData);
		deep_I1p_.resize(gridData.boundariesData);
		deep_I2p_.resize(gridData.boundariesData);

		deep_alpha_prime_n_.resize(gridData.boundariesData);
		deep_I0n_.resize(gridData.boundariesData);
		deep_I1n_.resize(gridData.boundariesData);
		deep_I2n_.resize(gridData.boundariesData);

		deep_dphi0xp_.allresize(gridData.boundariesData);
		deep_dphi0zp_.allresize(gridData.boundariesData);
		deep_dphi0yp_.allresize(gridData.boundariesData);

		deep_dphi0xn_.allresize(gridData.boundariesData);
		deep_dphi0zn_.allresize(gridData.boundariesData);
		deep_dphi0yn_.allresize(gridData.boundariesData);

		deep_alpha_prime_p_(0) = -Y_ / OW3DSeakeeping::UserInput.g + 1.0 / (8 * pow(Pi * s_, 2)); // the real part is constant
		deep_alpha_prime_n_(0) = -Y_ / OW3DSeakeeping::UserInput.g + 1.0 / (8 * pow(Pi * s_, 2)); // the real part is constant

		deep_omegaBarp_ = X_ * cos(betar_) + Z_ * sin(betar_); // in order to include the grid symmetry we
		deep_omegaBarn_ = X_ * cos(betar_) - Z_ * sin(betar_); // need to define omegaBar for both positive and negative side of the grid( +/- z)
	}

	// de-allocate the memories

	delete[] timeVector;
	delete[] s_ifftData;
	delete[] a_ifftData;
	delete[] flip;

	gsl_interp_free(interpSym);
	gsl_interp_free(interpAsy);
	gsl_interp_accel_free(interpAccel);

	gsl_fft_real_workspace_free(work);
	gsl_fft_halfcomplex_wavetable_free(hc);

} // end of constructor

OW3DSeakeeping::Diffraction::~Diffraction()
{
}

const OW3DSeakeeping::Modes::Motion &OW3DSeakeeping::Diffraction::GetMotionData(
	int step,
	int stage)
{
	double c = _rk_c[stage];
	double dt = _simulation_data.time_step;

	motions_.time = (step + c) * dt;

	double t = motions_.time - 0.5 * _simulation_data.sample_time;

	motions_.elevation = exp(-2.0 * pow(Pi * s_, 2.0) * pow(t, 2)); // note : elevation also must be shifted in time

	if (deep_water_)
	{
		// is called just for verification purpose or in deep water condition. In the case of
		// verification, turn on the "shift" variable in the parameters, and select a large water depth.

		DeepwaterDiffractionBCs_(t);

		motions_.gradphi0x = deep_dphi0x_;
		motions_.gradphi0y = deep_dphi0y_;
		motions_.gradphi0z = deep_dphi0z_;
	}

	else
	{
		int index = step * rk_stage_count_ + stage;

		motions_.gradphi0x = multx_ * dphi0dx_[index];
		motions_.gradphi0y = multy_ * dphi0dy_[index];
		motions_.gradphi0z = multz_ * dphi0dz_[index];
	}

	motions_.displacement = 0.0; // body is fixed in diffraction problem
	motions_.velocity = 0.0;	 // body is fixed in diffraction problem
	motions_.fsbcRamp = 1.0;

	return motions_;
}

void OW3DSeakeeping::Diffraction::StoreMotionData() const
{
	double time = motions_.time;

	ofstream tbout(timeFileName_, ios_base::out | ios_base::app | ios_base::binary);
	tbout.write((char *)&time, sizeof time);

	double elev = motions_.elevation;
	ofstream ebout(elevFileName_, ios_base::out | ios_base::app | ios_base::binary);
	ebout.write((char *)&elev, sizeof elev);
}