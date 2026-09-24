#include "SecondOrder.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::SecondOrder::PrintDriftForces() const
{
    if (OW3DSeakeeping::UserInput.wave_drift)
    {
        unsigned int freqs_size = allKsAndOmegas_.omegao.size() - allKsAndOmegas_.out_start_index;
        ofstream fout;
        unsigned int wdt = OW3DSeakeeping::print_width;
        fout.setf(ios_base::scientific);
        fout.precision(OW3DSeakeeping::print_precision);
        string filename = results_folder_ + '/' + UserInput.project_name + drift_forces_file_extention;
        fout.open(filename, ios::out);
        fout << "Second order wave drift forces" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
        fout << '\t' << print_freq_line << freqs_size << endl;
        fout << '\t' << print_froude_line << UserInput.U / sqrt(UserInput.ulen * UserInput.g) << endl;
        fout << '\t' << print_beta_line << UserInput.beta << endl;
        for (unsigned int i = 0; i < nDrfNer_; i++)
        {
            for (unsigned int f = allKsAndOmegas_.out_start_index; f < flength_; f++)
                fout << allKsAndOmegas_.omegao[f] << setw(wdt) << allKsAndOmegas_.omegaeAll[f] << '\t'
                     << i + 1 << setw(wdt) << forces_nearField_(i, f) << setw(wdt) << forces_salvesen_(i, f) << setw(wdt) << forces_farField_(i, f) << endl;
        }
        fout.close();
    }
}