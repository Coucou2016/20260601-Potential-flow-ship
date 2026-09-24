#include "Grid.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Grid::PrintSymmetryCoefficients_() const
{
    ofstream fout(grid_symcof_file_);
    int wb = OW3DSeakeeping::print_width;
    fout << "Grid symmetry coefficients " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
    unsigned int nresp = UserInput.responses.size(); // make a more descriptive name

    for (unsigned int i = 0; i < runs_.size(); i++)
    {
        string run = OW3DSeakeeping::ModeStrings.at(runs_[i].mode); // make a more descriptive name

        fout << setw(wb) << run << ":";

        for (unsigned int j = 0; j < nresp; j++)
        {
            string response = OW3DSeakeeping::ModeStrings.at(UserInput.responses[j]); // make a more descriptive name!
            fout << setw(wb) << response << " = " << gridData_.symmetryCoefficients[i][j];
        }

        fout << '\n';
    }

    fout.close();
}