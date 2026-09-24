#include "CompositeGridOperators.h"
#include "OW3DConstants.h"
#include "Grid.h"

void ClearVectors(OW3DSeakeeping::potentialDerivative &FdDervs)
{
    FdDervs.dx.clear();
    FdDervs.dy.clear();
    FdDervs.dz.clear();
    FdDervs.dxx.clear();
    FdDervs.dyy.clear();
    FdDervs.dzz.clear();
    FdDervs.dxy.clear();
    FdDervs.dxz.clear();
    FdDervs.dyz.clear();
}

void OW3DSeakeeping::Grid::PrintOW3DDerivatives()
{
    // Preliminary stuff
    string resultsDirectory = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;
    OW3DSeakeeping::OverrideResults(resultsDirectory);

    OW3DSeakeeping::All_boundaries_data boundariesData = gridData_.boundariesData;
    CompositeGridOperators operators = OW3DSeakeeping::DefineOperators(cg_, gridData_.order_space);

    // Set the incident wave solution on the grid
    RealCompositeGridFunction Phi(cg_);
    Phi = 0;
    Phi.setOperators(operators);
    double beta = 4 * Pi / 5;
    double K = gridData_.kMax / 10;
    for (int i = 0; i < cg_->numberOfComponentGrids; i++)
    {
        Index I1, I2, I3;
        MappedGrid &mg = cg_[i];
        getIndex(mg.dimension(), I1, I2, I3);
        RealArray x = mg.vertex()(I1, I2, I3, axis1);
        RealArray y = mg.vertex()(I1, I2, I3, axis2);
        RealArray z = mg.vertex()(I1, I2, I3, axis3);
        RealArray alpha = x * cos(beta) + z * sin(beta);
        Phi[i] = exp(K * y) * cos(K * alpha);
    }

    // Derivatives usging Overture
    RealCompositeGridFunction Phix = Phi.x();
    RealCompositeGridFunction Phiy = Phi.y();
    RealCompositeGridFunction Phiz = Phi.z();
    RealCompositeGridFunction Phixx = Phi.xx();
    RealCompositeGridFunction Phiyy = Phi.yy();
    RealCompositeGridFunction Phizz = Phi.zz();
    RealCompositeGridFunction Phixy = Phi.xy();
    RealCompositeGridFunction Phixz = Phi.xz();
    RealCompositeGridFunction Phiyz = Phi.yz();

    OW3DSeakeeping::potentialDerivative OvDervs;
    OW3DSeakeeping::potentialDerivative ExDervs;
    OW3DSeakeeping::potentialDerivative FdDervs;

    // ----------------------------------------------------------------------------------------------------------
    // Test the schemes at the body
    // ----------------------------------------------------------------------------------------------------------

    // ** Derivatives by the new scheme (assuming all points including hole points are set)

    for (unsigned int surface = 0; surface < boundariesData.exciting.size(); surface++)
    {
        const OW3DSeakeeping::Single_boundary_data &be = boundariesData.exciting[surface];
        const MappedGrid &mg = cg_[be.grid];
        vector<Index> Is = be.surface_indices;
        const RealArray &v = mg.vertex();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        z = 0.0;
        if (mg.numberOfDimensions() == 3)
            z = v(Is[0], Is[1], Is[2], axis3);

        // Transfer Overture results for printing
        OvDervs.dx.push_back(Phix[be.grid](Is[0], Is[1], Is[2]));
        OvDervs.dy.push_back(Phiy[be.grid](Is[0], Is[1], Is[2]));
        OvDervs.dz.push_back(Phiz[be.grid](Is[0], Is[1], Is[2]));
        OvDervs.dxx.push_back(Phixx[be.grid](Is[0], Is[1], Is[2]));
        OvDervs.dyy.push_back(Phiyy[be.grid](Is[0], Is[1], Is[2]));
        OvDervs.dzz.push_back(Phizz[be.grid](Is[0], Is[1], Is[2]));
        OvDervs.dxy.push_back(Phixy[be.grid](Is[0], Is[1], Is[2]));
        OvDervs.dxz.push_back(Phixz[be.grid](Is[0], Is[1], Is[2]));
        OvDervs.dyz.push_back(Phiyz[be.grid](Is[0], Is[1], Is[2]));

        // Excat solutions
        RealArray phi(Is[0], Is[1], Is[2]);
        RealArray phin(Is[0], Is[1], Is[2]);
        RealArray phix(Is[0], Is[1], Is[2]);
        RealArray phiy(Is[0], Is[1], Is[2]);
        RealArray phiz(Is[0], Is[1], Is[2]);
        RealArray alpha(Is[0], Is[1], Is[2]);
        alpha = x * cos(beta) + z * sin(beta);
        phi = exp(K * y) * cos(K * alpha);
        phix = -K * cos(beta) * exp(K * y) * sin(K * alpha);
        phiz = -K * sin(beta) * exp(K * y) * sin(K * alpha);
        phiy = K * exp(K * y) * cos(K * alpha);
        phin =
            phix * gridData_.body_fundamentals[surface].n1 +
            phiy * gridData_.body_fundamentals[surface].n2 +
            phiz * gridData_.body_fundamentals[surface].n3;
        ExDervs.dx.push_back(phix);
        ExDervs.dy.push_back(phiy);
        ExDervs.dz.push_back(phiz);
        ExDervs.dxx.push_back(-K * K * cos(beta) * cos(beta) * exp(K * y) * cos(K * alpha));
        ExDervs.dyy.push_back(K * K * exp(K * y) * cos(K * alpha));
        ExDervs.dzz.push_back(-K * K * sin(beta) * sin(beta) * exp(K * y) * cos(K * alpha));
        ExDervs.dxz.push_back(-K * K * cos(beta) * sin(beta) * exp(K * y) * cos(K * alpha));
        ExDervs.dxy.push_back(-K * K * cos(beta) * exp(K * y) * sin(K * alpha));
        ExDervs.dyz.push_back(-K * K * sin(beta) * exp(K * y) * sin(K * alpha));

        OW3DSeakeeping::SideDervs Dervs;
        OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_.body_fundamentals[surface], phi, phin, Dervs);
        FdDervs.dx.push_back(Dervs.dx);
        FdDervs.dy.push_back(Dervs.dy);
        FdDervs.dz.push_back(Dervs.dz);
        FdDervs.dxx.push_back(Dervs.dxx);
        FdDervs.dyy.push_back(Dervs.dyy);
        FdDervs.dzz.push_back(Dervs.dzz);
        FdDervs.dxy.push_back(Dervs.dxy);
        FdDervs.dxz.push_back(Dervs.dxz);
        FdDervs.dyz.push_back(Dervs.dyz);
    }

    // Print the results
    string ovfname = resultsDirectory + "/ovDervs.txt";
    string exfname = resultsDirectory + "/exDervs.txt";
    string s1fname = resultsDirectory + "/allDervs.txt";
    OW3DSeakeeping::PrintSurfaceDerivatives(cg_, boundariesData.exciting, OvDervs, ovfname);
    OW3DSeakeeping::PrintSurfaceDerivatives(cg_, boundariesData.exciting, ExDervs, exfname);
    OW3DSeakeeping::PrintSurfaceDerivatives(cg_, boundariesData.exciting, FdDervs, s1fname);

    ClearVectors(FdDervs);

    // ** Derivatives by the new scheme (Only physical points are considered)
    for (unsigned int surface = 0; surface < boundariesData.exciting.size(); surface++)
    {
        const OW3DSeakeeping::Single_boundary_data &be = boundariesData.exciting[surface];
        const MappedGrid &mg = cg_[be.grid];
        vector<Index> Is = be.surface_indices;
        const RealArray &v = mg.vertex();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        z = 0.0;
        if (mg.numberOfDimensions() == 3)
            z = v(Is[0], Is[1], Is[2], axis3);

        RealArray phi(Is[0], Is[1], Is[2]);
        RealArray phin(Is[0], Is[1], Is[2]);
        RealArray phix(Is[0], Is[1], Is[2]);
        RealArray phiy(Is[0], Is[1], Is[2]);
        RealArray phiz(Is[0], Is[1], Is[2]);
        RealArray alpha(Is[0], Is[1], Is[2]);

        where(mg.mask()(Is[0], Is[1], Is[2]) != 0)
        {
            alpha = x * cos(beta) + z * sin(beta);
            phi = exp(K * y) * cos(K * alpha);
            phix = -K * cos(beta) * exp(K * y) * sin(K * alpha);
            phiz = -K * sin(beta) * exp(K * y) * sin(K * alpha);
            phiy = K * exp(K * y) * cos(K * alpha);
            phin =
                phix * gridData_.body_fundamentals[surface].n1 +
                phiy * gridData_.body_fundamentals[surface].n2 +
                phiz * gridData_.body_fundamentals[surface].n3;
        }

        OW3DSeakeeping::SideDervs Dervs;
        OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_.body_fundamentals[surface], gridData_.body_surface_disc[surface], phi, phin, Dervs);

        FdDervs.dx.push_back(Dervs.dx);
        FdDervs.dy.push_back(Dervs.dy);
        FdDervs.dz.push_back(Dervs.dz);
        FdDervs.dxx.push_back(Dervs.dxx);
        FdDervs.dyy.push_back(Dervs.dyy);
        FdDervs.dzz.push_back(Dervs.dzz);
        FdDervs.dxy.push_back(Dervs.dxy);
        FdDervs.dxz.push_back(Dervs.dxz);
        FdDervs.dyz.push_back(Dervs.dyz);
    }
    // Print the results
    string s3fname = resultsDirectory + "/patchDervs.txt";
    OW3DSeakeeping::PrintSurfaceDerivatives(cg_, boundariesData.exciting, FdDervs, s3fname);

    ClearVectors(FdDervs);
    ClearVectors(OvDervs);
    ClearVectors(ExDervs);

    // ----------------------------------------------------------------------------------------------------------
    // Test the schemes at the free surface
    // ----------------------------------------------------------------------------------------------------------

    // ** Derivatives by the new scheme (assuming all points including hole points are set)

    for (unsigned int surface = 0; surface < boundariesData.free.size(); surface++)
    {
        const OW3DSeakeeping::Single_boundary_data &bf = boundariesData.free[surface];
        const MappedGrid &mg = cg_[bf.grid];
        vector<Index> Is = bf.surface_indices;
        const RealArray &v = mg.vertex();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        z = 0.0;
        if (mg.numberOfDimensions() == 3)
            z = v(Is[0], Is[1], Is[2], axis3);

        // Transfer Overture results for printing
        OvDervs.dx.push_back(Phix[bf.grid](Is[0], Is[1], Is[2]));
        OvDervs.dy.push_back(Phiy[bf.grid](Is[0], Is[1], Is[2]));
        OvDervs.dz.push_back(Phiz[bf.grid](Is[0], Is[1], Is[2]));
        OvDervs.dxx.push_back(Phixx[bf.grid](Is[0], Is[1], Is[2]));
        OvDervs.dyy.push_back(Phiyy[bf.grid](Is[0], Is[1], Is[2]));
        OvDervs.dzz.push_back(Phizz[bf.grid](Is[0], Is[1], Is[2]));
        OvDervs.dxy.push_back(Phixy[bf.grid](Is[0], Is[1], Is[2]));
        OvDervs.dxz.push_back(Phixz[bf.grid](Is[0], Is[1], Is[2]));
        OvDervs.dyz.push_back(Phiyz[bf.grid](Is[0], Is[1], Is[2]));

        // Excat solutions
        RealArray phi(Is[0], Is[1], Is[2]);
        RealArray phin(Is[0], Is[1], Is[2]);
        RealArray phix(Is[0], Is[1], Is[2]);
        RealArray phiy(Is[0], Is[1], Is[2]);
        RealArray phiz(Is[0], Is[1], Is[2]);
        RealArray alpha(Is[0], Is[1], Is[2]);
        RealArray n0 = gridData_.free_fundamentals[surface].n1;
        RealArray n1 = gridData_.free_fundamentals[surface].n2;
        RealArray n2 = gridData_.free_fundamentals[surface].n3;
        int S0 = phi.getLength(0);
        int S1 = phi.getLength(1);
        int S2 = phi.getLength(2);
        int N0, N1;
        if (S0 == 1)
        {
            N0 = S1;
            N1 = S2;
            n0.reshape(1, N0, N1);
            n1.reshape(1, N0, N1);
            n2.reshape(1, N0, N1);
        }
        else if (S1 == 1)
        {
            N0 = S0;
            N1 = S2;
            n0.reshape(N0, 1, N1);
            n1.reshape(N0, 1, N1);
            n2.reshape(N0, 1, N1);
        }
        alpha = x * cos(beta) + z * sin(beta);
        phi = exp(K * y) * cos(K * alpha);
        phix = -K * cos(beta) * exp(K * y) * sin(K * alpha);
        phiz = -K * sin(beta) * exp(K * y) * sin(K * alpha);
        phiy = K * exp(K * y) * cos(K * alpha);
        phin = phix * n0 + phiy * n1 + phiz * n2;
        ExDervs.dx.push_back(phix);
        ExDervs.dy.push_back(phiy);
        ExDervs.dz.push_back(phiz);
        ExDervs.dxx.push_back(-K * K * cos(beta) * cos(beta) * exp(K * y) * cos(K * alpha));
        ExDervs.dyy.push_back(K * K * exp(K * y) * cos(K * alpha));
        ExDervs.dzz.push_back(-K * K * sin(beta) * sin(beta) * exp(K * y) * cos(K * alpha));
        ExDervs.dxz.push_back(-K * K * cos(beta) * sin(beta) * exp(K * y) * cos(K * alpha));
        ExDervs.dxy.push_back(-K * K * cos(beta) * exp(K * y) * sin(K * alpha));
        ExDervs.dyz.push_back(-K * K * sin(beta) * exp(K * y) * sin(K * alpha));

        OW3DSeakeeping::SideDervs Dervs;
        OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_.free_fundamentals[surface], phi, phin, Dervs);
        RealArray tempx(Is[0], Is[1], Is[2]);
        RealArray tempy(Is[0], Is[1], Is[2]);
        RealArray tempz(Is[0], Is[1], Is[2]);
        RealArray tempxx(Is[0], Is[1], Is[2]);
        RealArray tempyy(Is[0], Is[1], Is[2]);
        RealArray tempzz(Is[0], Is[1], Is[2]);
        RealArray tempxy(Is[0], Is[1], Is[2]);
        RealArray tempxz(Is[0], Is[1], Is[2]);
        RealArray tempyz(Is[0], Is[1], Is[2]);

        tempx = Dervs.dx;
        tempy = Dervs.dy;
        tempz = Dervs.dz;
        tempxx = Dervs.dxx;
        tempyy = Dervs.dyy;
        tempzz = Dervs.dzz;
        tempxy = Dervs.dxy;
        tempxz = Dervs.dxz;
        tempyz = Dervs.dyz;

        FdDervs.dx.push_back(tempx);
        FdDervs.dy.push_back(tempy);
        FdDervs.dz.push_back(tempz);
        FdDervs.dxx.push_back(tempxx);
        FdDervs.dyy.push_back(tempyy);
        FdDervs.dzz.push_back(tempzz);
        FdDervs.dxy.push_back(tempxy);
        FdDervs.dxz.push_back(tempxz);
        FdDervs.dyz.push_back(tempyz);
    }

    // Print the results
    bool sub = gridData_.wlData.size() == 0 ? true : false;
    ovfname = resultsDirectory + "/ovDervs_f.txt";
    exfname = resultsDirectory + "/exDervs_f.txt";
    s1fname = resultsDirectory + "/allDervs_f.txt";
    OW3DSeakeeping::PrintSurfaceDerivatives(cg_, boundariesData.free, OvDervs, ovfname, sub);
    OW3DSeakeeping::PrintSurfaceDerivatives(cg_, boundariesData.free, ExDervs, exfname, sub);
    OW3DSeakeeping::PrintSurfaceDerivatives(cg_, boundariesData.free, FdDervs, s1fname, sub);

    ClearVectors(FdDervs);

    // ** Derivatives by the new scheme (Only physical points are considered)

    for (unsigned int surface = 0; surface < boundariesData.free.size(); surface++)
    {
        const OW3DSeakeeping::Single_boundary_data &bf = boundariesData.free[surface];
        const MappedGrid &mg = cg_[bf.grid];
        vector<Index> Is = bf.surface_indices;
        const RealArray &v = mg.vertex();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        z = 0.0;
        if (mg.numberOfDimensions() == 3)
            z = v(Is[0], Is[1], Is[2], axis3);

        RealArray phi(Is[0], Is[1], Is[2]);
        RealArray phin(Is[0], Is[1], Is[2]);
        RealArray phix(Is[0], Is[1], Is[2]);
        RealArray phiy(Is[0], Is[1], Is[2]);
        RealArray phiz(Is[0], Is[1], Is[2]);
        RealArray alpha(Is[0], Is[1], Is[2]);
        RealArray n0 = gridData_.free_fundamentals[surface].n1;
        RealArray n1 = gridData_.free_fundamentals[surface].n2;
        RealArray n2 = gridData_.free_fundamentals[surface].n3;
        int S0 = phi.getLength(0);
        int S1 = phi.getLength(1);
        int S2 = phi.getLength(2);
        int N0, N1;
        if (S0 == 1)
        {
            N0 = S1;
            N1 = S2;
            n0.reshape(1, N0, N1);
            n1.reshape(1, N0, N1);
            n2.reshape(1, N0, N1);
        }
        else if (S1 == 1)
        {
            N0 = S0;
            N1 = S2;
            n0.reshape(N0, 1, N1);
            n1.reshape(N0, 1, N1);
            n2.reshape(N0, 1, N1);
        }

        where(mg.mask()(Is[0], Is[1], Is[2]) != 0)
        {
            alpha = x * cos(beta) + z * sin(beta);
            phi = exp(K * y) * cos(K * alpha);
            phix = -K * cos(beta) * exp(K * y) * sin(K * alpha);
            phiz = -K * sin(beta) * exp(K * y) * sin(K * alpha);
            phiy = K * exp(K * y) * cos(K * alpha);
            phin = phix * n0 + phiy * n1 + phiz * n2;
        }

        OW3DSeakeeping::SideDervs Dervs;
        OW3DSeakeeping::ComputeSurfaceDerivatives(gridData_.free_fundamentals[surface], gridData_.free_surface_disc[surface], phi, phin, Dervs);

        RealArray tempx(Is[0], Is[1], Is[2]);
        RealArray tempy(Is[0], Is[1], Is[2]);
        RealArray tempz(Is[0], Is[1], Is[2]);
        RealArray tempxx(Is[0], Is[1], Is[2]);
        RealArray tempyy(Is[0], Is[1], Is[2]);
        RealArray tempzz(Is[0], Is[1], Is[2]);
        RealArray tempxy(Is[0], Is[1], Is[2]);
        RealArray tempxz(Is[0], Is[1], Is[2]);
        RealArray tempyz(Is[0], Is[1], Is[2]);

        tempx = Dervs.dx;
        tempy = Dervs.dy;
        tempz = Dervs.dz;
        tempxx = Dervs.dxx;
        tempyy = Dervs.dyy;
        tempzz = Dervs.dzz;
        tempxy = Dervs.dxy;
        tempxz = Dervs.dxz;
        tempyz = Dervs.dyz;

        FdDervs.dx.push_back(tempx);
        FdDervs.dy.push_back(tempy);
        FdDervs.dz.push_back(tempz);
        FdDervs.dxx.push_back(tempxx);
        FdDervs.dyy.push_back(tempyy);
        FdDervs.dzz.push_back(tempzz);
        FdDervs.dxy.push_back(tempxy);
        FdDervs.dxz.push_back(tempxz);
        FdDervs.dyz.push_back(tempyz);
    }
    // Print the results
    s3fname = resultsDirectory + "/patchDervs_f.txt";
    OW3DSeakeeping::PrintSurfaceDerivatives(cg_, boundariesData.free, FdDervs, s3fname, sub);
}
