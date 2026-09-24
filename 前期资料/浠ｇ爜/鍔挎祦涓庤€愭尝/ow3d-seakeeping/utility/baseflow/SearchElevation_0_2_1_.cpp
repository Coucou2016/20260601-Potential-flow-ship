// Note : This part of the class is implemented here due to readibility of the main implementation file.

#include "Baseflow.h"

void OW3DSeakeeping::Baseflow::SearchElevation_0_2_1_(
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
	int fs = Is[1].getBase(); // the base index in the search direction.

	if (side == "start")
	{
		for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
		{
			for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
			{
				for (int j = Is[1].getBase(); j < I[1].getBound(); j++)
				{
					// search in the up part
					if ((upFunction[bf.grid](i, j + 1, k) > 0 && upFunction[bf.grid](i, j, k) < 0) or (upFunction[bf.grid](i, j + 1, k) < 0 && upFunction[bf.grid](i, j, k) > 0))
					{
						int p;
						int dp_s = 0;
						int dp_n = 0;
						p = j - 1;
						while (p >= I[1].getBase() and mg.mask()(i, p, k) != 0)
						{
							dp_s++;
							p--;
						} // counts the number of eligible points before index j
						p = j + 1;
						while (p <= I[1].getBound() and mg.mask()(i, p, k) != 0)
						{
							dp_n++;
							p++;
						} // counts the number of eligible points after  index j
						realArray coord(I[0], I[1], I[2]);
						coord = -mg.vertex()(I[0], I[1], I[2], axis2);
						FindDoublebodyElevation_(i, j, k, bf.grid, fs, direction, upFunction, coord, dp_s, dp_n, doubleBodyElevation);
						break;
					}
					// search in the down part
					if ((downFunction[bf.grid](i, j + 1, k) > 0 && downFunction[bf.grid](i, j, k) < 0) or (downFunction[bf.grid](i, j + 1, k) < 0 && downFunction[bf.grid](i, j, k) > 0))
					{
						int p;
						int dp_s = 0;
						int dp_n = 0;
						p = j - 1;
						while (p >= I[1].getBase() and mg.mask()(i, p, k) != 0)
						{
							dp_s++;
							p--;
						} // counts the number of eligible points before index j
						p = j + 1;
						while (p <= I[1].getBound() and mg.mask()(i, p, k) != 0)
						{
							dp_n++;
							p++;
						} // counts the number of eligible points after  index j
						realArray coord(I[0], I[1], I[2]);
						coord = mg.vertex()(I[0], I[1], I[2], axis2);
						FindDoublebodyElevation_(i, j, k, bf.grid, fs, direction, downFunction, coord, dp_s, dp_n, doubleBodyElevation);
						break;
					}
				} // end of 1
			}	  // end of 2
		}		  // end of 0
	}			  // end of "start" side

	if (side == "end")
	{
		for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
		{
			for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
			{
				for (int j = Is[1].getBase(); j > I[1].getBase(); j--)
				{
					// search in the up part
					if ((upFunction[bf.grid](i, j - 1, k) > 0 && upFunction[bf.grid](i, j, k) < 0) or (upFunction[bf.grid](i, j - 1, k) < 0 && upFunction[bf.grid](i, j, k) > 0))
					{
						int p;
						int dp_s = 0;
						int dp_n = 0;
						p = j - 1;
						while (p >= I[1].getBase() and mg.mask()(i, p, k) != 0)
						{
							dp_s++;
							p--;
						} // counts the number of eligible points before index j
						p = j + 1;
						while (p <= I[1].getBound() and mg.mask()(i, p, k) != 0)
						{
							dp_n++;
							p++;
						} // counts the number of eligible points after  index j
						realArray coord(I[0], I[1], I[2]);
						coord = -mg.vertex()(I[0], I[1], I[2], axis2);
						FindDoublebodyElevation_(i, j, k, bf.grid, fs, direction, upFunction, coord, dp_s, dp_n, doubleBodyElevation);
						break;
					}
					// search in the down part
					if ((downFunction[bf.grid](i, j - 1, k) > 0 && downFunction[bf.grid](i, j, k) < 0) or (downFunction[bf.grid](i, j - 1, k) < 0 && downFunction[bf.grid](i, j, k) > 0))
					{
						int p;
						int dp_s = 0;
						int dp_n = 0;
						p = j - 1;
						while (p >= I[1].getBase() and mg.mask()(i, p, k) != 0)
						{
							dp_s++;
							p--;
						} // counts the number of eligible points before index j
						p = j + 1;
						while (p <= I[1].getBound() and mg.mask()(i, p, k) != 0)
						{
							dp_n++;
							p++;
						} // counts the number of eligible points after  index j
						realArray coord(I[0], I[1], I[2]);
						coord = mg.vertex()(I[0], I[1], I[2], axis2);
						FindDoublebodyElevation_(i, j, k, bf.grid, fs, direction, downFunction, coord, dp_s, dp_n, doubleBodyElevation);
						break;
					}
				} // end of 1
			}	  // end of 2
		}		  // end of 0
	}			  // end of "end" side

} // end of elevationSearch_0_2_1_ private member function
