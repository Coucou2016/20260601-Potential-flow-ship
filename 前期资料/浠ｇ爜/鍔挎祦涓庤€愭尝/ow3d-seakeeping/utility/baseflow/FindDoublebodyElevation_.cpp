#include "Baseflow.h"
#include "OW3DConstants.h"

int OW3DSeakeeping::Baseflow::FindDoublebodyElevation_(
    const int &i, const int &j, const int &k,
    const int &grid,
    const int &fs,
    const int &direction,
    const realCompositeGridFunction &func,
    const realArray &coord,
    const int &dp_s,
    const int &dp_n,
    realCompositeGridFunction &dbe)
{
    int w = 7;
    int hw = (w - 1) / 2; // w: the width of interpolation (must be odd)

    if (dp_s + dp_n + 1 < w)
    {
        throw runtime_error(GetColoredMessage("\t Error (OW3D), Baseflow::FindDoublebodyElevation_.cpp.\n\t Not enough grid points to find double body elevation.", 0));
    }

    int srest = hw - dp_s;
    int nrest = hw - dp_n;

    vector<double> interpCoeff(w), yc, fyc;

    if (direction == 0)
    {
        if (dp_s >= hw and dp_n >= hw) // enough disc. point around i (centered)
        {
            for (int p = i - hw; p <= i + hw; p++)
            {
                yc.push_back(coord(p, j, k));
                fyc.push_back(func[grid](p, j, k));
            }
        }
        else if (dp_s < hw) // not enough disc. point around i (off-centered)
        {
            for (int p = i - dp_s; p <= i + (hw + srest); p++)
            {
                yc.push_back(coord(p, j, k));
                fyc.push_back(func[grid](p, j, k));
            }
        }
        else if (dp_n < hw) // not enough disc. point around i (off-centered)
        {
            for (int p = i - (hw + nrest); p <= i + dp_n; p++)
            {
                yc.push_back(coord(p, j, k));
                fyc.push_back(func[grid](p, j, k));
            }
        }
        Polcoe_(yc, fyc, interpCoeff);                         // interpolation coefficients
        dbe[grid](fs, j, k) = Findroot_(interpCoeff, yc, fyc); // find the root
    }
    else if (direction == 1)
    {
        if (dp_s >= hw and dp_n >= hw) // enough disc. point around j (centered)
        {
            for (int p = j - hw; p <= j + hw; p++)
            {
                yc.push_back(coord(i, p, k));
                fyc.push_back(func[grid](i, p, k));
            }
        }
        else if (dp_s < hw) // not enough disc. point around j (off-centered)
        {
            for (int p = j - dp_s; p <= j + (hw + srest); p++)
            {
                yc.push_back(coord(i, p, k));
                fyc.push_back(func[grid](i, p, k));
            }
        }
        else if (dp_n < hw) // not enough disc. point around j (off-centered)
        {
            for (int p = j - (hw + nrest); p <= j + dp_n; p++)
            {
                yc.push_back(coord(i, p, k));
                fyc.push_back(func[grid](i, p, k));
            }
        }
        Polcoe_(yc, fyc, interpCoeff);                         // interpolation coefficients
        dbe[grid](i, fs, k) = Findroot_(interpCoeff, yc, fyc); // find the root
    }
    else
    {
        if (dp_s >= hw and dp_n >= hw) // enough disc. point around k (centered)
        {
            for (int p = k - hw; p <= k + hw; p++)
            {
                yc.push_back(coord(i, j, p));
                fyc.push_back(func[grid](i, j, p));
            }
        }
        else if (dp_s < hw) // not enough disc. point around k (off-centered)
        {
            for (int p = k - dp_s; p <= k + (hw + srest); p++)
            {
                yc.push_back(coord(i, j, p));
                fyc.push_back(func[grid](i, j, p));
            }
        }
        else if (dp_n < hw) // not enough disc. point around k (off-centered)
        {
            for (int p = k - (hw + nrest); p <= k + dp_n; p++)
            {
                yc.push_back(coord(i, j, p));
                fyc.push_back(func[grid](i, j, p));
            }
        }
        Polcoe_(yc, fyc, interpCoeff);                         // interpolation coefficients
        dbe[grid](i, j, fs) = Findroot_(interpCoeff, yc, fyc); // find the root
    }

    return 0;
}