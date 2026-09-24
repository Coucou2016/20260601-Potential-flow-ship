#include "gsl/gsl_sf_gamma.h"
#include "gsl/gsl_linalg.h"
#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::FdCf(
	int A,
	int B,
	int size,
	double *x,
	double ***C,
	int **ab)
{
	if (A + B + 1 > size)
		throw runtime_error("Error, FdCf.cpp: The stencil width is not correct !");

	// CALCULATE THE LENGTH OF THE INTERVALS

	vector<double> DX;

	for (int i = 0; i < size - 1; i++)
		DX.push_back(x[i + 1] - x[i]);

	double DXMIN = *min_element(DX.begin(), DX.end());

	int R = A + B + 1;

	gsl_matrix *MAT = gsl_matrix_calloc(size, size);

	for (int p = 0; p < size; p++)
	{
		if ((p > A or p == A) and (p + B < size - 1 or B + p == size - 1))
		{
			// Do not change A and B ( this is an internal point )

			ab[p][0] = A;
			ab[p][1] = B;
		}
		else
		{
			// Change A and B ( this is a boundary point )

			for (int i = 0; i < size; i++)
			{
				if ((p > A - i or p == A - i) and (p + B + i < size - 1 or B + p + i == size - 1))
				{
					ab[p][0] = A - i;
					ab[p][1] = B + i;
					break;
				}
			}
			for (int i = 0; i < size; i++)
			{
				if ((p > A + i or p == A + i) and (p + B - i < size - 1 or B + p - i == size - 1))
				{
					ab[p][0] = A + i;
					ab[p][1] = B - i;
					break;
				}
			}
		}

		for (int i = 0; i < ab[p][0]; i++)
		{
			for (int j = 0; j < R; j++)
			{
				gsl_matrix_set(MAT, i, j, pow((x[p - ab[p][0] + i] - x[p]) / DXMIN, j) / gsl_sf_fact(j));
			}
		}

		gsl_matrix_set(MAT, ab[p][0], 0, 1);

		for (int i = 0; i < ab[p][1]; i++)
		{
			for (int j = 0; j < R; j++)
			{
				gsl_matrix_set(MAT, i, j, pow((x[p + i + 1] - x[p]) / DXMIN, j) / gsl_sf_fact(j));
			}
		}
	}

	// INVERSE THE MATRIX

	int signum;
	gsl_matrix *inverse = gsl_matrix_alloc(size, size);
	gsl_permutation *perm = gsl_permutation_alloc(size);

	gsl_linalg_LU_decomp(MAT, perm, &signum);
	gsl_linalg_LU_invert(MAT, perm, inverse);

	// TRANSFER TO THE SOLUTION "C"

	for (int p = 0; p < size; p++)
	{
		for (int i = 0; i < R; i++) // FOR THE TYPE OF DERIVATIVES
		{
			for (int j = 0; j < R; j++) // FOR THE COEFFICIENTS
			{
				C[p][i][j] = gsl_matrix_get(MAT, i, j) / pow(DXMIN, i);
			}
		}
	}
}
