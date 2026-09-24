//
// -----------------------------------------------------------------------------------------------------------------------------------------
//
// This file contains the integrand functions "S(w)" required for the approximation of
// continuous inverse Fourier transform integrands.
// By calling one of the following functions, the integrand is sampled and calculated n times
// for the desired grid point located at x, y, z. The sampled data are then stored in
// the double* which has been supplied as an argument. One can simply add a new S(w) to this file.
//
// The wave number "k", becomes available to the integrands via the sixth argument that
// is a reference to all K that is evaluated just once. This is the whole vector containing
// the wave numbers that will be inserted in S(w) for sampling. By this we alleviate the need
// for calculating the wave numbers for each sampling operation.
//
// Since the inverse transform is with respect to encounter
// frequency, we use omegae as the variable name to emphasize this.
//
// Note: instead of calculating the term cosh(x), we can calculate
// the identical term :
//                        cosh(x) = [1 + exp(-2*x)] / (2*exp(-x))
//
// So the term : cosh(k(h+z)) / cosh(kh) is identical to:
//
//  [ (1+exp(-2*(k(h+z))))/(2*exp(-k(h+z))) ] / [ (1+exp(-2kh))/(2*exp(-kh)) ] which simplifies to:
//
//  [1+exp(-2*(k(h+z)))]*(2*exp(-kh) / ( [1+exp(-2kh)]*2*exp(-k(h+z)) ) = ( 1+exp(-2kz)*exp(-2kh) ) / ( exp(-kz)*(1+exp(-2kh)) )
//
// and finally we can write:
//
//  cosh(k(h+z)) / cosh(kh) = [exp(kz) + exp(-k(z+2h))] / [1 + exp(-2kh)]
//
// And for calculating the term sinh(x):
//
//                        sinh(x) = [1 - exp(-2*x)] / (2*exp(-x))
//
// So:
//
// sinh(k(h+z)) / cosh(kh) = [exp(kz) - exp(-k(z+2h))] / [1 + exp(-2kh)]
//
// This is done just to prevent the overflow while calculating cosh(k(h+z)) / cosh(kh) or sinh(k(h+z)) / cosh(kh) for very large k.
//
// Note also that the term [ gk/omega = gk/sqrt(gk*tanh(kh)) = sqrt(gk/tanh(kh)) ] has a removable singularity at k=0.
//
// Using Hopital's rule :  ( d/dk(gk)/d/dk(tanh(kh))) = g/(h*(1-tanh^2(kh)) so lim (sqrt(gk/tanh(kh))) k-> 0 is sqrt( g/h )
//
// Note:
//
// The pseudo-impulse term " exp(-pow(omegae),2)/a) " has been written based on encounter frequency. In the case we write this
// with respect to the absolute frequency, then we must multiply the time domain pseudo-impulse by:
//
//  exp(i*omega0*t).
//
// Where omega0 = k*U*cos(beta) that is the shift we brought to the encounter frequency.
//
// Then in this case the pseudo-impulse in frequency domain is : exp(-pow(omegae + k*U*cos(beta) ),2)/a). This shift
// in the frequency can be applied by the turning the "shift" parameter on.
//
// ---------------------------------------------------------------------------------------------------------------------------------------------

#include "Modes.h"

void OW3DSeakeeping::Diffraction::incidentWave_X_Integrand_(
	double *s_data,
	double *a_data,
	int n,
	const double &x,
	const double &y,
	const double &z,
	const vector<double> &K,
	void *params)
{
	integrandParameters *parameters = (integrandParameters *)params; // typecast the void pointer

	double h = parameters->h;
	double g = parameters->g;
	double betar = parameters->betar;
	double U = parameters->U;
	double a = parameters->a;
	double df = parameters->df;
	bool shift = parameters->shift;

	double w = 0.0;

	double S = sqrt(g / h); // to remove the singularity at k=0

	int increment = 1;
	int r = 0;

	double omegae, k;

	for (int p = 0; p < n; p += increment) // sampling loop
	{
		k = K[r];

		if (shift)
		{
			w = k * U * cos(betar);
		}

		if (k != 0)
		{
			S = sqrt(g * k / tanh(k * h));
		}

		omegae = df * p;

		if (parameters->isDif3)
		{
			s_data[p] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * cos(k * z * sin(betar)); // real sym.
			a_data[p] = S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * sin(k * z * sin(betar));  // real anti-sym.

			if (p != 0 and p != n - 1) // these two are pure real for even length sequences
			{
				s_data[p + 1] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * cos(k * z * sin(betar)); // imag sym.
				a_data[p + 1] = S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * sin(k * z * sin(betar));  // imag anti-sym.
			}
		}
		else
		{
			s_data[p] = S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * cos(k * z * sin(betar));  // real sym.
			a_data[p] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * sin(k * z * sin(betar)); // real anti-sym.

			if (p != 0 and p != n - 1) // these two are pure real for even length sequences
			{
				s_data[p + 1] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * cos(k * z * sin(betar)); // imag sym.
				a_data[p + 1] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * sin(k * z * sin(betar)); // imag anti-sym.
			}
		}

		if (p == 1)
			increment = 2;
		if (p == n - 2)
			increment = 1;
		r++;

	} // data is ready to be transformed
}

// ------------------------------------------------------------------------------------------------------------------------------------------------------------------
//
// NOTE : A special care is required to calculate the d_phi0_dz in the diffraction problem. As the boundary conditions are
//        splitted in to the symmetric and anti-symmetric parts we may have:
//
//        d_phis_dn = -n.grad(phi0)    =
//
//        -n.grad(phi0_sym + phi0_asm) = -[ nx(d_phi0_sym_dx) + ny(d_phi0_asm_dx) + nx(d_phi0_sym_dx) + ny(d_phi0_asm_dx) + nx(d_phi0_sym_dx) + ny(d_phi0_asm_dx)]
//
//                                     = -[nx(d_phi0_sym) + ny(d_phi0_sym) + nz(d_phi0_asm)] - [nx(d_phi0_asm) + ny(d_phi0_asm) + nz(d_phi0_sym)
//
//
//       As can be seen for the symmetric scattering problem, the anti-symmetric part of the BC related to the z derivative has been used instead
//       of the symmetric part. The opposite is also valid for the anti-symmetric scattering problem. All forcings for the non-homogeneous BC must be
//       symmetric in the symmetric scattering problem. The normal vector in z direction has opposite sign with respec to the symmetry plane, and the
//       anti-symmetric part of BC need to be used with nz in order to get the final BC forcing symmetric. The same is also valid for the anti-symmetric forcing.
//
// ------------------------------------------------------------------------------------------------------------------------------------------------------------------

void OW3DSeakeeping::Diffraction::incidentWave_Z_Integrand_(
	double *s_data,
	double *a_data,
	int n,
	const double &x,
	const double &y,
	const double &z,
	const vector<double> &K,
	void *params)
{
	integrandParameters *parameters = (integrandParameters *)params; // typecast the void pointer

	double h = parameters->h;
	double g = parameters->g;
	double betar = parameters->betar;
	double U = parameters->U;
	double a = parameters->a;
	double df = parameters->df;
	bool shift = parameters->shift;

	double w = 0.0;

	double S = sqrt(g / h); // to remove the singularity at k=0

	int increment = 1;
	int r = 0;

	double omegae, k;

	for (int p = 0; p < n; p += increment) // sampling loop
	{
		k = K[r];

		if (shift)
		{
			w = k * U * cos(betar);
		}

		if (k != 0)
		{
			S = sqrt(g * k / tanh(k * h));
		}

		omegae = df * p;

		if (parameters->isDif3)
		{
			s_data[p] = S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * sin(k * z * sin(betar));  // real anti-sym. (Read NOTE above)
			a_data[p] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * cos(k * z * sin(betar)); // real sym.      (Read NOTE above)

			if (p != 0 and p != n - 1) // these two are pure real for even length sequences
			{
				s_data[p + 1] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * sin(k * z * sin(betar)); // imag anti-sym. (Read NOTE above)
				a_data[p + 1] = S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * cos(k * z * sin(betar));  // imag sym.      (Read NOTE above)
			}
		}
		else
		{

			s_data[p] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * sin(k * z * sin(betar)); // real anti-sym. (Read NOTE above)
			a_data[p] = S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * cos(k * z * sin(betar));  // real sym.      (Read NOTE above)

			if (p != 0 and p != n - 1) // these two are pure real for even length sequences
			{
				s_data[p + 1] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * sin(k * z * sin(betar)); // imag anti-sym. (Read NOTE above)
				a_data[p + 1] = -S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * cos(k * z * sin(betar)); // imag sym.      (Read NOTE above)
			}
		}

		if (p == 1)
			increment = 2;
		if (p == n - 2)
			increment = 1;
		r++;

	} // data is ready to be transformed
}

void OW3DSeakeeping::Diffraction::incidentWave_Y_Integrand_(
	double *s_data,
	double *a_data,
	int n,
	const double &x,
	const double &y,
	const double &z,
	const vector<double> &K,
	void *params)
{
	integrandParameters *parameters = (integrandParameters *)params; // typecast the void pointer

	double h = parameters->h;
	double g = parameters->g;
	double betar = parameters->betar;
	double U = parameters->U;
	double a = parameters->a;
	double df = parameters->df;
	bool shift = parameters->shift;

	double w = 0.0;

	double S = sqrt(g / h); // to remove the singularity at k=0

	int increment = 1;
	int r = 0;

	double k, omegae;

	for (int p = 0; p < n; p += increment) // sampling loop
	{
		k = K[r];

		if (shift)
		{
			w = k * U * cos(betar);
		}

		if (k != 0)
		{
			S = sqrt(g * k / tanh(k * h));
		}

		omegae = df * p;

		if (parameters->isDif3)
		{
			s_data[p] = -S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * cos(k * z * sin(betar)); // real sym.
			a_data[p] = -S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * sin(k * z * sin(betar)); // real anti-sym.

			if (p != 0 and p != n - 1) // these two are pure real for even length sequences
			{
				s_data[p + 1] = S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * cos(k * z * sin(betar)); // imag sym.
				a_data[p + 1] = S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * sin(k * z * sin(betar)); // imag anti-sym.
			}
		}
		else
		{
			s_data[p] = S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * cos(k * z * sin(betar)); // real sym.
			a_data[p] = S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * sin(k * z * sin(betar)); // real anti-sym.

			if (p != 0 and p != n - 1) // these two are pure real for even length sequences
			{
				s_data[p + 1] = S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * cos(k * x * cos(betar)) * cos(k * z * sin(betar));  // imag sym.
				a_data[p + 1] = -S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae + w, 2) / a) * sin(k * x * cos(betar)) * sin(k * z * sin(betar)); // imag anti-sym.
			}
		}

		if (p == 1)
			increment = 2;
		if (p == n - 2)
			increment = 1;
		r++;

	} // data is ready to be transformed
}

void OW3DSeakeeping::Diffraction::incidentWave_Phi_Integrand_(
	double *s_data,
	double *a_data,
	int n,
	const double &x,
	const double &y,
	const double &z,
	const vector<double> &K,
	void *params)
{
	integrandParameters *parameters = (integrandParameters *)params; // typecast the void pointer

	double h = parameters->h;
	double g = parameters->g;
	double betar = parameters->betar;
	// double U = parameters->U;
	double a = parameters->a;
	double df = parameters->df;

	double S = 0;

	int increment = 1;
	int r = 0;

	double k, omegae;

	for (int p = 0; p < n; p += increment) // sampling loop
	{
		omegae = df * p;

		if (omegae == 0)
		{
			S = 1e-15;
		}

		k = K[r];

		if (parameters->isDif3)
		{
			s_data[p] = -g / (omegae + S) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae, 2) / a) * sin(k * x * cos(betar)) * cos(k * z * sin(betar)); // real sym.
			a_data[p] = -g / (omegae + S) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae, 2) / a) * cos(k * x * cos(betar)) * sin(k * z * sin(betar)); // real anti-sym.

			if (p != 0 and p != n - 1) // these two are pure real for even length sequences
			{
				s_data[p + 1] = g / (omegae + S) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae, 2) / a) * cos(k * x * cos(betar)) * cos(k * z * sin(betar)); // imag sym.
				a_data[p + 1] = g / (omegae + S) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae, 2) / a) * sin(k * x * cos(betar)) * sin(k * z * sin(betar)); // imag anti-sym.
			}
		}
		else
		{
			s_data[p] = g / (omegae + S) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae, 2) / a) * sin(k * x * cos(betar)) * cos(k * z * sin(betar)); // real sym.
			a_data[p] = g / (omegae + S) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae, 2) / a) * cos(k * x * cos(betar)) * sin(k * z * sin(betar)); // real anti-sym.

			if (p != 0 and p != n - 1) // these two are pure real for even length sequences
			{
				s_data[p + 1] = g / (omegae + S) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae, 2) / a) * cos(k * x * cos(betar)) * cos(k * z * sin(betar));	 // imag sym.
				a_data[p + 1] = -g / (omegae + S) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * exp(-pow(omegae, 2) / a) * sin(k * x * cos(betar)) * sin(k * z * sin(betar)); // imag anti-sym.
			}
		}

		if (p == 1)
			increment = 2;
		if (p == n - 2)
			increment = 1;
		r++;

	} // data is ready to be transformed
}
