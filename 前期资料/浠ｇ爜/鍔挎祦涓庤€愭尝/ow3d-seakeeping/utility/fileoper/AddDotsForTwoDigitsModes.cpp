#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::AddDotsForTwoDigitsModes(string &i, string &j)
{
  i.erase(remove(i.begin(), i.end(), '.'), i.end());
  j.erase(remove(j.begin(), j.end(), '.'), j.end());
  i = (i.length() == 2 || j.length() == 2) ? i + '.' : i;
}