#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::ExtrapolateSurfaceBoundaries(realCompositeGridFunction &u, vector<Single_boundary_data> bdata)
{
    // This code is a quick fix for filling out the ghost layers at the body surface. It is
    // simply a zeroth-order extrapolation which uses values at the surface boundaries.
    // This routine is called inside "ComputeIntegralByTriangulation" function, and before
    // the interpolation on the surface pacthes. Depending on the grid, pacthes and the interpolation width,
    // the Overture interpolation scheme might employ values at the ghost layers on the surface.

    for (unsigned int surface = 0; surface < bdata.size(); surface++)
    {
        const Single_boundary_data &be = bdata[surface];
        const vector<Index> &Is = be.surface_indices;

        if (Is[0].length() == 1)
        {
            u[be.grid](Is[0], Is[1].getBase() - 1, Is[2]) = u[be.grid](Is[0], Is[1].getBase(), Is[2]);
            u[be.grid](Is[0], Is[1].getBase() - 2, Is[2]) = u[be.grid](Is[0], Is[1].getBase(), Is[2]);
            u[be.grid](Is[0], Is[1].getBound() + 1, Is[2]) = u[be.grid](Is[0], Is[1].getBound(), Is[2]);
            u[be.grid](Is[0], Is[1].getBound() + 2, Is[2]) = u[be.grid](Is[0], Is[1].getBound(), Is[2]);
            u[be.grid](Is[0], Is[1], Is[2].getBase() - 1) = u[be.grid](Is[0], Is[1], Is[2].getBase());
            u[be.grid](Is[0], Is[1], Is[2].getBase() - 2) = u[be.grid](Is[0], Is[1], Is[2].getBase());
            u[be.grid](Is[0], Is[1], Is[2].getBound() + 1) = u[be.grid](Is[0], Is[1], Is[2].getBound());
            u[be.grid](Is[0], Is[1], Is[2].getBound() + 2) = u[be.grid](Is[0], Is[1], Is[2].getBound());
            // Corners
            u[be.grid](Is[0], Is[1].getBase() - 1, Is[2].getBase() - 1) = u[be.grid](Is[0], Is[1].getBase(), Is[2].getBase());
            u[be.grid](Is[0], Is[1].getBase() - 1, Is[2].getBase() - 2) = u[be.grid](Is[0], Is[1].getBase(), Is[2].getBase());
            u[be.grid](Is[0], Is[1].getBase() - 2, Is[2].getBase() - 1) = u[be.grid](Is[0], Is[1].getBase(), Is[2].getBase());
            u[be.grid](Is[0], Is[1].getBase() - 2, Is[2].getBase() - 2) = u[be.grid](Is[0], Is[1].getBase(), Is[2].getBase());
            u[be.grid](Is[0], Is[1].getBase() - 1, Is[2].getBound() + 1) = u[be.grid](Is[0], Is[1].getBase(), Is[2].getBound());
            u[be.grid](Is[0], Is[1].getBase() - 1, Is[2].getBound() + 2) = u[be.grid](Is[0], Is[1].getBase(), Is[2].getBound());
            u[be.grid](Is[0], Is[1].getBase() - 2, Is[2].getBound() + 1) = u[be.grid](Is[0], Is[1].getBase(), Is[2].getBound());
            u[be.grid](Is[0], Is[1].getBase() - 2, Is[2].getBound() + 2) = u[be.grid](Is[0], Is[1].getBase(), Is[2].getBound());
            u[be.grid](Is[0], Is[1].getBound() + 1, Is[2].getBound() + 1) = u[be.grid](Is[0], Is[1].getBound(), Is[2].getBound());
            u[be.grid](Is[0], Is[1].getBound() + 1, Is[2].getBound() + 2) = u[be.grid](Is[0], Is[1].getBound(), Is[2].getBound());
            u[be.grid](Is[0], Is[1].getBound() + 2, Is[2].getBound() + 1) = u[be.grid](Is[0], Is[1].getBound(), Is[2].getBound());
            u[be.grid](Is[0], Is[1].getBound() + 2, Is[2].getBound() + 2) = u[be.grid](Is[0], Is[1].getBound(), Is[2].getBound());
            u[be.grid](Is[0], Is[1].getBound() + 1, Is[2].getBase() - 1) = u[be.grid](Is[0], Is[1].getBound(), Is[2].getBase());
            u[be.grid](Is[0], Is[1].getBound() + 1, Is[2].getBase() - 2) = u[be.grid](Is[0], Is[1].getBound(), Is[2].getBase());
            u[be.grid](Is[0], Is[1].getBound() + 2, Is[2].getBase() - 1) = u[be.grid](Is[0], Is[1].getBound(), Is[2].getBase());
            u[be.grid](Is[0], Is[1].getBound() + 2, Is[2].getBase() - 2) = u[be.grid](Is[0], Is[1].getBound(), Is[2].getBase());
        }
        else if (Is[1].length() == 1)
        {
            u[be.grid](Is[0].getBase() - 1, Is[1], Is[2]) = u[be.grid](Is[0].getBase(), Is[1], Is[2]);
            u[be.grid](Is[0].getBase() - 2, Is[1], Is[2]) = u[be.grid](Is[0].getBase(), Is[1], Is[2]);
            u[be.grid](Is[0].getBound() + 1, Is[1], Is[2]) = u[be.grid](Is[0].getBound(), Is[1], Is[2]);
            u[be.grid](Is[0].getBound() + 2, Is[1], Is[2]) = u[be.grid](Is[0].getBound(), Is[1], Is[2]);
            u[be.grid](Is[0], Is[1], Is[2].getBase() - 1) = u[be.grid](Is[0], Is[1], Is[2].getBase());
            u[be.grid](Is[0], Is[1], Is[2].getBase() - 2) = u[be.grid](Is[0], Is[1], Is[2].getBase());
            u[be.grid](Is[0], Is[1], Is[2].getBound() + 1) = u[be.grid](Is[0], Is[1], Is[2].getBound());
            u[be.grid](Is[0], Is[1], Is[2].getBound() + 2) = u[be.grid](Is[0], Is[1], Is[2].getBound());
            // Corners
            u[be.grid](Is[0].getBase() - 1, Is[1], Is[2].getBase() - 1) = u[be.grid](Is[0].getBase(), Is[1], Is[2].getBase());
            u[be.grid](Is[0].getBase() - 1, Is[1], Is[2].getBase() - 2) = u[be.grid](Is[0].getBase(), Is[1], Is[2].getBase());
            u[be.grid](Is[0].getBase() - 2, Is[1], Is[2].getBase() - 1) = u[be.grid](Is[0].getBase(), Is[1], Is[2].getBase());
            u[be.grid](Is[0].getBase() - 2, Is[1], Is[2].getBase() - 2) = u[be.grid](Is[0].getBase(), Is[1], Is[2].getBase());
            u[be.grid](Is[0].getBase() - 1, Is[1], Is[2].getBound() + 1) = u[be.grid](Is[0].getBase(), Is[1], Is[2].getBound());
            u[be.grid](Is[0].getBase() - 1, Is[1], Is[2].getBound() + 2) = u[be.grid](Is[0].getBase(), Is[1], Is[2].getBound());
            u[be.grid](Is[0].getBase() - 2, Is[1], Is[2].getBound() + 1) = u[be.grid](Is[0].getBase(), Is[1], Is[2].getBound());
            u[be.grid](Is[0].getBase() - 2, Is[1], Is[2].getBound() + 2) = u[be.grid](Is[0].getBase(), Is[1], Is[2].getBound());
            u[be.grid](Is[0].getBound() + 1, Is[1], Is[2].getBound() + 1) = u[be.grid](Is[0].getBound(), Is[1], Is[2].getBound());
            u[be.grid](Is[0].getBound() + 1, Is[1], Is[2].getBound() + 2) = u[be.grid](Is[0].getBound(), Is[1], Is[2].getBound());
            u[be.grid](Is[0].getBound() + 2, Is[1], Is[2].getBound() + 1) = u[be.grid](Is[0].getBound(), Is[1], Is[2].getBound());
            u[be.grid](Is[0].getBound() + 2, Is[1], Is[2].getBound() + 2) = u[be.grid](Is[0].getBound(), Is[1], Is[2].getBound());
            u[be.grid](Is[0].getBound() + 1, Is[1], Is[2].getBase() - 1) = u[be.grid](Is[0].getBound(), Is[1], Is[2].getBase());
            u[be.grid](Is[0].getBound() + 1, Is[1], Is[2].getBase() - 2) = u[be.grid](Is[0].getBound(), Is[1], Is[2].getBase());
            u[be.grid](Is[0].getBound() + 2, Is[1], Is[2].getBase() - 1) = u[be.grid](Is[0].getBound(), Is[1], Is[2].getBase());
            u[be.grid](Is[0].getBound() + 2, Is[1], Is[2].getBase() - 2) = u[be.grid](Is[0].getBound(), Is[1], Is[2].getBase());
        }
        else
        {
            u[be.grid](Is[0].getBase() - 1, Is[1], Is[2]) = u[be.grid](Is[0].getBase(), Is[1], Is[2]);
            u[be.grid](Is[0].getBase() - 2, Is[1], Is[2]) = u[be.grid](Is[0].getBase(), Is[1], Is[2]);
            u[be.grid](Is[0].getBound() + 1, Is[1], Is[2]) = u[be.grid](Is[0].getBound(), Is[1], Is[2]);
            u[be.grid](Is[0].getBound() + 2, Is[1], Is[2]) = u[be.grid](Is[0].getBound(), Is[1], Is[2]);
            u[be.grid](Is[0], Is[1].getBase() - 1, Is[2]) = u[be.grid](Is[0], Is[1].getBase(), Is[2]);
            u[be.grid](Is[0], Is[1].getBase() - 2, Is[2]) = u[be.grid](Is[0], Is[1].getBase(), Is[2]);
            u[be.grid](Is[0], Is[1].getBound() + 1, Is[2]) = u[be.grid](Is[0], Is[1].getBound(), Is[2]);
            u[be.grid](Is[0], Is[1].getBound() + 2, Is[2]) = u[be.grid](Is[0], Is[1].getBound(), Is[2]);
            // Corners
            u[be.grid](Is[0].getBase() - 1, Is[1].getBase() - 1, Is[2]) = u[be.grid](Is[0].getBase(), Is[1].getBase(), Is[2]);
            u[be.grid](Is[0].getBase() - 1, Is[1].getBase() - 2, Is[2]) = u[be.grid](Is[0].getBase(), Is[1].getBase(), Is[2]);
            u[be.grid](Is[0].getBase() - 2, Is[1].getBase() - 1, Is[2]) = u[be.grid](Is[0].getBase(), Is[1].getBase(), Is[2]);
            u[be.grid](Is[0].getBase() - 2, Is[1].getBase() - 2, Is[2]) = u[be.grid](Is[0].getBase(), Is[1].getBase(), Is[2]);
            u[be.grid](Is[0].getBase() - 1, Is[1].getBound() + 1, Is[2]) = u[be.grid](Is[0].getBase(), Is[1].getBound(), Is[2]);
            u[be.grid](Is[0].getBase() - 1, Is[1].getBound() + 2, Is[2]) = u[be.grid](Is[0].getBase(), Is[1].getBound(), Is[2]);
            u[be.grid](Is[0].getBase() - 2, Is[1].getBound() + 1, Is[2]) = u[be.grid](Is[0].getBase(), Is[1].getBound(), Is[2]);
            u[be.grid](Is[0].getBase() - 2, Is[1].getBound() + 2, Is[2]) = u[be.grid](Is[0].getBase(), Is[1].getBound(), Is[2]);
            u[be.grid](Is[0].getBound() + 1, Is[1].getBound() + 1, Is[2]) = u[be.grid](Is[0].getBound(), Is[1].getBound(), Is[2]);
            u[be.grid](Is[0].getBound() + 1, Is[1].getBound() + 2, Is[2]) = u[be.grid](Is[0].getBound(), Is[1].getBound(), Is[2]);
            u[be.grid](Is[0].getBound() + 2, Is[1].getBound() + 1, Is[2]) = u[be.grid](Is[0].getBound(), Is[1].getBound(), Is[2]);
            u[be.grid](Is[0].getBound() + 2, Is[1].getBound() + 2, Is[2]) = u[be.grid](Is[0].getBound(), Is[1].getBound(), Is[2]);
            u[be.grid](Is[0].getBound() + 1, Is[1].getBase() - 1, Is[2]) = u[be.grid](Is[0].getBound(), Is[1].getBase(), Is[2]);
            u[be.grid](Is[0].getBound() + 1, Is[1].getBase() - 2, Is[2]) = u[be.grid](Is[0].getBound(), Is[1].getBase(), Is[2]);
            u[be.grid](Is[0].getBound() + 2, Is[1].getBase() - 1, Is[2]) = u[be.grid](Is[0].getBound(), Is[1].getBase(), Is[2]);
            u[be.grid](Is[0].getBound() + 2, Is[1].getBase() - 2, Is[2]) = u[be.grid](Is[0].getBound(), Is[1].getBase(), Is[2]);
        }
    }
}