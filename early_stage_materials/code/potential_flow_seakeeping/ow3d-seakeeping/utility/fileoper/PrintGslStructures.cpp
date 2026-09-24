#include "gsl/gsl_vector.h"
#include "gsl/gsl_matrix.h"
#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::PrintGslMatrix(const gsl_matrix *M)
{
    for (unsigned int i = 0; i < M->size1; i++)
    {
        for (unsigned int j = 0; j < M->size2; j++)
            cout << gsl_matrix_get(M, i, j) << "  ";
        cout << '\n';
    }
}

void OW3DSeakeeping::PrintGslMatrix(const gsl_matrix_complex *M)
{
    for (unsigned int i = 0; i < M->size1; i++)
    {
        for (unsigned int j = 0; j < M->size2; j++)
        {
            gsl_complex z = gsl_matrix_complex_get(M, i, j);
            cout << GSL_REAL(z) << " " << GSL_IMAG(z) << ", ";
        }
        cout << '\n';
    }
}

void OW3DSeakeeping::PrintGslVector(const gsl_vector *V)
{
    for (unsigned int i = 0; i < V->size; i++)
        cout << gsl_vector_get(V, i) << '\n';
}
