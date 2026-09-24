#include "SecondOrder.h"

void OW3DSeakeeping::SecondOrder::ComputeDphiDnOnBody_(
    const double &omegae,
    const double &omegao,
    const double &K,
    const int &symSign)
{

  for (unsigned int surface = 0; surface < NES_; surface++)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const vector<Index> &Is = be.surface_indices;

    MappedGrid &mg = (*cg_)[be.grid];
    const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);
    const RealArray &v = mg.vertex();

    RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
    RealArray n1(Is[0], Is[1], Is[2]), n2(Is[0], Is[1], Is[2]), n3(Is[0], Is[1], Is[2]);

    n1 = vbn(Is[0], Is[1], Is[2], axis1);
    n2 = vbn(Is[0], Is[1], Is[2], axis2); // Note : "n2" vertical up
    n3 = 0.;

    x = v(Is[0], Is[1], Is[2], axis1);
    y = v(Is[0], Is[1], Is[2], axis2); // Note : "y" vertical up
    z = 0.0;

    if (gridData_->nod == 3)
    {
      z = v(Is[0], Is[1], Is[2], axis3) * symSign;
      n3 = vbn(Is[0], Is[1], Is[2], axis3) * symSign;
    }

    RealArray alpha = x * cos(betar_) + z * sin(betar_);

    // -----------------------------------------------------------------------
    // Assign the dphi_dn_ values for this frequency (using BBC closed-form)
    // -----------------------------------------------------------------------

    if (bcsExact_) // BOTH RADIATION AND SCATTERING ARE EXACT
    {
      // REAL PART
      d_phi_dn_(0)[surface](Is[0], Is[1], Is[2]) =
          // THE RADIATION BODY BOUNDARY CONDITION.  (real part)
          mterms_.m1[surface] * xi1_re_ - omegae * n1 * xi1_im_ +
          mterms_.m2[surface] * xi2_re_ - omegae * n2 * xi2_im_ +
          mterms_.m3[surface] * xi3_re_ - omegae * n3 * xi3_im_ +
          mterms_.m4[surface] * alpha1_re_ - omegae * (n3 * (y - rCenter_[1]) - n2 * (z - rCenter_[2])) * alpha1_im_ +
          mterms_.m5[surface] * alpha2_re_ - omegae * (n1 * (z - rCenter_[2]) - n3 * (x - rCenter_[0])) * alpha2_im_ +
          mterms_.m6[surface] * alpha3_re_ - omegae * (n2 * (x - rCenter_[0]) - n1 * (y - rCenter_[1])) * alpha3_im_
          // THE SCATTERING BODY BOUNDARY CONDITION. (real part)
          - n1 * (cos(betar_) * K * g_ / omegao * cosh(K * (y + h_)) / cosh(K * h_) * cos(K * alpha)) +
          -n2 * (g_ * K / omegao * sinh(K * (y + h_)) / cosh(K * h_) * sin(K * alpha)) +
          -n3 * (sin(betar_) * K * g_ / omegao * cosh(K * (y + h_)) / cosh(K * h_) * cos(K * alpha));

      // IMAGINARY PART
      d_phi_dn_(1)[surface](Is[0], Is[1], Is[2]) =
          // THE RADIATION BODY BOUNDARY CONDITION.  (imaginary part)
          mterms_.m1[surface] * xi1_im_ + omegae * n1 * xi1_re_ +
          mterms_.m2[surface] * xi2_im_ + omegae * n2 * xi2_re_ +
          mterms_.m3[surface] * xi3_im_ + omegae * n3 * xi3_re_ +
          mterms_.m4[surface] * alpha1_im_ + omegae * (n3 * (y - rCenter_[1]) - n2 * (z - rCenter_[2])) * alpha1_re_ +
          mterms_.m5[surface] * alpha2_im_ + omegae * (n1 * (z - rCenter_[2]) - n3 * (x - rCenter_[0])) * alpha2_re_ +
          mterms_.m6[surface] * alpha3_im_ + omegae * (n2 * (x - rCenter_[0]) - n1 * (y - rCenter_[1])) * alpha3_re_
          // THE SCATTERING BODY BOUNDARY CONDITION. (imaginary part)
          - n1 * (-cos(betar_) * K * g_ / omegao * cosh(K * (y + h_)) / cosh(K * h_) * sin(K * alpha)) +
          -n2 * (g_ * K / omegao * sinh(K * (y + h_)) / cosh(K * h_) * cos(K * alpha)) +
          -n3 * (-sin(betar_) * K * g_ / omegao * cosh(K * (y + h_)) / cosh(K * h_) * cos(K * alpha));
    }
  }
}