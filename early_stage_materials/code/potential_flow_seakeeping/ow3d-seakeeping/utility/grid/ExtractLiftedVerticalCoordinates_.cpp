#include "Grid.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Grid::ExtractLiftedVerticalCoordinates_()
{
    Index Iwat; // The waterline index.
    Index Isub; // The first submerged index.

    // Here we loop over the body surfaces and select thoes which are connected
    // to the free surface. Then the nformation regarding the vertical coordinate
    // along the body surface is extracted.

    vector<realArray> submerged_y_coordinates;

    for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
    {
        Range all;

        vector<Index> vIndices;
        vIndices.resize(3);

        const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
        const vector<Index> &Is = be.surface_indices;
        const MappedGrid &mg = cg_[be.grid];
        const RealArray &v = mg.vertex();

        RealArray y(Is[0], Is[1], Is[2]);

        y = v(Is[0], Is[1], Is[2], axis2);

        if (gridData_.bodySurfaceTypes[surface] == BODY_SURFACE_TYPES::TOP)
        {
            vIndices[0] = Is[0]; // the length of one of these indices is already 1. We need
            vIndices[1] = Is[1]; // to determine which one of the other two should be used to
            vIndices[2] = Is[2]; // go in to the ocean! (i.e along the vertical direction).

            for (int axis = 0; axis < mg.numberOfDimensions(); axis++)
            {
                for (unsigned int side = 0; side <= 1; side++)
                {
                    if (mg.boundaryCondition()(side, axis) == gridData_.boundaryTypes.free)
                    {
                        if (side == 0)
                            Isub = Index(Is[axis].getBase() + 1, 1); // 1 is the count. (+1 because we want to get the next submerged point)
                        if (side == 1)
                            Isub = Index(Is[axis].getBound() - 1, 1); // 1 is the count. (-1 because we want to get the next submerged point)

                        if (side == 0)
                            Iwat = Index(Is[axis].getBase(), 1); // 1 is the count.
                        if (side == 1)
                            Iwat = Index(Is[axis].getBound(), 1); // 1 is the count.

                        if (axis == 0)
                            vIndices[0] = Iwat; // Then with index "0" we can dive in to the sea!
                        if (axis == 1)
                            vIndices[1] = Iwat; // Then with index "1" we can dive in to the sea!
                        if (axis == 2)
                            vIndices[2] = Iwat; // Then with index "2" we can dive in to the sea!
                    }
                }
            }

            if (vIndices[0].getLength() != 1 and vIndices[1] == Iwat)
            {
                y(all, Iwat, Is[2]) = 0.5 * y(all, Isub, Is[2]);
            }
            else if (vIndices[0].getLength() != 1 and vIndices[2] == Iwat)
            {
                y(all, Is[1], Iwat) = 0.5 * y(all, Is[1], Isub);
            }
            //
            if (vIndices[1].getLength() != 1 and vIndices[0] == Iwat)
            {
                y(Iwat, all, Is[2]) = 0.5 * y(Isub, all, Is[2]);
            }
            else if (vIndices[1].getLength() != 1 and vIndices[2] == Iwat)
            {
                y(Is[0], all, Iwat) = 0.5 * y(Is[0], all, Isub);
            }
            //
            if (vIndices[2].getLength() != 1 and vIndices[0] == Iwat)
            {
                y(Iwat, Is[1], all) = 0.5 * y(Isub, Is[1], all);
            }
            else if (vIndices[2].getLength() != 1 and vIndices[1] == Iwat)
            {
                y(Is[0], Iwat, all) = 0.5 * y(Is[0], Isub, all);
            }
        }

        submerged_y_coordinates.push_back(y);

    } // End of loop over the body surfaces

    gridData_.all_submerged_ys = submerged_y_coordinates;
}