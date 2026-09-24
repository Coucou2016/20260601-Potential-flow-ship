// Note : This part of the class is implemented here due to just readibility of the main implementation file.

// filter along index "1" and "2" over the free-surface which has index "0"

#include "Filter.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Filter::Filter_1_2_(
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

	int bound1 = Is[1].getBound();
	int bound2 = Is[2].getBound();
	int base1 = Is[1].getBase();
	int base2 = Is[2].getBase();

	for (i = Is[1].getBase(); i <= Is[1].getBound(); i++)
	{
		for (j = Is[2].getBase(); j <= Is[2].getBound(); j++)
		{
			vertexData_[surface][i][j].mask = mg.mask()(Is[0].getBase(), i, j); // we need this when applying the filter

			if (mg.mask()(Is[0].getBase(), i, j) > 0) // just for discretisation points
			{
				//----------------------------------------------------------------
				//
				//                         ALONG INDEX "1"
				//
				// ---------------------------------------------------------------

				int d1_elig = 0; // number of eligible points down
				int u1_elig = 0; // number of eligible points up
				int d1, u1;		 // number of points down and up along index "1" (decided finally)

				// Counts number of eligible points in the "1" up direction index (exclude hole points and ghost points)

				while ((i + 1) + u1_elig <= bound1 and mg.mask()(Is[0].getBase(), (i + 1) + u1_elig, j) != 0)
				{
					u1_elig++;
				}

				// Counts number of eligible points in the "1" down direction index (exclude hole points and ghost points)

				while ((i - 1) - d1_elig >= base1 and mg.mask()(Is[0].getBase(), (i - 1) - d1_elig, j) != 0)
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
					string str = "Error, OW3DSeakeeping::Filter_1_2_.cpp: Not enough grid points for filtering. There are " + DoubleToString(d1_elig) + " and " + DoubleToString(u1_elig) + " points.";
					throw runtime_error(str);
				}

				vertexData_[surface][i][j].d1 = d1;
				vertexData_[surface][i][j].u1 = u1;
				vertexData_[surface][i][j].R1 = Range(i - d1, i + u1);		// assign the range RangeArray
				vertexData_[surface][i][j].C1.reshape(1, (d1 + u1 + 1), 1); // reshape the coefficient RealArray
				vertexData_[surface][i][j].f1.reshape(1, (d1 + u1 + 1), 1); // reshape the coefficient RealArray

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

					while ((j + 1) + u2_elig <= bound2 and mg.mask()(Is[0].getBase(), i, (j + 1) + u2_elig) != 0)
					{
						u2_elig++;
					}

					// Counts number of eligible points in the "2" down direction index (exclude hole points and ghost points)

					while ((j - 1) - d2_elig >= base2 and mg.mask()(Is[0].getBase(), i, (j - 1) - d2_elig) != 0)
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

					else if (d2_elig >= hw_ and u2_elig >= hw_) // use a centered stencil smaller than the user definded one, but bigger than hw_
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
							if (sg == d2)
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
						string str = "Error, OW3DSeakeeping::Filter_1_2_.cpp: Not enough grid points for filtering. There are " + DoubleToString(d2_elig) + " and " + DoubleToString(u2_elig) + " points.";
						throw runtime_error(str);
					}

					vertexData_[surface][i][j].d2 = d2;
					vertexData_[surface][i][j].u2 = u2;
					vertexData_[surface][i][j].R2 = Range(j - d2, j + u2); // assign the range RangeArray

					// no reshape is needed as f and c arraya are along index 2 which is the original index used.

				} // end of 3d check

				if (print_)
				{
					int range_1_base = vertexData_[surface][i][j].R1.getBase();
					int range_1_bound = vertexData_[surface][i][j].R1.getBound();
					int range_2_base = vertexData_[surface][i][j].R2.getBase();
					int range_2_bound = vertexData_[surface][i][j].R2.getBound();
					int length1 = vertexData_[surface][i][j].C1.getLength(1);
					int length2 = vertexData_[surface][i][j].C2.getLength(2);

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

} // end of filter_1_2_ private member function
