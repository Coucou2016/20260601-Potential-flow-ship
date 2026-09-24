#include "Upwind.h"

void OW3DSeakeeping::Upwind::ApplyNeumannCondition(realCompositeGridFunction &u, const realCompositeGridFunction &forcing)
{
    CompositeGrid &cg = *u.getCompositeGrid();
    for (unsigned int surface = 0; surface < nofs_; surface++) // Loop over free surface and find body or wall
    {
        const Single_boundary_data &bs = boundariesData_->free[surface];
        const vector<Index> &Is = bs.surface_indices;
        const MappedGrid &mg = (*cg)[bs.grid];
        const RealArray &v = mg.vertex();
        int grid = directions_[surface].grid;

        if (mg.numberOfDimensions() == 2)
        {
            // Find the body and the wall
            if (mg.boundaryCondition()(0, 0) == boundaryTypes_->exciting or mg.boundaryCondition()(0, 0) == boundaryTypes_->absorbing)
            {
                // Ghost points are in the base of direction 0 (base-1, and base-2)
                int side = 0;
                int axis = 0;
                const RealArray &vbn = mg.vertexBoundaryNormal(side, axis);
                if (directions_[surface].index[0] == 0) // The axis in to neumann BC
                {
                    int i = Is[0].getBase();
                    int j = Is[2].getBound();
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        const Range &R0x = vertexData_[surface][i][j].R0x;
                        double nx = vbn(i, Is[1].getBase(), j, axis1);
                        double dx = sum(u[grid](vertexData_[surface][i][j].R0x, Is[1].getBase(), j) * vertexData_[surface][i][j].C0x) *
                                    vertexData_[surface][i][j].vder0x * 1.0 / directions_[surface].spacing[0];
                        double dn = nx * dx;

                        // Now fill out the ghost points

                        if (R0x.getBase() == Is[0].getBase()) // No ghost points in the stencil
                            continue;
                        else if (R0x.getBase() == Is[0].getBase() - 1) // Only one ghost layer
                            throw runtime_error("finish me!");
                        else if (R0x.getBase() == Is[0].getBase() - 2)
                        {
                            // Find the "wrong" parts in x and z derivatives
                            int fi = 1;                                       // The index in the range where 1st ghost sits
                            int si = 0;                                       // The index in the range where 2nd ghost sits
                            double cxgf = vertexData_[surface][i][j].C0x(fi); // The coefficient for the 1st ghost
                            double cxgs = vertexData_[surface][i][j].C0x(si); // The coefficient for the 2nd ghost
                            double metrics_x = vertexData_[surface][i][j].vder0x * 1.0 / directions_[surface].spacing[0];
                            double wrong_x_part = (u[grid](i - 1, Is[1].getBase(), j) * cxgf + u[grid](i - 2, Is[1].getBase(), j) * cxgs) * metrics_x * nx;
                            dn = dn - wrong_x_part;
                            // Get the extrapolation coefficients along axis 2 (origin s=0 at the first ghost layer)
                            const int ext_stencil_size = 5; // 4th order extrapolation
                            double s[ext_stencil_size], ec[ext_stencil_size];
                            s[0] = 0.;
                            int counter = 1;
                            double ds = abs(v(i, Is[1].getBase(), j, axis1) - v(i + 1, Is[1].getBase(), j, axis1));
                            for (int p = Is[0].getBase() - 1; p < ext_stencil_size - 2; p++)
                            {
                                double x0 = v(p, Is[1].getBase(), j, axis1);
                                double x1 = v(p + 1, Is[1].getBase(), j, axis1);
                                s[counter] = abs(x0 - x1) + s[counter - 1] * ds;
                                s[counter] = s[counter] / ds;
                                counter++;
                            }
                            double xsg = -abs(v(i - 2, Is[1].getBase(), j, axis1) - v(i - 1, Is[1].getBase(), j, axis1)) / ds;
                            LagrangeInterpolation(ext_stencil_size, s, xsg, ec);
                            double c1 = cxgf * nx * metrics_x;
                            double c2 = cxgs * nx * metrics_x;
                            double sum_e_u = 0., sum_e_u_sg = 0.;
                            for (int e = 1; e < ext_stencil_size; e++)
                                sum_e_u += ec[e] * u[grid](i + e - 1, Is[1].getBase(), j);

                            double rhs = forcing[grid](i - 1, Is[1].getBase(), j);

                            // Now fill out the ghost layers
                            u[grid](i - 1, directions_[surface].Is[1].getBase(), j) = (rhs - dn - c2 * sum_e_u) / (c1 + ec[0] * c2);
                            for (int e = 0; e < ext_stencil_size; e++)
                                sum_e_u_sg += ec[e] * u[grid](i + e - 1, Is[1].getBase(), j);
                            u[grid](i - 2, directions_[surface].Is[1].getBase(), j) = sum_e_u_sg;
                        }
                        else
                            throw runtime_error(GetColoredMessage("\t Error (OW3D), Upwind::ApplyNeumannCondition.cpp.\n\t maaf made a wrong assumption to write this code!", 0));
                    }
                }
                else if (directions_[surface].index[0] == 1) // The axis along the Neumann BC
                    throw runtime_error("finish me!");
            }
            if (mg.boundaryCondition()(0, 1) == boundaryTypes_->exciting or mg.boundaryCondition()(0, 1) == boundaryTypes_->absorbing)
            {
                // Ghost points are in the base of direction 1 (base-1, and base-2)
                int side = 0;
                int axis = 1;
                const RealArray &vbn = mg.vertexBoundaryNormal(side, axis);

                if (directions_[surface].index[0] == 0) // The axis in to the Neumann BC
                    throw runtime_error("finish me!");
                else if (directions_[surface].index[0] == 1) // The axis in to the Neumann BC
                {
                    int i = Is[1].getBase();
                    int j = Is[2].getBound();
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        const Range &R1x = vertexData_[surface][i][j].R1x;
                        double nx = vbn(Is[0].getBase(), i, j, axis1);
                        double dx = sum(u[grid](Is[0].getBase(), R1x, j) * vertexData_[surface][i][j].C1x) *
                                    vertexData_[surface][i][j].vder1x * 1.0 / directions_[surface].spacing[1];
                        double dn = nx * dx;

                        if (R1x.getBase() == Is[1].getBase()) // No ghost points in the stencil
                            continue;
                        else if (R1x.getBase() == Is[1].getBase() - 1) // Only one ghost layer
                            throw runtime_error("finish me!");
                        else if (R1x.getBase() == Is[1].getBase() - 2)
                        {
                            // Find the "wrong" parts in x and z derivatives
                            int fi = 1;                                       // The index in the range where 1st ghost sits
                            int si = 0;                                       // The index in the range where 2nd ghost sits
                            double cxgf = vertexData_[surface][i][j].C1x(0,fi); // The coefficient for the 1st ghost
                            double cxgs = vertexData_[surface][i][j].C1x(0,si); // The coefficient for the 2nd ghost
                            double metrics_x = vertexData_[surface][i][j].vder1x * 1.0 / directions_[surface].spacing[1];
                            double wrong_x_part = (u[grid](Is[0].getBase(), i - 1, j) * cxgf + u[grid](Is[0].getBase(), i - 2, j) * cxgs) * metrics_x * nx;
                            dn = dn - wrong_x_part;
                            // Get the extrapolation coefficients along axis 2 (origin s=0 at the first ghost layer)
                            const int ext_stencil_size = 5; // 4th order extrapolation
                            double s[ext_stencil_size], ec[ext_stencil_size];
                            s[0] = 0.;
                            int counter = 1;
                            double ds = abs(v(Is[0].getBase(), i - 1, j, axis1) - v(Is[0].getBase(), i, j, axis1));
                            for (int p = Is[1].getBase() - 1; p < ext_stencil_size - 2; p++)
                            {
                                double x0 = v(Is[0].getBase(), p, j, axis1);
                                double x1 = v(Is[0].getBase(), p + 1, j, axis1);
                                s[counter] = abs(x0 - x1) + s[counter - 1] * ds;
                                s[counter] = s[counter] / ds;
                                counter++;
                            }
                            double xsg = -abs(v(Is[0].getBase(), i - 2, j, axis1) - v(Is[0].getBase(), i - 1, j, axis1)) / ds;
                            LagrangeInterpolation(ext_stencil_size, s, xsg, ec);
                            double c1 = cxgf * nx * metrics_x;
                            double c2 = cxgs * nx * metrics_x;
                            double sum_e_u = 0., sum_e_u_sg = 0.;
                            for (int e = 1; e < ext_stencil_size; e++)
                                sum_e_u += ec[e] * u[grid](Is[0].getBase(), i + e - 1, j);

                            double rhs = forcing[grid](Is[0].getBase(), i - 1, j);

                            // Now fill out the ghost layers
                            u[grid](Is[0].getBase(), i - 1, j) = (rhs - dn - c2 * sum_e_u) / (c1 + ec[0] * c2);
                            for (int e = 0; e < ext_stencil_size; e++)
                                sum_e_u_sg += ec[e] * u[grid](Is[0].getBase(), i + e - 1, j);
                            u[grid](Is[0].getBase(), i - 2, j) = sum_e_u_sg;
                        }
                        else
                            throw runtime_error(GetColoredMessage("\t Error (OW3D), Upwind::ApplyNeumannCondition.cpp.\n\t maaf made a wrong assumption to write this code!", 0));
                    }
                }
            }
            if (mg.boundaryCondition()(1, 0) == boundaryTypes_->exciting or mg.boundaryCondition()(1, 0) == boundaryTypes_->absorbing)
            {
                // Ghost points are in the bound of direction 0 (base-1, and base-2)
                int side = 1;
                int axis = 0;
                const RealArray &vbn = mg.vertexBoundaryNormal(side, axis);
                if (directions_[surface].index[0] == 0) // The axis in to neumann BC
                {
                    int i = Is[0].getBound();
                    int j = Is[2].getBound();
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        const Range &R0x = vertexData_[surface][i][j].R0x;
                        double nx = vbn(i, Is[1].getBase(), j, axis1);
                        double dx = sum(u[grid](vertexData_[surface][i][j].R0x, Is[1].getBase(), j) * vertexData_[surface][i][j].C0x) *
                                    vertexData_[surface][i][j].vder0x * 1.0 / directions_[surface].spacing[0];
                        double dn = nx * dx;

                        if (R0x.getBound() == Is[0].getBound()) // No ghost points in the stencil
                            continue;
                        else if (R0x.getBound() == Is[0].getBound() + 1) // Only one ghost layer
                            throw runtime_error("finish me!");
                        else if (R0x.getBound() == Is[0].getBound() + 2)
                        {
                            // Find the "wrong" parts in x and z derivatives
                            int fi = R0x.length() - 2;                        // The index in the range where 1st ghost sits
                            int si = R0x.length() - 1;                        // The index in the range where 2nd ghost sits
                            double cxgf = vertexData_[surface][i][j].C0x(fi); // The coefficient for the 1st ghost
                            double cxgs = vertexData_[surface][i][j].C0x(si); // The coefficient for the 2nd ghost
                            double metrics_x = vertexData_[surface][i][j].vder0x * 1.0 / directions_[surface].spacing[0];
                            double wrong_x_part = (u[grid](i + 1, Is[1].getBase(), j) * cxgf + u[grid](i + 2, Is[1].getBase(), j) * cxgs) * metrics_x * nx;
                            dn = dn - wrong_x_part;
                            // Get the extrapolation coefficients along axis 2 (origin s=0 at the first ghost layer)
                            const int ext_stencil_size = 5; // 4th order extrapolation
                            double s[ext_stencil_size], ec[ext_stencil_size];
                            s[0] = 0.;
                            int counter = 1;
                            double ds = abs(v(i, Is[1].getBase(), j, axis1) - v(i + 1, Is[1].getBase(), j, axis1));
                            for (int p = Is[0].getBound() + 1; p > (Is[0].getBound() - ext_stencil_size + 2); p--)
                            {
                                double x0 = v(p, Is[1].getBase(), j, axis1);
                                double x1 = v(p - 1, Is[1].getBase(), j, axis1);
                                s[counter] = abs(x0 - x1) + s[counter - 1] * ds;
                                s[counter] = s[counter] / ds;
                                counter++;
                            }
                            double xsg = -abs(v(i + 2, Is[1].getBase(), j, axis1) - v(i + 1, Is[1].getBase(), j, axis1)) / ds;
                            LagrangeInterpolation(ext_stencil_size, s, xsg, ec);
                            double c1 = cxgf * nx * metrics_x;
                            double c2 = cxgs * nx * metrics_x;
                            double sum_e_u = 0., sum_e_u_sg = 0.;
                            for (int e = 1; e < ext_stencil_size; e++)
                                sum_e_u += ec[e] * u[grid](i - e + 1, Is[1].getBase(), j);

                            double rhs = forcing[grid](i + 1, Is[1].getBase(), j);

                            // Now fill out the ghost layers
                            u[grid](i + 1, directions_[surface].Is[1].getBase(), j) = (rhs - dn - c2 * sum_e_u) / (c1 + ec[0] * c2);
                            for (int e = 0; e < ext_stencil_size; e++)
                                sum_e_u_sg += ec[e] * u[grid](i - e + 1, Is[1].getBase(), j);
                            u[grid](i + 2, directions_[surface].Is[1].getBase(), j) = sum_e_u_sg;
                        }
                        else
                            throw runtime_error(GetColoredMessage("\t Error (OW3D), Upwind::ApplyNeumannCondition.cpp.\n\t maaf made a wrong assumption to write this code!", 0));
                    }
                }
                else if (directions_[surface].index[0] == 1) // The axis along the Neumann BC
                    throw runtime_error("finish me!");
            }
        }
        else
        {
            if (mg.boundaryCondition()(0, 2) == boundaryTypes_->exciting or mg.boundaryCondition()(0, 2) == boundaryTypes_->absorbing)
            {
                // Ghost points are in the base of direction 2 (base-1, and base-2)
                int side = 0;
                int axis = 2;
                const RealArray &vbn = mg.vertexBoundaryNormal(side, axis);
                int start, end;
                if (directions_[surface].index[0] == 0) // The axis along the Neumann BC
                {
                    start = Is[0].getBase();
                    end = Is[0].getBound();
                    int j = Is[2].getBase();
                    for (int i = start; i <= end; i++) // Goes along the Neumann boundary (body or wall)
                    {
                        if (vertexData_[surface][i][j].mask > 0)
                        {
                            const Range &R2x = vertexData_[surface][i][j].R2x;
                            const Range &R2z = vertexData_[surface][i][j].R2z;
                            double nx = vbn(i, Is[1].getBase(), j, axis1);
                            double nz = vbn(i, Is[1].getBase(), j, axis3);
                            // Compute x and z derivatives for this point on the neumann BC
                            double dx = sum(u[grid](vertexData_[surface][i][j].R0x, directions_[surface].Is[1].getBase(), j) * vertexData_[surface][i][j].C0x) *
                                            vertexData_[surface][i][j].vder0x * 1.0 / directions_[surface].spacing[0] +
                                        sum(u[grid](i, directions_[surface].Is[1].getBase(), vertexData_[surface][i][j].R2x) * vertexData_[surface][i][j].C2x) *
                                            vertexData_[surface][i][j].vder2x * 1.0 / directions_[surface].spacing[2];
                            double dz = sum(u[grid](vertexData_[surface][i][j].R0z, directions_[surface].Is[1].getBase(), j) * vertexData_[surface][i][j].C0z) *
                                            vertexData_[surface][i][j].vder0z * 1.0 / directions_[surface].spacing[0] +
                                        sum(u[grid](i, directions_[surface].Is[1].getBase(), vertexData_[surface][i][j].R2z) * vertexData_[surface][i][j].C2z) *
                                            vertexData_[surface][i][j].vder2z * 1.0 / directions_[surface].spacing[2];
                            double dn = nx * dx + nz * dz;

                            // Now fill out the ghost points

                            if (R2x.getBase() == Is[2].getBase() && R2z.getBase() == Is[2].getBase()) // No ghost points in the stencil
                                continue;

                            else if (R2x.getBase() == Is[2].getBase() - 1 && R2z.getBase() == Is[2].getBase()) // One ghost layer only in R2x
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() && R2z.getBase() == Is[2].getBase() - 1) // One ghost layer only in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 1 && R2z.getBase() == Is[2].getBase() - 1) // One ghost layer both in R2x and R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 2 && R2z.getBase() == Is[2].getBase()) // Two ghost layers only in R2x
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() && R2z.getBase() == Is[2].getBase() - 2) // Two ghost layers only in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 2 && R2z.getBase() == Is[2].getBase() - 1) // Two ghost layers in R2x, one layer in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 1 && R2z.getBase() == Is[2].getBase() - 2) // One ghost layer in R2x, two layers in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 2 && R2z.getBase() == Is[2].getBase() - 2) // Two ghost layers both in R2x and R2z
                            {
                                // Find the "wrong" parts in x and z derivatives
                                int fi = 1;                                             // The index in the range where 1st ghost sits
                                int si = 0;                                             // The index in the range where 2nd ghost sits
                                double cxgf = vertexData_[surface][i][j].C2x(0, 0, fi); // The coefficient for the 1st ghost
                                double cxgs = vertexData_[surface][i][j].C2x(0, 0, si); // The coefficient for the 2nd ghost
                                double metrics_x = vertexData_[surface][i][j].vder2x * 1.0 / directions_[surface].spacing[2];
                                double wrong_x_part = (u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBase() - 1) * cxgf +
                                                       u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBase() - 2) * cxgs) *
                                                      metrics_x * nx;
                                fi = 1;                                                 // The index in the range where 1st ghost sits
                                si = 0;                                                 // The index in the range where 2nd ghost sits
                                double czgf = vertexData_[surface][i][j].C2z(0, 0, fi); // The coefficient for the 1st ghost
                                double czgs = vertexData_[surface][i][j].C2z(0, 0, si); // The coefficient for the 2nd ghost
                                double metrics_z = vertexData_[surface][i][j].vder2z * 1.0 / directions_[surface].spacing[2];
                                double wrong_z_part = (u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBase() - 1) * czgf +
                                                       u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBase() - 2) * czgs) *
                                                      metrics_z * nz;
                                dn = dn - wrong_x_part - wrong_z_part;
                                // Get the extrapolation coefficients along axis 2 (origin s=0 at the first ghost layer)
                                const int ext_stencil_size = 5; // 4th order extrapolation
                                double s[ext_stencil_size], ec[ext_stencil_size];
                                s[0] = 0.;
                                int counter = 1;
                                double delx = v(i, Is[1].getBase(), j - 1, axis1) - v(i, Is[1].getBase(), j, axis1);
                                double delz = v(i, Is[1].getBase(), j - 1, axis3) - v(i, Is[1].getBase(), j, axis3);
                                double ds = sqrt(delx * delx + delz * delz);
                                for (int p = Is[2].getBase() - 1; p < ext_stencil_size - 2; p++)
                                {
                                    double x0 = v(i, Is[1].getBase(), p, axis1);
                                    double x1 = v(i, Is[1].getBase(), p + 1, axis1);
                                    double z0 = v(i, Is[1].getBase(), p, axis3);
                                    double z1 = v(i, Is[1].getBase(), p + 1, axis3);
                                    s[counter] = sqrt((x0 - x1) * (x0 - x1) + (z0 - z1) * (z0 - z1)) + s[counter - 1] * ds;
                                    s[counter] = s[counter] / ds;
                                    counter++;
                                }
                                double del_xsg = abs(v(i, Is[1].getBase(), j - 2, axis1) - v(i, Is[1].getBase(), j - 1, axis1));
                                double del_zsg = abs(v(i, Is[1].getBase(), j - 2, axis3) - v(i, Is[1].getBase(), j - 1, axis3));
                                double xsg = -sqrt(del_xsg * del_xsg + del_zsg * del_zsg) / ds;
                                LagrangeInterpolation(ext_stencil_size, s, xsg, ec);
                                double c1 = cxgf * nx * metrics_x + czgf * nz * metrics_z;
                                double c2 = cxgs * nx * metrics_x + czgs * nz * metrics_z;
                                double sum_e_u = 0., sum_e_u_sg = 0.;
                                for (int e = 1; e < ext_stencil_size; e++)
                                    sum_e_u += ec[e] * u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBase() + e - 1);

                                double rhs = forcing[grid](i, Is[1].getBase(), Is[2].getBase() - 1);

                                // Now fill out the ghost layers
                                u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBase() - 1) = (rhs - dn - c2 * sum_e_u) / (c1 + ec[0] * c2);
                                for (int e = 0; e < ext_stencil_size; e++)
                                    sum_e_u_sg += ec[e] * u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBase() + e - 1);
                                u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBase() - 2) = sum_e_u_sg;

                                continue; // Job finished for this point
                            }
                            else
                                throw runtime_error(GetColoredMessage("\t Error (OW3D), Upwind::ApplyNeumannCondition.cpp.\n\t maaf made a wrong assumption to write this code!", 0));
                        }
                    }
                }
                else if (directions_[surface].index[0] == 1)
                {
                    start = Is[1].getBase();
                    end = Is[1].getBound();
                    int j = Is[2].getBase();
                    for (int i = start; i <= end; i++) // Goes along the Neumann boundary (body or wall)
                    {
                        const Range &R2x = vertexData_[surface][i][j].R2x;
                        const Range &R2z = vertexData_[surface][i][j].R2z;
                        if (vertexData_[surface][i][j].mask > 0)
                        {
                            double nx = vbn(Is[0].getBase(), i, j, axis1);
                            double nz = vbn(Is[0].getBase(), i, j, axis3);
                            // Compute x and z derivatives for this point on the neumann BC
                            double dx = sum(u[grid](directions_[surface].Is[0].getBase(), vertexData_[surface][i][j].R1x, j) * vertexData_[surface][i][j].C1x) *
                                            vertexData_[surface][i][j].vder1x * 1.0 / directions_[surface].spacing[1] +
                                        sum(u[grid](directions_[surface].Is[0].getBase(), i, vertexData_[surface][i][j].R2x) * vertexData_[surface][i][j].C2x) *
                                            vertexData_[surface][i][j].vder2x * 1.0 / directions_[surface].spacing[2];
                            double dz = sum(u[grid](directions_[surface].Is[0].getBase(), vertexData_[surface][i][j].R1z, j) * vertexData_[surface][i][j].C1z) *
                                            vertexData_[surface][i][j].vder1z * 1.0 / directions_[surface].spacing[1] +
                                        sum(u[grid](directions_[surface].Is[0].getBase(), i, vertexData_[surface][i][j].R2z) * vertexData_[surface][i][j].C2z) *
                                            vertexData_[surface][i][j].vder2z * 1.0 / directions_[surface].spacing[2];
                            double dn = nx * dx + nz * dz;
                            // Now fill out the ghost points

                            if (R2x.getBase() == Is[2].getBase() && R2z.getBase() == Is[2].getBase()) // No ghost points in the stencil
                                continue;

                            else if (R2x.getBase() == Is[2].getBase() - 1 && R2z.getBase() == Is[2].getBase()) // One ghost layer only in R2x
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() && R2z.getBase() == Is[2].getBase() - 1) // One ghost layer only in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 1 && R2z.getBase() == Is[2].getBase() - 1) // One ghost layer both in R2x and R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 2 && R2z.getBase() == Is[2].getBase()) // Two ghost layers only in R2x
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() && R2z.getBase() == Is[2].getBase() - 2) // Two ghost layers only in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 2 && R2z.getBase() == Is[2].getBase() - 1) // Two ghost layers in R2x, one layer in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 1 && R2z.getBase() == Is[2].getBase() - 2) // One ghost layer in R2x, two layers in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBase() == Is[2].getBase() - 2 && R2z.getBase() == Is[2].getBase() - 2) // Two ghost layers both in R2x and R2z
                            {
                                // Find the "wrong" parts in x and z derivatives
                                int fi = 1;                                             // The index in the range where 1st ghost sits
                                int si = 0;                                             // The index in the range where 2nd ghost sits
                                double cxgf = vertexData_[surface][i][j].C2x(0, 0, fi); // The coefficient for the 1st ghost
                                double cxgs = vertexData_[surface][i][j].C2x(0, 0, si); // The coefficient for the 2nd ghost
                                double metrics_x = vertexData_[surface][i][j].vder2x * 1.0 / directions_[surface].spacing[2];
                                double wrong_x_part = (u[grid](directions_[surface].Is[0].getBase(), i, Is[2].getBase() - 1) * cxgf +
                                                       u[grid](directions_[surface].Is[0].getBase(), i, Is[2].getBase() - 2) * cxgs) *
                                                      metrics_x * nx;
                                fi = 1;                                                 // The index in the range where 1st ghost sits
                                si = 0;                                                 // The index in the range where 2nd ghost sits
                                double czgf = vertexData_[surface][i][j].C2z(0, 0, fi); // The coefficient for the 1st ghost
                                double czgs = vertexData_[surface][i][j].C2z(0, 0, si); // The coefficient for the 2nd ghost
                                double metrics_z = vertexData_[surface][i][j].vder2z * 1.0 / directions_[surface].spacing[2];
                                double wrong_z_part = (u[grid](directions_[surface].Is[0].getBase(), i, Is[2].getBase() - 1) * czgf +
                                                       u[grid](directions_[surface].Is[0].getBase(), i, Is[2].getBase() - 2) * czgs) *
                                                      metrics_z * nz;
                                dn = dn - wrong_x_part - wrong_z_part;
                                // Get the extrapolation coefficients along axis 2 (origin s=0 at the first ghost layer)
                                const int ext_stencil_size = 5; // 4th order extrapolation
                                double s[ext_stencil_size], ec[ext_stencil_size];
                                s[0] = 0.;
                                int counter = 1;
                                double delx = v(Is[0].getBase(), i, j - 1, axis1) - v(Is[0].getBase(), i, j, axis1);
                                double delz = v(Is[0].getBase(), i, j - 1, axis3) - v(Is[0].getBase(), i, j, axis3);
                                double ds = sqrt(delx * delx + delz * delz);
                                for (int p = Is[2].getBase() - 1; p < ext_stencil_size - 2; p++)
                                {
                                    double x0 = v(Is[0].getBase(), i, p, axis1);
                                    double x1 = v(Is[0].getBase(), i, p + 1, axis1);
                                    double z0 = v(Is[0].getBase(), i, p, axis3);
                                    double z1 = v(Is[0].getBase(), i, p + 1, axis3);
                                    s[counter] = sqrt((x0 - x1) * (x0 - x1) + (z0 - z1) * (z0 - z1)) + s[counter - 1] * ds;
                                    s[counter] = s[counter] / ds;
                                    counter++;
                                }
                                double del_xsg = v(Is[0].getBase(), i, j - 2, axis1) - v(Is[0].getBase(), i, j - 1, axis1);
                                double del_zsg = v(Is[0].getBase(), i, j - 2, axis3) - v(Is[0].getBase(), i, j - 1, axis3);
                                double xsg = -sqrt(del_xsg * del_xsg + del_zsg * del_zsg) / ds;
                                LagrangeInterpolation(ext_stencil_size, s, xsg, ec);
                                double c1 = cxgf * nx * metrics_x + czgf * nz * metrics_z;
                                double c2 = cxgs * nx * metrics_x + czgs * nz * metrics_z;
                                double sum_e_u = 0., sum_e_u_sg = 0.;
                                for (int e = 1; e < ext_stencil_size; e++)
                                    sum_e_u += ec[e] * u[grid](directions_[surface].Is[0].getBase(), i, Is[2].getBase() + e - 1);

                                double rhs = forcing[grid](Is[0].getBase(), i, Is[2].getBase() - 1);

                                // Now fill out the ghost layers
                                u[grid](directions_[surface].Is[0].getBase(), i, Is[2].getBase() - 1) = (rhs - dn - c2 * sum_e_u) / (c1 + ec[0] * c2);
                                for (int e = 0; e < ext_stencil_size; e++)
                                    sum_e_u_sg += ec[e] * u[grid](directions_[surface].Is[0].getBase(), i, Is[2].getBase() + e - 1);
                                u[grid](directions_[surface].Is[0].getBase(), i, Is[2].getBase() - 2) = sum_e_u_sg;

                                continue; // Job finished for this point
                            }
                            else
                                throw runtime_error(GetColoredMessage("\t Error (OW3D), Upwind::ApplyNeumannCondition.cpp.\n\t maaf made a wrong assumption to write this code!", 0));
                        }
                    }
                }
            }
            if (mg.boundaryCondition()(1, 1) == boundaryTypes_->exciting or mg.boundaryCondition()(1, 1) == boundaryTypes_->absorbing)
            {
                throw runtime_error("finish me!");
            }
            if (mg.boundaryCondition()(1, 2) == boundaryTypes_->exciting or mg.boundaryCondition()(1, 2) == boundaryTypes_->absorbing)
            {
                int side = 1;
                int axis = 2;
                // Ghost points are in the bound of direction 2 (bound+1, and bound+2)
                int start, end;
                if (directions_[surface].index[0] == 0) // The axis along the Neumann BC
                {
                    start = Is[0].getBase();
                    end = Is[0].getBound();
                    int j = Is[2].getBound();
                    const RealArray &vbn = mg.vertexBoundaryNormal(side, axis);
                    for (int i = start; i <= end; i++) // Goes along the Neumann boundary (body or wall)
                    {
                        const Range &R2x = vertexData_[surface][i][Is[2].getBound()].R2x;
                        const Range &R2z = vertexData_[surface][i][Is[2].getBound()].R2z;
                        if (vertexData_[surface][i][j].mask > 0)
                        {
                            double nx = vbn(i, Is[1].getBase(), Is[2].getBound(), axis1);
                            double nz = vbn(i, Is[2].getBase(), Is[2].getBound(), axis3);
                            // Compute x and z derivatives for this point on the neumann BC
                            double dx = sum(u[grid](vertexData_[surface][i][j].R0x, directions_[surface].Is[1].getBase(), j) * vertexData_[surface][i][j].C0x) *
                                            vertexData_[surface][i][j].vder0x * 1.0 / directions_[surface].spacing[0] +
                                        sum(u[grid](i, directions_[surface].Is[1].getBase(), vertexData_[surface][i][j].R2x) * vertexData_[surface][i][j].C2x) *
                                            vertexData_[surface][i][j].vder2x * 1.0 / directions_[surface].spacing[2];
                            double dz = sum(u[grid](vertexData_[surface][i][j].R0z, directions_[surface].Is[1].getBase(), j) * vertexData_[surface][i][j].C0z) *
                                            vertexData_[surface][i][j].vder0z * 1.0 / directions_[surface].spacing[0] +
                                        sum(u[grid](i, directions_[surface].Is[1].getBase(), vertexData_[surface][i][j].R2z) * vertexData_[surface][i][j].C2z) *
                                            vertexData_[surface][i][j].vder2z * 1.0 / directions_[surface].spacing[2];
                            double dn = nx * dx + nz * dz;

                            // Now fill out the ghost points

                            if (R2x.getBound() == Is[2].getBound() && R2z.getBound() == Is[2].getBound()) // No ghost points in the stencil
                                continue;

                            else if (R2x.getBound() == Is[2].getBound() + 1 && R2z.getBound() == Is[2].getBound()) // One ghost layer only in R2x
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBound() == Is[2].getBound() && R2z.getBound() == Is[2].getBound() + 1) // One ghost layer only in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBound() == Is[2].getBound() + 1 && R2z.getBound() == Is[2].getBound() + 1) // One ghost layer both in R2x and R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBound() == Is[2].getBound() + 2 && R2z.getBound() == Is[2].getBound()) // Two ghost layers only in R2x
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBound() == Is[2].getBound() && R2z.getBound() == Is[2].getBound() + 2) // Two ghost layers only in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBound() == Is[2].getBound() + 2 && R2z.getBound() == Is[2].getBound() + 1) // Two ghost layers in R2x, one layer in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBound() == Is[2].getBound() + 1 && R2z.getBound() == Is[2].getBound() + 2) // One ghost layer in R2x, two layers in R2z
                            {
                                throw runtime_error("finish me!");
                            }
                            else if (R2x.getBound() == Is[2].getBound() + 2 && R2z.getBound() == Is[2].getBound() + 2) // Two ghost layers both in R2x and R2z
                            {
                                // Find the "wrong" parts in x and z derivatives
                                int fi = R2x.length() - 2;                              // The index in the range where 1st ghost sits
                                int si = R2x.length() - 1;                              // The index in the range where 2nd ghost sits
                                double cxgf = vertexData_[surface][i][j].C2x(0, 0, fi); // The coefficient for the 1st ghost
                                double cxgs = vertexData_[surface][i][j].C2x(0, 0, si); // The coefficient for the 2nd ghost
                                double metrics_x = vertexData_[surface][i][j].vder2x * 1.0 / directions_[surface].spacing[2];
                                double wrong_x_part = (u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBound() + 1) * cxgf +
                                                       u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBound() + 2) * cxgs) *
                                                      metrics_x * nx;
                                fi = R2z.length() - 2;                                  // The index in the range where 1st ghost sits
                                si = R2z.length() - 1;                                  // The index in the range where 2nd ghost sits
                                double czgf = vertexData_[surface][i][j].C2z(0, 0, fi); // The coefficient for the 1st ghost
                                double czgs = vertexData_[surface][i][j].C2z(0, 0, si); // The coefficient for the 2nd ghost
                                double metrics_z = vertexData_[surface][i][j].vder2z * 1.0 / directions_[surface].spacing[2];
                                double wrong_z_part = (u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBound() + 1) * czgf +
                                                       u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBound() + 2) * czgs) *
                                                      metrics_z * nz;
                                dn = dn - wrong_x_part - wrong_z_part;
                                // Get the extrapolation coefficients along axis 2 (origin s=0 at the first ghost layer)
                                const int ext_stencil_size = 5;
                                double s[ext_stencil_size], ec[ext_stencil_size];
                                s[0] = 0.;
                                int counter = 1;
                                double delx = v(i, Is[1].getBase(), j + 1, axis1) - v(i, Is[1].getBase(), j, axis1);
                                double delz = v(i, Is[1].getBase(), j + 1, axis3) - v(i, Is[1].getBase(), j, axis3);
                                double ds = sqrt(delx * delx + delz * delz);
                                for (int p = Is[2].getBound() + 1; p > (Is[2].getBound() - ext_stencil_size + 2); p--)
                                {
                                    double x0 = v(i, Is[1].getBase(), p, axis1);
                                    double x1 = v(i, Is[1].getBase(), p - 1, axis1);
                                    double z0 = v(i, Is[1].getBase(), p, axis3);
                                    double z1 = v(i, Is[1].getBase(), p - 1, axis3);
                                    s[counter] = sqrt((x0 - x1) * (x0 - x1) + (z0 - z1) * (z0 - z1)) + s[counter - 1] * ds;
                                    s[counter] = s[counter] / ds;
                                    counter++;
                                }
                                double del_xsg = v(i, Is[1].getBase(), j + 2, axis1) - v(i, Is[1].getBase(), j + 1, axis1);
                                double del_zsg = v(i, Is[1].getBase(), j + 2, axis3) - v(i, Is[1].getBase(), j + 1, axis3);
                                double xsg = -sqrt(del_xsg * del_xsg + del_zsg * del_zsg) / ds;
                                LagrangeInterpolation(ext_stencil_size, s, xsg, ec);
                                double c1 = cxgf * nx * metrics_x + czgf * nz * metrics_z;
                                double c2 = cxgs * nx * metrics_x + czgs * nz * metrics_z;
                                double sum_e_u = 0., sum_e_u_sg = 0.;
                                for (int e = 1; e < ext_stencil_size; e++)
                                    sum_e_u += ec[e] * u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBound() - e + 1);

                                double rhs = forcing[grid](i, Is[1].getBase(), Is[2].getBound() + 1);

                                // Now fill out the ghost layers
                                u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBound() + 1) = (rhs - dn - c2 * sum_e_u) / (c1 + ec[0] * c2);
                                for (int e = 0; e < ext_stencil_size; e++)
                                    sum_e_u_sg += ec[e] * u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBound() + 1 - e);
                                u[grid](i, directions_[surface].Is[1].getBase(), Is[2].getBound() + 2) = sum_e_u_sg;

                                continue; // Job finished for this point
                            }
                            else
                                throw runtime_error(GetColoredMessage("\t Error (OW3D), Upwind::ApplyNeumannCondition.cpp.\n\t maaf made a wrong assumption to write this code!", 0));
                        }
                    }
                }
                else if (directions_[surface].index[0] == 1)
                {
                    start = Is[1].getBase();
                    end = Is[1].getBound();
                    throw runtime_error("finish me!");
                }
            }
        }
    } // end of loop over free surface

} // end of ApplyNeumannCondition public member function