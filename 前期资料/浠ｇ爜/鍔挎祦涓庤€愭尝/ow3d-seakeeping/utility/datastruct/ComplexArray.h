// This file imports the data objects and the member functions
// for the ComplexArray class. This class is designed to facilitate the operations
// on the complex numbers defined over the grid points of the body surface. For each exciting
// surface there is defined two VRealArrays to store the real and imaginary part. The size
// of the ComplexArray matches the size of these VRealArrays. Since the whole body surface may have
// more than one exciting surface, we need a vector of real arrays to store all real and imaginary part
// on the body surface.
// The constructor takes "boundaries data" as the only argument, and a ComplexArray
// is built based on the size of the each exciting surface.

#ifndef __COMPLEX__ARRAY__
#define __COMPLEX__ARRAY__


#include "VRealArrays.h"
#include "Faddeeva.h"

class ComplexArray
{
public:
  // member functions

  ComplexArray();
  ComplexArray(const OW3DSeakeeping::All_boundaries_data &);
  void resize(const OW3DSeakeeping::All_boundaries_data &);
  void display(unsigned int);

  // operators

  VRealArrays &operator()(int);
  ComplexArray operator-() const;

  ComplexArray operator*(double) const;
  ComplexArray operator*(gsl_complex) const;
  ComplexArray operator/(double) const;
  ComplexArray operator/(gsl_complex) const;
  ComplexArray operator+(double) const;
  ComplexArray operator+(gsl_complex) const;
  ComplexArray operator-(double) const;
  ComplexArray operator-(gsl_complex) const;

  ComplexArray operator*(const ComplexArray &) const;
  ComplexArray operator/(const ComplexArray &) const;
  ComplexArray operator+(const ComplexArray &) const;
  ComplexArray operator-(const ComplexArray &) const;

  friend ComplexArray operator*(gsl_complex, const ComplexArray &);
  friend ComplexArray operator/(gsl_complex, const ComplexArray &);
  friend ComplexArray operator/(double, const ComplexArray &);
  friend ComplexArray operator*(double, const ComplexArray &);
  friend ComplexArray exp(const ComplexArray &);
  friend ComplexArray sqrt(const ComplexArray &);
  friend ComplexArray comperrf(const ComplexArray &);

private:
  VRealArrays real_;
  VRealArrays imag_;
};

#endif
