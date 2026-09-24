
#include "Baseflow.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Baseflow::PrintBaseFlowElevation_(
    const realCompositeGridFunction &elevation,
    const string &filename) const
{
  ofstream fout(filename, ios::out);
  int wdt = OW3DSeakeeping::print_width;
  fout.setf(ios_base::scientific);
  fout.precision(OW3DSeakeeping::print_precision);
  fout << "Base-flow elevation" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
  fout << setw(wdt) << "x" << setw(wdt) << "z" << setw(wdt) << "y" << '\n';

  for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
  {
    const Single_boundary_data &bf = boundariesData_->free[surface];
    const MappedGrid &mg = (*cg_)[bf.grid];
    const vector<Index> &Is = bf.surface_indices;
    double x, z;

    for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
    {
      for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
      {
        for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
        {
          x = mg.vertex()(i, j, k, axis1);
          if (gridData_->nod == 2)
            z = 0.0;
          else
            z = mg.vertex()(i, j, k, axis3);

          if (mg.mask()(i, j, k) > 0)
          {
            fout << setw(wdt) << x << setw(wdt) << z << setw(wdt) << elevation[bf.grid](i, j, k) << '\n';
          }

        } // End of k

      } // End of j

    } // End of i

  } // End of loop over free-surface

  fout.close();
}