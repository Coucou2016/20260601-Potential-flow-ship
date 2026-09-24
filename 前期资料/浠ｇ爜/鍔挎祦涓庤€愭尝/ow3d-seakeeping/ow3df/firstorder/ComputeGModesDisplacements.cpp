// This public member function belongs to the FisrtOrderResults class, and just for
// the convenience is written in a seperate file.

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::ComputeGModesDisplacements()
{
    // Define the coordinate for computing sectional displacement

    double x_position = 0; //-1.225;
    const double XLb = gridData_->maximum_body_length;

    double SF_heave = 1.0;
    double SF_pitch = -x_position;
    double xfle = x_position / XLb * 2;
    vector<double> SF_Gmodes(UserInput.number_of_gmodes);
    unsigned int freqs_size = omegao_.size() - allKsAndOmegas_.out_start_index;

    if (gmode_type == GMODE_TYPES::EULERBERNOULLI)
    {
        double WDs[10] = {2.36502, 3.92660, 5.49780, 7.06858, 8.63938, 10.21018, 11.78097, 13.35177, 14.92257, 16.49336}; // Eigenvalues

        for (unsigned int isf = 0; isf < UserInput.number_of_gmodes; isf++)
        {
            if (isf % 2)
            {
                SF_Gmodes[isf] = 0.5 * (sin(WDs[isf] * xfle) / sin(WDs[isf]) + sinh(WDs[isf] * xfle) / sinh(WDs[isf]));
            }
            else
            {
                SF_Gmodes[isf] = 0.5 * (cos(WDs[isf] * xfle) / cos(WDs[isf]) + cosh(WDs[isf] * xfle) / cosh(WDs[isf]));
            }
        }
    }
    else if (gmode_type == GMODE_TYPES::TIMOSHENKO_STRUC || gmode_type == GMODE_TYPES::TIMOSHENKO_STRHY)
    {
        double gamma_Timo = OW3DSeakeeping::gamma_Timo;
        double WD[10];
        if (OW3DSeakeeping::gamma_Timo == 0.042426407)
        {
            double WD_temp[10] = {2.36176, 3.90651, 5.43826, 6.93833, 8.40025, 9.81867, 11.18988, 12.51169, 13.78324, 15.00475};
            for (unsigned int isf = 0; isf < 10; isf++)
            {
                WD[isf] = WD_temp[isf];
            }
        }
        else if (OW3DSeakeeping::gamma_Timo == 0.06)
        {
            double WD_temp[10] = {2.35852, 3.88691, 5.38179, 6.81923, 8.19092, 9.49234, 10.72264, 11.88361, 12.97881, 14.01277};
            for (unsigned int isf = 0; isf < 10; isf++)
            {
                WD[isf] = WD_temp[isf];
            }
        }
        else if (OW3DSeakeeping::gamma_Timo == 0.084852814)
        {
            double WD_temp[10] = {2.35210, 3.84910, 5.27700, 6.60840, 7.83909, 8.97240, 10.01630, 10.98061, 11.87526, 12.70946};
            for (unsigned int isf = 0; isf < 10; isf++)
            {
                WD[isf] = WD_temp[isf];
            }
        }
        else if (OW3DSeakeeping::gamma_Timo == 0.005372616)
        {
            double WD_temp[10] = {2.36497, 3.92628, 5.49682, 7.06640, 8.63527, 10.20326, 11.77020, 13.33593, 14.90028, 16.46309};
            for (unsigned int isf = 0; isf < 10; isf++)
            {
                WD[isf] = WD_temp[isf];
            }
        }
        else if (OW3DSeakeeping::gamma_Timo == 0.00567142)
        {
            double WD_temp[10] = {2.36496, 3.92624, 5.49671, 7.06615, 8.63480, 10.20247, 11.76897, 13.33412, 14.89774, 16.45964};
            for (unsigned int isf = 0; isf < 10; isf++)
            {
                WD[isf] = WD_temp[isf];
            }
        }
        else
        {
            throw runtime_error("Error, OW3DSeakeeping::FirstOrder::ComputeGModesGisplacements.cpp and OW3DSeakeeping::Grid::ComputeGModeShape_.cpp:Please choose a gamma from the given range in OW3DConstants.cpp.");
        }

        double alphaN[10], betaN[10];
        for (unsigned int isf = 0; isf < UserInput.number_of_gmodes; isf++)
        {
            alphaN[isf] = sqrt(0.5 * (sqrt(pow(WD[isf] * gamma_Timo, 4) + 4) + pow(WD[isf] * gamma_Timo, 2))); // Define alpha which is used in Timoshenko beam
            betaN[isf] = sqrt(0.5 * (sqrt(pow(WD[isf] * gamma_Timo, 4) + 4) - pow(WD[isf] * gamma_Timo, 2)));  // Define beta which is used in Timoshenko beam

            if (isf % 2)
            {
                SF_Gmodes[isf] = 1 / (1 + pow(alphaN[isf] / betaN[isf], 2)) * (sin(WD[isf] * alphaN[isf] * xfle) / sin(WD[isf] * alphaN[isf]) + sinh(WD[isf] * betaN[isf] * xfle) / sinh(WD[isf] * betaN[isf]) * pow(alphaN[isf] / betaN[isf], 2));
            }
            else
            {
                SF_Gmodes[isf] = 1 / (1 + pow(alphaN[isf] / betaN[isf], 2)) * (cos(WD[isf] * alphaN[isf] * xfle) / cos(WD[isf] * alphaN[isf]) + cosh(WD[isf] * betaN[isf] * xfle) / cosh(WD[isf] * betaN[isf]) * pow(alphaN[isf] / betaN[isf], 2));
            }
        }
    }

    unsigned int j_counter = 1;
    for (unsigned int f = allKsAndOmegas_.out_start_index; f < omegaeAll_.size(); f++)
    {
        double disp_H_real = 0.0, disp_H_imag = 0.0, disp_P_real = 0.0, disp_P_imag = 0.0, disp_total_real = 0.0, disp_total_imag = 0.0, disp_total = 0.0;
        vector<double> disp_G_real, disp_G_imag;
        disp_G_real.resize(UserInput.number_of_gmodes);
        disp_G_imag.resize(UserInput.number_of_gmodes);

        for (unsigned int s = 0; s < UserInput.responses.size(); s++)
        {
            string i = ModePrintTags.at(UserInput.responses[s]);
            i = (i == ModePrintTags.at(GMODE)) ? to_string(total_number_of_rigid_modes + j_counter++) : i;

            if (RAO_.size() != 0 and UserInput.solve_motion)
            {
                double real_rao = RAO_[s](0, f);
                double imag_rao = RAO_[s](1, f);

                if (UserInput.responses[s] == MODE_NAMES::HEAVE)
                {
                    disp_H_real = real_rao * SF_heave;
                    disp_H_imag = imag_rao * SF_heave;
                }

                if (UserInput.responses[s] == MODE_NAMES::PITCH)
                {
                    disp_P_real = real_rao * SF_pitch;
                    disp_P_imag = imag_rao * SF_pitch;
                }

                if (UserInput.responses[s] == MODE_NAMES::GMODE)
                {
                    disp_G_real[s - UserInput.number_of_rigid_modes] = real_rao * SF_Gmodes[s - UserInput.number_of_rigid_modes];
                    disp_G_imag[s - UserInput.number_of_rigid_modes] = imag_rao * SF_Gmodes[s - UserInput.number_of_rigid_modes];
                }
            }
        }

        disp_total_real = disp_H_real + disp_P_real;
        disp_total_imag = disp_H_imag + disp_P_imag;

        if (UserInput.number_of_gmodes != 0)
        {
            for (unsigned int fs = 0; fs < UserInput.number_of_gmodes; fs++)
            {
                disp_total_real = disp_G_real[fs] + disp_total_real;
                disp_total_imag = disp_G_imag[fs] + disp_total_imag;
            }
        }
        disp_total = sqrt(disp_total_real * disp_total_real + disp_total_imag * disp_total_imag);
        GMDISP_.push_back(disp_total);
    }

    if (UserInput.number_of_gmodes != 0)
        OW3DSeakeeping::PrintLogMessage("Displacements for the gmodes are computed.");
}
