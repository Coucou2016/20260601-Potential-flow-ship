#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./test09_ow3df/";
  string expected_folder = "./expected/";
  string name = "test09";

  string fE1, fA1;
  string fE2, fA2;
  string fE3, fA3;
  string fE4, fA4;
  string fE5, fA5;
  string fE6, fA6;

  fE1 = expected_folder + name + ".o3";
  fA1 = actual_folder + name + ".o3";
  fE2 = expected_folder + name + ".o1";
  fA2 = actual_folder + name + ".o1";
  fE3 = expected_folder + name + ".simp8";
  fA3 = actual_folder + name + ".simp8";
  fE4 = expected_folder + name + ".rimp83";
  fA4 = actual_folder + name + ".rimp83";
  fE5 = expected_folder + name + ".rimp87";
  fA5 = actual_folder + name + ".rimp87";
  fE6 = expected_folder + name + ".o8";
  fA6 = actual_folder + name + ".o8";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rao, forward-speed (gmode), beta=130]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rao, forward-speed (gmode), beta=130].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 3))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [hydro, forward-speed (gmode), beta=130]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [hydro, forward-speed (gmode), beta=130].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [simp8, forward-speed (gmode), beta=130]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [simp8, forward-speed (gmode), beta=130].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE4, fA4, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp83, forward-speed (gmode), beta=130]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp83, forward-speed (gmode), beta=130].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE5, fA5, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp87, forward-speed (gmode), beta=130]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp87, forward-speed (gmode), beta=130].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE6, fA6, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [displacement, forward-speed (gmode), beta=130]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [displacement, forward-speed (gmode), beta=130].", 'p');

  if (fail)
    return 0;

  return 1;
}
