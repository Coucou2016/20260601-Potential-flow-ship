#include "Grid.h"

OW3DSeakeeping::Grid::BODY_SURFACE_TYPES OW3DSeakeeping::Grid::FindBodySurfaceType_(const Single_boundary_data &be)
{
    BODY_SURFACE_TYPES surfaceType = BODY_SURFACE_TYPES::BOTTOM;

    MappedGrid mg = cg_[be.grid];

    for (int axis = 0; axis < mg.numberOfDimensions(); axis++)
    {
        for (unsigned int side = 0; side <= 1; side++)
        {
            // Here we mean that a mapped grid which has
            // a body surface, is regarded as the "top" surface,
            // if at least one of the other sides of the same
            // grid has a free surface.

            if (mg.boundaryCondition()(side, axis) == 1)
            {
                surfaceType = BODY_SURFACE_TYPES::TOP;
            }
        }
    }

    return surfaceType;
}