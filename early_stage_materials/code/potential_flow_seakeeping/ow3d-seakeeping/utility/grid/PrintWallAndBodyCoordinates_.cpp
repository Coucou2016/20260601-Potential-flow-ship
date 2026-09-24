#include "Grid.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Grid::PrintWallAndBodyCoordinates_() const
{
    int sp = OW3DSeakeeping::print_width;
    int preci = OW3DSeakeeping::print_precision;
    ofstream fout;
    fout.open(grid_wabcor_file_);
    fout.setf(ios_base::scientific);
    fout.precision(preci);
    fout << "Wall and body coordinates " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';

    fout << setw(sp) << "x" << setw(sp) << "z" << '\n';

    for (unsigned int p = 0; p < gridData_.bodyCoordinates.size(); p++)
    {
        fout << setw(sp) << gridData_.bodyCoordinates[p].x << setw(sp) << gridData_.bodyCoordinates[p].z << '\n';
    }
    for (unsigned int p = 0; p < gridData_.wallCoordinates.size(); p++)
    {
        fout << setw(sp) << gridData_.wallCoordinates[p].x << setw(sp) << gridData_.wallCoordinates[p].z << '\n';
    }

    fout.close();
}