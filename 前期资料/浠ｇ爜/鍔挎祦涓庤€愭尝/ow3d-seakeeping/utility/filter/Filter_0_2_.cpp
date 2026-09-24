// Note : This part of the class is implemented here due to just readibility of the main implementation file.

// filter along index "0" and "2" over the free-surface which has index "1"

#include "Filter.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Filter::Filter_0_2_(
	unsigned int surface,
	const MappedGrid &mg,
	const vector<Index> &Is)
{
	int sw = 5;	  // used for file formatting
	int bw = 10;  // used for file formatting
	int prec = 3; // used for file formatting

	string filename = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name + "/" + "filter_s" + DoubleToString(surface) + ".txt";

	ofstream fout;

	if (print_)
	{
		fout.open(filename);
		fout.precision(prec);
	}

	int i, j;

	int bound0 = Is[0].getBound();
	int bound2 = Is[2].getBound();
	int base0 = Is[0].getBase();
	int base2 = Is[2].getBase();

	for (i = Is[0].getBase(); i <= Is[0].getBound(); i++)
	{
		for (j = Is[2].getBase(); j <= Is[2].getBound(); j++)
		{
			vertexData_[surface][i][j].mask = mg.mask()(i, Is[1].getBase(), j); // we need this when applying the filter

			if (mg.mask()(i, Is[1].getBase(), j) > 0) // just for discretisation points
			{
				//----------------------------------------------------------------
				//
				//                         ALONG INDEX "0"
				//
				// ---------------------------------------------------------------

				int d0_elig = 0; // number of eligible points down
				int u0_elig = 0; // number of eligible points up
				int d0, u0;		 // number of points down and up along index "0" (decided finally)

				// Counts number of eligible points in the "0" up direction index (exclude hole points and ghost points)

				while ((i + 1) + u0_elig <= bound0 and mg.mask()((i + 1) + u0_elig, Is[1].getBase(), j) != 0)
				{
					u0_elig++;
				}

				// Counts number of eligible points in the "0" down direction index (exclude hole points and ghost points)

				while ((i - 1) - d0_elig >= base0 and mg.mask()((i - 1) - d0_elig, Is[1].getBase(), j) != 0)
				{
					d0_elig++;
				}

				// Determine a viable stencil and assign the range and the coefficients

				if (u0_elig >= HW_ and d0_elig >= HW_) // user defined centered stencil is possible
				{
					u0 = d0 = HW_;
					vertexData_[surface][i][j].C0 = c_;
					vertexData_[surface][i][j].f0 = f_;
				}

				else if (d0_elig >= hw_ and u0_elig >= hw_) // use a centered stencil smaller than the user definded one, but bigger than mhw_
				{
					d0 = u0 = min(d0_elig, u0_elig);

					int width = 2 * d0 + 1;
					int order = width - d_; // order is less by d_

					RealArray f(1, 1, width), C(1, 1, width);
					f = 0;
					f(0, 0, d0) = 1;

					double *c = new double[width];
					Savgol(c, width, d0, d0, 0, order);

					for (int sg = 0; sg < width; sg++)
					{
						if (sg == d0)
						{
							C(0, 0, sg) = 1 - c[sg];
						}
						else
						{
							C(0, 0, sg) = -c[sg]; // note Berland (2007) notation!
						}
					}
					delete[] c;

					vertexData_[surface][i][j].C0 = C;
					vertexData_[surface][i][j].f0 = f;

				} // end of program defined centered stencil

				else if ((d0_elig >= 0 and u0_elig >= 3) || (u0_elig >= 0 and d0_elig >= 3)) // Berland stencil is possible
				{
					if (d0_elig >= 4 and u0_elig >= 6) // S46
					{
						d0 = 4;
						u0 = 6;

						vertexData_[surface][i][j].C0 = c46_;
						vertexData_[surface][i][j].f0 = f46_;
					}
					else if (d0_elig >= 6 and u0_elig >= 4) // S64
					{
						d0 = 6;
						u0 = 4;

						vertexData_[surface][i][j].C0 = c64_;
						vertexData_[surface][i][j].f0 = f64_;
					}
					else if (d0_elig >= 3 and u0_elig >= 7) // S37
					{
						d0 = 3;
						u0 = 7;

						vertexData_[surface][i][j].C0 = c37_;
						vertexData_[surface][i][j].f0 = f37_;
					}
					else if (d0_elig >= 7 and u0_elig >= 3) // S73
					{
						d0 = 7;
						u0 = 3;

						vertexData_[surface][i][j].C0 = c73_;
						vertexData_[surface][i][j].f0 = f73_;
					}
					else if (d0_elig >= 2 and u0_elig >= 8) // S28
					{
						d0 = 2;
						u0 = 8;

						vertexData_[surface][i][j].C0 = c28_;
						vertexData_[surface][i][j].f0 = f28_;
					}
					else if (d0_elig >= 8 and u0_elig >= 2) // S82
					{
						d0 = 8;
						u0 = 2;

						vertexData_[surface][i][j].C0 = c82_;
						vertexData_[surface][i][j].f0 = f82_;
					}
					else if (d0_elig >= 1 and u0_elig >= 5) // S15
					{
						d0 = 1;
						u0 = 5;

						vertexData_[surface][i][j].C0 = c15_;
						vertexData_[surface][i][j].f0 = f15_;
					}
					else if (d0_elig >= 5 and u0_elig >= 1) // S51
					{
						d0 = 5;
						u0 = 1;

						vertexData_[surface][i][j].C0 = c51_;
						vertexData_[surface][i][j].f0 = f51_;
					}
					else if (d0_elig >= 0 and u0_elig >= 3) // S03
					{
						d0 = 0;
						u0 = 3;

						vertexData_[surface][i][j].C0 = c03_;
						vertexData_[surface][i][j].f0 = f03_;
					}
					else if (d0_elig >= 3 and u0_elig >= 0) // S30
					{
						d0 = 3;
						u0 = 0;

						vertexData_[surface][i][j].C0 = c30_;
						vertexData_[surface][i][j].f0 = f30_;
					}

				} // end of Berland stencil

				else
				{
					string str = "Error, OW3DSeakeeping::Filter_0_2_.cpp: Not enough grid points for filtering. There are " + DoubleToString(d0_elig) + " and " + DoubleToString(u0_elig) + " points.";
					throw runtime_error(str);
				}

				vertexData_[surface][i][j].d0 = d0;
				vertexData_[surface][i][j].u0 = u0;
				vertexData_[surface][i][j].R0 = Range(i - d0, i + u0);		// assign the range RangeArray
				vertexData_[surface][i][j].C0.reshape((d0 + u0 + 1), 1, 1); // reshape the coefficient RealArray
				vertexData_[surface][i][j].f0.reshape((d0 + u0 + 1), 1, 1); // reshape the coefficient RealArray

				//----------------------------------------------------------------
				//
				//                         ALONG INDEX "2"
				//
				// ---------------------------------------------------------------

				if (mg.numberOfDimensions() == 3)
				{
					int d2_elig = 0; // number of eligible points down
					int u2_elig = 0; // number of eligible points up
					int d2, u2;		 // number of points down and up along index "2" (decided finally)

					// Counts number of eligible points in the "2" up direction index (exclude hole points and ghost points)

					while ((j + 1) + u2_elig <= bound2 and mg.mask()(i, Is[1].getBase(), (j + 1) + u2_elig) != 0)
					{
						u2_elig++;
					}

					// Counts number of eligible points in the "2" down direction index (exclude hole points and ghost points)

					while ((j - 1) - d2_elig >= base2 and mg.mask()(i, Is[1].getBase(), (j - 1) - d2_elig) != 0)
					{
						d2_elig++;
					}

					// Determine a viable stencil and assign the range and the coefficients

					if (u2_elig >= HW_ and d2_elig >= HW_) // user defined centered stencil is possible
					{
						u2 = d2 = HW_;
						vertexData_[surface][i][j].C2 = c_;
						vertexData_[surface][i][j].f2 = f_;
					}

					else if (d2_elig >= hw_ and u2_elig >= hw_) // use a centered stencil smaller than the user definded one, but bigger than mhw_
					{
						d2 = u2 = min(d2_elig, u2_elig);

						int width = 2 * d2 + 1;
						int order = width - d_; // order is less by d_

						RealArray f(1, 1, width), C(1, 1, width);
						f = 0;
						f(0, 0, d2) = 1;

						double *c = new double[width];
						Savgol(c, width, d2, d2, 0, order);

						for (int sg = 0; sg < width; sg++)
						{
							if (i == d2)
							{
								C(0, 0, sg) = 1 - c[sg];
							}
							else
							{
								C(0, 0, sg) = -c[sg]; // note Berland (2007) notation!
							}
						}
						delete[] c;

						vertexData_[surface][i][j].C2 = C;
						vertexData_[surface][i][j].f2 = f;

					} // end of program defined centered stencil

					else if ((d2_elig >= 0 and u2_elig >= 3) || (u2_elig >= 0 and d2_elig >= 3)) // Berland stencil is possible
					{
						if (d2_elig >= 4 and u2_elig >= 6) // S46
						{
							d2 = 4;
							u2 = 6;

							vertexData_[surface][i][j].C2 = c46_;
							vertexData_[surface][i][j].f2 = f46_;
						}
						else if (d2_elig >= 6 and u2_elig >= 4) // S64
						{
							d2 = 6;
							u2 = 4;

							vertexData_[surface][i][j].C2 = c64_;
							vertexData_[surface][i][j].f2 = f64_;
						}
						else if (d2_elig >= 3 and u2_elig >= 7) // S37
						{
							d2 = 3;
							u2 = 7;

							vertexData_[surface][i][j].C2 = c37_;
							vertexData_[surface][i][j].f2 = f37_;
						}
						else if (d2_elig >= 7 and u2_elig >= 3) // S73
						{
							d2 = 7;
							u2 = 3;

							vertexData_[surface][i][j].C2 = c73_;
							vertexData_[surface][i][j].f2 = f73_;
						}
						else if (d2_elig >= 2 and u2_elig >= 8) // S28
						{
							d2 = 2;
							u2 = 8;

							vertexData_[surface][i][j].C2 = c28_;
							vertexData_[surface][i][j].f2 = f28_;
						}
						else if (d2_elig >= 8 and u2_elig >= 2) // S82
						{
							d2 = 8;
							u2 = 2;

							vertexData_[surface][i][j].C2 = c82_;
							vertexData_[surface][i][j].f2 = f82_;
						}
						else if (d2_elig >= 1 and u2_elig >= 5) // S15
						{
							d2 = 1;
							u2 = 5;

							vertexData_[surface][i][j].C2 = c15_;
							vertexData_[surface][i][j].f2 = f15_;
						}
						else if (d2_elig >= 5 and u2_elig >= 1) // S51
						{
							d2 = 5;
							u2 = 1;

							vertexData_[surface][i][j].C2 = c51_;
							vertexData_[surface][i][j].f2 = f51_;
						}
						else if (d2_elig >= 0 and u2_elig >= 3) // S03
						{
							d2 = 0;
							u2 = 3;

							vertexData_[surface][i][j].C2 = c03_;
							vertexData_[surface][i][j].f2 = f03_;
						}
						else if (d2_elig >= 3 and u2_elig >= 0) // S30
						{
							d2 = 3;
							u2 = 0;

							vertexData_[surface][i][j].C2 = c30_;
							vertexData_[surface][i][j].f2 = f30_;
						}

					} // end of Berland stencil

					else
					{
						string str = "Error, OW3DSeakeeping::Filter_0_2_.cpp: Not enough grid points for filtering. There are " + DoubleToString(d2_elig) + " and " + DoubleToString(u2_elig) + " points.";
						throw runtime_error(str);
					}

					vertexData_[surface][i][j].d2 = d2;
					vertexData_[surface][i][j].u2 = u2;
					vertexData_[surface][i][j].R2 = Range(j - d2, j + u2); // assign the range RangeArray

					// no reshape is needed as the coefficient and f RealArray a have the correct shape

				} // end of 3d check

				if (print_)
				{
					int range_0_base = vertexData_[surface][i][j].R0.getBase();
					int range_0_bound = vertexData_[surface][i][j].R0.getBound();
					int range_2_base = vertexData_[surface][i][j].R2.getBase();
					int range_2_bound = vertexData_[surface][i][j].R2.getBound();
					int length0 = vertexData_[surface][i][j].C0.getLength(0);
					int length2 = vertexData_[surface][i][j].C2.getLength(2);

					fout << vertexData_[surface][i][j].d0 << vertexData_[surface][i][j].u0 << '\n'
						 << " range starts at:=" << range_0_base << setw(sw) << " range ends at:=" << range_0_bound << '\n';
					for (int p = 0; p < length0; p++)
					{
						fout << setw(bw) << vertexData_[surface][i][j].f0(p, 0, 0);
					}
					fout << '\n';

					for (int p = 0; p < length0; p++)
					{
						fout << setw(bw) << vertexData_[surface][i][j].C0(p, 0, 0);
					}
					fout << '\n';

					if (vertexData_[surface][i][j].R2.length() > 1)
					{
						fout << vertexData_[surface][i][j].d2 << vertexData_[surface][i][j].u2 << '\n'
							 << " range starts at:=" << range_2_base << setw(sw) << " range ends at:=" << range_2_bound << '\n';
						for (int p = 0; p < length2; p++)
						{
							fout << setw(bw) << vertexData_[surface][i][j].f2(0, 0, p);
						}
						fout << '\n';

						for (int p = 0; p < length2; p++)
						{
							fout << setw(bw) << vertexData_[surface][i][j].C2(0, 0, p);
						}
						fout << "\n\n";
					}
				}

			} // end of positive mask

			if (print_)
				fout << " ****" << '\n';

		} // end of j

	} // end of i

} // end of filter_0_2_ private member function
