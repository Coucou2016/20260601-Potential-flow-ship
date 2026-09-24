#include "OW3DUtilFunctions.h"

// This file implemenst the findBodyGeometry function. The function is
// able to find the characteristics of the geometry of the primitives bodis
// like cylinder and sphere.
// At the moement it gives the radius of mentioned bodies. Since
// the geometry of other primitive bodies (like spheroid) may be of interest
// in the future, a vector data type is considered for storing the geometry.
// Note :: if the body is not primitive, then the vector is just empty.

vector<double> OW3DSeakeeping::FindBodyGeometry(
    CompositeGrid &cg,
    const All_boundaries_data &boundariesData)
{
  realCompositeGridFunction pv(cg);
  pv = 0.0;
  vector<double> geometry;
  double radiusMin = 0., radiusMax = 0.;

  double tol = 1e-6;

  for (unsigned int surface = 0; surface < boundariesData.exciting.size(); surface++)
  {
    const Single_boundary_data &be = boundariesData.exciting[surface];
    const vector<Index> &Ie = be.surface_indices;
    MappedGrid &mg = cg[be.grid];

    realArray z(Ie[0], Ie[1], Ie[2]);
    z = 0.;

    if (cg.numberOfDimensions() == 3)
    {
      z = mg.vertex()(Ie[0], Ie[1], Ie[2], axis3);
    }

    pv[be.grid](Ie[0], Ie[1], Ie[2]) = sqrt(pow(mg.vertex()(Ie[0], Ie[1], Ie[2], axis1), 2) + pow(mg.vertex()(Ie[0], Ie[1], Ie[2], axis2), 2) + pow(z, 2));

    radiusMin = min(pv[be.grid](Ie[0], Ie[1], Ie[2]));
    radiusMax = max(pv[be.grid](Ie[0], Ie[1], Ie[2]));

    if ((radiusMax - radiusMin) > tol)
    {
      return geometry; // the body is not primitive, and the geometry is just void vector
    }
  }

  geometry.push_back(radiusMin);

  return geometry;
}
