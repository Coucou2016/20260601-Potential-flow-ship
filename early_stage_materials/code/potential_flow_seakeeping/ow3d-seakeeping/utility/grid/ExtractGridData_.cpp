#include "Grid.h"
#include "OW3DConstants.h"

int OW3DSeakeeping::Grid::ExtractGridData_()
{
	// ==========================================================================
	// Extract spatial order.
	// ==========================================================================
	int nod = gridData_.nod;
	int nog = gridData_.nog;
	const Range dimensions_range = nod;
	const IntegerArray &iw = cg_.interpolationWidth();
	int minimum_discretisation_width;
	int minimum_interpolation_width;
	int order;

	for (int grid_1 = 0; grid_1 < nog; ++grid_1)
	{
		const MappedGrid &mg = cg_[grid_1];
		const IntegerArray &dw = mg.discretizationWidth();

		if (grid_1 == 0)
		{
			minimum_discretisation_width = min(dw(dimensions_range));
		}
		else
		{
			minimum_discretisation_width = min(minimum_discretisation_width, min(dw(dimensions_range)));
		}
		for (int grid_2 = 0; grid_2 < nog; ++grid_2)
		{
			if (grid_1 != grid_2)
			{
				if (grid_1 == 0 && grid_2 == 1)
				{
					minimum_interpolation_width = min(iw(3 * (grid_1 + grid_2 * nog) + dimensions_range));
				}
				else
				{
					minimum_interpolation_width = min(minimum_interpolation_width, min(iw(3 * (grid_1 + grid_2 * nog) + dimensions_range)));
				}
			}
		}

	} // end of loop over grids

	if (nog == 1)
	{
		order = minimum_discretisation_width - 1;
	}
	else
	{
		order = min(minimum_discretisation_width, minimum_interpolation_width) - 1;
	}
	if (order % 2 != 0)
	{
		--order;
	}

	gridData_.order_space = order;
	gridData_.ghost_line = gridData_.order_space / 2;

	// ==========================================================================
	// Extract maximum depth.
	// ==========================================================================
	const MappedGrid &mpg = cg_[0]; // assume tank is first grid to be laid down
	const IntegerArray &gir = mpg.gridIndexRange();
	const RealArray &vp = mpg.vertex();
	vector<Index> I;
	I.resize(3);
	getIndex(gir, I[0], I[1], I[2]);
	gridData_.maximum_depth = abs(min(vp(I[0], I[1], I[2], axis2)));

	// ==========================================================================
	// Extract grid spacings on body and free surface
	// ==========================================================================
	vector<double> sp_body = ComputeGridSpacingsOnSurface_(gridData_.boundariesData.exciting);
	vector<double> sp_free = ComputeGridSpacingsOnSurface_(gridData_.boundariesData.free);
	gridData_.minimum_spacing_body = sp_body[0];
	gridData_.maximum_spacing_body = sp_body[1];
	gridData_.minimum_spacing_free = sp_free[0];

	// ==========================================================================
	// Extract the maximum length of grid
	// ==========================================================================

	vector<double> max_ext;
	for (unsigned int surface = 0; surface < gridData_.boundariesData.free.size(); surface++)
	{
		const Single_boundary_data &bf = gridData_.boundariesData.free[surface];
		const vector<Index> &Is = bf.surface_indices;
		const MappedGrid &mg = cg_[bf.grid];
		const RealArray &v = mg.vertex();
		RealArray X = v(Is[0], Is[1], Is[2], axis1);
		RealArray Y = v(Is[0], Is[1], Is[2], axis2);
		RealArray Z(Is[0], Is[1], Is[2]);
		Z = (mg.numberOfDimensions() == 2) ? 0. * X : v(Is[0], Is[1], Is[2], axis3);
		max_ext.push_back(max(sqrt(X * X + Y * Y + Z * Z)));
	}
	gridData_.maximum_extension = *max_element(max_ext.begin(), max_ext.end()); // for the whole grid
	std::vector<double>::iterator max_res = max_element(max_ext.begin(), max_ext.end());
	int ocean_surface_index = std::distance(max_ext.begin(), max_res);
	gridData_.ocean_grid_index = (gridData_.boundariesData.free[ocean_surface_index]).grid;

	// ==========================================================================
	// Extract the maximum length of the body along x axis
	// ==========================================================================
	vector<double> max_x_cr;
	vector<double> min_x_cr;
	for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
	{
		const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
		const vector<Index> &Is = be.surface_indices;
		const MappedGrid &mg = cg_[be.grid];
		const RealArray &v = mg.vertex();
		RealArray X = v(Is[0], Is[1], Is[2], axis1);

		max_x_cr.push_back(max(X));
		min_x_cr.push_back(min(X));
	}
	gridData_.maximum_body_length = *max_element(max_x_cr.begin(), max_x_cr.end()) - *min_element(min_x_cr.begin(), min_x_cr.end()); // for the whole grid

	// ==========================================================================
	// Extract the maximum length of the body along z axis
	// ==========================================================================

	gridData_.maximum_body_width = 0.;

	if (gridData_.nod != 2)
	{
		vector<double> max_z_cr;
		vector<double> min_z_cr;

		for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
		{
			const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
			const vector<Index> &Is = be.surface_indices;
			const MappedGrid &mg = cg_[be.grid];
			const RealArray &v = mg.vertex();
			RealArray Z = v(Is[0], Is[1], Is[2], axis3);

			max_z_cr.push_back(max(Z));
			min_z_cr.push_back(min(Z));
		}

		gridData_.maximum_body_width = *max_element(max_z_cr.begin(), max_z_cr.end()) - *min_element(min_z_cr.begin(), min_z_cr.end()); // for the whole grid
	}

	// ==========================================================================
	// Check for symmetry
	// ==========================================================================

	// 2D symmetry
	if (gridData_.boundariesData.symmetry.size() != 0 and nod == 2)
		throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::ExtractGridData_.cpp.\n\t The symmetry plane can not be defined for 2D grids.", 0));

	// 3D symmetry
	if (OW3DSeakeeping::UserInput.symx && gridData_.boundariesData.symmetry.size() == 0)
		throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::ExtractGridData_.cpp.\n\t No symmetry plane is defined for a symmetric grid!.", 0));
	gridData_.halfSymmetry = OW3DSeakeeping::UserInput.symx;

	// ==========================================================================
	// Find the grid which covers midship
	// ==========================================================================

	vector<double> minxs;
	for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
	{
		const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
		const vector<Index> &Is = be.surface_indices;
		const MappedGrid &mg = cg_[be.grid];
		const RealArray &x = mg.vertex()(Is[0], Is[1], Is[2], axis1);
		minxs.push_back(min(abs(x)));
	}

	gridData_.mid_grid_index = std::distance(std::begin(minxs), std::min_element(std::begin(minxs), std::end(minxs)));

	return 0;
}