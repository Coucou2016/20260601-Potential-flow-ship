// This file contains the implementation of the Input class.

#include "Input.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Input::Input()
{
	ifstream fin_inp(ow3d_input_file_name);
	if (fin_inp.fail())
		throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t The input file is missing.", 0));
	string str_inp; // Used for storing lines read by the fin
	unsigned int line_count = 0;
	while (getline(fin_inp, str_inp)) // Read the input file line by line
	{
		if (line_count == INPUT_LINES::HEADLINE)
		{
			line_count++;
			continue;
		}
		if (str_inp.find(':') != input_colon_index)
			throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Wrong colon position in line " + DoubleToString(line_count) + '.', 0));
		istringstream rdf_inp(str_inp.substr(1 + input_colon_index));
		if (line_count == INPUT_LINES::NAMELINE) // Read the project name and build the results folder
			rdf_inp >> inputData_.project_name;
		else if (line_count == INPUT_LINES::SPEDLINE) // Read the forward speed
			rdf_inp >> inputData_.U;
		else if (line_count == INPUT_LINES::BASELINE) // Read the base-flow type
			rdf_inp >> base_type_string_;
		else if (line_count == INPUT_LINES::IDIFLINE) // Read the diffraction info.
			rdf_inp >> inputData_.idif;
		else if (line_count == INPUT_LINES::IRADLINE) // Read the radiation info.
			rdf_inp >> inputData_.irad;
		else if (line_count == INPUT_LINES::IRESLINE) // Read the resistance info.
			rdf_inp >> inputData_.ires;
		else if (line_count == INPUT_LINES::MODELINE) // Read the modes info.
		{
			int mode;
			while (rdf_inp >> mode)
				inputData_.user_modes.push_back(mode);
		}
		else if (line_count == INPUT_LINES::DRIFLINE) // Read drift-force info.
			rdf_inp >> inputData_.wave_drift;
		else if (line_count == INPUT_LINES::COURLINE)
			rdf_inp >> inputData_.courant;
		else if (line_count == INPUT_LINES::TIMELINE)
			rdf_inp >> inputData_.run_time;
		else if (line_count == INPUT_LINES::BETALINE)
			rdf_inp >> inputData_.beta;
		else if (line_count == INPUT_LINES::GRIDLINE)
			rdf_inp >> inputData_.gridFileName;
		else if (line_count == INPUT_LINES::GDIMLINE)
			rdf_inp >> inputData_.gdim;
		else if (line_count == INPUT_LINES::SYMXLINE)
			rdf_inp >> inputData_.symx;
		else if (line_count == INPUT_LINES::ROTCLINE)
		{
			double rotc;
			while (rdf_inp >> rotc)
				inputData_.rotation_centre.push_back(rotc);
		}
		else if (line_count == INPUT_LINES::COGRLINE)
		{
			double grac;
			while (rdf_inp >> grac)
				inputData_.gravitation_centre.push_back(grac);
		}
		else if (line_count == INPUT_LINES::GRAVLINE)
			rdf_inp >> inputData_.g;
		else if (line_count == INPUT_LINES::ULENLINE)
			rdf_inp >> inputData_.ulen;
		else if (line_count == INPUT_LINES::SOLVLINE)
			rdf_inp >> solver_type_string_;
		else if (line_count == INPUT_LINES::FFTZLINE)
			rdf_inp >> inputData_.zero_padding_multiple;
		else if (line_count == INPUT_LINES::ORATLINE)
			rdf_inp >> inputData_.postRate;

		line_count++;

	} // End of while loop to read all lines in ow3d.in file

	if ((line_count - 1) != number_of_user_input_lines)
		throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Some input data is missing.", 0));

	// ------------------------------------------------------------------------
	// Read mass matrix (if provided)
	// ------------------------------------------------------------------------
	ifstream fin_mass(ow3d_mass_file_name);
	if (!fin_mass.fail())
	{
		inputData_.user_mass = true;
		string str_mass;
		line_count = 0;
		while (getline(fin_mass, str_mass))
		{
			if (line_count == INPUT_LINES::HEADLINE)
			{
				line_count++;
				continue;
			}
			istringstream rdf_mass(str_mass);
			vector<double> entries;
			double entry;
			while (rdf_mass >> entry)
				entries.push_back(entry);
			inputData_.mass_matrix.push_back(entries);
		}
	}
	// ------------------------------------------------------------------------
	// Read hydrostatic matrix (if provided)
	// ------------------------------------------------------------------------
	ifstream fin_hydro(ow3d_hydrostatic_file_name);
	if (!fin_hydro.fail())
	{
		inputData_.user_hydro = true;
		string str_hydro;
		line_count = 0;
		while (getline(fin_hydro, str_hydro))
		{
			if (line_count == INPUT_LINES::HEADLINE)
			{
				line_count++;
				continue;
			}
			istringstream rdf_hydro(str_hydro);
			vector<double> entries;
			double entry;
			while (rdf_hydro >> entry)
				entries.push_back(entry);
			inputData_.hydrostatic_matrix.push_back(entries);
		}
	}
	// ------------------------------------------------------------------------
	// Read stiffness matrix for generalized modes (if provided)
	// ------------------------------------------------------------------------
	ifstream fin_stiff(ow3d_stiffness_file_name);
	if (!fin_stiff.fail())
	{
		inputData_.user_stiff = true;
		string str_stiff;
		line_count = 0;
		while (getline(fin_stiff, str_stiff))
		{
			if (line_count == INPUT_LINES::HEADLINE)
			{
				line_count++;
				continue;
			}
			istringstream rdf_stiff(str_stiff);
			vector<double> entries;
			double entry;
			while (rdf_stiff >> entry)
				entries.push_back(entry);
			inputData_.stiffness_matrix.push_back(entries);
		}
	}
	// ------------------------------------------------------------------------
	// Read shear stiffness matrix for generalized modes (if provided)
	// ------------------------------------------------------------------------
	ifstream fin_shear_stiff(ow3d_shear_stiffness_file_name);
	if (!fin_shear_stiff.fail())
	{
		inputData_.user_shear_stiff = true;
		string str_shear_stiff;
		line_count = 0;
		while (getline(fin_shear_stiff, str_shear_stiff))
		{
			if (line_count == INPUT_LINES::HEADLINE)
			{
				line_count++;
				continue;
			}
			istringstream rdf_shear_stiff(str_shear_stiff);
			vector<double> entries;
			double entry;
			while (rdf_shear_stiff >> entry)
				entries.push_back(entry);
			inputData_.shear_stiffness_matrix.push_back(entries);
		}
	}
	// ------------------------------------------------------------------------
	// Perform checks on the user data
	// ------------------------------------------------------------------------
	if (inputData_.ires == 1)
	{
		inputData_.irad = 0; // Override user data (wave resistance is allowed only as as a separate mode)
		inputData_.idif = 0; // Override user data (wave resistance is allowed only as as a separate mode)
	}

	if (inputData_.user_modes.size() < total_number_of_rigid_modes || inputData_.user_modes.size() > (total_number_of_rigid_modes + 1))
		throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Mode input must be a six-element array.", 0));
	if (inputData_.user_modes.size() == total_number_of_rigid_modes &&
		std::find(inputData_.user_modes.begin(), inputData_.user_modes.end(), 1) == inputData_.user_modes.end())
		throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Mode input is not correct.", 0));

	if (inputData_.U != 0)
	{
		if (base_type_string_ == "db")
			inputData_.base_flow_type = OW3DSeakeeping::BASE_FLOW_TYPES::DB;
		else if (base_type_string_ == "nk")
			inputData_.base_flow_type = OW3DSeakeeping::BASE_FLOW_TYPES::NK;
		else
			throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t The base-flow type is wrong. It should be nk or db.", 0));
	}
	else
	{
		base_type_string_ = "";
		inputData_.base_flow_type = OW3DSeakeeping::BASE_FLOW_TYPES::ZS;
	}

	if (solver_type_string_ == "di")
		inputData_.solver_type = OW3DSeakeeping::SOLVER_TYPES::DI;
	else if (solver_type_string_ == "it")
		inputData_.solver_type = OW3DSeakeeping::SOLVER_TYPES::IT;
	else if (solver_type_string_ == "mg")
		inputData_.solver_type = OW3DSeakeeping::SOLVER_TYPES::MG;
	else
		throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t The solver type is wrong. It should be di, it or mg.", 0));

	ExtractRunPacks_(); // Pack the hydrodynamic porblems which should be solved.

	if (!inputData_.user_stiff)
		inputData_.stiffness_matrix.resize(inputData_.responses.size(), std::vector<double>(inputData_.responses.size(), 0));
	if (!inputData_.user_shear_stiff)
		inputData_.shear_stiffness_matrix.resize(inputData_.responses.size(), std::vector<double>(inputData_.responses.size(), 0));
	if (inputData_.user_shear_stiff && gmode_type == GMODE_TYPES::EULERBERNOULLI)
		throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Shear stiffness matrix is used only for Timoshenko beam theory.", 0));

	// ------------------------------------------------------------------------
	// Some further checks on the user data after the runs are packed
	// ------------------------------------------------------------------------
	if (inputData_.mass_matrix.size() != 0)
	{
		if (inputData_.idif == 0 || inputData_.irad == 0)
			throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t For motion calculation, both irad and idif should be 1.", 0));
		if (inputData_.mass_matrix.size() != inputData_.responses.size())
			throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Size of the mass matrix is not consistent with the size of the responses.", 0));
		for (unsigned int i = 0; i < inputData_.mass_matrix.size(); i++)
		{
			if (inputData_.mass_matrix[i].size() != inputData_.responses.size())
				throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Size of the mass matrix is not consistent with the size of the responses.", 0));
		}
	}
	if (inputData_.hydrostatic_matrix.size() != 0)
	{
		if (inputData_.hydrostatic_matrix.size() != inputData_.responses.size())
			throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Size of the hydrostatic matrix is not consistent with the size of the responses.", 0));
		for (unsigned int i = 0; i < inputData_.hydrostatic_matrix.size(); i++)
		{
			if (inputData_.hydrostatic_matrix[i].size() != inputData_.responses.size())
				throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Size of the hydrostatic matrix is not consistent with the size of the responses.", 0));
		}
	}
	if (inputData_.irad != 0 && inputData_.idif != 0 && inputData_.wave_drift != 0 && !inputData_.solve_motion)
		throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Wave drift force for an oscillating body can't be computed without the motion.", 0));
	if (inputData_.wave_drift != 0 && !inputData_.idif)
		throw runtime_error(GetColoredMessage("\n\t Error (OW3D), Input.cpp.\n\t Wave drift force can't be computed without diffraction problem.", 0));

	PrintUserData_();

} // END OF THE CONSTRUCTOR

OW3DSeakeeping::Input::~Input()
{
}

OW3DSeakeeping::Input::INPUT OW3DSeakeeping::Input::getInputData() const
{
	return inputData_;
}
