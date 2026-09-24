// This public member function belongs to the FisrtOrderResults class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::BuildMotionData()
{
  int steps = simulationData_.print_step_count;

  time_.resize(1, steps);

  string timeFileName = time_domain_folder_ + '/' + OW3DSeakeeping::time_binary_file;
  ifstream tbout(timeFileName, ios_base::in | ios_base::binary);

  if (!tbout.is_open())
  {
    throw runtime_error("Error, OW3DSeakeeping::FirstOrder::BuildMotionData.cpp: File for the time data can not be opened.");
  }

  for (int i = 0; i < steps; i++)
  {
    double t;
    int shift = i;

    tbout.seekg(shift * (sizeof t), ios_base::beg);
    tbout.read((char *)&t, sizeof t);

    time_(0, i) = t; // READ TIME DATA
  }

  if (radiation_runs_.size() != 0 || gmodes_runs_.size() != 0)
  {
    displacement_.resize(1, steps);

    string dispFileName = time_domain_folder_ + '/' + OW3DSeakeeping::impulse_body_displacement_binary_file;
    ifstream dbout(dispFileName, ios_base::in | ios_base::binary);

    if (!dbout.is_open())
    {
      throw runtime_error("Error, OW3DSeakeeping::FirstOrder::BuildMotionData.cpp: File for the displacement data can not be opened.");
    }
    for (int i = 0; i < steps; i++)
    {
      double d;
      int shift = i;

      dbout.seekg(shift * (sizeof d), ios_base::beg);
      dbout.read((char *)&d, sizeof d);

      displacement_(0, i) = d; // READ DISPLACEMENT DTATA
    }

  } // End of store the (Gaussian) body displacement

  if (diffraction_runs_.size() != 0)
  {
    elevation_.resize(1, steps);

    string elevFileName = time_domain_folder_ + '/' + OW3DSeakeeping::impulse_wave_elevation_binary_file;
    ifstream ebout(elevFileName, ios_base::in | ios_base::binary);
    if (!ebout.is_open())
    {
      throw runtime_error("Error, OW3DSeakeeping::FirstOrder::BuildMotionData.cpp: File for the elevation data can not be opened.");
    }
    for (int i = 0; i < steps; i++)
    {
      double e;
      int shift = i;

      ebout.seekg(shift * (sizeof e), ios_base::beg);
      ebout.read((char *)&e, sizeof e);

      elevation_(0, i) = e; // READ ELEVATION DATA
    }

  } // End of store the (Gaussian) wave elevation

  if (resistance_runs_.size() != 0)
  {
    velocity_.resize(1, steps);

    string velcFileName = time_domain_folder_ + '/' + OW3DSeakeeping::impulse_body_velocity_binary_file;
    ifstream vbout(velcFileName, ios_base::in | ios_base::binary);
    if (!vbout.is_open())
    {
      throw runtime_error("Error, OW3DSeakeeping::FirstOrder::BuildMotionData.cpp: File for the velocity data can not be opened.");
    }
    for (int i = 0; i < steps; i++)
    {
      double v;
      int shift = i;

      vbout.seekg(shift * (sizeof v), ios_base::beg);
      vbout.read((char *)&v, sizeof v);

      velocity_(0, i) = v; // READ VELOCITY DATA
    }

  } // End of store the body velocity

  motionSupplied_ = true;

  OW3DSeakeeping::PrintLogMessage("Time-domain motion data is read.");
}
