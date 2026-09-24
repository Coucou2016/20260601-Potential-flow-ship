#include "Field.h"
#include "OW3DConstants.h"

// note : the above function stores the binary data as follows: [run][t][response]
//
// run[0]                                            run[1]                                         ...
// -------------------------------------------       ------------------------------------------
// t[0]                  t[1]  ...                   t[0]                  t[1] ...
// -------------------------------------------       ------------------------------------------
// resp[0]  resp[1] ...  resp[0]  resp[1] ...        resp[0]  resp[1] ...  resp[0]  resp[1] ...

void OW3DSeakeeping::Field::ExtractBodyPotentials_()
{
    char mode_type = (run_.mat_type == MAT_TYPES::SYMMAT) ? 's' : 'a';
    for (unsigned int surface = 0; surface < gridData_->boundariesData.exciting.size(); ++surface)
    {
        const Single_boundary_data &be = gridData_->boundariesData.exciting[surface];
        const vector<Index> &Is = be.surface_indices;

        phiu_on_body_[surface] = potential_[be.grid](Is[0], Is[1], Is[2]);

        if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
        {
            RealArray phi = potential_[be.grid](Is[0], Is[1], Is[2]);
            RealArray phin = PhiN_[be.grid](Is[0], Is[1], Is[2]);
            SideDervs Dervs;

            OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_->body_fundamentals[surface], gridData_->body_surface_disc[surface], phi, phin, Dervs, mode_type);

            d_phiu_dx_on_body_[surface] = Dervs.dx;
            d_phiu_dy_on_body_[surface] = Dervs.dy;
            d_phiu_dz_on_body_[surface] = Dervs.dz;
            d_phiu_dxx_on_body_[surface] = Dervs.dxx;
            d_phiu_dyy_on_body_[surface] = Dervs.dyy;
            d_phiu_dzz_on_body_[surface] = Dervs.dzz;
            d_phiu_dxy_on_body_[surface] = Dervs.dxy;
            d_phiu_dxz_on_body_[surface] = Dervs.dxz;
            d_phiu_dyz_on_body_[surface] = Dervs.dyz;
        }
        else
        {
            d_phiu_dx_on_body_[surface] = potential_[be.grid].x()(Is[0], Is[1], Is[2]);
            d_phiu_dy_on_body_[surface] = potential_[be.grid].y()(Is[0], Is[1], Is[2]);
            d_phiu_dxx_on_body_[surface] = potential_[be.grid].xx()(Is[0], Is[1], Is[2]); // for wave drift
            d_phiu_dxy_on_body_[surface] = potential_[be.grid].xy()(Is[0], Is[1], Is[2]); // for wave drift
            d_phiu_dyy_on_body_[surface] = potential_[be.grid].yy()(Is[0], Is[1], Is[2]); // for wave drift

            if (gridData_->nod == 3)
            {
                d_phiu_dz_on_body_[surface] = potential_[be.grid].z()(Is[0], Is[1], Is[2]);
                d_phiu_dxz_on_body_[surface] = potential_[be.grid].xz()(Is[0], Is[1], Is[2]); // for drift force
                d_phiu_dyz_on_body_[surface] = potential_[be.grid].yz()(Is[0], Is[1], Is[2]); // for drift force
                d_phiu_dzz_on_body_[surface] = potential_[be.grid].zz()(Is[0], Is[1], Is[2]); // for drift force
            }
        }

        grad_phiu_grad_phib_on_body_[surface] = d_phiu_dx_on_body_[surface] * baseFlowData_->BodySurfaceDerivatives[surface].dx +
                                                d_phiu_dy_on_body_[surface] * baseFlowData_->BodySurfaceDerivatives[surface].dy +
                                                d_phiu_dz_on_body_[surface] * baseFlowData_->BodySurfaceDerivatives[surface].dz;

        grad_phiu_grad_phiu_on_body_[surface] = (d_phiu_dx_on_body_[surface] * d_phiu_dx_on_body_[surface] +
                                                 d_phiu_dy_on_body_[surface] * d_phiu_dy_on_body_[surface] +
                                                 d_phiu_dz_on_body_[surface] * d_phiu_dz_on_body_[surface]);
    }
}