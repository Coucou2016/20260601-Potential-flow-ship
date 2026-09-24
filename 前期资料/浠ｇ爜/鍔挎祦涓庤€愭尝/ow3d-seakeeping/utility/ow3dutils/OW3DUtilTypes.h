#ifndef __PUBLIC__TYPES__
#define __PUBLIC__TYPES__

#include "CompositeGridFunction.h"
#include <vector>
#include "gsl/gsl_matrix.h"
#include "Overture.h"
#include "InterpolatePointsOnAGrid.h"

// note: some typedefs that basically belong to the public section of
// the classes are instead included here, they are needed for the
// declaration of some of the utility functions.

namespace OW3DSeakeeping
{
  enum INPUT_LINES
  {
    HEADLINE,
    NAMELINE,
    SPEDLINE,
    BASELINE,
    IDIFLINE,
    IRADLINE,
    IRESLINE,
    MODELINE,
    DRIFLINE,
    COURLINE,
    TIMELINE,
    BETALINE,
    GRIDLINE,
    GDIMLINE,
    SYMXLINE,
    ROTCLINE,
    COGRLINE,
    GRAVLINE,
    ULENLINE,
    SOLVLINE,
    FFTZLINE,
    ORATLINE
  };

  enum POTENTIAL_TYPES
  {
    PHI,
    PHIX,
    PHIY,
    PHIZ,
    PHIXX,
    PHIYY,
    PHIZZ,
    PHIXY,
    PHIXZ,
    PHIYZ
  };

  enum BASE_FLOW_TYPES
  {
    ZS, // zero-speed
    NK, // neumann-kelvin
    DB  // double body
  };

  enum GMODES_HYDROSTATICS
  {
    NE, // Newman (Without the gravitational part)
    NG, // Newman (With the gravitational part)
    MA, // Malenica ;
    WA  // Keep same as WAMIT based on the barge case for the symmetric ships
  };

  enum GMODE_TYPES
  {
    CUSTOM,
    TIMOSHENKO_STRUC, // only consider shape function of Timoshenko beam
    TIMOSHENKO_STRHY, // consider shape function and shear effects due to second-order hydrodynamic force
    EULERBERNOULLI
  };

  enum SOLVER_TYPES
  {
    DI, // direct
    IT, // itterative
    MG  // multigrid
  };

  enum BASE_FLOW_TAGS
  {
    PHIBX,
    PHIBY,
    PHIBZ,
    PHIBXX,
    PHIBYY,
    PHIBZZ,
    PHIBXY,
    PHIBXZ,
    PHIBYZ,
    M1,
    M2,
    M3,
    M4,
    M5,
    M6,
    MF
  };

  enum MODE_NAMES
  {
    RESISTANCE,
    SURGE,
    HEAVE,
    SWAY,
    ROLL,
    YAW,
    PITCH,
    DIFFRACTION,
    GMODE
  };

  enum DIFF_TYPES
  {
    FULL,
    HEAD,
    SYM,
    ASM,
    OM1,
    OM2,
    OM3,
    OM1_SYM,
    OM2_SYM,
    OM3_SYM,
    OM1_ASM,
    OM2_ASM,
    OM3_ASM,
    OM1_HLF,
    OM2_HLF,
    OM3_HLF
  };

  enum MAT_TYPES
  {
    SYMMAT,
    ASMMAT,
    WHLMAT
  };

  enum UPWIND_STENCIL_TYPES
  {
    NEUTRAL,
    CENTRAL,
    DECREM,
    INCREM,
  };

  typedef struct
  {
    MODE_NAMES mode;                // each simulation is for this excitation
    MAT_TYPES mat_type;             // "s" = symmetric "a" = anti-symmetric "w" = whole grid
    unsigned int gmode_counter = 0; // mode counter (used only for generalized mode)
    DIFF_TYPES diff_type;           // only for diffraction problems

  } HydrodynamicProblem;

  typedef struct
  {
    vector<Range> ROD; // Ranges including only discretisation point. (Interpolation points are not included)
    vector<Range> RNH; // Ranges excluding only hole points. (Interpolation points are included)
    vector<Range> ROH; // Ranges only holes
  } DiscRanges;

  typedef struct
  {
    RealArray E;
    RealArray F;
    RealArray G;
    RealArray H;
    RealArray n1_OV; // Overture normal vectors
    RealArray n2_OV; // Overture normal vectors
    RealArray n3_OV; // Overture normal vectors
    RealArray n1;    // FD normal vectors
    RealArray n2;    // FD normal vectors
    RealArray n3;    // FD normal vectors
    RealArray X;
    RealArray Y;
    RealArray Z;
    RealArray Xu;
    RealArray Yu;
    RealArray Zu;
    RealArray Xv;
    RealArray Yv;
    RealArray Zv;
    RealArray C4_u_nm, C4_v_nm, C4_u_dr, C4_v_dr;
    RealArray C2_u_nm, C2_v_nm, C2_u_dr, C2_v_dr;

  } FundamentalForms;

  typedef struct
  {
    double x;
    double z;

  } Coordinate; // this type is used for defining the body or the wall coordinates (sponge layer)

  typedef struct
  {
    size_t size;
    double *y;
    double *sigma;
    double omegac;
    size_t p;
    double *x_init;
    double dt;
    double tm;
    double n;

  } least_square_data;

  typedef struct
  {
    unsigned int original_signal_length;
    unsigned int number_of_fitting_coefficients; // number of least square model coefficients, ( a1*sin(wc*t) + a2*cos(wc*t) ) or 1/t*( a1*sin(wc*t) + a2*cos(wc*t) )
    double omegac;                               // critical frequency (omegac = tau*g/U), tau = 1/4.
    unsigned int zero_padding_multiple;          // multiple of original length of the time domain signals.
    unsigned int size_of_fft;
    unsigned int fitting_start_index;
    unsigned int fitting_length;  // the partial length of the original signal used for fitting
    double fitting_fraction;      // the fraction of total time of the force signal
    double fitting_start_time;    // the time when the least square fitting starts.
    double analytical_start_time; // the time when analytical transform starts.

  } Transform; // the Fourier transform data that is the same for all runs.

  typedef struct
  {
    double g;
    double depth;   // water depth
    double omega;   // can be encounter or absolute frequency
    double beta;    // wave heading
    double U;       // forward speed
    double FSK0lim; // The limit wave number in the following-seas condition.

  } dispersion_params;

  typedef struct
  {
    realCompositeGridFunction d_phib_dx; // defined over the whole grid (needed by Filed to calculate first order force integral
    realCompositeGridFunction d_phib_dy; // defined over the whole grid (needed by Filed to calculate first order force integral
    realCompositeGridFunction d_phib_dz; // defined over the whole grid (needed by Filed to calculate first order force integral
    realCompositeGridFunction d_phib_dxx;
    realCompositeGridFunction d_phib_dxy;
    realCompositeGridFunction d_phib_dxz;
    realCompositeGridFunction d_phib_dyy;
    realCompositeGridFunction d_phib_dyz;
    realCompositeGridFunction d_phib_dzz;

  } fieldBaseDerivative;

  typedef struct
  {
    vector<realArray> dx;
    vector<realArray> dy;
    vector<realArray> dz;
    vector<realArray> dxx;
    vector<realArray> dyy;
    vector<realArray> dzz;
    vector<realArray> dyz;
    vector<realArray> dxz;
    vector<realArray> dxy;

  } potentialDerivative; // can be defined on any desired surface (used for base flow derivatives)

  typedef struct
  {
    RealArray dx;
    RealArray dy;
    RealArray dz;
    RealArray dxx;
    RealArray dyy;
    RealArray dzz;
    RealArray dyz;
    RealArray dxz;
    RealArray dxy;
  } SideDervs; // Derivatives on one side of a mapped grids

  typedef struct
  {
    realCompositeGridFunction potential;
    potentialDerivative surface_derivative;
    potentialDerivative body_derivative;
    fieldBaseDerivative field_derivative;

  } analyticalData; // used in the case the body is primitive and we need to output analytical base flow solution for verification purpose.

  typedef struct
  {
    int grid;
    int axis;
    int side;
    vector<Index> surface_indices; // surface boundary points (excluding ghost points at either end)
    vector<Index> ghost_indices;   // surface ghost points
    vector<Index> surface_indices_with_ghosts;

  } Single_boundary_data; // the data related to each side of the component grids.

  typedef struct
  {
    vector<Single_boundary_data> third_periodic;
    vector<Single_boundary_data> second_periodic;
    vector<Single_boundary_data> first_periodic;
    vector<Single_boundary_data> interpolation;
    vector<Single_boundary_data> free;
    vector<Single_boundary_data> impermeable;
    vector<Single_boundary_data> exciting;
    vector<Single_boundary_data> absorbing;
    vector<Single_boundary_data> symmetry;

  } All_boundaries_data; // the data related to all sides of the composite grids.

  typedef struct
  {
    double k;
    double h;
    int surface;
    double g;
    double betar;
    double rho;
    double U;
    bool isDif3;

  } incidentWaveIntegralsParameters;

  typedef struct
  {
    double h;
    double g;
    double betar;
    double U;
    double a;
    double df;
    bool isDif3;
    bool shift;

  } integrandParameters;

  typedef struct
  {
    unsigned int p;
    unsigned int np;
    unsigned int nodenums;
    unsigned int concnums;
    string Wtype;
    double sigma;
    double Wmin;
    vector<int> isingular;
    realArray ds;
    realArray Ivec;
    gsl_matrix *nvec;
    RealArray nodes_xyz;
    InterpolatePointsOnAGrid *interp_object;

  } Patch;

  typedef struct
  {
    vector<Patch> patches;
    All_boundaries_data boundaries_data;

  } TriangulationData;

  typedef struct
  {
    int width;
    int order;
    double sigma;
  } filt_params;
}
#endif