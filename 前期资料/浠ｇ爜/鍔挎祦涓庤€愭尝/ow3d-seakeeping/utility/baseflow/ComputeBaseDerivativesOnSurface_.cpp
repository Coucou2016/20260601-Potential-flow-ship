#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::ComputeBaseDerivativesOnSurface_(
    potentialDerivative &potential_derivative,
    const Single_boundary_data &bs,
    int surface, bool scheme_option)
{
  const vector<Index> &Is = bs.surface_indices;

  if (scheme_option) // Derivatives based on the new scheme
  {
    RealArray phin = UserInput.U * gridData_->body_fundamentals[surface].n1;
    RealArray phi = data_.potential[bs.grid](Is[0], Is[1], Is[2]);
    SideDervs Dervs;

    OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_->body_fundamentals[surface], gridData_->body_surface_disc[surface], phi, phin, Dervs);

    potential_derivative.dx[surface] = Dervs.dx;
    potential_derivative.dy[surface] = Dervs.dy;
    potential_derivative.dz[surface] = Dervs.dz;
    potential_derivative.dxx[surface] = Dervs.dxx;
    potential_derivative.dyy[surface] = Dervs.dyy;
    potential_derivative.dzz[surface] = Dervs.dzz;
    potential_derivative.dxy[surface] = Dervs.dxy;
    potential_derivative.dxz[surface] = Dervs.dxz;
    potential_derivative.dyz[surface] = Dervs.dyz;
  }
  else
  {
    potential_derivative.dx[surface] = data_.DerivativesOnCompositeGrid.d_phib_dx[bs.grid](Is[0], Is[1], Is[2]);
    potential_derivative.dy[surface] = data_.DerivativesOnCompositeGrid.d_phib_dy[bs.grid](Is[0], Is[1], Is[2]);
    potential_derivative.dxx[surface] = data_.DerivativesOnCompositeGrid.d_phib_dxx[bs.grid](Is[0], Is[1], Is[2]);
    potential_derivative.dyy[surface] = data_.DerivativesOnCompositeGrid.d_phib_dyy[bs.grid](Is[0], Is[1], Is[2]);
    potential_derivative.dxy[surface] = data_.DerivativesOnCompositeGrid.d_phib_dxy[bs.grid](Is[0], Is[1], Is[2]);

    if (gridData_->nod == 3)
    {
      potential_derivative.dz[surface] = data_.DerivativesOnCompositeGrid.d_phib_dz[bs.grid](Is[0], Is[1], Is[2]);
      potential_derivative.dzz[surface] = data_.DerivativesOnCompositeGrid.d_phib_dzz[bs.grid](Is[0], Is[1], Is[2]);
      potential_derivative.dyz[surface] = data_.DerivativesOnCompositeGrid.d_phib_dyz[bs.grid](Is[0], Is[1], Is[2]);
      potential_derivative.dxz[surface] = data_.DerivativesOnCompositeGrid.d_phib_dxz[bs.grid](Is[0], Is[1], Is[2]);
    }

    // potential_derivative.dx[surface]  = data_.potential[bs.grid].x()(Is[0],Is[1],Is[2]);
    // potential_derivative.dy[surface]  = data_.potential[bs.grid].y()(Is[0],Is[1],Is[2]);
    // potential_derivative.dxx[surface] = data_.potential[bs.grid].xx()(Is[0],Is[1],Is[2]);
    // potential_derivative.dyy[surface] = data_.potential[bs.grid].yy()(Is[0],Is[1],Is[2]);
    // potential_derivative.dxy[surface] = data_.potential[bs.grid].xy()(Is[0],Is[1],Is[2]);

    // if(gridData_ -> nod == 3)
    //   {
    //     potential_derivative.dz[surface]  = data_.potential[bs.grid].z()(Is[0],Is[1],Is[2]);
    //     potential_derivative.dzz[surface] = data_.potential[bs.grid].zz()(Is[0],Is[1],Is[2]);
    //     potential_derivative.dyz[surface] = data_.potential[bs.grid].yz()(Is[0],Is[1],Is[2]);
    //     potential_derivative.dxz[surface] = data_.potential[bs.grid].xz()(Is[0],Is[1],Is[2]);
    //   }
  }
}
// =========================================================================================================