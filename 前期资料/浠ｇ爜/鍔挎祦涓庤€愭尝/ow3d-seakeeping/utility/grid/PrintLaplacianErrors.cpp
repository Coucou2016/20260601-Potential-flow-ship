#include "OW3DConstants.h"
#include <iomanip>
#include "Grid.h"

void OW3DSeakeeping::Grid::PrintLaplacianErrors() const
{
    string resultsDirectory = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;

    // Print the results

    string filename = resultsDirectory + "/laperrs.txt";
    ofstream fout(filename, ios::out);
    int wdt = OW3DSeakeeping::print_width;
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);
    fout << "Laplacian error at the body surface" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
    fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "phic" << setw(wdt) << "phi" << '\n';

    int nod = gridData_.nod;
    double norm = max(fabs(man_sol_));

    for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
    {
        const Single_boundary_data &bf = gridData_.boundariesData.exciting[surface];
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
                    {
                        fout << setw(wdt) << x << setw(wdt) << y << setw(wdt) << z << setw(wdt)
                             << man_sol_comp_[bf.grid](i, j, k) / norm << setw(wdt) << man_sol_[bf.grid](i, j, k) / norm << '\n';
                    }
                }
            }
        }
    }

    fout.close();
}