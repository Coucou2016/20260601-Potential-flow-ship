#include "Baseflow.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Baseflow::PrintBaseFlowDerivatives_(
    const potentialDerivative &potential_derivative,
    const elevationDerivative &elevation_derivative,
    const string &filename)
{
    ofstream fout(filename, ios::out);
    int wdt = OW3DSeakeeping::print_width;
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);

    fout << "Base-flow derivatives on the free surface" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
    fout << setw(wdt) << "x" << setw(wdt) << "z"
         << setw(wdt) << "dx" << setw(wdt) << "dxx"
         << setw(wdt) << "dxy" << setw(wdt) << "dxz"
         << setw(wdt) << "dy" << setw(wdt) << "dyy"
         << setw(wdt) << "dyz" << setw(wdt) << "dz"
         << setw(wdt) << "dzz" << setw(wdt) << "dx(eta)"
         << setw(wdt) << "dz(eta)"
         << '\n';

    int nod = gridData_->nod;

    for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
    {
        const Single_boundary_data &bf = boundariesData_->free[surface];
        const MappedGrid &mg = (*cg_)[bf.grid];
        const vector<Index> &Is = bf.surface_indices;

        double x, z;
        z = 0.0;

        for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
        {
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
            {
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
                {
                    x = mg.vertex()(i, j, k, axis1);
                    if (nod != 2)
                        z = mg.vertex()(i, j, k, axis3);

                    if (mg.mask()(i, j, k) > 0)
                    {
                        fout << setw(wdt) << x << setw(wdt) << z
                             << setw(wdt) << potential_derivative.dx[surface](i, j, k)
                             << setw(wdt) << potential_derivative.dxx[surface](i, j, k)
                             << setw(wdt) << potential_derivative.dxy[surface](i, j, k)
                             << setw(wdt) << potential_derivative.dxz[surface](i, j, k)
                             << setw(wdt) << potential_derivative.dy[surface](i, j, k)
                             << setw(wdt) << potential_derivative.dyy[surface](i, j, k)
                             << setw(wdt) << potential_derivative.dyz[surface](i, j, k)
                             << setw(wdt) << potential_derivative.dz[surface](i, j, k)
                             << setw(wdt) << potential_derivative.dzz[surface](i, j, k)
                             << setw(wdt) << elevation_derivative.dx[surface](i, j, k)
                             << setw(wdt) << elevation_derivative.dz[surface](i, j, k)
                             << '\n';
                    }
                }
            }
        }
    }

    fout.close();
}