#include "Grid.h"
#include "OW3DConstants.h"

vector<Index> GetSurfaceIndicesWithGhosts(const vector<Index> Is, const vector<Index> &I)
{
    vector<Index> It(3);

    if (Is[0].length() == 1 && I[0].length() > 1)
    {
        It[0] = Is[0];
        It[1] = I[1];
        It[2] = I[2];
    }
    else if (Is[1].length() == 1 && I[1].length() > 1)
    {
        It[0] = I[0];
        It[1] = Is[1];
        It[2] = I[2];
    }
    else if (Is[2].length() == 1 && I[2].length() > 1)
    {
        It[0] = I[0];
        It[1] = I[1];
        It[2] = Is[2];
    }
    else
        throw runtime_error(OW3DSeakeeping::GetColoredMessage("\n\t Error (OW3D), Grid::ExtractBoundariesData_.cpp\n\t Something is completely wrong!", 0));

    return It;
}

void OW3DSeakeeping::Grid::ExtractBoundariesData_()
{
    Single_boundary_data boundary_data;

    for (int grid = 0; grid < gridData_.nog; ++grid)
    {
        const MappedGrid &mg = cg_[grid];
        const IntegerArray &bc = mg.boundaryCondition();
        const IntegerArray &gir = mg.gridIndexRange();

        for (int axis = axis1; axis < gridData_.nod; ++axis)
        {
            for (int side = Start; side <= End; ++side)
            {
                boundary_data = ExtractBoundaryData_(grid, axis, side, gir);

                if (bc(side, axis) == gridData_.boundaryTypes.third_periodic)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.third_periodic.push_back(boundary_data);
                }
                else if (bc(side, axis) == gridData_.boundaryTypes.second_periodic)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.second_periodic.push_back(boundary_data);
                }
                else if (bc(side, axis) == gridData_.boundaryTypes.first_periodic)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.first_periodic.push_back(boundary_data);
                }
                else if (bc(side, axis) == gridData_.boundaryTypes.interpolation)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.interpolation.push_back(boundary_data);
                }
                else if (bc(side, axis) == gridData_.boundaryTypes.free)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.free.push_back(boundary_data);
                }
                else if (bc(side, axis) == gridData_.boundaryTypes.impermeable)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.impermeable.push_back(boundary_data);
                }
                else if (bc(side, axis) == gridData_.boundaryTypes.exciting)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.exciting.push_back(boundary_data);
                }
                else if (bc(side, axis) == gridData_.boundaryTypes.absorbing)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.absorbing.push_back(boundary_data);
                }
                else if (bc(side, axis) == gridData_.boundaryTypes.symmetry)
                {
                    vector<Index> I(3);
                    getIndex(mg.dimension(), I[0], I[1], I[2]);
                    boundary_data.surface_indices_with_ghosts = GetSurfaceIndicesWithGhosts(boundary_data.surface_indices, I);
                    gridData_.boundariesData.symmetry.push_back(boundary_data);
                }
                else
                {
                    throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::ExtractBoundariesData_.cpp.\n\t Boundary type is not recognised.", 0));
                }

            } // end of side loop

        } // end of axis loop

    } // end of grid loop
}