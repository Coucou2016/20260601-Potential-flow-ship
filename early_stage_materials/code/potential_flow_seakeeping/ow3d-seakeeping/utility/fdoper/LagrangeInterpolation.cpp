#include "OW3DUtilFunctions.h"

//
//
// This function calculates the interpolation/extrapolation
// coefficients based on the Lagrange's classical formula :
//
//
// f(x) = {    (x - x[1])(x - x[2]) ... (x - x[n-1]) / (x[0] - x[1])(x[0] - x[2]) ... (x[0] - x[n-1])    } y[0]
//      + {    (x - x[0])(x - x[2]) ... (x - x[n-1]) / (x[1] - x[0])(x[1] - x[2]) ... (x[1] - x[n-1])    } y[1]
//      + ...
//      + { (x - x[0])(x - x[1]) ... (x - x[n-2]) / (x[n-1] - x[0])(x[n-1] - x[1]) ... (x[n-1] - x[n-2]) } y[n-1]
//
// NOTES :
//       1. "x" array contains the coordinates of the points over which polynomail fits.
//       2.  n  denotes the number of points usedfor interpolation.
//       3.  p  is the coordinate of the point where the interpolated or extrapolated value is desired.
//       4.  c  is the array of the coefficients which will be used for interpolation/extrapolation as:
//
//          f(p) = c[0] * u[0] + c[1] * u[1] + c[2] * u[2] + ... c[n-1]u[n-1].
//
//           where "u" is the vector of the function values at the corresponding coordinates given by x array.
//
//

void OW3DSeakeeping::LagrangeInterpolation(int n, double *x, double p, double *c)
{
	for (int i = 0; i < n; i++)
	{
		c[i] = 1.;

		for (int j = 0; j < n; j++)
		{
			if (j != i)
			{
				c[i] *= (p - x[j]) / (x[i] - x[j]);
			}
		}
	}
}
