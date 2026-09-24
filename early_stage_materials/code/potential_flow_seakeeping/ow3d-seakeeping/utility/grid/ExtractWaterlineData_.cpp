#include "Grid.h"
#include <numeric>

int OW3DSeakeeping::Grid::ExtractWaterlineData_()
{
	Index I;

	// here we loop over the free surfaces and select thoes which are connected
	// to the body. Then the water line information are extracted.

	for (unsigned int surface = 0; surface < gridData_.boundariesData.free.size(); surface++)
	{
		if (gridData_.freeSurfaceTypes[surface] == FREE_SURFACE_TYPES::BODY)
		{
			WLD wld;

			const Single_boundary_data &bf = gridData_.boundariesData.free[surface];
			const vector<Index> &Is = bf.surface_indices;
			const MappedGrid &mg = cg_[bf.grid];

			wld.I0 = Is[0]; // the length of one of these indices is already 1. We need
			wld.I1 = Is[1]; // to determine which one of the other two should be used to
			wld.I2 = Is[2]; // loop over the waterline points.
			wld.grid = bf.grid;

			RealArray vbn;

			// in the 3d case two of Is's has a length that is greater than 1.
			// one of these Is's goes around the body, and we need to find that.
			// In this case then either the base or the bound of the other "Is"
			// specifies the index where the water line is located. In order to find
			// these indices we loop through all three axes and two sides of the
			// component grids whoes free surface is connected to the
			// body (the condition of this block). This means the free surface and
			// and the exciting surface has an interface which is in fact the waterline.
			// Now the side of the exciting surface shows either the base
			// or bound of the index at which the water line is located.
			// Moreover the axis shows the index of the waterline.
			// After finding the index and the correct side (base or bound) at which
			// the waterline is located, then the index which should be looped over to
			// get the waterline points, can be specified easily.

			// NOTE :: By the follwing loops the side and axis on which the exciting
			//         surface is located will be found.

			for (int axis = 0; axis < mg.numberOfDimensions(); axis++)
			{
				for (unsigned int side = 0; side <= 1; side++)
				{
					if (mg.boundaryCondition()(side, axis) == gridData_.boundaryTypes.exciting)
					{
						if (side == 0)
							I = Index(Is[axis].getBase(), 1); // 1 is the count
						if (side == 1)
							I = Index(Is[axis].getBound(), 1); // 1 is the count

						if (axis == 0)
							wld.I0 = I;
						if (axis == 1)
							wld.I1 = I;
						if (axis == 2)
							wld.I2 = I;

						vbn = mg.vertexBoundaryNormal(side, axis); // note : normal vectors belong to the body surface
					}
				}
			}

			// now we have found the correct indices for looping around the body water line.
			// In the follwoing lines we extract the desired data and store them as the
			// waterline information.

			unsigned int size, direction; // the size of the water line points, and the direction to get them

			if (wld.I0.getLength() > 1)
			{
				size = wld.I0.getLength();
				direction = 0;
			}

			else if (wld.I1.getLength() > 1)
			{
				size = wld.I1.getLength();
				direction = 1;
			}
			else if (wld.I2.getLength() > 1)
			{
				size = wld.I2.getLength();
				direction = 2;
			}

			else // It is a 2D grid
			{
				size = 1;	   // Just one point exists at the waterline
				direction = 2; // Means perpendicular to the plane.
			}

			wld.size = size;
			wld.direction = direction;

			for (int i = wld.I0.getBase(); i <= wld.I0.getBound(); i++)
			{
				for (int j = wld.I1.getBase(); j <= wld.I1.getBound(); j++)
				{
					for (int k = wld.I2.getBase(); k <= wld.I2.getBound(); k++)
					{
						double x = mg.vertex()(i, j, k, axis1); // the waterline
						double y = mg.vertex()(i, j, k, axis2); // points have these
						double n1 = vbn(i, j, k, axis1);		// coordinates and
						double z = 0.;							// normal vectors
						double n3 = 0.;
						double n2 = 0.; // NOTE : n2 is always zero.

						if (cg_.numberOfDimensions() == 3) // correct for 3D
						{
							z = mg.vertex()(i, j, k, axis3);
							n3 = vbn(i, j, k, axis3);
						}

						wld.mask.push_back(mg.mask()(i, j, k)); // store
						wld.x.push_back(x);						// the coordinates
						wld.y.push_back(y);						// and the
						wld.z.push_back(z);						// normal vectors
						wld.n1.push_back(n1);					// of this point (i,j,k)
						wld.n3.push_back(n3);					// at the waterline
						wld.n2.push_back(n2);

						// To store the length of elements (dl) for integration.
						// NOTE :: The loop is not entered for 2D grids.

						if (i != wld.I0.getBase() or j != wld.I1.getBase() or k != wld.I2.getBase())
						{
							double xb = 0.; // just
							double zb = 0.; // initialize

							if (wld.direction == 0) // decrement along "i"
							{
								xb = mg.vertex()(i - 1, j, k, axis1);

								if (cg_.numberOfDimensions() == 3)
								{
									zb = mg.vertex()(i - 1, j, k, axis3);
								}
							}
							else if (wld.direction == 1) // decrement along "j"
							{
								xb = mg.vertex()(i, j - 1, k, axis1);

								if (cg_.numberOfDimensions() == 3)
								{
									zb = mg.vertex()(i, j - 1, k, axis3);
								}
							}
							else // decrement along "k"
							{
								xb = mg.vertex()(i, j, k - 1, axis1);

								if (cg_.numberOfDimensions() == 3)
								{
									zb = mg.vertex()(i, j, k - 1, axis3);
								}
							}

							wld.dl.push_back(sqrt(pow(x - xb, 2) + pow(z - zb, 2))); // calculate and store the length element "dl"
						}
					}
				}
			}

			gridData_.wlData.push_back(wld);

		} // end of free surface attached to the body check

	} // end of loop over all free surfaces

	// Find the maximum and minimum grid spacing around the waterline

	vector<double> all_dls;

	for (unsigned int line = 0; line < gridData_.wlData.size(); line++)
	{
		if (gridData_.nod == 3)
		{
			gridData_.wlData[line].maxdl = 0.;						// First assumption
			gridData_.wlData[line].mindl = gridData_.maximum_depth; // First assumption

			for (int i = 0; i < gridData_.wlData[line].size - 1; i++)
			{
				if (gridData_.wlData[line].dl[i] > gridData_.wlData[line].maxdl)
				{
					gridData_.wlData[line].maxdl = gridData_.wlData[line].dl[i];
				}
				if (gridData_.wlData[line].dl[i] < gridData_.wlData[line].mindl)
				{
					gridData_.wlData[line].mindl = gridData_.wlData[line].dl[i];
				}
				all_dls.push_back(gridData_.wlData[line].dl[i]);
			}
		}
		else
		{
			gridData_.wlData[line].mindl = gridData_.minimum_spacing_free; // For 2D grids, the min grid spacing is used here.
			gridData_.wlData[line].maxdl = gridData_.minimum_spacing_free; // For 2D grids, the min grid spacing is used here.
		}

	} // End of loop over waterlines

	// Compute the average grid size at the waterline (Only 3D grid and floating bodies)

	if (all_dls.size() != 0) // floating bodies
	{
		gridData_.minWl_spacing = *min_element(all_dls.begin(), all_dls.end());
		gridData_.maxWl_spacing = *max_element(all_dls.begin(), all_dls.end());
		// gridData_.avgWl_spacing = 0.5 * (gridData_.maxWl_spacing + gridData_.minWl_spacing);
		gridData_.avgWl_spacing = accumulate(all_dls.begin(), all_dls.end(), 0.0) / all_dls.size();
	}
	else // submerged bodies and 2D grids
	{
		gridData_.avgWl_spacing = gridData_.minimum_spacing_free;
		gridData_.maxWl_spacing = gridData_.minimum_spacing_free;
	}

	// NOTE : Here it is checked if any  hole or interpolation
	//        point are located in the middle of the waterliens.
	//        As this situation is not allowed, an error message
	//        will be thrown out. It is only allowed to have any
	//        interpolation or hole points at the start or the end
	//        of each waterline. The idea is in fact to include just
	//        discretization points at each waterline in the calculation,
	//        and the calculation is caried out based on the assumption
	//        that the hole or interpolation points are located at
	//        the start or the end of the waterline.

	for (unsigned int line = 0; line < gridData_.wlData.size(); line++)
	{
		int count = 0; // Must be at most 2, otherwise the error is thrown!.

		unsigned int wlength = gridData_.wlData[line].size;

		for (unsigned int i = 0; i < wlength - 1; i++)
		{
			if ((gridData_.wlData[line].mask[i] < 0 and gridData_.wlData[line].mask[i + 1] > 0) or
				(gridData_.wlData[line].mask[i] > 0 and gridData_.wlData[line].mask[i + 1] < 0))

				count += 1;
		}

		if (count > 2)
		{
			throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::ExtractWaterlineData_.cpp.\n\t An interpolation point or a hole point is discovered in the middle of one of the waterlines.!", 0));
		}
	}

	return 0;
}
