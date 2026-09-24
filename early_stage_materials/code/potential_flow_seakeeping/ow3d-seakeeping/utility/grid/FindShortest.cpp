#include "OW3DUtilFunctions.h"

double OW3DSeakeeping::FindShortest(
    const Coordinate &point,
    const vector<Coordinate> &allPoints)
{
  vector<double> sh;

  for (unsigned int i = 0; i < allPoints.size(); i++)
  {
    sh.push_back(sqrt(pow(point.x - allPoints[i].x, 2) + pow(point.z - allPoints[i].z, 2)));
  }

  return *(min_element(sh.begin(), sh.end()));
}
