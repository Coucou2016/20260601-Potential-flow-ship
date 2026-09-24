# Installation note for OceanWave3D-seakeeping

Mostafa Amini Afshar and Harry B. Bingham

Section of Fluid Mechanics, Coastal and Maritime Engineering

Department of Mechanical Engineering

Technical University of Denmark

February 1, 2017

## 1 Introduction

In this document the required process for installation of the seakeeping solver is described. Please note that OceanWave3D-Seakeeping code is making use of several external libraries. These libraries must be built and installed before the seakeeping code is compiled and used. The main library is called Overture (Brown et al., 1999). It is assumed here that the Overture library has already been installed. For Overture installation procedure, please refer to the relevant document in this folder. It is also recommended to install the PETSc library as it has been explained in the Overture installation guide. The seakeeping code is also using the GNU Scientific Library (gsl) (Gough, 2009) whose installation will be described described in this note. For all other required libraries please refer to the documentation for the Overture installation in this folder.

## 2 Building the gsl library

This library is a collection of routines for the numerical calculation in C and C++. In the seakeeping code it is used for instance to perform the fft, least-square fitting, complex number operations and so on. The gsl library can be downloaded from https://ftp.gnu.org/gnu/gsl/. Note that he seakeeping code is written based on gsl version 1.16. For installation:

tar xzf gsl-1.16.tar.gz

cd gsl-1.16

./configure

make

make check

make install

For more information regarding the installation process for gsl refer to the INSTALL file in the gsl library folder.

## 3 Building the seakeeping code

The whole seakeeping code is arranged in the following folders:

##

This folder contains the whole implementation files of the code.

## include

Is the place for the header files. All implementation files in cpp folder are declared in the files located in include folder.

## bin

All the binary and object files resulting from the compilation will be located in this folder. Note that two executables RUN.exe and POST.exe are built in the parent folder.

The compilation of the code is simple and can be done just by typing:

make

in the parent folder. If successful, this would make the two executables RUN.exe and POST.exe in the parent folder. Finally you can also add the paths of these executables to your existing path, by adding the following line in to the .bashrc file in the home directory:

export=\$PATH:[the path to the executables (RUN.exe and POST.exe)].

## References

Brown, D. L., W. D. Henshaw, and D. J. Quinlan. Overture: An object-oriented framework for solving partial differential equations on overlapping grids. Object Oriented Methods for Interoperable Scientific and Engineering Computing, SIAM, pages 245–255, 1999.  
Gough, B. GNU scientific library reference manual. Network Theory Ltd., 2009.