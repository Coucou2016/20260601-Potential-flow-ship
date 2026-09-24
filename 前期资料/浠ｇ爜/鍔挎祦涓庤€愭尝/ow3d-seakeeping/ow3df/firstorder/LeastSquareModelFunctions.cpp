// This file contains the model functions and their derivatives for
// least squre fitting. New models can be easily added here.
// The implementation is based on the code from pp 462-463, GNU Scientific Libray-Reference Manual.

#include "OW3DUtilFunctions.h"

// ------------------------------------------------------------------------
//
// **** model no. 1 : 1/t^n * ( a1*sin(omegac*t) + a2*cos(omegac*t) ) *****
//
// ------------------------------------------------------------------------

int OW3DSeakeeping::t_n_sine_cosine_f(const gsl_vector *x, void *data, gsl_vector *f)
{
  size_t size = ((least_square_data *)data)->size;
  double *y = ((least_square_data *)data)->y;
  double *sigma = ((least_square_data *)data)->sigma;
  double omegac = ((least_square_data *)data)->omegac;
  double dt = ((least_square_data *)data)->dt;
  double tm = ((least_square_data *)data)->tm;
  double n = ((least_square_data *)data)->n;

  double a = gsl_vector_get(x, 0);
  double b = gsl_vector_get(x, 1);

  size_t i;

  for (i = 0; i < size; i++)
  {
    // model Yi = 1/t * ( a*sin(omegac*t) + b*cos(omegac*t) )
    double t = i * dt + tm;
    double Yi = 1.0 / pow(t, n) * (a * sin(omegac * t) + b * cos(omegac * t));
    gsl_vector_set(f, i, (Yi - y[i]) / sigma[i]);
  }

  return GSL_SUCCESS;
}

int OW3DSeakeeping::t_n_sine_cosine_df(const gsl_vector *x, void *data, gsl_matrix *J)
{
  size_t size = ((least_square_data *)data)->size;
  double *sigma = ((least_square_data *)data)->sigma;
  double omegac = ((least_square_data *)data)->omegac;
  double dt = ((least_square_data *)data)->dt;
  double tm = ((least_square_data *)data)->tm;
  double n = ((least_square_data *)data)->n;

  size_t i;

  for (i = 0; i < size; i++)
  {
    // Jacobian matrix J(i,j) = dfi/dxj,
    // where fi = (Yi-yi)/sigma[i],
    //       Yi = 1/t * ( a*sin(omegac*t) + b*cos(omegac*t) ),
    // and the xj are the parameters (a,b)
    double t = i * dt + tm;
    double s = sigma[i];
    gsl_matrix_set(J, i, 0, sin(omegac * t) / (pow(t, n) * s));
    gsl_matrix_set(J, i, 1, cos(omegac * t) / (pow(t, n) * s));
  }

  return GSL_SUCCESS;
}

int OW3DSeakeeping::t_n_sine_cosine_fdf(const gsl_vector *x, void *data, gsl_vector *f, gsl_matrix *J)
{
  t_n_sine_cosine_f(x, data, f);
  t_n_sine_cosine_df(x, data, J);

  return GSL_SUCCESS;
}

// ----------------------------------------------------------------------------
//
// **** model no. 2 : 1/t^n * ( a1*sin(omegac*t) + a2*cos(omegac*t) ) + b *****
//
// ----------------------------------------------------------------------------

int OW3DSeakeeping::t_n_sine_cosine_pc_f(const gsl_vector *x, void *data, gsl_vector *f)
{
  size_t size = ((least_square_data *)data)->size;
  double *y = ((least_square_data *)data)->y;
  double *sigma = ((least_square_data *)data)->sigma;
  double omegac = ((least_square_data *)data)->omegac;
  double dt = ((least_square_data *)data)->dt;
  double tm = ((least_square_data *)data)->tm;
  double n = ((least_square_data *)data)->n;

  double a = gsl_vector_get(x, 0);
  double b = gsl_vector_get(x, 1);
  double c = gsl_vector_get(x, 2);

  size_t i;

  for (i = 0; i < size; i++)
  {
    // model Yi = 1/t * ( a*sin(omegac*t) + b*cos(omegac*t) ) + c
    double t = i * dt + tm;
    double Yi = 1.0 / pow(t, n) * (a * sin(omegac * t) + b * cos(omegac * t)) + c;
    gsl_vector_set(f, i, (Yi - y[i]) / sigma[i]);
  }

  return GSL_SUCCESS;
}

int OW3DSeakeeping::t_n_sine_cosine_pc_df(const gsl_vector *x, void *data, gsl_matrix *J)
{
  size_t size = ((least_square_data *)data)->size;
  double *sigma = ((least_square_data *)data)->sigma;
  double omegac = ((least_square_data *)data)->omegac;
  double dt = ((least_square_data *)data)->dt;
  double tm = ((least_square_data *)data)->tm;
  double n = ((least_square_data *)data)->n;

  size_t i;

  for (i = 0; i < size; i++)
  {
    // Jacobian matrix J(i,j) = dfi/dxj,
    // where fi = (Yi-yi)/sigma[i],
    //       Yi = 1/t * ( a*sin(omegac*t) + b*cos(omegac*t) ) + c,
    // and the xj are the parameters (a,b,c)

    double t = i * dt + tm;
    double s = sigma[i];

    gsl_matrix_set(J, i, 0, sin(omegac * t) / (pow(t, n) * s));
    gsl_matrix_set(J, i, 1, cos(omegac * t) / (pow(t, n) * s));
    gsl_matrix_set(J, i, 2, 1 / s);
  }

  return GSL_SUCCESS;
}

int OW3DSeakeeping::t_n_sine_cosine_pc_fdf(const gsl_vector *x, void *data, gsl_vector *f, gsl_matrix *J)
{
  t_n_sine_cosine_f(x, data, f);
  t_n_sine_cosine_df(x, data, J);

  return GSL_SUCCESS;
}

// -------------------------------------------------
//
// **** model no. 3 :  A * exp(-lambda *i) + b *****
//
// -------------------------------------------------

int OW3DSeakeeping::expb_f(const gsl_vector *x, void *data, gsl_vector *f)
{
  size_t size = ((least_square_data *)data)->size;
  double *y = ((least_square_data *)data)->y;
  double *sigma = ((least_square_data *)data)->sigma;

  double A = gsl_vector_get(x, 0);
  double lambda = gsl_vector_get(x, 1);
  double b = gsl_vector_get(x, 2);

  size_t i;

  for (i = 0; i < size; i++)
  {
    // model Yi = A * exp(-lambda * i) + b
    double t = i;
    double Yi = A * exp(-lambda * t) + b;
    gsl_vector_set(f, i, (Yi - y[i]) / sigma[i]);
  }

  return GSL_SUCCESS;
}

int OW3DSeakeeping::expb_df(const gsl_vector *x, void *data, gsl_matrix *J)
{
  size_t size = ((least_square_data *)data)->size;
  double *sigma = ((least_square_data *)data)->sigma;

  double A = gsl_vector_get(x, 0);
  double lambda = gsl_vector_get(x, 1);

  size_t i;

  for (i = 0; i < size; i++)
  {
    // Jacobina matrix  J(i,j) = dfi/dxj,
    // where fi = (Yi- yi)/sigma[i],
    // Yi = A *exp(-lambda * t) + b;
    // and  the xj are the parameters (A,lambda,b)

    double t = i;
    double s = sigma[i];
    double e = exp(-lambda * t);
    gsl_matrix_set(J, i, 0, e / s);
    gsl_matrix_set(J, i, 1, -t * A * e / s);
    gsl_matrix_set(J, i, 2, 1. / s);
  }

  return GSL_SUCCESS;
}

int OW3DSeakeeping::expb_fdf(const gsl_vector *x, void *data, gsl_vector *f, gsl_matrix *J)
{
  expb_f(x, data, f);
  expb_df(x, data, J);

  return GSL_SUCCESS;
}
