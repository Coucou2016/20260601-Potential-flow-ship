#include "Grid.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Grid::PrintGridFeatures() const
{
     ofstream fout(grid_data_file_, ios::out);
     fout.setf(ios_base::scientific);
     fout.precision(OW3DSeakeeping::print_precision);
     fout << "Grid data " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
     fout << "grid spacial order ------------------------- :" << gridData_.order_space << '\n'
          << "number of component grids ------------------ :" << gridData_.nog << '\n'
          << "number of dimensions ----------------------- :" << gridData_.nod << '\n'
          << "maximum depth ------------------------------ :" << gridData_.maximum_depth << '\n'
          << "minimum grid spacing at the free surface --- :" << gridData_.minimum_spacing_free << '\n'
          << "average grid spacing at the waterline ------ :" << gridData_.avgWl_spacing << '\n'
          << "maximum grid spacing at the waterline ------ :" << gridData_.maxWl_spacing << '\n'
          << "minimum grid spacing at the waterline ------ :" << gridData_.minWl_spacing << '\n'
          << "maximum grid spacing on the body ----------- :" << gridData_.maximum_spacing_body << '\n'
          << "minimum grid spacing on the body ----------- :" << gridData_.minimum_spacing_body << '\n'
          << "maximun wave number ------------------------ :" << gridData_.kMax << '\n'
          << "draft of the body -------------------------- :" << gridData_.draft << '\n'
          << "maximum body extension along x axis -------- :" << gridData_.maximum_body_length << '\n'
          << "maximum body width ------------------------- :" << gridData_.maximum_body_width << '\n'
          << "maximum domain extensions ------------------ :" << gridData_.maximum_extension << endl;

     fout.close();

     PrintWaterlineData_();
     PrintBoundariesData_();
     PrintWallAndBodyCoordinates_();
     PrintSymmetryCoefficients_();
     PrintDiskRanges_();
}