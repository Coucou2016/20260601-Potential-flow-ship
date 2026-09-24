#include <iomanip>
#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::PrintPseudoImpulses_() const
{
    ofstream fout;
    int wdt = OW3DSeakeeping::print_width;
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);
    string filename = results_folder_ + '/' + UserInput.project_name + impulses_ascii_file;
    fout.open(filename, ios::out);
    if (velocity_.getLength(1) != 0)
    {
        fout << "Pseudo-impulsive body velocity" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        for (int t = 0; t < time_.getLength(1); t++)
            fout << time_(0, t) << setw(wdt) << velocity_(0, t) << endl;
    }
    else if (displacement_.getLength(1) != 0 && elevation_.getLength(1) != 0)
    {
        fout << "Pseudo-impulsive body displacement and wave elevation" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        for (int t = 0; t < time_.getLength(1); t++)
            fout << time_(0, t) << setw(wdt) << displacement_(0, t) << setw(wdt) << elevation_(0, t) << endl;
    }
    else if (displacement_.getLength(1) != 0)
    {
        fout << "Pseudo-impulsive body displacement" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        for (int t = 0; t < time_.getLength(1); t++)
            fout << time_(0, t) << setw(wdt) << displacement_(0, t) << endl;
    }
    else if (elevation_.getLength(1) != 0)
    {
        fout << "Pseudo-impulsive incident wave elevation" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        for (int t = 0; t < time_.getLength(1); t++)
            fout << time_(0, t) << setw(wdt) << elevation_(0, t) << endl;
    }
}