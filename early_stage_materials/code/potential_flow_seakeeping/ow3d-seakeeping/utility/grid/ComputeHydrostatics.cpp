// This public member function belongs to the Grid class, and just for
// the sake of convenience is written in a seperate file.

#include "Grid.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Grid::ComputeHydrostatics()
{
  // Following variables are used for calculation of
  // the displaced volume using the Gauss' theorem.

  realCompositeGridFunction datax(cg_), datay(cg_), dataz(cg_);
  datax = datay = dataz = 0.;

  realCompositeGridFunction dataSBSF(cg_); // For calculating the submerged surface
  dataSBSF = 1.;

  // Following variable are used for calculation of
  // the coordinates of center of buoyancy.

  realCompositeGridFunction n1x2(cg_), n2y2(cg_), n3z2(cg_);
  n1x2 = n2y2 = n3z2 = 0.;

  // Following variables are used for calculation of
  // hydrosttaic coefficients.

  realCompositeGridFunction dat_12(cg_), dat_14(cg_), dat_16(cg_), dat_22(cg_), dat_24(cg_), dat_26(cg_);
  realCompositeGridFunction dat_32(cg_), dat_34(cg_), dat_36(cg_), dat_42(cg_), dat_44(cg_), dat_46(cg_);
  realCompositeGridFunction dat_52(cg_), dat_54(cg_), dat_56(cg_), dat_62(cg_), dat_64(cg_), dat_66(cg_);

  dat_12 = dat_14 = dat_16 = dat_22 = dat_24 = dat_26 = 0.;
  dat_32 = dat_34 = dat_36 = dat_42 = dat_44 = dat_46 = 0.;
  dat_52 = dat_54 = dat_56 = dat_62 = dat_64 = dat_66 = 0.;

  realCompositeGridFunction dat_hv_hv(cg_), dat_hv_rl(cg_), dat_hv_pt(cg_);
  realCompositeGridFunction dat_rl_rl(cg_), dat_rl_pt(cg_);
  realCompositeGridFunction dat_pt_pt(cg_);

  dat_hv_hv = dat_hv_rl = dat_hv_pt = 0.;
  dat_rl_rl = dat_rl_pt = 0.;
  dat_pt_pt = 0.;

  vector<realCompositeGridFunction> dat_gmnv(UserInput.number_of_gmodes), dat_gmdisy(UserInput.number_of_gmodes), dat_gmdisyder(UserInput.number_of_gmodes);
  vector<realCompositeGridFunction> dat_gm1_(UserInput.number_of_gmodes), dat_gm2_(UserInput.number_of_gmodes), dat_gm3_(UserInput.number_of_gmodes);
  vector<realCompositeGridFunction> dat_gm4_(UserInput.number_of_gmodes), dat_gm5_(UserInput.number_of_gmodes), dat_gm6_(UserInput.number_of_gmodes);
  vector<realCompositeGridFunction> dat_gm_1(UserInput.number_of_gmodes), dat_gm_2(UserInput.number_of_gmodes), dat_gm_3(UserInput.number_of_gmodes);
  vector<realCompositeGridFunction> dat_gm_4(UserInput.number_of_gmodes), dat_gm_5(UserInput.number_of_gmodes), dat_gm_6(UserInput.number_of_gmodes);
  vector<vector<realCompositeGridFunction>> dat_gms(UserInput.number_of_gmodes, vector<realCompositeGridFunction>(UserInput.number_of_gmodes));

  for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
  {
    dat_gmnv[mcounter].updateToMatchGrid(cg_);
    dat_gmdisy[mcounter].updateToMatchGrid(cg_);
    dat_gmdisyder[mcounter].updateToMatchGrid(cg_);
    dat_gm1_[mcounter].updateToMatchGrid(cg_);
    dat_gm2_[mcounter].updateToMatchGrid(cg_);
    dat_gm3_[mcounter].updateToMatchGrid(cg_);
    dat_gm4_[mcounter].updateToMatchGrid(cg_);
    dat_gm5_[mcounter].updateToMatchGrid(cg_);
    dat_gm6_[mcounter].updateToMatchGrid(cg_);

    dat_gm_1[mcounter].updateToMatchGrid(cg_);
    dat_gm_2[mcounter].updateToMatchGrid(cg_);
    dat_gm_3[mcounter].updateToMatchGrid(cg_);
    dat_gm_4[mcounter].updateToMatchGrid(cg_);
    dat_gm_5[mcounter].updateToMatchGrid(cg_);
    dat_gm_6[mcounter].updateToMatchGrid(cg_);

    dat_gmnv[mcounter] = dat_gmdisy[mcounter] = dat_gmdisyder[mcounter] = 0.0;
    dat_gm1_[mcounter] = dat_gm2_[mcounter] = dat_gm3_[mcounter] = 0.0;
    dat_gm4_[mcounter] = dat_gm5_[mcounter] = dat_gm6_[mcounter] = 0.0;
    dat_gm_1[mcounter] = dat_gm_2[mcounter] = dat_gm_3[mcounter] = 0.0;
    dat_gm_4[mcounter] = dat_gm_5[mcounter] = dat_gm_6[mcounter] = 0.0;
  }

  for (unsigned int mcounter1 = 0; mcounter1 < UserInput.number_of_gmodes; mcounter1++)
  {
    for (unsigned int mcounter2 = 0; mcounter2 < UserInput.number_of_gmodes; mcounter2++)
    {
      dat_gms[mcounter1][mcounter2].updateToMatchGrid(cg_);
      dat_gms[mcounter1][mcounter2] = 0.0;
    }
  }

  double rho = OW3DSeakeeping::rho;
  double g = OW3DSeakeeping::UserInput.g;

  Integrate integrator;
  if (gridData_.triangulation.patches.size() == 0)
    integrator = GetIntegratorOverBody(cg_, gridData_.boundariesData);

  unsigned int numberOfIntegrals = (gridData_.halfSymmetry) ? 2 : 1;
  unsigned int mult = (gridData_.halfSymmetry) ? 2 : 1;

  double VOLM = 0., MASS = 0.;
  double volx = 0., voly = 0., volz = 0.;
  double xb = 0., yb = 0., zb = 0.;
  double SBSF = 0.;

  double xg = OW3DSeakeeping::UserInput.gravitation_centre[0];
  double yg = OW3DSeakeeping::UserInput.gravitation_centre[1];
  double zg = OW3DSeakeeping::UserInput.gravitation_centre[2];

  for (unsigned int i = 0; i < numberOfIntegrals; i++)
  {
    for (unsigned int surface = 0; surface < gridData_.boundariesData.exciting.size(); surface++)
    {
      const Single_boundary_data &be = gridData_.boundariesData.exciting[surface];
      const vector<Index> &Is = be.surface_indices;
      const MappedGrid &mg = cg_[be.grid];
      const RealArray &v = mg.vertex();
      const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

      RealArray x = v(Is[0], Is[1], Is[2], axis1);
      RealArray y = v(Is[0], Is[1], Is[2], axis2);
      RealArray z(Is[0], Is[1], Is[2]);

      RealArray n1 = vbn(Is[0], Is[1], Is[2], axis1);
      RealArray n2 = vbn(Is[0], Is[1], Is[2], axis2);
      RealArray n3(Is[0], Is[1], Is[2]);

      z = (gridData_.nod == 2) ? 0 * x : v(Is[0], Is[1], Is[2], axis3);
      z = (i == 0) ? z : -z;
      n3 = (gridData_.nod == 2) ? 0 *x : n3 = vbn(Is[0], Is[1], Is[2], axis3);
      n3 = (i == 0) ? n3 : -n3;

      // Define displacement in heave direction and generalized normal vector of shape function  in variours shapes

      RealArray n4 = -z * n2 + y * n3;
      RealArray n5 = z * n1 - x * n3;
      RealArray n6 = -y * n1 + x * n2;
      RealArray disy4 = -z;
      RealArray disy6 = x;

      datax[be.grid](Is[0], Is[1], Is[2]) = -n1 * x;
      datay[be.grid](Is[0], Is[1], Is[2]) = -n2 * y;
      dataz[be.grid](Is[0], Is[1], Is[2]) = -n3 * z;

      n1x2[be.grid](Is[0], Is[1], Is[2]) = n1 * x * x;
      n2y2[be.grid](Is[0], Is[1], Is[2]) = n2 * y * y;
      n3z2[be.grid](Is[0], Is[1], Is[2]) = n3 * z * z;

      if (gridData_.wlData.size() != 0) // No water line integral for submerged bodies
      {
        if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::MA)
        {
          // dat_22[be.grid](Is[0], Is[1], Is[2]) = n2;            // c 22   HEAVE - HEAVE
          // dat_62[be.grid](Is[0], Is[1], Is[2]) = n6;            // c 62   PITCH - HEAVE
          // dat_26[be.grid](Is[0], Is[1], Is[2]) = x * n2;        // c 26   HEAVE - PITCH
          // dat_44[be.grid](Is[0], Is[1], Is[2]) = -z * n4;       // c 44   ROLL  - ROLL
          // dat_54[be.grid](Is[0], Is[1], Is[2]) = -z * n5;       // c 54   YAW   - ROLL
          // dat_66[be.grid](Is[0], Is[1], Is[2]) = x * n6;        // c 66   PITCH - PITCH

          dat_22[be.grid](Is[0], Is[1], Is[2]) = n2;         // c 22   HEAVE - HEAVE
          dat_26[be.grid](Is[0], Is[1], Is[2]) = n2 * x;     // c 62   PITCH - HEAVE - PITCH
          dat_44[be.grid](Is[0], Is[1], Is[2]) = n2 * z * z; // c 44   ROLL  - ROLL
          dat_66[be.grid](Is[0], Is[1], Is[2]) = n2 * x * x; // c 66   PITCH - PITCH
        }

        else
        {
          dat_hv_hv[be.grid](Is[0], Is[1], Is[2]) = n2;
          dat_hv_rl[be.grid](Is[0], Is[1], Is[2]) = n2 * z; // 0
          dat_hv_pt[be.grid](Is[0], Is[1], Is[2]) = n2 * x;
          dat_rl_rl[be.grid](Is[0], Is[1], Is[2]) = n2 * z * z;
          dat_rl_pt[be.grid](Is[0], Is[1], Is[2]) = n2 * x * z; // 0
          dat_pt_pt[be.grid](Is[0], Is[1], Is[2]) = n2 * x * x;
        }

        if (gridData_.flexmodes.size() != 0)
        {
          for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
          {
            dat_gmnv[mcounter][be.grid](Is[0], Is[1], Is[2]) = gridData_.flexmodes[mcounter].flex_disp[surface] * n2;
            dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]) = gridData_.flexmodes[mcounter].flex_disp[surface];
            dat_gmdisyder[mcounter][be.grid](Is[0], Is[1], Is[2]) = gridData_.flexmodes[mcounter].flex_disp_der[surface];
          }

          if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::NE)
          {
            for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
            {
              dat_gm2_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmnv[mcounter][be.grid](Is[0], Is[1], Is[2]) * 1;
              dat_gm6_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmnv[mcounter][be.grid](Is[0], Is[1], Is[2]) * disy6;
            }
            for (unsigned int mcounter1 = 0; mcounter1 < UserInput.number_of_gmodes; mcounter1++)
            {
              for (unsigned int mcounter2 = 0; mcounter2 < UserInput.number_of_gmodes; mcounter2++)
              {
                dat_gms[mcounter1][mcounter2][be.grid](Is[0], Is[1], Is[2]) = dat_gmnv[mcounter2][be.grid](Is[0], Is[1], Is[2]) * dat_gmdisy[mcounter1][be.grid](Is[0], Is[1], Is[2]);
              }
            }
          }
          else if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::NG)
          {
            for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
            {
              dat_gm2_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmnv[mcounter][be.grid](Is[0], Is[1], Is[2]) * 1;
              dat_gm6_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmnv[mcounter][be.grid](Is[0], Is[1], Is[2]) * disy6;
            }
            for (unsigned int mcounter1 = 0; mcounter1 < UserInput.number_of_gmodes; mcounter1++)
            {
              for (unsigned int mcounter2 = 0; mcounter2 < UserInput.number_of_gmodes; mcounter2++)
              {
                dat_gms[mcounter1][mcounter2][be.grid](Is[0], Is[1], Is[2]) = dat_gmnv[mcounter2][be.grid](Is[0], Is[1], Is[2]) * dat_gmdisy[mcounter1][be.grid](Is[0], Is[1], Is[2]);
              }
            }
          }

          else if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::MA) // based on Malenica if j<6 exchange i and j, if j > 5, i and j keep same with paper Iwwwfb 2020
          {
            for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
            {
              dat_gm1_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]) * n1 - y * dat_gmdisyder[mcounter][be.grid](Is[0], Is[1], Is[2]) * n2;
              dat_gm2_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]) * n2;
              dat_gm6_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]) * n6 - y * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]) * n1 + y * y * dat_gmdisyder[mcounter][be.grid](Is[0], Is[1], Is[2]) * n2;
            }

            for (unsigned int mcounter1 = 0; mcounter1 < UserInput.number_of_gmodes; mcounter1++)
            {
              for (unsigned int mcounter2 = 0; mcounter2 < UserInput.number_of_gmodes; mcounter2++)
              {
                dat_gms[mcounter1][mcounter2][be.grid](Is[0], Is[1], Is[2]) = dat_gmdisy[mcounter2][be.grid](Is[0], Is[1], Is[2]) * dat_gmnv[mcounter1][be.grid](Is[0], Is[1], Is[2]);
              }
            }
          }

          if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::NE)
          {
            for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
            {
              dat_gm_1[mcounter][be.grid](Is[0], Is[1], Is[2]) = n1 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
              dat_gm_2[mcounter][be.grid](Is[0], Is[1], Is[2]) = n2 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
              dat_gm_4[mcounter][be.grid](Is[0], Is[1], Is[2]) = n4 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]); // equal to 0
              dat_gm_6[mcounter][be.grid](Is[0], Is[1], Is[2]) = n6 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
            }
          }

          else if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::NG)
          {
            for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
            {
              dat_gm_1[mcounter][be.grid](Is[0], Is[1], Is[2]) = 2 * n1 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
              dat_gm_2[mcounter][be.grid](Is[0], Is[1], Is[2]) = n2 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
              dat_gm_6[mcounter][be.grid](Is[0], Is[1], Is[2]) = n6 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]) - n1 * y * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
            }
          }

          else if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::MA)
          {
            for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
            {
              dat_gm_2[mcounter][be.grid](Is[0], Is[1], Is[2]) = n2 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
              dat_gm_6[mcounter][be.grid](Is[0], Is[1], Is[2]) = x * n2 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
            }
          }

          else if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::WA)
          {
            for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
            {
              if (mcounter % 2)
              {
                dat_gm2_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmnv[mcounter][be.grid](Is[0], Is[1], Is[2]) * 1;
                dat_gm_1[mcounter][be.grid](Is[0], Is[1], Is[2]) = n1 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
                dat_gm_6[mcounter][be.grid](Is[0], Is[1], Is[2]) = n6 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
              }
              else
              {
                dat_gm_2[mcounter][be.grid](Is[0], Is[1], Is[2]) = n2 * dat_gmdisy[mcounter][be.grid](Is[0], Is[1], Is[2]);
                dat_gm6_[mcounter][be.grid](Is[0], Is[1], Is[2]) = dat_gmnv[mcounter][be.grid](Is[0], Is[1], Is[2]) * disy6;
              }
            }

            for (unsigned int mcounter1 = 0; mcounter1 < UserInput.number_of_gmodes; mcounter1++)
            {
              for (unsigned int mcounter2 = 0; mcounter2 < UserInput.number_of_gmodes; mcounter2++)
              {
                if ((((mcounter1 + 2) % 2) && ((mcounter2 + 2) % 2)) || (((mcounter1 + 1) % 2) && ((mcounter2 + 1) % 2)))
                  dat_gms[mcounter1][mcounter2][be.grid](Is[0], Is[1], Is[2]) = dat_gmdisy[mcounter2][be.grid](Is[0], Is[1], Is[2]) * dat_gmnv[mcounter1][be.grid](Is[0], Is[1], Is[2]);
              }
            }
          }

        } // Gmodes check

      } // Submrged-bodies check

    } // End of loop over body surface

    volx = ComputeSurfaceIntegral(integrator, gridData_.triangulation, datax);
    voly = ComputeSurfaceIntegral(integrator, gridData_.triangulation, datay);
    volz = ComputeSurfaceIntegral(integrator, gridData_.triangulation, dataz);

    SBSF = ComputeSurfaceIntegral(integrator, gridData_.triangulation, dataSBSF);

    VOLM = (volx + voly + volz) / 3.;

    xb = -1. / (2 * VOLM) * ComputeSurfaceIntegral(integrator, gridData_.triangulation, n1x2);
    yb = -1. / (2 * VOLM) * ComputeSurfaceIntegral(integrator, gridData_.triangulation, n2y2);
    zb = -1. / (2 * VOLM) * ComputeSurfaceIntegral(integrator, gridData_.triangulation, n3z2);

    MASS = rho * VOLM;

    if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::NE || gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::NG || gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::WA)
    {
      gridData_.hrs.complete_hydro_matrix[1][1] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_hv_hv);                                       // HEAVE - HEAVE
      gridData_.hrs.complete_hydro_matrix[1][3] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_hv_rl);                                       // HEAVE - ROLL
      gridData_.hrs.complete_hydro_matrix[1][5] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_hv_pt);                                       // HEAVE - PITCH
      gridData_.hrs.complete_hydro_matrix[3][3] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_rl_rl) + rho * g * VOLM * yb - MASS * g * yg; // ROLL  - ROLL
      gridData_.hrs.complete_hydro_matrix[3][5] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_rl_pt);                                       // ROLL  - PITCH
      gridData_.hrs.complete_hydro_matrix[3][4] += -rho * g * VOLM * xb + MASS * g * xg;                                                                                   // ROLL  - YAW
      gridData_.hrs.complete_hydro_matrix[5][5] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_pt_pt) + rho * g * VOLM * yb - MASS * g * yg; // PITCH - PITCH
      gridData_.hrs.complete_hydro_matrix[5][4] += -rho * g * VOLM * zb + MASS * g * zg;                                                                                   // PITCH - YAW
    }
    else if (gmode_hydrostatics == OW3DSeakeeping::GMODES_HYDROSTATICS::MA)
    {
      // gridData_.hrs.complete_hydro_matrix[1][1] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_22);                 // c 22   HEAVE - HEAVE
      // gridData_.hrs.complete_hydro_matrix[1][5] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_26);                 // c 26   HEAVE - PITCH
      // gridData_.hrs.complete_hydro_matrix[3][3] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_44) - MASS * g * yg; // c 44   ROLL  - ROLL
      // gridData_.hrs.complete_hydro_matrix[4][3] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_54) + MASS * g * xg; // c 54   YAW   - ROLL
      // gridData_.hrs.complete_hydro_matrix[5][1] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_62);                 // c 62   PITCH - HEAVE
      // gridData_.hrs.complete_hydro_matrix[5][5] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_66) - MASS * g * yg; // c 66   PITCH - PITCH

      gridData_.hrs.complete_hydro_matrix[1][1] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_22);                                       // c 22   HEAVE - HEAVE
      gridData_.hrs.complete_hydro_matrix[1][5] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_26);                                       // c 62   HEAVE - PITCH
      gridData_.hrs.complete_hydro_matrix[3][3] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_44) + rho * g * VOLM * yb - MASS * g * yg; // c 44   ROLL  - ROLL
      gridData_.hrs.complete_hydro_matrix[4][3] += -rho * g * VOLM * xb + MASS * g * xg;                                                                                // c 54   YAW   - ROLL
      gridData_.hrs.complete_hydro_matrix[4][5] += -rho * g * VOLM * zb + MASS * g * zg;                                                                                // c 56    YAW  - PITCH
      gridData_.hrs.complete_hydro_matrix[5][5] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_66) + rho * g * VOLM * yb - MASS * g * yg; // c 66   PITCH - PITCH
    }

    if (gridData_.flexmodes.size() != 0)
    {
      for (unsigned int mcounter = 0; mcounter < UserInput.number_of_gmodes; mcounter++)
      {
        gridData_.hrs.complete_hydro_matrix[0][mcounter + 6] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm1_[mcounter]);
        gridData_.hrs.complete_hydro_matrix[1][mcounter + 6] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm2_[mcounter]);
        gridData_.hrs.complete_hydro_matrix[2][mcounter + 6] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm3_[mcounter]);
        gridData_.hrs.complete_hydro_matrix[3][mcounter + 6] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm4_[mcounter]);
        gridData_.hrs.complete_hydro_matrix[4][mcounter + 6] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm5_[mcounter]);
        gridData_.hrs.complete_hydro_matrix[5][mcounter + 6] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm6_[mcounter]);
        gridData_.hrs.complete_hydro_matrix[mcounter + 6][0] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm_1[mcounter]);
        gridData_.hrs.complete_hydro_matrix[mcounter + 6][1] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm_2[mcounter]); //
        gridData_.hrs.complete_hydro_matrix[mcounter + 6][3] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm_4[mcounter]); //
        gridData_.hrs.complete_hydro_matrix[mcounter + 6][5] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gm_6[mcounter]); //
      }
    }

    for (unsigned int mcounter1 = 0; mcounter1 < UserInput.number_of_gmodes; mcounter1++)
    {
      for (unsigned int mcounter2 = 0; mcounter2 < UserInput.number_of_gmodes; mcounter2++)
      {
        gridData_.hrs.complete_hydro_matrix[mcounter1 + 6][mcounter2 + 6] += rho * g * ComputeSurfaceIntegral(integrator, gridData_.triangulation, dat_gms[mcounter1][mcounter2]);
      }
    }

  } // End of loop for number of integration due to grid symmetry

  // The symmetric coefficients :00

  gridData_.hrs.complete_hydro_matrix[3][1] = gridData_.hrs.complete_hydro_matrix[1][3];
  gridData_.hrs.complete_hydro_matrix[5][1] = gridData_.hrs.complete_hydro_matrix[1][5];
  gridData_.hrs.complete_hydro_matrix[5][3] = gridData_.hrs.complete_hydro_matrix[5][3];

  // The submerged volume and center of buoyancy :

  gridData_.hrs.volx = mult * volx;
  gridData_.hrs.voly = mult * voly;
  gridData_.hrs.volz = mult * volz;

  gridData_.hrs.VOLM = mult * VOLM;
  gridData_.hrs.MASS = mult * MASS;

  gridData_.hrs.SBSF = mult * SBSF;

  gridData_.hrs.xb = xb;
  gridData_.hrs.yb = yb;

  if (!gridData_.halfSymmetry)
    gridData_.hrs.zb = zb;

  // Extract the "reduced" hydrostatic matrix for the equation of motion

  if (UserInput.solve_motion)
  {
    vector<unsigned int> index;
    gridData_.hrs.reduced_hydro_matrix.resize(UserInput.responses.size());

    for (unsigned int v = 0; v < UserInput.responses.size(); v++)
    {
      if (UserInput.responses[v] == MODE_NAMES::SURGE)
        index.push_back(0);
      else if (UserInput.responses[v] == MODE_NAMES::HEAVE)
        index.push_back(1);
      else if (UserInput.responses[v] == MODE_NAMES::SWAY)
        index.push_back(2);
      else if (UserInput.responses[v] == MODE_NAMES::ROLL)
        index.push_back(3);
      else if (UserInput.responses[v] == MODE_NAMES::YAW)
        index.push_back(4);
      else if (UserInput.responses[v] == MODE_NAMES::PITCH)
        index.push_back(5);
      else if (UserInput.responses[v] == MODE_NAMES::GMODE)
      {
        for (unsigned int i = total_number_of_rigid_modes; i < total_number_of_rigid_modes + UserInput.number_of_gmodes; i++)
          index.push_back(i);
      }
    }

    for (unsigned int e = 0; e < UserInput.responses.size(); e++)
    {
      unsigned int i = index[e];
      for (unsigned int res = 0; res < UserInput.responses.size(); res++)
      {
        unsigned int j = index[res];
        gridData_.hrs.reduced_hydro_matrix[e].push_back(gridData_.hrs.complete_hydro_matrix[i][j]);
      }
    }

  } // End of motion check

  PrintGridHydrostatics_();

} // End of ComputeHydrostatics
