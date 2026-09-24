#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::OverrideResults(string resultsDirectory)
{
    // Note! the folder_ located at the results directory given
    // by the user, will be deleted, and a new one with the same name
    // will be created.

    string remove_folder = "rm -rf " + resultsDirectory;
    system(remove_folder.c_str());

    string create_folder = "mkdir " + resultsDirectory;
    system(create_folder.c_str());
}