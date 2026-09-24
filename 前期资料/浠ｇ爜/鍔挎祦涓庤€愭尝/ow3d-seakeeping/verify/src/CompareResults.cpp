#include "TestHeaders.h"

int OW3DSeakeepingTESTS::CompareResults(std::string SExpected, std::string SActual, double pres, unsigned int skip)
{
  std::ifstream foutE(SExpected), foutA(SActual);
  if (foutE.is_open() && foutA.is_open())
  {
    for (unsigned int i = 0; i < skip; i++)
    {
      std::string headers;
      getline(foutE, headers);
      getline(foutA, headers);
    }
    std::string lineE, lineA;
    while (std::getline(foutE, lineE) && std::getline(foutA, lineA))
    {
      std::istringstream issE(lineE), issA(lineA);
      std::string sa = issA.str();
      std::string se = issE.str();
      std::size_t nanA_found = sa.find("nan");
      std::size_t nanE_found = se.find("nan");
      if (nanE_found != nanA_found)
        return 0;
      double resE, resA;
      std::vector<double> avec;
      std::vector<double> evec;
      while (issE >> resE && issA >> resA)
      {
        avec.push_back(resA);
        evec.push_back(resE);
      }
      for (unsigned int i = 0; i < avec.size(); i++)
      {
        if (std::abs(avec[i] - evec[i]) > pres)
        {
          foutE.close();
          foutA.close();
          return 0;
        }
      }
      avec.clear();
      evec.clear();
    }
    foutE.close();
    foutA.close();
    if (!lineA.size())
      return 0;
  }
  else
  {
    std::cout << "ERROR, OW3DSeakeepingTESTS::CompareResults.cpp:: Expected or Actual files can't be opened." << std::endl;
    return 0;
  }
  return 1;
}
