#include "CompositeGridOperators.h"
#include "Grid.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Grid::SetManufacturedSolution_()
{
    string resultsDirectory = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;

    OW3DSeakeeping::All_boundaries_data boundariesData = gridData_.boundariesData;
    CompositeGridOperators operators = OW3DSeakeeping::DefineOperators(cg_, gridData_.order_space);

    man_sol_comp_.updateToMatchGrid(cg_);
    man_sol_comp_ = 0.;
    man_sol_.updateToMatchGrid(cg_);
    man_sol_ = 0.;

    // Set a known solution (man_sol_) on the grid

    double beta = 5 * Pi / 5;
    double K = gridData_.kMax / 10;

    RealCompositeGridFunction Phix(cg_), Phiy(cg_), Phiz(cg_), Phixx(cg_), Phiyy(cg_), Phizz(cg_);

    for (int i = 0; i < (cg_)->numberOfComponentGrids; i++)
    {
        Index I1, I2, I3;
        MappedGrid &mg = (cg_)[i];
        getIndex(mg.dimension(), I1, I2, I3);
        RealArray x = mg.vertex()(I1, I2, I3, axis1);
        RealArray y = mg.vertex()(I1, I2, I3, axis2);
        RealArray z = mg.vertex()(I1, I2, I3, axis3);
        RealArray alpha = x * cos(beta) + z * sin(beta);
        man_sol_[i] = exp(K * y) * cos(K * alpha);
        Phix[i] = -K * cos(beta) * exp(K * y) * sin(K * alpha);
        Phiy[i] = K * exp(K * y) * cos(K * alpha);
        Phiz[i] = -K * sin(beta) * exp(K * y) * sin(K * alpha);
        Phixx[i] = -K * K * exp(K * y) * cos(beta) * cos(beta) * cos(K * alpha);
        Phiyy[i] = K * K * exp(K * y) * cos(K * alpha);
        Phizz[i] = -K * K * exp(K * y) * sin(beta) * sin(beta) * cos(K * alpha);
    }

    // Build the system matrix

    int nod = gridData_.nod;
    int order_space = gridData_.order_space;
    int stencil_points = floor(pow(order_space + 1, nod) + 1.5); // add 1 for interpolation equations
    int ghost_lines = order_space / 2;

    Range all;
    man_system_matrix_.updateToMatchGrid(cg_, stencil_points, all, all, all);
    man_system_matrix_ = 0.0;
    man_system_matrix_.setIsACoefficientMatrix(true, stencil_points, ghost_lines);
    man_system_matrix_.setOperators(operators); // apply operator

    BoundaryConditionParameters parameters;
    parameters.ghostLineToAssign = ghost_lines;

    // Order of operations is as follows:
    // 1. apply Laplacian at all interior and boundary points,
    // 2. apply Dirichlet boundary condition at free surfaces,
    // 3. extrapolate first ghost layer at free surfaces,
    // 4. apply Neumann boundary condition at impermeable surfaces via first ghost layer,
    // 5. apply Neumann boundary condition at exciting surfaces via first ghost layer,
    // 6. apply Neumann boundary condition at absorbing surfaces via first ghost layer,
    // 7. apply symmetry condition at symmetry plane (first ghost layer)
    // 8. extrapolate second ghost layer if required,
    // 9. apply symmetry condition at symmetry plane (second ghost layer)
    // 10. extrapolate corner ghost points.

    man_system_matrix_ = operators.laplacianCoefficients(); // populate system matrix with finite-difference coefficients.

    man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::dirichlet, gridData_.boundaryTypes.free);
    man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, gridData_.boundaryTypes.free);
    man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_.boundaryTypes.impermeable);
    man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_.boundaryTypes.exciting);
    man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_.boundaryTypes.absorbing);

    MAT_TYPES mat_type = MAT_TYPES::SYMMAT;

    if (nod == 3 and gridData_.halfSymmetry)
    {
        if (mat_type == MAT_TYPES::SYMMAT)
            man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_.boundaryTypes.symmetry);

        if (mat_type == MAT_TYPES::ASMMAT)
        {
            man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::dirichlet, gridData_.boundaryTypes.symmetry);
            man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, gridData_.boundaryTypes.symmetry);
        }
    }

    if (order_space == 4)
    {
        man_system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, BCTypes::allBoundaries, parameters);
    }

    man_system_matrix_.finishBoundaryConditions();

    man_system_right_.updateToMatchGrid(cg_);
    man_system_right_ = Phixx + Phiyy + Phizz;

    // Apply Neumann condition at the body

    for (unsigned int surface = 0; surface < boundariesData.exciting.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData.exciting[surface];
        const vector<Index> &Is = be.surface_indices;
        const vector<Index> &Ig = be.ghost_indices;
        const MappedGrid &mg = (cg_)[be.grid];
        const RealArray &v = mg.vertex();
        const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

        RealArray n3(Is[0], Is[1], Is[2]);
        n3 = 0.0;

        if ((cg_).numberOfDimensions() == 3)
        {
            n3(Is[0], Is[1], Is[2]) = vbn(Is[0], Is[1], Is[2], axis3);
        }

        man_system_right_[be.grid](Ig[0], Ig[1], Ig[2]) =
            vbn(Is[0], Is[1], Is[2], axis1) * Phix[be.grid](Is[0], Is[1], Is[2]) +
            vbn(Is[0], Is[1], Is[2], axis2) * Phiy[be.grid](Is[0], Is[1], Is[2]) +
            n3 * Phiz[be.grid](Is[0], Is[1], Is[2]);
    }

    // Apply Neumann condition at the bed

    for (unsigned int surface = 0; surface < boundariesData.impermeable.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData.impermeable[surface];
        const vector<Index> &Is = be.surface_indices;
        const vector<Index> &Ig = be.ghost_indices;
        const MappedGrid &mg = (cg_)[be.grid];
        const RealArray &v = mg.vertex();
        const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

        RealArray n3(Is[0], Is[1], Is[2]);
        n3 = 0.0;

        if ((cg_).numberOfDimensions() == 3)
        {
            n3(Is[0], Is[1], Is[2]) = vbn(Is[0], Is[1], Is[2], axis3);
        }

        man_system_right_[be.grid](Ig[0], Ig[1], Ig[2]) =
            vbn(Is[0], Is[1], Is[2], axis1) * Phix[be.grid](Is[0], Is[1], Is[2]) +
            vbn(Is[0], Is[1], Is[2], axis2) * Phiy[be.grid](Is[0], Is[1], Is[2]) +
            n3 * Phiz[be.grid](Is[0], Is[1], Is[2]);
    }

    // Apply Neumann condition around the wall

    for (unsigned int surface = 0; surface < boundariesData.absorbing.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData.absorbing[surface];
        const vector<Index> &Is = be.surface_indices;
        const vector<Index> &Ig = be.ghost_indices;
        const MappedGrid &mg = (cg_)[be.grid];
        const RealArray &v = mg.vertex();
        const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

        RealArray n3(Is[0], Is[1], Is[2]);
        n3 = 0.0;

        if ((cg_).numberOfDimensions() == 3)
        {
            n3(Is[0], Is[1], Is[2]) = vbn(Is[0], Is[1], Is[2], axis3);
        }

        man_system_right_[be.grid](Ig[0], Ig[1], Ig[2]) =
            vbn(Is[0], Is[1], Is[2], axis1) * Phix[be.grid](Is[0], Is[1], Is[2]) +
            vbn(Is[0], Is[1], Is[2], axis2) * Phiy[be.grid](Is[0], Is[1], Is[2]) +
            n3 * Phiz[be.grid](Is[0], Is[1], Is[2]);
    }

    // Apply Neumann condition at the symmetry plane

    for (unsigned int surface = 0; surface < boundariesData.symmetry.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData.symmetry[surface];
        const vector<Index> &Is = be.surface_indices;
        const vector<Index> &Ig = be.ghost_indices;
        const MappedGrid &mg = (cg_)[be.grid];
        const RealArray &v = mg.vertex();
        const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

        RealArray n3(Is[0], Is[1], Is[2]);
        n3 = 0.0;

        if ((cg_).numberOfDimensions() == 3)
        {
            n3(Is[0], Is[1], Is[2]) = vbn(Is[0], Is[1], Is[2], axis3);
        }

        man_system_right_[be.grid](Ig[0], Ig[1], Ig[2]) =
            vbn(Is[0], Is[1], Is[2], axis1) * Phix[be.grid](Is[0], Is[1], Is[2]) +
            vbn(Is[0], Is[1], Is[2], axis2) * Phiy[be.grid](Is[0], Is[1], Is[2]) +
            n3 * Phiz[be.grid](Is[0], Is[1], Is[2]);
    }

    // Apply Dirichlet condition at the free surface

    for (unsigned int surface = 0; surface < boundariesData.free.size(); surface++)
    {
        const Single_boundary_data &bf = boundariesData.free[surface];
        const vector<Index> &Is = bf.surface_indices;
        const MappedGrid &mg = (cg_)[bf.grid];

        where(mg.mask()(Is[0], Is[1], Is[2]) > 0)
        {
            man_system_right_[bf.grid](Is[0], Is[1], Is[2]) = man_sol_[bf.grid](Is[0], Is[1], Is[2]);
        }
    }
}
