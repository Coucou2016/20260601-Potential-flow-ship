#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::PrintDoubleBodyForces_()
{
    ofstream fout(base_force_file_, ios::out);
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);
    fout << "Double body forces on the body" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
    fout << std::right
         << data_.dbForces.fx << '\n'
         << data_.dbForces.fy << '\n'
         << data_.dbForces.fz << '\n'
         << data_.dbForces.mx << '\n'
         << data_.dbForces.my << '\n'
         << data_.dbForces.mz << '\n';
    fout.close();
}