// Note : This part of the class is implemented here due to readibility of the main implementation file.

#include "Baseflow.h"

void OW3DSeakeeping::Baseflow::SearchElevation_1_2_0_(
	string side,
	int direction,
	const vector<Index> &Is,
	const vector<Index> &I,
	const MappedGrid &mg,
	const Single_boundary_data &bf,
	const realCompositeGridFunction &downFunction,
	const realCompositeGridFunction &upFunction,
	realCompositeGridFunction &doubleBodyElevation)
{
	int fs = Is[0].getBase(); // the base index in the search direction.

	if (side == "start")
	{
		for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
		{
			for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
			{
				for (int i = Is[0].getBase(); i < I[0].getBound(); i++)
				{
					// search in the up part
					if ((upFunction[bf.grid](i + 1, j, k) > 0 && upFunction[bf.grid](i, j, k) < 0) or (upFunction[bf.grid](i + 1, j, k) < 0 && upFunction[bf.grid](i, j, k) > 0))
					{
						int p;
						int dp_s = 0;
						int dp_n = 0;
						p = i - 1;
						while (p >= I[0].getBase() and mg.mask()(p, j, k) != 0)
						{
							dp_s++;
							p--;
						} // counts the number of eligible points before index i
						p = i + 1;
						while (p <= I[0].getBound() and mg.mask()(p, j, k) != 0)
						{
							dp_n++;
							p++;
						} // counts the number of eligible points after  index i
						realArray coord(I[0], I[1], I[2]);
						coord = -(mg.vertex()(I[0], I[1], I[2], axis2));
						FindDoublebodyElevation_(i, j, k, bf.grid, fs, direction, upFunction, coord, dp_s, dp_n, doubleBodyElevation);
						break;
					}
					// search in the down part
					if ((downFunction[bf.grid](i + 1, j, k) > 0 && downFunction[bf.grid](i, j, k) < 0) or (downFunction[bf.grid](i + 1, j, k) < 0 && downFunction[bf.grid](i, j, k) > 0))
					{
						int p;
						int dp_s = 0;
						int dp_n = 0;
						p = i - 1;
						while (p >= I[0].getBase() and mg.mask()(p, j, k) != 0)
						{
							dp_s++;
							p--;
						} // counts the number of eligible points before index i
						p = i + 1;
						while (p <= I[0].getBound() and mg.mask()(p, j, k) != 0)
						{
							dp_n++;
							p++;
						} // counts the number of eligible points after  index i
						realArray coord(I[0], I[1], I[2]);
						coord = mg.vertex()(I[0], I[1], I[2], axis2);
						FindDoublebodyElevation_(i, j, k, bf.grid, fs, direction, downFunction, coord, dp_s, dp_n, doubleBodyElevation);
						break;
					}
				} // end of 0
			}	  // end of 2
		}		  // end of 1
	}			  // end of "start" side

	if (side == "end")
	{
		for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
		{
			for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
			{
				for (int i = Is[0].getBase(); i > I[0].getBase(); i--)
				{
					// search in the up part
					if ((upFunction[bf.grid](i - 1, j, k) > 0 && upFunction[bf.grid](i, j, k) < 0) or (upFunction[bf.grid](i - 1, j, k) < 0 && upFunction[bf.grid](i, j, k) > 0))
					{
						int p;
						int dp_s = 0;
						int dp_n = 0;
						p = i - 1;
						while (p >= I[0].getBase() and mg.mask()(p, j, k) != 0)
						{
							dp_s++;
							p--;
						} // counts the number of eligible points before index i
						p = i + 1;
						while (p <= I[0].getBound() and mg.mask()(p, j, k) != 0)
						{
							dp_n++;
							p++;
						} // counts the number of eligible points after  index i
						realArray coord(I[0], I[1], I[2]);
						coord = -mg.vertex()(I[0], I[1], I[2], axis2);
						FindDoublebodyElevation_(i, j, k, bf.grid, fs, direction, upFunction, coord, dp_s, dp_n, doubleBodyElevation);
						break;
					}
					// search in the down part
					if ((downFunction[bf.grid](i - 1, j, k) > 0 && downFunction[bf.grid](i, j, k) < 0) or (downFunction[bf.grid](i - 1, j, k) < 0 && downFunction[bf.grid](i, j, k) > 0))
					{
						int p;
						int dp_s = 0;
						int dp_n = 0;
						p = i - 1;
						while (p >= I[0].getBase() and mg.mask()(p, j, k) != 0)
						{
							dp_s++;
							p--;
						} // counts the number of eligible points before index i
						p = i + 1;
						while (p <= I[0].getBound() and mg.mask()(p, j, k) != 0)
						{
							dp_n++;
							p++;
						} // counts the number of eligible points before index i
						realArray coord(I[0], I[1], I[2]);
						coord = mg.vertex()(I[0], I[1], I[2], axis2);
						FindDoublebodyElevation_(i, j, k, bf.grid, fs, direction, downFunction, coord, dp_s, dp_n, doubleBodyElevation);
						break;
					}
				} // end of 0
			}	  // end of 2
		}		  // end of 1
	}			  // end of "end" side

} // end of elevationSearch_1_2_0_ private member function
