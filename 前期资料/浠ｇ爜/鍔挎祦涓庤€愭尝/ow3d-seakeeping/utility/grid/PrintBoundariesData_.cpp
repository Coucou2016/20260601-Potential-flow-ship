#include "Grid.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Grid::PrintBoundariesData_() const
{
    ofstream fout(grid_bdata_file_);
    int fw = OW3DSeakeeping::print_width;
    int hfw = ceil(fw / 2) + 1;
    fout << "Grid boundaries details " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';

    fout << setw(fw) << "type" << setw(hfw) << "grid" << setw(hfw) << "axis" << setw(hfw) << "side" << setw(hfw)
         << "1_base" << setw(hfw) << "1_bound" << setw(hfw) << "2_base" << setw(hfw) << "2_bound" << setw(hfw) << "3_base" << setw(hfw) << "3_bound" << '\n';

    for (unsigned int i = 0; i < gridData_.boundariesData.third_periodic.size(); ++i)
    {
        const Single_boundary_data &tp = gridData_.boundariesData.third_periodic[i];
        const vector<Index> &Is = tp.surface_indices;
        fout << setw(fw) << "third periodic" << setw(hfw) << tp.grid << setw(hfw) << tp.axis << setw(hfw) << tp.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }
    for (unsigned int i = 0; i < gridData_.boundariesData.second_periodic.size(); ++i)
    {
        const Single_boundary_data &sp = gridData_.boundariesData.second_periodic[i];
        const vector<Index> &Is = sp.surface_indices;
        fout << setw(fw) << "second periodic" << setw(hfw) << sp.grid << setw(hfw) << sp.axis << setw(hfw) << sp.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }
    for (unsigned int i = 0; i < gridData_.boundariesData.first_periodic.size(); ++i)
    {
        const Single_boundary_data &fp = gridData_.boundariesData.first_periodic[i];
        const vector<Index> &Is = fp.surface_indices;
        fout << setw(fw) << "first periodic" << setw(hfw) << fp.grid << setw(hfw) << fp.axis << setw(hfw) << fp.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }
    for (unsigned int j = 0; j < gridData_.boundariesData.interpolation.size(); ++j)
    {
        const Single_boundary_data &i = gridData_.boundariesData.interpolation[j];
        const vector<Index> &Is = i.surface_indices;
        fout << setw(fw) << "interpolation" << setw(hfw) << i.grid << setw(hfw) << i.axis << setw(hfw) << i.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }
    for (unsigned int i = 0; i < gridData_.boundariesData.free.size(); ++i)
    {
        const Single_boundary_data &f = gridData_.boundariesData.free[i];
        const vector<Index> &Is = f.surface_indices;
        fout << setw(fw) << "free" << setw(hfw) << f.grid << setw(hfw) << f.axis << setw(hfw) << f.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }
    for (unsigned int j = 0; j < gridData_.boundariesData.impermeable.size(); ++j)
    {
        const Single_boundary_data &i = gridData_.boundariesData.impermeable[j];
        const vector<Index> &Is = i.surface_indices;
        fout << setw(fw) << "impermeable" << setw(hfw) << i.grid << setw(hfw) << i.axis << setw(hfw) << i.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }
    for (unsigned int i = 0; i < gridData_.boundariesData.exciting.size(); ++i)
    {
        const Single_boundary_data &e = gridData_.boundariesData.exciting[i];
        const vector<Index> &Is = e.surface_indices;
        fout << setw(fw) << "exciting" << setw(hfw) << e.grid << setw(hfw) << e.axis << setw(hfw) << e.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }
    for (unsigned int i = 0; i < gridData_.boundariesData.absorbing.size(); ++i)
    {
        const Single_boundary_data &a = gridData_.boundariesData.absorbing[i];
        const vector<Index> &Is = a.surface_indices;
        fout << setw(fw) << "absorbing" << setw(hfw) << a.grid << setw(hfw) << a.axis << setw(hfw) << a.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }
    for (unsigned int i = 0; i < gridData_.boundariesData.symmetry.size(); ++i)
    {
        const Single_boundary_data &es = gridData_.boundariesData.symmetry[i];
        const vector<Index> &Is = es.surface_indices;
        fout << setw(fw) << "symmetry" << setw(hfw) << es.grid << setw(hfw) << es.axis << setw(hfw) << es.side << setw(hfw) << Is[axis1].getBase() << setw(hfw)
             << Is[axis1].getBound() << setw(hfw) << Is[axis2].getBase() << setw(hfw) << Is[axis2].getBound() << setw(hfw) << Is[axis3].getBase() << setw(hfw) << Is[axis3].getBound() << '\n';
    }

    fout.close();
}