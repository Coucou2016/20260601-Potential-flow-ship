#include "Ogshow.h"
#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::PrintAnalyticalDoublebody_(
    vector<double> geometry,
    analyticalData (*pf)(CompositeGrid &, const All_boundaries_data &, vector<double>, double))
{
    if (UserInput.base_flow_type != BASE_FLOW_TYPES::DB)
        throw runtime_error("ERROR! Baseflow.cpp: No analytical solution is expected for NK linearisations.");

    analyticalData analytical = (*pf)(*cg_, *boundariesData_, geometry, UserInput.U);

    // ** show base flow potential
    string showfile = resultsDirectory_ + '/' + abase_show_file;
    Ogshow show(showfile);
    show.startFrame();
    show.saveSolution(analytical.potential);

    // ---------------------------------------------
    // COMPARISON WITH THE COMPUTATIONAL SOLUTIONS
    // ---------------------------------------------
    string filename = resultsDirectory_ + '/' + base_error_file;
    ofstream fout(filename, ios::out);
    fout.setf(ios_base::scientific);
    fout.precision(OW3DSeakeeping::print_precision);
    fout << "Max double-body potential error on grids" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';

    vector<double> ptnErr;

    for (int grid = 0; grid < cg_->numberOfComponentGrids(); grid++)
    {
        Index I1, I2, I3;
        const MappedGrid &mg = (*cg_)[grid];
        getIndex(mg.gridIndexRange(), I1, I2, I3);

        ptnErr.clear();

        for (int i = I1.getBase(); i <= I1.getBound(); i++)
        {
            for (int j = I2.getBase(); j <= I2.getBound(); j++)
            {
                for (int k = I3.getBase(); k <= I3.getBound(); k++)
                {
                    if (mg.mask()(i, j, k) > 0)

                        ptnErr.push_back(abs(analytical.potential[grid](i, j, k) - data_.potential[grid](i, j, k)));
                }
            }
        }

        fout << " Grid " << grid << " : " << *max_element(ptnErr.begin(), ptnErr.end()) << '\n';
    }

    fout.close();

    // ** Base flow elevation

    if (calcBaseElev_)
    {
        ComputeDoublebodyElevation_(
            analytical_elevation_,
            analytical.field_derivative.d_phib_dx,
            analytical.field_derivative.d_phib_dy,
            analytical.field_derivative.d_phib_dz);

        elevationDerivative elevation_derivative;

        for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
        {
            const Single_boundary_data &bs = boundariesData_->free[surface];
            const vector<Index> &Is = bs.surface_indices;
            realArray temp(Is[0], Is[1], Is[2]);
            temp = 0.0;
            elevation_derivative.dx.push_back(temp);
            elevation_derivative.dz.push_back(temp);
        }

        string elevation_filename = resultsDirectory_ + '/' + abase_elev_file;
        PrintBaseFlowElevation_(analytical_elevation_, elevation_filename);
        ComputeBaseflowElevationDerivatives_(analytical_elevation_, elevation_derivative);
        string derivatives_filename = resultsDirectory_ + '/' + abase_free_dervs_file;
        PrintBaseFlowDerivatives_(analytical.surface_derivative, elevation_derivative, derivatives_filename);
    }

    // ** Calculate and output mterms

    Mterms mterms;
    for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++) // assign base-flow mterms (note: loop over exciting surface)
    {
        const Single_boundary_data &be = boundariesData_->exciting[surface];
        const vector<Index> &Ie = be.surface_indices;
        realArray temp(Ie[0], Ie[1], Ie[2]);
        temp = 0.0;
        mterms.m1.push_back(temp);
        mterms.m2.push_back(temp);
        mterms.m3.push_back(temp);
        mterms.m4.push_back(temp);
        mterms.m5.push_back(temp);
        mterms.m6.push_back(temp);
    }

    ComputeMTerms_(analytical.body_derivative, mterms);
    string mterms_file = resultsDirectory_ + '/' + abase_m_terms_file;
    PrintMTerms_(mterms, mterms_file);
}