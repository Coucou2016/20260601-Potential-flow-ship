#include "Upwind.h"

void OW3DSeakeeping::Upwind::ComputeDerivatives(
    const realCompositeGridFunction &u,
    realCompositeGridFunction &dudx,
    realCompositeGridFunction &dudz)
{
    int i, j;

    for (unsigned int surface = 0; surface < nofs_; surface++)
    {
        int grid = directions_[surface].grid;

        if (directions_[surface].index[0] == 1 and directions_[surface].index[1] == 2)
        {
            for (i = directions_[surface].Is[1].getBase(); i <= directions_[surface].Is[1].getBound(); i++)
                for (j = directions_[surface].Is[2].getBase(); j <= directions_[surface].Is[2].getBound(); j++)
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        dudx[grid](directions_[surface].Is[0].getBase(), i, j) =
                            sum(u[grid](directions_[surface].Is[0].getBase(), vertexData_[surface][i][j].R1x, j) * vertexData_[surface][i][j].C1x) *
                                vertexData_[surface][i][j].vder1x * 1.0 / directions_[surface].spacing[1] +
                            sum(u[grid](directions_[surface].Is[0].getBase(), i, vertexData_[surface][i][j].R2x) * vertexData_[surface][i][j].C2x) *
                                vertexData_[surface][i][j].vder2x * 1.0 / directions_[surface].spacing[2];
                        //
                        dudz[grid](directions_[surface].Is[0].getBase(), i, j) =
                            sum(u[grid](directions_[surface].Is[0].getBase(), vertexData_[surface][i][j].R1z, j) * vertexData_[surface][i][j].C1z) *
                                vertexData_[surface][i][j].vder1z * 1.0 / directions_[surface].spacing[1] +
                            sum(u[grid](directions_[surface].Is[0].getBase(), i, vertexData_[surface][i][j].R2z) * vertexData_[surface][i][j].C2z) *
                                vertexData_[surface][i][j].vder2z * 1.0 / directions_[surface].spacing[2];
                    }

        } // End for "0" index

        else if (directions_[surface].index[0] == 0 and directions_[surface].index[1] == 2)
        {
            for (i = directions_[surface].Is[0].getBase(); i <= directions_[surface].Is[0].getBound(); i++)
                for (j = directions_[surface].Is[2].getBase(); j <= directions_[surface].Is[2].getBound(); j++)
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        dudx[grid](i, directions_[surface].Is[1].getBase(), j) =
                            sum(u[grid](vertexData_[surface][i][j].R0x, directions_[surface].Is[1].getBase(), j) * vertexData_[surface][i][j].C0x) *
                                vertexData_[surface][i][j].vder0x * 1.0 / directions_[surface].spacing[0] +
                            sum(u[grid](i, directions_[surface].Is[1].getBase(), vertexData_[surface][i][j].R2x) * vertexData_[surface][i][j].C2x) *
                                vertexData_[surface][i][j].vder2x * 1.0 / directions_[surface].spacing[2];
                        //
                        dudz[grid](i, directions_[surface].Is[1].getBase(), j) =
                            sum(u[grid](vertexData_[surface][i][j].R0z, directions_[surface].Is[1].getBase(), j) * vertexData_[surface][i][j].C0z) *
                                vertexData_[surface][i][j].vder0z * 1.0 / directions_[surface].spacing[0] +
                            sum(u[grid](i, directions_[surface].Is[1].getBase(), vertexData_[surface][i][j].R2z) * vertexData_[surface][i][j].C2z) *
                                vertexData_[surface][i][j].vder2z * 1.0 / directions_[surface].spacing[2];
                    }

        } // End for "1" index

        else
        {
            for (i = directions_[surface].Is[0].getBase(); i <= directions_[surface].Is[0].getBound(); i++)
                for (j = directions_[surface].Is[1].getBase(); j <= directions_[surface].Is[1].getBound(); j++)
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        dudx[grid](i, j, directions_[surface].Is[2].getBase()) =
                            sum(u[grid](vertexData_[surface][i][j].R0x, j, directions_[surface].Is[2].getBase()) * vertexData_[surface][i][j].C0x) *
                                vertexData_[surface][i][j].vder0x * 1.0 / directions_[surface].spacing[0] +
                            sum(u[grid](i, vertexData_[surface][i][j].R1x, directions_[surface].Is[2].getBase()) * vertexData_[surface][i][j].C1x) *
                                vertexData_[surface][i][j].vder1x * 1.0 / directions_[surface].spacing[1];
                        //
                        dudz[grid](i, j, directions_[surface].Is[2].getBase()) =
                            sum(u[grid](vertexData_[surface][i][j].R0z, j, directions_[surface].Is[2].getBase()) * vertexData_[surface][i][j].C0z) *
                                vertexData_[surface][i][j].vder0z * 1.0 / directions_[surface].spacing[0] +
                            sum(u[grid](i, vertexData_[surface][i][j].R1z, directions_[surface].Is[2].getBase()) * vertexData_[surface][i][j].C1z) *
                                vertexData_[surface][i][j].vder1z * 1.0 / directions_[surface].spacing[1];
                    }

        } // End for "2" index

    } // End of loop over free surfaces
}