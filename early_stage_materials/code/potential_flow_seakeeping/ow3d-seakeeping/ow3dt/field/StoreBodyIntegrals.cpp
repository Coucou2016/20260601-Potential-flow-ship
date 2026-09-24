#include "Field.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Field::StoreBodyIntegrals()
{
  // first all desired data at the body surface gets updated before multiplying by normal vector.

  ExtractBodyPotentials_();

  // NOTE : After calling above function the required potentials at
  // the body surface will be stored in their corresponding
  // data structures. (phi_on_body, d_phi_dx_on_body, and .....)

  integrals_n integrals;

  ofstream fout(integralsFileName_, ios_base::out | ios_base::app | ios_base::binary);

  for (unsigned int resp = 0; resp < UserInput.responses.size(); resp++)
  {
    MultiplyByNormals_(UserInput.responses[resp], resp - UserInput.number_of_rigid_modes);

    integrals.phiu_n = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, potential_);
    integrals.d_phiu_dx_n = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, d_phiu_dx_);
    integrals.d_phib_dx_n = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, d_phib_dx_);
    integrals.d_phiu_dxx_n = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, d_phiu_dxx_);
    integrals.grad_phiu_grad_phib_n = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, grad_phiu_grad_phib_);
    integrals.grad_phiu_grad_phiu_n = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, grad_phiu_grad_phiu_);
    integrals.grad_phib_grad_phib_n = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, grad_phib_grad_phib_);

    fout.write((char *)&integrals, sizeof integrals);
  }

  fout.close();
}
