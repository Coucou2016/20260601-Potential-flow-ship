#include "Grid.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Grid::FREE_SURFACE_TYPES OW3DSeakeeping::Grid::FindFreeSurfaceType_(const Single_boundary_data &bf)
{
    FREE_SURFACE_TYPES surfaceType = FREE_SURFACE_TYPES::BACK;

    MappedGrid mg = cg_[bf.grid];

    for (int axis = 0; axis < mg.numberOfDimensions(); axis++)
    {
        for (unsigned int side = 0; side <= 1; side++)
        {
            // Here we mean that a mapped grid which has
            // a free surface, is regarded as the "body" surface,
            // if at least one of the other sides of the same
            // grid has an exciting surface.

            if (mg.boundaryCondition()(side, axis) == 3)
            {
                surfaceType = FREE_SURFACE_TYPES::BODY;
            }
        }
    }

    return surfaceType;
}