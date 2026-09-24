#include "OW3DUtilFunctions.h"
#include <numeric>
#include "Grid.h"

double OW3DSeakeeping::ComputeIntegralByTriangulation(RealCompositeGridFunction &u, const TriangulationData &tridat)
{
    double S = 0.;

    for (unsigned int p = 0; p < tridat.patches.size(); p++)
    {
        RealArray positionToInterpolate(tridat.patches[p].nodenums, 3);
        RealArray interpolated_nodes(tridat.patches[p].nodenums, 1);

        interpolated_nodes = 0.;
        Range all;
        positionToInterpolate(all, 0) = tridat.patches[p].nodes_xyz(all, 0);
        positionToInterpolate(all, 1) = tridat.patches[p].nodes_xyz(all, 1);
        positionToInterpolate(all, 2) = tridat.patches[p].nodes_xyz(all, 2);
        tridat.patches[p].interp_object->interpolatePoints(positionToInterpolate, u, interpolated_nodes);

        S += sum(tridat.patches[p].Ivec * tridat.patches[p].ds * interpolated_nodes);
    }

    return S;
}