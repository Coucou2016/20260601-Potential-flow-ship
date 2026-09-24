// This file implements the FieldSolver class.

#include "Solver.h"
#include "OW3DConstants.h"
#include <iomanip>

OW3DSeakeeping::Solver::Solver(CompositeGrid &cg)
{
  if (UserInput.solver_type == SOLVER_TYPES::DI) // direct
  {
    solver_.updateToMatchGrid(cg);
    solver_.set(OgesParameters::THEsolverType, OgesParameters::yale);
    solver_.set(OgesParameters::THEkeepSparseMatrix, true);
  }
  else if (UserInput.solver_type == SOLVER_TYPES::IT) // iterative
  {
    solver_.updateToMatchGrid(cg);
    solver_.set(OgesParameters::THEkeepSparseMatrix, true);
    double tol = 1.e-8;
    int iluLevels = 2;
    solver_.set(OgesParameters::THEsolverType, OgesParameters::PETSc);
    solver_.set(OgesParameters::THEpreconditioner, OgesParameters::incompleteLUPreconditioner);
    // solver_.set(OgesParameters::THEpreconditioner,OgesParameters::multigridPreconditioner);
    // solver_.set(OgesParameters::THEsolverMethod,OgesParameters::biConjugateGradientStabilized);
    solver_.set(OgesParameters::THEsolverMethod, OgesParameters::generalizedMinimalResidual);
    solver_.set(OgesParameters::THErelativeTolerance, max(tol, REAL_EPSILON * 10.));
    solver_.set(OgesParameters::THEmaximumNumberOfIterations, 10000);
    solver_.parameters.setPetscOption("-pc_factor_shift_type", "inblocks");

    if (iluLevels >= 0)
      solver_.set(OgesParameters::THEnumberOfIncompleteLULevels, iluLevels);
  }
  else // multigrid
  {
    mgSolver_->updateToMatchGrid(cg);
    int maximumNumberOfExtraLevels = 10;
    int maximumNumberOfIterations = 10;
    Ogmg::debug = 1;
    OgmgParameters &par = mgSolver_->parameters;
    par.set(OgmgParameters::THEmaximumNumberOfExtraLevels, maximumNumberOfExtraLevels);
    par.set(OgmgParameters::THEmaximumNumberOfIterations, maximumNumberOfIterations);
    par.setSmootherType(OgmgParameters::redBlack);
    par.setResidualTolerance(1.e-10);
    par.setErrorTolerance(1.e-7);
    par.updateToMatchGrid(cg, max(1, maximumNumberOfExtraLevels));

    int numBcData = 3;
    bc_.resize(2, 3, cg.numberOfComponentGrids());
    bc_ = 0;
    bcData_.resize(numBcData, 2, 3, cg.numberOfComponentGrids());
    bcData_ = 0.;

    mgSolver_->parameters.updateToMatchGrid(cg);
    mgSolver_->updateToMatchGrid(cg);

    for (int grid = 0; grid < cg.numberOfComponentGrids(); grid++)
    {
      for (int axis = 0; axis < cg.numberOfDimensions(); axis++)
      {
        for (int side = 0; side <= 1; side++)
        {
          if (cg[grid].boundaryCondition(side, axis) == 2 or
              cg[grid].boundaryCondition(side, axis) == 3 or
              cg[grid].boundaryCondition(side, axis) == 4)
          {
            bc_(side, axis, grid) = OgmgParameters::neumann;
          }
          if (cg[grid].boundaryCondition(side, axis) == 1)
          {
            bc_(side, axis, grid) = OgmgParameters::dirichlet;
          }
        }
      }
    }
  } // end of multigrid block

} // end of constructor

OW3DSeakeeping::Solver::~Solver()
{
}

void OW3DSeakeeping::Solver::SupplySystemMatrix(realCompositeGridFunction &system_matrix)
{
  if (UserInput.solver_type != SOLVER_TYPES::MG)
  {
    solver_.setCoefficientArray(system_matrix);
  }
  else
  {
    mgSolver_->setCoefficientArray(system_matrix, bc_, bcData_);
  }

} // end of supplySystemMatrix public member function

void OW3DSeakeeping::Solver::CalculateSolution(
    realCompositeGridFunction &u,
    realCompositeGridFunction &rhs)
{
  if (UserInput.solver_type != SOLVER_TYPES::MG)
  {
    solver_.solve(u, rhs);
  }
  else
  {
    mgSolver_->solve(u, rhs);
  }
}

void OW3DSeakeeping::Solver::OutputMatrixCoeff(const aString &fileName)
{
  solver_.writeMatrixToFile(fileName);
}

void OW3DSeakeeping::Solver::OutputMatrixIndex(
    CompositeGrid &cg,
    const aString &fileName)
{
  int neq = 0;
  for (int grid = 0; grid < cg.numberOfComponentGrids(); grid++)
  {
    Index I1, I2, I3;
    getIndex(cg[grid].dimension(), I1, I2, I3);
    neq += I1.getLength() * I2.getLength() * I3.getLength();
  }

  ofstream fout(fileName);
  unsigned int bw = 10;

  int ne, i1e, i2e, i3e, gride;
  for (int e = 1; e <= neq; e++)
  {
    solver_.equationToIndex(e, ne, i1e, i2e, i3e, gride);

    fout << setw(bw) << "eq. =: " << e << '\n';
    fout << setw(bw) << "grid=: " << gride
         << setw(bw) << "i =: " << i1e
         << setw(bw) << "j =: " << i2e
         << setw(bw) << "k =: " << i3e << '\n';

    // fout << setw(bw) << "eq. =: "    << e << '\n';
    // fout << setw(bw) << "grid=: "    << gride
    // 	   << setw(bw) << "x =: " << cg[gride].vertex()(i1e, i2e, i3e, axis1)
    // 	   << setw(bw) << "y =: " << cg[gride].vertex()(i1e, i2e, i3e, axis2)
    // 	   << setw(bw) << "z =: " << cg[gride].vertex()(i1e, i2e, i3e, axis3) <<'\n';

    fout << " ---------------------- " << '\n';
  }
}

void OW3DSeakeeping::Solver::GetEquationIndex(int &e, int &i, int &j, int &k, int &grid)
{
  int comp;
  solver_.equationToIndex(e, comp, i, j, k, grid);
}