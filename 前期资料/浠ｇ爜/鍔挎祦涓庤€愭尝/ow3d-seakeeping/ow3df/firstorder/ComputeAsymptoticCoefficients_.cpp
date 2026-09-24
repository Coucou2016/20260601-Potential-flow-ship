// This private member function belongs to the FisrtOrderResults class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::ComputeAsymptoticCoefficients_()
{
    if (diffractionBodyForces_.size() != 0) // For scattering problems
    {
        unsigned int numberOfFittingCoefficients = 2;
        for (unsigned int runIndex = 0; runIndex < UserInput.dif_runs.size(); runIndex++)
        {
            for (unsigned int respIndex = 0; respIndex < UserInput.responses.size(); respIndex++)
            {
                least_square_data lsd;
                lsd.size = (transformData_.original_signal_length - transformData_.fitting_start_index); // number of data points to be fitted
                lsd.y = new double[lsd.size];
                lsd.sigma = new double[lsd.size];

                for (unsigned int i = 0; i < lsd.size; i++)
                {
                    lsd.sigma[i] = 1.0;                                                                             // the measurement error (standard deviation)
                    lsd.y[i] = diffractionBodyForces_[runIndex](respIndex, transformData_.fitting_start_index + i); // the data points to be fitted
                }

                lsd.p = numberOfFittingCoefficients;
                lsd.x_init = new double[lsd.p];
                lsd.x_init[0] = 0.1; // initial guess for a1
                lsd.x_init[1] = 0.1; // initial guess for a2

                lsd.omegac = transformData_.omegac; // critical frequency
                lsd.dt = simulationData_.print_time_step;
                lsd.tm = transformData_.fitting_start_time;
                lsd.n = 1; // the power of the 1/t^n in the least square model function

                string filename = results_folder_ + '/' + UserInput.project_name + OW3DSeakeeping::least_square_status_file_extension;

                leastSquareFitting(t_n_sine_cosine_f, t_n_sine_cosine_df, t_n_sine_cosine_fdf, lsd, ls_fit_coeffs_scat_[runIndex][respIndex], filename);
                delete[] lsd.y;
                delete[] lsd.sigma;
                delete[] lsd.x_init;
            }
        }
    }
    if (radiationBodyForces_.size() != 0) // For radition problems
    {
        unsigned int numberOfFittingCoefficients = 2;

        for (unsigned int runIndex = 0; runIndex < UserInput.rad_runs.size(); runIndex++)
        {
            for (unsigned int respIndex = 0; respIndex < UserInput.responses.size(); respIndex++)
            {
                least_square_data lsd;
                lsd.size = (transformData_.original_signal_length - transformData_.fitting_start_index); // number of data points to be fitted
                lsd.y = new double[lsd.size];
                lsd.sigma = new double[lsd.size];

                for (unsigned int i = 0; i < lsd.size; i++)
                {
                    lsd.sigma[i] = 1.0;                                                                           // the measurement error (standard deviation)
                    lsd.y[i] = radiationBodyForces_[runIndex](respIndex, transformData_.fitting_start_index + i); // the data points to be fitted
                }

                lsd.p = numberOfFittingCoefficients;
                lsd.x_init = new double[lsd.p];
                lsd.x_init[0] = 0.1; // initial guess for a1
                lsd.x_init[1] = 0.1; // initial guess for a2

                lsd.omegac = transformData_.omegac; // critical frequency
                lsd.dt = simulationData_.print_time_step;
                lsd.tm = transformData_.fitting_start_time;
                lsd.n = 1; // the power of the 1/t^n in the least square model function

                string filename = results_folder_ + '/' + UserInput.project_name + OW3DSeakeeping::least_square_status_file_extension;

                leastSquareFitting(t_n_sine_cosine_f, t_n_sine_cosine_df, t_n_sine_cosine_fdf, lsd, ls_fit_coeffs_rad_[runIndex][respIndex], filename);
                delete[] lsd.y;
                delete[] lsd.sigma;
                delete[] lsd.x_init;
            }
        }
    }
    if (gmodesBodyForces_.size() != 0) // For radition problems
    {
        unsigned int numberOfFittingCoefficients = 2;

        for (unsigned int runIndex = 0; runIndex < UserInput.gmd_runs.size(); runIndex++)
        {
            for (unsigned int respIndex = 0; respIndex < UserInput.responses.size(); respIndex++)
            {
                least_square_data lsd;
                lsd.size = (transformData_.original_signal_length - transformData_.fitting_start_index); // number of data points to be fitted
                lsd.y = new double[lsd.size];
                lsd.sigma = new double[lsd.size];

                for (unsigned int i = 0; i < lsd.size; i++)
                {
                    lsd.sigma[i] = 1.0;                                                                        // the measurement error (standard deviation)
                    lsd.y[i] = gmodesBodyForces_[runIndex](respIndex, transformData_.fitting_start_index + i); // the data points to be fitted
                }

                lsd.p = numberOfFittingCoefficients;
                lsd.x_init = new double[lsd.p];
                lsd.x_init[0] = 0.1; // initial guess for a1
                lsd.x_init[1] = 0.1; // initial guess for a2

                lsd.omegac = transformData_.omegac; // critical frequency
                lsd.dt = simulationData_.print_time_step;
                lsd.tm = transformData_.fitting_start_time;
                lsd.n = 1; // the power of the 1/t^n in the least square model function

                string filename = results_folder_ + '/' + UserInput.project_name + OW3DSeakeeping::least_square_status_file_extension;

                leastSquareFitting(t_n_sine_cosine_f, t_n_sine_cosine_df, t_n_sine_cosine_fdf, lsd, ls_fit_coeffs_gmod_[runIndex][respIndex], filename);
                delete[] lsd.y;
                delete[] lsd.sigma;
                delete[] lsd.x_init;
            }
        }
    }
    if (resistanceBodyForces_.size() != 0) // For wave resistance problem
    {
        unsigned int numberOfFittingCoefficients = 3;

        for (unsigned int runIndex = 0; runIndex < UserInput.res_runs.size(); runIndex++)
        {
            for (unsigned int respIndex = 0; respIndex < UserInput.responses.size(); respIndex++)
            {
                least_square_data lsd;
                lsd.size = (transformData_.original_signal_length - transformData_.fitting_start_index); // number of data points to be fitted
                lsd.y = new double[lsd.size];
                lsd.sigma = new double[lsd.size];

                for (unsigned int i = 0; i < lsd.size; i++)
                {
                    lsd.sigma[i] = 1.0;                                                                            // the measurement error (standard deviation)
                    lsd.y[i] = resistanceBodyForces_[runIndex](respIndex, transformData_.fitting_start_index + i); // the data points to be fitted
                }

                lsd.p = numberOfFittingCoefficients;
                lsd.x_init = new double[lsd.p];
                lsd.x_init[0] = 0.1; // initial guess for a1
                lsd.x_init[1] = 0.1; // initial guess for a2
                lsd.x_init[2] = -11; // initial guess for a2

                lsd.omegac = transformData_.omegac; // critical frequency
                lsd.dt = simulationData_.print_time_step;
                lsd.tm = transformData_.fitting_start_time;
                lsd.n = 1; // the power of the 1/t^n in the least square model function

                string filename = results_folder_ + '/' + UserInput.project_name + OW3DSeakeeping::least_square_status_file_extension;

                leastSquareFitting(t_n_sine_cosine_pc_f, t_n_sine_cosine_pc_df, t_n_sine_cosine_pc_fdf, lsd, ls_fit_coeffs_res_[runIndex][respIndex], filename);
                delete[] lsd.y;
                delete[] lsd.sigma;
                delete[] lsd.x_init;
            }
        }
    }

} // End of calculateAsymptoticContinuation_ private member function
