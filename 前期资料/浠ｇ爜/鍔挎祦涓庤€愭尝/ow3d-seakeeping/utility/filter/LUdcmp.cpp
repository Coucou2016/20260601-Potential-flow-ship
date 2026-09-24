// This code implements the LU matrix decomposition.
// It has been copied from the book: "Numerical Recipes" by William H. Press et.al.

#include "LUdcmp.h"
#include <iomanip>

// constructor
LUdcmp::LUdcmp(double **a, int n)
{
  n_ = n;
  const double TINY = 1e-40;
  int i, imax, j, k;
  double big, temp;

  // allocate lu matrix
  lu_ = new double *[n_];
  for (i = 0; i < n_; i++)
  {
    lu_[i] = new double[n_];
  }
  // initialize lu matrix
  for (i = 0; i < n_; i++)
  {
    for (j = 0; j < n_; j++)
    {
      lu_[i][j] = a[i][j];
    }
  }

  // allocate indx array
  indx_ = new int[n_];

  // allocate vv array
  vv_ = new double[n_]; // vv stores the implicit scaling of each row

  d_ = 1.0; // no row interchanges yet

  for (i = 0; i < n_; i++)
  {
    big = 0.0;
    for (j = 0; j < n_; j++)
      if ((temp = abs(lu_[i][j])) > big)
        big = temp;
    if (big == 0.0)
      throw("Singular matrix in LUdcmp");
    vv_[i] = 1.0 / big;
  }
  for (k = 0; k < n_; k++)
  {
    big = 0.0;
    imax = k;
    for (i = k; i < n_; i++)
    {
      temp = vv_[i] * abs(lu_[i][k]);
      if (temp > big)
      {
        big = temp;
        imax = i;
      }
    }

    if (k != imax)
    {
      for (j = 0; j < n_; j++)
      {
        temp = lu_[imax][j];
        lu_[imax][j] = lu_[k][j];
        lu_[k][j] = temp;
      }
      d_ = -d_;
      vv_[imax] = vv_[k];
    }
    indx_[k] = imax;
    if (lu_[k][k] == 0.0)
      lu_[k][k] = TINY;

    for (i = k + 1; i < n_; i++)
    {
      temp = lu_[i][k] /= lu_[k][k];
      for (j = k + 1; j < n_; j++)
        lu_[i][j] -= temp * lu_[k][j];
    }
  }
}

void LUdcmp::solve(double *b, double *x, int p, int q)
{
  int i, ii = 0, ip, j;
  double sum;
  if (p != n_ || q != n_)
    throw("LUdcmp::solve bad sizes");
  for (i = 0; i < n_; i++)
    x[i] = b[i];
  for (i = 0; i < n_; i++)
  {
    ip = indx_[i];
    sum = x[ip];
    x[ip] = x[i];
    if (ii != 0)
      for (j = ii - 1; j < i; j++)
        sum -= lu_[i][j] * x[j];
    else if (sum != 0.0)
      ii = i + 1;
    x[i] = sum;
  }
  for (i = n_ - 1; i >= 0; i--)
  {
    sum = x[i];
    for (j = i + 1; j < n_; j++)
      sum -= lu_[i][j] * x[j];
    x[i] = sum / lu_[i][i];
  }
}

void LUdcmp::solve(double **b, double **x, int p, int q, int m, int s)
{
  int i, j;
  if (p != n_ || q != n_ || m != s)
    throw runtime_error("LUdcmp::solve bad sizes");

  double *xx = new double[n_];

  for (j = 0; j < m; j++)
  {
    for (i = 0; i < n_; i++)
      xx[i] = b[i][j];
    solve(xx, xx, n_, n_);
    for (i = 0; i < n_; i++)
      x[i][j] = xx[i];
  }
  delete[] xx;
}

void LUdcmp::inverse(double **ainv)
{
  int i, j;
  for (i = 0; i < n_; i++)
  {
    for (j = 0; j < n_; j++)
      ainv[i][j] = 0.0;
    ainv[i][i] = 1.0;
  }
  solve(ainv, ainv, n_, n_, n_, n_);
}

double LUdcmp::det()
{
  double dd = d_;
  for (int i = 0; i < n_; i++)
    dd *= lu_[i][i];
  return dd;
}

void LUdcmp::printLU()
{
  for (unsigned int i = 0; i < n_; i++)
  {
    for (unsigned int j = 0; j < n_; j++)
      cout << lu_[i][j] << setw(15);
    cout << '\n';
  }
}

LUdcmp::~LUdcmp()
{
  // deallocate lu matrix

  for (unsigned int i = 0; i < n_; i++)
  {
    delete[] lu_[i];
  }
  delete[] lu_;

  // deallocate indx array
  delete[] indx_;

  // deallocate vv array
  delete[] vv_;
}
