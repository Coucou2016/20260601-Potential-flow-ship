#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::Compute1DDerivatives(const RealArray &f, RealArray &df, int si, int ei, const RealArray &coefficients, Range range)
{
    df(range, Range(si, ei)) = 0;
    int order = coefficients.getLength(0) - 1;
    int N1 = ei - si + 1;

    const int stencil_point_count = order + 1;
    vector<Index> It;

    for (int i = 0; i < stencil_point_count; ++i)
    {
        if (i < ((stencil_point_count - 1) / 2))
        {
            Index I(i + si, 1); // left-centred schemes
            It.push_back(I);
        }
        else if (i > ((stencil_point_count - 1) / 2))
        {
            Index I(N1 - stencil_point_count + i + si, 1); // right-centred schemes
            It.push_back(I);
        }
        else
        {
            Index I(i + si, N1 - stencil_point_count + 1); // centered schemes
            It.push_back(I);
        }
    }
    for (int i = 0; i < stencil_point_count; ++i) // schemes
    {
        for (int j = 0; j < stencil_point_count; ++j) // stencil points
        {
            df(range, It[i]) += f(range, It[i] - i + j) * coefficients(i, j);
        }
    }
}