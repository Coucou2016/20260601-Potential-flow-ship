#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
    double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
    string actual_folder = "./upwind_ow3dt";
    string expected_folder = "./expected";
    string fE1, fA1;
    string fE2, fA2;
    string fE3, fA3;
    fE1 = expected_folder + "/neumann_hom_body.txt";
    fA1 = actual_folder + "/neumann_hom_body.txt";
    fE2 = expected_folder + "/neumann_nhom_body.txt";
    fA2 = actual_folder + "/neumann_nhom_body.txt";
    fE3 = expected_folder + "/neumann_varbx_body.txt";
    fA3 = actual_folder + "/neumann_varbx_body.txt";
    string fE4, fA4;
    string fE5, fA5;
    string fE6, fA6;
    fE4 = expected_folder + "/neumann_hom_wall.txt";
    fA4 = actual_folder + "/neumann_hom_wall.txt";
    fE5 = expected_folder + "/neumann_nhom_wall.txt";
    fA5 = actual_folder + "/neumann_nhom_wall.txt";
    fE6 = expected_folder + "/neumann_varbx_wall.txt";
    fA6 = actual_folder + "/neumann_varbx_wall.txt";
    string fE7, fA7;
    string fE8, fA8;
    fE7 = expected_folder + "/updervs_dx.txt";
    fA7 = actual_folder + "/updervs_dx.txt";
    fE8 = expected_folder + "/updervs_dz.txt";
    fA8 = actual_folder + "/updervs_dz.txt";

    bool fail = false;

    if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [neumann hom. on body]. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [neumann hom. on body].", 'p');

    if (!OW3DSeakeepingTESTS::CompareResults(fE2, fA2, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [neumann non hom. on body]. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [neumann non hom. on body].", 'p');

    if (!OW3DSeakeepingTESTS::CompareResults(fE3, fA3, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [neumann non hom. var. on body]. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [neumann non hom. var. on body].", 'p');

    // ---------------

    if (!OW3DSeakeepingTESTS::CompareResults(fE4, fA4, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [neumann hom. on wall]. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [neumann hom. on wall].", 'p');

    if (!OW3DSeakeepingTESTS::CompareResults(fE5, fA5, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [neumann non hom. on wall]. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [neumann non hom. on wall].", 'p');

    if (!OW3DSeakeepingTESTS::CompareResults(fE6, fA6, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [neumann non hom. var. on wall]. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [neumann non hom. var. on wall].", 'p');

    if (!OW3DSeakeepingTESTS::CompareResults(fE7, fA7, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [upwind x- derivatives]. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [upwind x- derivatives].", 'p');

    if (!OW3DSeakeepingTESTS::CompareResults(fE8, fA8, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping test failed: [upwind z- derivatives]. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping test passed: [upwind z- derivatives].", 'p');

    if (fail)
        return 0;

    return 1;
}