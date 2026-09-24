#ifndef __UTILITY__FUNCTIONS__
#define __UTILITY__FUNCTIONS__

#include "Integrate.h"
#include "InterpolatePointsOnAGrid.h"
#include "ComplexNumbers.h"
#include "ComplexArray.h"
#include <valarray>

namespace OW3DSeakeeping
{
	double Dispersion(double, void *);
	double DispersionDeep(double, void *);
	double FSK0limFunction(double, void *);
	double FSK01Function(double, void *);
	double FSK02Function(double, void *);
	double FSK03Function(double, void *);

	CompositeGridOperators DefineOperators(CompositeGrid &, const int);
	RealArray CalculateFirstCoefficients(const int, string boundary = "os");
	// By default the coefficients are computaed for an extrapolation at the boundaries (one-sided scheme, "os")
	// + Use "lnm", "rnm" to chnage the coefficients for a homogeneous neumann boundary (symmetry condition) at left or right
	// + Use "ldr", "rdr" to chnage the coefficients for a homogeneous dirichlet boundary (anti-symmetry condition) at left or right
	// Note: Implementation is only for 2nd and 4th order
	RealArray CalculateCoefficients(const double, const RealArray &, const int);

	string DoubleToString(const double &);
	void Savgol(double *, const int, const int, const int, const int, const int);
	analyticalData CylinderDoublebody(CompositeGrid &, const All_boundaries_data &, vector<double>, double);
	analyticalData SphereDoublebody(CompositeGrid &, const All_boundaries_data &, vector<double>, double);
	vector<double> FindBodyGeometry(CompositeGrid &, const All_boundaries_data &);
	void Comperrf(double, double, double &, double &);

	int expb_f(const gsl_vector *, void *, gsl_vector *);
	int expb_df(const gsl_vector *, void *, gsl_matrix *);
	int expb_fdf(const gsl_vector *, void *, gsl_vector *, gsl_matrix *);
	int t_n_sine_cosine_f(const gsl_vector *, void *, gsl_vector *);
	int t_n_sine_cosine_df(const gsl_vector *, void *, gsl_matrix *);
	int t_n_sine_cosine_fdf(const gsl_vector *, void *, gsl_vector *, gsl_matrix *);
	int t_n_sine_cosine_pc_f(const gsl_vector *, void *, gsl_vector *);
	int t_n_sine_cosine_pc_df(const gsl_vector *, void *, gsl_matrix *);
	int t_n_sine_cosine_pc_fdf(const gsl_vector *, void *, gsl_vector *, gsl_matrix *);

	void leastSquareFitting(int (*pf)(const gsl_vector *, void *, gsl_vector *), int (*pdf)(const gsl_vector *, void *, gsl_matrix *),
							int (*pfdf)(const gsl_vector *, void *, gsl_vector *, gsl_matrix *), least_square_data, vector<double> &, string);

	RealArray FdCoefficients(unsigned int, unsigned int, int);
	RealArray FdAllCoefficients(unsigned int, unsigned int);

	void SetFreeSurfaceGhostPoints(const CompositeGrid &, const All_boundaries_data &, realCompositeGridFunction &, realCompositeGridFunction &, const double &, const double &);

	double Wavenumber(double omega, double depth, double mwl, double beta, double U, double g, double bound = 10000);
	double WavenumberDeep(double omega, double depth, double mwl, double beta, double U, double g, double bound = 10000);
	double GetFSK0lim(double omega, double depth, double mwl, double beta, double U, double g, double bound = 10000);
	double GetFSK01(double omega, double depth, double mwl, double beta, double U, double g, double bound = 10000);
	double GetFSK02(double omega, double depth, double mwl, double beta, double U, double g, double bound = 10000);
	double GetFSK03(double omega, double depth, double mwl, double beta, double U, double g, double bound = 10000);
	void incidentWavePressure(vector<RealArray> &resy, vector<RealArray> &imsy, vector<RealArray> &reas, vector<RealArray> &imas, const RealArray &x, const RealArray &y, const RealArray &z, void *);
	void incidentWaveDphiDx(vector<RealArray> &resy, vector<RealArray> &imsy, vector<RealArray> &reas, vector<RealArray> &imas, const RealArray &x, const RealArray &y, const RealArray &z, void *);
	void incidentWaveDphiDy(vector<RealArray> &resy, vector<RealArray> &imsy, vector<RealArray> &reas, vector<RealArray> &imas, const RealArray &x, const RealArray &y, const RealArray &z, void *);
	void incidentWaveDphiDz(vector<RealArray> &resy, vector<RealArray> &imsy, vector<RealArray> &reas, vector<RealArray> &imas, const RealArray &x, const RealArray &y, const RealArray &z, void *);

	Integrate GetIntegratorOverBody(CompositeGrid &, const All_boundaries_data &);
	double FindShortest(const Coordinate &point, const vector<Coordinate> &allPoints);
	double IntegrateLineData(int size, double *f, double dl, const RealArray &C, const vector<RealArray> &Cleft, const vector<RealArray> &Cright);
	double IntegrateLineData(vector<double> f, vector<double> dl, const RealArray &C, const vector<RealArray> &Cleft, const vector<RealArray> &Cright);
	double IntegrateLineDataLo(int size, double *f, double dl, const RealArray &C, const vector<RealArray> &Cleft, const vector<RealArray> &Cright);
	double IntegrateLineDataBo(int size, double *f, double dl, const RealArray &C, const vector<RealArray> &Cleft, const vector<RealArray> &Cright);

	void ComputeSurfaceDerivatives(const FundamentalForms &, const vector<vector<DiscRanges>> &surface_ranges, RealArray &f, RealArray &fn, SideDervs &Dervs, char mode_type = 's');
	void ComputeSurfaceDerivatives(const FundamentalForms &, RealArray &F, RealArray &Fn, SideDervs &Dervs);
	void PrintSurfaceDerivatives(const RealArray &x, const RealArray &y, const RealArray &z, const SideDervs &Dervs, string filename);
	void PrintSurfaceDerivatives(const CompositeGrid &cg, const vector<Single_boundary_data> boundaries_data, const potentialDerivative &Dervs, string filename, bool sub = 1);
	void Compute1DDerivatives(const RealArray &f, RealArray &df, int si, int ei, const RealArray &coefficients, Range range = Range());
	void PrintGslMatrix(const gsl_matrix *M);
	void PrintGslMatrix(const gsl_matrix_complex *M);
	void PrintGslVector(const gsl_vector *V);
	double ComputeIntegralByTriangulation(RealCompositeGridFunction &u, const TriangulationData &);
	double ComputeSurfaceIntegral(Integrate &integrator, const TriangulationData &, realCompositeGridFunction &u);

	double FindCriticalDepth(double omega, double h, double mwl, double beta, double U, double g, double bound);
	double DepthCriticalFunction(double k, void *params);

	void FdCf(int A, int B, int size, double *x, double ***C, int **ab);
	void LagrangeInterpolation(int n, double *x, double p, double *c);
	void OverrideResults(string resultsDirectory);
	string GetTimeString();
	void PrintLogMessage(string message);
	string GetColoredMessage(string message, bool fail_pass);

	void AddDotsForTwoDigitsModes(string &i, string &j);

	void ExtrapolateSurfaceBoundaries(realCompositeGridFunction &u, std::vector<Single_boundary_data> bdata);

	template <typename T>
	vector<T> veccat(const vector<T> &ls, const vector<T> &rs)
	{
		vector<T> result;

		for (unsigned int i = 0; i < ls.size(); i++)
			result.push_back(ls[i]);

		for (unsigned int j = 0; j < rs.size(); j++)
			result.push_back(rs[j]);

		return result;
	}
}
#endif