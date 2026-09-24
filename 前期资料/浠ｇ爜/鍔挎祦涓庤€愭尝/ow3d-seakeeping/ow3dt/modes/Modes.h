// This file imports the data objects and member functions related to the
// abstract base class "Mode". The desired type of mode can be
// defined by deriving from this class.
// The simulation data (the shape of Gaussian impulse, time-step etc.) are
// the same for all types of excitations. The member function "getSimulationData"
// in the abstract base class serves to give this information to the outside world.
// All additional data objects and member functions specific to each type of mode
// can be defined during the class derivation. There have been already derived three
// classes: "Resistance" , "Radiation", and "Diffraction". New excitations can be added
// in exactly the same manner.
// The idea to write the Mode base class, is that each hydrodynamic problem
// basically is a specific type of motion which is introduced to the body via the body
// boundary condition.
//
// This base class has a virtual member function "getMotionData", which can have different
// implementations in the derived classes. These motion data are in fact the body boundary
// conditions in each specific type of exciation. So the Diffraction, Resistance and
// Radiation classes have their own implementation of this virtaul function.
//
// In the program, the user creates a pointer to the base class Mode. Then based on the
// type of the mode, the pointer will point to the object of the relevant derived class. Later
// in the program, the call to "getMotionData" becomes in fact a call to the desired implementation.
//
// The base class has also a virtual destructor. This is necessary to make sure that the destructor
// of the derived classes are also called, when a reference or pointer to object is used to call
// derived class methods. If the base class destructor is not virtual, then the destructor of the derived
// class is not getting called.

#ifndef __MODES_H__
#define __MODES_H__

#include "Grid.h"
#include "ComplexArray.h"
#include "gsl/gsl_interp.h"
#include "gsl/gsl_fft_halfcomplex.h"
namespace OW3DSeakeeping
{
  class Modes
  {
  public:
    typedef struct
    {
      int step_count;
      double maximum_frequency;
      double minimum_frequency;
      double frequency_deviation;
      double midpoint_time;
      double sample_time;
      double minimum_velocity;
      double maximum_velocity;
      double time_step;
      double print_time_step;        // Time step for printing and post-processing (Based on user-defined "prat" parameter)
      unsigned int print_step_count; // Number of steps for printing and post-processing (Based on user-defined "prat" parameter)
      double print_time;

    } Simulation;

    typedef struct // this type is used by all derived classes. (resistance, radiation and diffraction problem all need this).
    {
      double time;           // the simulation time
      double displacement;   // the displacement of the body at this time
      double velocity;       // the velocity of the body at this time.
      double elevation;      // the incident wave elevation used for diffraction problem
      double fsbcRamp;       // the coefficient for ramp function just for wave resistance problem in case of DB linearization.(to be applied to KFSBC and DFSBC).
      VRealArrays gradphi0x; // the gradient of the incident wave velocity potential(x)
      VRealArrays gradphi0y; // the gradient of the incident wave velocity potential(y)
      VRealArrays gradphi0z; // the gradient of the incident wave velocity potential(z)

    } Motion;

    Modes(const OW3DSeakeeping::Grid::GridData &); // the constructor, which assigns the values of simulation data. The constructor of the derived class will call this.

    virtual ~Modes(){};

    const Simulation &GetSimulationData() const; // public member function accessible by the derived class.

    virtual const Motion &GetMotionData(int step, int stage) = 0; // this function has different implementations based on the type of mode.

    virtual void StoreMotionData() const = 0; // this function has different implementations based on the type of mode.
    void StoreSimulationData() const;         // to write the simulation data in to "asReadUserInput.dat" file

  protected:
    Simulation _simulation_data; // contains information regarding the simulation (The Gaussian impulse data, time step, duration of simulation and ..)
    string _resultsDirectory;

    vector<double> _rk_c;

  private:
    double CalculateMinimumVelocity_(
        const double &,
        const double &,
        const double &);
  };

  // derive the Wave resistance class

  class Resistance : public Modes
  {
  public:
    Resistance(const OW3DSeakeeping::Grid::GridData &);

    // gets called at each time stage to get the required data for setting the
    // righ hand side (both for neumann and dirichlet BC)

    virtual const Modes::Motion &GetMotionData(int step, int stage);
    virtual void StoreMotionData() const;

  private:
    string veloFileName_; // for the Resistance run, the velocity of the body is stored in this file (as binary)
    string timeFileName_;

    Modes::Motion motions_;
    vector<Modes::Motion> motion_step_;
  };

  // derive the Radiation class

  class Radiation : public Modes
  {
  public:
    Radiation(const OW3DSeakeeping::Grid::GridData &); // will call the base class constructor

    // gets called at each time stage to get the required data for setting the
    // righ hand side (both for neumann and dirichlet BC)

    virtual const Modes::Motion &GetMotionData(int step, int stage);
    virtual void StoreMotionData() const;

  private:
    Modes::Motion motions_;
    string dispFileName_; // for all radiation runs, the displacement of the body is stored in this file (as binary)
    string timeFileName_;
  };

  // derive the Diffraction class

  class Diffraction : public Modes
  {
  public:
    Diffraction(
        const CompositeGrid &,
        const OW3DSeakeeping::Grid::GridData &,
        DIFF_TYPES); // will call the base class constructor

    ~Diffraction(); // the destructor

    // gets called at each time stage to get the required data for setting the
    // righ hand side (both for neumann and dirichlet BC)

    virtual const Modes::Motion &GetMotionData(int step, int stage);

    virtual void StoreMotionData() const;

  private:
    enum SymAsymWhole
    {
      Whole,
      Sym,
      Asym
    };

    const OW3DSeakeeping::Grid::GridData *gridData_;

    const All_boundaries_data *boundariesData_;
    string elevFileName_; // for all Diffraction runs, the elevations of the incident waves are stored in this file (as binary)
    string timeFileName_;
    DIFF_TYPES diff_type_;
    int noes_; // number of exciting surfacesdefined just for convenience !

    int rk_stage_count_;
    vector<double> rk_c_;

    Modes::Motion motions_;

    bool deep_check_;                 // make it true for comparision between deep water analytical integrals and inverse transform
    bool deep_water_;                 // make it on when if the deep water boundary conditions is desired
    ComplexArray deep_alpha_prime_p_; // For definition of these variables please
    ComplexArray deep_I0p_;           // refer to pp 73-75 of Bradley King's PhD thesis :
    ComplexArray deep_I1p_;           // "Time domain analysis of wave exciting forces on ships and bodies", University of Michigan.
    ComplexArray deep_I2p_;           // note that these complex arrays are defined over the body surface, and
    ComplexArray deep_alpha_prime_n_; // will be updated at each stage of the RK time stepping.
    ComplexArray deep_I0n_;           // Moreover we need to define these complex arrays for
    ComplexArray deep_I1n_;           // both positve and negative "z" coordinate, in order to be able
    ComplexArray deep_I2n_;           // to use the grid symmetry planes.
    VRealArrays deep_dphi0xp_;        // Note : these
    VRealArrays deep_dphi0yp_;        // are
    VRealArrays deep_dphi0zp_;        // defined
    VRealArrays deep_dphi0xn_;        // just
    VRealArrays deep_dphi0yn_;        // for
    VRealArrays deep_dphi0zn_;        // verification with
    VRealArrays deep_omegaBarp_;      // deep water analytical
    VRealArrays deep_omegaBarn_;      // diffraction boundary conditions
    VRealArrays deep_dphi0x_;
    VRealArrays deep_dphi0y_;
    VRealArrays deep_dphi0z_;

    double integTol_; // The tolerance for the integrands of the wave veclocities. Above the max frequency the integrand should be zero up to this tolerance.

    VRealArrays X_, Y_, Z_; // needed for defining the gradient of the incident wave's velocity potential over the body.
    double betar_;          // wave heading in radian, defined just for convenience !
    double U_;
    double g_;
    double mwl_; // minimum wave length given by user
    double h_;
    double s_;
    double a_;                      // parameter related to the Fourier transform of the sudo-impulse. a = 8*pi^2*s^2
    double b_;                      // parameter related to the Fourier transform of the sudo-impulse. b = s*sqrt(pi). F[exp(-2 * pi^2 * s^2 * t^2)] = 1/b exp(-omega^2/a)
    int n_;                         // the number of samples from the frequency domain signal (used in ifft)
    double FSK0lim_;                // The limit wave number for the following-seas condition
    double tauc_;                   // The critical tau
    double omegaec_;                // The critical frequency at tauc_
    SymAsymWhole SymOrAsymOrWhole_; // The type of the diffraction problem with regard to the symmetry

    double *timevector_; // the time vector in the inverse transform used to define body boundary condition
    vector<double> K_;   // the wave numbers which appear in the integrands of the continuous inverse transforms
    double multx_;       // defined just
    double multz_;       // for the ease. Thesre are the coefficients that are multiplied by the continuous transform
    double multy_;

    vector<VRealArrays> dphi0dx_; // these are defined to store the boundary conditions (arbitrary depth) for the whole stages of RK time stepping.
    vector<VRealArrays> dphi0dz_;
    vector<VRealArrays> dphi0dy_; // The vector is over the total number of stages, and all must be resized in the constructor.

    void InterpolateDiffractionBCs_(
        double *s_ifftData,
        double *a_ifftData,
        double *timevector,
        int n,
        vector<VRealArrays> &bc,
        int,
        int,
        int,
        int,
        gsl_interp *,
        gsl_interp *,
        gsl_interp_accel *);

    void DeepwaterDiffractionBCs_(double t); // the analytical solution in the deep water case based on King's PhD thesis

    void incidentWave_X_Integrand_(double *, double *, int n, const double &, const double &, const double &, const vector<double> &, void *);
    void incidentWave_Z_Integrand_(double *, double *, int n, const double &, const double &, const double &, const vector<double> &, void *);
    void incidentWave_Y_Integrand_(double *, double *, int n, const double &, const double &, const double &, const vector<double> &, void *);
    void incidentWave_Phi_Integrand_(double *, double *, int n, const double &, const double &, const double &, const vector<double> &, void *);
    void ComputeInverseTransform_(double *data, gsl_fft_halfcomplex_wavetable *hc, gsl_fft_real_workspace *work, int n, double dt, double *);

    Diffraction(const Diffraction &diffraction) : Modes(diffraction) {} // copy constructor   ( copying is illegal! )
    Diffraction &operator=(const Diffraction &) { return *this; }       // assignment operator ( assignment is illegal! )

  }; // end of Diffraction class declaration.

  class GMode : public Modes
  {

  public:
    GMode(const Grid::GridData &gridData);
    virtual const Modes::Motion &GetMotionData(int step, int stage);
    virtual void StoreMotionData() const;

  private:
    Modes::Motion motions_;
    string dispFileName_;
    string timeFileName_;
    VRealArrays X_, Y_, Z_;    // needed for defining the gradient of the incident wave's velocity potential over the body.
    VRealArrays n1_, n2_, n3_; // for generalized normal vector
  };

}

#endif
