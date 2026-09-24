// This file imports the data objects and member functions for the Baseflow class. This class
// is meant for calculation of the base-flow data including the base-flow derivatives, velocity
// potential, elevation and mtersm. If the shape of the body is of the primitive type, then it
// is also possible to get analytical solutions for validation purpuse. Analytical base flows
// can be written as an external function and supplied through a function pointer to the object
// of this calss.
// In the constructor, all base-flow data are first initialized to zero. If we are solving
// the zero-speed problem "ZS", then all base-flow data remaine initialized to zero.
// If linearisation is of "NK" type, just meterms need to be calculated.
// If linearisation is of "DB", then the double-body flow potential need to be solved first
// by outside solver. The system right and system matrix for double body are built inside the
// constructor.

#ifndef __BASEFLOW_H__
#define __BASEFLOW_H__

#include "HDF_DataBase.h"
#include "Grid.h"

extern "C" void actvels(double *, double *, double *, double *, double *, double *);

namespace OW3DSeakeeping
{
	class Baseflow
	{
	public:
		typedef struct
		{
			vector<realArray> m1;
			vector<realArray> m2;
			vector<realArray> m3;
			vector<realArray> m4;
			vector<realArray> m5;
			vector<realArray> m6;
			vector<vector<realArray>> mf;

		} Mterms;

		typedef struct
		{
			vector<realArray> dx;
			vector<realArray> dz;

		} elevationDerivative; // just for the derivative of the base flow elevation

		typedef struct
		{
			double fx, fy, fz;
			double mx, my, mz;

		} doubleBodyForce;

		typedef struct
		{
			Mterms mterms;									// mterms
			potentialDerivative fs_derivatives;				// derivatives of the base flow potential(loop over free-surface)
			elevationDerivative elevation_derivative;		// derivatives of the base elevation
			fieldBaseDerivative DerivativesOnCompositeGrid; // derivatives of the base-flow over the whole domain
			realCompositeGridFunction elevation;			// the base flow elevation
			realCompositeGridFunction potential;			// the base flow potential
			doubleBodyForce dbForces;
			vector<SideDervs> BodySurfaceDerivatives;
			vector<SideDervs> FreeSurfaceDerivatives;
			realArray speed_hydrostatics;

		} baseFlowData;

		Baseflow(
			CompositeGrid &,
			const OW3DSeakeeping::Grid::GridData &,
			CompositeGridOperators &,
			Interpolant &); // constructor

		~Baseflow();

		realCompositeGridFunction &GetPotential();

		const baseFlowData *ExtractBaseflowData(); // Returns all required data for the desired base flow

		realCompositeGridFunction &GetSystemRight();  // Returns system right for double body flow
		realCompositeGridFunction &GetSystemMatrix(); // Return system matrix prepared for double body flow

	private:
		double g_;
		baseFlowData data_;						  // All data for a base flow
		potentialDerivative derivative_on_body_;  // Based on loop over exciting surface (needed just for calculating computational mterms)
		Interpolant interpolant_;				  // Needed for calculation of the double body elevation
		realCompositeGridFunction system_matrix_; // To solve double body flow (should be supplied to the solver object outside)
		realCompositeGridFunction system_right_;  // To solve double body flow (should be supplied to the solver object outside)
		bool calcBaseElev_;						  // true if the double-body elevation should be calculated
												  // Computing the double-body m-terms using a B-spline based panel method (IWWWFB11)
		string resultsDirectory_;
		CompositeGrid *cg_;
		const OW3DSeakeeping::Grid::GridData *gridData_;
		const All_boundaries_data *boundariesData_;
		string base_show_file_;
		string base_elevation_file_;
		string base_dervs_free_file_;
		string base_dervs_body_file_;
		string mterms_file_;
		string data_base_file_;
		string base_force_file_;
		string base_pressure_showfile_;

		HDF_DataBase dataBase_; // To save base-flow data in hdf file to be used by POST module.

		realCompositeGridFunction M1_, M2_, M3_; // To save base-flow data in hdf file to be used by POST module.
		realCompositeGridFunction M4_, M5_, M6_; // To save base-flow data in hdf file to be used by POST module.
		vector<realCompositeGridFunction> MF_;	 // To save base-flow data in hdf file to be used by POST module.

		realCompositeGridFunction db_pressure_on_body_;

		realCompositeGridFunction analytical_elevation_;

		// private data objects related to thrust deduction

		bool build_act_vels_;

		vector<realArray> act_body_velocity_ux_;
		vector<realArray> act_body_velocity_uy_;
		vector<realArray> act_body_velocity_uz_;

		void BuildBaseflowSystemMatrix_(
			const OW3DSeakeeping::Grid::Boundary_integers &,
			CompositeGridOperators &);

		void BuildBaseflowSystemRight_();

		void ComputeDoublebodyElevation_(
			realCompositeGridFunction &,
			const realCompositeGridFunction &,
			const realCompositeGridFunction &,
			const realCompositeGridFunction &); // calculates the double body elevation
		int FindDoublebodyElevation_(
			const int &, const int &, const int &,
			const int &, const int &, const int &,
			const realCompositeGridFunction &,
			const realArray &,
			const int &, const int &,
			realCompositeGridFunction &);

		void PrintBaseFlowElevation_(
			const realCompositeGridFunction &,
			const string &) const;

		void PrintBaseFlowDerivatives_(
			const potentialDerivative &,
			const elevationDerivative &,
			const string &);

		void ComputeBaseDerivativesOnSurface_(
			potentialDerivative &,
			const Single_boundary_data &,
			int, // surface index
			bool scheme_option);

		void ComputeBaseflowElevationDerivatives_(
			const realCompositeGridFunction &,
			elevationDerivative &);

		void ComputeMTerms_(
			const potentialDerivative &,
			Mterms &);

		void ComputeDoublebodyForces_();

		void PrintMTerms_(
			const Mterms &,
			const string &);

		void PrintAnalyticalDoublebody_(
			vector<double>,
			analyticalData (*pf)(CompositeGrid &, const All_boundaries_data &, vector<double>, double));

		void SearchElevation_1_2_0_(
			string,
			int,
			const vector<Index> &,
			const vector<Index> &,
			const MappedGrid &,
			const Single_boundary_data &,
			const realCompositeGridFunction &,
			const realCompositeGridFunction &,
			realCompositeGridFunction &);

		void SearchElevation_0_2_1_(
			string,
			int,
			const vector<Index> &,
			const vector<Index> &,
			const MappedGrid &,
			const Single_boundary_data &,
			const realCompositeGridFunction &,
			const realCompositeGridFunction &,
			realCompositeGridFunction &);

		void SearchElevation_0_1_2_(
			string,
			int,
			const vector<Index> &,
			const vector<Index> &,
			const MappedGrid &,
			const Single_boundary_data &,
			const realCompositeGridFunction &,
			const realCompositeGridFunction &,
			realCompositeGridFunction &);

		double Findroot_(const vector<double> &, const vector<double> &, const vector<double> &);
		void Polcoe_(const vector<double> &, const vector<double> &, vector<double> &);
		void Poleval_(double *p, const vector<double> &, const double &);

		void PrintBaseFlowDerivativesBody_(const string &filename);
		void PrintDoubleBodyForces_();
		void ComputeForwardSpeedHydrostatics_();

		// private member functions related to thrust deduction

		void CheckDoublebodyBoundaryCondition_();
		void ComputeActBodyVelocities_();
	};

}

#endif