// This file contains the implementation of the ComplexArray class.

#include "gsl/gsl_complex_math.h"
#include "ComplexArray.h"

ComplexArray::ComplexArray()
{
}

ComplexArray::ComplexArray(const OW3DSeakeeping::All_boundaries_data &boundariesData)
{
  real_.allresize(boundariesData);
  imag_.allresize(boundariesData);
}

void ComplexArray::resize(const OW3DSeakeeping::All_boundaries_data &boundariesData)
{
  real_.allresize(boundariesData);
  imag_.allresize(boundariesData);
}

void ComplexArray::display(unsigned int surface)
{
  real_.display(surface);
  imag_.display(surface);
}

// ComplexArray()
VRealArrays &ComplexArray::operator()(int reim)
{
  if (reim != 0 and reim != 1)
    throw runtime_error("Error, ComplexArray::ComplexArray.cpp: The index in () operator must be 0 or 1.");

  if (reim == 0)
    return real_;
  else
    return imag_;
}

// -ComplexArray
ComplexArray ComplexArray::operator-() const
{
  ComplexArray result;
  result.real_ = -real_;
  result.imag_ = -imag_;
  return result;
}

// ComplexArray*a
ComplexArray ComplexArray::operator*(double a) const
{
  ComplexArray result;
  result.real_ = a * real_;
  result.imag_ = a * imag_;
  return result;
}

// ComplexArray*(a+ib)
ComplexArray ComplexArray::operator*(gsl_complex c) const
{
  ComplexArray result;
  result.real_ = c.dat[0] * real_ - c.dat[1] * imag_;
  result.imag_ = c.dat[0] * imag_ + c.dat[1] * real_;
  return result;
}

// ComplexArray/a
ComplexArray ComplexArray::operator/(double a) const
{
  ComplexArray result;
  result.real_ = real_ / a;
  result.imag_ = imag_ / a;
  return result;
}

// ComplexArray/(a+ib)
ComplexArray ComplexArray::operator/(gsl_complex c) const
{
  ComplexArray result;
  result.real_ = (real_ * c.dat[0] + imag_ * c.dat[1]) / (pow(c.dat[0], 2) + pow(c.dat[1], 2));
  result.imag_ = -(real_ * c.dat[1] - imag_ * c.dat[0]) / (pow(c.dat[0], 2) + pow(c.dat[1], 2));
  return result;
}

// ComplexArray+a
ComplexArray ComplexArray::operator+(double a) const
{
  ComplexArray result;
  result.real_ = real_ + a;
  result.imag_ = imag_;
  return result;
}

// ComplexArray + (a+ib)
ComplexArray ComplexArray::operator+(gsl_complex c) const
{
  ComplexArray result;
  result.real_ = real_ + c.dat[0];
  result.imag_ = imag_ + c.dat[1];
  return result;
}

// ComplexArray - a
ComplexArray ComplexArray::operator-(double a) const
{
  ComplexArray result;
  result.real_ = real_ - a;
  result.imag_ = imag_;
  return result;
}

// CommplexArray - (a+ib)
ComplexArray ComplexArray::operator-(gsl_complex c) const
{
  ComplexArray result;
  result.real_ = real_ - c.dat[0];
  result.imag_ = imag_ - c.dat[1];
  return result;
}

// ComplexArray * ComplexArray  (a+ib) * (c+id) = (ac-bd) + i (ad+bc);
ComplexArray ComplexArray::operator*(const ComplexArray &rhs) const
{
  ComplexArray result;
  result.real_ = real_ * rhs.real_ - imag_ * rhs.imag_;
  result.imag_ = real_ * rhs.imag_ + imag_ * rhs.real_;
  return result;
}

// ComplexArray / ComplexArray
ComplexArray ComplexArray::operator/(const ComplexArray &rhs) const
{
  ComplexArray result;
  result.real_ = (real_ * rhs.real_ + imag_ * rhs.imag_) / (pow(rhs.real_, 2) + pow(rhs.imag_, 2));
  result.imag_ = -(real_ * rhs.imag_ - imag_ * rhs.real_) / (pow(rhs.real_, 2) + pow(rhs.imag_, 2));
  return result;
}

// ComplexArray + ComplexArray
ComplexArray ComplexArray::operator+(const ComplexArray &rhs) const
{
  ComplexArray result;
  result.real_ = real_ + rhs.real_;
  result.imag_ = imag_ + rhs.imag_;
  return result;
}

// ComplexArray - ComplexArray
ComplexArray ComplexArray::operator-(const ComplexArray &rhs) const
{
  ComplexArray result;
  result.real_ = real_ - rhs.real_;
  result.imag_ = imag_ - rhs.imag_;
  return result;
}

// (a+ib) * ComplexArray
ComplexArray operator*(gsl_complex c, const ComplexArray &rhs)
{
  ComplexArray result;
  result.real_ = c.dat[0] * rhs.real_ - c.dat[1] * rhs.imag_;
  result.imag_ = c.dat[0] * rhs.imag_ + c.dat[1] * rhs.real_;
  return result;
}

// (a+ib) / ComplexArray
ComplexArray operator/(gsl_complex c, const ComplexArray &rhs)
{
  ComplexArray result;
  result.real_ = (c.dat[0] * rhs.real_ + c.dat[1] * rhs.imag_) / (pow(rhs.real_, 2) + pow(rhs.imag_, 2));
  result.imag_ = -(c.dat[0] * rhs.imag_ - c.dat[1] * rhs.real_) / (pow(rhs.real_, 2) + pow(rhs.imag_, 2));
  return result;
}

// a / ComplexArray
ComplexArray operator/(double a, const ComplexArray &rhs)
{
  ComplexArray result;
  result.real_ = a * rhs.real_ / (pow(rhs.real_, 2) + pow(rhs.imag_, 2));
  result.imag_ = -a * rhs.imag_ / (pow(rhs.real_, 2) + pow(rhs.imag_, 2));
  return result;
}

// a * ComplexArray
ComplexArray operator*(double a, const ComplexArray &rhs)
{
  ComplexArray result;
  result.real_ = a * rhs.real_;
  result.imag_ = a * rhs.imag_;
  return result;
}

// sqrt(ComplexArray)
ComplexArray sqrt(const ComplexArray &A)
{
  ComplexArray result;
  int tos = A.real_.getsize();
  result.real_.resize(tos);
  result.imag_.resize(tos);

  for (int surface = 0; surface < tos; surface++)
  {
    int li = A.real_[surface].getLength(0);
    int lj = A.real_[surface].getLength(1);
    int lk = A.real_[surface].getLength(2);

    result.real_[surface].resize(li, lj, lk);
    result.imag_[surface].resize(li, lj, lk);

    for (int i = 0; i < li; i++)
    {
      for (int j = 0; j < lj; j++)
      {
        for (int k = 0; k < lk; k++)
        {
          gsl_complex c = gsl_complex_sqrt(gsl_complex_rect(A.real_[surface](i, j, k), A.imag_[surface](i, j, k)));

          result.real_[surface](i, j, k) = c.dat[0];
          result.imag_[surface](i, j, k) = c.dat[1];
        }
      }
    }
  }

  return result;
}

// comperrf(ComplexArray)
ComplexArray comperrf(const ComplexArray &A)
{
  ComplexArray result;
  int tos = A.real_.getsize();
  result.real_.resize(tos);
  result.imag_.resize(tos);

  for (int surface = 0; surface < tos; surface++)
  {
    int li = A.real_[surface].getLength(0);
    int lj = A.real_[surface].getLength(1);
    int lk = A.real_[surface].getLength(2);

    result.real_[surface].resize(li, lj, lk);
    result.imag_[surface].resize(li, lj, lk);

    for (int i = 0; i < li; i++)
    {
      for (int j = 0; j < lj; j++)
      {
        for (int k = 0; k < lk; k++)
        {
          // comperrf(A.real_[surface](i,j,k), A.imag_[surface](i,j,k), result.real_[surface](i,j,k),result.imag_[surface](i,j,k) );
          std::complex<double> z(A.real_[surface](i, j, k), A.imag_[surface](i, j, k));
          std::complex<double> res = Faddeeva::w(z, 0);
          result.real_[surface](i, j, k) = res.real();
          result.imag_[surface](i, j, k) = res.imag();
        }
      }
    }
  }

  return result;
}

ComplexArray exp(const ComplexArray &A)
{
  ComplexArray result;
  int tos = A.real_.getsize();
  result.real_.resize(tos);
  result.imag_.resize(tos);

  for (int surface = 0; surface < tos; surface++)
  {
    int li = A.real_[surface].getLength(0);
    int lj = A.real_[surface].getLength(1);
    int lk = A.real_[surface].getLength(2);

    result.real_[surface].resize(li, lj, lk);
    result.imag_[surface].resize(li, lj, lk);

    for (int i = 0; i < li; i++)
    {
      for (int j = 0; j < lj; j++)
      {
        for (int k = 0; k < lk; k++)
        {
          gsl_complex c = gsl_complex_exp(gsl_complex_rect(A.real_[surface](i, j, k), A.imag_[surface](i, j, k)));

          result.real_[surface](i, j, k) = c.dat[0];
          result.imag_[surface](i, j, k) = c.dat[1];
        }
      }
    }
  }

  return result;
}
