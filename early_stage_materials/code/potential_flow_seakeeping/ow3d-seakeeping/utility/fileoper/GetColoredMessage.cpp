#include "OW3DUtilFunctions.h"
#include "OW3DConstants.h"

string OW3DSeakeeping::GetColoredMessage(string message, bool fail_pass)
{
    return (fail_pass) ? "\033[3;92;40m" + message + "\033[0m" : "\033[3;91;40m" + message + "\033[0m";
}