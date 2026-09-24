// This file imports the data objects and member functions for FirstOrder class. The
// class is meant for handling and post processing the first order results such as added mass
// damping, RAO, etc.

#ifndef __FIRST_ORDER_H__
#define __FIRST_ORDER_H__

#include "Grid.h"
#include "Modes.h"
#include <tuple>

namespace OW3DSeakeeping
{
  class FirstOrder
  {
  public:
    typedef struct
    {
      RealArray phiu_n;                // integral of the unsteady potential multiplied by normal on the surface
      RealArray d_phiu_dx_n;           // integral of dphiu/dx multiplied by normal on the surface
      RealArray d_phib_dx_n;           // integral of dphib/dx multiplied by normal on the surface
      RealArray d_phiu_dxx_n;          // integral of d^2phiu/dx^2 multiplied by normal on the surface
      RealArray grad_phiu_grad_phib_n; // integral of grad(phiu)*grad(phib) multiplied by normal on the surface
      RealArray grad_phiu_grad_phiu_n; // integral of grad(phiu)*grad(phiu) multiplied by normal on the surface
      RealArray grad_phib_grad_phib_n; // integral of grad(phib)*grad(phib) multiplied by normal on the surface

    } Bernoulli;

    // Note : This data type is for the force terms in the Bernoulli Eq. and
    // will be used for calculation of the first order force on the body.
    // All are RealArray(number_of_responses,number_of_time_steps)

    typedef struct
    {
      vector<double> k01;     // -----------------------------------
      vector<double> k02;     // NOTE : This class assigns
      vector<double> k03;     //        values to a variable
      vector<double> omega01; //        of this type. Only
      vector<double> omega02; //        in the follwoing-seas
      vector<double> omega03; //        condition, these parametres
      double FSK0lim;         //        may have a valid value.
      double FSOmegaec;       //
      int FSLimIndex;         // -----------------------------------

      vector<double> ko;     // These are justified to have values only for the diffraction
      vector<double> omegao; // problems which are not following-seas cases.

      vector<double> omegae;    // These two variables are always justified to assume
      vector<double> omegaeAll; // Concatenated encounter frequencies in the case of following seas
      RealArray omegaeArray;    // values. They are in fact frequency space used for fft.

      vector<double> koDeep; // This wave number is valid only in the pure deep water case, i.e ko = omega^2/g.

      unsigned int out_start_index;

    } KsAndOmegas;

    FirstOrder(
        const OW3DSeakeeping::Grid::GridData &,
        const Modes::Simulation &,
        CompositeGrid &);

    ~FirstOrder();

    void BuildMotionData();                // to get the data for the motion of the body including velocity, displacement and wave elevation.
    void BuildTransformData();             // the data that is used for the Fourier transformation of the time-domain solutions.
    void BuildFrequenciesAndWaveNumbers(); // to assign encounter and absolute frequencies

    void ComputeBodySurfaceForces();         // to calculate the first-order forces on the body in time domain.
    void ComputeHydrodynamicCoefficients();  // to calculate the added mass and damping
    void ComputeWaveExcitationForces();      // to calculate the complex phasors of the wave excitation forces
    void ComputeResponseAmplitudeOperator(); // to calculate the RAO's
    void ComputeGModesDisplacements();       // To compute the sectional displacement in case of generalized modes

    void TransformVelocityPotentials();
    void TransformPotentialAndDerivatives(); // to be called in the case of wave drift calculation
    void TransformWaterlineElevations();     // to be called in the case of wave drift calculation

    void PrintFrequencyDomainResults();
    void PrintTimedomainResults() const;

    const KsAndOmegas &GetAllKsAndOmegas();
    const vector<ComplexNumbers> &GetResponseAmplitudeOperators();

  private:
    // data objects

    RealArray time_;         // the simulation time vector
    RealArray displacement_; // the displacement of the body        (non-zero just for radiation problems)
    RealArray elevation_;    // the elevation of the incident waves (non-zero just for diffraction problem)
    RealArray velocity_;     // the velocity  of the body           (non-zero just for resistance problem)

    vector<OW3DSeakeeping::HydrodynamicProblem> allRuns_;

    vector<OW3DSeakeeping::HydrodynamicProblem> resistance_runs_;
    vector<RealArray> resistanceBodyForces_;

    vector<OW3DSeakeeping::HydrodynamicProblem> radiation_runs_;
    vector<RealArray> radiationBodyForces_; // vector over the size of the radiation runs, The RealArray(number of responses for this run,number of time steps)

    vector<OW3DSeakeeping::HydrodynamicProblem> gmodes_runs_;
    vector<RealArray> gmodesBodyForces_; // vector over the size of the radiation runs, The RealArray(number of responses for this run,number of time steps)

    vector<OW3DSeakeeping::HydrodynamicProblem> diffraction_runs_;
    vector<RealArray> diffractionBodyForces_; // vector over the size of the diffraction runs

    vector<RealArray> fitBodyForces_; // The asymptotic force fitting is perfomed on these forces.

    vector<RealArray> addedMass_;        // vector over the size of the radiation runs. RealArray(number of responses,number of desired frequencies)
    vector<RealArray> damping_;          // vector over the size of the radiation runs. RealArray(number of responses,number of desired frequencies)
    vector<RealArray> gmodes_addedMass_; // vector over the size of the gmodes. RealArray(number of responses,number of desired frequencies)
    vector<RealArray> gmodes_damping_;   // vector over the size of the gmodes. RealArray(number of responses,number of desired frequencies)

    ComplexNumbers freq_pseudo_disp_;
    ComplexNumbers freq_pseudo_elev_;

    double tau_;
    const OW3DSeakeeping::Grid::GridData *gridData_;
    const All_boundaries_data *boundariesData_;
    CompositeGrid *cg_;
    Integrate integrator_;
    vector<OW3DSeakeeping::Grid::WLD> wlData_;

    RealArray omegaeArray_;    // The encounter frequencies in a RealArray (Just for convenience in calculations)
    vector<double> omegae_;    // The encounter frequencies.
    vector<double> omegaeAll_; // The encounter frequencies, (Concatenated vector for the following-seas - USE ONLY FOR THE DIFFRACTION PROBLMES).
    vector<double> omegao_;    // The corresponding absolute frequencies.  For the following-seas cases, this containes all three omega01, omega02 and omega03 (with no duplication)
    vector<double> ko_;        // Wave numbers over the desired absolute frequency range. For the following-seas cases, this containes all three k01, k02 and k03 (with no duplication)
    vector<double> koDeep_;    // This wave number is valid only in the pure deep water case, i.e ko = omega^2/g.
    vector<double> k01_;       // The wave numbers related to omega01 for the following-seas cases
    vector<double> k02_;       // The wave numbers related to omega02 for the following-seas cases
    vector<double> k03_;       // The wave numbers related to omega03 for the following-seas cases
    vector<double> omega01_;   // The first  wave frequency in the following-seas condition
    vector<double> omega02_;   // The second wave frequency in the following-seas condition
    vector<double> omega03_;   // The third  wave frequency in the follwoing-seas condition
    double FSK0lim_;           // The limit wave number for the following-seas cases
    double FSOmegaec_;         // The encounter frequency at FSK0lim_, for the following-seas cases.
    unsigned int FSLimIndex_;  // The index of FSOmegaec_ in the vector of encounter frequency

    KsAndOmegas allKsAndOmegas_;

    string time_domain_folder_;
    string results_folder_;
    unsigned int gx_wu_bcs_tag_;

    string str_; // used just formatting in the log file
    int w_;      // used just formatting in the log file

    Modes::Simulation simulationData_; // simulation data is the same for all runs.

    unsigned int numberOfFittingCoefficients_; // number of least square model coefficients, ( a1*sin(wc*t) + a2*cos(wc*t) ) or 1/t*( a1*sin(wc*t) + a2*cos(wc*t) )
    Transform transformData_;                  // those transform data that are the same for all runs.
    int paddingMultiple_;                      // multiple of the original length of the signal that is padded either with zero or with the asymptotic values.
    bool transformSupplied_;                   // to make sure that the transform data has been provided.
    bool motionSupplied_;                      // to make sure that the motion data has been provided.
    bool forceCalc_;                           // to make sure that the forces on the body have been calculated.
    bool hydroCalc_;                           // to make sure that the hydrodynamic coefficiensts have been calculated.
    bool raoCalc_;                             // to make sure that the RAOs have been calculated.
    bool exciteCalc_;                          // to make sure that the wave excitation forces have been calculated.
    unsigned int npots_;                       // phi,phix,phiy,phiz,phixx,phixy,phixz,phiyy,phiyz,phizz (number of potentials data = 10)

    vector<ComplexNumbers> FroudeKrylov_;     // vector over the size of the responses.
    vector<ComplexNumbers> scattering_force_; // these are frequency domain trerms
    vector<ComplexNumbers> excitation_force_; // appearing in the first order force
    vector<ComplexNumbers> RAO_;              // response amplitude operator, vector over the size of the force vector
    vector<double> GMDISP_;                   // Vertical Displacement along the length of the body for generalized mode
    vector<ComplexNumbers> d_phi0_dx_;        // integral
    vector<ComplexNumbers> d_phib_phi0_dx_;   // these are required to calculate grad(phi0) . grad(phib) in frequency domain.
    vector<ComplexNumbers> d_phib_phi0_dy_;   // The derivatives are multiplied during the integration over the body surface
    vector<ComplexNumbers> d_phib_phi0_dz_;   // for calculation of wave exciting force in the frequency domain.

    vector<RealArray> d_phib_dx_; // the gradient of the base
    vector<RealArray> d_phib_dy_; // flow over the body surface
    vector<RealArray> d_phib_dz_; // vector over the size of exciting surface

    unsigned int noes_; // the total number of exciting surfaces (defined just for convenience)
    unsigned int steps_;

    vector<vector<vector<double>>> ls_fit_coeffs_rad_;
    vector<vector<vector<double>>> ls_fit_coeffs_scat_;
    vector<vector<vector<double>>> ls_fit_coeffs_res_;
    vector<vector<vector<double>>> ls_fit_coeffs_gmod_;

    int p_one_run_shift_;  // these are used for linear indexing
    int p_one_step_shift_; // in the binary file for potentials
    int w_one_run_shift_;  // these are used for linear indexing
    int w_one_step_shift_; // in the binary file for water lines

    double betar_; // beta radian
    double rho_;
    double g_;
    double h_;
    double U_;
    double mwl_;

    realArray speed_hydrostatics_;

    // member functions

    void Fft_(const RealArray &, int, ComplexNumbers &, const Transform &, const double &, vector<double>, string = "");

    void ComputeFrequencyDomainIntegrals_(
        void (*pf)(
            vector<RealArray> &,
            vector<RealArray> &,
            vector<RealArray> &,
            vector<RealArray> &,
            const RealArray &,
            const RealArray &,
            const RealArray &,
            void *),
        vector<ComplexNumbers> &,
        const vector<RealArray> & = vector<RealArray>(),
        string = "sym");

    void ComputeForceAnalyticalTransform_(ComplexNumbers &analyticalTransform, unsigned int runIndex, unsigned int respIndex, vector<vector<vector<double>>> ls_fit_coeffs);

    void ComputePotentialsAsymptoticCoefficients_(const vector<double> &, vector<double>);

    void ComputePotentialsAnalyticalTransform_(double *, double *, double *);

    void ComputeAsymptoticCoefficients_();
    void PrintTimedomainAsymptoticForces_() const;
    void PrintPseudoImpulses_() const;
    void AllocateFitcofsMemeories_(vector<vector<vector<double>>> &, unsigned int ncofts, unsigned int runsize);
    void ExtendFollowingSeasHydros_(RealArray &a, RealArray &b);

    FirstOrder(const FirstOrder &) {}                           // Copy constructor    ( copying is illegal! )
    FirstOrder &operator=(const FirstOrder &) { return *this; } // Assignment operator ( assignment is illegal! )
  };
}
#endif