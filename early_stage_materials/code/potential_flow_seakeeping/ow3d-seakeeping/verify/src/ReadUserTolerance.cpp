#include "TestHeaders.h"

double OW3DSeakeepingTESTS::ReadUserTolerance(int argc, char *argv[])
{
    double pres = 1e-9;
    if (argc == 2)
    {
        std::string pres_arg = argv[1];
        std::size_t index = pres_arg.find('=');
        if (index != std::string::npos)
        {
            std::string pres_string = pres_arg.substr(index + 1);
            pres = std::stod(pres_string);
        }
    }
    printf("!! Just for your information: The tests are performed with precision %.1e\n", pres);
    return pres;
}