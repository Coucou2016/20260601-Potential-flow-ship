#include "TestHeaders.h"

using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./test04_ow3df/";
  string expected_folder = "./expected/";
  string name = "test04";

  string fE1, fA1;
  string fE2, fA2;
  string fE3, fA3;

  fE1 = expected_folder + name + ".wimp1";
  fA1 = actual_folder + name + ".wimp1";
  fE2 = expected_folder + name + ".wimp3";
  fA2 = actual_folder + name + ".wimp3";
  fE3 = expected_folder + name + ".wimp5";
  fA3 = actual_folder + name + ".wimp5";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [Wave resistance, wimp1]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [Wave resistance,wimp1].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [Wave resistance, wimp3]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [Wave resistance, wimp3].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 2))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dseakeeping test failed: [Wave resistance, wimp5]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dseakeeping test passed: [Wave resistance, wimp5].", 'p');

  if (fail)
    return 0;

  return 1;
}
