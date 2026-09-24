// This public member function belongs to the SecondOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "SecondOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::SecondOrder::ComputeWaveDriftForces()
{
    if (OW3DSeakeeping::UserInput.wave_drift)
    {
        RealArray first_integrand;     //
        RealArray second_integrand_re; //
        RealArray second_integrand_im; // These variables are used
        RealArray third_integrand;     // for calculation of
        RealArray fourth_integrand_re; // the body integral parts
        RealArray fourth_integrand_im; // of the wave drift force
        RealArray fifth_integrand;     //
        RealArray sixth_integrand;     //

        realCompositeGridFunction x_force_integrand(*cg_);
        x_force_integrand = 0.;

        vector<double> dls;    // The segment length for the waterline
        vector<double> etap_0; // To store each waterline contribution (SURGE, SWAY , YAW)
        struct comp
        {
            double sym_real;
            double sym_imag;
            double asm_real;
            double asm_imag;

        } cp; // Wterline frequency domain data is stored in this variable.

        // Following are used for intgeration on other half of the geometry
        realCompositeGridFunction mir_base_dz = base_dz_;
        realCompositeGridFunction mir_base_dxz = base_dxz_;
        realCompositeGridFunction mir_base_dyz = base_dyz_;

        for (unsigned int f = 0; f < flength_; f++)
        {
            ComputePotentialsDerivatives_(f);

            const double omegae = allKsAndOmegas_.omegae[f];

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
            }

            for (unsigned int count = 0; count < numberOFIntegrations_; count++)
            {
                int side = (count == 0) ? 1 : -1; // Means integration on the other half of the body

                mir_base_dz = side * base_dz_;
                mir_base_dxz = side * base_dxz_;
                mir_base_dyz = side * base_dyz_;

                phi_ = sym_phi_ + asm_phi_ * side;
                d_phi_dz_ = sym_d_phi_dz_ + asm_d_phi_dz_ * side;
                d_phi_dxz_ = sym_d_phi_dxz_ + asm_d_phi_dxz_ * side;
                d_phi_dyz_ = sym_d_phi_dyz_ + asm_d_phi_dyz_ * side;

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
                    z = (gridData_->nod == 2) ? 0. * x : v(Is[0], Is[1], Is[2], axis3) * side;
                    n1 = vbn(Is[0], Is[1], Is[2], axis1);
                    n2 = vbn(Is[0], Is[1], Is[2], axis2); // Note : "n2" vertical up
                    n3 = (gridData_->nod == 2) ? 0. * n1 : vbn(Is[0], Is[1], Is[2], axis3) * side;

                    int l0 = Is[0].getLength();
                    int l1 = Is[1].getLength();
                    int l2 = Is[2].getLength();

                    first_integrand.resize(l0, l1, l2), first_integrand = 0.;
                    second_integrand_re.resize(l0, l1, l2), second_integrand_re = 0.;
                    second_integrand_im.resize(l0, l1, l2), second_integrand_im = 0.;
                    third_integrand.resize(l0, l1, l2), third_integrand = 0.;
                    fourth_integrand_re.resize(l0, l1, l2), fourth_integrand_re = 0.;
                    fourth_integrand_im.resize(l0, l1, l2), fourth_integrand_im = 0.;
                    fifth_integrand.resize(l0, l1, l2), fifth_integrand = 0.;
                    sixth_integrand.resize(l0, l1, l2), sixth_integrand = 0.;

                    // (grad(phiu))^2. Note : "1/2" is for the complex number operation
                    first_integrand =
                        1. / 2 *
                        (d_phi_dx_(0)[surface] * d_phi_dx_(0)[surface] + d_phi_dx_(1)[surface] * d_phi_dx_(1)[surface] +
                         d_phi_dy_(0)[surface] * d_phi_dy_(0)[surface] + d_phi_dy_(1)[surface] * d_phi_dy_(1)[surface] +
                         d_phi_dz_(0)[surface] * d_phi_dz_(0)[surface] + d_phi_dz_(1)[surface] * d_phi_dz_(1)[surface]);

                    // real{ dphiu/dt - U*dphiu/dx + grad(phiu).grad(phib) }
                    second_integrand_re = (-omegae * phi_(1)[surface] - U_ * d_phi_dx_(0)[surface] +
                                           d_phi_dx_(0)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                                           d_phi_dy_(0)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                                           d_phi_dz_(0)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]));

                    // imag{ dphiu/dt - U*dphiu/dx + grad(phiu).grad(phib) }
                    second_integrand_im = (omegae * phi_(0)[surface] - U_ * d_phi_dx_(1)[surface] +
                                           d_phi_dx_(1)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                                           d_phi_dy_(1)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                                           d_phi_dz_(1)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]));

                    // (xi + alpha * r) . grad ( dphi/dt - U*dphiu/dx + grad(phiu).grad(phib) )
                    //
                    // ( xi1 + alpha2*z - alpha3*y ) * d/dx( dphi/dt - U*dphiu/dx + grad(phiu).grad(phib) ) +
                    // ( xi2 - alpha1*z + alpha3*x ) * d/dy( dphi/dt - U*dphiu/dx + grad(phiu).grad(phib) ) +
                    // ( xi3 + alpha1*y - alpha2*x ) * d/dz( dphi/dt - U*dphiu/dx + grad(phiu).grad(phib) )
                    //   Note : "1/2" is required for the complex number operation
                    third_integrand =
                        1. / 2 *
                        // x
                        ((xi1_re_ + alpha2_re_ * z - alpha3_re_ * y) *
                             (-omegae * d_phi_dx_(1)[surface] - U_ * d_phi_dxx_(0)[surface] +
                              d_phi_dxx_(0)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dx_(0)[surface] * base_dxx_[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dxy_(0)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dy_(0)[surface] * base_dxy_[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dxz_(0)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]) + d_phi_dz_(0)[surface] * mir_base_dxz[be.grid](Is[0], Is[1], Is[2])) +
                         (xi1_im_ + alpha2_im_ * z - alpha3_im_ * y) *
                             (omegae * d_phi_dx_(0)[surface] - U_ * d_phi_dxx_(1)[surface] +
                              d_phi_dxx_(1)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dx_(1)[surface] * base_dxx_[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dxy_(1)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dy_(1)[surface] * base_dxy_[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dxz_(1)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]) + d_phi_dz_(1)[surface] * mir_base_dxz[be.grid](Is[0], Is[1], Is[2])) +
                         // y
                         (xi2_re_ - alpha1_re_ * z + alpha3_re_ * x) *
                             (-omegae * d_phi_dy_(1)[surface] - U_ * d_phi_dxy_(0)[surface] +
                              d_phi_dxy_(0)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dx_(0)[surface] * base_dxy_[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dyy_(0)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dy_(0)[surface] * base_dyy_[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dyz_(0)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]) + d_phi_dz_(0)[surface] * mir_base_dyz[be.grid](Is[0], Is[1], Is[2])) +
                         (xi2_im_ - alpha1_im_ * z + alpha3_im_ * x) *
                             (omegae * d_phi_dy_(0)[surface] - U_ * d_phi_dxy_(1)[surface] +
                              d_phi_dxy_(1)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dx_(1)[surface] * base_dxy_[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dyy_(1)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dy_(1)[surface] * base_dyy_[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dyz_(1)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]) + d_phi_dz_(1)[surface] * mir_base_dyz[be.grid](Is[0], Is[1], Is[2])) +
                         // z
                         (xi3_re_ + alpha1_re_ * y - alpha2_re_ * x) *
                             (-omegae * d_phi_dz_(1)[surface] - U_ * d_phi_dxz_(0)[surface] +
                              d_phi_dxz_(0)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dx_(0)[surface] * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dyz_(0)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dy_(0)[surface] * mir_base_dyz[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dzz_(0)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]) + d_phi_dz_(0)[surface] * base_dzz_[be.grid](Is[0], Is[1], Is[2])) +
                         (xi3_im_ + alpha1_im_ * y - alpha2_im_ * x) *
                             (omegae * d_phi_dz_(0)[surface] - U_ * d_phi_dxz_(1)[surface] +
                              d_phi_dxz_(1)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dx_(1)[surface] * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dyz_(1)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) + d_phi_dy_(1)[surface] * mir_base_dyz[be.grid](Is[0], Is[1], Is[2]) +
                              d_phi_dzz_(1)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]) + d_phi_dz_(1)[surface] * base_dzz_[be.grid](Is[0], Is[1], Is[2])));

                    // real{ (xi + alpha * r) . grad( -U*dphib/dx + 1/2*grad(phib).grad(phib) + g*z) }
                    //
                    // ( xi1 + alpha2*z - alpha3*y ) * d/dx ( -U*dphib/dx + 1/2*grad(phib).grad(phib) )+
                    // ( xi2 - alpha1*z + alpha3*x ) * d/dy ( -U*dphib/dx + 1/2*grad(phib).grad(phib) )+
                    // ( xi3 + alpha1*y - alpha2*x ) * d/dz ( -U*dphib/dx + 1/2*grad(phib).grad(phib) )
                    //
                    fourth_integrand_re =
                        (xi1_re_ + alpha2_re_ * z - alpha3_re_ * y) *
                            (-U_ * base_dxx_[be.grid](Is[0], Is[1], Is[2]) +
                             1. / 2 *
                                 (2 * base_dxx_[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * base_dxy_[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2]))) +
                        (xi2_re_ - alpha1_re_ * z + alpha3_re_ * x) *
                            (-U_ * base_dxy_[be.grid](Is[0], Is[1], Is[2]) +
                             1. / 2 *
                                 (2 * base_dxy_[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * base_dyy_[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * mir_base_dyz[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2])) +
                             g_) +
                        (xi3_re_ + alpha1_re_ * y - alpha2_re_ * x) *
                            (-U_ * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) +
                             1. / 2 *
                                 (2 * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * mir_base_dyz[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * base_dzz_[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2])));

                    // imag{ (xi + alpha * r) . grad( -U*dphib/dx + 1/2*grad(phib).grad(phib) + g*y) }
                    //
                    // ( xi1 + alpha2*z - alpha3*y ) * d/dx ( -U*dphib/dx + 1/2*grad(phib).grad(phib) )+
                    // ( xi2 - alpha1*z + alpha3*x ) * d/dy ( -U*dphib/dx + 1/2*grad(phib).grad(phib) )+
                    // ( xi3 + alpha1*y - alpha2*x ) * d/dz ( -U*dphib/dx + 1/2*grad(phib).grad(phib) )
                    //
                    fourth_integrand_im =
                        (xi1_im_ + alpha2_im_ * z - alpha3_im_ * y) *
                            (-U_ * base_dxx_[be.grid](Is[0], Is[1], Is[2]) +
                             1. / 2 *
                                 (2 * base_dxx_[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * base_dxy_[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2]))) +
                        (xi2_im_ - alpha1_im_ * z + alpha3_im_ * x) *
                            (-U_ * base_dxy_[be.grid](Is[0], Is[1], Is[2]) +
                             1. / 2 *
                                 (2 * base_dxy_[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * base_dyy_[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * mir_base_dyz[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2])) +
                             g_) +
                        (xi3_im_ + alpha1_im_ * y - alpha2_im_ * x) *
                            (-U_ * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) +
                             1. / 2 *
                                 (2 * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * mir_base_dyz[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                                  2 * base_dzz_[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2])));

                    // ( -U*dphib/dx + 1/2*grad(phib) . grad(phib) + g*y)
                    //
                    fifth_integrand =
                        -U_ * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                        1. / 2 *
                            (pow(base_dx_[be.grid](Is[0], Is[1], Is[2]), 2) +
                             pow(base_dy_[be.grid](Is[0], Is[1], Is[2]), 2) +
                             pow(mir_base_dz[be.grid](Is[0], Is[1], Is[2]), 2)) +
                        g_ * y;

                    // grad ( -U*dphib/dx + 1/2*grad(phib) . grad(phib) + g*y) . [H][r]
                    //
                    sixth_integrand =
                        (-U_ * base_dxx_[be.grid](Is[0], Is[1], Is[2]) +
                         1. / 2 *
                             (2 * base_dxx_[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                              2 * base_dxy_[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                              2 * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2])))
                            // Note : "1/2" is required becuase of the complex number operation
                            * (-1. / 2 * 1. / 2 * (alpha2_re_ * alpha2_re_ + alpha2_im_ * alpha2_im_ + alpha3_re_ * alpha3_re_ + alpha3_im_ * alpha3_im_) * x) +
                        (-U_ * base_dxy_[be.grid](Is[0], Is[1], Is[2]) +
                         1. / 2 *
                             (2 * base_dxy_[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                              2 * base_dyy_[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                              2 * mir_base_dyz[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2])) +
                         g_)
                            // Note : "1/2" is required because of the complex number operation
                            * (1. / 2 * (alpha1_re_ * alpha2_re_ + alpha1_im_ * alpha2_im_) * x +
                               1. / 2 * (alpha3_re_ * alpha2_re_ + alpha3_im_ * alpha2_im_) * z -
                               1. / 2 * 1. / 2 * (alpha1_re_ * alpha1_re_ + alpha1_im_ * alpha1_im_ + alpha3_re_ * alpha3_re_ + alpha3_im_ * alpha3_im_) * y) +
                        (-U_ * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) +
                         1. / 2 *
                             (2 * mir_base_dxz[be.grid](Is[0], Is[1], Is[2]) * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
                              2 * mir_base_dyz[be.grid](Is[0], Is[1], Is[2]) * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
                              2 * base_dzz_[be.grid](Is[0], Is[1], Is[2]) * mir_base_dz[be.grid](Is[0], Is[1], Is[2])))
                            // Note : "1/2" is required because of the complex number operation
                            * (1. / 2 * (alpha1_re_ * alpha3_re_ + alpha1_im_ * alpha3_im_) * x -
                               1. / 2 * 1. / 2 * (alpha1_re_ * alpha1_re_ + alpha1_im_ * alpha1_im_ + alpha2_re_ * alpha2_re_ + alpha2_im_ * alpha2_im_) * z);

                    x_force_integrand[be.grid](Is[0], Is[1], Is[2]) =
                        // -1/2 * rho * ( grad(phiu) )^2 * n1
                        -1. / 2 * rho_ * first_integrand * n1
                        // -rho * ( dphiu/dt - U*dphiu/dx + grad(phiu) . grad(phib) ) * (alpha2*n3 - alpha3*n2). Note, "1/2" for the complex number operation
                        - rho_ * 1. / 2 * (second_integrand_re * (alpha2_re_ * n3 - alpha3_re_ * n2) + second_integrand_im * (alpha2_im_ * n3 - alpha3_im_ * n2))
                        // -rho *  (xi + alpha * r) . grad ( dphi/dt - U*dphiu/dx + grad(phiu) . grad(phib) ) * n1
                        - rho_ * third_integrand * n1
                        // -rho * (xi + alpha * r) . grad(-U*dphib/dx + 1/2*grad(phib) . grad(phib)) * (alpha2*n3 - alpha3*n2). Note, "1/2" for the complex number operation
                        - rho_ * 1. / 2 * (fourth_integrand_re * (alpha2_re_ * n3 - alpha3_re_ * n2) + fourth_integrand_im * (alpha2_im_ * n3 - alpha3_im_ * n2))
                        // -rho * ( -U*dphib/dx + 1/2*grad(phib) . grad(phib) ) * ( -1/2(alpha2^2 + alpha3^2) ) * n1. Note, "1/2" for the complex number operation
                        - rho_ * fifth_integrand * -1. / 2 * (1. / 2 * (alpha2_re_ * alpha2_re_ + alpha2_im_ * alpha2_im_ + alpha3_re_ * alpha3_re_ + alpha3_im_ * alpha3_im_)) * n1
                        // -rho * d/dx ( -U*dphib/dx + 1/2*grad(phib) . grad(phib) ) * ( -(alpha2*alpha2 + alpha3*alpha3) ) * x * n1
                        - rho_ * sixth_integrand * n1;

                } // Body surface

                // Waterline contribution

                double drift_wline_0 = 0.;

                for (unsigned int line = 0; line < wlData_.size(); line++)
                {
                    etap_0.clear(); // MUST BE CLEARED, SO THEY ARE READY FOR THE NEXT WATERLINE DATA.
                    dls.clear();    // MUST BE CLEARED, SO THEY ARE READY FOR THE NEXT WATERLINE DATA.

                    int lines_shift = 0;

                    for (int back = line; back > 0; back--)
                    {
                        lines_shift += wlData_[back - 1].size * flength_; // The shift due to the previous water lines
                    }

                    unsigned int wlength = wlData_[line].size; // Number of grid points on this section of water line

                    int grid = wlData_[line].grid;

                    // --------------------------------
                    //
                    // Loop over water line points
                    //
                    // --------------------------------

                    for (unsigned int i = 0; i < wlength; i++) // Loop over waterline points
                    {
                        // NOTE : waterline phasors are saved as : [line][i][f]

                        int shift = lines_shift + i * flength_ + f;

                        const double x = wlData_[line].x[i];
                        const double z = wlData_[line].z[i] * side;
                        const double y = 0.;

                        wline_fin_.seekg(shift * (sizeof cp), ios_base::beg);
                        wline_fin_.read((char *)&cp, sizeof cp);

                        double eta_real = 0.;
                        double eta_imag = 0.;

                        eta_real = cp.sym_real + cp.asm_real * side;
                        eta_imag = cp.sym_imag + cp.asm_imag * side;

                        // Extract the base-flow data at the waterline

                        double base_dx = 0., base_dz = 0.;
                        double base_dxx = 0., base_dxz = 0.;
                        double base_dzz = 0.;

                        if (wlData_[line].direction == 0)
                        {
                            base_dx = base_dx_[grid](i, wlData_[line].I1.getBase(), wlData_[line].I2.getBase());
                            base_dz = mir_base_dz[grid](i, wlData_[line].I1.getBase(), wlData_[line].I2.getBase());
                            base_dxx = base_dxx_[grid](i, wlData_[line].I1.getBase(), wlData_[line].I2.getBase());
                            base_dxz = mir_base_dxz[grid](i, wlData_[line].I1.getBase(), wlData_[line].I2.getBase());
                            base_dzz = base_dzz_[grid](i, wlData_[line].I1.getBase(), wlData_[line].I2.getBase());
                        }
                        else if (wlData_[line].direction == 1)
                        {
                            base_dx = base_dx_[grid](wlData_[line].I0.getBase(), i, wlData_[line].I2.getBase());
                            base_dz = mir_base_dz[grid](wlData_[line].I0.getBase(), i, wlData_[line].I2.getBase());
                            base_dxx = base_dxx_[grid](wlData_[line].I0.getBase(), i, wlData_[line].I2.getBase());
                            base_dxz = mir_base_dxz[grid](wlData_[line].I0.getBase(), i, wlData_[line].I2.getBase());
                            base_dzz = base_dzz_[grid](wlData_[line].I0.getBase(), i, wlData_[line].I2.getBase());
                        }
                        else
                        {
                            base_dx = base_dx_[grid](wlData_[line].I0.getBase(), wlData_[line].I1.getBase(), i);
                            base_dz = mir_base_dz[grid](wlData_[line].I0.getBase(), wlData_[line].I1.getBase(), i);
                            base_dxx = base_dxx_[grid](wlData_[line].I0.getBase(), wlData_[line].I1.getBase(), i);
                            base_dxz = mir_base_dxz[grid](wlData_[line].I0.getBase(), wlData_[line].I1.getBase(), i);
                            base_dzz = base_dzz_[grid](wlData_[line].I0.getBase(), wlData_[line].I1.getBase(), i);
                        }

                        // force = 0.5*rho*g ( [ eta - (xi2 + x*alpha3 - z*alpha1) ]^2 ) * n
                        //            -rho   ( (xi + alpha * r).grad( -U*dphib/dx + 1/2*(grad(phib))^2) * eta) * n -
                        //            -rho   ( ( -U*dphib/dx + 1/2*(grad(phib))^2) * [eta - (xi2 + x*alpha3 - z*alpha1)] * (alpha * n) )
                        // Note : "1/2" is required for complex number operations

                        if (wlData_[line].mask[i] > 0)
                        {
                            double n1 = wlData_[line].n1[i];
                            double n2 = wlData_[line].n2[i];
                            double n3 = wlData_[line].n3[i];
                            double MotionReal1 = xi1_re_ + z * alpha2_re_ - y * alpha3_re_;
                            double MotionImag1 = xi1_im_ + z * alpha2_im_ - y * alpha3_im_;
                            double MotionReal3 = xi3_re_ + y * alpha1_re_ - x * alpha2_re_;
                            double MotionImag3 = xi3_im_ + y * alpha1_im_ - x * alpha2_im_;
                            double Base = -U_ * base_dx + 1. / 2 * (base_dx * base_dx + base_dz * base_dz);
                            double GradBase1 = -U_ * base_dxx + base_dxx * base_dx + base_dxz * base_dz;
                            double GradBase3 = -U_ * base_dxz + base_dxz * base_dx + base_dzz * base_dz;
                            double MotionGradBaseReal = MotionReal1 * GradBase1 + MotionReal3 * GradBase3;
                            double MotionGradBaseImag = MotionImag1 * GradBase1 + MotionImag3 * GradBase3;
                            double RelativeEtaReal = eta_real - (xi2_re_ + x * alpha3_re_ - z * alpha1_re_);
                            double RelativeEtaImag = eta_imag - (xi2_im_ + x * alpha3_im_ - z * alpha1_im_);
                            double RotNReal1 = alpha2_re_ * n3 - alpha3_re_ * n2;
                            double RotNImag1 = alpha2_im_ * n3 - alpha3_im_ * n2;
                            // NOTE: GradBase2, MotionReal2 and MotionImag2 are all zero, as dphib/dy = 0 everywhere at the free surface
                            double F0 =
                                n1 * (1. / 2 * rho_ * g_ * (1. / 2 * (RelativeEtaReal * RelativeEtaReal + RelativeEtaImag * RelativeEtaImag)) -
                                      1. / 2 * rho_ * (MotionGradBaseReal * RelativeEtaReal + MotionGradBaseImag * RelativeEtaImag)) -
                                1. / 2 * rho_ * (RelativeEtaReal * RotNReal1 + RelativeEtaImag * RotNImag1) * Base;

                            if (i != wlength - 1)
                                dls.push_back(wlData_[line].dl[i]);

                            etap_0.push_back(F0);

                        } // End of mask check

                    } // End of loop over waterline points (ALL DATA FOR THIS WATERLINE ARE STORED IN THE VECTORS)

                    //
                    // THE LINE INTEGRATION IS PERFORMED HERE FOR THIS WATERLINE.
                    // NOTE THAT AT THE SAME TIME THE RESULTS DUE TO ALL OTHER WATERLNES
                    // ARE ALSO ADDED HERE.

                    drift_wline_0 += IntegrateLineData(etap_0, dls, fdC_, fdCleft_, fdCright_);

                } // End loop over water lines

                forces_nearField_(0, f) += ComputeSurfaceIntegral(integrator_, gridData_->triangulation, x_force_integrand) + drift_wline_0;

            } // Integration count

        } // Frequency

    } // End of wave drift check
}