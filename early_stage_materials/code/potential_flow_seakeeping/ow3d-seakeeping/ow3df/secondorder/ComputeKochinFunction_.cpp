#include "SecondOrder.h"

void OW3DSeakeeping::SecondOrder::ComputeKochinFunction_(
    int symSign,
    double VertC,
    double C0,
    double C1,
    double *H)
{
    for (unsigned int surface = 0; surface < NES_; surface++)
    {
        const Single_boundary_data &be = boundariesData_->exciting[surface];
        const vector<Index> &Is = be.surface_indices;
        MappedGrid &mg = (*cg_)[be.grid];
        const RealArray &v = mg.vertex();
        const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        RealArray n1(Is[0], Is[1], Is[2]), n2(Is[0], Is[1], Is[2]), n3(Is[0], Is[1], Is[2]);

        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2); // Note : "y" vertical up
        z = 0.0;

        n1 = vbn(Is[0], Is[1], Is[2], axis1);
        n2 = vbn(Is[0], Is[1], Is[2], axis2); // Note : "n2" vertical up
        n3 = 0.;

        if (gridData_->nod == 3)
        {
            z = v(Is[0], Is[1], Is[2], axis3) * symSign;
            n3 = vbn(Is[0], Is[1], Is[2], axis3) * symSign;
        }

        RealArray N = n1 * C0 + n3 * C1;
        RealArray alpha = x * C0 + z * C1;
        RealArray cosAlpha = cos(alpha);
        RealArray sinAlpha = sin(alpha);

        // ---------------------------------------------------------------------------------------------------------------------
        // INTEGRAND := PHI_B * D_DN( EXP[VertC*Y + i(X*C0 + Z*C1)] ) -
        //              D_PHI_DN *  ( EXP[VertC*Y + i(X*C0 + Z*C1)] );
        // ---------------------------------------------------------------------------------------------------------------------

        if (!bcsExact_) // dphidn is based on the direct derivative of the potentials.
        {
            // THE REAL PART ----------------
            KOCHIN_INTEGRAND_REAL_[be.grid](Is[0], Is[1], Is[2]) =
                exp(VertC * y) * (phi_(0)[surface] * (VertC * n2 * cosAlpha - N * sinAlpha) -
                                  phi_(1)[surface] * (N * cosAlpha + VertC * n2 * sinAlpha)) -
                exp(VertC * y) * (cosAlpha * (n1 * d_phi_dx_(0)[surface] + n2 * d_phi_dy_(0)[surface] + n3 * d_phi_dz_(0)[surface]) -
                                  sinAlpha * (n1 * d_phi_dx_(1)[surface] + n2 * d_phi_dy_(1)[surface] + n3 * d_phi_dz_(1)[surface]));
            // THE IMAGINARY PART -----------
            KOCHIN_INTEGRAND_IMAG_[be.grid](Is[0], Is[1], Is[2]) =
                exp(VertC * y) * (phi_(1)[surface] * (VertC * n2 * cosAlpha - N * sinAlpha) +
                                  phi_(0)[surface] * (N * cosAlpha + VertC * n2 * sinAlpha)) -
                exp(VertC * y) * (sinAlpha * (n1 * d_phi_dx_(0)[surface] + n2 * d_phi_dy_(0)[surface] + n3 * d_phi_dz_(0)[surface]) +
                                  cosAlpha * (n1 * d_phi_dx_(1)[surface] + n2 * d_phi_dy_(1)[surface] + n3 * d_phi_dz_(1)[surface]));
        }

        else // dphidn is based on the closed-form BBCs. (NOTE : "calcDphiDnOnBody_" must be first called in the frequency loop)
        {
            // THE REAL PART ----------------
            KOCHIN_INTEGRAND_REAL_[be.grid](Is[0], Is[1], Is[2]) =
                exp(VertC * y) * (phi_(0)[surface] * (VertC * n2 * cosAlpha - N * sinAlpha) -
                                  phi_(1)[surface] * (N * cosAlpha + VertC * n2 * sinAlpha)) -
                exp(VertC * y) * (cosAlpha * d_phi_dn_(0)[surface] - sinAlpha * d_phi_dn_(1)[surface]);

            // THE IMAGINARY PART -----------
            KOCHIN_INTEGRAND_IMAG_[be.grid](Is[0], Is[1], Is[2]) =
                exp(VertC * y) * (phi_(1)[surface] * (VertC * n2 * cosAlpha - N * sinAlpha) +
                                  phi_(0)[surface] * (N * cos(alpha) + VertC * n2 * sinAlpha)) -
                exp(VertC * y) * (sinAlpha * d_phi_dn_(0)[surface] + cosAlpha * d_phi_dn_(1)[surface]);
        }
    }

    H[0] = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, KOCHIN_INTEGRAND_REAL_);
    H[1] = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, KOCHIN_INTEGRAND_IMAG_);
}
