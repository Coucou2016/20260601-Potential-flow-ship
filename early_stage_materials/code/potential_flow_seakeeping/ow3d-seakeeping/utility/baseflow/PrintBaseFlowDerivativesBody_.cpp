#include "Baseflow.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Baseflow::PrintBaseFlowDerivativesBody_(const string &filename)
{
  ofstream fout(filename, ios::out);
  int wdt = OW3DSeakeeping::print_width;
  fout.setf(ios_base::scientific);
  fout.precision(OW3DSeakeeping::print_precision);
  fout << "Base-flow derivatives on the body surface" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
  fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z"
       << setw(wdt) << "ux" << setw(wdt) << "uy" << setw(wdt) << "uz"
       << setw(wdt) << "uxx" << setw(wdt) << "uyy" << setw(wdt) << "uzz"
       << setw(wdt) << "uxy" << setw(wdt) << "uxz" << setw(wdt) << "uyz"
       << '\n';

  int nod = gridData_->nod;

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
  {
    const Single_boundary_data &bf = boundariesData_->exciting[surface];
    const MappedGrid &mg = (*cg_)[bf.grid];
    const vector<Index> &Is = bf.surface_indices;

    double x, y, z;

    for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
    {
      for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
      {
        for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
        {
          x = mg.vertex()(i, j, k, axis1);
          y = mg.vertex()(i, j, k, axis2);
          z = (nod == 2) ? 0. : mg.vertex()(i, j, k, axis3);

          if (mg.mask()(i, j, k) > 0)
          {
            fout << setw(wdt) << x << setw(wdt) << y << setw(wdt) << z
                 << setw(wdt) << derivative_on_body_.dx[surface](i, j, k)
                 << setw(wdt) << derivative_on_body_.dy[surface](i, j, k)
                 << setw(wdt) << derivative_on_body_.dz[surface](i, j, k)
                 << setw(wdt) << derivative_on_body_.dxx[surface](i, j, k)
                 << setw(wdt) << derivative_on_body_.dyy[surface](i, j, k)
                 << setw(wdt) << derivative_on_body_.dzz[surface](i, j, k)
                 << setw(wdt) << derivative_on_body_.dxy[surface](i, j, k)
                 << setw(wdt) << derivative_on_body_.dxz[surface](i, j, k)
                 << setw(wdt) << derivative_on_body_.dyz[surface](i, j, k)
                 << '\n';
          }
        }
      }
    }
  }

  fout.close();
}