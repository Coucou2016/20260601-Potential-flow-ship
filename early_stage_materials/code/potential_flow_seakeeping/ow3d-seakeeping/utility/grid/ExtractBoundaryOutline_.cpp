#include "Grid.h"

vector<OW3DSeakeeping::Coordinate> OW3DSeakeeping::Grid::ExtractBoundaryOutline_(const Single_boundary_data &bf)
{
    MappedGrid mg = cg_[bf.grid];
    vector<Index> si = bf.surface_indices;

    double tol = 1e-4 * gridData_.maximum_depth; // in the case y is not exactly 0

    vector<Coordinate> AllCoordinates;
    Coordinate coordinate;
    coordinate.z = 0.0;

    for (int i = si[0].getBase(); i <= si[0].getBound(); i++)
    {
        for (int j = si[1].getBase(); j <= si[1].getBound(); j++)
        {
            for (int k = si[2].getBase(); k <= si[2].getBound(); k++)
            {
                if (fabs(mg.vertex()(i, j, k, axis2)) < tol)
                {
                    coordinate.x = mg.vertex()(i, j, k, axis1);

                    if (cg_.numberOfDimensions() != 2)
                    {
                        coordinate.z = mg.vertex()(i, j, k, axis3);
                    }

                    AllCoordinates.push_back(coordinate);
                }
            }
        }
    }

    return AllCoordinates;
}