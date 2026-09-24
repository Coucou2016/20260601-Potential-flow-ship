// This public member function belongs to the FreeSurface class, and just for
// the sake of convenience is written in a seperate file.

#include "FreeSurface.h"

void OW3DSeakeeping::FreeSurface::StoreWaterlineElevations()
{
	double eta; // the data will be printed via this variable

	ofstream fout(wlinesFileName_, ios_base::out | ios_base::app | ios_base::binary);

	for (unsigned int line = 0; line < gridData_->wlData.size(); line++)
	{
		int grid = gridData_->wlData[line].grid;

		for (int i = 0; i < gridData_->wlData[line].size; i++)
		{
			if (gridData_->wlData[line].direction == 0)
			{
				eta = freeSurface_.solution_start.elevation[grid](i, gridData_->wlData[line].I1.getBase(), gridData_->wlData[line].I2.getBase());
			}
			else if (gridData_->wlData[line].direction == 1)
			{
				eta = freeSurface_.solution_start.elevation[grid](gridData_->wlData[line].I0.getBase(), i, gridData_->wlData[line].I2.getBase());
			}
			else
			{
				eta = freeSurface_.solution_start.elevation[grid](gridData_->wlData[line].I0.getBase(), gridData_->wlData[line].I1.getBase(), i);
			}

			fout.write((char *)&eta, sizeof eta);

		} // End of loop over the points on this water line

	} // End of loop over waterline free surfaces

	fout.close();
}

// note : the functin stores the binary data for each water line as follows: [run][t][line][i]
//
// run[0]
// ------
// t[0]
// ------
// line[0]
// ------
// i=0 i=1 i=2 ...
//
