#include "OW3DUtilFunctions.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::PrintLogMessage(string message)
{
    string log_file = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name + '/' + OW3DSeakeeping::program_name + ".log";
    ofstream lout(log_file, ios::out | ios::app);
    lout << OW3DSeakeeping::GetTimeString() << " --> " << message << '\n';
}