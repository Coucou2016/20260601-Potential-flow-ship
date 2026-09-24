// this file exports the data objects and member functions for
// the VRealArrays class. The class is used to do vector
// operations on Overture real arrays.

#ifndef __VREAL_ARRAYS__
#define __VREAL_ARRAYS__

#include "OW3DUtilTypes.h"

class VRealArrays
{
public:
  // member functions

  VRealArrays();
  VRealArrays(const OW3DSeakeeping::All_boundaries_data &);
  void allresize(const OW3DSeakeeping::All_boundaries_data &); // resize the vector and the RealArray at the same time.
  void resize(unsigned int);                                   // resizes the vector
  void display(unsigned int) const;                            // displays the desired element of the VRealArrays
  int getsize() const;                                         // gives the size of the vector

  // operators

  RealArray &operator[](unsigned int);             // used to assign value
  const RealArray &operator[](unsigned int) const; // we need const reference, as this operator is not used for assignment. The calling object must also remain const.
  VRealArrays operator-() const;

  VRealArrays operator*(const VRealArrays &) const;
  VRealArrays operator+(const VRealArrays &) const;
  VRealArrays operator-(const VRealArrays &) const;
  VRealArrays operator/(const VRealArrays &) const;

  VRealArrays operator*(double) const;
  VRealArrays operator+(double) const;
  VRealArrays operator-(double) const;
  VRealArrays operator/(double) const;

  friend VRealArrays operator*(double, const VRealArrays &);
  friend VRealArrays operator+(double, const VRealArrays &);
  friend VRealArrays operator-(double, const VRealArrays &);
  friend VRealArrays operator/(double, const VRealArrays &);

  friend VRealArrays pow(const VRealArrays &, double);
  friend VRealArrays cosh(const VRealArrays &);
  friend VRealArrays sinh(const VRealArrays &);
  friend VRealArrays sin(const VRealArrays &);
  friend VRealArrays cos(const VRealArrays &);
  friend VRealArrays exp(const VRealArrays &);

private:
  vector<RealArray> data_;
};

#endif
