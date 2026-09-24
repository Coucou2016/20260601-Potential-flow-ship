#include "GLTree.h"
#include <math.h>

// Author: Luigi Giaccari
// giaccariluigi@msn.com

// Some macros

// Compute th current distance between query point and point in the tree
#define CurrentDistance (px[idp] - pk[0]) * (px[idp] - pk[0]) + (py[idp] - pk[1]) * (py[idp] - pk[1])

// Constructor
GLTREE::GLTREE(double *px, double *py, int Np) // constructor

{

    const double npbox = 2; // number of exitimated point each leaf
    int i;                  // counter
    int idxi, idyi;
    double A;
    double Maxx = -HUGE_VAL;
    double Maxy = -HUGE_VAL;
    double step;
    double nxdouble, nydouble;
    int Nb;
    int id;
    int *idStore;

    N = Np;
    Leaves = new int[N];
    idStore = new int[N]; // Store for integer idBoxes data

    Minx = HUGE_VAL;
    Miny = HUGE_VAL;
    // Determinazione valori max e min
    for (i = 0; i < N; i++)
    {
        if (px[i] < Minx)
        {
            Minx = px[i];
        }

        if (px[i] > Maxx)
        {
            Maxx = px[i];
        }

        if (py[i] < Miny)
        {
            Miny = py[i];
        }

        if (py[i] > Maxy)
        {
            Maxy = py[i];
        }
    }

    Nb = (int)((N / npbox) + .5);
    A = (Maxx - Minx) * (Maxy - Miny);
    step = sqrt(A / Nb); // size of leaf
    nxdouble = (Maxx - Minx) / step;
    nydouble = (Maxy - Miny) / step;
    nxdouble = (int)(nxdouble + .5); // numero di foglie x , floor per approssimare per difetto
    nydouble = (int)(nydouble + .5); // numero di foglie y , consente l'uso di array predimensionati
    if ((Maxx - Minx) > (Maxy - Miny))
    {
        step = Maxx - Minx;
    }
    else
    {
        step = Maxy - Miny;
    }
    Toll = 1e-9 * step;
    PX = (Maxx - Minx + 1e4 * Toll) / (nxdouble); // passo
    PY = (Maxy - Miny + 1e4 * Toll) / (nydouble); // 1e-9 per aumentare il passo

    nxint = nxdouble;
    nyint = nydouble;
    Nb = nxint * nyint; // real number of leaves

    LeavesFinder1 = new int[Nb];
    LeavesFinder2 = new int[Nb];
    int *count;
    count = new int[Nb];

    for (i = 0; i < Nb; i++)
    {
        count[i] = 0;
        LeavesFinder1[i] = 0;
        LeavesFinder2[i] = 0;
    }

    // first loop to count points
    for (i = 0; i < N; i++)
    {

        idxi = (px[i] - Minx + Toll) / PX;
        idyi = (py[i] - Miny + Toll) / PY;
        id = nyint * idxi + idyi;
        LeavesFinder2[id] = LeavesFinder2[id] + 1; // temporary use as counter
        idStore[i] = id;
    }

    int idend = -1;
    int idstart;
    for (i = 0; i < Nb; i++)

    {
        if (LeavesFinder2[i] > 0)
        {
            idstart = idend + 1;
            idend = idstart + LeavesFinder2[i] - 1;
            LeavesFinder1[i] = idstart;
            LeavesFinder2[i] = idend;
        }
        else
            LeavesFinder2[i] = -1; // box is empty
    }

    for (i = 0; i < N; i++)
    {
        id = idStore[i];
        idstart = LeavesFinder1[id];
        Leaves[idstart + count[id]] = i;
        count[id] = count[id] + 1;
    }

    // inizilize for range search
    RangeStore = new int[N];

    // avoid memory leaks
    delete[] count;
    delete[] idStore;
}

GLTREE::~GLTREE() // destructor
{
    delete[] Leaves;
    delete[] LeavesFinder1;
    delete[] LeavesFinder2;
    delete[] RangeStore;
}

void GLTREE::SearchClosest(double *px, double *py, double *pk, int *idc, double *mindist)
{ /// Find the closest point using built Leaves

    int c;
    int ic1 = 0;
    int ic2 = 0;
    int jc1 = 0;
    int jc2 = 0;
    int id;
    int ptr;
    int idp;
    int idxi, idyi;
    bool goon;
    double sqrdist = HUGE_VAL;
    double dyu, dxd, dyd, dxu;
    int ii, jj;

    *mindist = HUGE_VAL;

    idxi = (pk[0] - Minx + Toll) / PX;
    if (idxi < 0)
    {
        idxi = 0;
        dxd = Minx - pk[0];
        dxu = dxd + PX;
    }

    else if (idxi > nxint - 1)
    {
        idxi = nxint - 1;
        dxd = pk[0] - (Minx + idxi * PX);
        dxu = dxd - PX;
    }
    else
    {
        dxd = pk[0] - (Minx + idxi * PX);
        dxu = Minx + (idxi + 1) * PX - pk[0];
    }

    idyi = (pk[1] - Miny + Toll) / PY;
    if (idyi < 0)
    {
        idyi = 0;
        dyd = Miny - pk[1];
        dyu = dyd + PY; // distance up y
    }

    else if (idyi > nyint - 1)
    {
        idyi = nyint - 1;
        dyd = pk[1] - (Miny + idyi * PY); // distance up y
        dyu = dyd - PY;
    }
    else
    {
        dyu = Miny + (idyi + 1) * PY - pk[1]; // distance up y
        dyd = pk[1] - (Miny + idyi * PY);
    }

    id = nyint * idxi + idyi;
    // search in the first leaf
    if (LeavesFinder2[id] > -1)
    {
        ptr = LeavesFinder1[id];
        while (ptr <= LeavesFinder2[id])
        {
            idp = Leaves[ptr];
            if (CurrentDistance < sqrdist)
            {
                *idc = idp;
                sqrdist = CurrentDistance;
                *mindist = sqrt(sqrdist);
            }
            ptr = ptr + 1;
        }
    }

    c = 1;
    do
    {
        goon = false;

        if (dxd < *mindist && idxi - c > -1)
        {
            goon = true;
            ic1 = -c;
            ii = -c;
            for (jj = jc1; jj <= jc2; jj++)

            { // leaf search
                id = nyint * (idxi + ii) + idyi + jj;
                if (LeavesFinder2[id] < 0)
                {
                    continue;
                } // leaf is empty
                ptr = LeavesFinder1[id];
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance < sqrdist)
                    {
                        *idc = idp;
                        sqrdist = CurrentDistance;
                        *mindist = sqrt(sqrdist);
                    }
                    ptr = ptr + 1;
                }
            }
            dxd = dxd + PX;
        }

        if (dxu < *mindist && idxi + c < nxint)
        {
            goon = true;
            ic2 = c;
            ii = c;
            for (jj = jc1; jj <= jc2; jj++)

            { // leaf search
                id = nyint * (idxi + ii) + idyi + jj;
                if (LeavesFinder2[id] < 0)
                {
                    continue;
                }
                ptr = LeavesFinder1[id];
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance < sqrdist)
                    {
                        *idc = idp;
                        sqrdist = CurrentDistance;
                        *mindist = sqrt(sqrdist);
                    }
                    ptr = ptr + 1;
                }
            }
            dxu = dxu + PX;
        }

        if (dyu < *mindist && idyi + c < nyint)
        {
            goon = true;
            jc2 = c;

            jj = c;
            for (ii = ic1; ii <= ic2; ii++)

            { // leaf search

                id = nyint * (idxi + ii) + idyi + jj;
                if (LeavesFinder2[id] < 0)
                {
                    continue;
                }
                ptr = LeavesFinder1[id];
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance < sqrdist)
                    {
                        *idc = idp;
                        sqrdist = CurrentDistance;
                        *mindist = sqrt(sqrdist);
                    }
                    ptr = ptr + 1;
                }
            }
            dyu = dyu + PY;
        }
        if (dyd < *mindist && idyi - c > -1)
        {
            goon = true;
            jc1 = -c;

            jj = -c;
            for (ii = ic1; ii <= ic2; ii++)

            { // leaf search
                id = nyint * (idxi + ii) + idyi + jj;
                if (LeavesFinder2[id] < 0)
                {
                    continue;
                } // leaf is empty
                ptr = LeavesFinder1[id];
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance < sqrdist)
                    {
                        *idc = idp;
                        sqrdist = CurrentDistance;
                        *mindist = sqrt(sqrdist);
                    }
                    ptr = ptr + 1;
                }
            }
            dyd = dyd + PY;
        }

        c = c + 1;
    } while (goon);

    return;
}

int *GLTREE::SearchRadius(double *px, double *py, double *pk, double r, int *nr)

{ /// Finds points inside a given radius using built Leaves

    int c = 0; // counter numbers of points found
    int ic1;
    int ic2;
    int jc1;
    int jc2;

    int id;
    int ptr;
    int idp;
    int *idc; // Now idc is an array
    int idxi, idyi;
    double sqrdist = r * r;
    int ii;

    // checking point coordinates
    idxi = (pk[0] - Minx + Toll) / PX;
    idyi = (pk[1] - Miny + Toll) / PY;

    // check range for leaves search
    ic1 = idxi - (r / PX + 1); // plus one so we are sure to check all leaves
    ic2 = idxi + r / PX + 1;

    jc1 = idyi - (r / PY + 1);
    jc2 = idyi + r / PY + 1;

    // Get idxi idyi inside the bbox
    if (ic1 < 0)
    {
        ic1 = 0;
    }
    else if (ic1 > nxint - 1)
    {
        ic1 = nxint - 1;
    }

    if (ic2 > nxint - 1)
    {
        ic2 = nxint - 1;
    }
    else if (ic2 < 0)
    {
        ic2 = 0;
    }

    if (jc1 < 0)
    {
        jc1 = 0;
    }
    else if (jc1 > nyint - 1)
    {
        jc1 = nyint - 1;
    }

    if (jc2 > nyint - 1)
    {
        jc2 = nyint - 1;
    }
    else if (jc2 < 0)
    {
        jc2 = 0;
    }

    // Area Search

    for (idxi = ic1; idxi <= ic2; idxi++)
    {
        for (idyi = jc1; idyi <= jc2; idyi++)
        {
            id = nyint * idxi + idyi;

            // search in the area
            if (LeavesFinder2[id] > -1)
            {
                ptr = LeavesFinder1[id];
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance <= sqrdist) // is it in radius?
                    {
                        RangeStore[c] = idp;
                        c = c + 1;
                    }
                    ptr = ptr + 1;
                }
            }
        }
    }

    // Search is over let's copy the results in the output array
    idc = new int[c];
    for (ii = 0; ii < c; ii++)
    {
        idc[ii] = RangeStore[ii];
    }

    *nr = c; // return number of found points
    return idc;
}

void GLTREE::SearchKClosest(double *px, double *py, double *pk, int k, int *idc, double *distances)

{ /// Finds the k closest point using built Leaves

    int c, n, count; // level counter,insert counter,position of new point
    int ic1 = 0;
    int ic2 = 0;
    int jc1 = 0;
    int jc2 = 0;
    int id;
    int ptr;
    int idp;
    int idxi, idyi;
    bool escape;
    double sqrdist = HUGE_VAL;
    double mindist = HUGE_VAL;
    double dyu, dxd, dyd, dxu;
    int ii, jj;

    // Set huge the distances value
    for (ii = 0; ii < k; ii++)
    {
        distances[ii] = HUGE_VAL;
    }

    idxi = (pk[0] - Minx + Toll) / PX;
    if (idxi < 0)
    {
        idxi = 0;
        dxd = (Minx + idxi * PX) - pk[0];
        dxu = Minx + (idxi + 1) * PX - pk[0];
    }

    else if (idxi > nxint - 1)
    {
        idxi = nxint - 1;
        dxd = pk[0] - (Minx + idxi * PX);
        dxu = pk[0] - (Minx + (idxi + 1) * PX);
    }
    else
    {
        dxd = pk[0] - (Minx + idxi * PX);
        dxu = Minx + (idxi + 1) * PX - pk[0];
    }

    idyi = (pk[1] - Miny + Toll) / PY;
    if (idyi < 0)
    {
        idyi = 0;
        dyu = Miny + (idyi + 1) * PY - pk[1]; // distance up y
        dyd = (Miny + idyi * PY) - pk[1];
    }

    else if (idyi > nyint - 1)
    {
        idyi = nyint - 1;
        dyu = pk[1] - (Miny + (idyi + 1) * PY); // distance up y
        dyd = pk[1] - (Miny + idyi * PY);
    }
    else
    {
        dyu = Miny + (idyi + 1) * PY - pk[1]; // distance up y
        dyd = pk[1] - (Miny + idyi * PY);
    }

    id = nyint * idxi + idyi;
    // search in the first leaf
    if (LeavesFinder2[id] > -1)
    {
        ptr = LeavesFinder1[id];
        while (ptr <= LeavesFinder2[id])
        {
            idp = Leaves[ptr];
            if (CurrentDistance < sqrdist)
            {
                sqrdist = sqrt(CurrentDistance); // non e la distanza al quadrato ma
                // � meglio calcolare adesso la radice q cos� ritorniamo le distanze vere
                count = 0;
                for (n = 1; n < k; n++) // FInd new point position
                {
                    if (sqrdist < (distances[n]))
                    {
                        count = count + 1;
                    }
                    else
                    {
                        break;
                    }
                }
                for (n = 0; n < count; n++) //<--------Evitare questo ciclo in una revisione!!!
                {
                    idc[n] = idc[n + 1];
                    distances[n] = distances[n + 1];
                }
                idc[count] = idp;
                distances[count] = sqrdist;
                mindist = distances[0];      // minima distanza di ricerca( max del set)
                sqrdist = mindist * mindist; // la stessa al quadrato per il confronto
            }
            ptr = ptr + 1;
        }
    }

    for (c = 1; c < N; c++)
    {
        escape = true;

        if (dxd < mindist && idxi - c > -1)
        {
            escape = false;
            ic1 = -c;
            ii = -c;
            for (jj = jc1; jj <= jc2; jj++)

            { // leaf search
                id = nyint * (idxi + ii) + idyi + jj;
                if (LeavesFinder2[id] < 0)
                {
                    continue;
                }                        // leaf is empty
                ptr = LeavesFinder1[id]; // future improvement check first and second ptrBoxes
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance < sqrdist)
                    {
                        sqrdist = sqrt(CurrentDistance); // non e la distanza al quadrato ma
                        // � meglio calcolare adesso la radice q cos� ritorniamo le distanze vere
                        count = 0;
                        for (n = 1; n < k; n++) // FInd new point position
                        {
                            if (sqrdist < (distances[n]))
                            {
                                count = count + 1;
                            }
                            else
                            {
                                break;
                            }
                        }
                        for (n = 0; n < count; n++) //<--------Evitare questo ciclo in una revisione!!!
                        {
                            idc[n] = idc[n + 1];
                            distances[n] = distances[n + 1];
                        }
                        idc[count] = idp;
                        distances[count] = sqrdist;
                        mindist = distances[0];      // minima distanza di ricerca( max del set)
                        sqrdist = mindist * mindist; // la stessa al quadrato per il confronto
                    }
                    ptr = ptr + 1;
                }
            }
            dxd = dxd + PX;
        }

        if (dxu < mindist && idxi + c < nxint)
        {
            escape = false;
            ic2 = c;
            ii = c;
            for (jj = jc1; jj <= jc2; jj++)

            { // leaf search
                id = nyint * (idxi + ii) + idyi + jj;
                if (LeavesFinder2[id] < 0)
                {
                    continue;
                }
                ptr = LeavesFinder1[id]; // future improvement check first and second ptrBoxes
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance < sqrdist)
                    {
                        sqrdist = sqrt(CurrentDistance); // non e la distanza al quadrato ma
                        // � meglio calcolare adesso la radice q cos� ritorniamo le distanze vere
                        count = 0;
                        for (n = 1; n < k; n++) // FInd new point position
                        {
                            if (sqrdist < (distances[n]))
                            {
                                count = count + 1;
                            }
                            else
                            {
                                break;
                            }
                        }
                        for (n = 0; n < count; n++) //<--------Evitare questo ciclo in una revisione!!!
                        {
                            idc[n] = idc[n + 1];
                            distances[n] = distances[n + 1];
                        }
                        idc[count] = idp;
                        distances[count] = sqrdist;
                        mindist = distances[0];      // minima distanza di ricerca( max del set)
                        sqrdist = mindist * mindist; // la stessa al quadrato per il confronto
                    }
                    ptr = ptr + 1;
                }
            }
            dxu = dxu + PX;
        }

        if (dyu < mindist && idyi + c < nyint)
        {
            escape = false;
            jc2 = c;

            jj = c;
            for (ii = ic1; ii <= ic2; ii++)

            { // leaf search

                id = nyint * (idxi + ii) + idyi + jj;
                if (LeavesFinder2[id] < 0)
                {
                    continue;
                }
                ptr = LeavesFinder1[id]; // future improvement check first and second ptrBoxes
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance < sqrdist)
                    {
                        sqrdist = sqrt(CurrentDistance); // non e la distanza al quadrato ma
                        // � meglio calcolare adesso la radice q cos� ritorniamo le distanze vere
                        count = 0;
                        for (n = 1; n < k; n++) // FInd new point position
                        {
                            if (sqrdist < (distances[n]))
                            {
                                count = count + 1;
                            }
                            else
                            {
                                break;
                            }
                        }
                        for (n = 0; n < count; n++) //<--------Evitare questo ciclo in una revisione!!!
                        {
                            idc[n] = idc[n + 1];
                            distances[n] = distances[n + 1];
                        }
                        idc[count] = idp;
                        distances[count] = sqrdist;
                        mindist = distances[0];      // minima distanza di ricerca( max del set)
                        sqrdist = mindist * mindist; // la stessa al quadrato per il confronto
                    }
                    ptr = ptr + 1;
                }
            }
            dyu = dyu + PY;
        }
        if (dyd < mindist && idyi - c > -1)
        {
            escape = false;
            jc1 = -c;

            jj = -c;
            for (ii = ic1; ii <= ic2; ii++)

            { // leaf search
                id = nyint * (idxi + ii) + idyi + jj;
                if (LeavesFinder2[id] < 0)
                {
                    continue;
                } // leaf is empty
                ptr = LeavesFinder1[id];
                while (ptr <= LeavesFinder2[id])
                {
                    idp = Leaves[ptr];
                    if (CurrentDistance < sqrdist)
                    {
                        sqrdist = sqrt(CurrentDistance); // non e la distanza al quadrato ma
                        // � meglio calcolare adesso la radice q cos� ritorniamo le distanze vere
                        count = 0;
                        for (n = 1; n < k; n++) // FInd new point position
                        {
                            if (sqrdist < (distances[n]))
                            {
                                count = count + 1;
                            }
                            else
                            {
                                break;
                            }
                        }
                        for (n = 0; n < count; n++) //<--------Evitare questo ciclo in una revisione!!!
                        {
                            idc[n] = idc[n + 1];
                            distances[n] = distances[n + 1];
                        }
                        idc[count] = idp;
                        distances[count] = sqrdist;
                        mindist = distances[0];      // minima distanza di ricerca( max del set)
                        sqrdist = mindist * mindist; // la stessa al quadrato per il confronto
                    }
                    ptr = ptr + 1;
                }
            }
            dyd = dyd + PY;
        }

        if (escape)
        {
            return;
        }
    }
    return;
}
