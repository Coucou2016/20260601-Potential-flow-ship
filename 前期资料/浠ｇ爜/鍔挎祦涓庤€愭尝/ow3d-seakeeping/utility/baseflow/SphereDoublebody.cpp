// This file gives the analytical solution for the double body flow around sphere

#include "OW3DUtilFunctions.h"

void sphereSurfaceDerivatives(
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
  realArray z(Is[0], Is[1], Is[2]);
  z = mg.vertex()(Is[0], Is[1], Is[2], axis3);

  realArray pv(Is[0], Is[1], Is[2]);
  pv(Is[0], Is[1], Is[2]) = sqrt(pow(x, 2) + pow(y, 2) + pow(z, 2));

  // dphi/dx =(3*R^3*U*x^2)/(2*(x^2 + y^2 + z^2)^(5/2)) - (R^3*U)/(2*(x^2 + y^2 + z^2)^(3/2))
  surface_derivative.dx.push_back(3. * U * R * R * R * pow(x, 2) / (2. * pow(pv, 5)) - U * R * R * R / (2. * pow(pv, 3)));

  // dphi/dy=(3*R^3*U*x*y)/(2*(x^2 + y^2 + z^2)^(5/2))
  surface_derivative.dy.push_back(3. * U * R * R * R * x * y / (2. * pow(pv, 5)));

  // dphi/dz=(3*R^3*U*x*z)/(2*(x^2 + y^2 + z^2)^(5/2))
  surface_derivative.dz.push_back(3. * U * R * R * R * x * z / (2. * pow(pv, 5)));

  // d^2phi/dx^2=(9*R^3*U*x)/(2*(x^2 + y^2 + z^2)^(5/2)) - (15*R^3*U*x^3)/(2*(x^2 + y^2 + z^2)^(7/2))
  surface_derivative.dxx.push_back(9. * U * R * R * R * x / (2. * pow(pv, 5)) - 15. * U * R * R * R * pow(x, 3) / (2. * pow(pv, 7)));

  // d^2phi/dy^2=(3*R^3*U*x)/(2*(x^2 + y^2 + z^2)^(5/2)) - (15*R^3*U*x*y^2)/(2*(x^2 + y^2 + z^2)^(7/2))
  surface_derivative.dyy.push_back(3. * U * R * R * R * x / (2. * pow(pv, 5)) - 15. * U * R * R * R * x * pow(y, 2) / (2. * pow(pv, 7)));

  // d^2phi/dz^2=(3*R^3*U*x)/(2*(x^2 + y^2 + z^2)^(5/2)) - (15*R^3*U*x*z^2)/(2*(x^2 + y^2 + z^2)^(7/2))
  surface_derivative.dzz.push_back(3. * U * R * R * R * x / (2. * pow(pv, 5)) - 15. * U * R * R * R * x * pow(z, 2) / (2. * pow(pv, 7)));

  // d^2phi/dxdy=(3*R^3*U*y)/(2*(x^2 + y^2 + z^2)^(5/2)) - (15*R^3*U*x^2*y)/(2*(x^2 + y^2 + z^2)^(7/2))
  surface_derivative.dxy.push_back(3. * U * R * R * R * y / (2. * pow(pv, 5)) - 15. * U * R * R * R * y * pow(x, 2) / (2. * pow(pv, 7)));

  // d^2phi/dxdz=(3*R^3*U*z)/(2*(x^2 + y^2 + z^2)^(5/2)) - (15*R^3*U*x^2*z)/(2*(x^2 + y^2 + z^2)^(7/2))
  surface_derivative.dxz.push_back(3. * U * R * R * R * z / (2. * pow(pv, 5)) - 15. * U * R * R * R * z * pow(x, 2) / (2. * pow(pv, 7)));

  // d^2phi/dydz=-(15*R^3*U*x*y*z)/(2*(x^2 + y^2 + z^2)^(7/2))
  surface_derivative.dyz.push_back(-15. * U * R * R * R * x * y * z / (2. * pow(pv, 7)));
}

OW3DSeakeeping::analyticalData OW3DSeakeeping::SphereDoublebody(
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
    realArray z(I1, I2, I3);
    z = mg.vertex()(I1, I2, I3, axis3);

    realArray pv(I1, I2, I3);
    pv = sqrt(pow(x, 2) + pow(y, 2) + pow(z, 2));

    // phi = -(R^3*U*x)/(2*(x^2 + y^2 + z^2)^(3/2))
    data.potential[grid](I1, I2, I3) = -R * R * R * U * x / (2. * pow(pv, 3));

    // dphi/dx = (3*R^3*U*x^2)/(2*(x^2 + y^2 + z^2)^(5/2)) - (R^3*U)/(2*(x^2 + y^2 + z^2)^(3/2))
    data.field_derivative.d_phib_dx[grid](I1, I2, I3) = 3. * U * R * R * R * pow(x, 2) / (2. * pow(pv, 5)) - U * R * R * R / (2. * pow(pv, 3));

    // dphi/dy = (3*R^3*U*x*y)/(2*(x^2 + y^2 + z^2)^(5/2))
    data.field_derivative.d_phib_dy[grid](I1, I2, I3) = 3. * U * R * R * R * x * y / (2 * pow(pv, 5));

    // dphi/dz = (3*R^3*U*x*z)/(2*(x^2 + y^2 + z^2)^(5/2))
    data.field_derivative.d_phib_dz[grid](I1, I2, I3) = 3. * U * R * R * R * x * z / (2 * pow(pv, 5));
  }

  for (unsigned int surface = 0; surface < boundariesData.free.size(); surface++)
  {
    const Single_boundary_data &sbd = boundariesData.free[surface];
    sphereSurfaceDerivatives(cg, data.surface_derivative, sbd, geometry, U);
  }

  for (unsigned int surface = 0; surface < boundariesData.exciting.size(); surface++)
  {
    const Single_boundary_data &sbd = boundariesData.exciting[surface];
    sphereSurfaceDerivatives(cg, data.body_derivative, sbd, geometry, U);
  }

  return data;
}
