// This class import the required data objects and member functions for
// the Grid class. An instance of the grid class has all desired information
// regarding the grid, boundaries and .... . They can be extracted using
// the provided member functions. The constructor needs the grid
// file name and the file name for boundaries output as the arguments.
// The Run data type is used for storing the valid excitation and response
// modes for final simulation. It is included here in the Grid class, because
// the user input excitation and response mode is checked based on the grid
// dimensions in this class.

#ifndef __GRID_H__
#define __GRID_H__

#include "Input.h"

namespace OW3DSeakeeping
{
  class Grid
  {
  public:
    enum FREE_SURFACE_TYPES
    {
      BODY,
      BACK
    };

    enum BODY_SURFACE_TYPES
    {
      TOP,
      BOTTOM
    };

    typedef struct
    {
      double volx, voly, volz, VOLM;
      double xb, yb, zb;
      double xg, yg, zg;
      double MASS, SBSF;
      vector<vector<double>> complete_hydro_matrix; // size = total rigid modes + total generalized modes
      vector<vector<double>> reduced_hydro_matrix;  // size = the user-difined modes + total generalized modes

    } Hydrostatics;

    typedef struct
    {
      int third_periodic;
      int second_periodic;
      int first_periodic;
      int interpolation;
      int free;
      int impermeable;
      int exciting;
      int absorbing;
      int symmetry;

    } Boundary_integers; // the values of this type must match boundary tags during the grid generation.

    typedef struct
    {
      Index I0, I1, I2;           // These indices go over the waterline around the body.
      int grid;                   // The grid to which the waterline belonges.
      vector<double> x, y, z, dl; // The coordinates and the arc length of the waterline points
      vector<double> n1, n3, n2;  // The normal vectors for the waterline grid points
      vector<double> mask;        // The mask for the grid points of the waterline
      int size;                   // The number of grid points for each waterline
      int direction;              // The direction index which goes around each waterline
      double maxdl;
      double mindl;

    } WLD; // This type is used for defining water line data

    typedef struct
    {
      int flex_no;
      VRealArrays flex_disp;
      VRealArrays flex_vbn;
      VRealArrays flex_disp_der;
    } Flexible;

    typedef struct
    {
      int order_space;
      int ghost_line;              // Number of ghost line(s)
      int nog;                     // Number of component grids
      int nod;                     // Number of dimension
      double maximum_depth;        // The maximum depth of the basin
      double minimum_spacing_free; // The minimum spacing of grid points at the free surface.
      double maximum_spacing_body; // The maximum spacing of grid points at the body surface.
      double minimum_spacing_body; // The minimum spacing of grid points at the body surface
      double avgWl_spacing;        // The average spacing of grid points at the waterline.
      double maxWl_spacing;        // The maximum spacing of grid points at the waterline.
      double minWl_spacing;        // The minimum spacing of grid points at the waterline.
      double maximum_extension;
      bool halfSymmetry;                  // True if the grid is half symmetric ( along the x axis )
      double **symmetryCoefficients;      // The results will be multiplied by these coefficients according to the grid.
      Hydrostatics hrs;                   // The hydrostatic data for the body
      double kMax;                        // The Nyquist wave number = pi/(max ( maxWl_spacing, maximum_spacing ).
      double draft;                       // The draft of the body (positive value).
      vector<realArray> all_submerged_ys; //
      vector<vector<vector<DiscRanges>>> free_surface_disc;
      vector<vector<vector<DiscRanges>>> body_surface_disc;
      vector<FundamentalForms> body_fundamentals;
      vector<FundamentalForms> free_fundamentals;
      All_boundaries_data boundariesData;
      Boundary_integers boundaryTypes;
      vector<BODY_SURFACE_TYPES> bodySurfaceTypes;
      vector<FREE_SURFACE_TYPES> freeSurfaceTypes; // each free surface is either connected to the "body" or belongs to the "back" ground grid.
      vector<WLD> wlData;                          // for each free surface
      vector<Coordinate> bodyCoordinates;          // the coordinates of the domain outline at y=0 at body;
      vector<Coordinate> wallCoordinates;          // the coordinates of the domain outline at y=0 at wall;
      double maximum_body_length;
      double maximum_body_width;
      vector<Flexible> flexmodes;
      TriangulationData triangulation;
      unsigned int mid_grid_index;
      unsigned int ocean_grid_index;

    } GridData; // All composite grid data are accessible through a variable of this type.

    Grid(); // constructor

    ~Grid(); // destructor

    CompositeGrid *GetTheGrid();
    GridData GetGridData();
    void ComputeHydrostatics();
    void PrintGridFeatures() const; // to write grid data in to the log file.
    void PrintOW3DDerivatives();
    void PrintLaplacianErrors() const;
    realCompositeGridFunction &GetManSolMatrix();
    realCompositeGridFunction &GetManSolRHS();
    realCompositeGridFunction &GetManSolComp();

  private:
    CompositeGrid cg_;
    GridData gridData_;
    vector<HydrodynamicProblem> runs_; // for each valid excitation there is one Run
    bool symMemory_;
    string resultsDirectory_;
    unsigned int totalNumberOfModes_;
    vector<HydrodynamicProblem> resistance_runs_;
    vector<HydrodynamicProblem> radiation_runs_;
    vector<HydrodynamicProblem> diffraction_runs_;

    realCompositeGridFunction man_system_matrix_;
    realCompositeGridFunction man_system_right_;
    realCompositeGridFunction man_sol_;
    realCompositeGridFunction man_sol_comp_;

    int ExtractGridData_();
    vector<double> ComputeGridSpacingsOnSurface_(vector<Single_boundary_data> surface_data);
    int ExtractWaterlineData_();
    void ExtractBoundariesData_();
    void FindWallAndBodyCoordinates_(double);
    void ComputeSymmetryCoefficients_(); // must be called to get the grid symmetry coefficients
    FREE_SURFACE_TYPES FindFreeSurfaceType_(const Single_boundary_data &);
    BODY_SURFACE_TYPES FindBodySurfaceType_(const Single_boundary_data &);
    int ComputeGModeShape_();
    void BuildTriangulationData_();
    void SetManufacturedSolution_();

    string grid_data_file_;
    string grid_wline_file_;
    string grid_bdata_file_;
    string grid_wabcor_file_;
    string grid_symcof_file_;
    string grid_hydro_file_;
    string grid_disk_file_;
    void PrintBoundariesData_() const; // to write all boundaries data to the file.
    void PrintWallAndBodyCoordinates_() const;
    void PrintSymmetryCoefficients_() const;
    void PrintWaterlineData_() const;
    void PrintGridHydrostatics_() const;
    void PrintDiskRanges_() const;

    vector<Coordinate> ExtractBoundaryOutline_(const Single_boundary_data &); // extracts the coordinates at y=0 for specific boundary tag

    Single_boundary_data ExtractBoundaryData_(
        const int &,
        const int &,
        const int &,
        const IntegerArray &);

    // A private member function. Can be called to obtaing the new vertical
    // coordinates (y), where the coordinate at the free-suface (y=0) will be replaced
    // by the coordinate of the next grid point over the body surface.
    // The resulting y coordinates are placed in a vector of realArray, with the size determined
    // by the size of the exciting surfaces. Note use this function only for the floating geometries.

    void ExtractLiftedVerticalCoordinates_();

    void ExtractDiscRanges_();
    void ExtractSurfaceFundamentals_();
    int FDInterpolate2DWLS_(double *x0, valarray<valarray<double>> x, unsigned int np, double p, valarray<double> w, double dx, gsl_matrix *c);
    void GaussianIntegration2DWLSSetUp_(double **x, double **uv, int **StencilMap, const intArray &EtoV, Patch *patch);
    double CheckPatchInterpolations_();
    void PrintPatchInterpolations_();

    Grid(const Grid &) {}                           // copy constructor   ( copying is illegal! )
    Grid &operator=(const Grid &) { return *this; } // assignment operator ( assignment is illegal! )
  };
}
#endif
