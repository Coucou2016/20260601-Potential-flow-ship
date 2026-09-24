// This public member function belongs to the Field class, and just for
// the sake of convenience is written in a seperate file.

#include "Field.h"

void OW3DSeakeeping::Field::StoreBodyPotentials()
{
	double phi, phix, phiy, phiz, phixx, phiyy, phizz, phixy, phixz, phiyz;

	ofstream fout(potentialsFileName_, ios_base::out | ios_base::app | ios_base::binary);

	for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
	{
		const Single_boundary_data &be = boundariesData_->exciting[surface];
		const vector<Index> &Is = be.surface_indices;

		for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
		{
			for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
			{
				for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
				{
					phi = phiu_on_body_[surface](i, j, k); // 0

					phix = d_phiu_dx_on_body_[surface](i, j, k); // 1
					phiy = d_phiu_dy_on_body_[surface](i, j, k); // 2
					phiz = d_phiu_dz_on_body_[surface](i, j, k); // 3

					phixx = d_phiu_dxx_on_body_[surface](i, j, k); // 4
					phiyy = d_phiu_dyy_on_body_[surface](i, j, k); // 5
					phizz = d_phiu_dzz_on_body_[surface](i, j, k); // 6
					phixy = d_phiu_dxy_on_body_[surface](i, j, k); // 7
					phixz = d_phiu_dxz_on_body_[surface](i, j, k); // 8
					phiyz = d_phiu_dyz_on_body_[surface](i, j, k); // 9

					fout.write((char *)&phi, sizeof phi);

					fout.write((char *)&phix, sizeof phix);
					fout.write((char *)&phiy, sizeof phiy);
					fout.write((char *)&phiz, sizeof phiz);

					fout.write((char *)&phixx, sizeof phixx);
					fout.write((char *)&phiyy, sizeof phiyy);
					fout.write((char *)&phizz, sizeof phizz);
					fout.write((char *)&phixy, sizeof phixy);
					fout.write((char *)&phixz, sizeof phixz);
					fout.write((char *)&phiyz, sizeof phiyz);
				}
			}
		}

	} // End of loop over surfaces

	fout.close();
}

// Note : The above function stores the binary data as follows: [run][t][surface][i][j][k][h]
//
//  run[0]
//  ------
//  t[0]
//  ------
//  surface[0]
//  ------
//  i=0
//  ------
//  j=0
//  ------
//  k=0
//  ------------------------------------------------------
//  phi phix phiy phiz phixx phiyy phizz phixy phixz phiyz
//
