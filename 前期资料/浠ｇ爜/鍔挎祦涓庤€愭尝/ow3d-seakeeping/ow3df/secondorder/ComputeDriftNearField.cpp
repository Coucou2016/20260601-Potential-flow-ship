// This public member function belongs to the SecondOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "SecondOrder.h"
#include "OW3DConstants.h"

// An outline of the function:
//
//  Data preparation for body and water line integrations
//
//   for(frequency)
//    |
//    |  Assign RAOs
//    |
//    |  for(integration counts)
//    |   |
//    |   |
//    |   |  for(body surface)
//    |   |   | for(i)
//    |   |   |  | for(j)
//    |   |   |  |  | for(k)
//    |   |   |  |  |  | for(type of data)
//    |   |   |  |  |  |  |
//    |   |   |  |  |  |  |  Read from binary file, and assign phi
//    |   |   |  |  |  |  |  and grad phi phasors on the body surfaces
//    |   |   |  |  |  |  |
//    |   |   |  |  |  | end for(type of data)
//    |   |   |  |  | end for(k)
//    |   |   |  | end for(j)
//    |   |   | end for(i)
//    |   |  end for (body surface)
//    |   |
//    |   |  Assign the composite grid functions for body integrations
//    |   |
//    |   |  for(waterline)
//    |   |   |  for(i)
//    |   |   |   |
//    |   |   |   | Read from binary file and assign
//    |   |   |   | phasors on the waterline points
//    |   |   |   |
//    |   |   |  end for(i)
//    |   |  end for(waterline)
//    |   |
//    |   |  Integrate over the body surfaces and
//    |   |  the waterlines to calculate drift forces
//    |   |
//    |   |
//    |  end for(integration counts)
//    |
//    |
//    |
//   end for(frequency)

void OW3DSeakeeping::SecondOrder::ComputeDriftNearField()
{
	if (OW3DSeakeeping::UserInput.wave_drift)
	{
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

		// For body integration

		realCompositeGridFunction data_0(*cg_);
		data_0 = 0.;
		realCompositeGridFunction data_1(*cg_);
		data_1 = 0.;
		realCompositeGridFunction data_2(*cg_);
		data_2 = 0.;
		realCompositeGridFunction data_3(*cg_);
		data_3 = 0.;
		realCompositeGridFunction data_4(*cg_);
		data_4 = 0.;
		realCompositeGridFunction data_5(*cg_);
		data_5 = 0.;

		RealArray first_integrand;	   //
		RealArray second_integrand_re; //
		RealArray second_integrand_im; // These variables are used
		RealArray third_integrand;	   // for calculation of
		RealArray fourth_integrand_re; // the body integral parts
		RealArray fourth_integrand_im; // of the wave drift force
		RealArray fifth_integrand;	   //
		RealArray sixth_integrand;	   //

		vector<double> dls;					   // The segment length for the waterline
		vector<double> etap_0, etap_1, etap_5; // To store each waterline contribution (SURGE, SWAY , YAW)

		vector<double> omegaeVector = allKsAndOmegas_.omegae;

		// Following are used for intgeration on other half of the geometry
		realCompositeGridFunction mir_base_dz = base_dz_;
		realCompositeGridFunction mir_base_dxz = base_dxz_;
		realCompositeGridFunction mir_base_dyz = base_dyz_;

		// ---------------------------------------------
		//
		// Frequency loop
		//
		// ----------------------------------------------

		for (unsigned int f = 0; f < flength_; f++)
		{
			const double omegae = omegaeVector[f];

			// Assign the response amplitude operators.

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
					throw runtime_error(GetColoredMessage("\n\t Error (OW3D), SecondOrder::ComputeDriftNearField.cpp.\n\t The type of radiation run can not be recognized", 0));
			}

			// -------------------------------------
			//
			// Loop due to symmetry of the grid.
			//
			// -------------------------------------

			for (unsigned int count = 0; count < numberOFIntegrations_; count++)
			{
				int symSign = (count == 0) ? 1 : -1; // Means integration on the other half of the body

				mir_base_dz = symSign * base_dz_;
				mir_base_dxz = symSign * base_dxz_;
				mir_base_dyz = symSign * base_dyz_;

				// ---------------------------------------------------------
				//
				// Body surface loop (to calculate the body contribution)
				//
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

					int l0 = Is[0].getLength();
					int l1 = Is[1].getLength();
					int l2 = Is[2].getLength();

					// ---------------------------------------------
					//
					// The shift due to the previous surfaces
					//
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

					first_integrand.resize(l0, l1, l2), first_integrand = 0.;
					second_integrand_re.resize(l0, l1, l2), second_integrand_re = 0.;
					second_integrand_im.resize(l0, l1, l2), second_integrand_im = 0.;
					third_integrand.resize(l0, l1, l2), third_integrand = 0.;
					fourth_integrand_re.resize(l0, l1, l2), fourth_integrand_re = 0.;
					fourth_integrand_im.resize(l0, l1, l2), fourth_integrand_im = 0.;
					fifth_integrand.resize(l0, l1, l2), fifth_integrand = 0.;
					sixth_integrand.resize(l0, l1, l2), sixth_integrand = 0.;

					// ------------------------------------------------
					//
					// Loop over the type of the data (phi or grad phi)
					// Loop over i
					// Loop over j
					// Loop over k
					//
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

									int shift = surface_shift + i * l1 * l2 * NPOTENS_ * flength_ + j * l2 * NPOTENS_ * flength_ + k * NPOTENS_ * flength_ + pot * flength_ + f;

									body_fin_.seekg(shift * (sizeof cp), ios_base::beg);
									body_fin_.read((char *)&cp, sizeof cp);

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

					} // End of loop over the type of the data (phi or grad phi)

					// ---------------------------------------------------------------------

					// ( grad(phiu) )^2
					//
					//  Note : "1/2" is required for the complex number operation
					//
					first_integrand =
						1. / 2 *
						(d_phi_dx_(0)[surface] * d_phi_dx_(0)[surface] + d_phi_dx_(1)[surface] * d_phi_dx_(1)[surface] +
						 d_phi_dy_(0)[surface] * d_phi_dy_(0)[surface] + d_phi_dy_(1)[surface] * d_phi_dy_(1)[surface] +
						 d_phi_dz_(0)[surface] * d_phi_dz_(0)[surface] + d_phi_dz_(1)[surface] * d_phi_dz_(1)[surface]);

					// real{ dphiu/dt - U*dphiu/dx + grad(phiu).grad(phib) }
					//
					second_integrand_re = (-omegae * phi_(1)[surface] - U_ * d_phi_dx_(0)[surface] +
										   d_phi_dx_(0)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
										   d_phi_dy_(0)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
										   d_phi_dz_(0)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]));

					// imag{ dphiu/dt - U*dphiu/dx + grad(phiu).grad(phib) }
					//
					second_integrand_im = (omegae * phi_(0)[surface] - U_ * d_phi_dx_(1)[surface] +
										   d_phi_dx_(1)[surface] * base_dx_[be.grid](Is[0], Is[1], Is[2]) +
										   d_phi_dy_(1)[surface] * base_dy_[be.grid](Is[0], Is[1], Is[2]) +
										   d_phi_dz_(1)[surface] * mir_base_dz[be.grid](Is[0], Is[1], Is[2]));

					// (xi + alpha * r) . grad ( dphi/dt - U*dphiu/dx + grad(phiu).grad(phib) )
					//
					// ( xi1 + alpha2*z - alpha3*y ) * d/dx( dphi/dt - U*dphiu/dx + grad(phiu).grad(phib) ) +
					// ( xi2 - alpha1*z + alpha3*x ) * d/dy( dphi/dt - U*dphiu/dx + grad(phiu).grad(phib) ) +
					// ( xi3 + alpha1*y - alpha2*x ) * d/dz( dphi/dt - U*dphiu/dx + grad(phiu).grad(phib) )
					//
					//   Note : "1/2" is required for the complex number operation
					//
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

					// ---------------------------------------------------------------------------------------
					//
					// Axis 0 - MEAN DRIFT FORCE - BODY
					//
					// ---------------------------------------------------------------------------------------

					data_0[be.grid](Is[0], Is[1], Is[2]) =
						// -1/2 * rho * ( grad(phiu) )^2 * n1
						-1. / 2 * rho_ * first_integrand * n1
						// -rho * ( dphiu/dt - U*dphiu/dx + grad(phiu) . grad(phib) ) * (alpha2*n3 - alpha3*n2)
						//
						// Note : "1/2" is required becuase of the complex number operation
						//
						- rho_ * 1. / 2 * (second_integrand_re * (alpha2_re_ * n3 - alpha3_re_ * n2) + second_integrand_im * (alpha2_im_ * n3 - alpha3_im_ * n2))
						// -rho *  (xi + alpha * r) . grad ( dphi/dt - U*dphiu/dx + grad(phiu) . grad(phib) ) * n1
						- rho_ * third_integrand * n1
						// -rho * (xi + alpha * r) . grad(-U*dphib/dx + 1/2*grad(phib) . grad(phib)) * (alpha2*n3 - alpha3*n2)
						//
						//  Note : "1/2" is required because of the complex number operation
						//
						- rho_ * 1. / 2 * (fourth_integrand_re * (alpha2_re_ * n3 - alpha3_re_ * n2) + fourth_integrand_im * (alpha2_im_ * n3 - alpha3_im_ * n2))
						// -rho * ( -U*dphib/dx + 1/2*grad(phib) . grad(phib) ) * ( -1/2(alpha2^2 + alpha3^2) ) * n1
						//
						//  Note : "1/2" is required because of the complex number operation
						//
						- rho_ * fifth_integrand * -1. / 2 * (1. / 2 * (alpha2_re_ * alpha2_re_ + alpha2_im_ * alpha2_im_ + alpha3_re_ * alpha3_re_ + alpha3_im_ * alpha3_im_)) * n1
						// -rho * d/dx ( -U*dphib/dx + 1/2*grad(phib) . grad(phib) ) * ( -(alpha2*alpha2 + alpha3*alpha3) ) * x * n1
						- rho_ * sixth_integrand * n1;

					// ---------------------------------------------------------------------------------------
					//
					// Axis 1 - MEAN DRIFT FORCE - BODY
					//
					// ---------------------------------------------------------------------------------------

					data_1[be.grid](Is[0], Is[1], Is[2]) = 0;

					// ---------------------------------------------------------------------------------------
					//
					// Axis 2 - MEAN DRIFT FORCE - BODY
					//
					// ---------------------------------------------------------------------------------------

					data_2[be.grid](Is[0], Is[1], Is[2]) = 0;

					// ---------------------------------------------------------------------------------------
					//
					// Axis 3 - MEAN DRIFT MOMENT - BODY
					//
					// ---------------------------------------------------------------------------------------

					data_3[be.grid](Is[0], Is[1], Is[2]) = 0;

					// ---------------------------------------------------------------------------------------
					//
					// Axis 4 - MEAN DRIFT MOMENT - BODY
					//
					// ---------------------------------------------------------------------------------------

					data_4[be.grid](Is[0], Is[1], Is[2]) = 0;

					// ---------------------------------------------------------------------------------------
					//
					// Axis 5 - MEAN DRIFT MOMENT - BODY
					//
					// ---------------------------------------------------------------------------------------

					data_5[be.grid](Is[0], Is[1], Is[2]) = 0;

				} // End surface loop

				// --------------------------------------------------------------
				//
				// Water line loop (to calculate the water line contribution)
				//
				// --------------------------------------------------------------

				double drift_wline_0 = 0.; // The final waterline
				double drift_wline_1 = 0.; // contribution are
				double drift_wline_5 = 0.; // initialized here first.

				for (unsigned int line = 0; line < wlData_.size(); line++)
				{
					etap_0.clear(); // NOTE : THESE CONTAINERS
					etap_1.clear(); //        MUST BE CLEARED, SO
					etap_5.clear(); //        THEY ARE READY FOR THE
					dls.clear();	//        NEXT WATERLINE DATA.

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
						const double z = wlData_[line].z[i] * symSign;
						const double y = 0.;

						wline_fin_.seekg(shift * (sizeof cp), ios_base::beg);
						wline_fin_.read((char *)&cp, sizeof cp);

						double eta_real = 0.;
						double eta_imag = 0.;

						eta_real = cp.sym_real + cp.asm_real * symSign;
						eta_imag = cp.sym_imag + cp.asm_imag * symSign;

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

							double F1 = 0.;
							double F5 = 0.;
							if (i != wlength - 1)
								dls.push_back(wlData_[line].dl[i]);

							etap_0.push_back(F0);
							etap_1.push_back(F1);
							etap_5.push_back(F5);

							// gwlc_[line][i] = F0; // Uncomment for the trapezoidal integration

						} // End of mask check

					} // End of loop over waterline points (ALL DATA FOR THIS WATERLINE ARE STORED IN THE VECTORS)

					//
					// THE LINE INTEGRATION IS PERFORMED HERE FOR THIS WATERLINE.
					// NOTE THAT AT THE SAME TIME THE RESULTS DUE TO ALL OTHER WATERLNES
					// ARE ALSO ADDED HERE.

					// Comment out for the trapezoidal integration
					drift_wline_0 += IntegrateLineData(etap_0, dls, fdC_, fdCleft_, fdCright_);
					// drift_wline_1 += IntegrateLineData(etap_1, dls, fdC_, fdCleft_, fdCright_);
					// drift_wline_5 += IntegrateLineData(etap_5, dls, fdC_, fdCleft_, fdCright_);

				} // End loop over water lines

				// ----------------------------------------------------------------------------------------------------------
				// Integrate and calculate the mean drift forces ( Waterline integration contributes to SURGE, SWAY and YAW )
				// -----------------------------------------------------------------------------------------------------------

				// drift_wline_0 = ComputeWaterlineTrapz_(gwlc_); // Uncomment for the trapezoidal integration

				forces_nearField_(0, f) += ComputeSurfaceIntegral(integrator_, gridData_->triangulation, data_0) + drift_wline_0;
				// forces_nearField_(1,f) += ComputeSurfaceIntegral(integrator_, gridData_->triangulation,data_1) + drift_wline_1;
				// forces_nearField_(2,f) += ComputeSurfaceIntegral(integrator_, gridData_->triangulation,data_2);
				// forces_nearField_(3,f) += ComputeSurfaceIntegral(integrator_, gridData_->triangulation,data_3);
				// forces_nearField_(4,f) += ComputeSurfaceIntegral(integrator_, gridData_->triangulation,data_4);
				// forces_nearField_(5,f) += ComputeSurfaceIntegral(integrator_, gridData_->triangulation,data_5) + drift_wline_5;

			} // Integrals count loop

			// Note : the drift forces are stored in the array as follows:
			//
			// axis 0 ---> :  (0)   (1) .... (5)
			//
			// axis 1 ( 0)     o     o        o
			// axis 1 ( 1)     o     o        o
			// axis 1 ( 2)     o     o        o
			// axis 1 ( 3)     o     o        o
			// axis 1 ( 4)     o     o        o
			// axis 1 ( 5)     o     o        o
			// ......          ...
			//
			// length of axis1 = number of frequencies
			// length of axix0 = 6. (0-2 force) (3-5 moment)

		} // End of frequency loop

		PrintLogMessage("Near-field wave drift force computed.");

	} // End of wave drift check
}

//            | (alpha2^2 + alpha3^2)            0                         0            |
//            |                                                                         |
// H =   -1/2 |  -2*alpha1*alpha2      (alpha1^2 + alpha3^2)               0            |
//            |                                                                         |
//            |  -2*alpha1*alpha3         -2*alpha2*alpha3       (alpha1^2 + alpha2^2)  |
//
//
// NOTE : If Y is upward then:
//
//
//            | (alpha2^2 + alpha3^2)            0                         0            |
//            |                                                                         |
// H =   -1/2 |  -2*alpha1*alpha2      (alpha1^2 + alpha3^2)       -2*alpha3*alpha2     |
//            |                                                                         |
//            |  -2*alpha1*alpha3                0               (alpha1^2 + alpha2^2)  |
//
//
