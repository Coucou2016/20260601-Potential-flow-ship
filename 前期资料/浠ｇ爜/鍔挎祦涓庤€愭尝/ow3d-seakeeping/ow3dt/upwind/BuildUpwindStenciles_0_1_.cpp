// Note : This part of the class is implemented here due to readibility of the main implementation file.

// -------------------------------------------------------------------------
// search along index "0" and "1" over the free-surface which has index "2"
// -------------------------------------------------------------------------

#include "Upwind.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Upwind::BuildUpwindStenciles_0_1_(
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
	int bound1 = I[1].getBound();
	int base0 = I[0].getBase();
	int base1 = I[1].getBase();

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
		for (j = Is[1].getBase(); j <= Is[1].getBound(); j++)
		{
			vertexData_[surface][i][j].mask = mg.mask()(i, j, Is[2].getBase());

			if (mg.mask()(i, j, Is[2].getBase()) > 0) // just for discretisation points
			{
				double xc = mg.vertex()(i, j, Is[2].getBase(), axis1);

				// -------------------------------------------------------------------------
				//
				//                                   INDEX "0"
				//
				// -------------------------------------------------------------------------

				int d0, u0; // number of points downwind and upwind along index "0"

				vertexData_[surface][i][j].vder0x = mg.inverseVertexDerivative()(Is[0].getBase(), i, j, 0, 0); // dr0_dx

				double xd0 = mg.vertex()(i - 1, j, Is[2].getBase(), axis1);
				double xi0 = mg.vertex()(i + 1, j, Is[2].getBase(), axis1);
				double xs0 = mg.vertex()(base0, j, Is[2].getBase(), axis1);
				double xn0 = mg.vertex()(bound0, j, Is[2].getBase(), axis1);
				int inc_0_counts = 0;
				int dec_0_counts = 0;

				// counts number of incrementable points in the "0" direction index (exclude hole points)

				while ((i + 1) + inc_0_counts <= bound0 and mg.mask()((i + 1) + inc_0_counts, j, Is[2].getBase()) != 0)
				{
					inc_0_counts++;
				}

				// counts number of decrementable points in the "0" direction index (exclude hole points)

				while ((i - 1) - dec_0_counts >= base0 and mg.mask()((i - 1) - dec_0_counts, j, Is[2].getBase()) != 0)
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
					d0 = u0 = a;

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
				//                                 INDEX "1"
				//
				// -------------------------------------------------------------------------

				int d1, u1; // number of points downwind and upwind along index "1"

				vertexData_[surface][i][j].vder1x = mg.inverseVertexDerivative()(Is[0].getBase(), i, j, 1, 0); // dr1_dx

				double xd1 = mg.vertex()(i, j - 1, Is[2].getBase(), axis1);
				double xi1 = mg.vertex()(i, j + 1, Is[2].getBase(), axis1);
				double xs1 = mg.vertex()(i, base1, Is[2].getBase(), axis1);
				double xn1 = mg.vertex()(i, bound1, Is[2].getBase(), axis1);
				int inc_1_counts = 0;
				int dec_1_counts = 0;

				// counts number of incrementable points in the "1" direction index (exclude hole points)

				while ((j + 1) + inc_1_counts <= bound1 and mg.mask()(i, (j + 1) + inc_1_counts, Is[2].getBase()) != 0)
				{
					inc_1_counts++;
				}

				// counts number of decrementable points in the "1" direction index (exclude hole points)

				while ((j - 1) - dec_1_counts >= base1 and mg.mask()(i, (j - 1) - dec_1_counts, Is[2].getBase()) != 0)
				{
					dec_1_counts++;
				}

				// calculate range and coefficienst

				if (((fabs(xd1 - xi1) <= tolb) and ((fabs(xc) > fabs(xd1) and fabs(xc) > fabs(xi1)) or fabs(xs1 - xn1) <= tols)) or U_ == 0) // neutral or centered stencil
				{
					if (u_ != d_)
						vertexData_[surface][i][j].ind1x = UPWIND_STENCIL_TYPES::NEUTRAL; //"neu";
					else
						vertexData_[surface][i][j].ind1x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

					// viable stencil
					int half = (u_ + d_) / 2;
					int a = min(min(half, dec_1_counts), min(half, inc_1_counts));
					d1 = u1 = a;

					vertexData_[surface][i][j].u1x = a;
					vertexData_[surface][i][j].d1x = a;
					vertexData_[surface][i][j].R1x = Range(j - a, j + a);
					vertexData_[surface][i][j].C1x = FdCoefficients(a, a, 1);
				}
				else if (U_ * xd1 > U_ * xc) // biased by decrementing
				{
					if (u_ != d_)
						vertexData_[surface][i][j].ind1x = UPWIND_STENCIL_TYPES::DECREM; //"dec";
					else
						vertexData_[surface][i][j].ind1x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

					// viable stencil
					u1 = min(u_, dec_1_counts);
					d1 = min(d_, inc_1_counts);
					if (d1 >= u1 and u_ != d_)
						d1 = u1 - 1;

					vertexData_[surface][i][j].u1x = u1;
					vertexData_[surface][i][j].d1x = d1;
					vertexData_[surface][i][j].R1x = Range(j - u1, j + d1);

					if (U_ * vertexData_[surface][i][j].vder1x > 0)
					{
						vertexData_[surface][i][j].C1x = FdCoefficients(d1, u1, 1);
						flipArray_(vertexData_[surface][i][j].C1x);
					}
					else
					{
						vertexData_[surface][i][j].C1x = FdCoefficients(u1, d1, 1);
					}
				}
				else // biased by incrementing
				{
					if (u_ != d_)
						vertexData_[surface][i][j].ind1x = UPWIND_STENCIL_TYPES::INCREM; //"inc";
					else
						vertexData_[surface][i][j].ind1x = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

					// viable stencil
					u1 = min(u_, inc_1_counts);
					d1 = min(d_, dec_1_counts);
					if (d1 >= u1 and u_ != d_)
						d1 = u1 - 1;

					vertexData_[surface][i][j].u1x = u1;
					vertexData_[surface][i][j].d1x = d1;
					vertexData_[surface][i][j].R1x = Range(j - d1, j + u1);

					if (U_ * vertexData_[surface][i][j].vder1x > 0)
					{
						vertexData_[surface][i][j].C1x = FdCoefficients(d1, u1, 1);
					}
					else
					{
						vertexData_[surface][i][j].C1x = FdCoefficients(u1, d1, 1);
						flipArray_(vertexData_[surface][i][j].C1x);
					}
				}

				vertexData_[surface][i][j].C1x.reshape(1, d1 + u1 + 1);

				if (printx_)
				{
					// print to file
					int range_0_base = vertexData_[surface][i][j].R0x.getBase();
					int range_0_bound = vertexData_[surface][i][j].R0x.getBound();
					int range_1_base = vertexData_[surface][i][j].R1x.getBase();
					int range_1_bound = vertexData_[surface][i][j].R1x.getBound();

					xfout << UpwindStencilsPrintTags.at(vertexData_[surface][i][j].ind0x)
						  << setw(sw) << vertexData_[surface][i][j].d0x << setw(sw) << vertexData_[surface][i][j].u0x
						  << setw(mw) << " start = " << range_0_base << setw(sw) << " end = " << range_0_bound << setw(sw) << " : ";

					for (int p = range_0_base; p <= range_0_bound; p++)
					{
						xfout << setw(bw) << mg.vertex()(p, j, Is[2].getBase(), axis1) << setw(bw);
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

					xfout << UpwindStencilsPrintTags.at(vertexData_[surface][i][j].ind1x);
					xfout << setw(sw) << vertexData_[surface][i][j].d1x << setw(sw) << vertexData_[surface][i][j].u1x << setw(mw)
						  << " start = " << range_1_base << setw(sw) << " end = " << range_1_bound << setw(sw) << " : ";

					for (int p = range_1_base; p <= range_1_bound; p++)
					{
						xfout << setw(bw) << mg.vertex()(i, p, Is[2].getBase(), axis1) << setw(bw);
					}

					xfout << '\n';

					xfout << setw(BW) << " coefficients : " << setw(bw);

					int c10 = vertexData_[surface][i][j].C1x.getBound(0);
					int c12 = vertexData_[surface][i][j].C1x.getBound(2);

					for (int cof = 0; cof < vertexData_[surface][i][j].C1x.getLength(1); cof++)
					{
						xfout << setw(bw) << vertexData_[surface][i][j].C1x(c10, cof, c12) << setw(bw);
					}

					xfout << "\n\n";
				}

			} // end of positive mask

		} // end of j

		if (printx_)
		{
			xfout << "****" << '\n';
		}

	} // end of i

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
			for (j = Is[1].getBase(); j <= Is[1].getBound(); j++)
			{
				vertexData_[surface][i][j].mask = mg.mask()(i, j, Is[2].getBase());

				double uzLocal = d_phib_dz[surface](i, j, Is[2].getBase());

				if (mg.mask()(i, j, Is[2].getBase()) > 0) // just for discretisation points
				{
					double zc = mg.vertex()(i, j, Is[2].getBase(), axis3);

					// -------------------------------------------------------------------------
					//
					//                                   INDEX "0"
					//
					// -------------------------------------------------------------------------

					int d0, u0; // number of points downwind and upwind along index "0"

					vertexData_[surface][i][j].vder0z = mg.inverseVertexDerivative()(Is[0].getBase(), i, j, 0, 2); // dr0_dz

					double zd0 = mg.vertex()(i - 1, j, Is[2].getBase(), axis3);
					double zi0 = mg.vertex()(i + 1, j, Is[2].getBase(), axis3);
					double zs0 = mg.vertex()(base0, j, Is[2].getBase(), axis3);
					double zn0 = mg.vertex()(bound0, j, Is[2].getBase(), axis3);
					int inc_0_counts = 0;
					int dec_0_counts = 0;

					// counts number of incrementable points in the "0" direction index (exclude hole points)

					while ((i + 1) + inc_0_counts <= bound0 and mg.mask()((i + 1) + inc_0_counts, j, Is[2].getBase()) != 0)
					{
						inc_0_counts++;
					}

					// counts number of decrementable points in the "0" direction index (exclude hole points)

					while ((i - 1) - dec_0_counts >= base0 and mg.mask()((i - 1) - dec_0_counts, j, Is[2].getBase()) != 0)
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
						d0 = u0 = a;

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
					//                                 INDEX "1"
					//
					// -------------------------------------------------------------------------

					int d1, u1; // number of points downwind and upwind along index "1"

					vertexData_[surface][i][j].vder1z = mg.inverseVertexDerivative()(Is[0].getBase(), i, j, 1, 2); // dr1_dz

					double zd1 = mg.vertex()(i, j - 1, Is[2].getBase(), axis3);
					double zi1 = mg.vertex()(i, j + 1, Is[2].getBase(), axis3);
					double zs1 = mg.vertex()(i, base1, Is[2].getBase(), axis3);
					double zn1 = mg.vertex()(i, bound1, Is[2].getBase(), axis3);
					int inc_1_counts = 0;
					int dec_1_counts = 0;

					// counts number of incrementable points in the "1" direction index (exclude hole points)

					while ((j + 1) + inc_1_counts <= bound1 and mg.mask()(i, (j + 1) + inc_1_counts, Is[2].getBase()) != 0)
					{
						inc_1_counts++;
					}

					// counts number of decrementable points in the "1" direction index (exclude hole points)

					while ((j - 1) - dec_1_counts >= base1 and mg.mask()(i, (j - 1) - dec_1_counts, Is[2].getBase()) != 0)
					{
						dec_1_counts++;
					}

					// calculate range and coefficienst

					if (((fabs(zd1 - zi1) <= tolb) and ((fabs(zc) > fabs(zd1) and fabs(zc) > fabs(zi1)) or fabs(zs1 - zn1) <= tols)) or U_ == 0 or uzLocal == 0) // neutral or centered stencil
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind1z = UPWIND_STENCIL_TYPES::NEUTRAL; //"neu";
						else
							vertexData_[surface][i][j].ind1z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						int half = (u_ + d_) / 2;
						int a = min(min(half, dec_1_counts), min(half, inc_1_counts));
						d1 = u1 = a;

						vertexData_[surface][i][j].u1z = a;
						vertexData_[surface][i][j].d1z = a;
						vertexData_[surface][i][j].R1z = Range(j - a, j + a);
						vertexData_[surface][i][j].C1z = FdCoefficients(a, a, 1);
					}
					else if (uzLocal * zd1 > uzLocal * zc) // biased by decrementing
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind1z = UPWIND_STENCIL_TYPES::DECREM; //"dec";
						else
							vertexData_[surface][i][j].ind1z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						u1 = min(u_, dec_1_counts);
						d1 = min(d_, inc_1_counts);
						if (d1 >= u1 and u_ != d_)
							d1 = u1 - 1;

						vertexData_[surface][i][j].u1z = u1;
						vertexData_[surface][i][j].d1z = d1;
						vertexData_[surface][i][j].R1z = Range(j - u1, j + d1);

						if (uzLocal * vertexData_[surface][i][j].vder1z > 0)
						{
							vertexData_[surface][i][j].C1z = FdCoefficients(d1, u1, 1);
							flipArray_(vertexData_[surface][i][j].C1z);
						}
						else
						{
							vertexData_[surface][i][j].C1z = FdCoefficients(u1, d1, 1);
						}
					}
					else // biased by incrementing
					{
						if (u_ != d_)
							vertexData_[surface][i][j].ind1z = UPWIND_STENCIL_TYPES::INCREM; //"inc";
						else
							vertexData_[surface][i][j].ind1z = UPWIND_STENCIL_TYPES::CENTRAL; //"cen";

						// viable stencil
						u1 = min(u_, inc_1_counts);
						d1 = min(d_, dec_1_counts);
						if (d1 >= u1 and u_ != d_)
							d1 = u1 - 1;

						vertexData_[surface][i][j].u1z = u1;
						vertexData_[surface][i][j].d1z = d1;
						vertexData_[surface][i][j].R1z = Range(j - d1, j + u1);

						if (uzLocal * vertexData_[surface][i][j].vder1z > 0)
						{
							vertexData_[surface][i][j].C1z = FdCoefficients(d1, u1, 1);
						}
						else
						{
							vertexData_[surface][i][j].C1z = FdCoefficients(u1, d1, 1);
							flipArray_(vertexData_[surface][i][j].C1z);
						}
					}

					vertexData_[surface][i][j].C1z.reshape(1, d1 + u1 + 1);

					if (printz_)
					{
						// print to file
						int range_0_base = vertexData_[surface][i][j].R0z.getBase();
						int range_0_bound = vertexData_[surface][i][j].R0z.getBound();
						int range_1_base = vertexData_[surface][i][j].R1z.getBase();
						int range_1_bound = vertexData_[surface][i][j].R1z.getBound();

						zfout << UpwindStencilsPrintTags.at(vertexData_[surface][i][j].ind0z)
							  << setw(sw) << vertexData_[surface][i][j].d0z << setw(sw) << vertexData_[surface][i][j].u0z
							  << setw(mw) << " start = " << range_0_base << setw(sw) << " end = " << range_0_bound << setw(sw) << " : ";

						for (int p = range_0_base; p <= range_0_bound; p++)
						{
							zfout << setw(bw) << mg.vertex()(p, j, Is[2].getBase(), axis3) << setw(bw);
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

						zfout << UpwindStencilsPrintTags.at(vertexData_[surface][i][j].ind1z);
						zfout << setw(sw) << vertexData_[surface][i][j].d1z << setw(sw) << vertexData_[surface][i][j].u1z << setw(mw)
							  << " start = " << range_1_base << setw(sw) << " end = " << range_1_bound << setw(sw) << " : ";

						for (int p = range_1_base; p <= range_1_bound; p++)
						{
							zfout << setw(bw) << mg.vertex()(i, p, Is[2].getBase(), axis3) << setw(bw);
						}

						zfout << '\n';

						zfout << setw(BW) << " coefficients : " << setw(bw);

						int c10 = vertexData_[surface][i][j].C1z.getBound(0);
						int c12 = vertexData_[surface][i][j].C1z.getBound(2);

						for (int cof = 0; cof < vertexData_[surface][i][j].C1z.getLength(1); cof++)
						{
							zfout << setw(bw) << vertexData_[surface][i][j].C1z(c10, cof, c12) << setw(bw);
						}

						zfout << "\n\n";
					}

				} // End of positive mask

			} // End of j

			if (printz_)
			{
				zfout << "****" << '\n';
			}

		} // End of i

	} // End of 3d grid check

	else // For 2d grids
	{
		for (i = Is[0].getBase(); i <= Is[0].getBound(); i++)
		{
			for (j = Is[1].getBase(); j <= Is[1].getBound(); j++)
			{
				vertexData_[surface][i][j].R0z = Range(0, 0);
				vertexData_[surface][i][j].C0z.resize(1, 1, 1);
				vertexData_[surface][i][j].C0z(0, 0, 0) = 0.0;
				vertexData_[surface][i][j].vder0z = 0.0; // dr0_dz

				vertexData_[surface][i][j].R1z = Range(0, 0);
				vertexData_[surface][i][j].C1z.resize(1, 1, 1);
				vertexData_[surface][i][j].C1z(0, 0, 0) = 0.0;
				vertexData_[surface][i][j].vder1z = 0.0; // dr1_dz
			}
		}
	}

} // End of biased_0_1_ private member function
