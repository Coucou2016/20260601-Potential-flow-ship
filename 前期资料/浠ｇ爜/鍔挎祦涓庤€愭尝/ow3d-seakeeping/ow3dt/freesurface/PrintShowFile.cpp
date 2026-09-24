#include "FreeSurface.h"

void OW3DSeakeeping::FreeSurface::PrintShowFile()
{
    show_.startFrame();
    show_.saveSolution(freeSurface_.solution_start.potential);
}