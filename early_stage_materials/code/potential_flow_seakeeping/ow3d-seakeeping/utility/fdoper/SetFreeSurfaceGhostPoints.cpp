#include "OvertureTypes.h"
#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::SetFreeSurfaceGhostPoints(
	const CompositeGrid &cg,
	const All_boundaries_data &boundariesData,
	realCompositeGridFunction &eta,
	realCompositeGridFunction &phi,
	const double &U,
	const double &ghostLines)
{
	int bc;
	int time = 0;

	// around the body
	for (unsigned int surface = 0; surface < boundariesData.exciting.size(); ++surface)
	{
		const Single_boundary_data &be = boundariesData.exciting[surface];
		const MappedGrid &mg = cg[be.grid];
		Index I1, I2, I3, ie1, ie2, ie3, ig1, ig2, ig3;
		Index Igs1, Igs2, Igs3;
		getGhostIndex(mg.gridIndexRange(), be.side, be.axis, Igs1, Igs2, Igs3, ghostLines);
		getIndex(mg.dimension(), I1, I2, I3);
		const vector<Index> &Ie = be.surface_indices;
		const vector<Index> &Ig = be.ghost_indices;
		const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

		// homogeneous neumann everywhere for the free surface elevation
		if (Ig[0].getLength() == 1 and I1.getLength() > 1)
		{
			ig1 = Ig[0];
			ig2 = I2;
			ig3 = I3;
			ie1 = Ie[0];
			ie2 = I2;
			ie3 = I3;

			eta[be.grid](Ig[0], I2, I3) = eta[be.grid](abs(Ie[0].getBase() - 1), I2, I3);

			if (ghostLines == 2) // * second ghost layer
				eta[be.grid](Igs1, I2, I3) = eta[be.grid](abs(Ie[0].getBase() - 2), I2, I3);
		}
		if (Ig[1].getLength() == 1 and I2.getLength() > 1)
		{
			ig1 = I1;
			ig2 = Ig[1];
			ig3 = I3;
			ie1 = I1;
			ie2 = Ie[1];
			ie3 = I3;

			eta[be.grid](I1, Ig[1], I3) = eta[be.grid](I1, abs(Ie[1].getBase() - 1), I3);

			if (ghostLines == 2) // * second ghost layer
				eta[be.grid](I1, Igs2, I3) = eta[be.grid](I1, abs(Ie[1].getBase() - 2), I3);
		}
		if (Ig[2].getLength() == 1 and I3.getLength() > 1)
		{
			ig1 = I1;
			ig2 = I2;
			ig3 = Ig[2];
			ie1 = I1;
			ie2 = I2;
			ie3 = Ie[2];

			eta[be.grid](I1, I2, Ig[2]) = eta[be.grid](I1, I2, abs(Ie[2].getBase() - 1));

			if (ghostLines == 2) // * second ghost layer
				eta[be.grid](I1, I2, Igs3) = eta[be.grid](I1, I2, abs(Ie[2].getBase() - 2));
		}
		// extrapolation where u.n<0
		if (be.side == 0 and be.axis == 0)
			bc = BCTypes::boundary1;
		if (be.side == 1 and be.axis == 0)
			bc = BCTypes::boundary2;
		if (be.side == 0 and be.axis == 1)
			bc = BCTypes::boundary3;
		if (be.side == 1 and be.axis == 1)
			bc = BCTypes::boundary4;
		if (be.side == 0 and be.axis == 2)
			bc = BCTypes::boundary5;
		if (be.side == 1 and be.axis == 2)
			bc = BCTypes::boundary6;

		BoundaryConditionParameters exparam1;
		exparam1.setUseMask();
		intArray exMask(ig1, ig2, ig3);
		exMask = 0;
		where(U * vbn(ie1, ie2, ie3, axis1) < 0)
		{
			exMask = 1;
		}
		exparam1.mask() = exMask;

		// * first ghost layer
		eta[be.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam1);
		phi[be.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam1);

		if (ghostLines == 2) // * second ghost layer
		{
			BoundaryConditionParameters exparam2;
			exparam2.setUseMask();
			exparam2.mask() = exMask;
			exparam2.lineToAssign = ghostLines;

			eta[be.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam2);
			phi[be.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam2);
		}

	} // end of the block for the ghost points around the body

	// around the wall
	for (unsigned int surface = 0; surface < boundariesData.absorbing.size(); ++surface)
	{
		const Single_boundary_data &ba = boundariesData.absorbing[surface];
		const MappedGrid &mg = cg[ba.grid];
		Index I1, I2, I3, ia1, ia2, ia3, ig1, ig2, ig3;
		Index Igs1, Igs2, Igs3;
		getGhostIndex(mg.gridIndexRange(), ba.side, ba.axis, Igs1, Igs2, Igs3, ghostLines);
		getIndex(mg.dimension(), I1, I2, I3);
		const vector<Index> &Ia = ba.surface_indices;
		const vector<Index> &Ig = ba.ghost_indices;
		const RealArray &vbn = mg.vertexBoundaryNormal(ba.side, ba.axis);

		// homogeneous neumann everywhere for free surface elevation
		if (Ig[0].getLength() == 1 and I1.getLength() > 1)
		{
			ig1 = Ig[0];
			ig2 = I2;
			ig3 = I3;
			ia1 = Ia[0];
			ia2 = I2;
			ia3 = I3;

			eta[ba.grid](Ig[0], I2, I3) = eta[ba.grid](abs(Ia[0].getBase() - 1), I2, I3);
			if (ghostLines == 2) // * second ghost layer
				eta[ba.grid](Igs1, I2, I3) = eta[ba.grid](abs(Ia[0].getBase() - 2), I2, I3);
		}
		if (Ig[1].getLength() == 1 and I2.getLength() > 1)
		{
			ig1 = I1;
			ig2 = Ig[1];
			ig3 = I3;
			ia1 = I1;
			ia2 = Ia[1];
			ia3 = I3;
			eta[ba.grid](I1, Ig[1], I3) = eta[ba.grid](I1, abs(Ia[1].getBase() - 1), I3);
			if (ghostLines == 2) // * second ghost layer
				eta[ba.grid](I1, Igs2, I3) = eta[ba.grid](I1, abs(Ia[1].getBase() - 2), I3);
		}
		if (Ig[2].getLength() == 1 and I3.getLength() > 1)
		{
			ig1 = I1;
			ig2 = I2;
			ig3 = Ig[2];
			ia1 = I1;
			ia2 = I2;
			ia3 = Ia[2];
			eta[ba.grid](I1, I2, Ig[2]) = eta[ba.grid](I1, I2, abs(Ia[2].getBase() - 1));
			if (ghostLines == 2) // * second ghost layer
				eta[ba.grid](I1, I2, Igs3) = eta[ba.grid](I1, I2, abs(Ia[2].getBase() - 2));
		}

		// extrapolation where u.n<0
		if (ba.side == 0 and ba.axis == 0)
			bc = BCTypes::boundary1;
		if (ba.side == 1 and ba.axis == 0)
			bc = BCTypes::boundary2;
		if (ba.side == 0 and ba.axis == 1)
			bc = BCTypes::boundary3;
		if (ba.side == 1 and ba.axis == 1)
			bc = BCTypes::boundary4;
		if (ba.side == 0 and ba.axis == 2)
			bc = BCTypes::boundary5;
		if (ba.side == 1 and ba.axis == 2)
			bc = BCTypes::boundary6;

		BoundaryConditionParameters exparam1;
		exparam1.setUseMask();
		exparam1.orderOfExtrapolation = 4;
		intArray exMask(ig1, ig2, ig3);
		exMask = 0;
		where(U * vbn(ia1, ia2, ia3, axis1) < 0)
		{
			exMask = 1;
		}
		exparam1.mask() = exMask;

		// * first ghost layer
		eta[ba.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam1);
		phi[ba.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam1);

		if (ghostLines == 2) // * second ghost layer
		{
			BoundaryConditionParameters exparam2;
			exparam2.setUseMask();
			exparam2.mask() = exMask;
			exparam2.lineToAssign = ghostLines;

			eta[ba.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam2);
			phi[ba.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam2);
		}
	} // end of the block for ghost points around the wall

} // end of setFreeSurfaceGhostPoints
