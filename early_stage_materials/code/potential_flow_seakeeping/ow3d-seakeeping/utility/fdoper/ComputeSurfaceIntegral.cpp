#include "OW3DUtilFunctions.h"

// This is a wrapper function which switches between 2 surface-integration routines:
//
// 1. The Overture integration function
// 2. The integration scheme which acts on triangulated patches (written by Harry. B. Bingham)
//

double OW3DSeakeeping::ComputeSurfaceIntegral(Integrate &integrator, const TriangulationData &tridat, realCompositeGridFunction &u)
{
    if (tridat.patches.size() == 0)
        return integrator.surfaceIntegral(u, 0);
    else
    {
        ExtrapolateSurfaceBoundaries(u, tridat.boundaries_data.exciting);
        return OW3DSeakeeping::ComputeIntegralByTriangulation(u, tridat);
    }
}