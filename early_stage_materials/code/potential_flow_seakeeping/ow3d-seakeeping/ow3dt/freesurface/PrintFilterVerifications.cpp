#include "FreeSurface.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::FreeSurface::PrintFilterVerifications()
{
    double K = gridData_->kMax / 10;
    double beta = 4 * Pi / 5;
    realCompositeGridFunction phi(*cg_), phi_org(*cg_);
    phi = 0.;
    for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
    {
        const OW3DSeakeeping::Single_boundary_data &be = boundariesData_->free[surface];
        const MappedGrid &mg = (*cg_)[be.grid];
        vector<Index> Is = be.surface_indices;
        const RealArray &v = mg.vertex();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        z = (gridData_->nod == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);
        RealArray alpha = x * cos(beta) + z * sin(beta);
        phi[be.grid](Is[0], Is[1], Is[2]) = exp(K * y) * cos(K * alpha);
        phi_org[be.grid](Is[0], Is[1], Is[2]) = exp(K * y) * cos(K * alpha);
    }

    filter_.ApplyFilter(phi);

    // Print to file

    string filename = resultsDirectory_ + "/filtered.txt";
    ofstream fout(filename, ios::out);
    int wdt = OW3DSeakeeping::print_width;
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);
    fout << "Velocity potentials at the surface, before and after filtering" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
    fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "phi" << setw(wdt) << "phi_filtered" << '\n';

    for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
    {
        const OW3DSeakeeping::Single_boundary_data &be = boundariesData_->free[surface];
        const MappedGrid &mg = (*cg_)[be.grid];
        vector<Index> Is = be.surface_indices;
        double x, y, z;
        for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
        {
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
            {
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
                {
                    x = mg.vertex()(i, j, k, axis1);
                    y = mg.vertex()(i, j, k, axis2);
                    z = (gridData_->nod == 2) ? 0 : mg.vertex()(i, j, k, axis3);

                    if (mg.mask()(i, j, k) > 0)
                        fout << setw(wdt) << x << setw(wdt) << y << setw(wdt) << z << setw(wdt) << phi_org[be.grid](i, j, k) << setw(wdt) << phi[be.grid](i, j, k) << '\n';
                }
            }
        }
    }
}