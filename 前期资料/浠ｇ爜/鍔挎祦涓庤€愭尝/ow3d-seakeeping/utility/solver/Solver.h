// This file imports the data object and member functions for the FiledSolver class. There is needed just
// one object of this class to solve the Laplacian for all steady and unsteady probloems.
// It is necessary to provide the solver object with the desired system matrix and right hand side.
// This class is allowed to update the private members (potential) of the Baseflow and Field classes.

#include "Ogmg.h"
#include "Oges.h"

#ifndef __FIELD_SOLVER_H__
#define __FIELD_SOLVER_H__

namespace OW3DSeakeeping
{
  class Solver
  {

  public:
    Solver(CompositeGrid &); // constructor

    ~Solver(); // destructor

    void SupplySystemMatrix(realCompositeGridFunction &); // to solve for each problem, first provide the corresponsding system matrix

    void CalculateSolution(
        realCompositeGridFunction &,
        realCompositeGridFunction &); // the function can be called at each time to solve the continuity equation.

    void OutputMatrixCoeff(const aString &fileName);
    void OutputMatrixIndex(CompositeGrid &, const aString &fileName);
    void GetEquationIndex(int &e, int &i, int &j, int &k, int &grid);

  private:
    Oges solver_;
    Ogmg *mgSolver_;
    IntegerArray bc_;
    RealArray bcData_;
  };

}
#endif
