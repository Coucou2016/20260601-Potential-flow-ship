#include "OW3DUtilFunctions.h"

string OW3DSeakeeping::DoubleToString(const double &time)

{
  string str = "";
  ostringstream os(str);
  os << time;
  return os.str();
}
