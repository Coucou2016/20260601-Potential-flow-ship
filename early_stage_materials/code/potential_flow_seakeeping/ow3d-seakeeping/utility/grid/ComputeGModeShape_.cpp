#include "Grid.h"
#include "OW3DConstants.h"

int OW3DSeakeeping::Grid::ComputeGModeShape_()
{
    if (UserInput.number_of_gmodes != 0)
    {
        VRealArrays X, Y, Z;
        VRealArrays n1, n2, n3;
        VRealArrays flex_vbn, flex_disp, flex_disp_der, flex_vbn2, flex_disp2, flex_disp2_der;

        X.allresize(gridData_.boundariesData);
        Y.allresize(gridData_.boundariesData);
        Z.allresize(gridData_.boundariesData);
        n1.allresize(gridData_.boundariesData);
        n2.allresize(gridData_.boundariesData);
        n3.allresize(gridData_.boundariesData);

        flex_vbn.allresize(gridData_.boundariesData);
        flex_disp.allresize(gridData_.boundariesData);
        flex_vbn2.allresize(gridData_.boundariesData);
        flex_disp2.allresize(gridData_.boundariesData);

        gridData_.flexmodes.resize(UserInput.number_of_gmodes);

        for (unsigned int i = 0; i < UserInput.number_of_gmodes; i++)
        {
            gridData_.flexmodes[i].flex_vbn.allresize(gridData_.boundariesData);
            gridData_.flexmodes[i].flex_disp.allresize(gridData_.boundariesData);
            gridData_.flexmodes[i].flex_disp_der.allresize(gridData_.boundariesData);
        }

        unsigned int noes_ = gridData_.boundariesData.exciting.size();

        for (unsigned int surface = 0; surface < noes_; surface++)
        {
            const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
            const MappedGrid &mg = cg_[be.grid];
            const RealArray &v = mg.vertex();
            const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);
            const vector<Index> &Is = be.surface_indices;

            // store the body surface coordinates

            X[surface] = v(Is[0], Is[1], Is[2], axis1);
            Y[surface] = v(Is[0], Is[1], Is[2], axis2);
            Z[surface] = 0.0;
            flex_vbn[surface] = 0.0;
            flex_disp[surface] = 0.0;
            flex_vbn2[surface] = 0.0;
            flex_disp2[surface] = 0.0;

            for (unsigned int kk = 0; kk < UserInput.number_of_gmodes; kk++)
            {
                gridData_.flexmodes[kk].flex_vbn[surface] = 1.0;
                gridData_.flexmodes[kk].flex_disp[surface] = 1.0;
                gridData_.flexmodes[kk].flex_disp_der[surface] = 1.0;
            }

            // Store the body outward normal vector:
            n1[surface] = vbn(Is[0], Is[1], Is[2], axis1);
            n2[surface] = vbn(Is[0], Is[1], Is[2], axis2);
            n3[surface] = 0.0;

            if (gridData_.nod == 3)
            {
                Z[surface] = v(Is[0], Is[1], Is[2], axis3);
                n3[surface] = vbn(Is[0], Is[1], Is[2], axis3);
            }

            int lnt0 = X[surface].getLength(0);
            int lnt1 = X[surface].getLength(1);
            int lnt2 = X[surface].getLength(2);

            if (gmode_type == GMODE_TYPES::EULERBERNOULLI)
            {
                const double XL = gridData_.maximum_body_length;                                                                 // Barge length
                double WD[10] = {2.36502, 3.92660, 5.49780, 7.06858, 8.63938, 10.21018, 11.78097, 13.35177, 14.92257, 16.49336}; // Eigenvalues
                                                                                                                                 // double WD[2] = {8.035, 15.400};

                for (unsigned int mode_index = 0; mode_index < UserInput.number_of_gmodes; mode_index++)
                {
                    for (int i0 = 0; i0 < lnt0; i0++)
                    {
                        for (int i1 = 0; i1 < lnt1; i1++)
                        {
                            for (int i2 = 0; i2 < lnt2; i2++)
                            {
                                double XI[3] = {X[surface](i0, i1, i2), Y[surface](i0, i1, i2), Z[surface](i0, i1, i2)};    // Coordinate of patch
                                double XN[3] = {n1[surface](i0, i1, i2), n2[surface](i0, i1, i2), n3[surface](i0, i1, i2)}; // corresponding normal vector
                                double XI1 = 2.0 * XI[0] / XL;                                                              // Transform (make x-coordinate dimensionless relative to halft-length of barge)
                                // double XI1 = XI[0] / XL;

                                if (mode_index % 2)
                                {
                                    double b = 0.5 * (sin(WD[mode_index] * XI1) / sin(WD[mode_index]) + sinh(WD[mode_index] * XI1) / sinh(WD[mode_index]));
                                    double b_der = 0.5 * WD[mode_index] * (cos(WD[mode_index] * XI1) / sin(WD[mode_index]) + cosh(WD[mode_index] * XI1) / sinh(WD[mode_index]));
                                    gridData_.flexmodes[mode_index].flex_disp[surface](i0, i1, i2) = 1 * b;
                                    gridData_.flexmodes[mode_index].flex_vbn[surface](i0, i1, i2) = 1 * b * XN[1];
                                    gridData_.flexmodes[mode_index].flex_disp_der[surface](i0, i1, i2) = 1 * b_der;
                                }
                                else
                                {
                                    double a = 0.5 * (cos(WD[mode_index] * XI1) / cos(WD[mode_index]) + cosh(WD[mode_index] * XI1) / cosh(WD[mode_index]));
                                    double a_der = -0.5 * WD[mode_index] * (sin(WD[mode_index] * XI1) / cos(WD[mode_index]) + sinh(WD[mode_index] * XI1) / cosh(WD[mode_index]));
                                    gridData_.flexmodes[mode_index].flex_disp[surface](i0, i1, i2) = 1 * a;
                                    gridData_.flexmodes[mode_index].flex_vbn[surface](i0, i1, i2) = 1 * a * XN[1];
                                }
                            }
                        }

                    } // End of geometry loop.

                } // End newmds-for loop over noofmodes

            } // End newmds-if loop

            else if (gmode_type == GMODE_TYPES::TIMOSHENKO_STRHY || gmode_type == GMODE_TYPES::TIMOSHENKO_STRUC)
            {
                double gamma_Timo = OW3DSeakeeping::gamma_Timo; //  Get gamma from input file
                const double XL = gridData_.maximum_body_length;
                double WD[10];
                if (OW3DSeakeeping::gamma_Timo == 0.042426407)
                {
                    double WD_temp[10] = {2.36176, 3.90651, 5.43826, 6.93833, 8.40025, 9.81867, 11.18988, 12.51169, 13.78324, 15.00475}; // Eigenvalues
                    for (unsigned int WD_index = 0; WD_index < 10; WD_index++)
                    {
                        WD[WD_index] = WD_temp[WD_index];
                    }
                }
                else if (OW3DSeakeeping::gamma_Timo == 0.06)
                {
                    double WD_temp[10] = {2.35852, 3.88691, 5.38179, 6.81923, 8.19092, 9.49234, 10.72264, 11.88361, 12.97881, 14.01277}; // Eigenvalues
                    for (unsigned int WD_index = 0; WD_index < 10; WD_index++)
                    {
                        WD[WD_index] = WD_temp[WD_index];
                    }
                }
                else if (OW3DSeakeeping::gamma_Timo == 0.084852814) // gammma^2 == 0.0072
                {
                    double WD_temp[10] = {2.35210, 3.84910, 5.27700, 6.60840, 7.83909, 8.97240, 10.01630, 10.98061, 11.87526, 12.70946}; // Eigenvalues
                    for (unsigned int WD_index = 0; WD_index < 10; WD_index++)
                    {
                        WD[WD_index] = WD_temp[WD_index];
                    }
                }

                else if (OW3DSeakeeping::gamma_Timo == 0.005372616) // 4mm case using Timoshenko beam model
                {
                    double WD_temp[10] = {2.36497, 3.92628, 5.49682, 7.06640, 8.63527, 10.20326, 11.77020, 13.33593, 14.90028, 16.46309}; // Eigenvalues
                    for (unsigned int WD_index = 0; WD_index < 10; WD_index++)
                    {
                        WD[WD_index] = WD_temp[WD_index];
                    }
                }
                else if (OW3DSeakeeping::gamma_Timo == 0.00567142) // 6mm case using Timoshenko beam model
                {
                    double WD_temp[10] = {2.36496, 3.92624, 5.49671, 7.06615, 8.63480, 10.20247, 11.76897, 13.33412, 14.89774, 16.45964}; // Eigenvalues
                    for (unsigned int WD_index = 0; WD_index < 10; WD_index++)
                    {
                        WD[WD_index] = WD_temp[WD_index];
                    }
                }
                // Barge length

                double alphaN[10],
                    betaN[10];
                for (unsigned int mode_flex_index = 0; mode_flex_index < 10; mode_flex_index++)
                {
                    alphaN[mode_flex_index] = sqrt(0.5 * (sqrt(pow(WD[mode_flex_index] * gamma_Timo, 4) + 4) + pow(WD[mode_flex_index] * gamma_Timo, 2))); // Define alpha which is used in Timoshenko beam
                    betaN[mode_flex_index] = sqrt(0.5 * (sqrt(pow(WD[mode_flex_index] * gamma_Timo, 4) + 4) - pow(WD[mode_flex_index] * gamma_Timo, 2)));  // Define beta which is used in Timoshenko beam
                }

                for (unsigned int mode_index = 0; mode_index < UserInput.number_of_gmodes; mode_index++)
                {
                    for (int i0 = 0; i0 < lnt0; i0++)
                    {
                        for (int i1 = 0; i1 < lnt1; i1++)
                        {
                            for (int i2 = 0; i2 < lnt2; i2++)
                            {
                                double XI[3] = {X[surface](i0, i1, i2), Y[surface](i0, i1, i2), Z[surface](i0, i1, i2)};    // Coordinate of patch
                                double XN[3] = {n1[surface](i0, i1, i2), n2[surface](i0, i1, i2), n3[surface](i0, i1, i2)}; // corresponding normal vector
                                double XI1 = 2.0 * XI[0] / XL;                                                              // Transform (make x-coordinate dimensionless relative to halft-length of barge)
                                // double XI1 = XI[0] / XL;

                                if (mode_index % 2)
                                {
                                    double b = 1 / (1 + pow(alphaN[mode_index] / betaN[mode_index], 2)) * (sin(WD[mode_index] * alphaN[mode_index] * XI1) / sin(WD[mode_index] * alphaN[mode_index]) + sinh(WD[mode_index] * betaN[mode_index] * XI1) / sinh(WD[mode_index] * betaN[mode_index]) * pow(alphaN[mode_index] / betaN[mode_index], 2));
                                    double b_der = 1 / (1 + pow(alphaN[mode_index] / betaN[mode_index], 2)) * WD[mode_index] * (alphaN[mode_index] * cos(WD[mode_index] * alphaN[mode_index] * XI1) / sin(WD[mode_index] * alphaN[mode_index]) + betaN[mode_index] * cosh(WD[mode_index] * betaN[mode_index] * XI1) / sinh(WD[mode_index] * betaN[mode_index]) * pow(alphaN[mode_index] / betaN[mode_index], 2));
                                    gridData_.flexmodes[mode_index].flex_disp[surface](i0, i1, i2) = 1 * b;
                                    gridData_.flexmodes[mode_index].flex_vbn[surface](i0, i1, i2) = 1 * b * XN[1];
                                    gridData_.flexmodes[mode_index].flex_disp_der[surface](i0, i1, i2) = 1 * b_der;
                                }
                                else
                                {
                                    double a = 1 / (1 + pow(alphaN[mode_index] / betaN[mode_index], 2)) * (cos(WD[mode_index] * alphaN[mode_index] * XI1) / cos(WD[mode_index] * alphaN[mode_index]) + cosh(WD[mode_index] * betaN[mode_index] * XI1) / cosh(WD[mode_index] * betaN[mode_index]) * pow(alphaN[mode_index] / betaN[mode_index], 2));
                                    double a_der = -1 / (1 + pow(alphaN[mode_index] / betaN[mode_index], 2)) * WD[mode_index] * (alphaN[mode_index] * sin(WD[mode_index] * alphaN[mode_index] * XI1) / cos(WD[mode_index] * alphaN[mode_index]) + betaN[mode_index] * sinh(WD[mode_index] * betaN[mode_index] * XI1) / cosh(WD[mode_index] * betaN[mode_index]) * pow(alphaN[mode_index] / betaN[mode_index], 2));
                                    gridData_.flexmodes[mode_index].flex_disp[surface](i0, i1, i2) = 1 * a;
                                    gridData_.flexmodes[mode_index].flex_vbn[surface](i0, i1, i2) = 1 * a * XN[1];
                                }
                            }
                        }
                    }
                }
            }

        } // End surface-for loop
    }

    return 0;
}
