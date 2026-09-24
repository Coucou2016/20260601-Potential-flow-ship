// Note : This part of the class is implemented here due to just readibility of the main implementation file.

// filter along index "0" and "1" over the free-surface which has index "2"

#include "Filter.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Filter::Filter_0_1_(
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
	int bound1 = Is[1].getBound();
	int base0 = Is[0].getBase();
	int base1 = Is[1].getBase();

	for (i = Is[0].getBase(); i <= Is[0].getBound(); i++)
	{
		for (j = Is[1].getBase(); j <= Is[1].getBound(); j++)
		{
			vertexData_[surface][i][j].mask = mg.mask()(i, j, Is[2].getBase()); // we need this when applying the filter

			if (mg.mask()(i, j, Is[2].getBase()) > 0) // just for discretisation points
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

				while ((i + 1) + u0_elig <= bound0 and mg.mask()((i + 1) + u0_elig, j, Is[2].getBase()) != 0)
				{
					u0_elig++;
				}

				// Counts number of eligible points in the "0" down direction index (exclude hole points and ghost points)

				while ((i - 1) - d0_elig >= base0 and mg.mask()((i - 1) - d0_elig, j, Is[2].getBase()) != 0)
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

				else if (d0_elig >= hw_ and u0_elig >= hw_) // use a centered stencil smaller than the user definded one, but bigger than hw_
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
					string str = "Error, OW3DSeakeeping::Filter_0_1_.cpp: Not enough grid points for filtering. There are " + DoubleToString(d0_elig) + " and " + DoubleToString(u0_elig) + " points.";
					throw runtime_error(str);
				}

				vertexData_[surface][i][j].d0 = d0;
				vertexData_[surface][i][j].u0 = u0;
				vertexData_[surface][i][j].R0 = Range(i - d0, i + u0);		// assign the range RangeArray
				vertexData_[surface][i][j].C0.reshape((d0 + u0 + 1), 1, 1); // reshape the coefficient RealArray
				vertexData_[surface][i][j].f0.reshape((d0 + u0 + 1), 1, 1); // reshape the coefficient RealArray

				//----------------------------------------------------------------
				//
				//                         ALONG INDEX "1"
				//
				// ---------------------------------------------------------------

				int d1_elig = 0; // number of eligible points down
				int u1_elig = 0; // number of eligible points up
				int d1, u1;		 // number of points down and up along index "1" (decided finally)

				// Counts number of eligible points in the "1" up direction index (exclude hole points and ghost points)

				while ((j + 1) + u1_elig <= bound1 and mg.mask()(i, (j + 1) + u1_elig, Is[2].getBase()) != 0)
				{
					u1_elig++;
				}

				// Counts number of eligible points in the "1" down direction index (exclude hole points and ghost points)

				while ((j - 1) - d1_elig >= base1 and mg.mask()(i, (j - 1) - d1_elig, Is[2].getBase()) != 0)
				{
					d1_elig++;
				}

				// Determine a viable stencil and assign the range and the coefficients

				if (u1_elig >= HW_ and d1_elig >= HW_) // user defined centered stencil is possible
				{
					u1 = d1 = HW_;
					vertexData_[surface][i][j].C1 = c_;
					vertexData_[surface][i][j].f1 = f_;
				}

				else if (d1_elig >= hw_ and u1_elig >= hw_) // use a centered stencil smaller than the user definded one, but bigger than hw_
				{
					d1 = u1 = min(d1_elig, u1_elig);

					int width = 2 * d1 + 1;
					int order = width - d_; // order is less by d_

					RealArray f(1, 1, width), C(1, 1, width);
					f = 0;
					f(0, 0, d1) = 1;

					double *c = new double[width];
					Savgol(c, width, d1, d1, 0, order);

					for (int sg = 0; sg < width; sg++)
					{
						if (sg == d1)
						{
							C(0, 0, sg) = 1 - c[sg];
						}
						else
						{
							C(0, 0, sg) = -c[sg]; // note Berland (2007) notation!
						}
					}
					delete[] c;

					vertexData_[surface][i][j].C1 = C;
					vertexData_[surface][i][j].f1 = f;

				} // end of program defined centered stencil

				else if ((d1_elig >= 0 and u1_elig >= 3) || (u1_elig >= 0 and d1_elig >= 3)) // Berland stencil is possible
				{
					if (d1_elig >= 4 and u1_elig >= 6) // S46
					{
						d1 = 4;
						u1 = 6;

						vertexData_[surface][i][j].C1 = c46_;
						vertexData_[surface][i][j].f1 = f46_;
					}
					else if (d1_elig >= 6 and u1_elig >= 4) // S64
					{
						d1 = 6;
						u1 = 4;

						vertexData_[surface][i][j].C1 = c64_;
						vertexData_[surface][i][j].f1 = f64_;
					}
					else if (d1_elig >= 3 and u1_elig >= 7) // S37
					{
						d1 = 3;
						u1 = 7;

						vertexData_[surface][i][j].C1 = c37_;
						vertexData_[surface][i][j].f1 = f37_;
					}
					else if (d1_elig >= 7 and u1_elig >= 3) // S73
					{
						d1 = 7;
						u1 = 3;

						vertexData_[surface][i][j].C1 = c73_;
						vertexData_[surface][i][j].f1 = f73_;
					}
					else if (d1_elig >= 2 and u1_elig >= 8) // S28
					{
						d1 = 2;
						u1 = 8;

						vertexData_[surface][i][j].C1 = c28_;
						vertexData_[surface][i][j].f1 = f28_;
					}
					else if (d1_elig >= 8 and u1_elig >= 2) // S82
					{
						d1 = 8;
						u1 = 2;

						vertexData_[surface][i][j].C1 = c82_;
						vertexData_[surface][i][j].f1 = f82_;
					}
					else if (d1_elig >= 1 and u1_elig >= 5) // S15
					{
						d1 = 1;
						u1 = 5;

						vertexData_[surface][i][j].C1 = c15_;
						vertexData_[surface][i][j].f1 = f15_;
					}
					else if (d1_elig >= 5 and u1_elig >= 1) // S51
					{
						d1 = 5;
						u1 = 1;

						vertexData_[surface][i][j].C1 = c51_;
						vertexData_[surface][i][j].f1 = f51_;
					}
					else if (d1_elig >= 0 and u1_elig >= 3) // S03
					{
						d1 = 0;
						u1 = 3;

						vertexData_[surface][i][j].C1 = c03_;
						vertexData_[surface][i][j].f1 = f03_;
					}
					else if (d1_elig >= 3 and u1_elig >= 0) // S30
					{
						d1 = 3;
						u1 = 0;

						vertexData_[surface][i][j].C1 = c30_;
						vertexData_[surface][i][j].f1 = f30_;
					}

				} // end of Berland stencil

				else
				{
					string str = "Error, OW3DSeakeeping::Filter_0_1_.cpp: Not enough grid points for filtering. There are " + DoubleToString(d1_elig) + " and " + DoubleToString(u1_elig) + " points.";
					throw runtime_error(str);
				}

				vertexData_[surface][i][j].d1 = d1;
				vertexData_[surface][i][j].u1 = u1;
				vertexData_[surface][i][j].R1 = Range(j - d1, j + u1);		// assign the range RangeArray
				vertexData_[surface][i][j].C1.reshape(1, (d1 + u1 + 1), 1); // reshape the coefficient RealArray
				vertexData_[surface][i][j].f1.reshape(1, (d1 + u1 + 1), 1); // reshape the coefficient RealArray

				if (print_)
				{
					int range_0_base = vertexData_[surface][i][j].R0.getBase();
					int range_0_bound = vertexData_[surface][i][j].R0.getBound();
					int range_1_base = vertexData_[surface][i][j].R1.getBase();
					int range_1_bound = vertexData_[surface][i][j].R1.getBound();
					int length0 = vertexData_[surface][i][j].C0.getLength(0);
					int length1 = vertexData_[surface][i][j].C1.getLength(1);

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

					fout << vertexData_[surface][i][j].d1 << vertexData_[surface][i][j].u1 << '\n'
						 << " range starts at:=" << range_1_base << setw(sw) << " range ends at:=" << range_1_bound << '\n';
					for (int p = 0; p < length1; p++)
					{
						fout << setw(bw) << vertexData_[surface][i][j].f1(0, p, 0);
					}
					fout << '\n';

					for (int p = 0; p < length1; p++)
					{
						fout << setw(bw) << vertexData_[surface][i][j].C1(0, p, 0);
					}
					fout << "\n\n";
				}

			} // end of positive mask

			if (print_)
				fout << " ****" << '\n';

		} // end of j

	} // end of i

} // end of filter_0_1_ private member function
