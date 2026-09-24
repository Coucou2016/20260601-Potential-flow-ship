#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./test11_ow3df/";
  string expected_folder = "./expected/";
  string name = "test11";

  string fE1, fA1;
  string fE2, fA2;
  string fE3, fA3;
  string fE4, fA4;
  string fE5, fA5;

  fE1 = expected_folder + name + ".o1";
  fA1 = actual_folder + name + ".o1";
  fE2 = expected_folder + name + ".o3";
  fA2 = actual_folder + name + ".o3";
  fE3 = expected_folder + name + ".o6";
  fA3 = actual_folder + name + ".o6";
  fE4 = expected_folder + name + ".rimp13";
  fA4 = actual_folder + name + ".rimp13";
  fE5 = expected_folder + name + ".simp1";
  fA5 = actual_folder + name + ".simp1";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [hydro, forward-speed (2D grid, beta=0)]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [hydro, forward-speed (2D grid, beta=0)].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 3))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rao, forward-speed (2D grid, beta=0)]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rao, forward-speed (2D grid, beta=0)].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 1))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [drift, forward-speed (2D grid, beta=0)]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [drift, forward-speed (2D grid, beta=0)].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE4, fA4, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp13, forward-speed (2D grid, beta=0)]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp13, forward-speed (2D grid, beta=0)].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE5, fA5, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [simp1, forward-speed (2D grid, beta=0)]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [simp1, forward-speed (2D grid, beta=0)].", 'p');

  if (fail)
    return 0;

  return 1;
}
