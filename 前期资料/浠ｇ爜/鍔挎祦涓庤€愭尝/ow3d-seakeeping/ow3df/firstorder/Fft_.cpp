//
// ----------------------------------------------------------------------------------------------------------------------------------------------------------
//
// This file contains the implementation of fft based on the code
// from pp 192-193, GNU Scientific Library-Reference Manual.
//
// The arguments to the function are :
//
// 1.  a const reference to the time domain data that is stored as a two- or one-dimensional RealArray
// 2.  The index which specifies on which column of the RealArray (on which response), the fft should act. 0 in the case of one-dimensional RealArray
// 3.  a reference to the frequency domain data that is a ComplexNumbers.
// 4.  a const reference to the transform data
// 5.  time step
// 6.  asymptotic fitting coefficients. Must be zero if zero padding is desired.
// 7.  a string which is part of the name of the output file to distinguish between different ffts.
// 8.  the result directory
//
// The results of the fft will be written in a file located in the folder called "other".
//
// Note: it has been assumed that the time domain signal is purely real.
//
// ----------------------------------------------------------------------------------------------------------------------------------------------------------

#include "gsl/gsl_fft_complex.h"
#include "ComplexNumbers.h"
#include "FirstOrder.h"
#include <iomanip>

#define REAL(z, i) ((z)[2 * (i)])
#define IMAG(z, i) ((z)[2 * (i) + 1])

void OW3DSeakeeping::FirstOrder::Fft_(
    const RealArray &time_domain_signal,
    int response,
    ComplexNumbers &freq_domain_signal,
    const Transform &transformData,
    const double &dt,
    vector<double> a,
    string fileName)
{
  ofstream fout(fileName);
  int prs = 5;
  int W = prs + 10;
  fout.precision(prs);
  fout.setf(ios_base::scientific);

  unsigned int print_fraction = 30;
  unsigned int output_size = transformData.size_of_fft / print_fraction;
  unsigned int original_length = transformData.original_signal_length; // make a shorter name
  unsigned int size = transformData.size_of_fft;                       // make a shorter name
  double te = transformData.original_signal_length * dt;               // the end time of the original signal
  double omegac = transformData.omegac;                                // make a shorter name

  unsigned int i;

  double *data = new double[2 * size];

  gsl_fft_complex_wavetable *wavetable;
  gsl_fft_complex_workspace *workspace;

  for (i = 0; i < size; i++)
  {
    if (i < original_length)
    {
      REAL(data, i) = time_domain_signal(response, i); // the real and imaginary part are stored alternately
    }
    else if (a[0] != 0 and a[1] != 0) // pad with asymptotic value
    {
      double t = te + (i - original_length) * dt;
      REAL(data, i) = (a[0] * sin(omegac * t) + a[1] * cos(omegac * t)) / t;
    }
    else // pad with zero
    {
      REAL(data, i) = 0.0;
    }

    IMAG(data, i) = 0.0; // time domain signal assumed to be real
  }

  wavetable = gsl_fft_complex_wavetable_alloc(size);
  workspace = gsl_fft_complex_workspace_alloc(size);

  gsl_fft_complex_forward(data, 1, size, wavetable, workspace);

  for (i = 0; i < size; i++)
  {
    freq_domain_signal(0, i) = REAL(data, i);
    freq_domain_signal(1, i) = IMAG(data, i);

    if (i < output_size and fout.is_open())
    {
      fout << setw(W) << freq_domain_signal(0, i) << setw(W) << freq_domain_signal(1, i) << '\n';
    }
  }

  gsl_fft_complex_wavetable_free(wavetable);
  gsl_fft_complex_workspace_free(workspace);
  delete[] data;

} // end of the fft function
