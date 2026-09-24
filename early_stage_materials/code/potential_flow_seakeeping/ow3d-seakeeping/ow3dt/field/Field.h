// This file imports the data object and member function for the Field class.  There needs to be
// just one instance of this class for all excitations. An instance of this class contains among other
// data objects the velocity potential and its derivatives. For each excitation the public member
// function "initialise(...)" must be called in order to initialise the data objects for the run. This
// function also define the system matrix according to the specified excitation.
//
// The field is solved by the FieldSolver class at each stage of RK time stepping. It is necessary
// to update the right hand side before solving the system.
// This class is meant for handling the solution of continuity equation. Through the member
// functions of this class the desired field solution like velocity potential, pressure or
// velocity on the desired locations (at the body surface, at the far-field control surface)
// can be extracted. The idea is that, since we know the solution at each specific time, we are
// able to extract and derive the desired values and store them for the final postprocessing.

#ifndef __FIELD_H__
#define __FIELD_H__

#include "Baseflow.h"
#include "Modes.h"

namespace OW3DSeakeeping
{
    class Field
    {
    public:
        typedef struct
        {
            double phiu_n;                // integral of the unsteady potential multiplied by normal on the surface
            double d_phiu_dx_n;           // integral of dphiu/dx multiplied by normal on the surface
            double d_phib_dx_n;           // integral of dphib/dx multiplied by normal on the surface
            double d_phiu_dxx_n;          // integral of d^2phiu/dx^2 multiplied by normal on the surface
            double grad_phiu_grad_phib_n; // integral of grad(phiu) * grad(phib) multiplied by the normal on the surface
            double grad_phib_grad_phib_n; // integral of grad(phib) * grad(phib) multiplied by the normal on the surface
            double grad_phiu_grad_phiu_n; // integral of grad(phiu) * grad(phiu) multiplied by the normal on the surface

        } integrals_n; // this type is defined for storing the integral of the potentials as binary format (n here means multiplied by normal)

        Field(
            const OW3DSeakeeping::Grid::GridData &,
            const OW3DSeakeeping::Baseflow::baseFlowData *,
            CompositeGridOperators &); // constructor

        ~Field();

        typedef struct
        {
            realCompositeGridFunction phi;
            realCompositeGridFunction phix, phiy, phiz;
            realCompositeGridFunction phixx, phiyy, phizz;
            realCompositeGridFunction phixy, phixz, phiyz;

        } fieldDervs;

        void Initialise(HydrodynamicProblem, CompositeGridOperators &); // must be called for each excitation.

        realCompositeGridFunction &GetSystemMatrix();
        realCompositeGridFunction &GetSystemRight();

        void ApplyNeumannDirichletConditions(
            const realCompositeGridFunction &,
            const OW3DSeakeeping::Baseflow::baseFlowData *,
            const Modes::Motion &); // this function is called to update right hand side at each stage of time stepping

        realCompositeGridFunction &GetPotential(); // a reference to the updated solution (for use in the FreeSurface class)

        void StoreBodyIntegrals();
        // very important note : after calling this function the "potential_"
        // of the body surface. Instead the potential and its gradient can be obtained
        // through members like "phiu_on_body_" and so on for the derivatives.

        void StoreBodyPotentials(); // call this to store field data required for the drift force

    private:
        CompositeGrid *cg_;
        realCompositeGridFunction potential_;     // at each stage of Runge-Kutta time stepping, gets updated by the solver. It is the field solution.
        realCompositeGridFunction system_matrix_; // each excitation has its own system matrix (should be supplied to the solver object outside)
        realCompositeGridFunction system_right_;  // at each stage of Runge-Kutta time stepping, gets updated by a public member function of this class.

        fieldBaseDerivative baseFlow_fieldDerivative_; // the derivative of the base flow over the whole domain

        realCompositeGridFunction d_phiu_dx_;           // needed for integration
        realCompositeGridFunction d_phib_dx_;           // needed for integration
        realCompositeGridFunction d_phiu_dxx_;          // needed for integration
        realCompositeGridFunction grad_phiu_grad_phib_; // needed for integration
        realCompositeGridFunction grad_phiu_grad_phiu_; // needed for integration
        realCompositeGridFunction grad_phib_grad_phib_; // needed for integration

        vector<RealArray> phiu_on_body_;      // each RealArray has the same dimension as the corresponding exciting surface.
        vector<RealArray> d_phiu_dx_on_body_; // each RealArray has the same dimension as the corresponding exciting surface.
        vector<RealArray> d_phiu_dy_on_body_;
        vector<RealArray> d_phiu_dz_on_body_;

        vector<RealArray> d_phiu_dxx_on_body_;
        vector<RealArray> d_phiu_dxy_on_body_;
        vector<RealArray> d_phiu_dxz_on_body_;
        vector<RealArray> d_phiu_dyy_on_body_;
        vector<RealArray> d_phiu_dyz_on_body_;
        vector<RealArray> d_phiu_dzz_on_body_;

        vector<RealArray> d_phib_dx_on_body_;           // each RealArray has the same dimension as the corresponding exciting surface.
        vector<RealArray> grad_phiu_grad_phib_on_body_; // each RealArray has the same dimension as the corresponding exciting surface.
        vector<RealArray> grad_phiu_grad_phiu_on_body_; // each RealArray has the same dimension as the corresponding exciting surface.
        vector<RealArray> grad_phib_grad_phib_on_body_; // each RealArray has the same dimension as the corresponding exciting surface. (vector over the size of exciting surface)

        const OW3DSeakeeping::Baseflow::baseFlowData *baseFlowData_;

        HydrodynamicProblem run_; // is assigned when the public member function "initialise(...)" gets called.
                                  // Computing the double-body m -terms using a B-spline based panel method (IWWWFB11)

        RealCompositeGridFunction PhiN_; // The body boundary condition used for new surface gradient scheme.

        Integrate integrator_; // for integration on the body

        const All_boundaries_data *boundariesData_;
        const OW3DSeakeeping::Grid::GridData *gridData_;
        string integralsFileName_;
        string potentialsFileName_;
        string resultsDirectory_;

        void BuildSystemMatrix_(CompositeGridOperators &);

        void ExtractBodyPotentials_();

        void MultiplyByNormals_(const MODE_NAMES &response, unsigned int gmode_resp_index); // multiply field data by normal vector of the desired surface.

        Field(const Field &) {}                           // copy constructor ( copying is illegal!)
        Field &operator=(const Field &) { return *this; } // assignment operator ( assignment is illegal!)
    };
}
#endif