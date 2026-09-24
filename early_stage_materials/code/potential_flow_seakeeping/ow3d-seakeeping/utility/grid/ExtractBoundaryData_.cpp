#include "Grid.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Single_boundary_data OW3DSeakeeping::Grid::ExtractBoundaryData_(
    const int &grid,
    const int &axis,
    const int &side,
    const IntegerArray &gir)
{
    const int ghost_line = 1; // get indices for this line of ghost points
    Single_boundary_data boundary_data;
    boundary_data.grid = grid;
    boundary_data.axis = axis;
    boundary_data.side = side;

    vector<Index> &Is = boundary_data.surface_indices;
    Is.resize(3);
    getBoundaryIndex(gir, side, axis, Is[0], Is[1], Is[2]);

    vector<Index> &Ig = boundary_data.ghost_indices;
    Ig.resize(3);
    getGhostIndex(gir, side, axis, Ig[0], Ig[1], Ig[2], ghost_line);

    return boundary_data;
}