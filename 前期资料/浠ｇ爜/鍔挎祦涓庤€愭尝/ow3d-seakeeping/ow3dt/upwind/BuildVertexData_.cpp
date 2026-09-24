#include "Upwind.h"

void OW3DSeakeeping::Upwind::BuildVertexData_(
	CompositeGrid &cg,
	const vector<realArray> &dphib_dx,
	const vector<realArray> &dphib_dz)
{
	for (unsigned int surface = 0; surface < nofs_; surface++)
	{
		vector<Index> I;
		I.resize(3);

		const Single_boundary_data &bs = boundariesData_->free[surface];
		const vector<Index> &Is = bs.surface_indices;
		const MappedGrid &mg = cg[bs.grid];

		getIndex(mg.dimension(), I[0], I[1], I[2]);

		if (Is[0].length() == 1 and I[0].length() > 1) // ******* biased index : 1 and 2
		{
			BuildUpwindStenciles_1_2_(surface, mg, Is, I, dphib_dx, dphib_dz);
		}

		if (Is[1].length() == 1 and I[1].length() > 1) // ******* biased index : 0 and 2
		{
			BuildUpwindStenciles_0_2_(surface, mg, Is, I, dphib_dx, dphib_dz);
		}

		if (Is[2].length() == 1 and I[2].length() > 1) // ******* biased index : 0 and 1
		{
			BuildUpwindStenciles_0_1_(surface, mg, Is, I, dphib_dx, dphib_dz);
		}

	} // end of loop over free surface

} // end of obtainVertexData_ private member function