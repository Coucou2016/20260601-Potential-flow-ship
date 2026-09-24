// This public member function belongs to the FisrtOrderResults class, and just for
// the convenience is written in a seperate file.

#include "gsl/gsl_linalg.h"
#include "gsl/gsl_matrix.h"
#include "gsl/gsl_complex_math.h"
#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::ComputeResponseAmplitudeOperator()
{
  if (diffraction_runs_.size() != 0 and addedMass_.size() != 0 and damping_.size() != 0 and UserInput.solve_motion)
  {
    unsigned int vec_size = UserInput.responses.size();
    gsl_matrix_complex *C = gsl_matrix_complex_alloc(vec_size, vec_size);
    gsl_matrix_complex *hydrostatic = gsl_matrix_complex_alloc(vec_size, vec_size);
    gsl_matrix_complex *mass = gsl_matrix_complex_alloc(vec_size, vec_size);
    gsl_matrix_complex *addedmass = gsl_matrix_complex_alloc(vec_size, vec_size);
    gsl_matrix_complex *damping = gsl_matrix_complex_alloc(vec_size, vec_size);
    gsl_vector_complex *force = gsl_vector_complex_alloc(vec_size);
    gsl_vector_complex *rao = gsl_vector_complex_alloc(vec_size);                      // The solution vector
    gsl_matrix_complex *gm_stiff = gsl_matrix_complex_alloc(vec_size, vec_size);       // generalized stiffness matrix
    gsl_matrix_complex *gm_shear_stiff = gsl_matrix_complex_alloc(vec_size, vec_size); // The generalized stiffness matrix

    // Initialize all to zero

    gsl_matrix_complex_set_zero(C);
    gsl_matrix_complex_set_zero(hydrostatic);
    gsl_matrix_complex_set_zero(gm_stiff);
    gsl_matrix_complex_set_zero(gm_shear_stiff);
    gsl_matrix_complex_set_zero(mass);
    gsl_matrix_complex_set_zero(addedmass);
    gsl_matrix_complex_set_zero(damping);
    gsl_vector_complex_set_zero(force);

    int signum;
    gsl_permutation *perm = gsl_permutation_alloc(vec_size);

    // Note : for each "i" the data are stored column-wise in the matrices by incrementing the "j" index:
    //
    // In the matrices:       In the force vector:
    //
    //  i=0 i=1 ..
    // | o   o ... | j=0          | o | i=0
    // | o   o ... | j=1          | o | i=1
    // | o   o ... | j=2          | . | ...
    // | o   o ... | j=3          | . | ...
    //

    // NOTE : The hydrodynamic coefficients are stored for each excitation
    //        mode in a "realArray". They are accessible by indexing as follows:
    //
    //                             a[mode](i,f),
    //
    //        where "i" is the response mode index and "f" is the frequency index.
    //
    //        This way of storing the hydrodynamic coefficients justifies that
    //        the matrices in the equation of motion are set column-wise. For each
    //        direction of the force, all response coefficients for the same mode of motion will
    //        be stored in the corresponding column of the matrix. This is the reason for
    //        setting the gsl matrix by column.
    //

    // Loop over encounter frequencies and build the complex matrix C

    for (unsigned int f = 0; f < omegaeAll_.size(); f++)
    {
      for (unsigned int i = 0; i < vec_size; i++)
      {
        // The force vector
        gsl_vector_complex_set(force, i, gsl_complex_rect(excitation_force_[i](0, f), excitation_force_[i](1, f)));

        for (unsigned int j = 0; j < vec_size; j++) // All coefficinets for motion in "i" direction are stored column-wise.
        {
          // The added mass matrix
          gsl_matrix_complex_set(addedmass, j, i, gsl_complex_rect(addedMass_[i](j, f), 0));

          // The damping matrix ( i*omega*b )
          gsl_matrix_complex_set(damping, j, i, gsl_complex_rect(0, omegaeAll_[f] * damping_[i](j, f)));

          // The mass matrix (user input)
          gsl_matrix_complex_set(mass, j, i, gsl_complex_rect(OW3DSeakeeping::UserInput.mass_matrix[j][i], 0));

          // The generalized modes structural stiffness (user input):
          gsl_matrix_complex_set(gm_stiff, j, i, gsl_complex_rect(UserInput.stiffness_matrix[j][i], 0));

          // The generalized modes structural shear stiffness (user input):
          gsl_matrix_complex_set(gm_shear_stiff, j, i, gsl_complex_rect(UserInput.shear_stiffness_matrix[j][i], 0));

          // The hydrostatic matrix
          gsl_matrix_complex_set(hydrostatic, j, i, gsl_complex_rect(gridData_->hrs.reduced_hydro_matrix[j][i] + speed_hydrostatics_(j, i), 0));
        }
      }

      // Set the C matrix
      gsl_matrix_complex_add(mass, addedmass);                                     // Now added mass has been added to the mass matrix
      gsl_matrix_complex_scale(mass, gsl_complex_rect(-pow(omegaeAll_[f], 2), 0)); // Now -omega^2 * (mass + added mass) is in the mass matrix
      if (gmode_type == GMODE_TYPES::TIMOSHENKO_STRHY || gmode_type == GMODE_TYPES::TIMOSHENKO_STRUC)
      {
        gsl_matrix_complex_scale(gm_shear_stiff, gsl_complex_rect(pow(omegaeAll_[f], 2), 0)); // Now omega^2 * shear stiffness is in the shear stiffness matrix
        gsl_matrix_complex_add(gm_stiff, gm_shear_stiff);                                     // Now bending and shear stiffness are both included in structal stiffness
      }
      gsl_matrix_complex_add(hydrostatic, gm_stiff); // Add stiffness matrix to hydrostatic matrix for generalized modes
      gsl_matrix_complex_add(damping, hydrostatic);  // Now  i*omega*damping + hydrostatic is in hydrostatic matrix
      gsl_matrix_complex_add(mass, damping);
      gsl_matrix_complex_add(C, mass); // We could use instead the mass matrix here, but we build a new C matrix

      // C is now set for this frequency. Solve the matrix to get
      // the rao for this frequency and for the corresponding responses

      gsl_linalg_complex_LU_decomp(C, perm, &signum);
      gsl_linalg_complex_LU_solve(C, perm, force, rao);

      // Store the results. RAO for each response direction is arranged as follows:
      //
      //                         real    imag
      // axis 0 ---> :            (0)     (1)
      //
      // axis 1 ( 0) omega(0)      o       o
      // axis 1 ( 1) omega(1)      o       o
      // axis 1 ( 2) omega(2)      o       o
      // axis 1 ( 3) omega(3)      o       o
      // axis 1 ( 4) omega(4)      o       o
      // axis 1 ( 5) omega(5)      o       o
      // ...                       ...
      //

      for (unsigned int i = 0; i < vec_size; i++)
      {
        RAO_[i](0, f) = (gsl_vector_complex_get(rao, i)).dat[0]; // Real
        RAO_[i](1, f) = (gsl_vector_complex_get(rao, i)).dat[1]; // Imag
      }

      gsl_matrix_complex_set_zero(C);

    } // End of frequency loop

    // Free the memories

    gsl_matrix_complex_free(C);
    gsl_matrix_complex_free(mass);
    gsl_matrix_complex_free(addedmass);
    gsl_matrix_complex_free(hydrostatic);
    gsl_matrix_complex_free(damping);
    gsl_permutation_free(perm);
    gsl_vector_complex_free(force);

    OW3DSeakeeping::PrintLogMessage("Reponse amplitude operators computed.");
    raoCalc_ = true;

  } // End of check for force vector size
}