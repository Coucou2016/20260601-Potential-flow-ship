#include "FreeSurface.h"
#include "OW3DConstants.h"
#include "OW3DUtilFunctions.h"
#include <iomanip>

void PrintSurfaceDataOfGrid(const realCompositeGridFunction &u, const vector<OW3DSeakeeping::Single_boundary_data> &bdat, string filename)
{
    const CompositeGrid *cg = u.getCompositeGrid();
    ofstream fout(filename, ios::out);
    int wdt = 18;
    fout.setf(ios_base::scientific);
    fout.precision(10);
    fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "u" << endl;
    for (unsigned int surface = 0; surface < bdat.size(); surface++)
    {
        const MappedGrid &mg = (*cg)[bdat[surface].grid];
        vector<Index> Is = bdat[surface].surface_indices;
        const RealArray &v = mg.vertex();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        z = (mg.numberOfDimensions() == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);
        for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
                {
                    if (mg.mask()(i, j, k) > 0)
                        fout << setw(wdt) << x(i, j, k) << setw(wdt) << y(i, j, k) << setw(wdt) << z(i, j, k) << setw(wdt) << u[bdat[surface].grid](i, j, k) << endl;
                }
    }
}

void PrintNeumannConditions(
    const realCompositeGridFunction &dx,
    const realCompositeGridFunction &dz,
    const vector<OW3DSeakeeping::Single_boundary_data> &bdat, string filename, double tol)
{

    const CompositeGrid *cg = dx.getCompositeGrid();
    ofstream fout(filename, ios::out);
    int wdt = 18;
    fout.setf(ios_base::scientific);
    fout.precision(10);
    fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "u" << endl;
    for (unsigned int surface = 0; surface < bdat.size(); surface++)
    {
        const MappedGrid &mg = (*cg)[bdat[surface].grid];
        vector<Index> Is = bdat[surface].surface_indices;
        const RealArray &v = mg.vertex();
        const RealArray &vbn = mg.vertexBoundaryNormal(bdat[surface].side, bdat[surface].axis);
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        RealArray nx(Is[0], Is[1], Is[2]), ny(Is[0], Is[1], Is[2]), nz(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        nx = vbn(Is[0], Is[1], Is[2], axis1);
        ny = vbn(Is[0], Is[1], Is[2], axis2);
        z = (mg.numberOfDimensions() == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);
        nz = (mg.numberOfDimensions() == 2) ? 0 * x : vbn(Is[0], Is[1], Is[2], axis3);
        for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
                {
                    if (mg.mask()(i, j, k) > 0 && fabs(mg.vertex()(i, j, k, axis2)) < tol)
                    {
                        double ddn = dx[bdat[surface].grid](i, j, k) * nx(i, j, k) + dz[bdat[surface].grid](i, j, k) * nz(i, j, k);
                        fout << setw(wdt) << x(i, j, k) << setw(wdt) << y(i, j, k) << setw(wdt) << z(i, j, k) << setw(wdt) << ddn << endl;
                    }
                }
    }
}

void OW3DSeakeeping::FreeSurface::VerifyDerivatives_()
{
    string resultsDirectory = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;
    string updervs_dx = resultsDirectory + "/updervs_dx.txt";
    string updervs_dz = resultsDirectory + "/updervs_dz.txt";
    string ovdervs_dx = resultsDirectory + "/ovdervs_dx.txt";
    string ovdervs_dz = resultsDirectory + "/ovdervs_dz.txt";
    freeSurface_.solution_stage.potential = 0.;
    double beta = 4 * Pi / 5;
    double K = gridData_->kMax / 10;

    // Check when the ghost points are already filled out

    for (unsigned int surface = 0; surface < boundariesData_->free.size(); ++surface)
    {
        const Single_boundary_data &bf = boundariesData_->free[surface];
        const MappedGrid &mg = (*cg_)[bf.grid];
        vector<Index> Is = bf.surface_indices_with_ghosts;

        const RealArray &v = mg.vertex();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        z = (mg.numberOfDimensions() == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);
        RealArray alpha = x * cos(beta) + z * sin(beta);
        freeSurface_.solution_stage.potential[bf.grid](Is[0], Is[1], Is[2]) = exp(K * y) * cos(K * alpha);
    }

    upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.potential, d_eta_dx_, d_eta_dz_);
    PrintSurfaceDataOfGrid(d_eta_dx_, boundariesData_->free, updervs_dx);
    PrintSurfaceDataOfGrid(d_eta_dz_, boundariesData_->free, updervs_dz);
    d_eta_dx_ = 0.;
    d_eta_dz_ = 0.;
    d_eta_dx_ = freeSurface_.solution_stage.potential.x();
    d_eta_dz_ = freeSurface_.solution_stage.potential.z();
    PrintSurfaceDataOfGrid(d_eta_dx_, boundariesData_->free, ovdervs_dx);
    PrintSurfaceDataOfGrid(d_eta_dz_, boundariesData_->free, ovdervs_dz);
}

void OW3DSeakeeping::FreeSurface::VerifyNeumannConditions_()
{
    string resultsDirectory = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;
    string homw = resultsDirectory + "/neumann_hom_wall.txt";
    string nhomw = resultsDirectory + "/neumann_nhom_wall.txt";
    string varbxw = resultsDirectory + "/neumann_varbx_wall.txt";
    string homb = resultsDirectory + "/neumann_hom_body.txt";
    string nhomb = resultsDirectory + "/neumann_nhom_body.txt";
    string varbxb = resultsDirectory + "/neumann_varbx_body.txt";
    freeSurface_.solution_stage.potential = 0.;

    double beta = 4 * Pi / 5;
    double K = gridData_->kMax / 10;
    double tol = 1e-4 * gridData_->maximum_depth;

    // Fill out the surface data
    for (unsigned int surface = 0; surface < boundariesData_->free.size(); ++surface)
    {
        const Single_boundary_data &bf = boundariesData_->free[surface];
        const MappedGrid &mg = (*cg_)[bf.grid];
        vector<Index> Is = bf.surface_indices_with_ghosts;

        const RealArray &v = mg.vertex();
        RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
        x = v(Is[0], Is[1], Is[2], axis1);
        y = v(Is[0], Is[1], Is[2], axis2);
        z = (mg.numberOfDimensions() == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);
        RealArray alpha = x * cos(beta) + z * sin(beta);
        freeSurface_.solution_stage.potential[bf.grid](Is[0], Is[1], Is[2]) = exp(K * y) * cos(K * alpha);
    }

    realCompositeGridFunction system_right = freeSurface_.solution_stage.potential;

    // --------------------------------------------------------------------------
    // Check BC around the body
    // --------------------------------------------------------------------------

    // homogeneous BC
    for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData_->exciting[surface];
        const vector<Index> &Ig = be.ghost_indices;
        system_right[be.grid](Ig[0], Ig[1], Ig[2]) = 0.;
    }
    upwind_object_.ApplyNeumannCondition(freeSurface_.solution_stage.potential, system_right);
    upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.potential, d_eta_dx_, d_eta_dz_);
    PrintNeumannConditions(d_eta_dx_, d_eta_dz_, boundariesData_->exciting, homb, tol);
    // Check a non-homogeneous constant BC
    for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData_->exciting[surface];
        const vector<Index> &Ig = be.ghost_indices;
        system_right[be.grid](Ig[0], Ig[1], Ig[2]) = 8.5;
    }
    upwind_object_.ApplyNeumannCondition(freeSurface_.solution_stage.potential, system_right);
    upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.potential, d_eta_dx_, d_eta_dz_);
    PrintNeumannConditions(d_eta_dx_, d_eta_dz_, boundariesData_->exciting, nhomb, tol);
    // Check a non-homogeneous variable BC
    for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData_->exciting[surface];
        const vector<Index> &Is = be.surface_indices;
        const vector<Index> &Ig = be.ghost_indices;
        const MappedGrid &mg = (*cg_)[be.grid];
        const RealArray &v = mg.vertex();
        system_right[be.grid](Ig[0], Ig[1], Ig[2]) = v(Is[0], Is[1], Is[2], axis1);
    }
    upwind_object_.ApplyNeumannCondition(freeSurface_.solution_stage.potential, system_right);
    upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.potential, d_eta_dx_, d_eta_dz_);
    PrintNeumannConditions(d_eta_dx_, d_eta_dz_, boundariesData_->exciting, varbxb, tol);

    // --------------------------------------------------------------------------
    // Check BC around the wall
    // --------------------------------------------------------------------------

    // homogeneous BC
    for (unsigned int surface = 0; surface < boundariesData_->absorbing.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData_->absorbing[surface];
        const vector<Index> &Ig = be.ghost_indices;
        system_right[be.grid](Ig[0], Ig[1], Ig[2]) = 0.;
    }
    upwind_object_.ApplyNeumannCondition(freeSurface_.solution_stage.potential, system_right);
    upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.potential, d_eta_dx_, d_eta_dz_);
    PrintNeumannConditions(d_eta_dx_, d_eta_dz_, boundariesData_->absorbing, homw, tol);
    // Check a non-homogeneous constant BC
    for (unsigned int surface = 0; surface < boundariesData_->absorbing.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData_->absorbing[surface];
        const vector<Index> &Ig = be.ghost_indices;
        system_right[be.grid](Ig[0], Ig[1], Ig[2]) = 8.5;
    }
    upwind_object_.ApplyNeumannCondition(freeSurface_.solution_stage.potential, system_right);
    upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.potential, d_eta_dx_, d_eta_dz_);
    PrintNeumannConditions(d_eta_dx_, d_eta_dz_, boundariesData_->absorbing, nhomw, tol);
    // Check a non-homogeneous variable BC
    for (unsigned int surface = 0; surface < boundariesData_->absorbing.size(); ++surface)
    {
        const Single_boundary_data &be = boundariesData_->absorbing[surface];
        const vector<Index> &Is = be.surface_indices;
        const vector<Index> &Ig = be.ghost_indices;
        const MappedGrid &mg = (*cg_)[be.grid];
        const RealArray &v = mg.vertex();
        system_right[be.grid](Ig[0], Ig[1], Ig[2]) = v(Is[0], Is[1], Is[2], axis1);
    }
    upwind_object_.ApplyNeumannCondition(freeSurface_.solution_stage.potential, system_right);
    upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.potential, d_eta_dx_, d_eta_dz_);
    PrintNeumannConditions(d_eta_dx_, d_eta_dz_, boundariesData_->absorbing, varbxw, tol);
}

void OW3DSeakeeping::FreeSurface::PrintUpwindVerifications()
{
    VerifyDerivatives_();
    VerifyNeumannConditions_();
}