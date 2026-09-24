// This public member function belongs to the FisrtOrderResults class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"

void OW3DSeakeeping::FirstOrder::BuildTransformData()
{

  double time_step = simulationData_.print_time_step;
  double end_time = simulationData_.print_time;

  transformData_.original_signal_length = simulationData_.print_step_count;

  // Choose the fft size here

  unsigned int user_specified_fft_size = (1 + paddingMultiple_) * transformData_.original_signal_length;

  // Correct the fft size as a power of 2

  double exponent = log(user_specified_fft_size) / log(2.0);
  transformData_.size_of_fft = pow(2, ceil(exponent));

  // No asymptotic continuation for zero speed problem

  transformData_.fitting_fraction = 0;
  transformData_.omegac = 0.0;
  transformData_.fitting_fraction = 0.0;
  transformData_.fitting_start_index = 0.0;
  transformData_.analytical_start_time = 0.0;
  transformData_.fitting_length = 0;

  // Asymptotic force continuation in the case of froward speed

  if (U_ != 0)
  {
    transformData_.omegac = fabs(tau_ * g_ / U_);
    transformData_.fitting_fraction = 0.1;
    transformData_.fitting_start_index = floor(end_time / time_step * (1.0 - transformData_.fitting_fraction));
    transformData_.fitting_start_time = (transformData_.fitting_start_index - 1) * time_step;
    transformData_.analytical_start_time = transformData_.size_of_fft * time_step;
    transformData_.fitting_length = simulationData_.print_step_count - transformData_.fitting_start_index;
  }

  transformSupplied_ = true;
  OW3DSeakeeping::PrintLogMessage("Transform data is built.");
}
