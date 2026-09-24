#include "TestHeaders.h"

using namespace std;

int main(int argc, char *argv[])
{
  double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
  string actual_folder = "./dervs_ow3dt";
  string expected_folder = "./expected";

  string fE1_b, fA1_b;
  string fE2_b, fA2_b;

  string fE1_f, fA1_f;
  string fE2_f, fA2_f;

  fE1_b = expected_folder + "/allDervs.txt";
  fA1_b = actual_folder + "/allDervs.txt";
  fE2_b = expected_folder + "/patchDervs.txt";
  fA2_b = actual_folder + "/patchDervs.txt";

  fE1_f = expected_folder + "/allDervs_f.txt";
  fA1_f = actual_folder + "/allDervs_f.txt";
  fE2_f = expected_folder + "/patchDervs_f.txt";
  fA2_f = actual_folder + "/patchDervs_f.txt";

  bool fail = false;

  if (!OW3DSeakeepingTESTS::CompareResults(fE1_b, fA1_b, pres))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dd test failed: [derivative on the body using all points]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dd test passed: [derivative on the body using all points].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2_b, fA2_b, pres))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dd test failed: [derivative on the body using physical points] <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dd test passed: [derivative on the body using physical points]", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE1_f, fA1_f, pres))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dd test failed: [derivative on the free surface using all points]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dd test passed: [derivative on the free surface using all points].", 'p');

  if (!OW3DSeakeepingTESTS::CompareResults(fE2_f, fA2_f, pres))
  {
    OW3DSeakeepingTESTS::PrintColorMessage("========> ow3dd test failed: [derivative on the free surface using physical points]. <========", 'f');
    fail = true;
  }
  else
    OW3DSeakeepingTESTS::PrintColorMessage("** ow3dd test passed: [derivative on the free surface using physical points].", 'p');

  if (fail)
    return 0;

  return 1;
}