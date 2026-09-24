// This header file exports the data objects and
// the member functions of the LUdcmp class

#include "OW3DUtilFunctions.h"

#ifndef __LUdcmp_H__
#define __LUdcmp_H__

class LUdcmp
{
private:
  // data objects
  int n_;
  double **lu_; //stores the decomposition
  int *indx_;   //stores the permutation
  double *vv_;
  double d_;

public:
  LUdcmp(double **a, int n);                                      // constructor
  void solve(double *b, double *x, int p, int q);                 // solves the set of n linear equations A.x=b,(p and q: number of rows in b and x)
  void solve(double **b, double **x, int p, int q, int m, int s); // solves m  sets of n linear equations A.x=b,(m and s: number of columns in b and x)
  void inverse(double **ainv);
  double det();
  void printLU();
  ~LUdcmp(); // destructor
};

#endif
