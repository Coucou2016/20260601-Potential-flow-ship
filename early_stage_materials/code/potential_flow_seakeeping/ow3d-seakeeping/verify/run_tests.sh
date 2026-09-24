#!/bin/bash
shopt -s extglob
user_precision=1e-9
test_arg="$1"
update_arg="$2"
test_tag=${test_arg:1}
# -------------------------------------------------------------------
# Run derivatives test with option -dervs, add -u for update
# Note: First turn on "print_ow3d_derivatives_verification" and
# trun off "use_grid_symmetry_for_derivatives" in OW3DConstants.cpp 
# and rebuild.
# -------------------------------------------------------------------
if [ "$test_tag" == dervs ]; then

cd $OW3D_DIR/verify/tests/dervs
$Overture/bin/ogen -noplot build_grid
if [ "$update_arg" = "-u" ]; then
    $OW3D_DIR/ow3dt/ow3dt
    mv expected no_longer_valid
    mv dervs_ow3dt expected
fi
$OW3D_DIR/ow3dt/ow3dt
$OW3D_DIR/verify/src/TestDervs -p=$user_precision
fi
# -------------------------------------------------------------------
# Run baseflow test with option -baseflow, add -u for update.
# Note: First turn on "calcBaseElev_" in Baseflow.cpp, and rebuild 
# -------------------------------------------------------------------
if [ "$test_tag" == baseflow ]; then

cd $OW3D_DIR/verify/tests/baseflow
$Overture/bin/ogen -noplot build_grid
if [ "$update_arg" = "-u" ]; then
    $OW3D_DIR/ow3dt/ow3dt
     mv expected no_longer_valid
     mv baseflow_ow3dt expected
fi
$OW3D_DIR/ow3dt/ow3dt
$OW3D_DIR/verify/src/TestBaseflow -p=$user_precision
fi
# -------------------------------------------------------------------
# Run upwind test with option -upwind, add -u for update.
# Note: First turn on "print_ow3d_upwind_verification" 
# in OW3DConstants.cpp and rebuild.
# -------------------------------------------------------------------
if [ "$test_tag" == upwind ]; then

cd $OW3D_DIR/verify/tests/upwind
$Overture/bin/ogen -noplot build_grid
if [ "$update_arg" = "-u" ]; then
    $OW3D_DIR/ow3dt/ow3dt
     mv expected no_longer_valid
     mv upwind_ow3dt expected
fi
$OW3D_DIR/ow3dt/ow3dt
$OW3D_DIR/verify/src/TestUpwind -p=$user_precision
fi
# -------------------------------------------------------------------
# The tests for generalized-mode hydrostatic coefficients.
# Run the test with options -gmng, -gmne, -gmma and -gmwa. 
# Add -u  for update. Note for each test option the solver 
# should be  compiled after changing the corresponding flag for 
# GMODES_HYDROSTATICS in OW3DConstants.cpp file.
# -------------------------------------------------------------------
if [ "$test_tag" == gmma ] || \
   [ "$test_tag" == gmne ] || \
   [ "$test_tag" == gmng ] || \
   [ "$test_tag" == gmwa ]; then

cd $OW3D_DIR/verify/tests/gmhydros/${test_tag:2:3}/
$Overture/bin/ogen -noplot build_grid
if [ "$update_arg" = "-u" ]; then
    $OW3D_DIR/ow3dt/ow3dt
    $OW3D_DIR/ow3df/ow3df
    mv expected no_longer_valid
    mv gmhydro_ow3df expected
fi
$OW3D_DIR/ow3dt/ow3dt
$OW3D_DIR/ow3df/ow3df
$OW3D_DIR/verify/src/TestGmHydros -p=$user_precision
fi
# -------------------------------------------------------------------
#   Run the test for Timoshenko theory.
#   Use gmode_type = TIMOSHENKO_STRUC & gamma_Timo = 0.005372616
# -------------------------------------------------------------------
if [ "$test_tag" == timosh ]; then
cd $OW3D_DIR/verify/tests/timoshenko
$Overture/bin/ogen -noplot build_grid
if [ "$update_arg" = "-u" ]; then
    $OW3D_DIR/ow3dt/ow3dt
    $OW3D_DIR/ow3df/ow3df
    mv expected no_longer_valid
    mv timoshenko_ow3df expected
fi
$OW3D_DIR/ow3dt/ow3dt
$OW3D_DIR/ow3df/ow3df
$OW3D_DIR/verify/src/TestTimoshenko -p=$user_precision
fi
# -------------------------------------------------------------------
# Run ow3dseakeeping tests with option -01 to -14, add -u for update.
# -------------------------------------------------------------------
if [ "$test_tag" == 01 ] || \
   [ "$test_tag" == 02 ] || \
   [ "$test_tag" == 03 ] || \
   [ "$test_tag" == 04 ] || \
   [ "$test_tag" == 05 ] || \
   [ "$test_tag" == 06 ] || \
   [ "$test_tag" == 07 ] || \
   [ "$test_tag" == 08 ] || \
   [ "$test_tag" == 09 ] || \
   [ "$test_tag" == 10 ] || \
   [ "$test_tag" == 11 ] || \
   [ "$test_tag" == 12 ] || \
   [ "$test_tag" == 13 ] || \
   [ "$test_tag" == 14 ]; then
    exe_name=$OW3D_DIR/verify/src/Test$test_tag
    test_folder=test$test_tag   

    cd $OW3D_DIR/verify/tests/ow3d/$test_folder
    $Overture/bin/ogen -noplot build_grid
        if [ "$test_tag" == 13 ]; then
        ./build_patches
        fi
        if [ "$update_arg" == "-u" ]; then
        $OW3D_DIR/ow3dt/ow3dt
        $OW3D_DIR/ow3df/ow3df
        mv expected no_longer_valid
        mv $test_folder\_ow3df expected
        fi
    $OW3D_DIR/ow3dt/ow3dt
    $OW3D_DIR/ow3df/ow3df
    $exe_name -p=$user_precision
fi
# -------------------------------------------------------------------
# Run all ow3d tests with option -ow3d
# -------------------------------------------------------------------
if [ "$test_tag" == ow3d ]; then
    test_results=()
    pass_array=()
    fail_array=()
    test_array=(01 02 03 04 05 06 07 08 09 10 11 12 13 14)

    cd $OW3D_DIR/verify/tests/ow3d
    for num in ${test_array[@]}
        do
            cd test$num
            $Overture/bin/ogen -noplot build_grid
                if [ "$num" == 13 ]; then
                ./build_patches
                fi
            $OW3D_DIR/ow3dt/ow3dt
            $OW3D_DIR/ow3df/ow3df
            $OW3D_DIR/verify/src/Test$num -p=$user_precision
            test_results+=($?)
            cd ..
    done
    echo "Test   Result"
    echo "-------------"
    counter=0
    for res in ${test_results[@]}
    do
        test_number=${test_array[$counter]}
        if (($res==1)); then
            echo -e "\e[0;40;1;92m $test_number    PASSED \e[0m"
        else
            echo -e "\e[0;40;1;31m $test_number    FAILED \e[0m"
        fi
    counter=$[$counter+1]
    done
fi
# -------------------------------------------------------------------
# Run test for Filter class with option -filter, add -u for update.
# Note: First turn on "print_ow3d_filter_verification" in 
# the OW3DConstants.cpp and "filter_on_ = true" in the 
# FreeSurface class. Then rebuild.
# -------------------------------------------------------------------
if [ "$test_tag" == filter ]; then

cd $OW3D_DIR/verify/tests/filter
$Overture/bin/ogen -noplot build_grid
if [ "$update_arg" = "-u" ]; then
    $OW3D_DIR/ow3dt/ow3dt
     mv expected no_longer_valid
     mv filter_ow3dt expected
fi
$OW3D_DIR/ow3dt/ow3dt
$OW3D_DIR/verify/src/TestFilter -p=$user_precision
fi