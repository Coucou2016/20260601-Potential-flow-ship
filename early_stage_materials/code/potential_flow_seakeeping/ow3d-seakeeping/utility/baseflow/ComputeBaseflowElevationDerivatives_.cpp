#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::ComputeBaseflowElevationDerivatives_(
    const realCompositeGridFunction &elevation,
    elevationDerivative &elevation_derivative)
{
  for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
  {
    const Single_boundary_data &bs = boundariesData_->free[surface];
    const vector<Index> &Is = bs.surface_indices;

    elevation_derivative.dx[surface] = elevation[bs.grid].x()(Is[0], Is[1], Is[2]);

    if (gridData_->nod == 3)
    {
      elevation_derivative.dz[surface] = elevation[bs.grid].z()(Is[0], Is[1], Is[2]);
    }
  }
}