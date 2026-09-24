#include "FreeSurface.h"

void OW3DSeakeeping::FreeSurface::InterpolateSolutions(string s)
{
  if (s == "stage")
  {
    interpolant_.interpolate(freeSurface_.solution_stage.elevation);
    interpolant_.interpolate(freeSurface_.solution_stage.potential);
  }
  else
  {
    interpolant_.interpolate(freeSurface_.solution_start.elevation);
    interpolant_.interpolate(freeSurface_.solution_start.potential);
  }
}