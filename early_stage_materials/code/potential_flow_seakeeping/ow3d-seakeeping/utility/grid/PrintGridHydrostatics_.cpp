#include "Grid.h"
#include "OW3DConstants.h"
#include <iomanip>

namespace OW3DSeakeeping
{
     string GetModePrintIndex(unsigned int i)
     {
          string I;
          switch (i)
          {
          case 1:
               I = '3';
               break;
          case 2:
               I = '2';
               break;
          case 4:
               I = '6';
               break;
          case 5:
               I = '5';
               break;
          default:
               I = to_string(i + 1);
               break;
          }
          return I;
     }
}

void OW3DSeakeeping::Grid::PrintGridHydrostatics_() const
{
     ofstream fout(grid_hydro_file_, ios::out);
     unsigned int width = OW3DSeakeeping::print_width;
     fout.setf(ios_base::scientific);
     fout.precision(OW3DSeakeeping::print_precision);
     fout << "Grid hydrostatics " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << "\n\n";
     fout << " Submerged volume (x)" << setw(width) << gridData_.hrs.volx << '\n'
          << " Submerged volume (y)" << setw(width) << gridData_.hrs.volz << '\n'
          << " Submerged volume (z)" << setw(width) << gridData_.hrs.voly << '\n'
          << " Submerged volume    " << setw(width) << gridData_.hrs.VOLM << '\n'
          << " Mass                " << setw(width) << gridData_.hrs.MASS << '\n'
          << " Wetted surface      " << setw(width) << gridData_.hrs.SBSF << '\n'
          << " Center of buoyancy x" << setw(width) << gridData_.hrs.xb << '\n'
          << " Center of buoyancy y" << setw(width) << gridData_.hrs.zb << '\n'
          << " Center of buoyancy z" << setw(width) << gridData_.hrs.yb << "\n\n";

     for (unsigned int i = 0; i < totalNumberOfModes_; i++)
     {
          unsigned int k = i;
          string I = GetModePrintIndex(i);
          if (i == 1 || i == 4)
          {
               k = i + 1;
               I = GetModePrintIndex(k);
          }
          if (i == 2 || i == 5)
          {
               k = i - 1;
               I = GetModePrintIndex(k);
          }
          for (unsigned int j = 0; j < totalNumberOfModes_; j++)
          {
               double c = gridData_.hrs.complete_hydro_matrix[k][j];
               string J = GetModePrintIndex(j);
               if (j == 1 || j == 4)
               {
                    c = gridData_.hrs.complete_hydro_matrix[k][j + 1];
                    J = GetModePrintIndex(j + 1);
               }
               if (j == 2 || j == 5)
               {
                    c = gridData_.hrs.complete_hydro_matrix[k][j - 1];
                    J = GetModePrintIndex(j - 1);
               }
               c = ((I == "5" && J != "5") || (I != "5" && J == "5")) ? -c : c;
               fout << '\t' << I << '\t' << J << '\t' << setw(width) << c << endl;
          }
     }

     fout.close();
}