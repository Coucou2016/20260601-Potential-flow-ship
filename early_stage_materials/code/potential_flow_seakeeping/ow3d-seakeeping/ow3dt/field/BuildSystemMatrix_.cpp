#include "CompositeGridOperators.h"
#include "Field.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Field::BuildSystemMatrix_(CompositeGridOperators &operators)
{
    int nod = gridData_->nod;
    int order_space = gridData_->order_space;
    int stencil_points = floor(pow(order_space + 1, nod) + 1.5); // add 1 for interpolation equations
    int ghost_lines = order_space / 2;
    Range all;

    system_matrix_.updateToMatchGrid(*cg_, stencil_points, all, all, all);
    system_matrix_ = 0.0;
    system_matrix_.setIsACoefficientMatrix(true, stencil_points, ghost_lines);
    system_matrix_.setOperators(operators); // apply operator

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

    system_matrix_ = operators.laplacianCoefficients(); // populate system matrix with finite-difference coefficients.

    system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::dirichlet, gridData_->boundaryTypes.free);
    system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, gridData_->boundaryTypes.free);
    system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_->boundaryTypes.impermeable);
    system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_->boundaryTypes.exciting);
    system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_->boundaryTypes.absorbing);

    if (nod == 3 and gridData_->halfSymmetry)
    {
        if (run_.mat_type == MAT_TYPES::SYMMAT)
            system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, gridData_->boundaryTypes.symmetry);

        if (run_.mat_type == MAT_TYPES::ASMMAT)
        {
            system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::dirichlet, gridData_->boundaryTypes.symmetry);
            system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, gridData_->boundaryTypes.symmetry);
        }
    }

    if (order_space == 4)
    {
        system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, BCTypes::allBoundaries, parameters);
    }

    system_matrix_.finishBoundaryConditions();
}