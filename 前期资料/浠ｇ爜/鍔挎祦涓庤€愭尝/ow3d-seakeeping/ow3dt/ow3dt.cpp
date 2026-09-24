#include "Solver.h"
#include "Field.h"
#include "FreeSurface.h"
#include "OW3DConstants.h"

const string OW3DSeakeeping::program_name = "ow3dt";

int main(int argc, char *argv[])
try
{
	Overture::start(argc, argv);
	INIT_PETSC_SOLVER();

	OW3DSeakeeping::OverrideResults(OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name);
	OW3DSeakeeping::PrintLogMessage("Program started.");
	vector<OW3DSeakeeping::HydrodynamicProblem> runs = OW3DSeakeeping::UserInput.all_runs;
	OW3DSeakeeping::Grid grid;
	CompositeGrid &cg = *grid.GetTheGrid();
	OW3DSeakeeping::Grid::GridData gridData = grid.GetGridData();

	bool no_run = OW3DSeakeeping::UserInput.ires == 0 && OW3DSeakeeping::UserInput.irad == 0 && OW3DSeakeeping::UserInput.idif == 0;
	if (no_run)
		grid.ComputeHydrostatics();

	grid.PrintGridFeatures();
	OW3DSeakeeping::PrintLogMessage("Grid is read. Grid location and name: " + OW3DSeakeeping::UserInput.gridFileName);
	CompositeGridOperators operators = OW3DSeakeeping::DefineOperators(cg, gridData.order_space);
	Interpolant &interpolant = *new Interpolant(cg);

	if (OW3DSeakeeping::print_laplacian_erros)
	{
		OW3DSeakeeping::Solver *solver = new OW3DSeakeeping::Solver(cg);
		solver->SupplySystemMatrix(grid.GetManSolMatrix());
		solver->CalculateSolution(grid.GetManSolComp(), grid.GetManSolRHS());
		grid.PrintLaplacianErrors();
		delete solver;
	}

	OW3DSeakeeping::Baseflow baseflow(cg, gridData, operators, interpolant);
	const OW3DSeakeeping::Baseflow::baseFlowData *baseFlowData;
	if (OW3DSeakeeping::UserInput.base_flow_type == OW3DSeakeeping::BASE_FLOW_TYPES::DB)
	{
		OW3DSeakeeping::Solver *solver = new OW3DSeakeeping::Solver(cg);
		solver->SupplySystemMatrix(baseflow.GetSystemMatrix());
		solver->CalculateSolution(baseflow.GetPotential(), baseflow.GetSystemRight());
		OW3DSeakeeping::PrintLogMessage("Double-body flow solved.");
		delete solver;
	}
	baseFlowData = baseflow.ExtractBaseflowData();

	OW3DSeakeeping::Field field(gridData, baseFlowData, operators);
	OW3DSeakeeping::FreeSurface free_surface(gridData, baseFlowData, operators, interpolant);

	OW3DSeakeeping::Modes *pseudoImpulse;
	for (unsigned int mode_index = 0; mode_index < runs.size(); mode_index++) // Solve the hydrodynamic problems
	{
		OW3DSeakeeping::MODE_NAMES mode_name = runs[mode_index].mode;
		if (mode_name == OW3DSeakeeping::MODE_NAMES::RESISTANCE)
			pseudoImpulse = new OW3DSeakeeping::Resistance(gridData);
		else if (
			mode_name == OW3DSeakeeping::MODE_NAMES::SURGE ||
			mode_name == OW3DSeakeeping::MODE_NAMES::HEAVE ||
			mode_name == OW3DSeakeeping::MODE_NAMES::SWAY ||
			mode_name == OW3DSeakeeping::MODE_NAMES::ROLL ||
			mode_name == OW3DSeakeeping::MODE_NAMES::YAW ||
			mode_name == OW3DSeakeeping::MODE_NAMES::PITCH)
			pseudoImpulse = new OW3DSeakeeping::Radiation(gridData);
		else if (mode_name == OW3DSeakeeping::MODE_NAMES::GMODE)
			pseudoImpulse = new OW3DSeakeeping::GMode(gridData);
		else
			pseudoImpulse = new OW3DSeakeeping::Diffraction(cg, gridData, runs[mode_index].diff_type);

		const OW3DSeakeeping::Modes::Simulation &simulationData = pseudoImpulse->GetSimulationData(); // Get simulation data for this excitation
		pseudoImpulse->StoreSimulationData();

		field.Initialise(runs[mode_index], operators); // Update the filed
		free_surface.Initialise(mode_name);			   // Update the free surface

		OW3DSeakeeping::Solver *solver = new OW3DSeakeeping::Solver(cg);

		solver->SupplySystemMatrix(field.GetSystemMatrix());

		for (int step = 0; step < simulationData.step_count; step++) // Time-step loop
		{
			for (int stage = 0; stage < OW3DSeakeeping::rk_stage_count; stage++) // Runge-Kutta stage
			{
				const OW3DSeakeeping::Modes::Motion &stageMotion = pseudoImpulse->GetMotionData(step, stage);
				free_surface.SetStageSolution(stage, simulationData.time_step);
				const realCompositeGridFunction &stageSurfacePhi = free_surface.GetStagePotential();
				field.ApplyNeumannDirichletConditions(stageSurfacePhi, baseFlowData, stageMotion);
				solver->CalculateSolution(field.GetPotential(), field.GetSystemRight()); // Solve the field
				const realCompositeGridFunction &stageFieldPhi = field.GetPotential();
				free_surface.ComputeSolutionSlope(runs[mode_index].mat_type, field.GetSystemRight(), stageFieldPhi, stage, stageMotion);

				if (stage == 0 and step % OW3DSeakeeping::UserInput.postRate == 0) // Extract the desired solution in this block
				{
					field.StoreBodyIntegrals();
					pseudoImpulse->StoreMotionData();
					if (OW3DSeakeeping::UserInput.wave_drift != 0)
					{
						field.StoreBodyPotentials();
						free_surface.StoreWaterlineElevations();
					}
					if (OW3DSeakeeping::create_showfile)
						free_surface.PrintShowFile();
					if (OW3DSeakeeping::print_elevation)
						free_surface.PrintElevation(stageMotion.time);

				} // End of stage 0 block

			} // End of stage loop

			free_surface.March(simulationData.time_step);
			cout << "Run " << mode_index + 1 << " of " << runs.size() << ". Step " << step + 1 << " of " << simulationData.step_count << "." << endl;

		} // End time-step loop

		delete pseudoImpulse;
		delete solver;

		OW3DSeakeeping::PrintLogMessage(OW3DSeakeeping::ModeStrings.at(mode_name) + " is solved.");

	} // End excitation loop

	Overture::finish();
	OW3DSeakeeping::PrintLogMessage("Program terminated normally.");
	cout << "Program terminated normally." << endl;
	return 0;

} // End of try block

catch (exception &e)
{
	cerr << e.what() << endl;
	return 1;
}
catch (...)
{
	cerr << "exception" << endl;
	return 2;
}