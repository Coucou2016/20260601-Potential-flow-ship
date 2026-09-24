#include "Baseflow.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Baseflow::ComputeActBodyVelocities_()
{
  string filename = resultsDirectory_ + "/act_body_vel.txt";

  ofstream fout(filename, ios::out);
  int wdt = 20;

  fout.setf(ios_base::scientific);
  fout.precision(10);

  fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "ux" << setw(wdt) << "uy" << setw(wdt) << "uz"
       << "\n\n";

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

    if (gridData_->nod != 2)
    {
      Z = mg.vertex()(Ie[0], Ie[1], Ie[2], axis3);
    }

    // Loop over the surface points

    for (int i = Ie[0].getBase(); i <= Ie[0].getBound(); i++)
    {
      for (int j = Ie[1].getBase(); j <= Ie[1].getBound(); j++)
      {
        for (int k = Ie[2].getBase(); k <= Ie[2].getBound(); k++)
        {
          double x = X(i, j, k);
          double yb = Y(i, j, k);
          double yt = -Y(i, j, k);
          double z = Z(i, j, k);

          double uxb, uyb, uzb;
          double uxt, uyt, uzt;

          actvels(&x, &yb, &z, &uxb, &uyb, &uzb);
          actvels(&x, &yt, &z, &uxt, &uyt, &uzt);

          if (mg.mask()(i, j, k) > 0)
          {
            fout << setw(wdt) << x << setw(wdt) << yb << setw(wdt) << z << setw(wdt) << (uxb + uxt) << setw(wdt) << (uyb - uyt) << setw(wdt) << (uzb + uzt) << '\n';
          }

          act_body_velocity_ux_[surface](i, j, k) = -(uxb + uxt);
          act_body_velocity_uy_[surface](i, j, k) = -(uyb - uyt);
          act_body_velocity_uz_[surface](i, j, k) = -(uzb + uzt);

        } // End k

      } // End j

    } // End i

  } // End of loop over the body surface

} // End of buildActBodyVelocities_ private member function