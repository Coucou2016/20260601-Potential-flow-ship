#include "Filter.h"

void OW3DSeakeeping::Filter::ApplyFilter(realCompositeGridFunction &elevation)
{
    int i, j; // filtering indices

    for (unsigned int surface = 0; surface < nofs_; surface++)
    {
        int grid = directions_[surface].grid;

        realMappedGridFunction eta = elevation[grid]; // keep the original data

        if (directions_[surface].index[0] == 1 and directions_[surface].index[1] == 2)
        {
            for (i = directions_[surface].Is[1].getBase(); i <= directions_[surface].Is[1].getBound(); i++)
            {
                for (j = directions_[surface].Is[2].getBase(); j <= directions_[surface].Is[2].getBound(); j++)
                {
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        elevation[grid](directions_[surface].Is[0].getBase(), i, j) =
                            sum((vertexData_[surface][i][j].f1 - sigma_ * vertexData_[surface][i][j].C1) *
                                eta(directions_[surface].Is[0].getBase(), vertexData_[surface][i][j].R1, j)); // filter along axis 1

                    } // end of mask

                } // end of j

            } // end of i

            if (directions_[surface].Is[2].getBound() != 0)
            {
                eta = elevation[grid];

                for (i = directions_[surface].Is[1].getBase(); i <= directions_[surface].Is[1].getBound(); i++)
                {
                    for (j = directions_[surface].Is[2].getBase(); j <= directions_[surface].Is[2].getBound(); j++)
                    {
                        if (vertexData_[surface][i][j].mask > 0)
                        {
                            elevation[grid](directions_[surface].Is[0].getBase(), i, j) =
                                sum((vertexData_[surface][i][j].f2 - sigma_ * vertexData_[surface][i][j].C2) *
                                    eta(directions_[surface].Is[0].getBase(), i, vertexData_[surface][i][j].R2)); // filter along axis 2

                        } // end of mask

                    } // end of j

                } // end of i
            }

        } // end of surface index "0" ************************************************************

        else if (directions_[surface].index[0] == 0 and directions_[surface].index[1] == 2)
        {
            for (i = directions_[surface].Is[0].getBase(); i <= directions_[surface].Is[0].getBound(); i++)
            {
                for (j = directions_[surface].Is[2].getBase(); j <= directions_[surface].Is[2].getBound(); j++)
                {
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        elevation[grid](i, directions_[surface].Is[1].getBase(), j) =
                            sum((vertexData_[surface][i][j].f0 - sigma_ * vertexData_[surface][i][j].C0) *
                                eta(vertexData_[surface][i][j].R0, directions_[surface].Is[1].getBase(), j)); // filter along axis 0

                    } // end of mask

                } // end of j

            } // end of i

            if (directions_[surface].Is[2].getBound() != 0)
            {
                eta = elevation[grid];

                for (i = directions_[surface].Is[0].getBase(); i <= directions_[surface].Is[0].getBound(); i++)
                {
                    for (j = directions_[surface].Is[2].getBase(); j <= directions_[surface].Is[2].getBound(); j++)
                    {
                        if (vertexData_[surface][i][j].mask > 0)
                        {
                            elevation[grid](i, directions_[surface].Is[1].getBase(), j) =
                                sum((vertexData_[surface][i][j].f2 - sigma_ * vertexData_[surface][i][j].C2) *
                                    eta(i, directions_[surface].Is[1].getBase(), vertexData_[surface][i][j].R2)); // filter along axis 2

                        } // end of mask

                    } // end of j

                } // end of i
            }

        } // end of surface index "1" ************************************************************

        else
        {
            for (i = directions_[surface].Is[0].getBase(); i <= directions_[surface].Is[0].getBound(); i++)
            {
                for (j = directions_[surface].Is[1].getBase(); j <= directions_[surface].Is[1].getBound(); j++)
                {
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        elevation[grid](i, j, directions_[surface].Is[2].getBase()) =
                            sum((vertexData_[surface][i][j].f0 - sigma_ * vertexData_[surface][i][j].C0) *
                                eta(vertexData_[surface][i][j].R0, j, directions_[surface].Is[2].getBase())); // filter along axis 0

                    } // end of mask

                } // end of j

            } // end of i

            eta = elevation[grid];

            for (i = directions_[surface].Is[0].getBase(); i <= directions_[surface].Is[0].getBound(); i++)
            {
                for (j = directions_[surface].Is[1].getBase(); j <= directions_[surface].Is[1].getBound(); j++)
                {
                    if (vertexData_[surface][i][j].mask > 0)
                    {
                        elevation[grid](i, j, directions_[surface].Is[2].getBase()) =
                            sum((vertexData_[surface][i][j].f1 - sigma_ * vertexData_[surface][i][j].C1) *
                                eta(i, vertexData_[surface][i][j].R1, directions_[surface].Is[2].getBase())); // filter along axis 1

                    } // end of mask

                } // end of j

            } // end of i

        } // end of surface index "2" ************************************************************

    } // end of loop over free surfaces
}