#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./test13_ow3df/";
  string expected_folder = "./expected/";
  string name = "test13";

  string fE1, fA1;
  string fE2, fA2;
  string fE3, fA3;
  string fE4, fA4;

  fE1 = expected_folder + name + ".o3";
  fA1 = actual_folder + name + ".o3";
  fE2 = expected_folder + name + ".o6";
  fA2 = actual_folder + name + ".o6";
  fE3 = expected_folder + name + ".rimp53";
  fA3 = actual_folder + name + ".rimp53";
  fE4 = expected_folder + name + ".simp1";
  fA4 = actual_folder + name + ".simp1";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 4))
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

  if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp53, forward-speed, beta=155]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp53, forward-speed, beta=155].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE4, fA4, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [simp1, forward-speed, beta=155]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [simp1, forward-speed, beta=155].", 'p');

  if (fail)
    return 0;

  return 1;
}
