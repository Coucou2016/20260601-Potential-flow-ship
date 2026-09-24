#include "gsl/gsl_sf_gamma.h"
#include "OW3DUtilFunctions.h"

// This function implements the line integration according to the procedure described by Harry B. Bingham
// in "A note on finite differences in multiple-domain boundary-fitted coordinates".
//
// The line integration of a discretized function over a non-uniform grid is transformed to the
// integration of the same function in the unit space uniform grid. Integral of each segment in
// the physical domain is carried out by an equivalent integral over the interval [0 1].
// Using the Taylor series, the function value in the unit space is expanded around 0. By this
// the line integration reduces in to a summation of the derivatives of the function expressed
// based on the function value at the start of the segment. These derivatives can now easily be
// calculated using the finite-difference coefficients.
//
// This function needs :
//
//                     Npt = The number of grid points (Note: This is not needed in the overloaded function)
//                       f = A pointer to double, giving the function's value (Note: in the overloaded function this is vector<double>)
//                      dl = length of the segments (Note : the function is overloaded and "dl" can be either double or vector<double>)
//                       C = A RealArray, giving the fd coefficients for all derivatives for the internal points
//                   Cleft = A vector of RealArrays, each giving the fd coefficients for all points at the left  boundary.
//                  Cright = A vector of RealArrays, each giving the fd coefficients for all points at the right boundary.
//
//
//
//  NOTE : THIS FUNCTION IS OVERLOADED, AND TEHRE ARE 2 VERSIONS AVAILABLE : ONE
//         WITH CONSTANT "dl" AND THE ONE WITH VARIABLE "dl".
//         2 NEW FUNCTION ARE ALSO ADDED, WHICH CAN BE USED TO CALCULATE THE INTEGRALS
//         WITH THE INTEGRABLE SINGULARITIES AT THE LEFT-MOST OR THE RIGHT-MOST BOUNDARY. IN THIS CASE,
//         THE TAYLOR EXPANSION IS PERFORMED AROUND X=1 OR X=0 (WHERE APPLICABLE ) IN THE MAPPED DOMAIN.
//         IN IN THE ORIGINAL FUNCTIONS THIS IS PERFORMED ONLY AROUND X=0. NOTE THAT THESE 2 FUNCTIONS ARE
//         ONLY FOR UNIFORMLY SPACED INTEGRANDS.
//
//  NOTE : THESE INTEGRATION ROUTINES SHOULD NOT BE USED IN THE CASE OF HIGHLY OSCILLATORY FUNCTIONS,
//         FOR EXAMPLE: INT[SIN(1/X)] DX AND X[0,1].
//
//
//
//

double OW3DSeakeeping::IntegrateLineData(
	int Npt,
	double *f,
	double dl,
	const RealArray &C,
	const vector<RealArray> &Cleft,
	const vector<RealArray> &Cright)
{
	if (Cleft.size() != Cright.size())
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The supplied coefficients are not correct.");
	}

	if (Cleft.size() % 2 != 0)
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The integration order must be even.");
	}

	if (Npt < C.getLength(0))
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The desired order can not be supported by this number of points.");
	}

	int R = C.getLength(0); // STENCIL WIDTH
	int Order = R - 1;
	int NumSeg = Npt - 1; // NUMBER OF THE SEGMENTS
	double result = 0.;

	for (int s = 0; s < NumSeg; s++) // CALCULATE THE INTEGRAL FOR THE SEGMENT WITH INDEX "s"
	{
		for (int i = 0; i <= Order; i++) // THIS DEPENDS ON THE DERIVATIVES OP TO ORDER "Order"
		{
			if (s < Order / 2) // POINTS AT THE LEFT BOUNDARY
			{
				int counter = 0;

				for (int j = 0; j <= Order; j++)
				{
					result += f[j] * Cleft[s](counter++, i) / gsl_sf_fact(i + 1);
				}
			}

			else if ((Npt - s - 1) < Order / 2) // POINTS AT THE RIGHT BOUNDARY
			{
				int rem = Npt - s - 1;
				int counter = 0;

				for (int j = s - (Order - rem); j < Npt; j++)
				{
					result += f[j] * Cright[Npt - s - 1](counter++, i) / gsl_sf_fact(i + 1);
				}
			}

			else
			{
				int counter = 0;

				for (int j = s - Order / 2; j <= s + Order / 2; j++) // INTERNAL POINTS
				{
					result += f[j] * C(counter++, i) / gsl_sf_fact(i + 1);
				}
			}
		}
	}

	return (result * dl); // NOTE : IT IS ASSUMED THAT ALL SEGMENTS HAVE A CONSTANT LENGTH "dl"
}

// -------------------------------------------------------------------
//
// The overloaded function with "f" and "dl" given as vector<double>
//
// -------------------------------------------------------------------

double OW3DSeakeeping::IntegrateLineData(
	vector<double> f,
	vector<double> dl,
	const RealArray &C,
	const vector<RealArray> &Cleft,
	const vector<RealArray> &Cright)
{
	if (Cleft.size() != Cright.size())
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The supplied coefficients are not correct.");
	}

	if (Cleft.size() % 2 != 0)
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The integration order must be even.");
	}

	int Npt = f.size(); // Number of the points in the vector

	if (Npt < C.getLength(0))
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The desired order can not be supported by this number of points.");
	}

	int R = C.getLength(0); // STENCIL WIDTH
	int Order = R - 1;
	int NumSeg = Npt - 1; // NUMBER OF THE SEGMENTS
	double result = 0.;

	for (int s = 0; s < NumSeg; s++) // CALCULATE THE INTEGRAL FOR THE SEGMENT WITH INDEX "s"
	{
		for (int i = 0; i <= Order; i++) // THIS DEPENDS ON THE DERIVATIVES UP TO ORDER "Order"
		{
			if (s < Order / 2) // POINTS AT THE LEFT BOUNDARY
			{
				int counter = 0;

				for (int j = 0; j <= Order; j++)
				{
					result += dl[s] * f[j] * Cleft[s](counter++, i) / gsl_sf_fact(i + 1);
				}
			}

			else if ((Npt - s - 1) < Order / 2) // POINTS AT THE RIGHT BOUNDARY
			{
				int rem = Npt - s - 1;
				int counter = 0;

				for (int j = s - (Order - rem); j < Npt; j++)
				{
					result += dl[s] * f[j] * Cright[Npt - s - 1](counter++, i) / gsl_sf_fact(i + 1);
				}
			}

			else
			{
				int counter = 0;

				for (int j = s - Order / 2; j <= s + Order / 2; j++) // INTERNAL POINTS
				{
					result += dl[s] * f[j] * C(counter++, i) / gsl_sf_fact(i + 1);
				}
			}
		}

	} // End of segment loop

	return result;
}

// -------------------------------------------------------------------
//
// The following function implements a left-open integration scheme
//
// NOTE : The function value at the leftmost part is irrelavant to
//        the final results, but its place in the array must be
//        reserved. Juts initialize that with an arbitrary value.
//
// -------------------------------------------------------------------

double OW3DSeakeeping::IntegrateLineDataLo(
	int Npt,
	double *f,
	double dl,
	const RealArray &C,
	const vector<RealArray> &Cleft,
	const vector<RealArray> &Cright)
{
	if (Cleft.size() != Cright.size())
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The supplied coefficients are not correct.");
	}

	if (Cleft.size() % 2 != 0)
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The integration order must be even.");
	}

	if (Npt < C.getLength(0))
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The desired order can not be supported by this number of points.");
	}

	int R = C.getLength(0); // STENCIL WIDTH
	int Order = R - 1;
	int NumSeg = Npt - 1; // NUMBER OF THE SEGMENTS
	double result = 0.;

	for (int s = 0; s < NumSeg; s++) // CALCULATE THE INTEGRAL FOR THE SEGMENT WITH INDEX "s"
	{
		for (int i = 0; i <= Order; i++) // THIS DEPENDS ON THE DERIVATIVES OP TO ORDER "Order"
		{
			if (s < Order / 2) // POINTS AT THE LEFT BOUNDARY
			{
				int counter = 0;

				for (int j = 1; j <= Order + 1; j++)
				{
					result += f[j] * Cleft[s](counter++, i) / gsl_sf_fact(i + 1) * pow(-1, i + 2);
				}
			}

			else if ((Npt - s - 2) < Order / 2) // POINTS AT THE RIGHT BOUNDARY
			{
				int counter = 0;

				for (int j = Npt - Order - 1; j < Npt; j++)
				{
					result += f[j] * Cright[Npt - s - 2](counter++, i) / gsl_sf_fact(i + 1) * pow(-1, i + 2);
				}
			}

			else
			{
				int counter = 0;

				for (int j = s - Order / 2 + 1; j <= s + Order / 2 + 1; j++) // INTERNAL POINTS
				{
					result += f[j] * C(counter++, i) / gsl_sf_fact(i + 1) * pow(-1, i + 2);
				}
			}
		}
	}

	return (result * dl); // NOTE : IT IS ASSUMED THAT ALL SEGMENTS HAVE A CONSTANT LENGTH "dl"
}

// ----------------------------------------------------------------------------------
//
// The following function implements a left- and right-open integration scheme
//
// NOTE : The function value at the left- and right-most part are irrelavant to
//        the final results, but their places in the array must be
//        reserved. Juts initialize thoes with arbitrary values.
//
// ---------------------------------------------------------------------------------

double OW3DSeakeeping::IntegrateLineDataBo(
	int Npt,
	double *f,
	double dl,
	const RealArray &C,
	const vector<RealArray> &Cleft,
	const vector<RealArray> &Cright)
{
	if (Cleft.size() != Cright.size())
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The supplied coefficients are not correct.");
	}

	if (Cleft.size() % 2 != 0)
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The integration order must be even.");
	}

	if (Npt < C.getLength(0))
	{
		throw runtime_error("Error, IntegrateLineData.cpp: The desired order can not be supported by this number of points.");
	}

	int R = C.getLength(0); // STENCIL WIDTH
	int Order = R - 1;
	int NumSeg = Npt - 1; // NUMBER OF THE SEGMENTS
	double result = 0.;

	for (int s = 0; s < NumSeg; s++) // CALCULATE THE INTEGRAL FOR THE SEGMENT WITH INDEX "s"
	{
		for (int i = 0; i <= Order; i++) // THIS DEPENDS ON THE DERIVATIVES OP TO ORDER "Order"
		{
			if (s < Order / 2 + 1) // POINTS AT THE LEFT BOUNDARY
			{
				int counter = 0;

				for (int j = 1; j <= Order + 1; j++) // Expansion around 1
				{
					result += f[j] * Cleft[s](counter++, i) / gsl_sf_fact(i + 1) * pow(-1, i + 2);
				}
			}

			else if ((Npt - s - 2) < Order / 2) // POINTS AT THE RIGHT BOUNDARY (Expansion around 0)
			{
				int rem = Npt - s - 2;
				int counter = 0;

				for (int j = s - (Order - rem); j < Npt - 1; j++)
				{
					result += f[j] * Cright[Npt - s - 2](counter++, i) / gsl_sf_fact(i + 1);
				}
			}

			else
			{
				int counter = 0;

				for (int j = s - Order / 2; j <= s + Order / 2; j++) // INTERNAL POINTS (Expansion around 0)
				{
					result += f[j] * C(counter++, i) / gsl_sf_fact(i + 1);
				}
			}
		}
	}

	return (result * dl); // NOTE : IT IS ASSUMED THAT ALL SEGMENTS HAVE A CONSTANT LENGTH "dl"
}
