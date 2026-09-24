To compare the results with the closed-form solutions from

G. Wu, Hydrodynamic forces on a submerged cylinder advancing in 
water waves of ﬁnite depth, J. Fluid Mech. 224 (1991) 645–659.

run this geometry with the variable "GX_WU_BCS = true" in the OW3DConstants.cpp

NOTE: For this example we need the results from lower frequency limit. 
      Before running ow3df, go to BuildFrequenciesAndWaveNumbers.cpp 
      and change allKsAndOmegas_.out_start_index = 1
