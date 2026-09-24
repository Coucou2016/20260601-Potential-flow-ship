#include "Baseflow.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Baseflow::PrintMTerms_(
    const Mterms &mterms,
    const string &filename)
{
  ofstream fout(filename, ios::out);
  int wdt = OW3DSeakeeping::print_width;
  fout.setf(ios_base::scientific);
  fout.precision(OW3DSeakeeping::print_precision);
  fout << "Double-body m terms" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
  fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt)
       << "m1" << setw(wdt) << "m2" << setw(wdt) << "m3" << setw(wdt)
       << "m4" << setw(wdt) << "m5" << setw(wdt) << "m6"
       << '\n';

  int nod = gridData_->nod;

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
  {
    const Single_boundary_data &bf = boundariesData_->exciting[surface];
    const MappedGrid &mg = (*cg_)[bf.grid];

    const vector<Index> &Is = bf.surface_indices;
    double x, y, z;
    z = 0.0;

    for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
    {
      for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
      {
        for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
        {
          x = mg.vertex()(i, j, k, axis1);
          y = mg.vertex()(i, j, k, axis2);
          if (nod != 2)
            z = mg.vertex()(i, j, k, axis3);

          if (mg.mask()(i, j, k) > 0)
            fout << setw(wdt) << x << setw(wdt) << y << setw(wdt) << z << setw(wdt)
                 << mterms.m1[surface](i, j, k) << setw(wdt) << mterms.m2[surface](i, j, k) << setw(wdt)
                 << mterms.m3[surface](i, j, k) << setw(wdt) << mterms.m4[surface](i, j, k) << setw(wdt)
                 << mterms.m5[surface](i, j, k) << setw(wdt) << mterms.m6[surface](i, j, k) << '\n';
        }
      }
    }
  }

  fout.close();
}