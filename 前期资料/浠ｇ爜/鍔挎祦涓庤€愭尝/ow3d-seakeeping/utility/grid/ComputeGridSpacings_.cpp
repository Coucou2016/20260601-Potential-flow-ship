//
// Here we search along both directions of the surface, and store the corresponding grid spacings.
// The spacings are calculated simply as the distance between two points by sqrt((x2-x1)^2 (y2-y1)^2 + (z2-z1)^2).
// The minimum, maximum and average spacings are returened as spacings[0], spacings[1] and spacings[2].
//

#include "Grid.h"
#include <numeric>

vector<double> OW3DSeakeeping::Grid::ComputeGridSpacingsOnSurface_(vector<Single_boundary_data> surface_data)
{
    vector<double> all_grid_spacings_on_surfaces;
    vector<double> spacings(3);
    for (unsigned int surface = 0; surface < surface_data.size(); surface++)
    {
        const Single_boundary_data &bs = surface_data[surface];
        const vector<Index> &Is = bs.surface_indices;
        const MappedGrid &mg = cg_[bs.grid];
        Index I0, I1, I2;
        getIndex(mg.dimension(), I0, I1, I2);
        const RealArray &v = mg.vertex();
        double z1, z2;
        z1 = z2 = 0;

        if (Is[0].length() == 1 && I0.length() > 1)
        {
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
            {
                for (int k = Is[2].getBase(); k < Is[2].getBound(); k++)
                {
                    if (mg.mask()(Is[0].getBase(), j, k + 1) > 0 and mg.mask()(Is[0].getBase(), j, k) > 0) // just discretization points
                    {
                        all_grid_spacings_on_surfaces.push_back(sqrt(
                            pow(v(Is[0].getBase(), j, k + 1, axis1) - v(Is[0].getBase(), j, k, axis1), 2) +
                            pow(v(Is[0].getBase(), j, k + 1, axis2) - v(Is[0].getBase(), j, k, axis2), 2) +
                            pow(v(Is[0].getBase(), j, k + 1, axis3) - v(Is[0].getBase(), j, k, axis3), 2)));
                    }
                }
            }
            for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
            {
                for (int j = Is[1].getBase(); j < Is[1].getBound(); j++)
                {
                    if (mg.mask()(Is[0].getBase(), j + 1, k) > 0 and mg.mask()(Is[0].getBase(), j, k) > 0) // just discretization points
                    {
                        if (mg.numberOfDimensions() == 3)
                        {
                            z2 = v(Is[0].getBase(), j + 1, k, axis3);
                            z1 = v(Is[0].getBase(), j, k, axis3);
                        }
                        all_grid_spacings_on_surfaces.push_back(sqrt(
                            pow(v(Is[0].getBase(), j + 1, k, axis1) - v(Is[0].getBase(), j, k, axis1), 2) +
                            pow(v(Is[0].getBase(), j + 1, k, axis2) - v(Is[0].getBase(), j, k, axis2), 2) +
                            pow(z2 - z1, 2)));
                    }
                }
            }
        }
        if (Is[1].length() == 1 && I1.length() > 1)
        {
            for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
            {
                for (int k = Is[2].getBase(); k < Is[2].getBound(); k++)
                {
                    if (mg.mask()(i, Is[1].getBase(), k + 1) > 0 and mg.mask()(i, Is[1].getBase(), k) > 0) // just discretization points
                    {
                        all_grid_spacings_on_surfaces.push_back(sqrt(
                            pow(v(i, Is[1].getBase(), k + 1, axis1) - v(i, Is[1].getBase(), k, axis1), 2) +
                            pow(v(i, Is[1].getBase(), k + 1, axis2) - v(i, Is[1].getBase(), k, axis2), 2) +
                            pow(v(i, Is[1].getBase(), k + 1, axis3) - v(i, Is[1].getBase(), k, axis3), 2)));
                    }
                }
            }
            for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
            {
                for (int i = Is[0].getBase(); i < Is[0].getBound(); i++)
                {
                    if (mg.mask()(i + 1, Is[1].getBase(), k) > 0 and mg.mask()(i, Is[1].getBase(), k) > 0) // just discretization points
                    {
                        if (mg.numberOfDimensions() == 3)
                        {
                            z2 = v(i + 1, Is[1].getBase(), k, axis3);
                            z1 = v(i, Is[1].getBase(), k, axis3);
                        }
                        all_grid_spacings_on_surfaces.push_back(sqrt(
                            pow(v(i + 1, Is[1].getBase(), k, axis1) - v(i, Is[1].getBase(), k, axis1), 2) +
                            pow(v(i + 1, Is[1].getBase(), k, axis2) - v(i, Is[1].getBase(), k, axis2), 2) +
                            pow(z2 - z1, 2)));
                    }
                }
            }
        }
        if (Is[2].length() == 1 && I2.length() > 1)
        {
            for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
            {
                for (int j = Is[1].getBase(); j < Is[1].getBound(); j++)
                {
                    if (mg.mask()(i, j + 1, Is[2].getBase()) > 0 and mg.mask()(i, j, Is[2].getBase()) > 0) // just discretization points
                    {
                        all_grid_spacings_on_surfaces.push_back(sqrt(
                            pow(v(i, j + 1, Is[2].getBase(), axis1) - v(i, j, Is[2].getBase(), axis1), 2) +
                            pow(v(i, j + 1, Is[2].getBase(), axis2) - v(i, j, Is[2].getBase(), axis2), 2) +
                            pow(v(i, j + 1, Is[2].getBase(), axis3) - v(i, j, Is[2].getBase(), axis3), 2)));
                    }
                }
            }
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
            {
                for (int i = Is[0].getBase(); i < Is[0].getBound(); i++)
                {
                    if (mg.mask()(i + 1, j, Is[2].getBase()) > 0 and mg.mask()(i, j, Is[2].getBase()) > 0) // just discretization points
                    {
                        all_grid_spacings_on_surfaces.push_back(sqrt(
                            pow(v(i + 1, j, Is[2].getBase(), axis1) - v(i, j, Is[2].getBase(), axis1), 2) +
                            pow(v(i + 1, j, Is[2].getBase(), axis2) - v(i, j, Is[2].getBase(), axis2), 2) +
                            pow(v(i + 1, j, Is[2].getBase(), axis3) - v(i, j, Is[2].getBase(), axis3), 2)));
                    }
                }
            }
        }

    } // end surface loop

    spacings[0] = *min_element(all_grid_spacings_on_surfaces.begin(), all_grid_spacings_on_surfaces.end());
    spacings[1] = *max_element(all_grid_spacings_on_surfaces.begin(), all_grid_spacings_on_surfaces.end());
    spacings[2] = accumulate(all_grid_spacings_on_surfaces.begin(), all_grid_spacings_on_surfaces.end(), 0.0) / all_grid_spacings_on_surfaces.size();

    return spacings;
}
