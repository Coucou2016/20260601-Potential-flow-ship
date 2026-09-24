#include "Grid.h"
#include "OW3DUtilFunctions.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Grid::ExtractSurfaceFundamentals_()
{
    // * Body surfaces ---------------------------------------------------------

    gridData_.body_fundamentals.resize(gridData_.boundariesData.exciting.size());
    for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
    {
        const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
        const MappedGrid &mg = (*cg_)[be.grid];
        const RealArray &v = mg.vertex();
        const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);
        const vector<Index> &Is = be.surface_indices;
        Mapping &mapping = mg.mapping().getMapping();
        int jsg = mapping.getSignForJacobian();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2); // Note : "y" vertical up
        z = (gridData_.nod == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);

        int S0 = x.getLength(0);
        int S1 = x.getLength(1);
        int S2 = x.getLength(2); // Y is upward
        int N0, N1;

        if (S0 == 1) // v and u run along axis1 and axis2
        {
            N0 = S1;
            N1 = S2;
        }
        else if (S1 == 1) // v and u run along axis0 and axis2
        {
            N0 = S0;
            N1 = S2;
        }
        else if (S2 == 1) // v and u run along axis0 and axis1
        {
            N0 = S0;
            N1 = S1;
        }
        else
            throw runtime_error(OW3DSeakeeping::GetColoredMessage("\t Error (OW3D), Grid::ExtractSurfaceFirstFundamentalForms_.cpp.\n\t The coordinates of only 1 side should be given.", 0));

        // Assign the coefficients with the boundary options
        // NOTE : Convention: Always first index for v, second index for u

        RealArray C4_u_nm = OW3DSeakeeping::C4;
        RealArray C4_v_nm = OW3DSeakeeping::C4;
        RealArray C4_u_dr = OW3DSeakeeping::C4;
        RealArray C4_v_dr = OW3DSeakeeping::C4;
        RealArray C2_u_nm = OW3DSeakeeping::C2;
        RealArray C2_v_nm = OW3DSeakeeping::C2;
        RealArray C2_u_dr = OW3DSeakeeping::C2;
        RealArray C2_v_dr = OW3DSeakeeping::C2;

        if (use_grid_symmetry_for_derivatives and gridData_.halfSymmetry)
        {
            for (int axis = 0; axis < mg.numberOfDimensions(); axis++)
            {
                for (int side = Start; side <= End; side++)
                {
                    if (mg.boundaryCondition()(side, axis) == gridData_.boundaryTypes.symmetry)
                    {
                        if (axis == 0 or axis == 2 or (axis == 1 and S2 > 1))
                        {
                            C4_v_nm = (side == 0) ? OW3DSeakeeping::C4_left_neumann : OW3DSeakeeping::C4_right_neumann;
                            C4_v_dr = (side == 0) ? OW3DSeakeeping::C4_left_dirichlet : OW3DSeakeeping::C4_right_dirichlet;
                            C2_v_nm = (side == 0) ? OW3DSeakeeping::C2_left_neumann : OW3DSeakeeping::C2_right_neumann;
                            C2_v_dr = (side == 0) ? OW3DSeakeeping::C2_left_dirichlet : OW3DSeakeeping::C2_right_dirichlet;
                        }
                        else
                        {
                            C4_u_nm = (side == 0) ? OW3DSeakeeping::C4_left_neumann : OW3DSeakeeping::C4_right_neumann;
                            C4_u_dr = (side == 0) ? OW3DSeakeeping::C4_left_dirichlet : OW3DSeakeeping::C4_right_dirichlet;
                            C2_u_nm = (side == 0) ? OW3DSeakeeping::C2_left_neumann : OW3DSeakeeping::C2_right_neumann;
                            C2_u_dr = (side == 0) ? OW3DSeakeeping::C2_left_dirichlet : OW3DSeakeeping::C2_right_dirichlet;
                        }
                    }
                }
            }
        }

        gridData_.body_fundamentals[surface].C4_u_nm = C4_u_nm;
        gridData_.body_fundamentals[surface].C4_v_nm = C4_v_nm;
        gridData_.body_fundamentals[surface].C4_u_dr = C4_u_dr;
        gridData_.body_fundamentals[surface].C4_v_dr = C4_v_dr;
        gridData_.body_fundamentals[surface].C2_u_nm = C2_u_nm;
        gridData_.body_fundamentals[surface].C2_v_nm = C2_v_nm;
        gridData_.body_fundamentals[surface].C2_u_dr = C2_u_dr;
        gridData_.body_fundamentals[surface].C2_v_dr = C2_v_dr;

        // Convention: Always first index for v, second index for u

        double dv = 1.0 / (N0 - 1);
        double du = 1.0 / (N1 - 1);
        x.reshape(N0, N1);
        y.reshape(N0, N1);
        z.reshape(N0, N1);
        RealArray Xu(N0, N1), Yu(N0, N1), Zu(N0, N1);
        Xu = 0, Yu = 0, Zu = 0;
        RealArray Xv(N0, N1), Yv(N0, N1), Zv(N0, N1);
        Xv = 0, Yv = 0, Zv = 0;
        // Compute 1D derivatives along u ---------------------------------------------------
        OW3DSeakeeping::Compute1DDerivatives(x, Xu, 0, N1 - 1, C4_u_nm);
        OW3DSeakeeping::Compute1DDerivatives(y, Yu, 0, N1 - 1, C4_u_nm);
        OW3DSeakeeping::Compute1DDerivatives(z, Zu, 0, N1 - 1, C4_u_dr);
        Xu *= du, Yu *= du, Zu *= du;
        // ---------------------------------------------------------------------------------
        RealArray tX = transpose(x);
        RealArray tXv = transpose(Xv);
        RealArray tY = transpose(y);
        RealArray tYv = transpose(Yv);
        RealArray tZ = transpose(z);
        RealArray tZv = transpose(Zv);
        // Compute 1D derivatives along v ---------------------------------------------------
        OW3DSeakeeping::Compute1DDerivatives(tX, tXv, 0, N0 - 1, C4_v_nm);
        OW3DSeakeeping::Compute1DDerivatives(tY, tYv, 0, N0 - 1, C4_v_nm);
        OW3DSeakeeping::Compute1DDerivatives(tZ, tZv, 0, N0 - 1, C4_v_dr);
        tXv *= dv, tYv *= dv, tZv *= dv;
        Xv = transpose(tXv);
        Yv = transpose(tYv);
        Zv = transpose(tZv);

        gridData_.body_fundamentals[surface].E = Xu * Xu + Yu * Yu + Zu * Zu;
        gridData_.body_fundamentals[surface].F = Xu * Xv + Yu * Yv + Zu * Zv;
        gridData_.body_fundamentals[surface].G = Xv * Xv + Yv * Yv + Zv * Zv;

        RealArray E = gridData_.body_fundamentals[surface].E;
        RealArray F = gridData_.body_fundamentals[surface].F;
        RealArray G = gridData_.body_fundamentals[surface].G;

        gridData_.body_fundamentals[surface].H = sqrt(E * G - F * F);
        gridData_.body_fundamentals[surface].n1 = (Yu * Zv - Zu * Yv) / gridData_.body_fundamentals[surface].H * jsg;
        gridData_.body_fundamentals[surface].n2 = (Zu * Xv - Xu * Zv) / gridData_.body_fundamentals[surface].H * jsg;
        gridData_.body_fundamentals[surface].n3 = (Xu * Yv - Yu * Xv) / gridData_.body_fundamentals[surface].H * jsg;
        gridData_.body_fundamentals[surface].Xu = Xu;
        gridData_.body_fundamentals[surface].Yu = Yu;
        gridData_.body_fundamentals[surface].Zu = Zu;
        gridData_.body_fundamentals[surface].Xv = Xv;
        gridData_.body_fundamentals[surface].Yv = Yv;
        gridData_.body_fundamentals[surface].Zv = Zv;
        gridData_.body_fundamentals[surface].X = x;
        gridData_.body_fundamentals[surface].Y = y;
        gridData_.body_fundamentals[surface].Z = z;
        gridData_.body_fundamentals[surface].n1_OV = vbn(Is[0], Is[1], Is[2], axis1);
        gridData_.body_fundamentals[surface].n2_OV = vbn(Is[0], Is[1], Is[2], axis2);
        gridData_.body_fundamentals[surface].n3_OV = vbn(Is[0], Is[1], Is[2], axis3);
    }

    // * Free surfaces ---------------------------------------------------------

    gridData_.free_fundamentals.resize(gridData_.boundariesData.free.size());
    for (unsigned int surface = 0; surface < gridData_.boundariesData.free.size(); surface++)
    {
        const Single_boundary_data &bf = gridData_.boundariesData.free[surface];
        const MappedGrid &mg = (*cg_)[bf.grid];
        const RealArray &v = mg.vertex();
        const RealArray &vbn = mg.vertexBoundaryNormal(bf.side, bf.axis);
        const vector<Index> &Is = bf.surface_indices;
        Mapping &mapping = mg.mapping().getMapping();
        int jsg = mapping.getSignForJacobian();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2); // Note : "y" vertical up
        z = (gridData_.nod == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);

        int S0 = x.getLength(0);
        int S1 = x.getLength(1);
        int S2 = x.getLength(2); // Y is upward
        int N0, N1;

        if (S0 == 1) // v and u run along axis1 and axis2
        {
            N0 = S1;
            N1 = S2;
        }
        else if (S1 == 1) // v and u run along axis0 and axis2
        {
            N0 = S0;
            N1 = S2;
        }
        else if (S2 == 1) // v and u run along axis0 and axis1
        {
            N0 = S0;
            N1 = S1;
        }
        else
            throw runtime_error(OW3DSeakeeping::GetColoredMessage("\t Error (OW3D), Grid::ExtractSurfaceFirstFundamentalForms_.cpp.\n\t The coordinates of only 1 side should be given.", 0));

        // Convention: Always first index for v, second index for u

        double dv = 1.0 / (N0 - 1);
        double du = 1.0 / (N1 - 1);
        x.reshape(N0, N1);
        y.reshape(N0, N1);
        z.reshape(N0, N1);
        RealArray Xu(N0, N1), Yu(N0, N1), Zu(N0, N1);
        Xu = 0, Yu = 0, Zu = 0;
        RealArray Xv(N0, N1), Yv(N0, N1), Zv(N0, N1);
        Xv = 0, Yv = 0, Zv = 0;
        // Compute 1D derivatives along u ---------------------------------------------------
        OW3DSeakeeping::Compute1DDerivatives(x, Xu, 0, N1 - 1, OW3DSeakeeping::C4);
        OW3DSeakeeping::Compute1DDerivatives(y, Yu, 0, N1 - 1, OW3DSeakeeping::C4);
        OW3DSeakeeping::Compute1DDerivatives(z, Zu, 0, N1 - 1, OW3DSeakeeping::C4);
        Xu *= du, Yu *= du, Zu *= du;
        // ---------------------------------------------------------------------------------
        RealArray tX = transpose(x);
        RealArray tXv = transpose(Xv);
        RealArray tY = transpose(y);
        RealArray tYv = transpose(Yv);
        RealArray tZ = transpose(z);
        RealArray tZv = transpose(Zv);
        // Compute 1D derivatives along v ---------------------------------------------------
        OW3DSeakeeping::Compute1DDerivatives(tX, tXv, 0, N0 - 1, OW3DSeakeeping::C4);
        OW3DSeakeeping::Compute1DDerivatives(tY, tYv, 0, N0 - 1, OW3DSeakeeping::C4);
        OW3DSeakeeping::Compute1DDerivatives(tZ, tZv, 0, N0 - 1, OW3DSeakeeping::C4);
        tXv *= dv, tYv *= dv, tZv *= dv;
        Xv = transpose(tXv);
        Yv = transpose(tYv);
        Zv = transpose(tZv);

        gridData_.free_fundamentals[surface].E = Xu * Xu + Yu * Yu + Zu * Zu;
        gridData_.free_fundamentals[surface].F = Xu * Xv + Yu * Yv + Zu * Zv;
        gridData_.free_fundamentals[surface].G = Xv * Xv + Yv * Yv + Zv * Zv;

        RealArray E = gridData_.free_fundamentals[surface].E;
        RealArray F = gridData_.free_fundamentals[surface].F;
        RealArray G = gridData_.free_fundamentals[surface].G;

        gridData_.free_fundamentals[surface].H = sqrt(E * G - F * F);
        gridData_.free_fundamentals[surface].n1 = (Yu * Zv - Zu * Yv) / gridData_.free_fundamentals[surface].H * jsg;
        gridData_.free_fundamentals[surface].n2 = (Zu * Xv - Xu * Zv) / gridData_.free_fundamentals[surface].H * jsg;
        gridData_.free_fundamentals[surface].n3 = (Xu * Yv - Yu * Xv) / gridData_.free_fundamentals[surface].H * jsg;
        gridData_.free_fundamentals[surface].Xu = Xu;
        gridData_.free_fundamentals[surface].Yu = Yu;
        gridData_.free_fundamentals[surface].Zu = Zu;
        gridData_.free_fundamentals[surface].Xv = Xv;
        gridData_.free_fundamentals[surface].Yv = Yv;
        gridData_.free_fundamentals[surface].Zv = Zv;
        gridData_.free_fundamentals[surface].X = x;
        gridData_.free_fundamentals[surface].Y = y;
        gridData_.free_fundamentals[surface].Z = z;
        gridData_.free_fundamentals[surface].n1_OV = vbn(Is[0], Is[1], Is[2], axis1);
        gridData_.free_fundamentals[surface].n2_OV = vbn(Is[0], Is[1], Is[2], axis2);
        gridData_.free_fundamentals[surface].n3_OV = vbn(Is[0], Is[1], Is[2], axis3);

        // Reshpae the arrays

        gridData_.free_fundamentals[surface].n1_OV.reshape(N0, N1);
        gridData_.free_fundamentals[surface].n2_OV.reshape(N0, N1);
        gridData_.free_fundamentals[surface].n3_OV.reshape(N0, N1);

        //

        gridData_.free_fundamentals[surface].C4_u_nm = OW3DSeakeeping::C4;
        gridData_.free_fundamentals[surface].C4_v_nm = OW3DSeakeeping::C4;
        gridData_.free_fundamentals[surface].C4_u_dr = OW3DSeakeeping::C4;
        gridData_.free_fundamentals[surface].C4_v_dr = OW3DSeakeeping::C4;
        gridData_.free_fundamentals[surface].C2_u_nm = OW3DSeakeeping::C2;
        gridData_.free_fundamentals[surface].C2_v_nm = OW3DSeakeeping::C2;
        gridData_.free_fundamentals[surface].C2_u_dr = OW3DSeakeeping::C2;
        gridData_.free_fundamentals[surface].C2_v_dr = OW3DSeakeeping::C2;
    }
}