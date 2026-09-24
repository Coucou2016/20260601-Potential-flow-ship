#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./test08_ow3df/";
  string expected_folder = "./expected/";
  string name = "test08";

  string fE1, fA1;
  string fE2, fA2;
  string fE3, fA3;
  string fE4, fA4;
  string fE5, fA5;

  fE1 = expected_folder + name + ".o3";
  fA1 = actual_folder + name + ".o3";
  fE2 = expected_folder + name + ".o6";
  fA2 = actual_folder + name + ".o6";
  fE3 = expected_folder + name + ".o5";
  fA3 = actual_folder + name + ".o5";
  fE4 = expected_folder + name + ".rimp33";
  fA4 = actual_folder + name + ".rimp33";
  fE5 = expected_folder + name + ".rimp45";
  fA5 = actual_folder + name + ".rimp45";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 3))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rao, forward-speed, beta=155]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rao, forward-speed, beta=155].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [drift, forward-speed, beta=155]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [drift, forward-speed, beta=155].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [Froude-Krylov, forward-speed, beta=155]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [Froude-Krylov, forward-speed, beta=155].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE4, fA4, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp33, forward-speed, beta=155]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp33, forward-speed, beta=155].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE5, fA5, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp45, forward-speed, beta=155]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp45, forward-speed, beta=155].", 'p');

  if (fail)
    return 0;

  return 1;
}
