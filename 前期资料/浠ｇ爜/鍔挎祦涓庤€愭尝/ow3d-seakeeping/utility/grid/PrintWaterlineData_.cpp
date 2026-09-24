#include "Grid.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Grid::PrintWaterlineData_() const
{
    if (gridData_.wlData.size() != 0)
    {
        ofstream fout(grid_wline_file_);
        fout.setf(ios_base::scientific);
        unsigned int sp = OW3DSeakeeping::print_width;
        fout.precision(OW3DSeakeeping::print_precision);
        fout << "Waterline data " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';

        fout << "number of waterlines " << gridData_.wlData.size() << '\n';
        fout << setw(sp) << "line" << setw(sp) << "index" << setw(sp) << "base" << setw(sp) << "bound" << '\n';

        for (unsigned int line = 0; line < gridData_.wlData.size(); line++)
        {
            fout << setw(sp) << line + 1 << setw(sp) << 0 << setw(sp) << gridData_.wlData[line].I0.getBase() << setw(sp) << gridData_.wlData[line].I0.getBound() << '\n'
                 << setw(sp) << line + 1 << setw(sp) << 1 << setw(sp) << gridData_.wlData[line].I1.getBase() << setw(sp) << gridData_.wlData[line].I1.getBound() << '\n'
                 << setw(sp) << line + 1 << setw(sp) << 2 << setw(sp) << gridData_.wlData[line].I2.getBase() << setw(sp) << gridData_.wlData[line].I2.getBound() << '\n';
        }

        fout << setw(sp) << setw(sp) << "x" << setw(sp) << "y" << setw(sp) << "z" << setw(sp)
             << setw(sp) << "nx" << setw(sp) << "nz" << setw(sp)
             << setw(sp) << setw(sp) << "dl" << '\n';

        for (unsigned int line = 0; line < gridData_.wlData.size(); line++)
        {
            for (unsigned int p = 0; p < gridData_.wlData[line].x.size(); p++)
            {
                fout << setw(sp) << setw(sp) << gridData_.wlData[line].x[p] << setw(sp) << gridData_.wlData[line].y[p] << setw(sp) << gridData_.wlData[line].z[p] << setw(sp)
                     << gridData_.wlData[line].n1[p] << setw(sp) << gridData_.wlData[line].n3[p] << setw(sp);
                if (p != 0)
                    fout << gridData_.wlData[line].dl[p - 1] << '\n';
                else
                    fout << '\n';
            }
        }

        fout.close();
    }
}