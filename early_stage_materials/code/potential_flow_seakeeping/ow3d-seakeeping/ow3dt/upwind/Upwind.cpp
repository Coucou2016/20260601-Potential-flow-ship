// This file contains the implemetation of the Biased class.

#include "Upwind.h"
#include "OW3DConstants.h"
#include <iomanip>

bool OW3DSeakeeping::Upwind::printx_ = (OW3DSeakeeping::long_print) ? true : false;
bool OW3DSeakeeping::Upwind::printz_ = (OW3DSeakeeping::long_print) ? true : false;

OW3DSeakeeping::Upwind::Upwind()
{
	nofs_ = 1;
	direction d;
	d.size[0] = 1;
	d.size[1] = 1;
	directions_.push_back(d);

	vertexData_ = new data **[nofs_];

	for (unsigned int surface = 0; surface < nofs_; surface++)
	{
		vertexData_[surface] = new data *[directions_[surface].size[0]];
		for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
		{
			vertexData_[surface][i] = new data[directions_[surface].size[1]];
		}
	}
}

OW3DSeakeeping::Upwind::Upwind(
	CompositeGrid &cg,
	const vector<realArray> &dphib_dx,
	const vector<realArray> &dphib_dz,
	const OW3DSeakeeping::Grid::GridData &gridData,
	int a,
	int b) : u_(a), d_(b), U_(OW3DSeakeeping::UserInput.U), nofs_(gridData.boundariesData.free.size()), gridData_(&gridData),
			 boundariesData_(&gridData.boundariesData), boundaryTypes_(&gridData.boundaryTypes)
{
	if (a < b or (a == 0 and b == 0) or (a < 0 or b < 0))
	{
		throw runtime_error(GetColoredMessage("\t Error (OW3D), Upwind::Upwind.cpp.\n\t Wrong stencil for biased differencing.", 0));
	}

	unsigned int surface, i;

	vertexData_ = new data **[nofs_]; // vertexData_ points to an array with the size of number of free surfaces.

	vector<Index> I;
	I.resize(3);

	// find the search directions and the sizes of vertexData_

	for (surface = 0; surface < nofs_; surface++)
	{
		const Single_boundary_data &bs = boundariesData_->free[surface];
		const vector<Index> &Is = bs.surface_indices;
		const MappedGrid &mg = cg[bs.grid];
		getIndex(mg.gridIndexRange(), I[0], I[1], I[2]);

		direction d;

		d.spacing[0] = mg.gridSpacing(0);
		d.spacing[1] = mg.gridSpacing(1);
		d.spacing[2] = mg.gridSpacing(2);

		d.Is = Is;
		d.grid = bs.grid;

		if (Is[0].length() == 1 and I[0].length() > 1)
		{
			d.index[0] = 1;
			d.index[1] = 2;
			d.size[0] = Is[1].length();
			d.size[1] = Is[2].length();
		}
		if (Is[1].length() == 1 and I[1].length() > 1)
		{
			d.index[0] = 0;
			d.index[1] = 2;
			d.size[0] = Is[0].length();
			d.size[1] = Is[2].length();
		}
		if (Is[2].length() == 1 and I[2].length() > 1)
		{
			d.index[0] = 0;
			d.index[1] = 1;
			d.size[0] = Is[0].length();
			d.size[1] = Is[1].length();
		}

		directions_.push_back(d);

		// allocate memory for vertexData_

		vertexData_[surface] = new data *[d.size[0]];

		for (i = 0; i < d.size[0]; i++)
		{
			vertexData_[surface][i] = new data[d.size[1]];
		}

	} // end of loop over free surface

	BuildVertexData_(cg, dphib_dx, dphib_dz);

	if (printx_)
		printx_ = false;
	if (printz_)
		printz_ = false;

} // end of the constructor

OW3DSeakeeping::Upwind &OW3DSeakeeping::Upwind::operator=(const Upwind &existing)
{
	if (this != &existing)
	{
		// De-allocate old memory for the target object

		for (unsigned int surface = 0; surface < nofs_; surface++)
		{
			for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
			{
				delete[] vertexData_[surface][i];
			}
			delete[] vertexData_[surface];
		}
		delete[] vertexData_;

		// copy the data members

		directions_ = existing.directions_;
		u_ = existing.u_;
		d_ = existing.d_;
		U_ = existing.U_;
		nofs_ = existing.nofs_;
		boundariesData_ = existing.boundariesData_;
		boundaryTypes_ = existing.boundaryTypes_;
		gridData_ = existing.gridData_;

		// allocate new memory for target object

		vertexData_ = new data **[nofs_];

		for (unsigned int surface = 0; surface < nofs_; surface++)
		{
			vertexData_[surface] = new data *[directions_[surface].size[0]];

			for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
			{
				vertexData_[surface][i] = new data[directions_[surface].size[1]];
			}
		}

		// assign the new memory to the existing vertexData_

		for (unsigned int surface = 0; surface < nofs_; surface++)
		{
			for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
			{
				for (unsigned int j = 0; j < directions_[surface].size[1]; j++)
				{
					vertexData_[surface][i][j] = existing.vertexData_[surface][i][j];
				}
			}
		}

	} // end of self-assignment check

	return *this;

} // end of assignment operator

OW3DSeakeeping::Upwind::~Upwind()
{
	for (unsigned int surface = 0; surface < nofs_; surface++)
	{
		for (unsigned int i = 0; i < directions_[surface].size[0]; i++)
		{
			delete[] vertexData_[surface][i];
		}

		delete[] vertexData_[surface];
	}

	delete[] vertexData_;
}

OW3DSeakeeping::Upwind::data ***OW3DSeakeeping::Upwind::GetVertexData()
{
	return vertexData_;
}

vector<OW3DSeakeeping::Upwind::direction> OW3DSeakeeping::Upwind::GetDirectionsData()
{
	return directions_;
}

void OW3DSeakeeping::Upwind::flipArray_(RealArray &array)
{
	if (array.getLength(1) != 1 or array.getLength(2) != 1)
	{
		throw runtime_error(GetColoredMessage("Error (OW3D), Upwind::Upwind.cpp.\n\t Error in array flipping.", 0));
	}

	RealArray temp = array;
	int base = array.getBase(0);
	int bound = array.getBound(0);

	int index_1 = array.getBound(1);
	int index_2 = array.getBound(2);

	for (int i = base; i <= bound; i++)
	{
		temp(i, index_1, index_2) = array(bound - i, index_1, index_2);
	}

	array = temp;
}
