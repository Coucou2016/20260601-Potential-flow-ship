#include "gsl/gsl_vector.h"
#include "gsl/gsl_matrix.h"
#include "gsl/gsl_linalg.h"
#include "gsl/gsl_sf_gamma.h"
#include "OW3DUtilFunctions.h"
#include <valarray>
#include "Grid.h"

double GetMatCondition(const gsl_matrix *A)
{
    size_t M = A->size1;
    size_t N = A->size2;
    if (M != N)
        throw runtime_error(OW3DSeakeeping::GetColoredMessage("\t Error (OW3D), FDInterpolate2DWLS_.cpp (GetMatCondition).\n\t Input should be a square matrix.", 0));
    gsl_matrix *B = gsl_matrix_alloc(M, M);
    gsl_matrix_memcpy(B, A);
    int signum;
    gsl_permutation *perm = gsl_permutation_alloc(M);
    gsl_linalg_LU_decomp(B, perm, &signum);
    double rcond[0];
    gsl_vector *work = gsl_vector_alloc(3 * M);
    gsl_linalg_tri_rcond(CblasUpper, B, rcond, work);
    gsl_vector_free(work);
    gsl_permutation_free(perm);
    return rcond[0];
}

int OW3DSeakeeping::Grid::FDInterpolate2DWLS_(double *x0, valarray<valarray<double>> x, unsigned int np, double p, valarray<double> w, double dx, gsl_matrix *c)
{
    // Written by Harry B. Bingham in Matlab (Converted to C++ by maaf)
    //
    // Source: https://gitlab.gbar.dtu.dk/oceanwave3d/OW3D_FD_Utilities.git
    //
    // A function to pass a polynomial interpolant through the np
    // points at positions x(1:np,1:2) and evaluate the function plus it's
    // up to order p derivatives (p+1 Taylor coefficients) at the position
    // x0(1:2).  dx is a scale factor for the coefficients which is a
    // representative grid spacing. w(1:np) is the weight function for each
    //  stencil point.
    //
    //  The derivatives are ordered following Pascals triangle with y-derivatives
    //  in the inner loop.

    //
    // Build the scaled, Taylor coefficient matrix:
    //
    unsigned int nTaylor = (p + 1) * (p + 1);
    double fact = 1. / dx;
    gsl_matrix *W = gsl_matrix_alloc(np, np);
    gsl_matrix_set_zero(W);
    for (unsigned int i = 0; i < np; i++)
        gsl_matrix_set(W, i, i, w[i]);
    if (np < nTaylor)
        throw runtime_error(GetColoredMessage("\t Error (OW3D), FDInterpolate2DWLS.cpp.\n\t np must be >= (p+1)^2 for this WLS interpolation.", 0));
    int jm = 0;
    gsl_matrix *mat = gsl_matrix_alloc(np, nTaylor);
    for (unsigned int m = 0; m <= p; m++) // x-derivatives
    {
        for (unsigned int n = 0; n <= p; n++) // y-derivatives
        {
            for (unsigned int im = 0; im < np; im++)
            {
                double val = pow(fact * (x[im][0] - x0[0]), m) / gsl_sf_fact(m) * pow(fact * (x[im][1] - x0[1]), n) / gsl_sf_fact(n);
                gsl_matrix_set(mat, im, jm, val);
            }
            jm++;
        }
    }
    // Solve for the coefficients
    gsl_matrix *temp = gsl_matrix_alloc(nTaylor, np);
    gsl_matrix *Mat = gsl_matrix_alloc(nTaylor, nTaylor);
    gsl_matrix *MatInv = gsl_matrix_alloc(nTaylor, nTaylor);
    gsl_permutation *perm = gsl_permutation_alloc(nTaylor);
    gsl_blas_dgemm(CblasTrans, CblasNoTrans, 1.0, mat, W, 0.0, temp);
    gsl_blas_dgemm(CblasNoTrans, CblasNoTrans, 1.0, temp, mat, 0.0, Mat);
    int signum;
    gsl_linalg_LU_decomp(Mat, perm, &signum);
    gsl_linalg_LU_invert(Mat, perm, MatInv);
    gsl_blas_dgemm(CblasNoTrans, CblasTrans, 1.0, MatInv, mat, 0.0, temp);
    gsl_blas_dgemm(CblasNoTrans, CblasNoTrans, 1.0, temp, W, 0.0, c);
    //
    // Trap for a nearly singular matrix
    //
    double rcond = GetMatCondition(Mat);
    int errflag = (rcond <= 1.0e-15) ? 1 : 0;
    //
    // Re-scale the coefficients
    int im = 0;
    for (int m = 0; m <= p; m++)
        for (int n = 0; n <= p; n++)
        {
            for (unsigned int i = 0; i < np; i++)
                gsl_matrix_set(c, im, i, pow(fact, m) * pow(fact, n) * gsl_matrix_get(c, im, i));
            im++;
        }

    // Free the memories
    gsl_matrix_free(W);
    gsl_matrix_free(mat);
    gsl_matrix_free(temp);
    gsl_matrix_free(Mat);
    gsl_matrix_free(MatInv);
    gsl_permutation_free(perm);

    return errflag;
}