#include "OW3DUtilFunctions.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::ComputeSurfaceDerivatives(const FundamentalForms &forms, RealArray &phi, RealArray &phin, SideDervs &Dervs)
{
    int S0 = phi.getLength(0);
    int S1 = phi.getLength(1);
    int S2 = phi.getLength(2); // Y is upward
    int N0, N1;

    if (S0 == 1)
    {
        N0 = S1;
        N1 = S2;
        phi.reshape(N0, N1);
        phin.reshape(N0, N1);
    }
    else if (S1 == 1)
    {
        N0 = S0;
        N1 = S2;
        phi.reshape(N0, N1);
        phin.reshape(N0, N1);
    }
    else if (S2 == 1)
    {
        N0 = S0;
        N1 = S1;
    }
    else
    {
        throw runtime_error("Error, OW3DSeakeeping::ComputeSurfaceDerivatives.cpp: The coordinates of only 1 side should be given.");
    }

    // Convention: u is along axis0, v is along axis 1
    double dv = 1.0 / (N0 - 1);
    double du = 1.0 / (N1 - 1);
    Range All;
    RealArray phiu(N0, N1), phiv(N0, N1);
    phiu = 0, phiv = 0;
    RealArray tphi = transpose(phi);
    RealArray tphiv = transpose(phiv);

    // Compute 1D derivatives along u
    Compute1DDerivatives(phi, phiu, 0, N1 - 1, OW3DSeakeeping::C4);
    phiu *= du;

    // Compute 1D derivatives along v
    Compute1DDerivatives(tphi, tphiv, 0, N0 - 1, OW3DSeakeeping::C4);
    tphiv *= dv;
    phiv = transpose(tphiv);

    // ----------------------------------------------------------------------------------
    const RealArray &Xu = forms.Xu;
    const RealArray &Yu = forms.Yu;
    const RealArray &Zu = forms.Zu;
    const RealArray &Xv = forms.Xv;
    const RealArray &Yv = forms.Yv;
    const RealArray &Zv = forms.Zv;
    const RealArray &E = forms.E;
    const RealArray &F = forms.F;
    const RealArray &G = forms.G;
    const RealArray &H = forms.H;
    const RealArray &n1 = forms.n1;
    const RealArray &n2 = forms.n2;
    const RealArray &n3 = forms.n3;

    // Compute first derivatives ----------------------------------------------------------------
    Dervs.dx = 1.0 / (H * H) * (Xu * (G * phiu - F * phiv) + Xv * (E * phiv - F * phiu)) + phin * n1;
    Dervs.dy = 1.0 / (H * H) * (Yu * (G * phiu - F * phiv) + Yv * (E * phiv - F * phiu)) + phin * n2;
    Dervs.dz = 1.0 / (H * H) * (Zu * (G * phiu - F * phiv) + Zv * (E * phiv - F * phiu)) + phin * n3;

    // Compute second derivatives --------------------------------------------------------------
    RealArray phiXu(N0, N1), phiYu(N0, N1), phiZu(N0, N1), phiXv(N0, N1), phiYv(N0, N1), phiZv(N0, N1);
    phiXu = 0, phiYu = 0, phiZu = 0, phiXv = 0, phiYv = 0, phiZv = 0;
    RealArray tphiX = transpose(Dervs.dx);
    RealArray tphiY = transpose(Dervs.dy);
    RealArray tphiZ = transpose(Dervs.dz);
    RealArray tphiXv = transpose(phiXv);
    RealArray tphiYv = transpose(phiYv);
    RealArray tphiZv = transpose(phiZv);
    Compute1DDerivatives(Dervs.dx, phiXu, 0, N1 - 1, OW3DSeakeeping::C4);
    Compute1DDerivatives(Dervs.dy, phiYu, 0, N1 - 1, OW3DSeakeeping::C4);
    Compute1DDerivatives(Dervs.dz, phiZu, 0, N1 - 1, OW3DSeakeeping::C4);
    phiXu *= du, phiYu *= du, phiZu *= du;

    Compute1DDerivatives(tphiX, tphiXv, 0, N0 - 1, OW3DSeakeeping::C4);
    Compute1DDerivatives(tphiY, tphiYv, 0, N0 - 1, OW3DSeakeeping::C4);
    Compute1DDerivatives(tphiZ, tphiZv, 0, N0 - 1, OW3DSeakeeping::C4);

    tphiXv *= dv, tphiYv *= dv, tphiZv *= dv;
    phiXv = transpose(tphiXv);
    phiYv = transpose(tphiYv);
    phiZv = transpose(tphiZv);

    RealArray phisx_1 = 1.0 / (H * H) * (Xu * (G * phiXu - F * phiXv) + Xv * (E * phiXv - F * phiXu));
    RealArray phisx_2 = 1.0 / (H * H) * (Yu * (G * phiXu - F * phiXv) + Yv * (E * phiXv - F * phiXu));
    RealArray phisx_3 = 1.0 / (H * H) * (Zu * (G * phiXu - F * phiXv) + Zv * (E * phiXv - F * phiXu));
    RealArray phisy_1 = 1.0 / (H * H) * (Xu * (G * phiYu - F * phiYv) + Xv * (E * phiYv - F * phiYu));
    RealArray phisy_2 = 1.0 / (H * H) * (Yu * (G * phiYu - F * phiYv) + Yv * (E * phiYv - F * phiYu));
    RealArray phisy_3 = 1.0 / (H * H) * (Zu * (G * phiYu - F * phiYv) + Zv * (E * phiYv - F * phiYu));
    RealArray phisz_1 = 1.0 / (H * H) * (Xu * (G * phiZu - F * phiZv) + Xv * (E * phiZv - F * phiZu));
    RealArray phisz_2 = 1.0 / (H * H) * (Yu * (G * phiZu - F * phiZv) + Yv * (E * phiZv - F * phiZu));
    RealArray phisz_3 = 1.0 / (H * H) * (Zu * (G * phiZu - F * phiZv) + Zv * (E * phiZv - F * phiZu));

    Dervs.dxx.resize(N0, N1);
    Dervs.dyy.resize(N0, N1);
    Dervs.dzz.resize(N0, N1);
    Dervs.dxy.resize(N0, N1);
    Dervs.dxz.resize(N0, N1);
    Dervs.dyz.resize(N0, N1);

    RealArray GradsGradPhiN0 = n1 * phisx_1 + n2 * phisy_1 + n3 * phisz_1;
    RealArray GradsGradPhiN1 = n1 * phisx_2 + n2 * phisy_2 + n3 * phisz_2;
    RealArray GradsGradPhiN2 = n1 * phisx_3 + n2 * phisy_3 + n3 * phisz_3;
    RealArray GradsDotGradPhi = phisx_1 + phisy_2 + phisz_3;
    RealArray m1 = -(GradsGradPhiN0 - n1 * GradsDotGradPhi);
    RealArray m2 = -(GradsGradPhiN1 - n2 * GradsDotGradPhi);
    RealArray m3 = -(GradsGradPhiN2 - n3 * GradsDotGradPhi);
    Dervs.dxx = phisx_1 - n1 * m1;
    Dervs.dxy = phisx_2 - n2 * m1;
    Dervs.dxz = phisx_3 - n3 * m1;
    Dervs.dyy = phisy_2 - n2 * m2;
    Dervs.dyz = phisy_3 - n3 * m2;
    Dervs.dzz = -(Dervs.dxx + Dervs.dyy);
    //

    // Reshape the solutions -------------------------------------------------------------------
    if (S0 == 1)
    {
        Dervs.dx.reshape(1, N0, N1);
        Dervs.dy.reshape(1, N0, N1);
        Dervs.dz.reshape(1, N0, N1);
        Dervs.dxx.reshape(1, N0, N1);
        Dervs.dyy.reshape(1, N0, N1);
        Dervs.dzz.reshape(1, N0, N1);
        Dervs.dxy.reshape(1, N0, N1);
        Dervs.dxz.reshape(1, N0, N1);
        Dervs.dyz.reshape(1, N0, N1);
    }
    else if (S1 == 1)
    {
        Dervs.dx.reshape(N0, 1, N1);
        Dervs.dy.reshape(N0, 1, N1);
        Dervs.dz.reshape(N0, 1, N1);
        Dervs.dxx.reshape(N0, 1, N1);
        Dervs.dyy.reshape(N0, 1, N1);
        Dervs.dzz.reshape(N0, 1, N1);
        Dervs.dxy.reshape(N0, 1, N1);
        Dervs.dxz.reshape(N0, 1, N1);
        Dervs.dyz.reshape(N0, 1, N1);
    }
}

void OW3DSeakeeping::ComputeSurfaceDerivatives(
    const FundamentalForms &forms, const vector<vector<DiscRanges>> &surface_ranges, RealArray &phi, RealArray &phin, SideDervs &Dervs, char mode_type)
{
    bool IncludeInterpPointsForFirstDerivatives = true;
    int S0 = phi.getLength(0);
    int S1 = phi.getLength(1);
    int S2 = phi.getLength(2); // Y is upward
    int N0, N1;
    int order = 4; // Note: for the "patchwise" derivatives (this function) only 4th order is supported.

    if (S0 == 1)
    {
        N0 = S1;
        N1 = S2;
        phi.reshape(N0, N1);
        phin.reshape(N0, N1);
    }
    else if (S1 == 1)
    {
        N0 = S0;
        N1 = S2;
        phi.reshape(N0, N1);
        phin.reshape(N0, N1);
    }
    else if (S2 == 1)
    {
        N0 = S0;
        N1 = S1;
    }
    else
    {
        throw runtime_error("Error, OW3DSeakeeping::ComputeSurfaceDerivatives.cpp: The coordinates of only 1 side should be given.");
    }

    // Convention: u is along axis0, v is along axis 1
    double dv = 1.0 / (N0 - 1);
    double du = 1.0 / (N1 - 1);
    Range All;
    RealArray phiu(N0, N1), phiv(N0, N1);
    phiu = 0, phiv = 0;
    RealArray tphi = transpose(phi);
    RealArray tphiv = transpose(phiv);

    if (!IncludeInterpPointsForFirstDerivatives)
    {
        // Compute 1D derivatives along u
        for (int i = 0; i < N0; i++)
        {
            for (unsigned int p = 0; p < surface_ranges[0][i].ROD.size(); p++)
            {
                int si = surface_ranges[0][i].ROD[p].getBase();
                int se = surface_ranges[0][i].ROD[p].getBound();
                if (se - si >= order)
                    OW3DSeakeeping::Compute1DDerivatives(phi, phiu, si, se, OW3DSeakeeping::C4, Range(i, i));
                else
                    OW3DSeakeeping::Compute1DDerivatives(phi, phiu, si, se, OW3DSeakeeping::C2, Range(i, i));
            }
        }
        // Compute 1D derivatives along v
        for (int j = 0; j < N1; j++)
        {
            for (unsigned int p = 0; p < surface_ranges[1][j].ROD.size(); p++)
            {
                int si = surface_ranges[1][j].ROD[p].getBase();
                int se = surface_ranges[1][j].ROD[p].getBound();
                if (se - si >= order)
                    OW3DSeakeeping::Compute1DDerivatives(tphi, tphiv, si, se, OW3DSeakeeping::C4, Range(j, j));
                else
                    OW3DSeakeeping::Compute1DDerivatives(tphi, tphiv, si, se, OW3DSeakeeping::C2, Range(j, j));
            }
        }
    }
    else
    {
        RealArray c4u = mode_type == 's' ? forms.C4_u_nm : forms.C4_u_dr;
        RealArray c4v = mode_type == 's' ? forms.C4_v_nm : forms.C4_v_dr;
        // Compute 1D derivatives along u
        OW3DSeakeeping::Compute1DDerivatives(phi, phiu, 0, N1 - 1, c4u);
        // Compute 1D derivatives along v
        OW3DSeakeeping::Compute1DDerivatives(tphi, tphiv, 0, N0 - 1, c4v);
    }
    phiu *= du;
    tphiv *= dv;
    phiv = transpose(tphiv);

    // ----------------------------------------------------------------------------------
    const RealArray &Xu = forms.Xu;
    const RealArray &Yu = forms.Yu;
    const RealArray &Zu = forms.Zu;
    const RealArray &Xv = forms.Xv;
    const RealArray &Yv = forms.Yv;
    const RealArray &Zv = forms.Zv;
    const RealArray &E = forms.E;
    const RealArray &F = forms.F;
    const RealArray &G = forms.G;
    const RealArray &H = forms.H;
    const RealArray &n1 = forms.n1;
    const RealArray &n2 = forms.n2;
    const RealArray &n3 = forms.n3;

    // Compute first derivatives ----------------------------------------------------------------
    Dervs.dx = 1.0 / (H * H) * (Xu * (G * phiu - F * phiv) + Xv * (E * phiv - F * phiu)) + phin * n1;
    Dervs.dy = 1.0 / (H * H) * (Yu * (G * phiu - F * phiv) + Yv * (E * phiv - F * phiu)) + phin * n2;
    Dervs.dz = 1.0 / (H * H) * (Zu * (G * phiu - F * phiv) + Zv * (E * phiv - F * phiu)) + phin * n3;

    // Compute second derivatives --------------------------------------------------------------
    RealArray phiXu(N0, N1), phiYu(N0, N1), phiZu(N0, N1), phiXv(N0, N1), phiYv(N0, N1), phiZv(N0, N1);
    phiXu = 0, phiYu = 0, phiZu = 0, phiXv = 0, phiYv = 0, phiZv = 0;
    RealArray tphiX = transpose(Dervs.dx);
    RealArray tphiY = transpose(Dervs.dy);
    RealArray tphiZ = transpose(Dervs.dz);
    RealArray tphiXv = transpose(phiXv);
    RealArray tphiYv = transpose(phiYv);
    RealArray tphiZv = transpose(phiZv);
    for (int i = 0; i < N0; i++)
    {
        for (unsigned int p = 0; p < surface_ranges[0][i].ROD.size(); p++)
        {
            int si = surface_ranges[0][i].ROD[p].getBase();
            int se = surface_ranges[0][i].ROD[p].getBound();
            RealArray c4_neumann = (si == 0 or se == N1 - 1) ? forms.C4_u_nm : OW3DSeakeeping::C4;
            RealArray c4_dirichlet = (si == 0 or se == N1 - 1) ? forms.C4_u_dr : OW3DSeakeeping::C4;
            RealArray c2_neumann = (si == 0 or se == N1 - 1) ? forms.C2_u_nm : OW3DSeakeeping::C2;
            RealArray c2_dirichlet = (si == 0 or se == N1 - 1) ? forms.C2_u_dr : OW3DSeakeeping::C2;
            if (se - si >= order)
            {
                if (mode_type == 's')
                {
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dx, phiXu, si, se, c4_neumann, Range(i, i));
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dy, phiYu, si, se, c4_neumann, Range(i, i));
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dz, phiZu, si, se, c4_dirichlet, Range(i, i));
                }
                else
                {
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dx, phiXu, si, se, c4_dirichlet, Range(i, i));
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dy, phiYu, si, se, c4_dirichlet, Range(i, i));
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dz, phiZu, si, se, c4_neumann, Range(i, i));
                }
            }
            else
            {
                if (mode_type == 's')
                {
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dx, phiXu, si, se, c2_neumann, Range(i, i));
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dy, phiYu, si, se, c2_neumann, Range(i, i));
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dz, phiZu, si, se, c2_dirichlet, Range(i, i));
                }
                else
                {
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dx, phiXu, si, se, c2_dirichlet, Range(i, i));
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dy, phiYu, si, se, c2_dirichlet, Range(i, i));
                    OW3DSeakeeping::Compute1DDerivatives(Dervs.dz, phiZu, si, se, c2_neumann, Range(i, i));
                }
            }
        }
    }
    phiXu *= du, phiYu *= du, phiZu *= du;
    for (int j = 0; j < N1; j++)
    {
        for (unsigned int p = 0; p < surface_ranges[1][j].ROD.size(); p++)
        {
            int si = surface_ranges[1][j].ROD[p].getBase();
            int se = surface_ranges[1][j].ROD[p].getBound();
            RealArray c4_neumann = (si == 0 or se == N0 - 1) ? forms.C4_v_nm : OW3DSeakeeping::C4;
            RealArray c4_dirichlet = (si == 0 or se == N0 - 1) ? forms.C4_v_dr : OW3DSeakeeping::C4;
            RealArray c2_neumann = (si == 0 or se == N0 - 1) ? forms.C2_v_nm : OW3DSeakeeping::C2;
            RealArray c2_dirichlet = (si == 0 or se == N0 - 1) ? forms.C2_v_dr : OW3DSeakeeping::C2;
            if (se - si >= order)
            {
                if (mode_type == 's')
                {
                    OW3DSeakeeping::Compute1DDerivatives(tphiX, tphiXv, si, se, c4_neumann, Range(j, j));
                    OW3DSeakeeping::Compute1DDerivatives(tphiY, tphiYv, si, se, c4_neumann, Range(j, j));
                    OW3DSeakeeping::Compute1DDerivatives(tphiZ, tphiZv, si, se, c4_dirichlet, Range(j, j));
                }
                else
                {
                    OW3DSeakeeping::Compute1DDerivatives(tphiX, tphiXv, si, se, c4_dirichlet, Range(j, j));
                    OW3DSeakeeping::Compute1DDerivatives(tphiY, tphiYv, si, se, c4_dirichlet, Range(j, j));
                    OW3DSeakeeping::Compute1DDerivatives(tphiZ, tphiZv, si, se, c4_neumann, Range(j, j));
                }
            }
            else
            {
                if (mode_type == 's')
                {

                    OW3DSeakeeping::Compute1DDerivatives(tphiX, tphiXv, si, se, c2_neumann, Range(j, j));
                    OW3DSeakeeping::Compute1DDerivatives(tphiY, tphiYv, si, se, c2_neumann, Range(j, j));
                    OW3DSeakeeping::Compute1DDerivatives(tphiZ, tphiZv, si, se, c2_dirichlet, Range(j, j));
                }
                else
                {
                    OW3DSeakeeping::Compute1DDerivatives(tphiX, tphiXv, si, se, c2_dirichlet, Range(j, j));
                    OW3DSeakeeping::Compute1DDerivatives(tphiY, tphiYv, si, se, c2_dirichlet, Range(j, j));
                    OW3DSeakeeping::Compute1DDerivatives(tphiZ, tphiZv, si, se, c2_neumann, Range(j, j));
                }
            }
        }
    }
    tphiXv *= dv, tphiYv *= dv, tphiZv *= dv;
    phiXv = transpose(tphiXv);
    phiYv = transpose(tphiYv);
    phiZv = transpose(tphiZv);

    RealArray phisx_1 = 1.0 / (H * H) * (Xu * (G * phiXu - F * phiXv) + Xv * (E * phiXv - F * phiXu));
    RealArray phisx_2 = 1.0 / (H * H) * (Yu * (G * phiXu - F * phiXv) + Yv * (E * phiXv - F * phiXu));
    RealArray phisx_3 = 1.0 / (H * H) * (Zu * (G * phiXu - F * phiXv) + Zv * (E * phiXv - F * phiXu));
    RealArray phisy_1 = 1.0 / (H * H) * (Xu * (G * phiYu - F * phiYv) + Xv * (E * phiYv - F * phiYu));
    RealArray phisy_2 = 1.0 / (H * H) * (Yu * (G * phiYu - F * phiYv) + Yv * (E * phiYv - F * phiYu));
    RealArray phisy_3 = 1.0 / (H * H) * (Zu * (G * phiYu - F * phiYv) + Zv * (E * phiYv - F * phiYu));
    RealArray phisz_1 = 1.0 / (H * H) * (Xu * (G * phiZu - F * phiZv) + Xv * (E * phiZv - F * phiZu));
    RealArray phisz_2 = 1.0 / (H * H) * (Yu * (G * phiZu - F * phiZv) + Yv * (E * phiZv - F * phiZu));
    RealArray phisz_3 = 1.0 / (H * H) * (Zu * (G * phiZu - F * phiZv) + Zv * (E * phiZv - F * phiZu));

    Dervs.dxx.resize(N0, N1);
    Dervs.dyy.resize(N0, N1);
    Dervs.dzz.resize(N0, N1);
    Dervs.dxy.resize(N0, N1);
    Dervs.dxz.resize(N0, N1);
    Dervs.dyz.resize(N0, N1);

    RealArray GradsGradPhiN0 = n1 * phisx_1 + n2 * phisy_1 + n3 * phisz_1;
    RealArray GradsGradPhiN1 = n1 * phisx_2 + n2 * phisy_2 + n3 * phisz_2;
    RealArray GradsGradPhiN2 = n1 * phisx_3 + n2 * phisy_3 + n3 * phisz_3;
    RealArray GradsDotGradPhi = phisx_1 + phisy_2 + phisz_3;
    RealArray m1 = -(GradsGradPhiN0 - n1 * GradsDotGradPhi);
    RealArray m2 = -(GradsGradPhiN1 - n2 * GradsDotGradPhi);
    RealArray m3 = -(GradsGradPhiN2 - n3 * GradsDotGradPhi);
    Dervs.dxx = phisx_1 - n1 * m1;
    Dervs.dxy = phisx_2 - n2 * m1;
    Dervs.dxz = phisx_3 - n3 * m1;
    Dervs.dyy = phisy_2 - n2 * m2;
    Dervs.dyz = phisy_3 - n3 * m2;
    Dervs.dzz = -(Dervs.dxx + Dervs.dyy);

    // Reshape the solutions -------------------------------------------------------------------
    if (S0 == 1)
    {
        Dervs.dx.reshape(1, N0, N1);
        Dervs.dy.reshape(1, N0, N1);
        Dervs.dz.reshape(1, N0, N1);
        Dervs.dxx.reshape(1, N0, N1);
        Dervs.dyy.reshape(1, N0, N1);
        Dervs.dzz.reshape(1, N0, N1);
        Dervs.dxy.reshape(1, N0, N1);
        Dervs.dxz.reshape(1, N0, N1);
        Dervs.dyz.reshape(1, N0, N1);
    }
    else if (S1 == 1)
    {
        Dervs.dx.reshape(N0, 1, N1);
        Dervs.dy.reshape(N0, 1, N1);
        Dervs.dz.reshape(N0, 1, N1);
        Dervs.dxx.reshape(N0, 1, N1);
        Dervs.dyy.reshape(N0, 1, N1);
        Dervs.dzz.reshape(N0, 1, N1);
        Dervs.dxy.reshape(N0, 1, N1);
        Dervs.dxz.reshape(N0, 1, N1);
        Dervs.dyz.reshape(N0, 1, N1);
    }
}