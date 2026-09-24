// Note : This part of the class is implemented here due to readibility of the main implementation file.

// -------------------------------------------------------------------------
// search along index "0" and "2" over the free-surface which has index "1"
// -------------------------------------------------------------------------

#include "Upwind.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Upwind::BuildUpwindStenciles_0_2_(
	unsigned int surface,
	const MappedGrid &mg,
	const vector<Index> &Is,
	const vector<Index> &I,
	const vector<realArray> &d_phib_dx,
	const vector<realArray> &d_phib_dz)
{
	int sw = 3;	  // used for file formatting
	int bw = 12;  // used for file formatting
	int BW = 41;  // used for file formatting
	int mw = 14;  // used for file formatting
	int prec = 6; // used for file formatting

	double tols = 1e-10;
	double tolb = 1e-10;
	int i, j;

	int bound0 = I[0].getBound();
	int bound2 = I[2].getBound();
	int base0 = I[0].getBase();
	int base2 = I[2].getBase();

	// -----------------------------------------------------------------------------------------------------------------------------------
	// -----------------------------------------------------------------------------------------------------------------------------------
	//
	//                                                UPWIND STENCIL FOR X DERIVATIVES
	//
	// -----------------------------------------------------------------------------------------------------------------------------------
	// -----------------------------------------------------------------------------------------------------------------------------------

	string xfilename = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name + "/" + upwind_x_coefficients_file + DoubleToString(surface);
	ofstream xfout;

	if (printx_)
	{
		xfout.open(xfilename);
		xfout << "Upwind x coefficients " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << "\n\n";
		xfout.precision(prec);
	}

	for (i = Is[0].getBase(); i <= Is[0].getBound(); i++)
	{
		for (j = Is[2].getBase(); j <= Is[2].getBound(); j++)
		{
			vertexData_[surface][i][j].mask = mg.mask()(i, Is[1].getBase(), j);

			if (mg.mask()(i, Is[1].getBase(), j) > 0) // just for discretisation points
			{
				double xc = mg.vertex()(i, Is[1].getBase(), j, axis1);

				// -------------------------------------------------------------------------
				//
				//                                  INDEX "0"
				//
				// -------------------------------------------------------------------------

				int d0, u0; // number of points downwind and upwind along index "0"

				vertexData_[surface][i][j].vder0x = mg.inverseVertexDerivative()(i, Is[1].getBase(), j, 0, 0); // dr0_dx

				double xd0 = mg.vertex()(i - 1, Is[1].getBase(), j, axis1);
				double xi0 = mg.vertex()(i + 1, Is[1].getBase(), j, axis1);
				double xs0 = mg.vertex()(base0, Is[1].getBase(), j, axis1);
				double xn0 = mg.vertex()(bound0, Is[1].getBase(), j, axis1);
				int inc_0_counts = 0;
				int dec_0_counts = 0;

				// counts number of incrementable points in the "0" direction index (exclude hole points)

				while ((i + 1) + inc_0_counts <= bound0 and mg.mask()((i + 1) + inc_0_counts, Is[1].getBase(), j) != 0)
				{
					inc_0_counts++;
				}

				// counts number of decrementable points in the "0" direction index (exclude hole points)

				while ((i - 1) - dec_0_counts >= base0 and mg.mask()((i - 1) - dec_0_counts, Is[1].getBase(), j) != 0)
				{
					dec_0_counts++;
				}

				// calculate range and coefficienst

				if (((fabs(xd0 - xi0) <= tolb) and ((fabs(xc) > fabs(xd0) and fabs(xc) > fabs(xi0)) or fabs(xs0 - xn0) <= tols)) or U_ == 0) // neutral or centered stencil
				{
					if (u_ != d_)
						vertexData_[surface][i][j].ind0x = UPWIND_STENCIL_TYPES::NEUTRAL; //"neu";
					else
						vertexData_[surface][i][j].ind0x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

					// viable stencil
					int half = (u_ + d_) / 2;
					int a = min(min(half, dec_0_counts), min(half, inc_0_counts));
					u0 = d0 = a;

					vertexData_[surface][i][j].u0x = a;
					vertexData_[surface][i][j].d0x = a;
					vertexData_[surface][i][j].R0x = Range(i - a, i + a);
					vertexData_[surface][i][j].C0x = FdCoefficients(a, a, 1);
				}
				else if (U_ * xd0 > U_ * xc) // biased by decrementing
				{
					if (u_ != d_)
						vertexData_[surface][i][j].ind0x = UPWIND_STENCIL_TYPES::DECREM; //"dec";
					else
						vertexData_[surface][i][j].ind0x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

					// viable stencil
					u0 = min(u_, dec_0_counts);
					d0 = min(d_, inc_0_counts);
					if (d0 >= u0 and u_ != d_)
						d0 = u0 - 1;

					vertexData_[surface][i][j].u0x = u0;
					vertexData_[surface][i][j].d0x = d0;
					vertexData_[surface][i][j].R0x = Range(i - u0, i + d0);

					if (U_ * vertexData_[surface][i][j].vder0x > 0)
					{
						vertexData_[surface][i][j].C0x = FdCoefficients(d0, u0, 1);
						flipArray_(vertexData_[surface][i][j].C0x);
					}
					else
					{
						vertexData_[surface][i][j].C0x = FdCoefficients(u0, d0, 1);
					}
				}
				else // biased by incrementing
				{
					if (u_ != d_)
						vertexData_[surface][i][j].ind0x = UPWIND_STENCIL_TYPES::INCREM; //"inc";
					else
						vertexData_[surface][i][j].ind0x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

					// viable stencil
					u0 = min(u_, inc_0_counts);
					d0 = min(d_, dec_0_counts);
					if (d0 >= u0 and u_ != d_)
						d0 = u0 - 1;

					vertexData_[surface][i][j].u0x = u0;
					vertexData_[surface][i][j].d0x = d0;
					vertexData_[surface][i][j].R0x = Range(i - d0, i + u0);

					if (U_ * vertexData_[surface][i][j].vder0x > 0)
					{
						vertexData_[surface][i][j].C0x = FdCoefficients(d0, u0, 1);
					}
					else
					{
						vertexData_[surface][i][j].C0x = FdCoefficients(u0, d0, 1);
						flipArray_(vertexData_[surface][i][j].C0x);
					}
				}

				// -------------------------------------------------------------------------
				//
				//                              INDEX "2" just 3D
				//
				// -------------------------------------------------------------------------

				if (mg.numberOfDimensions() == 3)
				{
					int d2, u2; // number of points downwind and upwind along index "2"

					vertexData_[surface][i][j].vder2x = mg.inverseVertexDerivative()(i, Is[1].getBase(), j, 2, 0); // dr2_dx

					double xd2 = mg.vertex()(i, Is[1].getBase(), j - 1, axis1);
					double xi2 = mg.vertex()(i, Is[1].getBase(), j + 1, axis1);
					double xs2 = mg.vertex()(i, Is[1].getBase(), bound2, axis1);
					double xn2 = mg.vertex()(i, Is[1].getBase(), bound2, axis1);
					int inc_2_counts = 0;
					int dec_2_counts = 0;

					// counts number of incrementable points in the "2" direction index (exclude hole points)

					while ((j + 1) + inc_2_counts <= bound2 and mg.mask()(i, Is[1].getBase(), (j + 1) + inc_2_counts) != 0)
					{
						inc_2_counts++;
					}

					// counts number of decrementable points in the "2" direction index (exclude hole points)

					while ((j - 1) - dec_2_counts >= base2 and mg.mask()(i, Is[1].getBase(), (j - 1) - dec_2_counts) != 0)
					{
						dec_2_counts++;
					}

					// calculate range and coefficienst

					if (((fabs(xd2 - xi2) <= tolb) and ((fabs(xc) > fabs(xd2) and fabs(xc) > fabs(xi2)) or fabs(xs2 - xn2) <= tols)) or U_ == 0) // neutral or centered stencil
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind2x = UPWIND_STENCIL_TYPES::NEUTRAL; //"neu";
						else
							vertexData_[surface][i][j].ind2x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						int half = (u_ + d_) / 2;
						int a = min(min(half, dec_2_counts), min(half, inc_2_counts));
						d2 = u2 = a;

						vertexData_[surface][i][j].u2x = a;
						vertexData_[surface][i][j].d2x = a;
						vertexData_[surface][i][j].R2x = Range(j - a, j + a);
						vertexData_[surface][i][j].C2x = FdCoefficients(a, a, 1);
					}
					else if (U_ * xd2 > U_ * xc) // biased by decrementing
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind2x = UPWIND_STENCIL_TYPES::DECREM; //"dec";
						else
							vertexData_[surface][i][j].ind2x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						u2 = min(u_, dec_2_counts);
						d2 = min(d_, inc_2_counts);
						if (d2 >= u2 and u_ != d_)
							d2 = u2 - 1;

						vertexData_[surface][i][j].u2x = u2;
						vertexData_[surface][i][j].d2x = d2;
						vertexData_[surface][i][j].R2x = Range(j - u2, j + d2);

						if (U_ * vertexData_[surface][i][j].vder2x > 0)
						{
							vertexData_[surface][i][j].C2x = FdCoefficients(d2, u2, 1);
							flipArray_(vertexData_[surface][i][j].C2x);
						}
						else
						{
							vertexData_[surface][i][j].C2x = FdCoefficients(u2, d2, 1);
						}
					}
					else // biased by incrementing
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind2x = UPWIND_STENCIL_TYPES::INCREM; //"inc";
						else
							vertexData_[surface][i][j].ind2x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						u2 = min(u_, inc_2_counts);
						d2 = min(d_, dec_2_counts);
						if (d2 >= u2 and u_ != d_)
							d2 = u2 - 1;

						vertexData_[surface][i][j].u2x = u2;
						vertexData_[surface][i][j].d2x = d2;
						vertexData_[surface][i][j].R2x = Range(j - d2, j + u2);

						if (U_ * vertexData_[surface][i][j].vder2x > 0)
						{
							vertexData_[surface][i][j].C2x = FdCoefficients(d2, u2, 1);
						}
						else
						{
							vertexData_[surface][i][j].C2x = FdCoefficients(u2, d2, 1);
							flipArray_(vertexData_[surface][i][j].C2x);
						}
					}

					vertexData_[surface][i][j].C2x.reshape(1, 1, u2 + d2 + 1);

				} // end of 3D check
				else
				{
					vertexData_[surface][i][j].R2x = Range(0, 0);
					vertexData_[surface][i][j].C2x.resize(1, 1, 1);
					vertexData_[surface][i][j].C2x(0, 0, 0) = 0.0;
					vertexData_[surface][i][j].vder2x = 0.0;
				}

				if (printx_)
				{
					// print to file
					int range_0_base = vertexData_[surface][i][j].R0x.getBase();
					int range_0_bound = vertexData_[surface][i][j].R0x.getBound();
					int range_2_base = vertexData_[surface][i][j].R2x.getBase();
					int range_2_bound = vertexData_[surface][i][j].R2x.getBound();

					xfout << UpwindStencilsPrintTags.at(vertexData_[surface][i][j].ind0x)
						  << setw(sw) << vertexData_[surface][i][j].d0x << setw(sw) << vertexData_[surface][i][j].u0x
						  << setw(mw) << " start = " << range_0_base << setw(sw) << " end = " << range_0_bound << setw(sw) << " : ";

					for (int p = range_0_base; p <= range_0_bound; p++)
					{
						xfout << setw(bw) << mg.vertex()(p, Is[1].getBase(), j, axis1) << setw(bw);
					}

					xfout << '\n';

					xfout << setw(BW) << " coefficients : " << setw(bw);

					int c01 = vertexData_[surface][i][j].C0x.getBound(1);
					int c02 = vertexData_[surface][i][j].C0x.getBound(2);

					for (int cof = 0; cof < vertexData_[surface][i][j].C0x.getLength(0); cof++)
					{
						xfout << setw(bw) << vertexData_[surface][i][j].C0x(cof, c01, c02) << setw(bw);
					}

					xfout << '\n';

					if (vertexData_[surface][i][j].R2x.length() > 1)
					{
						xfout << UpwindStencilsPrintTags.at(vertexData_[surface][i][j].ind2x);
						xfout << setw(sw) << vertexData_[surface][i][j].d2x << setw(sw) << vertexData_[surface][i][j].u2x << setw(mw)
							  << " start = " << range_2_base << setw(sw) << " end = " << range_2_bound << setw(sw) << " : ";

						for (int p = range_2_base; p <= range_2_bound; p++)
						{
							xfout << setw(bw) << mg.vertex()(i, Is[1].getBase(), p, axis1) << setw(bw);
						}

						xfout << '\n';

						xfout << setw(BW) << " coefficients : " << setw(bw);

						int c20 = vertexData_[surface][i][j].C2x.getBound(0);
						int c21 = vertexData_[surface][i][j].C2x.getBound(1);

						for (int cof = 0; cof < vertexData_[surface][i][j].C2x.getLength(2); cof++)
						{
							xfout << setw(bw) << vertexData_[surface][i][j].C2x(c20, c21, cof) << setw(bw);
						}

						xfout << "\n\n";
					}

				} // End of print

			} // End of positive mask

		} // End of j

		if (printx_)
		{
			xfout << "****" << '\n';
		}

	} // End of i

	// -----------------------------------------------------------------------------------------------------------------------------------
	// -----------------------------------------------------------------------------------------------------------------------------------
	//
	//                                                UPWIND STENCIL FOR Z DERIVATIVES
	//
	// -----------------------------------------------------------------------------------------------------------------------------------
	// -----------------------------------------------------------------------------------------------------------------------------------

	if (mg.numberOfDimensions() == 3)
	{
		string zfilename = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name + "/" + upwind_z_coefficients_file + DoubleToString(surface);
		ofstream zfout;

		if (printz_)
		{
			zfout.open(zfilename);
			zfout << "Upwind z coefficients " + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << "\n\n";
			zfout.precision(prec);
		}

		for (i = Is[0].getBase(); i <= Is[0].getBound(); i++)
		{
			for (j = Is[2].getBase(); j <= Is[2].getBound(); j++)
			{
				vertexData_[surface][i][j].mask = mg.mask()(i, Is[1].getBase(), j);

				double uzLocal = d_phib_dz[surface](i, Is[1].getBase(), j);

				if (mg.mask()(i, Is[1].getBase(), j) > 0) // just for discretisation points
				{
					double zc = mg.vertex()(i, Is[1].getBase(), j, axis3);

					// -------------------------------------------------------------------------
					//
					//                                  INDEX "0"
					//
					// -------------------------------------------------------------------------

					int d0, u0; // number of points downwind and upwind along index "0"

					vertexData_[surface][i][j].vder0z = mg.inverseVertexDerivative()(i, Is[1].getBase(), j, 0, 2); // dr0_dz

					double zd0 = mg.vertex()(i - 1, Is[1].getBase(), j, axis3);
					double zi0 = mg.vertex()(i + 1, Is[1].getBase(), j, axis3);
					double zs0 = mg.vertex()(base0, Is[1].getBase(), j, axis3);
					double zn0 = mg.vertex()(bound0, Is[1].getBase(), j, axis3);
					int inc_0_counts = 0;
					int dec_0_counts = 0;

					// counts number of incrementable points in the "0" direction index (exclude hole points)

					while ((i + 1) + inc_0_counts <= bound0 and mg.mask()((i + 1) + inc_0_counts, Is[1].getBase(), j) != 0)
					{
						inc_0_counts++;
					}

					// counts number of decrementable points in the "0" direction index (exclude hole points)

					while ((i - 1) - dec_0_counts >= base0 and mg.mask()((i - 1) - dec_0_counts, Is[1].getBase(), j) != 0)
					{
						dec_0_counts++;
					}

					// calculate range and coefficienst

					if (((fabs(zd0 - zi0) <= tolb) and ((fabs(zc) > fabs(zd0) and fabs(zc) > fabs(zi0)) or fabs(zs0 - zn0) <= tols)) or U_ == 0 or uzLocal == 0) // neutral or centered stencil
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind0z = UPWIND_STENCIL_TYPES::NEUTRAL; //"neu";
						else
							vertexData_[surface][i][j].ind0z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						int half = (u_ + d_) / 2;
						int a = min(min(half, dec_0_counts), min(half, inc_0_counts));
						u0 = d0 = a;

						vertexData_[surface][i][j].u0z = a;
						vertexData_[surface][i][j].d0z = a;
						vertexData_[surface][i][j].R0z = Range(i - a, i + a);
						vertexData_[surface][i][j].C0z = FdCoefficients(a, a, 1);
					}
					else if (uzLocal * zd0 > uzLocal * zc) // biased by decrementing
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind0z = UPWIND_STENCIL_TYPES::DECREM; //"dec";
						else
							vertexData_[surface][i][j].ind0z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						u0 = min(u_, dec_0_counts);
						d0 = min(d_, inc_0_counts);
						if (d0 >= u0 and u_ != d_)
							d0 = u0 - 1;

						vertexData_[surface][i][j].u0z = u0;
						vertexData_[surface][i][j].d0z = d0;
						vertexData_[surface][i][j].R0z = Range(i - u0, i + d0);

						if (uzLocal * vertexData_[surface][i][j].vder0z > 0)
						{
							vertexData_[surface][i][j].C0z = FdCoefficients(d0, u0, 1);
							flipArray_(vertexData_[surface][i][j].C0z);
						}
						else
						{
							vertexData_[surface][i][j].C0z = FdCoefficients(u0, d0, 1);
						}
					}
					else // biased by incrementing
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind0z = UPWIND_STENCIL_TYPES::INCREM; //"inc";
						else
							vertexData_[surface][i][j].ind0z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						u0 = min(u_, inc_0_counts);
						d0 = min(d_, dec_0_counts);
						if (d0 >= u0 and u_ != d_)
							d0 = u0 - 1;

						vertexData_[surface][i][j].u0z = u0;
						vertexData_[surface][i][j].d0z = d0;
						vertexData_[surface][i][j].R0z = Range(i - d0, i + u0);

						if (uzLocal * vertexData_[surface][i][j].vder0z > 0)
						{
							vertexData_[surface][i][j].C0z = FdCoefficients(d0, u0, 1);
						}
						else
						{
							vertexData_[surface][i][j].C0z = FdCoefficients(u0, d0, 1);
							flipArray_(vertexData_[surface][i][j].C0z);
						}
					}

					// -------------------------------------------------------------------------
					//
					//                               INDEX "2"
					//
					// -------------------------------------------------------------------------

					int d2, u2; // number of points downwind and upwind along index "2"

					vertexData_[surface][i][j].vder2z = mg.inverseVertexDerivative()(i, Is[1].getBase(), j, 2, 2); // dr2_dz

					double zd2 = mg.vertex()(i, Is[1].getBase(), j - 1, axis3);
					double zi2 = mg.vertex()(i, Is[1].getBase(), j + 1, axis3);
					double zs2 = mg.vertex()(i, Is[1].getBase(), bound2, axis3);
					double zn2 = mg.vertex()(i, Is[1].getBase(), bound2, axis3);
					int inc_2_counts = 0;
					int dec_2_counts = 0;

					// counts number of incrementable points in the "2" direction index (exclude hole points)

					while ((j + 1) + inc_2_counts <= bound2 and mg.mask()(i, Is[1].getBase(), (j + 1) + inc_2_counts) != 0)
					{
						inc_2_counts++;
					}

					// counts number of decrementable points in the "2" direction index (exclude hole points)

					while ((j - 1) - dec_2_counts >= base2 and mg.mask()(i, Is[1].getBase(), (j - 1) - dec_2_counts) != 0)
					{
						dec_2_counts++;
					}

					// calculate range and coefficienst

					if (((fabs(zd2 - zi2) <= tolb) and ((fabs(zc) > fabs(zd2) and fabs(zc) > fabs(zi2)) or fabs(zs2 - zn2) <= tols)) or U_ == 0 or uzLocal == 0) // neutral or centered stencil
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind2z = UPWIND_STENCIL_TYPES::NEUTRAL; //"neu";
						else
							vertexData_[surface][i][j].ind2z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						int half = (u_ + d_) / 2;
						int a = min(min(half, dec_2_counts), min(half, inc_2_counts));
						d2 = u2 = a;

						vertexData_[surface][i][j].u2z = a;
						vertexData_[surface][i][j].d2z = a;
						vertexData_[surface][i][j].R2z = Range(j - a, j + a);
						vertexData_[surface][i][j].C2z = FdCoefficients(a, a, 1);
					}
					else if (uzLocal * zd2 > uzLocal * zc) // biased by decrementing
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind2z = UPWIND_STENCIL_TYPES::DECREM; //"dec";
						else
							vertexData_[surface][i][j].ind2z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						u2 = min(u_, dec_2_counts);
						d2 = min(d_, inc_2_counts);
						if (d2 >= u2 and u_ != d_)
							d2 = u2 - 1;

						vertexData_[surface][i][j].u2z = u2;
						vertexData_[surface][i][j].d2z = d2;
						vertexData_[surface][i][j].R2z = Range(j - u2, j + d2);

						if (uzLocal * vertexData_[surface][i][j].vder2z > 0)
						{
							vertexData_[surface][i][j].C2z = FdCoefficients(d2, u2, 1);
							flipArray_(vertexData_[surface][i][j].C2z);
						}
						else
						{
							vertexData_[surface][i][j].C2z = FdCoefficients(u2, d2, 1);
						}
					}
					else // biased by incrementing
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind2z = UPWIND_STENCIL_TYPES::INCREM; //"inc";
						else
							vertexData_[surface][i][j].ind2z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						u2 = min(u_, inc_2_counts);
						d2 = min(d_, dec_2_counts);
						if (d2 >= u2 and u_ != d_)
							d2 = u2 - 1;

						vertexData_[surface][i][j].u2z = u2;
						vertexData_[surface][i][j].d2z = d2;
						vertexData_[surface][i][j].R2z = Range(j - d2, j + u2);

						if (uzLocal * vertexData_[surface][i][j].vder2z > 0)
						{
							vertexData_[surface][i][j].C2z = FdCoefficients(d2, u2, 1);
						}
						else
						{
							vertexData_[surface][i][j].C2z = FdCoefficients(u2, d2, 1);
							flipArray_(vertexData_[surface][i][j].C2z);
						}
					}

					vertexData_[surface][i][j].C2z.reshape(1, 1, u2 + d2 + 1);

					if (printz_)
					{
						// print to file
						int range_0_base = vertexData_[surface][i][j].R0z.getBase();
						int range_0_bound = vertexData_[surface][i][j].R0z.getBound();
						int range_2_base = vertexData_[surface][i][j].R2z.getBase();
						int range_2_bound = vertexData_[surface][i][j].R2z.getBound();

						zfout << UpwindStencilsPrintTags.at(vertexData_[surface][i][j].ind0z)
							  << setw(sw) << vertexData_[surface][i][j].d0z << setw(sw) << vertexData_[surface][i][j].u0z
							  << setw(mw) << " start = " << range_0_base << setw(sw) << " end = " << range_0_bound << setw(sw) << " : ";

						for (int p = range_0_base; p <= range_0_bound; p++)
						{
							zfout << setw(bw) << mg.vertex()(p, Is[1].getBase(), j, axis3) << setw(bw);
						}

						zfout << '\n';

						zfout << setw(BW) << " coefficients : " << setw(bw);

						int c01 = vertexData_[surface][i][j].C0z.getBound(1);
						int c02 = vertexData_[surface][i][j].C0z.getBound(2);

						for (int cof = 0; cof < vertexData_[surface][i][j].C0z.getLength(0); cof++)
						{
							zfout << setw(bw) << vertexData_[surface][i][j].C0z(cof, c01, c02) << setw(bw);
						}

						zfout << '\n';

						if (vertexData_[surface][i][j].R2z.length() > 1)
						{
							zfout << UpwindStencilsPrintTags.at(vertexData_[surface][i][j].ind2z);
							zfout << setw(sw) << vertexData_[surface][i][j].d2z << setw(sw) << vertexData_[surface][i][j].u2z << setw(mw)
								  << " start = " << range_2_base << setw(sw) << " end = " << range_2_bound << setw(sw) << " : ";

							for (int p = range_2_base; p <= range_2_bound; p++)
							{
								zfout << setw(bw) << mg.vertex()(i, Is[1].getBase(), p, axis3) << setw(bw);
							}

							zfout << '\n';

							zfout << setw(BW) << " coefficients : " << setw(bw);

							int c20 = vertexData_[surface][i][j].C2z.getBound(0);
							int c21 = vertexData_[surface][i][j].C2z.getBound(1);

							for (int cof = 0; cof < vertexData_[surface][i][j].C2z.getLength(2); cof++)
							{
								zfout << setw(bw) << vertexData_[surface][i][j].C2z(c20, c21, cof) << setw(bw);
							}

							zfout << "\n\n";
						}

					} // End of print

				} // End of positive mask

			} // End of j

			if (printz_)
			{
				zfout << "****" << '\n';
			}

		} // End of i

	} // End of 3d grid check

	else // For 2D grids
	{
		for (i = Is[0].getBase(); i <= Is[0].getBound(); i++)
		{
			for (j = Is[2].getBase(); j <= Is[2].getBound(); j++)
			{
				vertexData_[surface][i][j].R0z = Range(0, 0);
				vertexData_[surface][i][j].C0z.resize(1, 1, 1);
				vertexData_[surface][i][j].C0z(0, 0, 0) = 0.0;
				vertexData_[surface][i][j].vder0z = 0.0;

				vertexData_[surface][i][j].R2z = Range(0, 0);
				vertexData_[surface][i][j].C2z.resize(1, 1, 1);
				vertexData_[surface][i][j].C2z(0, 0, 0) = 0.0;
				vertexData_[surface][i][j].vder2z = 0.0;
			}
		}
	}

} // End of biased_0_2_ private member function
