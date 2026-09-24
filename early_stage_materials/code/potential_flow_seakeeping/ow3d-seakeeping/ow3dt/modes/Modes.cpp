// This file contains the implementation of the excitation class.

#include "Modes.h"
#include "OW3DConstants.h"

// Implementation of abstract base class Excitation

OW3DSeakeeping::Modes::Modes(const OW3DSeakeeping::Grid::GridData &gridData)
{
  _resultsDirectory = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;
  _rk_c = OW3DSeakeeping::rk_c;

  // Time domain discription of the displacement:
  //
  // eta(t) = exp( -2*pi^2*s^2(t-4/(pi*s))^2 )
  // frequency deviation s = sqrt(-fmax^2/(2*log(p)) )
  // p = frequency cut-off that is the ratio between the maximum displacement and the displacement at the maximum frequency.
  // fmax = calculated using grid spacing

  // Determine the pseudo-impulse characteristics

  double lmax = gridData.maximum_extension;
  double lmin = gridData.avgWl_spacing;
  double h = gridData.maximum_depth;
  double g = OW3DSeakeeping::UserInput.g;
  double Kmin = 2 * Pi / lmax;
  double Kmax = 2 * Pi / lmin;

  _simulation_data.minimum_frequency = sqrt(g * Kmin * tanh(Kmin * h));                                                       // NOTE : This is an angular frequency!.
  _simulation_data.maximum_frequency = 1. / (2 * Pi) * sqrt(g * Kmax * tanh(Kmax * h));                                       // NOTE : This is not an angular frequency!.
  _simulation_data.frequency_deviation = sqrt(-pow(_simulation_data.maximum_frequency, 2.0) / (2.0 * log(frequency_cutoff))); // Hz
  _simulation_data.midpoint_time = 4.0 / (Pi * _simulation_data.frequency_deviation);                                         // the time of peak displacement s

  // Determine simulation time
  double midpoint_multiple = UserInput.run_time / _simulation_data.midpoint_time * sqrt(gridData.maximum_body_length / g);
  _simulation_data.sample_time = _simulation_data.midpoint_time * midpoint_multiple; // run duration

  // The velocity corresponding to the shortest wave (maximum frequency)
  _simulation_data.minimum_velocity = CalculateMinimumVelocity_(_simulation_data.maximum_frequency, gridData.maximum_depth, g);

  // The highest possible velocity at this grid (long wave)
  _simulation_data.maximum_velocity = sqrt(g * gridData.maximum_depth); // phase velocity in shallow water m/s

  // Number of tiem steps
  _simulation_data.time_step = OW3DSeakeeping::UserInput.courant * lmin / _simulation_data.maximum_velocity;
  _simulation_data.step_count = int(ceil(_simulation_data.sample_time / _simulation_data.time_step) + 1); // number of steps in the run duration
  if (1 / _simulation_data.time_step < _simulation_data.maximum_frequency)
    throw runtime_error(GetColoredMessage("\t Error (OW3D), Modes::Modes.cpp. \n\t Maximum frequency based on CFL condition exceeds the fmax computed based on the grid spacing.", 0));
  _simulation_data.sample_time = _simulation_data.time_step * _simulation_data.step_count;
  _simulation_data.print_step_count = int(floor((_simulation_data.step_count) / UserInput.postRate));
  _simulation_data.print_time_step = UserInput.postRate * _simulation_data.time_step;
  _simulation_data.print_time = _simulation_data.print_step_count * _simulation_data.print_time_step;
  if (_simulation_data.step_count % _simulation_data.print_step_count != 0)
    throw runtime_error(GetColoredMessage("\t Error (OW3D), Modes::Modes.cpp.\n\t Change your print rate!.", 0));
}

double OW3DSeakeeping::Modes::CalculateMinimumVelocity_(
    const double &maximum_frequency,
    const double &maximum_depth,
    const double &g)
{
  double angular_frequency = 2 * Pi * maximum_frequency;
  double wave_number_new;
  double wave_number_old = 1.0;
  double error = 1.0;
  while (abs(error) > 1e-6)
  {
    wave_number_new = pow(angular_frequency, 2.0) / (g * tanh(wave_number_old * maximum_depth));
    error = wave_number_old - wave_number_new;
    wave_number_old = wave_number_new;
  }

  double minimum_velocity = 2 * Pi * maximum_frequency / wave_number_new;

  return minimum_velocity;

} // end of calculate_minimum_velocity function

void OW3DSeakeeping::Modes::StoreSimulationData() const
{
  string ascii_file_name = _resultsDirectory + '/' + OW3DSeakeeping::simulation_data_ascii_file;
  ofstream fout(ascii_file_name, ios::out);
  fout.setf(ios_base::scientific);
  fout.precision(OW3DSeakeeping::print_precision);
  fout << "Time-domain simulation data " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';

  fout << "number of time steps ---------- " << _simulation_data.step_count << '\n'
       << "number of print time steps ---- " << _simulation_data.print_step_count << '\n'
       << "duration ---------------------- " << _simulation_data.sample_time << '\n'
       << "print duration ---------------- " << _simulation_data.print_time << '\n'
       << "time step --------------------- " << _simulation_data.time_step << '\n'
       << "print time step --------------- " << _simulation_data.print_time_step << '\n'
       << "midpoint time ----------------- " << _simulation_data.midpoint_time << '\n'
       << "minimum frequency ------------- " << _simulation_data.minimum_frequency << '\n'
       << "maximum frequency ------------- " << _simulation_data.maximum_frequency * 2 * Pi << '\n'
       << "frequency deviation ----------- " << _simulation_data.frequency_deviation << '\n'
       << "minimum velocity -------------- " << _simulation_data.minimum_velocity << '\n'
       << "maximum velocity -------------- " << _simulation_data.maximum_velocity << '\n';
  fout.close();

  string binary_file_name = _resultsDirectory + '/' + OW3DSeakeeping::simulation_data_binary_file;
  ofstream fbout(binary_file_name, ios_base::out | ios_base::binary);
  fbout.write((char *)&_simulation_data, sizeof _simulation_data);
  fbout.close();
}

const OW3DSeakeeping::Modes::Simulation &OW3DSeakeeping::Modes::GetSimulationData() const
{
  return _simulation_data;
}
