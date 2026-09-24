// this file implements ComplexNumbers class.

#include "gsl/gsl_complex_math.h"
#include "ComplexNumbers.h"
#include "OvertureTypes.h"

ComplexNumbers::ComplexNumbers(unsigned int length)
{
  cArray_.resize(2, length);
  cArray_ = 0.0;
}

ComplexNumbers::ComplexNumbers(const RealArray &carray)
{
  if (carray.getLength(0) > 2)
  {
    throw runtime_error("Error, ComplexNumbers::ComplexNumbers.cpp: Length along the first axis must be 2.");
  }

  cArray_ = carray;
}

ComplexNumbers::ComplexNumbers()
{

} // default constructor

void ComplexNumbers::resize(unsigned int length)
{
  cArray_.resize(2, length);
  cArray_ = 0.0;
}

// (a+ib)+(c+id) a+ib is the reciever object and c+id is the parameter

ComplexNumbers ComplexNumbers::operator+(const ComplexNumbers &rhs) const
{
  ComplexNumbers result(rhs.getLength(1));

  int base = rhs(0).getBase(1);
  int bound = rhs(0).getBound(1);
  int bs = cArray_.getBase(1);

  int j = 0;

  for (int i = base; i <= bound; i++)
  {
    gsl_complex c = gsl_complex_add(gsl_complex_rect(cArray_(0, bs + j), cArray_(1, bs + j)), gsl_complex_rect(rhs.cArray_(0, i), rhs.cArray_(1, i)));

    result.cArray_(0, j) = c.dat[0];
    result.cArray_(1, j) = c.dat[1];

    j++;
  }

  return result;
}

// (a+ib)*(c+id) a+ib is the reciever object and c+id is the parameter

ComplexNumbers ComplexNumbers::operator*(const ComplexNumbers &rhs) const
{
  ComplexNumbers result(rhs.getLength(1));

  int base = rhs(0).getBase(1);
  int bound = rhs(0).getBound(1);
  int bs = cArray_.getBase(1);

  int j = 0;

  for (int i = base; i <= bound; i++)
  {
    gsl_complex c = gsl_complex_mul(gsl_complex_rect(cArray_(0, bs + j), cArray_(1, bs + j)), gsl_complex_rect(rhs.cArray_(0, i), rhs.cArray_(1, i)));

    result.cArray_(0, j) = c.dat[0];
    result.cArray_(1, j) = c.dat[1];

    j++;
  }

  return result;
}

// (a+ib) * rhs (which is a double)

ComplexNumbers ComplexNumbers::operator*(double rhs) const
{
  ComplexNumbers result(cArray_.getLength(1));

  result.cArray_ = cArray_ * rhs;

  return result;
}

// (a+ib)/(c+id) a+ib is the reciever object and c+id is the parameter

ComplexNumbers ComplexNumbers::operator/(const ComplexNumbers &rhs) const
{
  ComplexNumbers result(rhs.getLength(1));

  int base = rhs(0).getBase(1);
  int bound = rhs(0).getBound(1);
  int bs = cArray_.getBase(1);

  int j = 0;

  for (int i = base; i <= bound; i++)
  {
    gsl_complex c = gsl_complex_div(gsl_complex_rect(cArray_(0, bs + j), cArray_(1, bs + j)), gsl_complex_rect(rhs.cArray_(0, i), rhs.cArray_(1, i)));

    result.cArray_(0, j) = c.dat[0];
    result.cArray_(1, j) = c.dat[1];

    j++;
  }

  return result;
}

// (a+ib)-(c+id) a+ib is the reciever object and c+id is the parameter

ComplexNumbers ComplexNumbers::operator-(const ComplexNumbers &rhs) const
{
  ComplexNumbers result(rhs.getLength(1));

  int base = rhs(0).getBase(1);
  int bound = rhs(0).getBound(1);
  int bs = cArray_.getBase(1);

  int j = 0;

  for (int i = base; i <= bound; i++)
  {
    gsl_complex c = gsl_complex_sub(gsl_complex_rect(cArray_(0, bs + j), cArray_(1, bs + j)), gsl_complex_rect(rhs.cArray_(0, i), rhs.cArray_(1, i)));

    result.cArray_(0, j) = c.dat[0];
    result.cArray_(1, j) = c.dat[1];

    j++;
  }

  return result;
}

void ComplexNumbers::operator=(const ComplexNumbers &rhs)
{
  if (this != &rhs)
  {
    if (rhs.getLength(0) != 2)
    {
      throw runtime_error("Error, ComplexNumbers::ComplexNumbers.cpp: The size of the RealArray in assignment operator must be 2.");
    }

    cArray_ = rhs.cArray_;
  }
}

void ComplexNumbers::operator()(Range range, double val)
{
  cArray_(0, range) = val;
  cArray_(1, range) = val;
}

void ComplexNumbers::operator()(Range range, const ComplexNumbers &rhs)
{
  Range all;

  cArray_(0, range) = rhs(0)(0, all);
  cArray_(1, range) = rhs(1)(1, all);
}

RealArray ComplexNumbers::operator()(int ri) const
{
  if (ri != 0 and ri != 1)
  {
    throw runtime_error("Error, ComplexNumbers::ComplexNumbers.cpp: The index must be 0 or 1.");
  }

  int base = cArray_.getBase(1);

  Range range(base, cArray_.getBound(1));

  return cArray_(ri, range);
}

double &ComplexNumbers::operator()(int ri, int index)
{
  if (ri != 0 and ri != 1)
  {
    throw runtime_error("Error, ComplexNumbers::ComplexNumbers.cpp: The first index must be 0 or 1.");
  }

  if (index > cArray_.getBound(1))
  {
    throw runtime_error("Error, ComplexNumbers::ComplexNumbers.cpp: The bound exceeds the limit.");
  }

  return cArray_(ri, index);
}

ComplexNumbers ComplexNumbers::operator()(Range range) const
{
  if (range.getBound() > cArray_.getBound(1))
  {
    throw runtime_error("Error, ComplexNumbers::ComplexNumbers.cpp: The bound exceeds the limit.");
  }

  Range r(0, 1);

  return ComplexNumbers(cArray_(r, range));
}

int ComplexNumbers::getLength(int axis) const
{
  return cArray_.getLength(axis);
}

void ComplexNumbers::display()
{
  cArray_.display();
}

ComplexNumbers operator*(double n, const ComplexNumbers &rhs) // n * (a+ib)
{
  ComplexNumbers result(rhs.getLength(1));

  for (int i = 0; i < rhs.getLength(1); i++)
  {
    result.cArray_(0, i) = n * rhs.cArray_(0, i);
    result.cArray_(1, i) = n * rhs.cArray_(1, i);
  }

  return result;
}
