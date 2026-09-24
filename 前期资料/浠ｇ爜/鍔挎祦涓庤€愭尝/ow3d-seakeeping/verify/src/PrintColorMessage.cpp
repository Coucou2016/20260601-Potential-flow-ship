#include "TestHeaders.h"

void OW3DSeakeepingTESTS::PrintColorMessage(std::string message, char p)
{
    if (p == 'f')
    {
        std::string temp = "\033[3;91;40m" + message + "\033[0m";
        std::cout << temp << std::endl;
    }
    if (p == 'p')
    {
        std::string temp = "\033[3;92;40m" + message + "\033[0m";
        std::cout << temp << std::endl;
    }
}
