
// implementation of the Resistance class

#include "Modes.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Resistance::Resistance(const OW3DSeakeeping::Grid::GridData &gridData) : Modes(gridData)
{
  veloFileName_ = _resultsDirectory + '/' + OW3DSeakeeping::impulse_body_velocity_binary_file;
  timeFileName_ = _resultsDirectory + '/' + OW3DSeakeeping::time_binary_file;

} // just call the base class constructor

const OW3DSeakeeping::Modes::Motion &OW3DSeakeeping::Resistance::GetMotionData(
    int step,
    int stage)
{
  double c = _rk_c[stage];
  double dt = _simulation_data.time_step;

  motions_.time = (step + c) * dt;

  motions_.displacement = 0.0; // no displacement for steady-wave problem
  motions_.elevation = 0.0;    // non-zero just for diffraction problem

  if (UserInput.base_flow_type == BASE_FLOW_TYPES::DB) // double body
  {
    motions_.velocity = 0.0;                                      // no velocity is applied for the wave resistance with DB linearization.
    motions_.fsbcRamp = 1.0 - exp(-0.15 * pow(motions_.time, 2)); // ramp function for the free surface BC's is always 1 except for the wave resistance with DB linearization.
  }
  if (UserInput.base_flow_type == BASE_FLOW_TYPES::NK) // neumann kelvin
  {
    motions_.velocity = UserInput.U * (1.0 - exp(-0.15 * pow(motions_.time, 2))); // velocity applied for the body boundary condition.
    motions_.fsbcRamp = 1.0;
  }

  return motions_;
}

void OW3DSeakeeping::Resistance::StoreMotionData() const
{
  double time = motions_.time;

  ofstream tbout(timeFileName_, ios_base::out | ios_base::app | ios_base::binary);
  tbout.write((char *)&time, sizeof time);

  double velo = motions_.velocity;
  ofstream vbout(veloFileName_, ios_base::out | ios_base::app | ios_base::binary);
  vbout.write((char *)&velo, sizeof velo);
}
