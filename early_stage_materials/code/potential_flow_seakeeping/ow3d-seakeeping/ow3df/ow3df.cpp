#include "Ogmg.h"
#include "Oges.h"
#include "OW3DConstants.h"
#include "FirstOrder.h"
#include "SecondOrder.h"

const string OW3DSeakeeping::program_name = "ow3df";

int main(int argc, char **argv)
try
{
  Overture::start(argc, argv);
  INIT_PETSC_SOLVER();

  OW3DSeakeeping::OverrideResults(OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name);
  OW3DSeakeeping::PrintLogMessage("Program started.");

  OW3DSeakeeping::Grid grid;
  CompositeGrid &cg = *grid.GetTheGrid();
  if (OW3DSeakeeping::UserInput.solve_motion)
    grid.ComputeHydrostatics();
  OW3DSeakeeping::Grid::GridData gridData = grid.GetGridData();
  OW3DSeakeeping::PrintLogMessage("Grid is read. Grid location and name: " + OW3DSeakeeping::UserInput.gridFileName);

  string ow3dt_results = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::time_domain_program;
  OW3DSeakeeping::Modes::Simulation simulationData;
  ifstream fbin(ow3dt_results + '/' + OW3DSeakeeping::simulation_data_binary_file, ios::in | ios_base::binary);
  if (!fbin.is_open())
    throw runtime_error(OW3DSeakeeping::GetColoredMessage("\t Error (OW3D), ow3df.cpp.\n\t File for the impulse data is missing.", 0));
  fbin.read((char *)&simulationData, sizeof simulationData);
  fbin.close();
  OW3DSeakeeping::PrintLogMessage("Time-domain impulse data is read.");

  OW3DSeakeeping::FirstOrder first_order(gridData, simulationData, cg);
  first_order.BuildMotionData();
  first_order.BuildTransformData();
  first_order.BuildFrequenciesAndWaveNumbers();

  first_order.ComputeBodySurfaceForces();         // First order forces on the body in time domain
  first_order.ComputeHydrodynamicCoefficients();  // Added mass and damping
  first_order.ComputeWaveExcitationForces();      // Scattering and Froude-Krylov complex force phasors
  first_order.ComputeResponseAmplitudeOperator(); // Motion phasors
  first_order.ComputeGModesDisplacements();

  first_order.PrintFrequencyDomainResults();
  first_order.PrintTimedomainResults();

  // -------------------------------------------------------------------------------------
  //                             Second-order quantities
  // -------------------------------------------------------------------------------------

  const vector<ComplexNumbers> RAOs = first_order.GetResponseAmplitudeOperators();
  const OW3DSeakeeping::FirstOrder::KsAndOmegas &allKsAndOmegas = first_order.GetAllKsAndOmegas();

  if (OW3DSeakeeping::transform_only_pots_for_drift)
    first_order.TransformVelocityPotentials();
  else
    first_order.TransformPotentialAndDerivatives();

  first_order.TransformWaterlineElevations();

  OW3DSeakeeping::SecondOrder second_order = OW3DSeakeeping::SecondOrder(gridData, cg, allKsAndOmegas, RAOs);

  if (OW3DSeakeeping::transform_only_pots_for_drift)
    second_order.ComputeWaveDriftForces();
  else
  {
    second_order.ComputeDriftFarField_m();
    second_order.ComputeDriftNearField();
    second_order.ComputeDriftSalvesen();
  }

  second_order.PrintDriftForces();

  Overture::finish();

  cout << "Program terminated normally." << '\n';
  OW3DSeakeeping::PrintLogMessage("Program terminated normally.");
  return 0;

} // End of try block

catch (exception &e)
{
  cerr << e.what() << endl;
  return 1;
}
catch (...)
{
  cerr << "exception" << endl;
  return 2;
}
