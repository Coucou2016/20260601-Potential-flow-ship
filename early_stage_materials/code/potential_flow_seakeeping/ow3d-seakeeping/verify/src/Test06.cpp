#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./test06_ow3df/";
  string expected_folder = "./expected/";
  string name = "test06";

  string fE1, fA1;
  string fE2, fA2;
  string fE3, fA3;
  string fE4, fA4;
  string fE5, fA5;
  string fE6, fA6;

  fE1 = expected_folder + name + ".o3";
  fA1 = actual_folder + name + ".o3";
  fE2 = expected_folder + name + ".o2";
  fA2 = actual_folder + name + ".o2";
  fE3 = expected_folder + name + ".rimp11";
  fA3 = actual_folder + name + ".rimp11";
  fE4 = expected_folder + name + ".simp5";
  fA4 = actual_folder + name + ".simp5";
  fE5 = expected_folder + name + ".rimp64";
  fA5 = actual_folder + name + ".rimp64";
  fE6 = expected_folder + name + ".simp3";
  fA6 = actual_folder + name + ".simp3";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rao, forward-speed, beta=35]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rao, forward-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [wave force, forward-speed, beta=35]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [wave force, forward-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp11, forward-speed, beta=35]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp11, forward-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE4, fA4, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [simp5, forward-speed, beta=35] <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [simp5, forward-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE5, fA5, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp64, forward-speed, beta=35] <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp64, forward-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE6, fA6, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [simp3, forward-speed, beta=35] <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [simp3, forward-speed, beta=35].", 'p');

  if (fail)
    return 0;

  return 1;
}
