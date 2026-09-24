#include "FreeSurface.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FreeSurface::March(const double &time_step)
{
    for (int stage = 0; stage < OW3DSeakeeping::rk_stage_count; ++stage)
    {
        for (unsigned int surface = 0; surface < boundariesData_->free.size(); ++surface)
        {
            const Single_boundary_data &bf = boundariesData_->free[surface];
            const MappedGrid &mg = (*cg_)[bf.grid];
            const vector<Index> &Is = bf.surface_indices;

            where(mg.mask()(Is[0], Is[1], Is[2]) > 0) // only discretisation points
            {
                freeSurface_.solution_start.elevation[bf.grid](Is[0], Is[1], Is[2]) +=
                    freeSurface_.slope[stage].elevation[bf.grid](Is[0], Is[1], Is[2]) * OW3DSeakeeping::rk_b[stage] * time_step;

                freeSurface_.solution_start.potential[bf.grid](Is[0], Is[1], Is[2]) +=
                    freeSurface_.slope[stage].potential[bf.grid](Is[0], Is[1], Is[2]) * OW3DSeakeeping::rk_b[stage] * time_step;
            }

        } // end of loop over free surface

    } // end of loop over RK stages

    if (filter_on_)
    {
        filter_.ApplyFilter(freeSurface_.solution_start.elevation);

        InterpolateSolutions("start");
    }
}