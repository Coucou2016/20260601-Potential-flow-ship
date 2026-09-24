#include "FreeSurface.h"

void OW3DSeakeeping::FreeSurface::ExtractFreeSurfaceIndices_()
{
  // Around the body

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const MappedGrid &mg = (*cg_)[be.grid];

    Index I1, I2, I3;
    Index Igs1, Igs2, Igs3; // Second ghost layer indices

    getGhostIndex(mg.gridIndexRange(), be.side, be.axis, Igs1, Igs2, Igs3, gridData_->ghost_line);

    getIndex(mg.dimension(), I1, I2, I3);

    const vector<Index> &Ie = be.surface_indices;
    const vector<Index> &Ig = be.ghost_indices; // First ghost layer indices

    GBIX gbix;

    if (Ig[0].getLength() == 1 and I1.getLength() > 1)
    {
      gbix.iG1 = Ig[0];
      gbix.iG2 = I2;
      gbix.iG3 = I3;

      gbix.iB1 = Ie[0];
      gbix.iB2 = I2;
      gbix.iB3 = I3;
    }

    else if (Ig[1].getLength() == 1 and I2.getLength() > 1)
    {
      gbix.iG1 = I1;
      gbix.iG2 = Ig[1];
      gbix.iG3 = I3;

      gbix.iB1 = I1;
      gbix.iB2 = Ie[1];
      gbix.iB3 = I3;
    }

    else if (Ig[2].getLength() == 1 and I3.getLength() > 1)
    {
      gbix.iG1 = I1;
      gbix.iG2 = I2;
      gbix.iG3 = Ig[2];

      gbix.iB1 = I1;
      gbix.iB2 = I2;
      gbix.iB3 = Ie[2];
    }

    bodyInd_.push_back(gbix);
  }

  // Around the wall

  for (unsigned int surface = 0; surface < boundariesData_->absorbing.size(); surface++)
  {
    const Single_boundary_data &ba = boundariesData_->absorbing[surface];
    const MappedGrid &mg = (*cg_)[ba.grid];

    Index I1, I2, I3;
    Index Igs1, Igs2, Igs3; // Second ghost later indices

    getGhostIndex(mg.gridIndexRange(), ba.side, ba.axis, Igs1, Igs2, Igs3, gridData_->ghost_line);

    getIndex(mg.dimension(), I1, I2, I3);

    const vector<Index> &Ia = ba.surface_indices;
    const vector<Index> &Ig = ba.ghost_indices; // First ghost layer indices

    GBIX gbix;

    if (Ig[0].getLength() == 1 and I1.getLength() > 1)
    {
      gbix.iG1 = Ig[0];
      gbix.iG2 = I2;
      gbix.iG3 = I3;

      gbix.iB1 = Ia[0];
      gbix.iB2 = I2;
      gbix.iB3 = I3;
    }

    else if (Ig[1].getLength() == 1 and I2.getLength() > 1)
    {
      gbix.iG1 = I1;
      gbix.iG2 = Ig[1];
      gbix.iG3 = I3;

      gbix.iB1 = I1;
      gbix.iB2 = Ia[1];
      gbix.iB3 = I3;
    }

    else if (Ig[2].getLength() == 1 and I3.getLength() > 1)
    {
      gbix.iG1 = I1;
      gbix.iG2 = I2;
      gbix.iG3 = Ig[2];

      gbix.iB1 = I1;
      gbix.iB2 = I2;
      gbix.iB3 = Ia[2];
    }

    wallInd_.push_back(gbix);
  }
}