#include "FreeSurface.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::FreeSurface::PrintElevation(const double &time) const
{
    string elevationFileName = resultsDirectory_ + '/' + OW3DSeakeeping::ModeStrings.at(mode_name_) + '/' + to_string(time) + ".txt";
    ofstream fout(elevationFileName, ios::out);
    int wdt = OW3DSeakeeping::print_width;
    fout.precision(OW3DSeakeeping::print_precision);
    fout.setf(ios_base::scientific);
    fout << "Free-surface elevation " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
    fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "zeta" << '\n';

    ofstream streamTimes(resultsDirectory_ + '/' + OW3DSeakeeping::ModeStrings.at(mode_name_) + '/' + "loadtimes.txt", ios::out | ios::app);
    streamTimes << to_string(time) + ".txt" << '\n';

    for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
    {
        const Single_boundary_data &bf = boundariesData_->free[surface];
        const MappedGrid &mg = (*cg_)[bf.grid];
        const vector<Index> &Is = bf.surface_indices;
        double x, z;
        for (int i = Is[0].getBase(); i <= Is[0].getBound(); ++i)
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); ++j)
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); ++k)
                {
                    x = mg.vertex()(i, j, k, axis1);
                    z = ((*cg_).numberOfDimensions() == 2) ? 0. : mg.vertex()(i, j, k, axis3);
                    if (mg.mask()(i, j, k) > 0)
                        fout << setw(wdt) << x << setw(wdt) << z << setw(wdt) << freeSurface_.solution_start.elevation[bf.grid](i, j, k) << '\n';
                }
    }
    fout.close();
    streamTimes.close();
}