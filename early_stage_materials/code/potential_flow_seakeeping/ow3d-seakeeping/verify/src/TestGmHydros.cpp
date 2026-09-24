#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./gmhydro_ow3df/";
  string expected_folder = "./expected/";
  string name = "gmhydro";

  string fE1, fA1;
  string fE2, fA2;

  fE1 = expected_folder + name + ".o3";
  fA1 = actual_folder + name + ".o3";
  fE2 = expected_folder + "grid.o6";
  fA2 = actual_folder + "grid.o6";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rao, forward-speed (gmode), beta=130]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rao, forward-speed (gmode), beta=130].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 12))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [hydrostatic coefficients (gmode)]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [hydrostatic coefficients (gmode)].", 'p');

  if (fail)
    return 0;

  return 1;
}
