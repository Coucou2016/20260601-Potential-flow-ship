#include "TestHeaders.h"
using namespace std;

int main(int argc, char *argv[])
{
    double pres = OW3DSeakeepingTESTS::ReadUserTolerance(argc, argv);
    string actual_folder = "./filter_ow3dt";
    string expected_folder = "./expected";
    string fE1, fA1;
    fE1 = expected_folder + "/filtered.txt";
    fA1 = actual_folder + "/filtered.txt";

    bool fail = false;

    if (!OW3DSeakeepingTESTS::CompareResults(fE1, fA1, pres, 1))
    {
        OW3DSeakeepingTESTS::PrintColorMessage("========> OW3DSakeeping Filter class test failed. <========", 'f');
        fail = true;
    }
    else
        OW3DSeakeepingTESTS::PrintColorMessage("** OW3DSakeeping Filter class test passed.", 'p');

    if (fail)
        return 0;

    return 1;
}