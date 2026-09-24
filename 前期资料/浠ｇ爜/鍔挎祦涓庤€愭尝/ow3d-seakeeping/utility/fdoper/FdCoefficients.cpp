// This script calculates the standard finite difference coefficients
// for a one-dimensional stencil comprised af "a" and "b" surrounding points.
//
// As an example:
//
//  * * O * * * *     a = 2, and b = 4 (left and right) , r = a + b + 1.
//
// Taylor series expansion always starts from the leftmost point.

#include "gsl/gsl_linalg.h"
#include "gsl/gsl_sf_gamma.h"
#include "OW3DUtilFunctions.h"

RealArray OW3DSeakeeping::FdCoefficients(unsigned int a, unsigned int b, int derivative)
{
  unsigned int i, j;

  // build coefficient matrix

  unsigned int size = a + b + 1;

  RealArray results(size, size);
  Range r(0, size - 1);

  gsl_matrix *m = gsl_matrix_alloc(size, size);

  for (i = 0; i < size; i++)
  {
    for (j = 0; j < size; j++)
    {
      if (i < a)
      {
        double lp = pow(-1, j) * pow(a - i, j) / gsl_sf_fact(j);
        gsl_matrix_set(m, i, j, lp);
      }
      else if (i == a)
      {
        double p = 0.0;
        if (j == 0)
          p = 1.0;

        gsl_matrix_set(m, i, j, p);
      }
      else
      {
        double rp = pow(i - a, j) / gsl_sf_fact(j);
        gsl_matrix_set(m, i, j, rp);
      }
    }
  }

  // invert the matrix

  int signum;
  gsl_matrix *inverse = gsl_matrix_alloc(size, size);
  gsl_permutation *perm = gsl_permutation_alloc(size);
  gsl_linalg_LU_decomp(m, perm, &signum);
  gsl_linalg_LU_invert(m, perm, inverse);

  for (i = 0; i < size; i++) // for this derivative
  {
    for (j = 0; j < size; j++) // all coefficients
    {
      results(j, i) = gsl_matrix_get(inverse, i, j); // This is not a bug! note below.
    }
  }

  gsl_matrix_free(m);
  gsl_permutation_free(perm);
  gsl_matrix_free(inverse);

  return results(r, derivative);
}

//
// the reason why we write results(j,i) instead of results(i,j) is becuase
// of the way RealArray in A++ stores the data. If we print a RealArray, the elements
// along axis0 are printed in a row, and elements along axis1 are printed in a column.
// We defined the "results" to be a RealArray where axis0 specifies the type of
// the derivative, and axis1 contains the whole finite difference coefficients.
// The fd coefficients in the gsl matrix are in a row but in the "results" RealArray
// they are in a column.
//
// axis 0 ---> :   (0) (1) (2) (3)
//
// axis 1 ( 0)      o   o   o   o   ....
// axis 1 ( 1)      o   o   o   o   ....
// axis 1 ( 2)      o   o   o   o   ....
// axis 1 ( 3)      o   o   o   o   ....
// axis 1 ( 4)      o   o   o   o   ....
// axis 1 ( 5)      o   o   o   o   ....
