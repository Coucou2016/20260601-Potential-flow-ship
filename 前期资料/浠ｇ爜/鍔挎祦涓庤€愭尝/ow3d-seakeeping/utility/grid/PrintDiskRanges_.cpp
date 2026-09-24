#include "Grid.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Grid::PrintDiskRanges_() const
{
    if (OW3DSeakeeping::ow3d_surface_derivative && gridData_.nod == 3)
    {
        int sp = OW3DSeakeeping::print_width;
        int preci = OW3DSeakeeping::print_precision;
        ofstream fout;
        fout.open(grid_disk_file_);
        fout.setf(ios_base::scientific);
        fout.precision(preci);

        // print body surface ranges

        fout << "Ranges at body and free surfaces " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << "\n\n";

        for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
        {
            OW3DSeakeeping::Single_boundary_data bs = gridData_.boundariesData.exciting[surface];
            const vector<Index> &Is = bs.surface_indices;
            fout << "* ========== body surface {s" << surface << ", ";
            fout << "Is[0]:(" << Is[0].getBase() << "," << Is[0].getBound() << ")" << " "
                 << "Is[1]:(" << Is[1].getBase() << "," << Is[1].getBound() << ")" << " "
                 << "Is[2]:(" << Is[2].getBase() << "," << Is[2].getBound() << ")" << " ========== \n\n";

            for (unsigned int line = 0; line < gridData_.body_surface_disc[surface][0].size(); line++)
            {
                if (gridData_.body_surface_disc[surface][0][line].ROD.size() != 0)
                {
                    fout << "bs" << surface << " " << "line " << line << " (1st axis) ROD:\t";
                    for (unsigned int r = 0; r < gridData_.body_surface_disc[surface][0][line].ROD.size(); r++)
                    {
                        int base = gridData_.body_surface_disc[surface][0][line].ROD[r].getBase();
                        int bound = gridData_.body_surface_disc[surface][0][line].ROD[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            for (unsigned int line = 0; line < gridData_.body_surface_disc[surface][0].size(); line++)
            {
                if (gridData_.body_surface_disc[surface][0][line].RNH.size() != 0)
                {
                    fout << "bs" << surface << " " << "line " << line << " (1st axis) RNH:\t";
                    for (unsigned int r = 0; r < gridData_.body_surface_disc[surface][0][line].RNH.size(); r++)
                    {
                        int base = gridData_.body_surface_disc[surface][0][line].RNH[r].getBase();
                        int bound = gridData_.body_surface_disc[surface][0][line].RNH[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            for (unsigned int line = 0; line < gridData_.body_surface_disc[surface][0].size(); line++)
            {
                if (gridData_.body_surface_disc[surface][0][line].ROH.size() != 0)
                {
                    fout << "bs" << surface << " " << "line " << line << " (1st axis) ROH:\t";
                    for (unsigned int r = 0; r < gridData_.body_surface_disc[surface][0][line].ROH.size(); r++)
                    {
                        int base = gridData_.body_surface_disc[surface][0][line].ROH[r].getBase();
                        int bound = gridData_.body_surface_disc[surface][0][line].ROH[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            fout << '\n';
            for (unsigned int line = 0; line < gridData_.body_surface_disc[surface][1].size(); line++)
            {
                if (gridData_.body_surface_disc[surface][1][line].ROD.size() != 0)
                {
                    fout << "bs" << surface << " " << "line " << line << " (2nd axis) ROD:\t";
                    for (unsigned int r = 0; r < gridData_.body_surface_disc[surface][1][line].ROD.size(); r++)
                    {
                        int base = gridData_.body_surface_disc[surface][1][line].ROD[r].getBase();
                        int bound = gridData_.body_surface_disc[surface][1][line].ROD[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            for (unsigned int line = 0; line < gridData_.body_surface_disc[surface][1].size(); line++)
            {
                if (gridData_.body_surface_disc[surface][1][line].RNH.size() != 0)
                {
                    fout << "bs" << surface << " " << "line " << line << " (2nd axis) RNH:\t";
                    for (unsigned int r = 0; r < gridData_.body_surface_disc[surface][1][line].RNH.size(); r++)
                    {
                        int base = gridData_.body_surface_disc[surface][1][line].RNH[r].getBase();
                        int bound = gridData_.body_surface_disc[surface][1][line].RNH[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            for (unsigned int line = 0; line < gridData_.body_surface_disc[surface][1].size(); line++)
            {
                if (gridData_.body_surface_disc[surface][1][line].ROH.size() != 0)
                {
                    fout << "bs" << surface << " " << "line " << line << " (2nd axis) ROH:\t";
                    for (unsigned int r = 0; r < gridData_.body_surface_disc[surface][1][line].ROH.size(); r++)
                    {
                        int base = gridData_.body_surface_disc[surface][1][line].ROH[r].getBase();
                        int bound = gridData_.body_surface_disc[surface][1][line].ROH[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            fout << '\n';
        }
        // print free surface ranges
        for (unsigned int surface = 0; surface < gridData_.boundariesData.free.size(); surface++)
        {
            OW3DSeakeeping::Single_boundary_data bs = gridData_.boundariesData.free[surface];
            const vector<Index> &Is = bs.surface_indices;
            fout << "* ========== free surface {s" << surface << ", ";
            fout << "Is[0]:(" << Is[0].getBase() << "," << Is[0].getBound() << ")" << " "
                 << "Is[1]:(" << Is[1].getBase() << "," << Is[1].getBound() << ")" << " "
                 << "Is[2]:(" << Is[2].getBase() << "," << Is[2].getBound() << ")" << " ========== \n\n";

            for (unsigned int line = 0; line < gridData_.free_surface_disc[surface][0].size(); line++)
            {
                if (gridData_.free_surface_disc[surface][0][line].ROD.size() != 0)
                {
                    fout << "fs" << surface << " " << "line " << line << " (1st axis) ROD:\t";
                    for (unsigned int r = 0; r < gridData_.free_surface_disc[surface][0][line].ROD.size(); r++)
                    {
                        int base = gridData_.free_surface_disc[surface][0][line].ROD[r].getBase();
                        int bound = gridData_.free_surface_disc[surface][0][line].ROD[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            for (unsigned int line = 0; line < gridData_.free_surface_disc[surface][0].size(); line++)
            {
                if (gridData_.free_surface_disc[surface][0][line].RNH.size() != 0)
                {
                    fout << "fs" << surface << " " << "line " << line << " (1st axis) RNH:\t";
                    for (unsigned int r = 0; r < gridData_.free_surface_disc[surface][0][line].RNH.size(); r++)
                    {
                        int base = gridData_.free_surface_disc[surface][0][line].RNH[r].getBase();
                        int bound = gridData_.free_surface_disc[surface][0][line].RNH[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            for (unsigned int line = 0; line < gridData_.free_surface_disc[surface][0].size(); line++)
            {
                if (gridData_.free_surface_disc[surface][0][line].ROH.size() != 0)
                {
                    fout << "fs" << surface << " " << "line " << line << " (1st axis) ROH:\t";
                    for (unsigned int r = 0; r < gridData_.free_surface_disc[surface][0][line].ROH.size(); r++)
                    {
                        int base = gridData_.free_surface_disc[surface][0][line].ROH[r].getBase();
                        int bound = gridData_.free_surface_disc[surface][0][line].ROH[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            fout << '\n';
            for (unsigned int line = 0; line < gridData_.free_surface_disc[surface][1].size(); line++)
            {
                if (gridData_.free_surface_disc[surface][1][line].ROD.size() != 0)
                {
                    fout << "fs" << surface << " " << "line " << line << " (2nd axis) ROD:\t";
                    for (unsigned int r = 0; r < gridData_.free_surface_disc[surface][1][line].ROD.size(); r++)
                    {
                        int base = gridData_.free_surface_disc[surface][1][line].ROD[r].getBase();
                        int bound = gridData_.free_surface_disc[surface][1][line].ROD[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            for (unsigned int line = 0; line < gridData_.free_surface_disc[surface][1].size(); line++)
            {
                if (gridData_.free_surface_disc[surface][1][line].RNH.size() != 0)
                {
                    fout << "fs" << surface << " " << "line " << line << " (2nd axis) RNH:\t";
                    for (unsigned int r = 0; r < gridData_.free_surface_disc[surface][1][line].RNH.size(); r++)
                    {
                        int base = gridData_.free_surface_disc[surface][1][line].RNH[r].getBase();
                        int bound = gridData_.free_surface_disc[surface][1][line].RNH[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            for (unsigned int line = 0; line < gridData_.free_surface_disc[surface][1].size(); line++)
            {
                if (gridData_.free_surface_disc[surface][1][line].ROH.size() != 0)
                {
                    fout << "fs" << surface << " " << "line " << line << " (2nd axis) ROH:\t";
                    for (unsigned int r = 0; r < gridData_.free_surface_disc[surface][1][line].ROH.size(); r++)
                    {
                        int base = gridData_.free_surface_disc[surface][1][line].ROH[r].getBase();
                        int bound = gridData_.free_surface_disc[surface][1][line].ROH[r].getBound();
                        fout << base << ',' << bound << "\t";
                    }
                    fout << '\n';
                }
            }
            fout << '\n';
        }

        fout.close();
    }
}