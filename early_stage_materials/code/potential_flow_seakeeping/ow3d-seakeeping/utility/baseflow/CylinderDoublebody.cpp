// This file gives the analytical solution for the double body flow around cylinder

#include "OW3DUtilFunctions.h"

void cylinderSurfaceDerivatives(
    CompositeGrid &cg,
    OW3DSeakeeping::potentialDerivative &surface_derivative,
    const OW3DSeakeeping::Single_boundary_data &sbd,
    vector<double> geometry,
    double U)
{
  double R = geometry[0];
  const vector<Index> &Is = sbd.surface_indices;
  MappedGrid &mg = cg[sbd.grid];

  realArray temp(Is[0], Is[1], Is[2]);
  temp = 0.;

  realArray x(Is[0], Is[1], Is[2]);
  x = mg.vertex()(Is[0], Is[1], Is[2], axis1);
  realArray y(Is[0], Is[1], Is[2]);
  y = mg.vertex()(Is[0], Is[1], Is[2], axis2);

  realArray pv(Is[0], Is[1], Is[2]);
  pv = sqrt(pow(x, 2) + pow(y, 2));

  // dphi/dx = (2*U*a^2*x^2)/(x^2 + y^2)^2 - (U*a^2)/(x^2 + y^2)
  surface_derivative.dx.push_back(2 * U * R * R * pow(x, 2) / pow(pv, 4) - U * R * R / pow(pv, 2));

  // dphi/dy = (2*U*a^2*x*y)/(x^2 + y^2)^2
  surface_derivative.dy.push_back(2 * U * R * R * x * y / pow(pv, 4));

  // d^2phidx² = (6*R^2*U*x)/(x^2 + y^2)^2 - (8*R^2*U*x^3)/(x^2 + y^2)^3
  surface_derivative.dxx.push_back(6 * R * R * U * x / pow(pv, 4) - 8 * R * R * U * pow(x, 3) / pow(pv, 6));

  // d^2phidy^2 = (2*R^2*U*x)/(x^2 + y^2)^2 - (8*R^2*U*x*y^2)/(x^2 + y^2)^3
  surface_derivative.dyy.push_back(2 * R * R * U * x / pow(pv, 4) - 8 * R * R * U * x * pow(y, 2) / pow(pv, 6));

  // d^2phi/dxdy = (2*R^2*U*y)/(x^2 + y^2)^2 - (8*R^2*U*x^2*y)/(x^2 + y^2)^3
  surface_derivative.dxy.push_back(2 * R * R * U * y / pow(pv, 4) - 8 * R * R * U * y * pow(x, 2) / pow(pv, 6));

  surface_derivative.dz.push_back(temp);
  surface_derivative.dyz.push_back(temp);
  surface_derivative.dxz.push_back(temp);
  surface_derivative.dzz.push_back(temp);
}

OW3DSeakeeping::analyticalData OW3DSeakeeping::CylinderDoublebody(
    CompositeGrid &cg,
    const All_boundaries_data &boundariesData,
    vector<double> geometry,
    double U)
{
  double R = geometry[0];
  analyticalData data;
  data.potential.updateToMatchGrid(cg);
  data.field_derivative.d_phib_dx.updateToMatchGrid(cg);
  data.field_derivative.d_phib_dy.updateToMatchGrid(cg);
  data.field_derivative.d_phib_dz.updateToMatchGrid(cg);

  for (int grid = 0; grid < cg.numberOfComponentGrids(); grid++)
  {
    Index I1, I2, I3;
    const MappedGrid &mg = cg[grid];
    getIndex(mg.dimension(), I1, I2, I3);

    realArray x(I1, I2, I3);
    x = mg.vertex()(I1, I2, I3, axis1);
    realArray y(I1, I2, I3);
    y = mg.vertex()(I1, I2, I3, axis2);

    realArray pv(I1, I2, I3);
    pv = sqrt(pow(x, 2) + pow(y, 2));

    // phi = -(U*a^2*x)/(x^2 + y^2)
    data.potential[grid](I1, I2, I3) = -U * R * R * x / pow(pv, 2);

    // dphi/dx = (2*U*a^2*x^2)/(x^2 + y^2)^2- (U*a^2)/(x^2 + y^2)
    data.field_derivative.d_phib_dx[grid](I1, I2, I3) = 2 * U * R * R * pow(x, 2) / pow(pv, 4) - U * R * R / pow(pv, 2);

    // dphi/dy = (2*U*a^2*x*y)/(x^2 + y^2)^2
    data.field_derivative.d_phib_dy[grid](I1, I2, I3) = 2 * U * R * R * x * y / pow(pv, 4);

    // dphi/dz = 0
    data.field_derivative.d_phib_dz[grid](I1, I2, I3) = 0.0;
  }

  for (unsigned int surface = 0; surface < boundariesData.free.size(); surface++)
  {
    const Single_boundary_data &sbd = boundariesData.free[surface];
    cylinderSurfaceDerivatives(cg, data.surface_derivative, sbd, geometry, U);
  }
  for (unsigned int surface = 0; surface < boundariesData.exciting.size(); surface++)
  {
    const Single_boundary_data &sbd = boundariesData.exciting[surface];
    cylinderSurfaceDerivatives(cg, data.body_derivative, sbd, geometry, U);
  }

  return data;
}
