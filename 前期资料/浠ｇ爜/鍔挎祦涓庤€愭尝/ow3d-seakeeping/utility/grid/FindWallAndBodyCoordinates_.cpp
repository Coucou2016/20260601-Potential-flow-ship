// This private member function belongs to the Grid class, and just for
// the sake of convenience is written in a seperate file.

#include "Grid.h"
#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::Grid::FindWallAndBodyCoordinates_(double sponge_length)
{
  for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
  {
    const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];

    gridData_.bodyCoordinates = veccat(gridData_.bodyCoordinates, ExtractBoundaryOutline_(be));
  }
  for (unsigned int surface = 0; surface < gridData_.boundariesData.absorbing.size(); surface++)
  {
    const Single_boundary_data &ba = gridData_.boundariesData.absorbing[surface];

    gridData_.wallCoordinates = veccat(gridData_.wallCoordinates, ExtractBoundaryOutline_(ba));
  }

  // check for domain length in the case of floating bodies

  for (unsigned int i = 0; i < gridData_.bodyCoordinates.size(); i++)
  {
    if (sponge_length > FindShortest(gridData_.bodyCoordinates[i], gridData_.wallCoordinates))
    {
      throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::FindWallAndBodyCoordinates_.cpp.\n\t The length of the sponge layer exceeds the domain length.", 0));
    }
  }

  // and in the case of submerged bodies

  Coordinate origin;
  origin.x = 0;
  origin.z = 0;

  if (sponge_length > FindShortest(origin, gridData_.wallCoordinates))
  {
    throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::FindWallAndBodyCoordinates_.cpp.\n\t The length of the sponge layer exceeds the domain length.", 0));
  }
}
