// This private member function belongs to the FisrtOrderResults class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"

void OW3DSeakeeping::FirstOrder::ComputePotentialsAsymptoticCoefficients_(const vector<double> &data, vector<double> cofs)
{
  least_square_data lsd;
  lsd.size = (transformData_.original_signal_length - transformData_.fitting_start_index); // number of data points to be fitted
  lsd.y = new double[lsd.size];
  lsd.sigma = new double[lsd.size];

  for (unsigned int i = 0; i < lsd.size; i++)
  {
    lsd.sigma[i] = 1.0;                                      // the measurement error (standard deviation)
    lsd.y[i] = data[transformData_.fitting_start_index + i]; // the data points to be fitted
  }

  lsd.p = numberOfFittingCoefficients_;
  lsd.x_init = new double[lsd.p];
  lsd.x_init[0] = 0.1;                // initial guess for a1
  lsd.x_init[1] = 0.1;                // initial guess for a2
  lsd.omegac = transformData_.omegac; // critical frequency
  lsd.dt = simulationData_.print_time_step;
  lsd.tm = transformData_.fitting_start_time;
  lsd.n = 1;

  string filename = results_folder_ + "/potential_least_square_results.dat";

  leastSquareFitting(t_n_sine_cosine_f, t_n_sine_cosine_df, t_n_sine_cosine_fdf, lsd, cofs, filename);

  delete[] lsd.y;
  delete[] lsd.sigma;
  delete[] lsd.x_init;
}
