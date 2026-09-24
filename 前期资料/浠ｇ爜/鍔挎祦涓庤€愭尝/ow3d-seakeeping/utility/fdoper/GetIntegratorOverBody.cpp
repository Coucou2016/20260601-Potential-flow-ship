
#include "OvertureTypes.h"
#include "OW3DUtilFunctions.h"

Integrate OW3DSeakeeping::GetIntegratorOverBody(
    CompositeGrid &cg,
    const All_boundaries_data &boundariesData)
{
  Integrate integrator;

  integrator.updateToMatchGrid(cg);

  const unsigned int integration_surface_count = boundariesData.exciting.size();

  IntegerArray boundary(3, integration_surface_count);

  for (unsigned int surface = 0; surface < integration_surface_count; ++surface)
  {
    const Single_boundary_data &be = boundariesData.exciting[surface];
    boundary(0, surface) = be.side;
    boundary(1, surface) = be.axis;
    boundary(2, surface) = be.grid;
  }

  integrator.defineSurface(0, integration_surface_count, boundary);

  return integrator;
}
