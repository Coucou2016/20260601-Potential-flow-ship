// This class imports the data objects and member functions for the
// FreeSurface class. This class is aimed for having the required
// data types and member functions for handling the velocity potential
// and elevation of the free surface. This class is the counterpart of
// the Field class that is introduced for handling of the velocity
// potential in the field. These two classes are also used for storing the
// desired sloution quantaties at the specific locations that will be used
// for final postprocessing.
// Note: Any object of this class is provided with one instance of
// the BiasedDifferencingScheme and Filter class. In the case of forward
// speed problems, either a biased scheme or a filter need to be used.
// There is also possible to apply a sponge layer at the free surface. The
// sponge layer is defined based on the user defined length and the shortest
// distance from any point in the sponge layer to the wall. The sponge layer
// is in fact a vector<RealArray> which has values between 0 and 1. The sponge
// is then applied at the free surface boundary condition. In the case no sponge
// layer is desired, all elements in the vector<RealArray> are just 0.

#ifndef __FREESURFACE_H__
#define __FREESURFACE_H__

#include "Ogshow.h"
#include "CompositeGridOperators.h"
#include "Baseflow.h"
#include "Modes.h"
#include "Upwind.h"
#include "Filter.h"

namespace OW3DSeakeeping
{
  class FreeSurface
  {
  public:
    typedef struct
    {
      realCompositeGridFunction elevation;
      realCompositeGridFunction potential;

    } ElvPot;

    typedef struct
    {
      ElvPot solution_start;
      ElvPot solution_stage;
      vector<ElvPot> slope;

    } StrStgSlp;

    typedef struct
    {
      Index iB1, iB2, iB3;
      Index iG1, iG2, iG3;

    } GBIX;

    FreeSurface(
        const OW3DSeakeeping::Grid::GridData &,
        const OW3DSeakeeping::Baseflow::baseFlowData *,
        CompositeGridOperators &,
        Interpolant &); // constructor

    ~FreeSurface();

    void Initialise(MODE_NAMES);

    void ComputeSolutionSlope(
        MAT_TYPES,
        const realCompositeGridFunction &,
        const realCompositeGridFunction &, // Field solution
        const int &,
        const Modes::Motion &);

    void SetStageSolution(
        const int &,   // set for this stage
        const double & // time step of the simulation
    );                 // this function is called before setting the right hand side of the field.

    void March(const double &);

    const realCompositeGridFunction &GetStagePotential();
    void PrintElevation(const double &) const;

    void PrintShowFile(); // outputs the surface elevation data in a hdf file.

    realCompositeGridFunction &GetElevationStart(); // the elevation at the start of the time interval
    realCompositeGridFunction &GetPotentialStart(); // the potential at the start of the time interval

    void InterpolateSolutions(string); // interpolate solutions at each "stage" or "step" given as the argument
    void StoreWaterlineElevations();
    void PrintUpwindVerifications();
    void PrintFilterVerifications();

  private:
    CompositeGrid *cg_;
    const OW3DSeakeeping::Grid::GridData *gridData_;
    const All_boundaries_data *boundariesData_;
    const OW3DSeakeeping::Grid::Boundary_integers *boundaryTypes_;
    string resultsDirectory_;
    unsigned int gx_wu_bcs_tag_;
    realCompositeGridFunction hom_frc_;

    const OW3DSeakeeping::Baseflow::baseFlowData *baseFlowData_;

    StrStgSlp freeSurface_;    // The free-surface data containing the velocity potential, elevation and their time derivatives at each stage of RK.
    vector<realArray> sponge_; // The damping array used for applying spong layer to the free surface.
    Interpolant interpolant_;  // For interpolation of free-surface solution, needed for differentiation of free-surface.
    string wlinesFileName_;
    MODE_NAMES mode_name_;

    int doubleBodyTag_; // used in the free-surface conditions: 1 only for the wave resistance problem with double body, otherwise 0

    realCompositeGridFunction d_phi_dx_, d_eta_dx_; // Needed for biased differencing
    realCompositeGridFunction d_phi_dz_, d_eta_dz_; // Needed for biased differencing
    Upwind upwind_object_;                          // Object of Upwind class.
    Filter filter_;                                 // Object of the Filter class
    bool filter_on_;
    bool showfile_; // For outputing the show file for surface elevation
    bool elevfile_; // For outputing the surface elevation in to text file
    Ogshow show_;

    vector<GBIX> bodyInd_;
    vector<GBIX> wallInd_;

    void BuildSpongLayer_(
        const vector<Coordinate> &,
        const vector<Grid::FREE_SURFACE_TYPES> &,
        double);

    void ExtractFreeSurfaceIndices_();
    void VerifyNeumannConditions_();
    void VerifyDerivatives_();

    FreeSurface(const FreeSurface &) {}                           // copy constructor   ( copying is illegal! )
    FreeSurface &operator=(const FreeSurface &) { return *this; } // assignment operator ( assignment is illegal! )
  };
}
#endif