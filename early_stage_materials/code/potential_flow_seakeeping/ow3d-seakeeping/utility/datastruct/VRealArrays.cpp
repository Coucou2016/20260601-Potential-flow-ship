// This file contains implementation of the VRealArray class.

#include "VRealArrays.h"

VRealArrays::VRealArrays()
{
}

VRealArrays::VRealArrays(const OW3DSeakeeping::All_boundaries_data &boundariesData)
{
  unsigned int tos = boundariesData.exciting.size();

  data_.resize(tos);

  for (unsigned int surface = 0; surface < tos; ++surface)
  {
    const OW3DSeakeeping::Single_boundary_data &be = boundariesData.exciting[surface];
    const vector<Index> &Is = be.surface_indices;
    data_[surface].resize(Is[0].getLength(), Is[1].getLength(), Is[2].getLength());
    data_[surface].resize(Is[0].getLength(), Is[1].getLength(), Is[2].getLength());
    data_[surface] = 0.0;
  }
}

void VRealArrays::allresize(const OW3DSeakeeping::All_boundaries_data &boundariesData)
{
  unsigned int tos = boundariesData.exciting.size();

  data_.resize(tos);

  for (unsigned int surface = 0; surface < tos; ++surface)
  {
    const OW3DSeakeeping::Single_boundary_data &be = boundariesData.exciting[surface];
    const vector<Index> &Is = be.surface_indices;
    data_[surface].resize(Is[0].getLength(), Is[1].getLength(), Is[2].getLength());
    data_[surface].resize(Is[0].getLength(), Is[1].getLength(), Is[2].getLength());
    data_[surface] = 0.0;
  }
}

void VRealArrays::resize(unsigned int s)
{
  data_.resize(s);
}

void VRealArrays::display(unsigned int index) const
{
  data_[index].display();
}

int VRealArrays::getsize() const
{
  return data_.size();
}

// VRealArrays[]

RealArray &VRealArrays::operator[](unsigned int index)
{
  if (index > data_.size())
    throw runtime_error("Error, VRealArrays:VRealArray.cpp: Out of bound index in () operator");
  else
    return data_[index];
}

// VRealArrays[] const

const RealArray &VRealArrays::operator[](unsigned int index) const
{
  if (index > data_.size())
    throw runtime_error("Error, VRealArrays:VRealArray.cpp: Out of bound index in () operator");
  else
    return data_[index];
}

// - VRealArrays

VRealArrays VRealArrays::operator-() const
{
  VRealArrays result;
  result.data_.resize(data_.size());

  for (unsigned int i = 0; i < data_.size(); i++)
    result.data_[i] = -data_[i];

  return result;
}

// VRealArrays * VRealArrays

VRealArrays VRealArrays::operator*(const VRealArrays &rhs) const
{
  VRealArrays result;
  result.data_.resize(data_.size());

  for (unsigned int i = 0; i < data_.size(); i++)
    result.data_[i] = data_[i] * rhs.data_[i];

  return result;
}

// VRealArrays + VRealArrays
VRealArrays VRealArrays::operator+(const VRealArrays &rhs) const
{
  VRealArrays result;
  result.data_.resize(data_.size());

  for (unsigned int i = 0; i < data_.size(); i++)
    result.data_[i] = data_[i] + rhs.data_[i];

  return result;
}

// VRealArrays - VRealArrays

VRealArrays VRealArrays::operator-(const VRealArrays &rhs) const
{
  VRealArrays result;
  result.data_.resize(data_.size());

  for (unsigned int i = 0; i < data_.size(); i++)
    result.data_[i] = data_[i] - rhs.data_[i];

  return result;
}

// VRealArrays / VRealArrays

VRealArrays VRealArrays::operator/(const VRealArrays &rhs) const
{
  VRealArrays result;
  result.data_.resize(rhs.data_.size());

  for (unsigned int i = 0; i < rhs.data_.size(); i++)
    result.data_[i] = data_[i] / rhs.data_[i];

  return result;
}

// VRealArrays * c

VRealArrays VRealArrays::operator*(double c) const
{
  VRealArrays result;
  result.data_.resize(data_.size());

  for (unsigned int i = 0; i < data_.size(); i++)
    result.data_[i] = data_[i] * c;

  return result;
}

// VRealArrays + c

VRealArrays VRealArrays::operator+(double c) const
{
  VRealArrays result;
  result.data_.resize(data_.size());

  for (unsigned int i = 0; i < data_.size(); i++)
    result.data_[i] = data_[i] + c;

  return result;
}

// VRealArrays - c
VRealArrays VRealArrays::operator-(double c) const
{
  VRealArrays result;
  result.data_.resize(data_.size());

  for (unsigned int i = 0; i < data_.size(); i++)
    result.data_[i] = data_[i] - c;

  return result;
}

// VRealArrays / c

VRealArrays VRealArrays::operator/(double c) const
{
  VRealArrays result;
  result.data_.resize(data_.size());

  for (unsigned int i = 0; i < data_.size(); i++)
    result.data_[i] = data_[i] / c;

  return result;
}

// c * VRealArrays

VRealArrays operator*(double c, const VRealArrays &rhs)
{
  VRealArrays result;
  result.data_.resize(rhs.data_.size());

  for (unsigned int i = 0; i < rhs.data_.size(); i++)
    result.data_[i] = c * rhs.data_[i];

  return result;
}

// c + VRealArrays
VRealArrays operator+(double c, const VRealArrays &rhs)
{
  VRealArrays result;
  result.data_.resize(rhs.data_.size());

  for (unsigned int i = 0; i < rhs.data_.size(); i++)
    result.data_[i] = c + rhs.data_[i];

  return result;
}

// c - VRealArrays

VRealArrays operator-(double c, const VRealArrays &rhs)
{
  VRealArrays result;
  result.data_.resize(rhs.data_.size());

  for (unsigned int i = 0; i < rhs.data_.size(); i++)
    result.data_[i] = c - rhs.data_[i];

  return result;
}

// c / VRealArrays

VRealArrays operator/(double c, const VRealArrays &rhs)
{
  VRealArrays result;
  result.data_.resize(rhs.data_.size());

  for (unsigned int i = 0; i < rhs.data_.size(); i++)
    result.data_[i] = c / rhs.data_[i];

  return result;
}

// pow(VRealArrays,c)

VRealArrays pow(const VRealArrays &vrs, double c)
{
  VRealArrays result;
  result.data_.resize(vrs.data_.size());

  for (unsigned int i = 0; i < vrs.data_.size(); i++)
    result.data_[i] = pow(vrs.data_[i], c);

  return result;
}

// cosh(VRealArrays)

VRealArrays cosh(const VRealArrays &vrs)
{
  VRealArrays result;
  result.data_.resize(vrs.data_.size());

  for (unsigned int i = 0; i < vrs.data_.size(); i++)
    result.data_[i] = cosh(vrs.data_[i]);

  return result;
}

// sinh(VRealArrays)

VRealArrays sinh(const VRealArrays &vrs)
{
  VRealArrays result;
  result.data_.resize(vrs.data_.size());

  for (unsigned int i = 0; i < vrs.data_.size(); i++)
    result.data_[i] = sinh(vrs.data_[i]);

  return result;
}

// sin(VRealArrays)

VRealArrays sin(const VRealArrays &vrs)
{
  VRealArrays result;
  result.data_.resize(vrs.data_.size());

  for (unsigned int i = 0; i < vrs.data_.size(); i++)
    result.data_[i] = sin(vrs.data_[i]);

  return result;
}

// cos(VRealArrays)

VRealArrays cos(const VRealArrays &vrs)
{
  VRealArrays result;
  result.data_.resize(vrs.data_.size());

  for (unsigned int i = 0; i < vrs.data_.size(); i++)
    result.data_[i] = cos(vrs.data_[i]);

  return result;
}

// exp(VRealArrays)

VRealArrays exp(const VRealArrays &vrs)
{
  VRealArrays result;
  result.data_.resize(vrs.data_.size());

  for (unsigned int i = 0; i < vrs.data_.size(); i++)
    result.data_[i] = exp(vrs.data_[i]);

  return result;
}
