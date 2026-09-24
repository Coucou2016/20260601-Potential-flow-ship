// This file imports the data objects and member functions for
// the Biased class. This class is designed for arbitrary
// evaluation of the convective derivatives appearing at the free surface
// boundary condition. Note that it is just surface points that are
// included in the differentiation. So other surfaces can be easily included.
// At the moment just the first derivative in "x" and "z" direction has been implemented.
// The class can be easily extended for other derivatives.
//
// Note that the current version of "fdCoefficients" function produces the
// finite difference coefficients for the one-dimensional stencil. So this function
// must be changed accordingly to include the two-dimensional stencil, if the class is to
// be extended for other derivatives.
//
// For each point at the free surface and along two directions we find
// the biased stencil based on the criterion that the biasing is always
// towrads increasing the "x" coordinate.  This is becuase the body has a
// forward speed just in x direction. Accordingly we have defined three
// string variables (ind0 ind1 ind2) to save this information.
// In the case of zero forward speed all these string variables are "cen" meaning
// that a centered stencil is assigned for all points.
// Note that there is another possibility where in the case of forward speed
// problems some points may have neutral positions with regard to upwinding.
// This happens when a grid line is totally perpendicualr to the x coordinate.
// So in this case we assign a neutral stencil "neu" that is in fact a
// centered stencil. This means that we can for example have a "dec" stencil in
// one direction and a "neu" stencil in the other direction. "cen" happens when
// forward speed is zero. All these are checked by the following line in the code:

// if( ( (fabs(xd1 - xi1) <= tolb) and ( ( fabs(xc)>fabs(xd1) and fabs(xc)>fabs(xi1) ) or fabs(xs1-xn1)<= tols ) ) or U_==0 ) // neutral or centered stencil
//             (1)                                            (2)                                (3)                   (4)
//
// (1) says that at this point incrementing or decrementing (just by one index) will not change the x coordinates.
//
// Then two cases may happen: first at symmetry plane along x axis where we have the follwing situations:
//
//
//
//    symmetry plane  --------------o        o-----------------          o are the grid points on the body, and xc is the point at the symmetry plane
//                                  o        o
//                                  o        o
//                                   o      o
//
//
// so (2) will care for these cases. In the left case, xc is less than xd and xi. In the right case xc is greater than xd and xi
//
// And in the second case we may have following case:
//
//
//    symmetry plane  ---------------o       o----------------
//                                    o     o
//                                      o o
//                                       o
//                                       o
//                                       o
//
// So (3), checks if the first and last grid points on the line have the same x coordinate. In this case all point along the line
// will have neutral stencil
//
// and finally (4) makes sure that in the case of zero forward speed, the code inside the block after the above if condition will execute to
// assign a centered stencil

#ifndef __BIASED__
#define __BIASED__

#include "Input.h"
#include "Grid.h"

namespace OW3DSeakeeping
{
  class Upwind
  {
  public:
    typedef struct
    {
      UPWIND_STENCIL_TYPES ind0x, ind1x, ind2x; // Biasing by index incrementing "inc" or index decrementing "dec" ? Or a neutral stencil ("neu") and a centered stencil ("cen").
      UPWIND_STENCIL_TYPES ind0z, ind1z, ind2z;
      int u0x, d0x, u1x, d1x, u2x, d2x; // Number of stencil points
      int u0z, d0z, u1z, d1z, u2z, d2z; // Number of stencil points
      RealArray C0x, C1x, C2x;          // Finite-difference coefficients along axis 1, axis 2 and axis 3.
      RealArray C0z, C1z, C2z;
      Range R0x, R1x, R2x; // Range of involving points for the differentiation, along axis 1, axis 2 and axis 3.
      Range R0z, R1z, R2z;
      double vder0x, vder1x, vder2x; // The partial derivative of axis "1", "2" and "3" (in parameter space) with respect to "x" axis.
      double vder0z, vder1z, vder2z; // The partial derivative of axis "1", "2" and "3" (in parameter space) with respect to "z" axis.
      double mask;                   // Mask of the grid point(needed to exclude the hole points)

    } data; // Each point on the free surface has a variable of this type.

    typedef struct
    {
      int index[2];         // Loop index
      unsigned int size[2]; // The length of grid points in the corresponding directions
      vector<Index> Is;     //
      int grid;             // The surface belongs to this grid
      double spacing[3];    // Grid spacing on unit square

    } direction; // For each surface there can be a variable of this type

    Upwind(
        CompositeGrid &,
        const vector<realArray> &d_phin_dx,
        const vector<realArray> &d_phib_dz,
        const OW3DSeakeeping::Grid::GridData &gridData,
        int a, int b); // Constructor

    Upwind(); // Default constructor

    ~Upwind(); // Destructor

    Upwind &operator=(const Upwind &); // Assignment operator ( by deep copy )

    void ComputeDerivatives(
        const realCompositeGridFunction &,
        realCompositeGridFunction &,
        realCompositeGridFunction &); // Pass by reference both the function and the derivatives as realCompositeGridFunction

    void ApplyNeumannCondition(realCompositeGridFunction& u,const realCompositeGridFunction& forcing);

    data ***GetVertexData();               // Can be called to obtain the information for the biased stencil of each grid point at free surface
    vector<direction> GetDirectionsData(); // Can be called to obtain the information regarding the search direction for each free surface

  private:
    data ***vertexData_;           // The data for each point on each free surfce is stored in a two-dimensional array ( the third dimension is for all free surfaces )
    vector<direction> directions_; // Vector over the size of the free surface
    int u_, d_;                    // Number of stencil points. u_ : upwind d_: downwind
    double U_;                     // Forward speed needed to find upwind direction (defined just for convenience in coding)
    unsigned int nofs_;            // Number of free surface (defined just for convenience in coding)
    static bool printx_;           // To make sure that the vertex data is printed just once regardless of the number of objects created.
    static bool printz_;
    const OW3DSeakeeping::Grid::GridData *gridData_;
    const All_boundaries_data *boundariesData_;
    const OW3DSeakeeping::Grid::Boundary_integers *boundaryTypes_;

    void BuildVertexData_(
        CompositeGrid &,
        const vector<realArray> &d_phib_dx,
        const vector<realArray> &d_phib_dz);
    void flipArray_(RealArray &);

    void BuildUpwindStenciles_1_2_(
        unsigned int,
        const MappedGrid &,
        const vector<Index> &,
        const vector<Index> &,
        const vector<realArray> &d_phib_dx,
        const vector<realArray> &d_phib_dz);
    void BuildUpwindStenciles_0_2_(
        unsigned int,
        const MappedGrid &,
        const vector<Index> &,
        const vector<Index> &,
        const vector<realArray> &d_phib_dx,
        const vector<realArray> &d_phib_dz);
    void BuildUpwindStenciles_0_1_(
        unsigned int,
        const MappedGrid &,
        const vector<Index> &,
        const vector<Index> &,
        const vector<realArray> &d_phib_dx,
        const vector<realArray> &d_phib_dz);

    Upwind(const Upwind &) {} // Copy constructor ( copying is illegal! )
  };
}
#endif
