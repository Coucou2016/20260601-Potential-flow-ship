#include "OW3DUtilFunctions.h"
#include <iomanip>

void OW3DSeakeeping::PrintSurfaceDerivatives(
    const RealArray &x,
    const RealArray &y,
    const RealArray &z,
    const SideDervs &Dervs,
    string filename)
{
    ofstream fout(filename, ios::out);
    int wdt = 18;
    fout.setf(ios_base::scientific);
    fout.precision(10);

    fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "dx" << setw(wdt) << "dy" << setw(wdt) << "dz" << setw(wdt)
         << "dxx" << setw(wdt) << "dxy" << setw(wdt) << "dxz" << setw(wdt) << "dyy" << setw(wdt) << "dyz" << setw(wdt) << "dzz"
         << "\n";

    for (int i = x.getBase(0); i <= x.getBound(0); i++)
    {
        for (int j = x.getBase(1); j <= x.getBound(1); j++)
        {
            fout << setw(wdt) << x(i, j) << setw(wdt) << y(i, j) << setw(wdt) << z(i, j) << setw(wdt)
                 << Dervs.dx(i, j) << setw(wdt) << Dervs.dy(i, j) << setw(wdt) << Dervs.dz(i, j) << setw(wdt)
                 << Dervs.dxx(i, j) << setw(wdt) << Dervs.dxy(i, j) << setw(wdt) << Dervs.dxz(i, j) << setw(wdt)
                 << Dervs.dyy(i, j) << setw(wdt) << Dervs.dyz(i, j) << setw(wdt) << Dervs.dzz(i, j) << setw(wdt) << '\n';
        }
    }
}

void OW3DSeakeeping::PrintSurfaceDerivatives(const CompositeGrid &cg, const vector<Single_boundary_data> boundaries_data, const potentialDerivative &Dervs, string filename, bool sub)
{
    ofstream fout(filename, ios::out);
    int wdt = 18;
    fout.setf(ios_base::scientific);
    fout.precision(10);

    fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "dx" << setw(wdt) << "dy" << setw(wdt) << "dz" << setw(wdt)
         << "dxx" << setw(wdt) << "dyy" << setw(wdt) << "dzz" << setw(wdt) << "dxy" << setw(wdt) << "dxz" << setw(wdt) << "dyz"
         << "\n";

    for (unsigned int surface = 0; surface < boundaries_data.size(); surface++)
    {
        const Single_boundary_data &bs = boundaries_data[surface];
        const MappedGrid &mg = (*cg)[bs.grid];
        const vector<Index> &Is = bs.surface_indices;

        for (int axis = 0; axis < mg.numberOfDimensions(); axis++)
        {
            for (unsigned int side = 0; side <= 1; side++)
            {
                if (mg.boundaryCondition()(side, axis) == 3 || (mg.boundaryCondition()(side, axis) == 1 and sub))
                {
                    double x, y, z;

                    for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
                    {
                        for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
                        {
                            for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
                            {
                                x = mg.vertex()(i, j, k, axis1);
                                y = mg.vertex()(i, j, k, axis2);
                                z = (cg->numberOfComponentGrids == 2) ? 0. : mg.vertex()(i, j, k, axis3);

                                if (mg.mask()(i, j, k) > 0)
                                {
                                    fout << setw(wdt) << x << setw(wdt) << y << setw(wdt) << z
                                         << setw(wdt) << Dervs.dx[surface](i, j, k)
                                         << setw(wdt) << Dervs.dy[surface](i, j, k)
                                         << setw(wdt) << Dervs.dz[surface](i, j, k)
                                         << setw(wdt) << Dervs.dxx[surface](i, j, k)
                                         << setw(wdt) << Dervs.dyy[surface](i, j, k)
                                         << setw(wdt) << Dervs.dzz[surface](i, j, k)
                                         << setw(wdt) << Dervs.dxy[surface](i, j, k)
                                         << setw(wdt) << Dervs.dxz[surface](i, j, k)
                                         << setw(wdt) << Dervs.dyz[surface](i, j, k)
                                         << '\n';
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}