// This file imports the data objects and member functions for SecondOrder class. The
// class is meant for handling and post processing the second order results such as wave drift
// forces.

#ifndef __SECOND_ORDER_H__
#define __SECOND_ORDER_H__

#include "FirstOrder.h"
#include "Baseflow.h"

namespace OW3DSeakeeping
{
    class SecondOrder
    {
    public:
        SecondOrder(
            const OW3DSeakeeping::Grid::GridData &gridData,
            CompositeGrid &cg,
            const OW3DSeakeeping::FirstOrder::KsAndOmegas &,
            const vector<ComplexNumbers> &); // Constructor

        ~SecondOrder(); // Destructor

        void ComputeDriftNearField();
        void ComputeDriftFarField_m();
        void ComputeDriftFarFieldDirect_m();
        void ComputeDriftFarField_theta();
        void ComputeDriftSalvesen();
        void ComputeWaveDriftForces();

        void PrintDriftForces() const;

    private:
        const OW3DSeakeeping::Grid::GridData *gridData_;
        const OW3DSeakeeping::Grid::GridData *fineGridData_;

        CompositeGrid *cg_;
        CompositeGrid *fineCg_;

        const All_boundaries_data *boundariesData_;
        const All_boundaries_data *fineBnsData_;

        vector<OW3DSeakeeping::HydrodynamicProblem> radiation_runs_, diffraction_runs_;
        Integrate integrator_;

        RealArray fdC_;                                                                 // fd coefficients for the internal points       (used for line integration)
        vector<RealArray> fdCleft_;                                                     // fd coefficients for the left  boundary points (used for line integration)
        vector<RealArray> fdCright_;                                                    // fd coefficienst for the right boundary points (used for line integration)
        vector<vector<realArray>> phi0_, phi0x_, phi0y_, phi0z_;                        // First loop over radiation runs, second loop over body surfaces
        vector<vector<realArray>> phi0xx_, phi0yy_, phi0zz_, phi0xy_, phi0xz_, phi0yz_; // First loop over radiation runs, second loop over body surfaces

        ComplexArray phi_;       //
        ComplexArray d_phi_dx_;  //
        ComplexArray d_phi_dy_;  //
        ComplexArray d_phi_dz_;  // NOET : All these varibales are assigned by the data read from
        ComplexArray d_phi_dxx_; //        the binary files for each frequecny.
        ComplexArray d_phi_dyy_; //
        ComplexArray d_phi_dzz_; //
        ComplexArray d_phi_dxy_; //
        ComplexArray d_phi_dxz_; //
        ComplexArray d_phi_dyz_; //

        ComplexArray sym_phi_, asm_phi_;
        ComplexArray sym_d_phi_dz_, asm_d_phi_dz_;
        ComplexArray sym_d_phi_dxz_, asm_d_phi_dxz_;
        ComplexArray sym_d_phi_dyz_, asm_d_phi_dyz_;

        ComplexArray d_phi_dn_;    // Note : this derivative is calculated by BBC as closed-form.
        ComplexArray phi_rd_;      // Note : Only radiation  potentials
        ComplexArray phi_sc_;      // Note : Only scattering potentials
        ComplexArray d_phi_dx_rd_; // Note : Only radiation  potentials
        ComplexArray d_phi_dy_rd_; // Note : Only radiation  potentials
        ComplexArray d_phi_dz_rd_; // Note : Only radiation  potentials
        ComplexArray d_phi_dx_sc_; // Note : Only scattering potentials
        ComplexArray d_phi_dy_sc_; // Note : Only scattering potentials
        ComplexArray d_phi_dz_sc_; // Note : Only scattering potentials

        realCompositeGridFunction base_dx_;
        realCompositeGridFunction base_dy_;  // These variables are used to store the base flow velocity
        realCompositeGridFunction base_dz_;  // potentials which have been already produced by RUN and are
        realCompositeGridFunction base_dxx_; // saved in a hdf file. The hdf file is mounted in the class
        realCompositeGridFunction base_dyy_; // constructor, and the variables are assigned accordingly.
        realCompositeGridFunction base_dzz_; //
        realCompositeGridFunction base_dxy_; //
        realCompositeGridFunction base_dxz_;
        realCompositeGridFunction base_dyz_;

        OW3DSeakeeping::Baseflow::Mterms mterms_; // The base-flow mterms from the hdf database file are stored in this variable.

        vector<double> rCenter_; // The coordinate of the point around which the moment integration is carried out.

        vector<realArray> DphiDnOnBody_;

        realCompositeGridFunction KOCHIN_INTEGRAND_REAL_; // REAL PART OF THE KOCHINS FUNCTION INTEGRAL
        realCompositeGridFunction KOCHIN_INTEGRAND_IMAG_; // IMAG PART OF THE KOCHINS FUNCTION INTEGRAL

        double xi1_re_, xi1_im_;       // Surge RAO
        double xi2_re_, xi2_im_;       // Heave  RAO
        double xi3_re_, xi3_im_;       // Sway RAO
        double alpha1_re_, alpha1_im_; // Roll  RAO
        double alpha2_re_, alpha2_im_; // YAW RAO
        double alpha3_re_, alpha3_im_; // Pitch   RAO

        unsigned int numberOFIntegrations_; // is "2" if the grid is symmetric and is "1" otherwise.

        string results_folder_;
        string time_domain_folder_;

        bool bcsExact_;

        vector<ComplexNumbers> RAOs_;
        vector<OW3DSeakeeping::Grid::WLD> wlData_;

        unsigned int NPOTENS_;   // Number of velocity potential data that is read as binary.
        unsigned int FarPots_;   // Number of velocity potential data used for calculation of drift force based on the  FAR-FIELD method.
        unsigned int NTHETA_;    // Number of the theta angels ( between th0 and 2 * Pi), required for the Kochin's function inegration.
        unsigned int OrderLine_; // Desired order for the line integration in the far-field method.
        unsigned int NES_;       // Just for convenience (The number of exciting surfaces)

        const OW3DSeakeeping::FirstOrder::KsAndOmegas allKsAndOmegas_;

        RealArray forces_nearField_; // including force and moments
        RealArray forces_farField_;  //
        RealArray forces_salvesen_;
        unsigned int nDrfNer_; // Number of force directions for the drift force based on the Near-Field.
        unsigned int nDrfFar_; // Number of force directions for the drift force based on the  Far-Field.

        unsigned int flength_; // Number of frequencies
        double betar_;         // Beta radian
        double rho_;
        double g_;
        double h_;
        double U_;
        double sin_betar_, cos_betar_;
        vector<vector<double>> gwlc_;
        string body_pot_file_;
        string body_scat_pot_file_;
        string body_radi_pot_file_;
        string waterline_elev_file_;
        ifstream wline_fin_;
        ifstream body_fin_;
        ifstream body_radi_fin_;
        ifstream body_scat_fin_;

        void ComputePotentialsDerivatives_(unsigned int f);
        double ComputeWaterlineTrapz_(vector<vector<double>> gwlc);
        void ComputeKochinFunction_(int symSign, double VertC, double C0, double C1, double *H);

        void ComputeDphiDnOnBody_(
            const double &omegae,
            const double &omegao,
            const double &K,
            const int &sign); // To calculate the closed-form dphi_dn where phi = phi (scattering) + Sigma [ rao * phi(radiation) ]. Can be used for the far-field calculations.
    };
}
#endif