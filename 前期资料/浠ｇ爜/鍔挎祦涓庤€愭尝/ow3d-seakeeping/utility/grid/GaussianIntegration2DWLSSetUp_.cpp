
#include "OW3DUtilTypes.h"
#include "OW3DUtilFunctions.h"
#include "gsl/gsl_blas.h"
#include <numeric>
#include <valarray>
#include "Grid.h"

void OW3DSeakeeping::Grid::GaussianIntegration2DWLSSetUp_(double **x, double **uv, int **StencilMap, const intArray &EtoV, Patch *patch)
{
    // Written by Harry B. Bingham in Matlab (Converted to C++ by maaf)
    //
    // Source: https://gitlab.gbar.dtu.dk/oceanwave3d/OW3D_FD_Utilities.git
    //

    // Extract the parameters of the WLS scheme.

    unsigned int N = patch->nodenums;
    unsigned int p = patch->p;
    unsigned int np = patch->np;
    string Wtype = patch->Wtype;
    double sigma = patch->sigma;
    double Wmin = patch->Wmin;
    unsigned int nTaylor = (p + 1) * (p + 1);
    patch->nvec = gsl_matrix_alloc(N, 3);

    valarray<valarray<double>> xp;
    xp.resize(np, std::valarray<double>(0.0, 2));
    double xp0[2];
    valarray<double> d;
    vector<double> temp;
    d.resize(np);
    valarray<double> w(0., np);

    gsl_matrix *D[2][2];
    for (unsigned int i = 0; i < 2; i++)
        for (unsigned int j = 0; j < 2; j++)
        {
            D[i][j] = gsl_matrix_alloc(N, N);
            gsl_matrix_set_zero(D[i][j]);
        }

    gsl_matrix *c = gsl_matrix_alloc(nTaylor, np);

    for (unsigned int i = 0; i < N; i++)
    {
        for (unsigned int j = 0; j < np; j++)
        {
            xp[j][0] = uv[0][StencilMap[i][j]];
            xp[j][1] = uv[1][StencilMap[i][j]];
            xp0[0] = uv[0][i];
            xp0[1] = uv[1][i];
            d[j] = sqrt((xp[j][0] - xp0[0]) * (xp[j][0] - xp0[0]) + (xp[j][1] - xp0[1]) * (xp[j][1] - xp0[1]));
            if (d[j] != 0)
                temp.push_back(d[j]);
        }
        sort(temp.begin(), temp.end());
        double dist = accumulate(temp.begin(), temp.begin() + p + 1, 0.0) / (p + 1);
        temp.clear();
        double s = sigma * dist;
        if (Wtype == "Gaussian")
        {
            w = exp(-d * d / (s * s));
            w[w < Wmin] = Wmin;
        }
        else
            w = 1;
        int errflag = Grid::FDInterpolate2DWLS_(xp0, xp, np, p, w, dist, c);
        if (errflag != 0)
            patch->isingular.push_back(i);

        for (unsigned int m = 1; m <= 2; m++)
        {
            for (unsigned int n = 1; n <= 2; n++)
            {
                int k = (m - 1) * (p + 1) + n - 1;
                for (unsigned int j = 0; j < np; j++)
                    gsl_matrix_set(D[m - 1][n - 1], i, StencilMap[i][j], gsl_matrix_get(c, k, j));
            }
        }
    }
    //
    // Take all of the coordinate derivatives and build the normal vector and
    // the element of the surface area.
    //
    gsl_vector_view x1 = gsl_vector_view_array(x[0], N);
    gsl_vector_view x2 = gsl_vector_view_array(x[1], N);
    gsl_vector_view x3 = gsl_vector_view_array(x[2], N);

    gsl_vector *xu1 = gsl_vector_alloc(N);
    gsl_vector *xu2 = gsl_vector_alloc(N);
    gsl_vector *xu3 = gsl_vector_alloc(N);
    gsl_vector *xv1 = gsl_vector_alloc(N);
    gsl_vector *xv2 = gsl_vector_alloc(N);
    gsl_vector *xv3 = gsl_vector_alloc(N);

    gsl_blas_dgemv(CblasNoTrans, 1, D[1][0], &x1.vector, 0, xu1);
    gsl_blas_dgemv(CblasNoTrans, 1, D[1][0], &x2.vector, 0, xu2);
    gsl_blas_dgemv(CblasNoTrans, 1, D[1][0], &x3.vector, 0, xu3);
    gsl_blas_dgemv(CblasNoTrans, 1, D[0][1], &x1.vector, 0, xv1);
    gsl_blas_dgemv(CblasNoTrans, 1, D[0][1], &x2.vector, 0, xv2);
    gsl_blas_dgemv(CblasNoTrans, 1, D[0][1], &x3.vector, 0, xv3);

    gsl_vector *E = gsl_vector_alloc(N);
    gsl_vector *F = gsl_vector_alloc(N);
    gsl_vector *G = gsl_vector_alloc(N);
    gsl_vector *dsrecp = gsl_vector_alloc(N);
    for (unsigned int i = 0; i < N; i++)
    {
        vector<double> a = {gsl_vector_get(xu1, i), gsl_vector_get(xu2, i), gsl_vector_get(xu3, i)};
        vector<double> b = {gsl_vector_get(xv1, i), gsl_vector_get(xv2, i), gsl_vector_get(xv3, i)};
        double e = inner_product(begin(a), end(a), begin(a), 0.0);
        double f = inner_product(begin(a), end(a), begin(b), 0.0);
        double g = inner_product(begin(b), end(b), begin(b), 0.0);
        gsl_vector_set(E, i, e);
        gsl_vector_set(F, i, f);
        gsl_vector_set(G, i, g);
        double n1 = gsl_vector_get(xv2, i) * gsl_vector_get(xu3, i) - gsl_vector_get(xv3, i) * gsl_vector_get(xu2, i);
        double n2 = gsl_vector_get(xv3, i) * gsl_vector_get(xu1, i) - gsl_vector_get(xv1, i) * gsl_vector_get(xu3, i);
        double n3 = gsl_vector_get(xv1, i) * gsl_vector_get(xu2, i) - gsl_vector_get(xv2, i) * gsl_vector_get(xu1, i);
        gsl_matrix_set(patch->nvec, i, 0, n1);
        gsl_matrix_set(patch->nvec, i, 1, n2);
        gsl_matrix_set(patch->nvec, i, 2, n3);
        double val = sqrt(e * g - f * f);
        patch->ds(i) = val;
        gsl_vector_set(dsrecp, i, 1.0 / val);
    }
    gsl_matrix_scale_rows(patch->nvec, dsrecp);
    unsigned int nel = EtoV.getLength(0); // The number of triangles on the body.
    //
    // Set up the Gauss integration scheme.
    //
    const unsigned int nG = 6;
    vector<vector<double>> xiG = {{0.231933383, 0.1090390162}, {0.1090390162, 0.6590276008}, {0.6590276008, 0.2319333830}}; // The Gauss point coordinates on the standard triangle.
    vector<vector<double>> xiGrev = xiG;
    for (unsigned int i = 0; i < xiG.size(); i++)
        reverse(xiGrev[i].begin(), xiGrev[i].end());
    xiG.insert(xiG.end(), xiGrev.begin(), xiGrev.end());
    vector<double> wG(nG, 1. / 6); // The Gauss weights
    //
    // Build the Gaussian integration vector for this grid of triangles.
    // Initialize the integration vector and loop over elements and Gauss points.

    patch->Ivec.resize(N);
    temp.clear();
    for (unsigned int ie = 0; ie < nel; ie++)
    {
        unsigned int i = EtoV(ie, 0); // The expansion point for the WLS interpolation

        // The vertices of this triangle
        double u1[2], u2[2], u3[2];
        u1[0] = uv[0][EtoV(ie, 0)];
        u1[1] = uv[1][EtoV(ie, 0)];
        u2[0] = uv[0][EtoV(ie, 1)];
        u2[1] = uv[1][EtoV(ie, 1)];
        u3[0] = uv[0][EtoV(ie, 2)];
        u3[1] = uv[1][EtoV(ie, 2)];
        //  The Jacobian for mapping this triangle to the standard triangle.
        double Jg = abs((u2[0] - u1[0]) * (u3[1] - u1[1]) - (u3[0] - u1[0]) * (u2[1] - u1[1]));
        for (unsigned int j = 0; j < np; j++)
        {
            xp[j][0] = uv[0][StencilMap[i][j]]; // The stencil points
            xp[j][1] = uv[1][StencilMap[i][j]]; // The stencil points
        }

        vector<double> Ivec(np, 0);
        for (unsigned int iG = 0; iG < nG; iG++)
        {
            // The Gauss points in the (u,v)-space
            xp0[0] = u1[0] + xiG[iG][0] * (u2[0] - u1[0]) + xiG[iG][1] * (u3[0] - u1[0]);
            xp0[1] = u1[1] + xiG[iG][0] * (u2[1] - u1[1]) + xiG[iG][1] * (u3[1] - u1[1]);
            //
            // Set up the WLS weights.
            //
            for (unsigned int j = 0; j < np; j++)
            {
                d[j] = sqrt((xp[j][0] - xp0[0]) * (xp[j][0] - xp0[0]) + (xp[j][1] - xp0[1]) * (xp[j][1] - xp0[1]));
                if (d[j] != 0)
                    temp.push_back(d[j]);
            }
            sort(temp.begin(), temp.end());
            double dist = accumulate(temp.begin(), temp.begin() + p + 1, 0.0) / (p + 1);
            temp.clear();
            double s = sigma * dist;
            if (Wtype == "Gaussian")
            {
                w = exp(-d * d / (s * s));
                w[w < Wmin] = Wmin; // Limit the minimum value of the weight
            }
            else
                w = 1;

            // Get the coefficients

            int errflag = Grid::FDInterpolate2DWLS_(xp0, xp, np, p, w, dist, c);
            if (errflag != 0)
                patch->isingular.push_back(i);

            // Accumulate this Gauss point contribution.
            for (unsigned int j = 0; j < np; j++)
                Ivec[j] = Ivec[j] + 0.5 * wG[iG] * gsl_matrix_get(c, 0, j);
        }
        //
        // Scale with the Jacobian and add this contribution to the integration vector.
        //
        for (unsigned int j = 0; j < np; j++)
            patch->Ivec(StencilMap[i][j]) = patch->Ivec(StencilMap[i][j]) + Jg * Ivec[j];
    }

    // De-allocate

    for (unsigned int i = 0; i < 2; i++)
        for (unsigned int j = 0; j < 2; j++)
            gsl_matrix_free(D[i][j]);

    gsl_matrix_free(c);

    gsl_vector_free(xu1);
    gsl_vector_free(xu2);
    gsl_vector_free(xu3);
    gsl_vector_free(xv1);
    gsl_vector_free(xv2);
    gsl_vector_free(xv3);

    gsl_vector_free(E);
    gsl_vector_free(F);
    gsl_vector_free(G);
    gsl_vector_free(dsrecp);
}