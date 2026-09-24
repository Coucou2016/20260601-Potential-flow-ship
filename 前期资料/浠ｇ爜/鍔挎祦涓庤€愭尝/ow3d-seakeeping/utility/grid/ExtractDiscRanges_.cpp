#include "OW3DUtilFunctions.h"
#include "Grid.h"

vector<vector<vector<OW3DSeakeeping::DiscRanges>>> GetTheRanges(
    const CompositeGrid &cg,
    OW3DSeakeeping::All_boundaries_data boundariesData_,
    int order,
    string surfce_type)
{
    if (order != 4)
        throw runtime_error(OW3DSeakeeping::GetColoredMessage("\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Only 4th order is supported.", 0));

    unsigned int ns;
    if (surfce_type == "body")
        ns = boundariesData_.exciting.size();
    else if (surfce_type == "free")
        ns = boundariesData_.free.size();
    else
        throw runtime_error(OW3DSeakeeping::GetColoredMessage("\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t The surface type is not correct.", 0));

    vector<vector<vector<OW3DSeakeeping::DiscRanges>>> all_disc_ranges;
    all_disc_ranges.resize(ns);

    for (unsigned int surface = 0; surface < ns; surface++)
    {
        OW3DSeakeeping::Single_boundary_data bs;
        if (surfce_type == "body")
            bs = boundariesData_.exciting[surface];
        else
            bs = boundariesData_.free[surface];

        const vector<Index> &Is = bs.surface_indices;
        all_disc_ranges[surface].resize(2);

        int l0, l1;
        if (Is[0].length() == 1)
        {
            l0 = Is[1].length();
            l1 = Is[2].length();
        }
        else if (Is[1].length() == 1)
        {
            l0 = Is[0].length();
            l1 = Is[2].length();
        }
        else
        {
            l0 = Is[0].length();
            l1 = Is[1].length();
        }

        all_disc_ranges[surface][0].resize(l0);
        all_disc_ranges[surface][1].resize(l1);
    }

    for (unsigned int surface = 0; surface < ns; surface++)
    {
        OW3DSeakeeping::Single_boundary_data bs;
        if (surfce_type == "body")
            bs = boundariesData_.exciting[surface];
        else
            bs = boundariesData_.free[surface];

        const vector<Index> &Is = bs.surface_indices;
        const MappedGrid &mg = cg[bs.grid];

        if (Is[0].length() == 1)
        {
            int s0 = Is[0].getBase();
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
            {
                OW3DSeakeeping::DiscRanges disc_ranges;
                int start_index_disc;
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++) // ROD
                {
                    if ((mg.mask()(s0, j, k) > 0) & (k == Is[2].getBase() || mg.mask()(s0, j, k - 1) <= 0))
                        start_index_disc = k;
                    if ((mg.mask()(s0, j, k) > 0) & (k == Is[2].getBound() || mg.mask()(s0, j, k + 1) <= 0))
                    {
                        if (k - start_index_disc < order / 2)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough physical points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.ROD.push_back(Range(start_index_disc, k));
                    }
                }
                int start_index_intp;
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++) // RNH
                {
                    if ((mg.mask()(s0, j, k) != 0) & (k == Is[2].getBase() || mg.mask()(s0, j, k - 1) == 0))
                        start_index_intp = k;
                    if ((mg.mask()(s0, j, k) != 0) & (k == Is[2].getBound() || mg.mask()(s0, j, k + 1) == 0))
                    {
                        Range range(start_index_intp, k);
                        Range range_with_ghost = range;
                        if (k == Is[2].getBase())
                            range_with_ghost = Range(start_index_intp - order / 2, k);
                        if (k == Is[2].getBound())
                            range_with_ghost = Range(start_index_intp, k + order / 2);
                        int aDiscretisationPointInTheRange = sum(mg.mask()(s0, j, range_with_ghost) > 0);
                        if (range_with_ghost.length() < (order + 1) && aDiscretisationPointInTheRange)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough valid points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.RNH.push_back(range);
                    }
                }
                int start_index_hole;
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++) // ROH
                {
                    if ((mg.mask()(s0, j, k) == 0) & (k == Is[2].getBase() || mg.mask()(s0, j, k - 1) != 0))
                        start_index_hole = k;
                    if ((mg.mask()(s0, j, k) == 0) & (k == Is[2].getBound() || mg.mask()(s0, j, k + 1) != 0))
                        disc_ranges.ROH.push_back(Range(start_index_hole, k));
                }

                all_disc_ranges[surface][0][j] = disc_ranges;
            }
            //
            for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
            {
                OW3DSeakeeping::DiscRanges disc_ranges;
                int start_index_disc;
                for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++) // ROD
                {
                    if ((mg.mask()(s0, j, k) > 0) & (j == Is[1].getBase() || mg.mask()(s0, j - 1, k) <= 0))
                        start_index_disc = j;
                    if ((mg.mask()(s0, j, k) > 0) & (j == Is[1].getBound() || mg.mask()(s0, j + 1, k) <= 0))
                    {
                        if (j - start_index_disc < order / 2)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough physical points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.ROD.push_back(Range(start_index_disc, j));
                    }
                }
                int start_index_intp;
                for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++) // RNH
                {
                    if ((mg.mask()(s0, j, k) != 0) & (j == Is[1].getBase() || mg.mask()(s0, j - 1, k) == 0))
                        start_index_intp = j;
                    if ((mg.mask()(s0, j, k) != 0) & (j == Is[1].getBound() || mg.mask()(s0, j + 1, k) == 0))
                    {
                        Range range(start_index_intp, j);
                        Range range_with_ghost = range;
                        if (j == Is[1].getBase())
                            range_with_ghost = Range(start_index_intp - order / 2, j);
                        if (j == Is[1].getBound())
                            range_with_ghost = Range(start_index_intp, j + order / 2);
                        int aDiscretisationPointInTheRange = sum(mg.mask()(s0, range_with_ghost, k) > 0);
                        if (range_with_ghost.length() < (order + 1) && aDiscretisationPointInTheRange)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough valid points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.RNH.push_back(range);
                    }
                }
                int start_index_hole;
                for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++) // ROH
                {
                    if ((mg.mask()(s0, j, k) == 0) & (j == Is[1].getBase() || mg.mask()(s0, j - 1, k) != 0))
                        start_index_hole = j;
                    if ((mg.mask()(s0, j, k) == 0) & (j == Is[1].getBound() || mg.mask()(s0, j + 1, k) != 0))
                        disc_ranges.ROH.push_back(Range(start_index_hole, j));
                }

                all_disc_ranges[surface][1][k] = disc_ranges;
            }
        }
        //
        if (Is[1].length() == 1)
        {
            int s1 = Is[1].getBase();
            for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
            {
                OW3DSeakeeping::DiscRanges disc_ranges;
                int start_index_disc;
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++) // ROD
                {
                    if ((mg.mask()(i, s1, k) > 0) & (k == Is[2].getBase() || mg.mask()(i, s1, k - 1) <= 0))
                        start_index_disc = k;
                    if ((mg.mask()(i, s1, k) > 0) & (k == Is[2].getBound() || mg.mask()(i, s1, k + 1) <= 0))
                    {
                        if (k - start_index_disc < order / 2)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough physical points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.ROD.push_back(Range(start_index_disc, k));
                    }
                }
                int start_index_intp;
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++) // RNH
                {
                    if ((mg.mask()(i, s1, k) != 0) & (k == Is[2].getBase() || mg.mask()(i, s1, k - 1) == 0))
                        start_index_intp = k;
                    if ((mg.mask()(i, s1, k) != 0) & (k == Is[2].getBound() || mg.mask()(i, s1, k + 1) == 0))
                    {
                        Range range(start_index_intp, k);
                        Range range_with_ghost = range;
                        if (k == Is[2].getBase())
                            range_with_ghost = Range(start_index_intp - order / 2, k);
                        if (k == Is[2].getBound())
                            range_with_ghost = Range(start_index_intp, k + order / 2);
                        int aDiscretisationPointInTheRange = sum(mg.mask()(i, s1, range_with_ghost) > 0);
                        if (range_with_ghost.length() < (order + 1) && aDiscretisationPointInTheRange)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough valid points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.RNH.push_back(range);
                    }
                }
                int start_index_hole;
                for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++) // ROH
                {
                    if ((mg.mask()(i, s1, k) == 0) & (k == Is[2].getBase() || mg.mask()(i, s1, k - 1) != 0))
                        start_index_hole = k;
                    if ((mg.mask()(i, s1, k) == 0) & (k == Is[2].getBound() || mg.mask()(i, s1, k + 1) != 0))
                        disc_ranges.ROH.push_back(Range(start_index_hole, k));
                }

                all_disc_ranges[surface][0][i] = disc_ranges;
            }
            //
            for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
            {
                OW3DSeakeeping::DiscRanges disc_ranges;
                int start_index_disc;
                for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++) // ROD
                {
                    if ((mg.mask()(i, s1, k) > 0) & (i == Is[0].getBase() || mg.mask()(i - 1, s1, k) <= 0))
                        start_index_disc = i;
                    if ((mg.mask()(i, s1, k) > 0) & (i == Is[0].getBound() || mg.mask()(i + 1, s1, k) <= 0))
                    {
                        if (i - start_index_disc < order / 2)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough physical points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.ROD.push_back(Range(start_index_disc, i));
                    }
                }
                int start_index_intp;
                for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++) // RNH
                {
                    if ((mg.mask()(i, s1, k) != 0) & (i == Is[0].getBase() || mg.mask()(i - 1, s1, k) == 0))
                        start_index_intp = i;
                    if ((mg.mask()(i, s1, k) != 0) & (i == Is[0].getBound() || mg.mask()(i + 1, s1, k) == 0))
                    {
                        Range range(start_index_intp, i);
                        Range range_with_ghost = range;
                        if (i == Is[0].getBase())
                            range_with_ghost = Range(start_index_intp - order / 2, i);
                        if (i == Is[0].getBound())
                            range_with_ghost = Range(start_index_intp, i + order / 2);
                        int aDiscretisationPointInTheRange = sum(mg.mask()(range_with_ghost, s1, k) > 0);
                        if (range_with_ghost.length() < (order + 1) && aDiscretisationPointInTheRange)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough valid points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.RNH.push_back(range);
                    }
                }
                int start_index_hole;
                for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++) // ROH
                {
                    if ((mg.mask()(i, s1, k) == 0) & (i == Is[0].getBase() || mg.mask()(i - 1, s1, k) != 0))
                        start_index_hole = i;
                    if ((mg.mask()(i, s1, k) == 0) & (i == Is[0].getBound() || mg.mask()(i + 1, s1, k) != 0))
                        disc_ranges.ROH.push_back(Range(start_index_hole, i));
                }

                all_disc_ranges[surface][1][k] = disc_ranges;
            }
        }
        //
        if (Is[2].length() == 1)
        {
            int s2 = Is[2].getBase();
            for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
            {
                OW3DSeakeeping::DiscRanges disc_ranges;
                int start_index_disc;
                for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++) // ROD
                {
                    if ((mg.mask()(i, j, s2) > 0) & (j == Is[1].getBase() || mg.mask()(i, j - 1, s2) <= 0))
                        start_index_disc = j;
                    if ((mg.mask()(i, j, s2) > 0) & (j == Is[1].getBound() || mg.mask()(i, j + 1, s2) <= 0))
                    {
                        if (j - start_index_disc < order / 2)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough physical points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.ROD.push_back(Range(start_index_disc, j));
                    }
                }
                int start_index_intp;
                for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++) // RNH
                {
                    if ((mg.mask()(i, j, s2) != 0) & (j == Is[1].getBase() || mg.mask()(i, j - 1, s2) == 0))
                        start_index_intp = j;
                    if ((mg.mask()(i, j, s2) != 0) & (j == Is[1].getBound() || mg.mask()(i, j + 1, s2) == 0))
                    {
                        Range range(start_index_intp, j);
                        Range range_with_ghost = range;
                        if (j == Is[1].getBase())
                            range_with_ghost = Range(start_index_intp - order / 2, j);
                        if (j == Is[1].getBound())
                            range_with_ghost = Range(start_index_intp, j + order / 2);
                        int aDiscretisationPointInTheRange = sum(mg.mask()(i, range_with_ghost, s2) > 0);
                        if (range_with_ghost.length() < (order + 1) && aDiscretisationPointInTheRange)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough valid points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.RNH.push_back(range);
                    }
                }
                int start_index_hole;
                for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++) // ROH
                {
                    if ((mg.mask()(i, j, s2) == 0) & (j == Is[1].getBase() || mg.mask()(i, j - 1, s2) != 0))
                        start_index_hole = j;
                    if ((mg.mask()(i, j, s2) == 0) & (j == Is[1].getBound() || mg.mask()(i, j + 1, s2) != 0))
                        disc_ranges.ROH.push_back(Range(start_index_hole, j));
                }
                all_disc_ranges[surface][0][i] = disc_ranges;
            }
            //
            for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
            {
                OW3DSeakeeping::DiscRanges disc_ranges;
                int start_index_disc;
                for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++) // ROD
                {
                    if ((mg.mask()(i, j, s2) > 0) & (i == Is[0].getBase() || mg.mask()(i - 1, j, s2) <= 0))
                        start_index_disc = i;
                    if ((mg.mask()(i, j, s2) > 0) & (i == Is[0].getBound() || mg.mask()(i + 1, j, s2) <= 0))
                    {
                        if (i - start_index_disc < order / 2)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough physical points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.ROD.push_back(Range(start_index_disc, i));
                    }
                }
                int start_index_intp;
                for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++) // RNH
                {
                    if ((mg.mask()(i, j, s2) != 0) & (i == Is[0].getBase() || mg.mask()(i - 1, j, s2) == 0))
                        start_index_intp = i;
                    if ((mg.mask()(i, j, s2) != 0) & (i == Is[0].getBound() || mg.mask()(i + 1, j, s2) == 0))
                    {
                        Range range(start_index_intp, i);
                        Range range_with_ghost = range;
                        if (i == Is[0].getBase())
                            range_with_ghost = Range(start_index_intp - order / 2, i);
                        if (i == Is[0].getBound())
                            range_with_ghost = Range(start_index_intp, i + order / 2);
                        int aDiscretisationPointInTheRange = sum(mg.mask()(range_with_ghost, j, s2) > 0);
                        if (range_with_ghost.length() < (order + 1) && aDiscretisationPointInTheRange)
                        {
                            string message = "\t Error (OW3D), Grid::ExtractDiscRanges_.cpp.\n\t Not enough valid points on " + surfce_type + " " + "surface.";
                            throw runtime_error(OW3DSeakeeping::GetColoredMessage(message, 0));
                        }
                        disc_ranges.RNH.push_back(range);
                    }
                }
                int start_index_hole;
                for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++) // ROH
                {
                    if ((mg.mask()(i, j, s2) == 0) & (i == Is[0].getBase() || mg.mask()(i - 1, j, s2) != 0))
                        start_index_hole = i;
                    if ((mg.mask()(i, j, s2) == 0) & (i == Is[0].getBound() || mg.mask()(i + 1, j, s2) != 0))
                        disc_ranges.ROH.push_back(Range(start_index_hole, i));
                }

                all_disc_ranges[surface][1][j] = disc_ranges;
            }
        }
    }

    return all_disc_ranges;
}

void OW3DSeakeeping::Grid::ExtractDiscRanges_()
{
    int order = gridData_.order_space;
    gridData_.body_surface_disc = GetTheRanges(cg_, gridData_.boundariesData, order, "body");
    gridData_.free_surface_disc = GetTheRanges(cg_, gridData_.boundariesData, order, "free");
}