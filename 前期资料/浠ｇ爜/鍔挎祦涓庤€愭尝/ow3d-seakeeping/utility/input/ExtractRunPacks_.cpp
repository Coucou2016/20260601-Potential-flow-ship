#include "Input.h"
#include "OW3DConstants.h"

vector<OW3DSeakeeping::MODE_NAMES> get_runs_responses(vector<unsigned int> user_modes, unsigned int gdim)
{
    vector<OW3DSeakeeping::MODE_NAMES> resps;
    unsigned int gmode_index = 6;

    if (gdim == 2)
    {
        if (user_modes[0] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::SURGE);
        if (user_modes[2] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::HEAVE);
        if (user_modes[4] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::PITCH);
        if (user_modes.size() == gmode_index + 1)
        {
            for (unsigned int i = 0; i < user_modes[gmode_index]; i++)
                resps.push_back(OW3DSeakeeping::MODE_NAMES::GMODE);
        }
    }
    else
    {
        if (user_modes[0] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::SURGE);
        if (user_modes[1] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::SWAY);
        if (user_modes[2] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::HEAVE);
        if (user_modes[3] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::ROLL);
        if (user_modes[4] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::PITCH);
        if (user_modes[5] == 1)
            resps.push_back(OW3DSeakeeping::MODE_NAMES::YAW);
        if (user_modes.size() == gmode_index + 1)
        {
            for (unsigned int i = 0; i < user_modes[gmode_index]; i++)
                resps.push_back(OW3DSeakeeping::MODE_NAMES::GMODE);
        }
    }

    return resps;
}

void OW3DSeakeeping::Input::ExtractRunPacks_()
{
    unsigned int gdim = inputData_.gdim;
    unsigned int nFol = 3;          // Number of diffraction runs in following-seas condition
    unsigned int sym_asm_modes = 2; // Number of diffraction runs when beta!=0 or beta!=180 on a symmetric grid
    double beta = inputData_.beta;
    double U = inputData_.U;
    inputData_.responses = get_runs_responses(inputData_.user_modes, gdim);

    if (inputData_.idif) // Pack diffraction problems
    {
        if (gdim == 2) // 2D GRIDS
        {
            bool following_seas_condition_2d = U != 0 && beta == 0;

            if (!following_seas_condition_2d)
            {
                inputData_.dif_runs.resize(1);
                inputData_.dif_runs[0].mode = MODE_NAMES::DIFFRACTION;
                inputData_.dif_runs[0].mat_type = MAT_TYPES::WHLMAT;
                inputData_.dif_runs[0].diff_type = DIFF_TYPES::FULL;
            }
            else // FOLLOWING-SEAS DIFRRACTIONS
            {
                inputData_.dif_runs.resize(nFol);
                for (unsigned int i = 0; i < nFol; i++)
                {
                    inputData_.dif_runs[i].mode = MODE_NAMES::DIFFRACTION;
                    inputData_.dif_runs[i].mat_type = MAT_TYPES::WHLMAT;
                }

                inputData_.dif_runs[0].diff_type = DIFF_TYPES::OM1;
                inputData_.dif_runs[1].diff_type = DIFF_TYPES::OM2;
                inputData_.dif_runs[2].diff_type = DIFF_TYPES::OM3;
            }
        }
        else // 3D GRIDS
        {
            bool following_seas_condition_3d = U != 0 && (beta < 90 || beta > 270);

            if (!following_seas_condition_3d)
            {
                if (inputData_.symx)
                {
                    if (beta == 180 && U != 0) // HEAD-SEAS DIFFRACTION (U!=0) ON A SYMMETRIC GRID
                    {
                        inputData_.dif_runs.resize(1);
                        inputData_.dif_runs[0].mode = MODE_NAMES::DIFFRACTION;
                        inputData_.dif_runs[0].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[0].diff_type = DIFF_TYPES::HEAD;
                    }
                    else if (beta == 180 || beta == 0) // ZERO SPEED DIFFRACTION ON A SYMMETRIC GRID, BETA = 0 OR 180
                    {
                        inputData_.dif_runs.resize(1);
                        inputData_.dif_runs[0].mode = MODE_NAMES::DIFFRACTION;
                        inputData_.dif_runs[0].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[0].diff_type = DIFF_TYPES::SYM;
                    }
                    else // BEAM- TO HEAD-SEAS DIFFRACTION (U!=0 OR U=0), AND ALL-HEADINGS DIFFRACTION (U=0) ON A SYMMETRIC GRID
                    {
                        inputData_.dif_runs.resize(sym_asm_modes);

                        inputData_.dif_runs[0].mode = MODE_NAMES::DIFFRACTION;
                        inputData_.dif_runs[0].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[0].diff_type = DIFF_TYPES::SYM;

                        inputData_.dif_runs[1].mode = MODE_NAMES::DIFFRACTION;
                        inputData_.dif_runs[1].mat_type = MAT_TYPES::ASMMAT;
                        inputData_.dif_runs[1].diff_type = DIFF_TYPES::ASM;
                    }
                }
                else // DIFFRACTION ON A FULL 3D GRID
                {
                    inputData_.dif_runs.resize(1);
                    inputData_.dif_runs[0].mat_type = MAT_TYPES::WHLMAT;
                    inputData_.dif_runs[0].mode = MODE_NAMES::DIFFRACTION;
                    inputData_.dif_runs[0].diff_type = DIFF_TYPES::FULL;
                }
            }
            else // FOLLOWING-SEAS DIFRRACTIONS
            {
                if (inputData_.symx) // ON A SYMMETRIC GRID
                {
                    if (beta != 0)
                    {
                        inputData_.dif_runs.resize(sym_asm_modes * nFol);
                        for (unsigned int i = 0; i < sym_asm_modes * nFol; i++)
                            inputData_.dif_runs[i].mode = MODE_NAMES::DIFFRACTION;

                        inputData_.dif_runs[0].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[0].diff_type = DIFF_TYPES::OM1_SYM;

                        inputData_.dif_runs[1].mat_type = MAT_TYPES::ASMMAT;
                        inputData_.dif_runs[1].diff_type = DIFF_TYPES::OM1_ASM;

                        inputData_.dif_runs[2].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[2].diff_type = DIFF_TYPES::OM2_SYM;

                        inputData_.dif_runs[3].mat_type = MAT_TYPES::ASMMAT;
                        inputData_.dif_runs[3].diff_type = DIFF_TYPES::OM2_ASM;

                        inputData_.dif_runs[4].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[4].diff_type = DIFF_TYPES::OM3_SYM;

                        inputData_.dif_runs[5].mat_type = MAT_TYPES::ASMMAT;
                        inputData_.dif_runs[5].diff_type = DIFF_TYPES::OM3_ASM;
                    }
                    else // BETA=0 AND U!=0 ON A SYMMETRIC GRID
                    {
                        inputData_.dif_runs.resize(nFol);
                        for (unsigned int i = 0; i < nFol; i++)
                            inputData_.dif_runs[i].mode = MODE_NAMES::DIFFRACTION;

                        inputData_.dif_runs[0].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[0].diff_type = DIFF_TYPES::OM1_HLF;

                        inputData_.dif_runs[1].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[1].diff_type = DIFF_TYPES::OM2_HLF;

                        inputData_.dif_runs[2].mat_type = MAT_TYPES::SYMMAT;
                        inputData_.dif_runs[2].diff_type = DIFF_TYPES::OM3_HLF;
                    }
                }
                else // FOLLOWING-SEA ON A FULL GRID
                {
                    inputData_.dif_runs.resize(nFol);
                    for (unsigned int i = 0; i < nFol; i++)
                    {
                        inputData_.dif_runs[i].mode = MODE_NAMES::DIFFRACTION;
                        inputData_.dif_runs[i].mat_type = MAT_TYPES::WHLMAT;
                    }
                    inputData_.dif_runs[0].diff_type = DIFF_TYPES::OM1;
                    inputData_.dif_runs[1].diff_type = DIFF_TYPES::OM2;
                    inputData_.dif_runs[2].diff_type = DIFF_TYPES::OM3;
                }
            }
        }

    } // ENF OF IDIF

    if (inputData_.irad) // Pack radiation problems
    {
        if (gdim == 2)
        {
            HydrodynamicProblem rad_run;
            rad_run.mat_type = MAT_TYPES::WHLMAT;
            if (inputData_.user_modes[0] == 1)
            {
                rad_run.mode = MODE_NAMES::SURGE;
                inputData_.rad_runs.push_back(rad_run);
            }
            if (inputData_.user_modes[2] == 1)
            {
                rad_run.mode = MODE_NAMES::HEAVE;
                inputData_.rad_runs.push_back(rad_run);
            }
            if (inputData_.user_modes[4] == 1)
            {
                rad_run.mode = MODE_NAMES::PITCH;
                inputData_.rad_runs.push_back(rad_run);
            }
        }
        else
        {
            HydrodynamicProblem rad_run;
            if (inputData_.user_modes[0] == 1)
            {
                rad_run.mode = MODE_NAMES::SURGE;
                rad_run.mat_type = (inputData_.symx == 1) ? MAT_TYPES::SYMMAT : MAT_TYPES::WHLMAT;
                inputData_.rad_runs.push_back(rad_run);
            }
            if (inputData_.user_modes[1] == 1)
            {
                rad_run.mode = MODE_NAMES::SWAY;
                rad_run.mat_type = (inputData_.symx == 1) ? MAT_TYPES::ASMMAT : MAT_TYPES::WHLMAT;
                inputData_.rad_runs.push_back(rad_run);
            }
            if (inputData_.user_modes[2] == 1)
            {
                rad_run.mode = MODE_NAMES::HEAVE;
                rad_run.mat_type = (inputData_.symx == 1) ? MAT_TYPES::SYMMAT : MAT_TYPES::WHLMAT;
                inputData_.rad_runs.push_back(rad_run);
            }
            if (inputData_.user_modes[3] == 1)
            {
                rad_run.mode = MODE_NAMES::ROLL;
                rad_run.mat_type = (inputData_.symx == 1) ? MAT_TYPES::ASMMAT : MAT_TYPES::WHLMAT;
                inputData_.rad_runs.push_back(rad_run);
            }
            if (inputData_.user_modes[4] == 1)
            {
                rad_run.mode = MODE_NAMES::PITCH;
                rad_run.mat_type = (inputData_.symx == 1) ? MAT_TYPES::SYMMAT : MAT_TYPES::WHLMAT;
                inputData_.rad_runs.push_back(rad_run);
            }
            if (inputData_.user_modes[5] == 1)
            {
                rad_run.mode = MODE_NAMES::YAW;
                rad_run.mat_type = (inputData_.symx == 1) ? MAT_TYPES::ASMMAT : MAT_TYPES::WHLMAT;
                inputData_.rad_runs.push_back(rad_run);
            }
        }

    } // ENF OF IRAD

    if (inputData_.ires) // Pack wave-resistance problems
    {
        HydrodynamicProblem res_run;
        res_run.mat_type = (gdim == 3 && inputData_.symx) ? MAT_TYPES::SYMMAT : MAT_TYPES::WHLMAT;
        res_run.mode = MODE_NAMES::RESISTANCE;
        inputData_.res_runs.push_back(res_run);
        inputData_.all_runs = inputData_.res_runs;

    } // ENF OF IRES

    // Pack generalized mode problems

    inputData_.number_of_gmodes = (inputData_.user_modes.size() == total_number_of_rigid_modes + 1) ? inputData_.user_modes[total_number_of_rigid_modes] : 0;

    if (inputData_.irad != 0 && inputData_.user_modes.size() == total_number_of_rigid_modes + 1)
    {
        HydrodynamicProblem gmd_run;
        gmd_run.mode = MODE_NAMES::GMODE;
        gmd_run.mat_type = (inputData_.symx == 1) ? MAT_TYPES::SYMMAT : MAT_TYPES::WHLMAT;
        for (unsigned int i = 0; i < inputData_.number_of_gmodes; i++)
        {
            gmd_run.gmode_counter = i;
            inputData_.gmd_runs.push_back(gmd_run);
        }

        // Important note: For a half-grid computation, all generalized modes by default are stored
        // as "symmetric" with respect to z axis (y is upward). Any anti-symmetric case, for example
        // a "torsion" mode should be specified by overriding the default values in this section.
        // This can be done for example by: inputData_.gmd_runs[1].mat_type = MAT_TYPES::ASM. Also
        // note that the definitions of all generalized modes should be implemented in ComputeGModeShape_.cpp,
        // which is a private member function of the Grid class. The generalized mode definitions then
        // become available to all parts of the programs through the "grid data" struct.
    }

    // Pack all runs
    inputData_.all_runs.insert(inputData_.all_runs.end(), inputData_.dif_runs.begin(), inputData_.dif_runs.end());
    inputData_.all_runs.insert(inputData_.all_runs.end(), inputData_.rad_runs.begin(), inputData_.rad_runs.end());
    inputData_.all_runs.insert(inputData_.all_runs.end(), inputData_.gmd_runs.begin(), inputData_.gmd_runs.end());
    if (inputData_.all_runs.size() != 0)
    {
        inputData_.number_of_rigid_modes = inputData_.responses.size() - inputData_.number_of_gmodes;
        inputData_.solve_motion = (inputData_.mass_matrix.size() != 0 && inputData_.irad != 0 && inputData_.dif_runs.size() != 0) ? true : false;
    }

} // End of ExtractRunPacks_ private function