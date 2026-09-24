// This private member function belongs to the FreeSurface class, and just for
// the sake of convenience is written in a seperate file.

#include "FreeSurface.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::FreeSurface::BuildSpongLayer_(
	const vector<Coordinate> &wallCoordinates,
	const vector<Grid::FREE_SURFACE_TYPES> &sfTypes,
	double sponge_length)
{
	string filename = resultsDirectory_ + "/sponge.txt";

	int preci = 5;
	int width = 15;

	ofstream fout;

	if (sponge_length != 0)
	{
		fout.open(filename);
		fout.setf(ios_base::scientific);
		fout.precision(preci);
		fout << setw(width) << "x" << setw(width) << "z" << setw(width) << "c" << '\n';
	}

	for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
	{
		const Single_boundary_data &bf = boundariesData_->free[surface];
		MappedGrid mg = (*cg_)[bf.grid];
		const vector<Index> &Is = bf.surface_indices;

		sponge_[surface] = RealArray(Is[0], Is[1], Is[2]);

		double z = 0.0;

		if (sfTypes[surface] == Grid::FREE_SURFACE_TYPES::BACK and sponge_length != 0)
		{
			double wallSh, nl;

			for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
			{
				for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
				{
					for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
					{
						Coordinate coordinate;

						if ((*cg_).numberOfDimensions() != 2)
						{
							z = mg.vertex()(i, j, k, axis3);
						}

						coordinate.x = mg.vertex()(i, j, k, axis1);
						coordinate.z = z;

						wallSh = FindShortest(coordinate, wallCoordinates);

						if (wallSh < sponge_length)
						{
							nl = (sponge_length - wallSh) / sponge_length;

							sponge_[surface](i, j, k) = -2 * pow(nl, 3) + 3 * pow(nl, 2); // -2*x^3 + 3*x^2   x [0 1]
						}

						else
						{
							sponge_[surface](i, j, k) = 0.0;
						}

						if (mg.mask()(i, j, k) > 0)
						{
							fout << setw(width) << coordinate.x << setw(width) << coordinate.z << setw(width) << sponge_[surface](i, j, k) << '\n';
						}

					} // end of k

				} // end of j

			} // end of i

		} // end of check for "back" surface and zero sponge length

		else
		{
			sponge_[surface] = 0.0;
		}

	} // end surface loop
}
