//
// This file exports the data objects and member functions for the Filter class. The task of
// this class is to design the off-centered and centered filters for each free surface. All filters are
// defined using the notation mentioned in Berland et al. (JCP 2007). The idea used in the Filter
// class is very similar to that in the Biased class. This is why the implementation of both
// classes are accordingly similar.
//
// First we find the free surfaces and the corresponding index. Then the other two indices
// are selected to design and to apply the filter. For example  assume the free surface has been
// stored in A(I0,I1,I2), and the length of the I1 is 1. In this case, filtering will be
// carried out along index 0 and 2.
//
// After finding the filtering indices, we loop over all discritisation points on the
// free surface, and assign for each single point two sets of ranges and coefficients corresponding
// to the two filtering directions. We choose a dynamically allocated 3d matrix to store these
// information for every point at the free surface. The ranges and coefficients for each point
// are defined based on the desired stencil for the filter. Generally the stencil will be the one
// which is asked by the user, but close to the boundaries the stencil are changed. In this regard
// each point at the free surface has two sets of eligible points along the two directions which can be
// included in the filtering process.
//
// All discritisation and interpolation points are regarded as eligible, but hole points and ghost
// point are not. We exclude the ghost points since the filtering process will be applied after
// marching the free surrface where the ghost points are not updated correspondingly. If we would
// like to incldue the ghost points, we must update them after marching the free surface.
// The interpolation points get updated after time marching. Note that the operation to get the
// ranges and coefficients, are done just once and in the class constructor. Then the public member
// function which applies the filter in two directions of the structured grid will use these information.
// For the centered stencil we make use of the Savitzky-Golay filter coefficients, and for the
// off-centered stencils we make use of the coefficients proposed by Berland et al. (JCP 2007).
//
// The notation is as follows: (Ex. for a stencil width of 7)
//
// phi_new = sum( [f - sigma * C] * phi ) : multiplication is elementwise
//
// phi_new(0) = sum( [ (0 0 0 1 0 0 0) - sigma * (C(-3) C(-2) C(-1) C(0) C(1) C(2) C(3)) ] ) * (phi(-3) phi(-2) phi(-1) phi(0) phi(3) phi(2) phi(1) phi(0))
//
//                      (RealArray f)                           (RealArray C)                                  (RealMappedGridFunction)
//
// So the final coefficient which is multiplied by the function value is :
//
// sigma * (-C(-3) -C(-2) -C(-1) (1-C(0)) -C(1) -C(2) -C(3)) * (phi(-3) phi(-2) phi(-1) phi(0) phi(3) phi(2) phi(1) phi(0))
//
// In Berland's paper the off-center coefficients are defined as C(-3) C(-2) and so on. When we generate the Savitzky-Golay coefficienst
// we have to negate the coefficienst at indices -3, -2 , -1 , 1 , 2 , 3 ( as an example here), and we have to subtract by 1 the index
// at position 0. Eventually during applying the filter based on the above notation, the original Savitzky-Golay coefficiensts will recovder
// again. During the generation : (1 - sg) , -sg, but during filtering this becomes : 1 - (1 - sg) and -(-sg).
// We are doing this just to be consistent with the notation used for off-centered filter by Berland.
//

#ifndef __FILTER_H__
#define __FILTER_H__

#include "OW3DUtilFunctions.h"
#include "Grid.h"

namespace OW3DSeakeeping
{
  class Filter
  {
  public:
    typedef struct
    {
      int u0, d0, u1, d1, u2, d2; // Number of stencil points
      RealArray C0, C1, C2;       // Finite difference coefficients along axis 1, axis 2 and axis 3.
      RealArray f0, f1, f2;       // In Berland notation
      Range R0, R1, R2;           // Range of involving points for the differentiation, along axis 1, axis 2 and axis 3.
      double mask;

    } data; // Each point on the free surface has a variable of this type.

    typedef struct
    {
      int index[2];         // Loop index
      unsigned int size[2]; // The length of grid points in the corresponding directions
      vector<Index> Is;     //
      int grid;             // The surface belongs to this grid

    } direction; // For each surface there can be a variable of this type

    Filter(const CompositeGrid &, const vector<Single_boundary_data> &, const filt_params params); // constructor

    Filter(); // default constructor

    ~Filter(); // destructor

    Filter &operator=(const Filter &); // Assignment operator ( by deep copy )

    void ApplyFilter(realCompositeGridFunction &); // Apply the filter to the free surface potential and elevation in both directions

  private:
    data ***vertexData_;           // the data for each point on each free surfce is stored in a two-dimensional array ( the third dimension is for all free surfaces )
    vector<direction> directions_; // vector over the size of the free surface
    unsigned int nofs_;            // number of free surfaces, defined just for convenience.
    double sigma_;                 // filter strength
    int W_;                        // filter stencil width (asked by user)
    int HW_;                       // filter stencil half width (asked by user)
    int w_;                        // minimum width allowed by the program
    int hw_;                       // minimum half width allowed by the program
    int ORDER_;                    // user defined filter order
    int d_;                        // program defined centered stencil has an order = (w_ - d_)
    RealArray c_;                  // filter coefficients for user defined centered stencil
    RealArray f_;
    RealArray f03_, f30_;
    RealArray f15_, f51_;
    RealArray f28_, f82_;
    RealArray f37_, f73_;
    RealArray f46_, f64_;
    //
    RealArray c03_, c30_;
    RealArray c15_, c51_;
    RealArray c28_, c82_;
    RealArray c37_, c73_;
    RealArray c46_, c64_;

    static bool print_; // to make sure that the vertex data is printed just once regardless of the number of objects created.
    //
    void BuildFilters_(const CompositeGrid &, const vector<Single_boundary_data> &);
    void Filter_0_2_(
        unsigned int,
        const MappedGrid &,
        const vector<Index> &);
    void Filter_0_1_(
        unsigned int,
        const MappedGrid &,
        const vector<Index> &);
    void Filter_1_2_(
        unsigned int,
        const MappedGrid &,
        const vector<Index> &);
    Filter(const Filter &) {}; // Copy constructor ( copying is illegal! )
  };
}
#endif