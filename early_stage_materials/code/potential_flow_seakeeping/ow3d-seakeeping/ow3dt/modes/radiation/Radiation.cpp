
// implementation of the Radiation class

#include "Modes.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Radiation::Radiation(const OW3DSeakeeping::Grid::GridData &gridData) : Modes(gridData)
{
  dispFileName_ = _resultsDirectory + '/' + OW3DSeakeeping::impulse_body_displacement_binary_file;
  timeFileName_ = _resultsDirectory + '/' + OW3DSeakeeping::time_binary_file;
}

const OW3DSeakeeping::Modes::Motion &OW3DSeakeeping::Radiation::GetMotionData(int step, int stage)
{
  double c = _rk_c[stage];
  double dt = _simulation_data.time_step;
  double fd = _simulation_data.frequency_deviation;

  motions_.time = (step + c) * dt;

  motions_.displacement = exp(-2.0 * pow(Pi * fd, 2.0) * pow(motions_.time - 4.0 / (Pi * fd), 2.0));
  motions_.velocity = -4.0 * pow(Pi * fd, 2.0) * (motions_.time - 4.0 / (Pi * fd)) * motions_.displacement;
  motions_.fsbcRamp = 1.0;

  motions_.elevation = 0.0; // non-zero just for diffraction problem

  return motions_;
}

void OW3DSeakeeping::Radiation::StoreMotionData() const
{
  double time = motions_.time;

  ofstream tbout(timeFileName_, ios_base::out | ios_base::app | ios_base::binary);
  tbout.write((char *)&time, sizeof time);

  double disp = motions_.displacement;
  ofstream dbout(dispFileName_, ios_base::out | ios_base::app | ios_base::binary);
  dbout.write((char *)&disp, sizeof disp);
}
