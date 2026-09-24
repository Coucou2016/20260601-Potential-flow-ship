// This public member function belongs to the SecondOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "SecondOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::SecondOrder::ComputeDriftSalvesen()
{
    if (OW3DSeakeeping::UserInput.wave_drift)
    {
        // --------------------------------------------
        // Open the frequency-domain files (phasors)
        // --------------------------------------------

        // NOTE : For the far-field method no incident wave potentials are in the phasors.

        string bodyFile = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_no_incident_binary_file;
        ifstream bfin(bodyFile, ios_base::in | ios_base::binary);
        if (!bfin.is_open())
            throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftSalvesen.cpp: Frequency-domain potential file can not be opened.");

        // ---------------------------------------------
        // Data initializations
        // ----------------------------------------------

        struct comp
        {
            double sym_real;
            double sym_imag;
            double asm_real;
            double asm_imag;
        } cp; // The frequency domain data is stored in this variable.

        vector<double> omegaoVector = allKsAndOmegas_.omegao;
        vector<double> omegaeVector = allKsAndOmegas_.omegae;
        vector<double> koVector = allKsAndOmegas_.ko;
        vector<double> koDeepVector = allKsAndOmegas_.koDeep; // NOTE : Only valid for deep water

        const double cosB = cos(betar_);
        const double sinB = sin(betar_);

        realCompositeGridFunction ScattererIntegrand(*cg_);
        ScattererIntegrand = 0;

        // ---------------------------------------------------
        // Frequency loop (Start calculating the drift force)
        // ---------------------------------------------------

        for (unsigned int f = 0; f < flength_; f++)
        {
            double RwKochin = 0.;                  // The Kochin function part
            double RwScatterer = 0;                // The scatterer part
            const double omegae = omegaeVector[f]; // ENCOUNTER FREQUENCY
            const double omegao = omegaoVector[f]; // WAVE      FREQUENCY
            const double K = koVector[f];          // WAVE NUMBER
            const double KDeep = koDeepVector[f];  // NOTE : Only valid for deep water

            // ------------------------------------------
            // Assign the response amplitude operators.
            // ------------------------------------------

            for (unsigned int run = 0; run < radiation_runs_.size(); run++)
            {
                MODE_NAMES mode_name = radiation_runs_[run].mode;

                if (mode_name == MODE_NAMES::SURGE)
                {
                    xi1_re_ = RAOs_[run](0, f);
                    xi1_im_ = RAOs_[run](1, f);
                }
                else if (mode_name == MODE_NAMES::HEAVE)
                {
                    xi2_re_ = RAOs_[run](0, f);
                    xi2_im_ = RAOs_[run](1, f);
                }
                else if (mode_name == MODE_NAMES::SWAY)
                {
                    xi3_re_ = RAOs_[run](0, f);
                    xi3_im_ = RAOs_[run](1, f);
                }
                else if (mode_name == MODE_NAMES::ROLL)
                {
                    alpha1_re_ = RAOs_[run](0, f);
                    alpha1_im_ = RAOs_[run](1, f);
                }
                else if (mode_name == MODE_NAMES::YAW)
                {
                    alpha2_re_ = RAOs_[run](0, f);
                    alpha2_im_ = RAOs_[run](1, f);
                }
                else if (mode_name == MODE_NAMES::PITCH)
                {
                    alpha3_re_ = RAOs_[run](0, f);
                    alpha3_im_ = RAOs_[run](1, f);
                }
                else
                {
                    throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftSalvesen.cpp: The type of radiation run can not be recognized.");
                }
            }

            // -------------------------------------
            // Loop due to symmetry of the grid.
            // -------------------------------------

            for (unsigned int count = 0; count < numberOFIntegrations_; count++)
            {
                int symSign = (count == 0) ? 1 : -1; // Means integration on the other half of the body

                // ---------------------------------------------------------
                // Body surface loop (to store the complex phasors)
                // ---------------------------------------------------------

                for (unsigned int surface = 0; surface < NES_; surface++)
                {
                    const Single_boundary_data &be = boundariesData_->exciting[surface];
                    const vector<Index> &Is = be.surface_indices;
                    MappedGrid &mg = (*cg_)[be.grid];
                    const RealArray &v = mg.vertex();
                    const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

                    RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
                    RealArray n1(Is[0], Is[1], Is[2]), n2(Is[0], Is[1], Is[2]), n3(Is[0], Is[1], Is[2]);

                    x = v(Is[0], Is[1], Is[2], axis1);
                    y = v(Is[0], Is[1], Is[2], axis2); // Note : "y" vertical up
                    z = 0.0;

                    n1 = vbn(Is[0], Is[1], Is[2], axis1);
                    n2 = vbn(Is[0], Is[1], Is[2], axis2); // Note : "n2" vertical up
                    n3 = 0.;

                    if (gridData_->nod == 3)
                    {
                        z = v(Is[0], Is[1], Is[2], axis3) * symSign;
                        n3 = vbn(Is[0], Is[1], Is[2], axis3) * symSign;
                    }

                    int l1 = Is[1].getLength();
                    int l2 = Is[2].getLength();

                    // ---------------------------------------------
                    // The shift due to the previous surfaces
                    // ---------------------------------------------

                    int surface_shift = 0;

                    for (int back = surface; back > 0; back--)
                    {
                        const Single_boundary_data &sbd = boundariesData_->exciting[back - 1];
                        const vector<Index> &I = sbd.surface_indices;

                        const int bcl0 = I[0].getLength();
                        const int bcl1 = I[1].getLength();
                        const int bcl2 = I[2].getLength();

                        surface_shift += bcl0 * bcl1 * bcl2 * NPOTENS_ * flength_;
                    }

                    // ------------------------------------------------
                    // Loop over the type of the data (phi or grad phi)
                    // Loop over i
                    // Loop over j
                    // Loop over k
                    // ------------------------------------------------

                    for (unsigned int pot = 0; pot < NPOTENS_; pot++)
                    {
                        for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
                        {
                            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
                            {
                                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
                                {
                                    // Note : the data has been stored as [surface][i][j][k][type][f].

                                    const int shift = surface_shift + i * l1 * l2 * NPOTENS_ * flength_ + j * l2 * NPOTENS_ * flength_ + k * NPOTENS_ * flength_ + pot * flength_ + f;

                                    bfin.seekg(shift * (sizeof cp), ios_base::beg);
                                    bfin.read((char *)&cp, sizeof cp);

                                    double real_phasor = 0.;
                                    double imag_phasor = 0.;

                                    real_phasor = cp.sym_real + cp.asm_real * symSign;
                                    imag_phasor = cp.sym_imag + cp.asm_imag * symSign;

                                    // Set the ComplexArrays

                                    if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHI)
                                    {
                                        phi_(0)[surface](i, j, k) = real_phasor;
                                        phi_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIX)
                                    {
                                        d_phi_dx_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dx_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIY)
                                    {
                                        d_phi_dy_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dy_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZ)
                                    {
                                        d_phi_dz_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dz_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXX)
                                    {
                                        d_phi_dxx_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dxx_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIYY)
                                    {
                                        d_phi_dyy_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dyy_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZZ)
                                    {
                                        d_phi_dzz_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dzz_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXY)
                                    {
                                        d_phi_dxy_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dxy_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIXZ)
                                    {
                                        d_phi_dxz_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dxz_(1)[surface](i, j, k) = imag_phasor;
                                    }
                                    else // (pot==9)
                                    {
                                        d_phi_dyz_(0)[surface](i, j, k) = real_phasor;
                                        d_phi_dyz_(1)[surface](i, j, k) = imag_phasor;
                                    }

                                } // k

                            } // j

                        } // i

                    } // End of data type loop

                    ScattererIntegrand[be.grid](Is[0], Is[1], Is[2]) =
                        phi_(0)[surface] * (n1 * d_phi_dxx_(0)[surface] + n2 * d_phi_dxy_(0)[surface] + n3 * d_phi_dxz_(0)[surface]) +
                        phi_(1)[surface] * (n1 * d_phi_dxx_(1)[surface] + n2 * d_phi_dxy_(1)[surface] + n3 * d_phi_dxz_(1)[surface]) -
                        (d_phi_dx_(0)[surface] * (n1 * d_phi_dx_(0)[surface] + n2 * d_phi_dy_(0)[surface] + n3 * d_phi_dz_(0)[surface]) +
                         d_phi_dx_(1)[surface] * (n1 * d_phi_dx_(1)[surface] + n2 * d_phi_dy_(1)[surface] + n3 * d_phi_dz_(1)[surface]));

                } // End body surface loop

                // ----------------------------------------------------------------------------------------
                //  NOTE : dphi_dn_ private member function is assigned by calling the following function.
                // ----------------------------------------------------------------------------------------
                ComputeDphiDnOnBody_(omegae, omegao, K, symSign);
                double H[2];
                H[0] = 0., H[1] = 0.;
                ComputeKochinFunction_(symSign, KDeep, KDeep * cosB, KDeep * sinB, H); // NOTE : Results are stored in H[0] (real) and H[1] (imaginary)
                RwKochin += H[0];
                RwScatterer += ComputeSurfaceIntegral(integrator_, gridData_->triangulation,ScattererIntegrand);

            } // End integrals count loop

            forces_salvesen_(0, f) = -(0.5 * rho_ * g_ * KDeep * cosB) / omegao * RwKochin - 1. / 4 * rho_ * RwScatterer;

            // Note : the drift forces are stored in the array as follows:
            //
            // axis 0 ---> :  (0)
            //
            // axis 1 ( 0)     o
            // axis 1 ( 1)     o
            // axis 1 ( 2)     o
            // axis 1 ( 3)     o
            // axis 1 ( 4)     o
            // axis 1 ( 5)     o
            // ......          ...
            //
            // length of axis1 = number of frequencies
            // length of axix0 = 1 ( Just the resistance force )

        } // End of frequency loop

        bfin.close();

        PrintLogMessage("Salvesen wave drift force computed.");

    } // End of wave drift check

} // End of the function.
