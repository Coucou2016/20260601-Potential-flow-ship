// This file contains the implementation of the Filter class

#include "Filter.h"
#include "OW3DConstants.h"

bool OW3DSeakeeping::Filter::print_ = true;

OW3DSeakeeping::Filter::Filter()
{
  // here we make sure that whenever the default constructor is called, a vertexData_
  // just for one surface is allocated. We must do this as in the assignment operator
  // the memory for the target object are first de-allocated. Then if an object is built
  // by the default constructor we are sure that de-allocating memory in the assignment
  // operator does not fail.

  nofs_ = 1;
  direction d;
  d.size[0] = 1;
  d.size[1] = 1;
  directions_.push_back(d);

  vertexData_ = new data **[nofs_];

  for (unsigned int surface = 0; surface < nofs_; surface++)
  {
    vertexData_[surface] = new data *[directions_[surface].size[0]];
    for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
    {
      vertexData_[surface][i] = new data[directions_[surface].size[1]];
    }
  }
}

OW3DSeakeeping::Filter::Filter(const CompositeGrid &cg, const vector<Single_boundary_data> &bdata, filt_params params) : nofs_(bdata.size())
{
  if (params.width % 2 == 0 or params.order >= params.width - 1)
  {
    throw runtime_error("Error, OW3DSeakeeping::Filter.cpp: Filter width or its order is wrong.");
  }

  // 7 is the minimum allowed filter width

  if (params.width < 7)
  {
    throw runtime_error("Error, OW3DSeakeeping::Filter.cpp: Filter width must be greater than 7.");
  }
  if (params.sigma > 1)
  {
    throw runtime_error("Error, OW3DSeakeeping::Filter.cpp: Filter strength must be less than 1.");
  }

  W_ = params.width;
  HW_ = (params.width - 1) / 2;
  ORDER_ = params.order;
  w_ = 7;
  hw_ = (w_ - 1) / 2;
  d_ = 2;
  sigma_ = params.sigma;

  unsigned int surface, i;

  vertexData_ = new data **[nofs_]; // vertexData_ points to an array with the size of number of free surfaces.

  vector<Index> I;
  I.resize(3);

  // find the search directions and the sizes of vertexData_

  for (surface = 0; surface < nofs_; surface++)
  {
    const Single_boundary_data &bs = bdata[surface];
    const vector<Index> &Is = bs.surface_indices;
    const MappedGrid &mg = cg[bs.grid];
    getIndex(mg.gridIndexRange(), I[0], I[1], I[2]);

    direction d;

    d.Is = Is;
    d.grid = bs.grid;

    if (Is[0].length() == 1 and I[0].length() > 1)
    {
      d.index[0] = 1;
      d.index[1] = 2;
      d.size[0] = Is[1].length();
      d.size[1] = Is[2].length();
    }
    if (Is[1].length() == 1 and I[1].length() > 1)
    {
      d.index[0] = 0;
      d.index[1] = 2;
      d.size[0] = Is[0].length();
      d.size[1] = Is[2].length();
    }
    if (Is[2].length() == 1 and I[2].length() > 1)
    {
      d.index[0] = 0;
      d.index[1] = 1;
      d.size[0] = Is[0].length();
      d.size[1] = Is[1].length();
    }

    directions_.push_back(d);

    // allocate memory for vertexData_

    vertexData_[surface] = new data *[d.size[0]];

    for (i = 0; i < d.size[0]; i++)
    {
      vertexData_[surface][i] = new data[d.size[1]];
    }

  } // end of loop over free surface

  BuildFilters_(cg, bdata);

  if (print_)
    print_ = false;

} // end of constructor

OW3DSeakeeping::Filter &OW3DSeakeeping::Filter::operator=(const Filter &existing)
{

  if (this != &existing)
  {
    // deallocate old memory for the target object

    for (unsigned int surface = 0; surface < nofs_; surface++)
    {
      for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
      {
        delete[] vertexData_[surface][i];
      }
      delete[] vertexData_[surface];
    }
    delete[] vertexData_;

    // copy data members

    directions_ = existing.directions_;
    nofs_ = existing.nofs_;
    sigma_ = existing.sigma_;
    W_ = existing.W_;
    HW_ = existing.HW_;
    w_ = existing.w_;
    hw_ = existing.hw_;
    ORDER_ = existing.ORDER_;
    d_ = existing.d_;
    //
    c_ = existing.c_;
    f_ = existing.f_;
    //
    f03_ = existing.f03_;
    f30_ = existing.f30_;
    f15_ = existing.f15_;
    f51_ = existing.f51_;
    f28_ = existing.f28_;
    f82_ = existing.f82_;
    f37_ = existing.f37_;
    f73_ = existing.f73_;
    f46_ = existing.f46_;
    f64_ = existing.f64_;
    //
    c03_ = existing.c03_;
    c30_ = existing.c30_;
    c15_ = existing.c15_;
    c51_ = existing.c51_;
    c28_ = existing.c28_;
    c82_ = existing.c82_;
    c37_ = existing.c37_;
    c73_ = existing.c73_;
    c46_ = existing.c46_;
    c64_ = existing.c64_;

    // allocate new memory for target object

    vertexData_ = new data **[nofs_];

    for (unsigned int surface = 0; surface < nofs_; surface++)
    {
      vertexData_[surface] = new data *[directions_[surface].size[0]];

      for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
      {
        vertexData_[surface][i] = new data[directions_[surface].size[1]];
      }
    }

    // assign the new memory to the existing vertexData_

    for (unsigned int surface = 0; surface < nofs_; surface++)
    {
      for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
      {
        for (unsigned int j = 0; j < directions_[surface].size[1]; j++)
        {
          vertexData_[surface][i][j] = existing.vertexData_[surface][i][j];
        }
      }
    }

  } // end of self-assignment check

  return *this;

} // end of assignment operator

OW3DSeakeeping::Filter::~Filter()
{
  for (unsigned int surface = 0; surface < nofs_; surface++)
  {
    for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
    {
      delete[] vertexData_[surface][i];
    }

    delete[] vertexData_[surface];
  }

  delete[] vertexData_;
}
