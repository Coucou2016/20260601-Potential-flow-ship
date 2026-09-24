// This code calculates the Savitzky-Golay filter coefficients
// It has been copied from the book: "Numerical Recipes" by William H. Press et.al.

#include "OW3DUtilFunctions.h"
#include "LUdcmp.h"

void OW3DSeakeeping::Savgol(
    double *c,
    const int np,
    const int nl,
    const int nr,
    const int ld,
    const int m)
{
  int j, k, imj, ipj, kk, mm;
  double fac, sum;

  if (np < nl + nr + 1 || nl < 0 || nr < 0 || ld > m || nl + nr < m)
    throw runtime_error("bad args in savgol");

  double **a = new double *[m + 1];
  for (int i = 0; i < m + 1; i++)
    a[i] = new double[m + 1];

  double *b = new double[m + 1];

  for (ipj = 0; ipj <= (m << 1); ipj++)
  {
    sum = (ipj ? 0.0 : 1.0);
    for (k = 1; k <= nr; k++)
      sum += pow(double(k), double(ipj));
    for (k = 1; k <= nl; k++)
      sum += pow(double(-k), double(ipj));
    mm = min(ipj, 2 * m - ipj);
    for (imj = -mm; imj <= mm; imj += 2)
      a[(ipj + imj) / 2][(ipj - imj) / 2] = sum;
  }

  LUdcmp alud(a, m + 1);
  for (j = 0; j < m + 1; j++)
    b[j] = 0.0;
  b[ld] = 1.0;
  alud.solve(b, b, m + 1, m + 1);

  for (kk = 0; kk < np; kk++)
    c[kk] = 0.0;
  for (k = -nl; k <= nr; k++)
  {
    sum = b[0];
    fac = 1.0;
    for (mm = 1; mm <= m; mm++)
      sum += b[mm] * (fac *= k);
    kk = (np - k) % np;
    c[kk] = sum;
  }

  //  change the wrap-around order
  double C[np];
  for (int i = 0; i < np; i++)
    C[i] = c[i];
  int h = 0;
  for (int i = 0; i < np; i++)
  {
    if (i <= nl)
      C[i] = c[nl - i];
    else
    {
      C[i] = c[nl + nr - h];
      h++;
    }
  }

  for (int i = 0; i < np; i++)
    c[i] = C[i];

  // de-allocate the memory
  for (int i = 0; i < m + 1; i++)
    delete[] a[i];
  delete[] a;
  delete[] b;
}
