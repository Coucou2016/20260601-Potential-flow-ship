// This private member function belongs to the SecondOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "SecondOrder.h"

double OW3DSeakeeping::SecondOrder::ComputeWaterlineTrapz_(vector<vector<double>> data)
{
  double result = 0.;

  for (unsigned int line = 0; line < wlData_.size(); line++)
  {
    unsigned int wlength = wlData_[line].size;

    double sum = 0.;

    for (unsigned int i = 0; i < wlength - 1; i++) // a simple trapezoidal integration
    {
      // NOTE : Only discretisation points in the waterline are considered.

      if (wlData_[line].mask[i] > 0 and wlData_[line].mask[i + 1] > 0)
      {
        double dl = wlData_[line].dl[i];

        sum += 0.5 * (data[line][i] + data[line][i + 1]) * dl;
      }
    }

    result += sum;

  } // end of loop over the waterlines

  return result;
}
