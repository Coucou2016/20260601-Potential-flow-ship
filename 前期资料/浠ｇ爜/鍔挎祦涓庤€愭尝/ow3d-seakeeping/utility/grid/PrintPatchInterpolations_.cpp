#include "Grid.h"
#include "Overture.h"
#include "OW3DConstants.h"
#include <iomanip>

void OW3DSeakeeping::Grid::PrintPatchInterpolations_()
{
    string resultsDirectory = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;
    const TriangulationData &tridat = gridData_.triangulation;
    realCompositeGridFunction phi(cg_);
    phi = 0;
    double beta = 4 * Pi / 5;
    double K = gridData_.kMax / 10;

    Interpolant &interpolant = *new Interpolant(cg_);

    for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
    {
        const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];

        const MappedGrid &mg = cg_[be.grid];
        vector<Index> Is = be.surface_indices;
        getIndex(mg.dimension(), Is[0], Is[1], Is[2]);
        RealArray x = mg.vertex()(Is[0], Is[1], Is[2], axis1);
        RealArray y = mg.vertex()(Is[0], Is[1], Is[2], axis2);
        RealArray z = mg.vertex()(Is[0], Is[1], Is[2], axis3);
        RealArray alpha = x * cos(beta) + z * sin(beta);
        where(mg.mask()(Is[0], Is[1], Is[2]) > 0) // Set only disc. points
            phi[be.grid](Is[0], Is[1], Is[2]) = exp(K * y) * cos(K * alpha);
    }

    interpolant.interpolate(phi); // Now set interp. points

    // Note: the interpolatePoints consideres disc. and interp. points but not ghost points.

    for (unsigned int p = 0; p < tridat.patches.size(); p++)
    {
        RealArray positionToInterpolate(tridat.patches[p].nodenums, 3);
        RealArray interpolated_nodes(tridat.patches[p].nodenums, 1);

        interpolated_nodes = 0.;
        Range all;
        positionToInterpolate(all, 0) = tridat.patches[p].nodes_xyz(all, 0);
        positionToInterpolate(all, 1) = tridat.patches[p].nodes_xyz(all, 1);
        positionToInterpolate(all, 2) = tridat.patches[p].nodes_xyz(all, 2);
        tridat.patches[p].interp_object->interpolatePoints(positionToInterpolate, phi, interpolated_nodes);
        const RealArray &x = positionToInterpolate(all, 0);
        const RealArray &y = positionToInterpolate(all, 1);
        const RealArray &z = positionToInterpolate(all, 2);
        const RealArray &alpha = x * cos(beta) + z * sin(beta);
        RealArray phi_exact = exp(K * y) * cos(K * alpha);

        // Print to file
        string filename = resultsDirectory + "/patch_" + to_string(p) + ".interp";
        ofstream fout(filename, ios::out);
        int wdt = 18;
        fout.setf(ios_base::scientific);
        fout.precision(10);

        fout << setw(wdt) << "x" << setw(wdt) << "y" << setw(wdt) << "z" << setw(wdt) << "phi_interp" << setw(wdt) << "phi_exact"
             << endl;
        for (unsigned int i = 0; i < tridat.patches[p].nodenums; i++)
            fout << setw(wdt) << x(i) << setw(wdt) << y(i) << setw(wdt) << z(i) << setw(wdt) << interpolated_nodes(i) << setw(wdt) << phi_exact(i) << endl;

        fout.close();
    }
}