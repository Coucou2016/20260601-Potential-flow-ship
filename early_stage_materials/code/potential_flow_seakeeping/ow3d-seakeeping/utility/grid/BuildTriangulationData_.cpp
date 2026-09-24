#include "Overture.h"
#include "HDF_DataBase.h"
#include "InterpolatePointsOnAGrid_OW3D.h"
#include "CompositeSurface.h"
#include "CompositeTopology.h"
#include "UnstructuredMapping.h"
#include "Grid.h"
#include "GLTree.h"
#include <numeric>
#include <filesystem>
#include <sys/stat.h>
#include "OW3DConstants.h"

void OW3DSeakeeping::Grid::BuildTriangulationData_()
{
  struct stat st;
  if (stat(path_to_triangulations, &st) == 0)
  {
    for (const auto &entry : std::filesystem::directory_iterator(path_to_triangulations))
    {
      // Read the hdf file containing triangulated patches

      string full_name = entry.path();
      string file_extension = full_name.substr(full_name.find_last_of('.') + 1);
      if (file_extension != "hdf")
        throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::BuildTriangulationData_.cpp.\n\t No patch data found in hdf format!", 0));
      string projection_plane = full_name.substr(full_name.find_last_of('_') + 1, 2);

      // Read the triangulations from the hdf file

      HDF_DataBase db;
      db.mount(full_name, "R");
      CompositeSurface &model = *new CompositeSurface();
      model.get(db, "Rap model");
      CompositeTopology &compositeTopology = *model.getCompositeTopology();
      UnstructuredMapping *tridat = compositeTopology.getTriangulation();
      const unsigned int numberOFNodes = tridat->getNumberOfNodes();
      RealArray nodes = tridat->getNodes();
      Range all;
      Range rg(0, 2, 1);
      const intArray &t = tridat->getElements();
      const intArray EtoV = t(all, rg);

      where(nodes(all, 2) < 0) nodes(all, 2) = 0.; // Replace small negative values with 0.
      where(nodes(all, 1) > 0) nodes(all, 1) = 0.; // Replace small positive values with 0.
      double x1 = max(nodes(all, 0));              //
      double x0 = min(nodes(all, 0));              //
      double y1 = max(nodes(all, 1));              // Important Note: y is the vertical axis
      double y0 = min(nodes(all, 1));              //
      double z1 = max(nodes(all, 2));              //
      double z0 = min(nodes(all, 2));              //

      // Map the patch on to the projection plane

      double *uv1 = new double[numberOFNodes];
      double *uv2 = new double[numberOFNodes];

      if (projection_plane == "yz")
      {
        double numer = abs(y1 - y0) > abs(z1 - z0) ? abs(y1 - y0) : abs(z1 - z0);
        double denom = abs(y1 - y0) < abs(z1 - z0) ? abs(y1 - y0) : abs(z1 - z0);
        int fac = round(numer / denom);

        for (unsigned int i = 0; i < numberOFNodes; i++)
        {
          uv1[i] = (nodes(i, 1) - y0) / (y1 - y0);
          uv2[i] = 1. / fac * (nodes(i, 2) - z0) / (z1 - z0);
        }
      }
      else if (projection_plane == "xz")
      {
        double numer = abs(x1 - x0) > abs(z1 - z0) ? abs(x1 - x0) : abs(z1 - z0);
        double denom = abs(x1 - x0) < abs(z1 - z0) ? abs(x1 - x0) : abs(z1 - z0);
        int fac = round(numer / denom);

        for (unsigned int i = 0; i < numberOFNodes; i++)
        {
          uv1[i] = (nodes(i, 0) - x0) / (x1 - x0);
          uv2[i] = 1. / fac * (nodes(i, 2) - z0) / (z1 - z0);
        }
      }
      else if (projection_plane == "xy")
      {
        double numer = abs(x1 - x0) > abs(y1 - y0) ? abs(x1 - x0) : abs(y1 - y0);
        double denom = abs(x1 - x0) < abs(y1 - y0) ? abs(x1 - x0) : abs(y1 - y0);
        int fac = round(numer / denom);

        for (unsigned int i = 0; i < numberOFNodes; i++)
        {
          uv1[i] = (nodes(i, 0) - x0) / (x1 - x0);
          uv2[i] = 1. / fac * (nodes(i, 1) - y0) / (y1 - y0);
        }
      }
      else
        throw runtime_error(GetColoredMessage("\t Error (OW3D), Grid::BuildTriangulationData_.cpp.\n\t Patch projection plane is not specified correctly.", 0));

      // Find k nearest neighbors

      int **stencil_map = new int *[numberOFNodes];
      double **distances = new double *[numberOFNodes];

      int order = 4;
      const int np = (order + 3) * (order + 3);

      for (unsigned int i = 0; i < numberOFNodes; i++)
      {
        stencil_map[i] = new int[np];
        distances[i] = new double[np];
      }

      GLTREE Tree(uv1, uv2, numberOFNodes);
      for (unsigned int i = 0; i < numberOFNodes; i++)
      {
        double pk[2];
        pk[0] = uv1[i];
        pk[1] = uv2[i];
        Tree.SearchKClosest(uv1, uv2, pk, np, stencil_map[i], distances[i]);
      }

      // Build the integration operator

      double **x = new double *[3];
      double **uv = new double *[2];
      for (unsigned int i = 0; i < 3; i++)
        x[i] = new double[numberOFNodes];
      for (unsigned int i = 0; i < 2; i++)
        uv[i] = new double[numberOFNodes];
      for (unsigned int i = 0; i < numberOFNodes; i++)
      {
        x[0][i] = nodes(i, 0);
        x[1][i] = nodes(i, 1);
        x[2][i] = nodes(i, 2);
        uv[0][i] = uv1[i];
        uv[1][i] = uv2[i];
      }

      OW3DSeakeeping::Patch patch;
      patch.nodenums = numberOFNodes;
      patch.p = 4;
      patch.np = np;
      patch.Wtype = "Gaussian";
      patch.Wmin = 0.000001;
      patch.sigma = 1.0;
      patch.nodes_xyz = nodes;
      patch.ds.resize(numberOFNodes);
      patch.Ivec.resize(numberOFNodes);
      patch.Ivec = 0.;
      patch.ds = 0.;
      patch.interp_object = new InterpolatePointsOnAGrid;
      RealArray positionToInterpolate(patch.nodenums, 3);
      positionToInterpolate(all, 0) = patch.nodes_xyz(all, 0);
      positionToInterpolate(all, 1) = patch.nodes_xyz(all, 1);
      positionToInterpolate(all, 2) = patch.nodes_xyz(all, 2);
      patch.interp_object->setNumberOfValidGhostPoints(0);
      patch.interp_object->setInterpolationWidth(patch_interpolation_width);
      patch.interp_object->buildInterpolationInfo(positionToInterpolate, cg_);
      GaussianIntegration2DWLSSetUp_(x, uv, stencil_map, EtoV, &patch);
      gridData_.triangulation.patches.push_back(patch);

      // De-allocate the memories

      for (int i = 0; i < np; i++)
      {
        delete[] stencil_map[i];
        delete[] distances[i];
      }
      delete[] stencil_map;
      delete[] distances;

      for (unsigned int i = 0; i < 3; i++)
        delete[] x[i];
      for (unsigned int i = 0; i < 2; i++)
        delete[] uv[i];

      delete[] x;
      delete[] uv;
      delete[] uv1;
      delete[] uv2;

    } // End loop over patches

    if (gridData_.triangulation.patches.size() != 0)
    {
      gridData_.triangulation.boundaries_data = gridData_.boundariesData;
      double area = CheckPatchInterpolations_();
      unsigned int mult = gridData_.halfSymmetry ? 2 : 1;
      OW3DSeakeeping::PrintLogMessage("Success in integration by triangulation. Computed submerged area = " + std::to_string(area * mult));
      PrintPatchInterpolations_();
    }

  } // End folder check
}