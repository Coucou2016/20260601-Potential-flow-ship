#include "FreeSurface.h"
#include "OW3DConstants.h"

// The following function calculates the value of the
// right hand side of the dy/dt = f(y ,t) at the evaluation
// points considered for the Runge-Kutta time integration.
// I norder to perform this, it is required that the time
// gradient of the velocity potential and the surface elevation
// is known at each evaluation point. This can be carried out
// by the "calculateSolutionSlope" function, where using the
// dynamid and kinematic free-surface conditions, the time gradinets
// for the velocity potential and the wave elevation are calculated.
// Later by the march function from this class, the next time-step
// solution can be obtained, as the solution at all evaluation points
// are now obtained. The following function must be called at each
// stage of the Runge-Kutta time integration.

void OW3DSeakeeping::FreeSurface::SetStageSolution(const int &stage, const double &time_step)
{
  for (unsigned int surface = 0; surface < boundariesData_->free.size(); ++surface)
  {
    const Single_boundary_data &bf = boundariesData_->free[surface];
    const vector<Index> &Is = bf.surface_indices;
    const MappedGrid &mg = (*cg_)[bf.grid];

    where(mg.mask()(Is[0], Is[1], Is[2]) > 0) // only discretisation points
    {
      if (stage == 0)
      {
        freeSurface_.solution_stage.elevation[bf.grid](Is[0], Is[1], Is[2]) = freeSurface_.solution_start.elevation[bf.grid](Is[0], Is[1], Is[2]);
        freeSurface_.solution_stage.potential[bf.grid](Is[0], Is[1], Is[2]) = freeSurface_.solution_start.potential[bf.grid](Is[0], Is[1], Is[2]);
      }
      else
      {
        freeSurface_.solution_stage.elevation[bf.grid](Is[0], Is[1], Is[2]) =
            freeSurface_.solution_start.elevation[bf.grid](Is[0], Is[1], Is[2]) +
            freeSurface_.slope[stage - 1].elevation[bf.grid](Is[0], Is[1], Is[2]) * OW3DSeakeeping::rk_c[stage] * time_step;

        freeSurface_.solution_stage.potential[bf.grid](Is[0], Is[1], Is[2]) =
            freeSurface_.solution_start.potential[bf.grid](Is[0], Is[1], Is[2]) +
            freeSurface_.slope[stage - 1].potential[bf.grid](Is[0], Is[1], Is[2]) * OW3DSeakeeping::rk_c[stage] * time_step;
      }

    } // end of where

  } // end of loop over free surface
}