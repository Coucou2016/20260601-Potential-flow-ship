// This file imports the data objects and member functions for ComplexNumbers
// class. The class uses a RealArray as the underlying data structure, in the sence that the
// RealArray has a length of 2 along axis 0, and contains the real and
// imaginary parts respectively. But the second axis of the RealArray has just
// the desired length.
//
// a ComplexNumbers:
//
//                real    imag
// axis 0 ---> :  ( 0)    ( 1)
//
// axis 1 ( 0)      o       o
// axis 1 ( 1)      o       o
// axis 1 ( 2)      o       o
// axis 1 ( 3)      o       o
// axis 1 ( 4)      o       o
// axis 1 ( 5)      o       o
// ...
// ...
//
// Note : There are 2 "non-dafault" constructors. The one that takes an unsigned int argument
// as the size of the complex array, initializes all real and imaginary parts to zero.
// The other constructor takes a RealArray, and copies the elements of the real array
// to the complex array.

#ifndef __COMPELEX__NUMBERS__
#define __COMPELEX__NUMBERS__


#include "OvertureTypes.h"

class ComplexNumbers
{
public:
  ComplexNumbers(unsigned int);
  ComplexNumbers(const RealArray &);
  ComplexNumbers();

  int getLength(int) const;
  void resize(unsigned int);
  void display();

  void operator=(const ComplexNumbers &);
  ComplexNumbers operator+(const ComplexNumbers &) const;
  ComplexNumbers operator-(const ComplexNumbers &) const;
  ComplexNumbers operator*(const ComplexNumbers &) const;
  ComplexNumbers operator*(double) const;
  ComplexNumbers operator/(const ComplexNumbers &) const;
  RealArray operator()(int) const;                         // Returns just the real or the imaginary part as a RealArray
  double &operator()(int, int);                            // First index is for the real or imaginary, and the second is the desired index.
  ComplexNumbers operator()(Range) const;                  // Returns the data in the desired range.
  void operator()(Range range, double value);              // The real and imaginary parts in the range will take the value.
  void operator()(Range range, const ComplexNumbers &rhs); // The real and imaginary parts in the range will take the value of rhs. Must be used instead of ComplexNumber_1(range) = ComplexNumber_2(range), so
                                                           // instead use CompelxNumber_1( range, CompelxNumber_2). This problem should be fixed in this class.

  friend ComplexNumbers operator*(double, const ComplexNumbers &);

private:
  RealArray cArray_;
};

#endif
