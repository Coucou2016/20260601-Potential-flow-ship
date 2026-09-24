#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::ComputeDoublebodyElevation_(
    realCompositeGridFunction &doubleBodyElevation,
    const realCompositeGridFunction &dphidx,
    const realCompositeGridFunction &dphidy,
    const realCompositeGridFunction &dphidz)
{
  realCompositeGridFunction eta(*cg_), downFunction(*cg_), upFunction(*cg_);
  eta = 0.0;
  downFunction = 0.0;
  upFunction = 0.0;

  for (int gr = 0; gr < cg_->numberOfComponentGrids(); ++gr) // loop over grids to define up and down functions
  {
    Index I1, I2, I3;
    MappedGrid mg = (*cg_)[gr];
    getIndex(mg.dimension(), I1, I2, I3);

    // Dynamic free surface bc etas=-1/2g*(grad(phib).grad(phib)-2*U*dphib/dx)

    eta[gr](I1, I2, I3) =
        -1. / (2 * g_) * (pow(dphidx[gr](I1, I2, I3), 2) + pow(dphidy[gr](I1, I2, I3), 2) + pow(dphidz[gr](I1, I2, I3), 2) - 2. * UserInput.U * dphidx[gr](I1, I2, I3));

    getIndex(mg.gridIndexRange(), I1, I2, I3);
    where(mg.mask()(I1, I2, I3) > 0) // just the discretization points
    {
      upFunction[gr](I1, I2, I3) = eta[gr](I1, I2, I3) + mg.vertex()(I1, I2, I3, axis2);
      downFunction[gr](I1, I2, I3) = eta[gr](I1, I2, I3) - mg.vertex()(I1, I2, I3, axis2);
    }
  }

  // Populate interpolation points (in the case interpolation points are needed to find the root for a discretization point)

  interpolant_.interpolate(downFunction);
  interpolant_.interpolate(upFunction);

  for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++) // loop over free-surface
  {
    const Single_boundary_data &bf = boundariesData_->free[surface];
    const vector<Index> &Is = bf.surface_indices;
    vector<Index> I;
    I.resize(3);
    MappedGrid &mg = (*cg_)[bf.grid];
    getIndex(mg.gridIndexRange(), I[0], I[1], I[2]);

    // There are two criteria which have been taken in to account while finding the double-body elevation: the search side and the search direction.
    // The idea is to start at a free-surface and do the search in the direction perpendicular to the free-surface. This direction is the one where
    // the length of the free-surface index is one. The search side is also important as it dictates incrementing or decrementing the index for the
    // search. If the seach begins at the start side of the free-surface, the index will be incremented to find the root and vice versa.
    //
    // The search begins by first finding the index where there is a sign change in the up or down function. It then checks if the point at this
    // index is a discritization point. If yes it finds the number of eligible points (discretization or interpolation) along the search direction which
    // can be used for fitting the required polynomial and root finding. The eligible points are named as: dp_s and dp_n for start and end of the desired
    // discretization point.

    string side = "start"; // Assume the search begins from start side.
    int direction;         // The search direction.

    if (Is[0].length() == 1 and I[0].length() > 1)
    {
      direction = 0;
      if (Is[0].getBase() != 0)
        side = "end"; // get the search diretion and side

      SearchElevation_1_2_0_(side, direction, Is, I, mg, bf, downFunction, upFunction, doubleBodyElevation); // do the search
    }
    else if (Is[1].length() == 1 and I[1].length() > 1)
    {
      direction = 1;
      if (Is[1].getBase() != 0)
        side = "end"; // get the search diretion and side

      SearchElevation_0_2_1_(side, direction, Is, I, mg, bf, downFunction, upFunction, doubleBodyElevation); // do the search
    }
    else // (Is[2].length()==1 and I[2].length()>1)
    {
      direction = 2;
      if (Is[2].getBase() != 0)
        side = "end"; // get the search diretion and side

      SearchElevation_0_1_2_(side, direction, Is, I, mg, bf, downFunction, upFunction, doubleBodyElevation); // do the search
    }

  } // End surface loop

  // Interpolation the double body elevation

  interpolant_.interpolate(doubleBodyElevation);

} // End of solveElevation_ private member function