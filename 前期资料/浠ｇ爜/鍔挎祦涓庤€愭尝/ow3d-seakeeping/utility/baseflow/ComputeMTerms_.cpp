#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::ComputeMTerms_(const potentialDerivative &derivatives, Mterms &mterms)
{
    for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData_->exciting[surface];
        const vector<Index> &Ie = be.surface_indices;
        MappedGrid &mg = (*cg_)[be.grid];
        // coordinates
        const realArray &X = mg.vertex()(Ie[0], Ie[1], Ie[2], axis1);
        const realArray &Y = mg.vertex()(Ie[0], Ie[1], Ie[2], axis2);
        realArray Z(Ie[0], Ie[1], Ie[2]);
        Z = 0.0;

        // surface normals
        const realArray &normals = mg.vertexBoundaryNormal(be.side, be.axis);
        const realArray &n1 = normals(Ie[0], Ie[1], Ie[2], axis1);
        const realArray &n2 = normals(Ie[0], Ie[1], Ie[2], axis2);
        realArray n3(Ie[0], Ie[1], Ie[2]);
        n3 = 0.0;

        if (gridData_->nod != 2)
        {
            Z = mg.vertex()(Ie[0], Ie[1], Ie[2], axis3);
            n3 = normals(Ie[0], Ie[1], Ie[2], axis3);
        }

        // m1
        mterms.m1[surface] = -(n1 * derivatives.dxx[surface] + n2 * derivatives.dxy[surface] + n3 * derivatives.dxz[surface]);
        // m2
        mterms.m2[surface] = -(n1 * derivatives.dxy[surface] + n2 * derivatives.dyy[surface] + n3 * derivatives.dyz[surface]);
        // m3
        mterms.m3[surface] = -(n1 * derivatives.dxz[surface] + n2 * derivatives.dyz[surface] + n3 * derivatives.dzz[surface]);
        // m4
        mterms.m4[surface] =
            -(n1 * (Y * derivatives.dxz[surface] - Z * derivatives.dxy[surface]) +
              n2 * (Y * derivatives.dyz[surface] - Z * derivatives.dyy[surface] + derivatives.dz[surface]) +
              n3 * (Y * derivatives.dzz[surface] - Z * derivatives.dyz[surface] - derivatives.dy[surface]));
        // m5
        mterms.m5[surface] =
            (n1 * (X * derivatives.dxz[surface] - Z * derivatives.dxx[surface] + derivatives.dz[surface]) +
             n2 * (X * derivatives.dyz[surface] - Z * derivatives.dxy[surface]) +
             n3 * (X * derivatives.dzz[surface] - Z * derivatives.dxz[surface] - derivatives.dx[surface] + UserInput.U));
        // m6
        mterms.m6[surface] =
            -(n1 * (X * derivatives.dxy[surface] - Y * derivatives.dxx[surface] + derivatives.dy[surface]) +
              n2 * (X * derivatives.dyy[surface] - Y * derivatives.dxy[surface] - derivatives.dx[surface] + UserInput.U) +
              n3 * (X * derivatives.dyz[surface] - Y * derivatives.dxz[surface]));

        // ----------------------------------------------------------------------
        // The following is only performed to store mterms in hdf database file
        // ----------------------------------------------------------------------
        M1_[be.grid](Ie[0], Ie[1], Ie[2]) = mterms.m1[surface];
        M2_[be.grid](Ie[0], Ie[1], Ie[2]) = mterms.m2[surface];
        M3_[be.grid](Ie[0], Ie[1], Ie[2]) = mterms.m3[surface];
        M4_[be.grid](Ie[0], Ie[1], Ie[2]) = mterms.m4[surface];
        M5_[be.grid](Ie[0], Ie[1], Ie[2]) = mterms.m5[surface];
        M6_[be.grid](Ie[0], Ie[1], Ie[2]) = mterms.m6[surface];
    }

    for (unsigned int Imf = 0; Imf < UserInput.number_of_gmodes; Imf++)
    {
        for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); ++surface)
        {
            const Single_boundary_data &be = boundariesData_->exciting[surface];
            const vector<Index> &Ie = be.surface_indices;
            MappedGrid &mg = (*cg_)[be.grid];
            // coordinates
            const realArray &X = mg.vertex()(Ie[0], Ie[1], Ie[2], axis1);
            const realArray &Y = mg.vertex()(Ie[0], Ie[1], Ie[2], axis2);
            realArray Z(Ie[0], Ie[1], Ie[2]);
            Z = 0.0;

            // surface normals
            const realArray &normals = mg.vertexBoundaryNormal(be.side, be.axis);
            const realArray &n1 = normals(Ie[0], Ie[1], Ie[2], axis1);
            const realArray &n2 = normals(Ie[0], Ie[1], Ie[2], axis2);
            realArray n3(Ie[0], Ie[1], Ie[2]);
            n3 = 0.0;

            if (gridData_->nod != 2)
            {
                Z = mg.vertex()(Ie[0], Ie[1], Ie[2], axis3);
                n3 = normals(Ie[0], Ie[1], Ie[2], axis3);
            }
            // mfm
            mterms.mf[Imf][surface] =
                -gridData_->flexmodes[Imf].flex_disp[surface](Ie[0], Ie[1], Ie[2]) *
                    (n1 * derivatives.dxz[surface] + n2 * derivatives.dyz[surface] + n3 * derivatives.dzz[surface]) +
                n3 * (derivatives.dx[surface] - UserInput.U) * gridData_->flexmodes[Imf].flex_disp_der[surface](Ie[0], Ie[1], Ie[2]);
            // ----------------------------------------------------------------------
            // The following is only performed to store mterms in hdf database file
            // ----------------------------------------------------------------------
            MF_[Imf][be.grid](Ie[0], Ie[1], Ie[2]) = mterms.mf[Imf][surface];
        }
    }

    bool InterpolateMterm = 1;
    if (InterpolateMterm)
    {
        interpolant_.interpolate(M1_);
        interpolant_.interpolate(M2_);
        interpolant_.interpolate(M3_);
        interpolant_.interpolate(M4_);
        interpolant_.interpolate(M5_);
        interpolant_.interpolate(M6_);

        for (unsigned int Imf = 0; Imf < UserInput.number_of_gmodes; Imf++)
        {
            interpolant_.interpolate(MF_[Imf]);
        }

        for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); ++surface)
        {
            const Single_boundary_data &be = boundariesData_->exciting[surface];
            const vector<Index> &Ie = be.surface_indices;
            mterms.m1[surface] = M1_[be.grid](Ie[0], Ie[1], Ie[2]);
            mterms.m2[surface] = M2_[be.grid](Ie[0], Ie[1], Ie[2]);
            mterms.m3[surface] = M3_[be.grid](Ie[0], Ie[1], Ie[2]);
            mterms.m4[surface] = M4_[be.grid](Ie[0], Ie[1], Ie[2]);
            mterms.m5[surface] = M5_[be.grid](Ie[0], Ie[1], Ie[2]);
            mterms.m6[surface] = M6_[be.grid](Ie[0], Ie[1], Ie[2]);
        }

        for (unsigned int Imf = 0; Imf < UserInput.number_of_gmodes; Imf++)
        {
            for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); ++surface)
            {
                const Single_boundary_data &be = boundariesData_->exciting[surface];
                const vector<Index> &Ie = be.surface_indices;
                mterms.mf[Imf][surface] = MF_[Imf][be.grid](Ie[0], Ie[1], Ie[2]);
            }
        }
    }
}