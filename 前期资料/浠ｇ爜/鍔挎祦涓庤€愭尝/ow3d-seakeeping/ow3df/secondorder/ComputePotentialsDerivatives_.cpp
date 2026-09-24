// This public member function belongs to the FisrtOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "SecondOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::SecondOrder::ComputePotentialsDerivatives_(unsigned int f)
{
	const double omegae = allKsAndOmegas_.omegae[f];
	const double omega = allKsAndOmegas_.omegao[f]; // Angular frequency (absolute).
	const double wnb = allKsAndOmegas_.ko[f];		// Wave number.

	// Assign the response amplitude operators.

	unsigned int nrads = radiation_runs_.size();
	unsigned int ndifs = diffraction_runs_.size();

	struct comp
	{
		double sym_real;
		double sym_imag;
		double asm_real;
		double asm_imag;

	} cp; // The frequency domain data is stored in this variable.

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
		z = (gridData_->nod == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);

		n1 = vbn(Is[0], Is[1], Is[2], axis1);
		n2 = vbn(Is[0], Is[1], Is[2], axis2); // Note : "n2" vertical up
		n3 = (gridData_->nod == 2) ? 0 * n1 : vbn(Is[0], Is[1], Is[2], axis3);

		realArray sym_phi_real(Is[0], Is[1], Is[2]), sym_phi_imag(Is[0], Is[1], Is[2]);
		realArray asm_phi_real(Is[0], Is[1], Is[2]), asm_phi_imag(Is[0], Is[1], Is[2]);
		realArray dx_real(Is[0], Is[1], Is[2]), dx_imag(Is[0], Is[1], Is[2]);
		realArray dy_real(Is[0], Is[1], Is[2]), dy_imag(Is[0], Is[1], Is[2]);
		realArray sym_dz_real(Is[0], Is[1], Is[2]), sym_dz_imag(Is[0], Is[1], Is[2]);
		realArray asm_dz_real(Is[0], Is[1], Is[2]), asm_dz_imag(Is[0], Is[1], Is[2]);
		realArray dxx_real(Is[0], Is[1], Is[2]), dxx_imag(Is[0], Is[1], Is[2]);
		realArray dyy_real(Is[0], Is[1], Is[2]), dyy_imag(Is[0], Is[1], Is[2]);
		realArray dzz_real(Is[0], Is[1], Is[2]), dzz_imag(Is[0], Is[1], Is[2]);
		realArray dxy_real(Is[0], Is[1], Is[2]), dxy_imag(Is[0], Is[1], Is[2]);
		realArray sym_dxz_real(Is[0], Is[1], Is[2]), sym_dxz_imag(Is[0], Is[1], Is[2]);
		realArray asm_dxz_real(Is[0], Is[1], Is[2]), asm_dxz_imag(Is[0], Is[1], Is[2]);
		realArray sym_dyz_real(Is[0], Is[1], Is[2]), sym_dyz_imag(Is[0], Is[1], Is[2]);
		realArray asm_dyz_real(Is[0], Is[1], Is[2]), asm_dyz_imag(Is[0], Is[1], Is[2]);

		sym_phi_real = 0., sym_phi_imag = 0.;
		asm_phi_real = 0., asm_phi_imag = 0.;
		dx_real = 0., dx_imag = 0., dy_real = 0., dy_imag = 0.;
		dxx_real = 0., dxx_imag = 0., dyy_real = 0., dyy_imag = 0., dzz_real = 0., dzz_imag = 0., dxy_real = 0., dxy_imag = 0.;
		sym_dz_real = 0., sym_dz_imag = 0., asm_dz_real = 0., asm_dz_imag = 0.;
		sym_dxz_real = 0., sym_dxz_imag = 0., asm_dxz_real = 0., asm_dxz_imag = 0.;
		sym_dyz_real = 0., sym_dyz_imag = 0., asm_dyz_real = 0., asm_dyz_imag = 0.;

		int l0 = Is[0].getLength();
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

			surface_shift += bcl0 * bcl1 * bcl2 * nrads * flength_;
		}

		for (unsigned int r = 0; r < nrads; r++)
		{
			double rao_real = RAOs_[r](0, f);
			double rao_imag = RAOs_[r](1, f);

			for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
			{
				for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
				{
					for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
					{
						// Note : the data has been stored as [surface][i][j][k][type][f].

						int shift = surface_shift + i * l1 * l2 * nrads * flength_ + j * l2 * nrads * flength_ + k * nrads * flength_ + r * flength_ + f;
						body_radi_fin_.seekg(shift * (sizeof cp), ios_base::beg);
						body_radi_fin_.read((char *)&cp, sizeof cp);

						double real_phasor = cp.sym_real + cp.asm_real;
						double imag_phasor = cp.sym_imag + cp.asm_imag;

						phi_(0)[surface](i, j, k) = real_phasor;
						phi_(1)[surface](i, j, k) = imag_phasor;

					} // k

				} // j

			} // i

			MODE_NAMES mode_name = radiation_runs_[r].mode;

			OW3DSeakeeping::SideDervs dervs_real, dervs_imag;
			realArray phin_real, phin_imag;

			if (mode_name == MODE_NAMES::SURGE)
			{
				phin_real = mterms_.m1[surface];
				phin_imag = omegae * n1;
			}
			else if (mode_name == MODE_NAMES::HEAVE)
			{
				phin_real = mterms_.m2[surface];
				phin_imag = omegae * n2;
			}
			else if (mode_name == MODE_NAMES::SWAY)
			{
				phin_real = mterms_.m3[surface];
				phin_imag = omegae * n3;
			}
			else if (mode_name == MODE_NAMES::ROLL)
			{
				phin_real = mterms_.m4[surface];
				phin_imag = omegae * (n3 * y - n2 * z);
			}
			else if (mode_name == MODE_NAMES::YAW)
			{
				phin_real = mterms_.m5[surface];
				phin_imag = omegae * (n1 * z - n3 * x);
			}
			else if (mode_name == MODE_NAMES::PITCH)
			{
				phin_real = mterms_.m6[surface];
				phin_imag = omegae * (n2 * x - n1 * y);
			}

			char mode_type = (mode_name == MODE_NAMES::SWAY || mode_name == MODE_NAMES::ROLL || mode_name == MODE_NAMES::YAW) ? 'a' : 's';
			OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_->body_fundamentals[surface], gridData_->body_surface_disc[surface], phi_(0)[surface], phin_real, dervs_real, mode_type);
			OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_->body_fundamentals[surface], gridData_->body_surface_disc[surface], phi_(1)[surface], phin_imag, dervs_imag, mode_type);

			if (f == 0) // Save the zero-frequency mode
			{
				phi0_[r][surface] = phi_(0)[surface];
				phi0x_[r][surface] = dervs_real.dx;
				phi0y_[r][surface] = dervs_real.dy;
				phi0z_[r][surface] = dervs_real.dz;
				phi0xx_[r][surface] = dervs_real.dxx;
				phi0yy_[r][surface] = dervs_real.dyy;
				phi0zz_[r][surface] = dervs_real.dzz;
				phi0xy_[r][surface] = dervs_real.dxy;
				phi0xz_[r][surface] = dervs_real.dxz;
				phi0yz_[r][surface] = dervs_real.dyz;
			}
			else
			{
				// Remove the zero-frequency mode

				phi_(0)[surface] -= phi0_[r][surface];
				dervs_real.dx -= phi0x_[r][surface];
				dervs_real.dy -= phi0y_[r][surface];
				dervs_real.dz -= phi0z_[r][surface];
				dervs_real.dxx -= phi0xx_[r][surface];
				dervs_real.dyy -= phi0yy_[r][surface];
				dervs_real.dzz -= phi0zz_[r][surface];
				dervs_real.dxy -= phi0xy_[r][surface];
				dervs_real.dxz -= phi0xz_[r][surface];
				dervs_real.dyz -= phi0yz_[r][surface];

				// Multiply by rao: (a+ib)*(c+id) = (ac-bd) + i(ad+bc) where a+ib is rao. Add also all modes.

				// * real
				dx_real += dervs_real.dx * rao_real - dervs_imag.dx * rao_imag;
				dy_real += dervs_real.dy * rao_real - dervs_imag.dy * rao_imag;
				dxx_real += dervs_real.dxx * rao_real - dervs_imag.dxx * rao_imag;
				dyy_real += dervs_real.dyy * rao_real - dervs_imag.dyy * rao_imag;
				dzz_real += dervs_real.dzz * rao_real - dervs_imag.dzz * rao_imag;
				dxy_real += dervs_real.dxy * rao_real - dervs_imag.dxy * rao_imag;

				// * imaginary
				dx_imag += dervs_imag.dx * rao_real + dervs_real.dx * rao_imag;
				dy_imag += dervs_imag.dy * rao_real + dervs_real.dy * rao_imag;
				dxx_imag += dervs_imag.dxx * rao_real + dervs_real.dxx * rao_imag;
				dyy_imag += dervs_imag.dyy * rao_real + dervs_real.dyy * rao_imag;
				dzz_imag += dervs_imag.dzz * rao_real + dervs_real.dzz * rao_imag;
				dxy_imag += dervs_imag.dxy * rao_real + dervs_real.dxy * rao_imag;

				// z derivatives are assigned separately for symmetric and anti-symmetric modes

				if (mode_name == MODE_NAMES::HEAVE or
					mode_name == MODE_NAMES::SURGE or
					mode_name == MODE_NAMES::PITCH)
				{
					sym_phi_real += phi_(0)[surface] * rao_real - phi_(1)[surface] * rao_imag;
					asm_dz_real += dervs_real.dz * rao_real - dervs_imag.dz * rao_imag;
					asm_dxz_real += dervs_real.dxz * rao_real - dervs_imag.dxz * rao_imag;
					asm_dyz_real += dervs_real.dyz * rao_real - dervs_imag.dyz * rao_imag;

					sym_phi_imag += phi_(1)[surface] * rao_real + phi_(0)[surface] * rao_imag;
					asm_dz_imag += dervs_imag.dz * rao_real + dervs_real.dz * rao_imag;
					asm_dxz_imag += dervs_imag.dxz * rao_real + dervs_real.dxz * rao_imag;
					asm_dyz_imag += dervs_imag.dyz * rao_real + dervs_real.dyz * rao_imag;
				}
				else
				{
					asm_phi_real += phi_(0)[surface] * rao_real - phi_(1)[surface] * rao_imag;
					sym_dz_real += dervs_real.dz * rao_real - dervs_imag.dz * rao_imag;
					sym_dxz_real += dervs_real.dxz * rao_real - dervs_imag.dxz * rao_imag;
					sym_dyz_real += dervs_real.dyz * rao_real - dervs_imag.dyz * rao_imag;

					asm_phi_imag += phi_(1)[surface] * rao_real + phi_(0)[surface] * rao_imag;
					sym_dz_imag += dervs_imag.dz * rao_real + dervs_real.dz * rao_imag;
					sym_dxz_imag += dervs_imag.dxz * rao_real + dervs_real.dxz * rao_imag;
					sym_dyz_imag += dervs_imag.dyz * rao_real + dervs_real.dyz * rao_imag;
				}
			}

		} // End of raditions

		// Diffraction

		surface_shift = 0; // Reset the surface shift

		for (int back = surface; back > 0; back--)
		{
			const Single_boundary_data &sbd = boundariesData_->exciting[back - 1];
			const vector<Index> &I = sbd.surface_indices;

			const int bcl0 = I[0].getLength();
			const int bcl1 = I[1].getLength();
			const int bcl2 = I[2].getLength();

			surface_shift += bcl0 * bcl1 * bcl2 * ndifs * flength_;
		}

		for (unsigned int r = 0; r < ndifs; r++)
		{
			for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
			{
				for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
				{
					for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
					{
						// Note : the data has been stored as [surface][i][j][k][type][f].

						int shift = surface_shift + i * l1 * l2 * ndifs * flength_ + j * l2 * ndifs * flength_ + k * ndifs * flength_ + r * flength_ + f;
						body_scat_fin_.seekg(shift * (sizeof cp), ios_base::beg);
						body_scat_fin_.read((char *)&cp, sizeof cp);

						double real_phasor = cp.sym_real + cp.asm_real;
						double imag_phasor = cp.sym_imag + cp.asm_imag;

						phi_(0)[surface](i, j, k) = real_phasor;
						phi_(1)[surface](i, j, k) = imag_phasor;

					} // k

				} // j

			} // i

			// ---------------------------------
			// Define incident wave components
			// ---------------------------------

			realArray COSH = cosh(wnb * (y + h_)) / cosh(wnb * h_);
			realArray SINH = sinh(wnb * (y + h_)) / cosh(wnb * h_);
			// realArray COSH = (exp(wnb * y) + exp(-wnb * (y + 2 * h_))) / (1. + exp(-2 * wnb * h_));
			// realArray SINH = (exp(wnb * y) - exp(-wnb * (y + 2 * h_))) / (1. + exp(-2 * wnb * h_));

			realArray COS_KZ_SIN_BET = cos(wnb * z * sin_betar_);
			realArray SIN_KZ_SIN_BET = sin(wnb * z * sin_betar_);
			realArray COS_KX_COS_BET = cos(wnb * x * cos_betar_);
			realArray SIN_KX_COS_BET = sin(wnb * x * cos_betar_);

			// phi
			realArray incid_phi_sym_real = g_ / (omega)*COSH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phi_sym_imag = g_ / (omega)*COSH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phi_asm_real = g_ / (omega)*COSH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phi_asm_imag = g_ / (omega)*COSH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			// phix
			realArray incid_phix_sym_real = (g_ * wnb * cos_betar_) / omega * COSH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phix_sym_imag = -(g_ * wnb * cos_betar_) / omega * COSH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phix_asm_real = -(g_ * wnb * cos_betar_) / omega * COSH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phix_asm_imag = -(g_ * wnb * cos_betar_) / omega * COSH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			// phiy
			realArray incid_phiy_sym_real = (g_ * wnb) / omega * SINH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phiy_sym_imag = (g_ * wnb) / omega * SINH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phiy_asm_real = (g_ * wnb) / omega * SINH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phiy_asm_imag = -(g_ * wnb) / omega * SINH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			// phiz
			realArray incid_phiz_sym_real = (g_ * wnb * sin_betar_) / omega * COSH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phiz_sym_imag = -(g_ * wnb * sin_betar_) / omega * COSH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phiz_asm_real = -(g_ * wnb * sin_betar_) / omega * COSH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phiz_asm_imag = -(g_ * wnb * sin_betar_) / omega * COSH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			// phixx
			realArray incid_phixx_sym_real = -(g_ * wnb * wnb * cos_betar_ * cos_betar_) / omega * COSH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phixx_sym_imag = -(g_ * wnb * wnb * cos_betar_ * cos_betar_) / omega * COSH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phixx_asm_real = -(g_ * wnb * wnb * cos_betar_ * cos_betar_) / omega * COSH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phixx_asm_imag = (g_ * wnb * wnb * cos_betar_ * cos_betar_) / omega * COSH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			// phiyy
			realArray incid_phiyy_sym_real = (g_ * wnb * wnb) / omega * COSH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phiyy_sym_imag = (g_ * wnb * wnb) / omega * COSH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phiyy_asm_real = (g_ * wnb * wnb) / omega * COSH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phiyy_asm_imag = -(g_ * wnb * wnb) / omega * COSH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			// phizz
			realArray incid_phizz_sym_real = -(g_ * wnb * wnb * sin_betar_ * sin_betar_) / omega * COSH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phizz_sym_imag = -(g_ * wnb * wnb * sin_betar_ * sin_betar_) / omega * COSH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phizz_asm_real = -(g_ * wnb * wnb * sin_betar_ * sin_betar_) / omega * COSH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phizz_asm_imag = (g_ * wnb * wnb * sin_betar_ * sin_betar_) / omega * COSH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			// phixy
			realArray incid_phixy_sym_real = (g_ * wnb * wnb * cos_betar_) / omega * SINH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phixy_sym_imag = -(g_ * wnb * wnb * cos_betar_) / omega * SINH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phixy_asm_real = -(g_ * wnb * wnb * cos_betar_) / omega * SINH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phixy_asm_imag = -(g_ * wnb * wnb * cos_betar_) / omega * SINH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			// phixz
			realArray incid_phixz_sym_real = -(g_ * wnb * wnb * cos_betar_ * sin_betar_) / omega * COSH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phixz_sym_imag = -(g_ * wnb * wnb * cos_betar_ * sin_betar_) / omega * COSH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phixz_asm_real = -(g_ * wnb * wnb * cos_betar_ * sin_betar_) / omega * COSH * SIN_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phixz_asm_imag = (g_ * wnb * wnb * cos_betar_ * sin_betar_) / omega * COSH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			// phiyz
			realArray incid_phiyz_sym_real = (g_ * wnb * wnb * sin_betar_) / omega * SINH * COS_KZ_SIN_BET * COS_KX_COS_BET;
			realArray incid_phiyz_sym_imag = -(g_ * wnb * wnb * sin_betar_) / omega * SINH * COS_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phiyz_asm_real = -(g_ * wnb * wnb * sin_betar_) / omega * SINH * SIN_KZ_SIN_BET * SIN_KX_COS_BET;
			realArray incid_phiyz_asm_imag = -(g_ * wnb * wnb * sin_betar_) / omega * SINH * SIN_KZ_SIN_BET * COS_KX_COS_BET;

			DIFF_TYPES diftype = diffraction_runs_[r].diff_type;
			OW3DSeakeeping::SideDervs dervs_real, dervs_imag;
			realArray phin_real, phin_imag;

			if (diftype == DIFF_TYPES::HEAD || diftype == DIFF_TYPES::SYM)
			{
				phin_real = -(n1 * incid_phix_sym_real + n2 * incid_phiy_sym_real + n3 * incid_phiz_sym_real);
				phin_imag = -(n1 * incid_phix_sym_imag + n2 * incid_phiy_sym_imag + n3 * incid_phiz_sym_imag);

				OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_->body_fundamentals[surface], gridData_->body_surface_disc[surface], phi_(0)[surface], phin_real, dervs_real);
				OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_->body_fundamentals[surface], gridData_->body_surface_disc[surface], phi_(1)[surface], phin_imag, dervs_imag);

				dx_real += dervs_real.dx + incid_phix_sym_real;
				dy_real += dervs_real.dy + incid_phiy_sym_real;
				dxx_real += dervs_real.dxx + incid_phixx_sym_real;
				dyy_real += dervs_real.dyy + incid_phiyy_sym_real;
				dzz_real += dervs_real.dzz + incid_phizz_sym_real;
				dxy_real += dervs_real.dxy + incid_phixy_sym_real;

				// * imaginary
				dx_imag += dervs_imag.dx + incid_phix_sym_imag;
				dy_imag += dervs_imag.dy + incid_phiy_sym_imag;
				dxx_imag += dervs_imag.dxx + incid_phixx_sym_imag;
				dyy_imag += dervs_imag.dyy + incid_phiyy_sym_imag;
				dzz_imag += dervs_imag.dzz + incid_phizz_sym_imag;
				dxy_imag += dervs_imag.dxy + incid_phixy_sym_imag;

				// z derivatives are assigned separately for symmetric and anti-symmetric modes

				sym_phi_real += phi_(0)[surface] + incid_phi_sym_real;
				asm_dz_real += dervs_real.dz + incid_phiz_asm_real;
				asm_dxz_real += dervs_real.dxz + incid_phixz_asm_real;
				asm_dyz_real += dervs_real.dyz + incid_phiyz_asm_real;

				sym_phi_imag += phi_(1)[surface] + incid_phi_sym_imag;
				asm_dz_imag += dervs_imag.dz + incid_phiz_asm_imag;
				asm_dxz_imag += dervs_imag.dxz + incid_phixz_asm_imag;
				asm_dyz_imag += dervs_imag.dyz + incid_phiyz_asm_imag;
			}
			else
				throw runtime_error("Added resistance only implemented for head seas. Implementation for other headings is underway by maaf!");
		}

		sym_phi_(0)[surface] = sym_phi_real;
		asm_phi_(0)[surface] = asm_phi_real;
		d_phi_dx_(0)[surface] = dx_real;
		d_phi_dy_(0)[surface] = dy_real;
		sym_d_phi_dz_(0)[surface] = sym_dz_real;
		asm_d_phi_dz_(0)[surface] = asm_dz_real;
		d_phi_dxx_(0)[surface] = dxx_real;
		d_phi_dyy_(0)[surface] = dyy_real;
		d_phi_dzz_(0)[surface] = dzz_real;
		d_phi_dxy_(0)[surface] = dxy_real;
		sym_d_phi_dxz_(0)[surface] = sym_dxz_real;
		asm_d_phi_dxz_(0)[surface] = asm_dxz_real;
		sym_d_phi_dyz_(0)[surface] = sym_dyz_real;
		asm_d_phi_dyz_(0)[surface] = asm_dyz_real;

		sym_phi_(1)[surface] = sym_phi_imag;
		asm_phi_(1)[surface] = asm_phi_imag;
		d_phi_dx_(1)[surface] = dx_imag;
		d_phi_dy_(1)[surface] = dy_imag;
		sym_d_phi_dz_(1)[surface] = sym_dz_imag;
		asm_d_phi_dz_(1)[surface] = asm_dz_imag;
		d_phi_dxx_(1)[surface] = dxx_imag;
		d_phi_dyy_(1)[surface] = dyy_imag;
		d_phi_dzz_(1)[surface] = dzz_imag;
		d_phi_dxy_(1)[surface] = dxy_imag;
		sym_d_phi_dxz_(1)[surface] = sym_dxz_imag;
		asm_d_phi_dxz_(1)[surface] = asm_dxz_imag;
		sym_d_phi_dyz_(1)[surface] = sym_dyz_imag;
		asm_d_phi_dyz_(1)[surface] = asm_dyz_imag;

	} // End of body surfaces

} // End of the function