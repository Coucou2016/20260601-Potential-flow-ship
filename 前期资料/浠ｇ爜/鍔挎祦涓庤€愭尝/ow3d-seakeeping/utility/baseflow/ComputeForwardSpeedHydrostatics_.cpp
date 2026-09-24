#include "Solver.h"
#include "Ogshow.h"
#include "CompositeGridOperators.h"
#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::ComputeForwardSpeedHydrostatics_()
{
    vector<OW3DSeakeeping::HydrodynamicProblem> runs = OW3DSeakeeping::UserInput.rad_runs;
    int nod = cg_->numberOfDimensions();
    int order_space = gridData_->order_space;
    int stencil_points = floor(pow(order_space + 1, nod) + 1.5); // add 1 for interpolation equations
    int ghost_lines = order_space / 2;
    Range all;
    realCompositeGridFunction system_matrix, system_right;
    system_matrix.updateToMatchGrid(*cg_, stencil_points, all, all, all);
    system_matrix.setIsACoefficientMatrix(true, stencil_points, ghost_lines);
    CompositeGridOperators operators = OW3DSeakeeping::DefineOperators(*cg_, gridData_->order_space);
    system_matrix.setOperators(operators);

    BoundaryConditionParameters parameters;
    parameters.ghostLineToAssign = ghost_lines;

    Integrate integrator;
    if (gridData_->triangulation.patches.size() == 0)
        integrator = GetIntegratorOverBody(*cg_, *boundariesData_); // Composite grid integrator

    int numberOFIntegrations = gridData_->halfSymmetry ? 2 : 1;

    for (unsigned int mode_index = 0; mode_index < runs.size(); mode_index++) // Solve the hydrodynamic problems
    {
        OW3DSeakeeping::MODE_NAMES mode_name = runs[mode_index].mode;

        // order of operations is as follows:
        // 1. apply Laplacian at all interior and boundary points,
        // 2. apply Dirichlet boundary condition at free surfaces,
        // 3. extrapolate first ghost layer at free surfaces,
        // 4. apply neumann boundary condition at body surfaces via first ghost layer,
        // 5. apply neumann boundary condition at bed and absorbing surfaces
        // 7. extrapolate second ghost layer if required,
        // 8. extrapolate corner ghost points.

        system_matrix = operators.laplacianCoefficients(); // populate system matrix with finite-difference coefficients.
        system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::dirichlet, gridData_->boundaryTypes.free);
        system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, gridData_->boundaryTypes.free);
        system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_->boundaryTypes.absorbing);
        system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_->boundaryTypes.exciting);
        system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_->boundaryTypes.impermeable);

        if (nod == 3 and gridData_->halfSymmetry)
        {
            if (runs[mode_index].mat_type == MAT_TYPES::SYMMAT)
                system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_->boundaryTypes.symmetry);

            if (runs[mode_index].mat_type == MAT_TYPES::ASMMAT)
            {
                system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::dirichlet, gridData_->boundaryTypes.symmetry);
                system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, gridData_->boundaryTypes.symmetry);
            }
        }

        if (order_space == 4)
            system_matrix.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, BCTypes::allBoundaries, parameters);

        system_matrix.finishBoundaryConditions();

        system_right.updateToMatchGrid(*cg_);
        system_right = 0.;

        for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
        {
            const Single_boundary_data &be = boundariesData_->exciting[surface];
            const vector<Index> &Is = be.surface_indices;
            const vector<Index> &Ig = be.ghost_indices;

            switch (mode_name)
            {
            case OW3DSeakeeping::MODE_NAMES::SURGE:
                system_right[be.grid](Ig[0], Ig[1], Ig[2]) = data_.mterms.m1[surface](Is[0], Is[1], Is[2]);
                break;
            case OW3DSeakeeping::MODE_NAMES::HEAVE:
                system_right[be.grid](Ig[0], Ig[1], Ig[2]) = data_.mterms.m2[surface](Is[0], Is[1], Is[2]);
                break;
            case OW3DSeakeeping::MODE_NAMES::SWAY:
                system_right[be.grid](Ig[0], Ig[1], Ig[2]) = data_.mterms.m3[surface](Is[0], Is[1], Is[2]);
                break;
            case OW3DSeakeeping::MODE_NAMES::ROLL:
                system_right[be.grid](Ig[0], Ig[1], Ig[2]) = data_.mterms.m4[surface](Is[0], Is[1], Is[2]);
                break;
            case OW3DSeakeeping::MODE_NAMES::YAW:
                system_right[be.grid](Ig[0], Ig[1], Ig[2]) = data_.mterms.m5[surface](Is[0], Is[1], Is[2]);
                break;
            case OW3DSeakeeping::MODE_NAMES::PITCH:
                system_right[be.grid](Ig[0], Ig[1], Ig[2]) = data_.mterms.m6[surface](Is[0], Is[1], Is[2]);
                break;

            default:
                break;
            }
        }
        realCompositeGridFunction phi(*cg_);
        phi = 0.;
        phi.setOperators(operators);

        OW3DSeakeeping::Solver *solver = new OW3DSeakeeping::Solver(*cg_);
        solver->SupplySystemMatrix(system_matrix);
        solver->CalculateSolution(phi, system_right);
        delete solver;

        realCompositeGridFunction phix(*cg_), phiy(*cg_), phiz(*cg_);
        phix = phi.x();
        phiy = phi.y();
        phiz = phi.z();

        realCompositeGridFunction integrand(*cg_);
        integrand = 0.;

        for (int count = 0; count < numberOFIntegrations; count++)
        {
            int sign = (count == 1) ? -1 : 1; // Means integration on the other half of the body

            for (unsigned int resp_index = 0; resp_index < UserInput.responses.size(); resp_index++)
            {
                OW3DSeakeeping::MODE_NAMES resp_name = UserInput.responses[resp_index];

                for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
                {
                    const Single_boundary_data &be = boundariesData_->exciting[surface];
                    const vector<Index> &Is = be.surface_indices;
                    const MappedGrid &mg = (*cg_)[be.grid];
                    const RealArray &v = mg.vertex();
                    const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

                    RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
                    RealArray n1(Is[0], Is[1], Is[2]), n2(Is[0], Is[1], Is[2]), n3(Is[0], Is[1], Is[2]);

                    x = v(Is[0], Is[1], Is[2], axis1);
                    y = v(Is[0], Is[1], Is[2], axis2); // Note : "y" vertical up
                    z = (gridData_->nod == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3) * sign;

                    n1 = vbn(Is[0], Is[1], Is[2], axis1);
                    n2 = vbn(Is[0], Is[1], Is[2], axis2); // Note : "n2" vertical up
                    n3 = (gridData_->nod == 2) ? 0 * n1 : vbn(Is[0], Is[1], Is[2], axis3) * sign;

                    integrand[be.grid](Is[0], Is[1], Is[2]) = (-UserInput.U + data_.BodySurfaceDerivatives[surface].dx) * phix[be.grid](Is[0], Is[1], Is[2]) +
                                                              data_.BodySurfaceDerivatives[surface].dy * phiy[be.grid](Is[0], Is[1], Is[2]) +
                                                              data_.BodySurfaceDerivatives[surface].dz * phiz[be.grid](Is[0], Is[1], Is[2]);

                    switch (resp_name)
                    {
                    case OW3DSeakeeping::MODE_NAMES::SURGE:
                        integrand[be.grid](Is[0], Is[1], Is[2]) *= n1;
                        break;
                    case OW3DSeakeeping::MODE_NAMES::HEAVE:
                        integrand[be.grid](Is[0], Is[1], Is[2]) *= n2;
                        break;
                    case OW3DSeakeeping::MODE_NAMES::SWAY:
                        integrand[be.grid](Is[0], Is[1], Is[2]) *= n3;
                        break;
                    case OW3DSeakeeping::MODE_NAMES::ROLL:
                        integrand[be.grid](Is[0], Is[1], Is[2]) *= (n3 * y - n2 * z);
                        break;
                    case OW3DSeakeeping::MODE_NAMES::YAW:
                        integrand[be.grid](Is[0], Is[1], Is[2]) *= (n1 * z - n3 * x);
                        break;
                    case OW3DSeakeeping::MODE_NAMES::PITCH:
                        integrand[be.grid](Is[0], Is[1], Is[2]) *= (n2 * x - n1 * y);

                    default:
                        break;
                    }
                }

                data_.speed_hydrostatics(mode_index, resp_index) += -OW3DSeakeeping::rho * ComputeSurfaceIntegral(integrator, gridData_->triangulation, integrand);

            } // The response loop

        } // Integration count
    }

    OW3DSeakeeping::PrintLogMessage("Forward-speed hydrostatics computed.");
}