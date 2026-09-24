#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./test05_ow3df/";
  string expected_folder = "./expected/";
  string name = "test05";

  string fE1, fA1;
  string fE2, fA2;
  string fE3, fA3;
  string fE4, fA4;
  string fE5, fA5;
  string fE6, fA6;

  fE1 = expected_folder + name + ".o1";
  fA1 = actual_folder + name + ".o1";
  fE2 = expected_folder + name + ".o2";
  fA2 = actual_folder + name + ".o2";
  fE3 = expected_folder + name + ".o3";
  fA3 = actual_folder + name + ".o3";
  fE4 = expected_folder + name + ".rimp36";
  fA4 = actual_folder + name + ".rimp36";
  fE5 = expected_folder + name + ".rimp66";
  fA5 = actual_folder + name + ".rimp66";
  fE6 = expected_folder + name + ".simp6";
  fA6 = actual_folder + name + ".simp6";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 3))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [hydro, zero-speed, beta=35]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [hydro, zero-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [wave force, zero-speed, beta=35]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [wave force, zero-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 4))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rao, zero-speed, beta=35]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rao, zero-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE4, fA4, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp36, zero-speed, beta=35] <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp36, zero-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE5, fA5, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [rimp66, zero-speed, beta=35] <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [rimp66, zero-speed, beta=35].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE6, fA6, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [simp6, zero-speed, beta=35] <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [simp6, zero-speed, beta=35].", 'p');

  if (fail)
    return 0;

  return 1;
}
