// This file contains the implementation of the non-linear least squre fitting
// based on the code from pp 464-466, GNU Scientific Libray-Reference Manual.
// the results of the fitting will be written in the file "lstsqr.txt" in the
// results directory

#include "gsl/gsl_multifit_nlin.h"
#include "gsl/gsl_blas.h"
#include "OW3DUtilFunctions.h"
#include "OW3DConstants.h"
#include <iomanip>

void print_state(size_t iter, gsl_multifit_fdfsolver *s, size_t size, ofstream &fout)
{
  fout << "iter: " << iter << ", x=";
  for (unsigned int i = 0; i < size; i++)
  {
    fout << gsl_vector_get(s->x, i) << " ";
  }
  fout << setw(8) << "|f(x)|=" << gsl_blas_dnrm2(s->f) << '\n';
}

void OW3DSeakeeping::leastSquareFitting(
    int (*pf)(const gsl_vector *, void *, gsl_vector *),
    int (*pdf)(const gsl_vector *, void *, gsl_matrix *),
    int (*pfdf)(const gsl_vector *, void *, gsl_vector *, gsl_matrix *),
    least_square_data d,
    vector<double> &fits,
    string filename)
{
  ofstream fout;
  if (OW3DSeakeeping::long_print)
  {
    fout.open(filename, ios_base::out | ios_base::app); // output results to this file
    fout.setf(ios_base::fixed);
    fout << setw(8) << "fitting starts at : " << d.tm << '\n';
  }

  const gsl_multifit_fdfsolver_type *T;
  gsl_multifit_fdfsolver *s;
  int status;
  unsigned int iter = 0;
  const size_t n = d.size;
  const size_t p = d.p;

  gsl_matrix *covar = gsl_matrix_alloc(p, p);
  gsl_multifit_function_fdf f;
  gsl_vector_view x = gsl_vector_view_array(d.x_init, p);

  f.f = pf;     // pointer to the model function
  f.df = pdf;   // pointer to the derivative of the model function
  f.fdf = pfdf; // pointer to both
  f.n = n;
  f.p = p;
  f.params = &d;

  T = gsl_multifit_fdfsolver_lmsder;
  s = gsl_multifit_fdfsolver_alloc(T, n, p);
  gsl_multifit_fdfsolver_set(s, &f, &x.vector);
  if (OW3DSeakeeping::long_print)
    print_state(iter, s, p, fout);

  do
  {
    iter++;
    status = gsl_multifit_fdfsolver_iterate(s);
    if (OW3DSeakeeping::long_print)
      fout << "status =" << gsl_strerror(status) << '\n';
    if (OW3DSeakeeping::long_print)
      print_state(iter, s, p, fout);

    if (status)
      break;

    status = gsl_multifit_test_delta(s->dx, s->x, 1e-4, 1e-4);
  } while (status == GSL_CONTINUE && iter < 1000);

  gsl_matrix *J = gsl_matrix_alloc(n, p);
  gsl_multifit_fdfsolver_jac(s, J);
  gsl_multifit_covar(J, 0.0, covar);

#define FIT(i) gsl_vector_get(s->x, i)
#define ERR(i) sqrt(gsl_matrix_get(covar, i, i))

  {
    double chi = gsl_blas_dnrm2(s->f);
    double dof = n - p;
    double c = GSL_MAX_DBL(1, chi / sqrt(dof));
    if (OW3DSeakeeping::long_print)
      fout << "chisq/dof = " << pow(chi, 2.0) / dof << '\n';

    for (unsigned int l = 0; l < p; l++)
    {
      if (OW3DSeakeeping::long_print)
        fout << "c_" << l << " = " << FIT(l) << " +/- " << c * ERR(l) << '\n';
      fits[l] = FIT(l);
    }
  }
  if (OW3DSeakeeping::long_print)
    fout << "status = " << gsl_strerror(status) << "\n\n";

  gsl_multifit_fdfsolver_free(s);
  gsl_matrix_free(covar);
}
