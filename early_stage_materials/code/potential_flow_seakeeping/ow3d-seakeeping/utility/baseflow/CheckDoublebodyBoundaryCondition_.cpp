#include "Baseflow.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Baseflow::CheckDoublebodyBoundaryCondition_()
{
  string filename = resultsDirectory_ + '/' + base_bccheck_file;

  ofstream fout(filename, ios::out);
  int wdt = 15;

  fout.setf(ios_base::scientific);
  fout.precision(6);
  fout << "Double-body boundary condition checks" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
  fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "BC residual" << '\n';

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const vector<Index> &Ie = be.surface_indices;
    MappedGrid &mg = (*cg_)[be.grid];

    // coordinates
    const realArray &X = mg.vertex()(Ie[0], Ie[1], Ie[2], axis1);
    const realArray &Y = mg.vertex()(Ie[0], Ie[1], Ie[2], axis2);
    realArray Z(Ie[0], Ie[1], Ie[2]);
    Z = 0.0;

    // surface normals
    const realArray &normals = mg.vertexBoundaryNormal(be.side, be.axis);
    const realArray &n1 = normals(Ie[0], Ie[1], Ie[2], axis1);
    const realArray &n2 = normals(Ie[0], Ie[1], Ie[2], axis2);

    realArray n3(Ie[0], Ie[1], Ie[2]);
    n3 = 0.0;

    if (gridData_->nod != 2)
    {
      Z = mg.vertex()(Ie[0], Ie[1], Ie[2], axis3);
      n3 = normals(Ie[0], Ie[1], Ie[2], axis3);
    }

    RealArray residual =

        data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Ie[0], Ie[1], Ie[2]) * n1(Ie[0], Ie[1], Ie[2]) +
        data_.DerivativesOnCompositeGrid.d_phib_dy[be.grid](Ie[0], Ie[1], Ie[2]) * n2(Ie[0], Ie[1], Ie[2]) +
        data_.DerivativesOnCompositeGrid.d_phib_dz[be.grid](Ie[0], Ie[1], Ie[2]) * n3(Ie[0], Ie[1], Ie[2]) -

        n1(Ie[0], Ie[1], Ie[2], axis1) * UserInput.U -
        act_body_velocity_ux_[surface](Ie[0], Ie[1], Ie[2]) * n1(Ie[0], Ie[1], Ie[2]) -
        act_body_velocity_uy_[surface](Ie[0], Ie[1], Ie[2]) * n2(Ie[0], Ie[1], Ie[2]) -
        act_body_velocity_uz_[surface](Ie[0], Ie[1], Ie[2]) * n3(Ie[0], Ie[1], Ie[2]);

    // Loop over the surface points

    for (int i = Ie[0].getBase(); i <= Ie[0].getBound(); i++)
    {
      for (int j = Ie[1].getBase(); j <= Ie[1].getBound(); j++)
      {
        for (int k = Ie[2].getBase(); k <= Ie[2].getBound(); k++)
        {
          double x = X(i, j, k);
          double y = Y(i, j, k);
          double z = Z(i, j, k);

          if (mg.mask()(i, j, k) > 0)
          {
            fout << setw(wdt) << x << setw(wdt) << y << setw(wdt) << z << setw(wdt) << residual(i, j, k) << '\n';
          }

        } // End k

      } // End j

    } // End i

  } // End of loop over the body surface
}