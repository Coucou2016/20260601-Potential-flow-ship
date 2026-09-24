#include "OW3DUtilFunctions.h"

string OW3DSeakeeping::GetTimeString()
{
    time_t tm = time(NULL);
    struct tm *now = localtime(&tm);
    string date_time = asctime(now);
    date_time.erase(std::remove(date_time.begin(), date_time.end(), '\n'), date_time.end());
    return date_time;
}