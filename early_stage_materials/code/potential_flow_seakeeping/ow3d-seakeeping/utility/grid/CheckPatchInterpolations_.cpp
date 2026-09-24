#include "Grid.h"
#include "Overture.h"

double OW3DSeakeeping::Grid::CheckPatchInterpolations_()
{
    realCompositeGridFunction u(cg_);
    u = 0.;
    Integrate integrator;
    integrator = GetIntegratorOverBody(cg_, gridData_.boundariesData);

    for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
    {
        const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
        const vector<Index> &Is = be.surface_indices;

        u[be.grid](Is[0], Is[1], Is[2]) = 1.0;
    }

    double SurfaceArea_with_u_0 = ComputeSurfaceIntegral(integrator, gridData_.triangulation, u);

    u = 100000000000000.0;

    for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
    {
        const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
        const vector<Index> &Is = be.surface_indices;

        u[be.grid](Is[0], Is[1], Is[2]) = 1.0;
    }

    double SurfaceArea_with_u_large = ComputeSurfaceIntegral(integrator, gridData_.triangulation, u);

    if (SurfaceArea_with_u_0 != SurfaceArea_with_u_large)
    {
        string msg = "\t Error (OW3D), Grid::CheckPatchInterpolations_.cpp.\n";
        msg = msg + "\t Some points which are not at the body surface are involved in the patch interpolation.\n";
        msg = msg + "\t Reduce the \"patch_interpolation_width\" and try again.";
        throw runtime_error(GetColoredMessage(msg, 0));
    }

    for (unsigned int p = 0; p < gridData_.triangulation.patches.size(); p++)
    {
        RealArray positionToInterpolate(gridData_.triangulation.patches[p].nodenums, 3);
        RealArray interpolated_nodes(gridData_.triangulation.patches[p].nodenums, 1);

        interpolated_nodes = 0. / 0.; // nan
        Range all;
        positionToInterpolate(all, 0) = gridData_.triangulation.patches[p].nodes_xyz(all, 0);
        positionToInterpolate(all, 1) = gridData_.triangulation.patches[p].nodes_xyz(all, 1);
        positionToInterpolate(all, 2) = gridData_.triangulation.patches[p].nodes_xyz(all, 2);
        gridData_.triangulation.patches[p].interp_object->interpolatePoints(positionToInterpolate, u, interpolated_nodes);
        if (isnan(sum(interpolated_nodes)))
        {
            string msg = "\t Error (OW3D), Grid::CheckPatchInterpolations_.cpp.\n";
            msg = msg + "\t There are some points on the patch which can't be interpolated.\n";
            msg = msg + "\t Reduce the \"patch_interpolation_width\" and try again.";
            throw runtime_error(GetColoredMessage(msg, 0));
        }
    }

    return SurfaceArea_with_u_0;
}