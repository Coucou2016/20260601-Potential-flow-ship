#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./baseflow_ow3dt";
  string expected_folder = "./expected";

  string fE1, fA1;
  string fE2, fA2;
  string fE3, fA3;
  string fE4, fA4;

  fE1 = expected_folder + "/base.o1";
  fA1 = actual_folder + "/base.o1";
  fE2 = expected_folder + "/base.o2";
  fA2 = actual_folder + "//base.o2";
  fE3 = expected_folder + "/base.o3";
  fA3 = actual_folder + "/base.o3";
  fE4 = expected_folder + "/base.o4";
  fA4 = actual_folder + "/base.o4";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 1))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [double-body m-terms]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [double-body m-terms].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 1))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [double-body derivatives at the free-surface]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [double-body derivatives at the free-surface].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 1))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [double-body derivatives at the body]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [double-body derivatives at the body].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE4, fA4, pres, 1))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [double-body elevation]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [double-body elevation].", 'p');

  if (fail)
    return 0;

  return 1;
}