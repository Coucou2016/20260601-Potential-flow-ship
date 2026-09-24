## Modelling and Simulation of Marine Surface Vessel Dynamics (Module 10: Software and Rapid Model Prototyping)

Dr Tristan Perez

Centre for Complex Dynamic Systems and Control (CDSC)

Professor Thor I Fossen

Department of Engineering Cybernetics

![](images/8962ba0bc872ad077847583e2841494ce51a6476cb145d28b6251702cc8e12a0.jpg)

![](images/e29b613ed08a3f4363bdbd18f84ff9baef4b407f0950166ce6b405c5c0a30cbe.jpg)

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

1

## MSS – Marine Systems Simulator

- **GNC Toolbox** (m-file library and Simulink blocks) Ref. T. I. Fossen Marine Control Systems (2002)
- **Hydro** (m-file library for hydrodynamic post-processing of hydrodynamic data + Simulink blocks for time-domain simulation of vessel responses in 6 DOF). Ref. T. Perez and T. I. Fossen (new book with worked examples, in progress)

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

2

![](images/bfcbe5359ef14bca46c905e3f9e77165dfcfcf9c6b312264477c7189bae34a67.jpg)

![](images/86f0fea657cab7925e3220a27b966935b6110de2f9f02e0a220ac2ab34ad772e.jpg)

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

3

## From Vessel Body Plan to MSS

1. Body plan (general arrangement)

\- Drawing can be scanned and digitalized manually

\- Geometry file: AutoCad, ShipX, Wamit, Napa, etc.

2. Hydrodynamic Configuration and Computations

\- SW: Wamit, Shipx (VERES), Octopus (SEAWAY) etc.

\- Computes:

- Frequency-dependent added mass and potential damping
- Restoring forces
- Froude-Krylov and diffraction forces (1st-order wave loads)
- Wave drift (2nd-order wave loads)
- Viscous roll damping (Ikeda damping etc.)

![](images/db74f6b04134f436d8a3e55526532e4fbd46680951b8d9ebddf4586e18216b4a.jpg)

3. Post-Processing (MSS Hydro)

\- Computes state-space models for frequency-dependent hydrodynamics

\- Add viscous damping like linear skin friction, ITTC drag, cross-flow drag

\- Add nonlinear maneuvering coefficients

4. Simulink Vessel Simulator (MSS Hydro)

\- 6 DOF real-time simulation of vessel position, velocity, and acceleration +  wind, current, and wave generators.

\- For a floating vessel the resulting model will be described by 100-200 ODEs. Wave load data for different speeds and headings (0-360 deg) are also included.

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

4

## Digitizing the Ship Lines using a Drawing

![](images/156c8b4ac0620556bae11c7bdb03ff324ca7768fedb141b8ed1f15fe98d8d7a4.jpg)

3 known axes points (x, y)

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

5

## Data Processing – Table of Offsets

![](images/c1a90a464e515d52d27454e18b7303e89b1af0f738658c4f3c60b92834e8ce65.jpg)

![](images/2946db5b310d3e24627457d7eecab16c115782862079366534a96472bd008c67.jpg)

The digitized ship sections are exported to Excel  in two columns (xz-plan) from Digitizer

![](images/9b14ebfa3f2036781bf8e2d4c7de6fba23ddc81f2565885a09fbf223a3d6bcef.jpg)

Example:

S175 container ship.

Ascii file:

S175.mgf

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

6

## ShipX (VERES) by MARINTEK

![](images/50ddad39a73c96c583997f0979d85c1d404dd497042456b35cf96934c89c5cbb.jpg)

**MARINTEK** - the Norwegian Marine Technology Research Institute - does research and development in the maritime sector for industry and the public sector. The Institute develops and verifies technological solutions for the shipping and maritime equipment industries and for offshore petroleum production.

<strong>VERES</strong> - <strong>VEssel RESponse program</strong> is a <strong><u>Strip Theory Program</u></strong> which calculates wave-induced loads on and motions of mono-hulls and barges in deep to very shallow water. The program is based on the famous paper by <strong>Salvesen</strong>, <strong>Tuck</strong> and <strong>Faltinsen</strong> (1970). <em>Ship Motions and Sea Loads</em>. Trans. SNAME.

![](images/e27d355a9393ecf736ff330929e4235af7928cd0e0bd405f8c4adc8cc9d4c436.jpg)

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

7

![](images/294640336a47a67e1132c072ead384d4f72cef2fabec7fbb2a845675d2d74eb4.jpg)

## OCTOPUS SEAWAY by Amarcon

**and AMARCON cooperate in further development of SEAWAY**

The Maritime Research Institute Netherlands (MARIN) and AMARCON agree to cooperate in further development of SEAWAY. MARIN is an internationally recognized authority on hydrodynamics, involved in frontier breaking research programs for the maritime and offshore industries and navies.

![](images/eaee2363f5ea9189e92962b27a828edc07fec50541f0cf596df296cb3937609c.jpg)

SEAWAY is developed by Professor J.M.J. Journée at the Delft Univ. of Technology

SEAWAY is a <strong><u>Strip Theory Program</u></strong> to calculate wave-induced loads on and motions of mono-hulls and barges in deep to very shallow water. When not accounting for interaction effects between the hulls, also catamarans can be analyzed. Work of very acknowledged hydromechanic scientists (like Ursell, Tasai, Frank, Keil, Newman, Faltinsen, Ikeda, etc.) has been used, when developing this code.

SEAWAY has extensively been verified and validated using other computer

**codes and experimental data.**

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

9

![](images/36a7adbf2b23f90cce16168eee9ac26276585e8d47a488e1e951cab9408bc328.jpg)

## WAMIT (Vers. 6.3) by WAMIT INC.

**WAMIT®**  is the most advanced set of tools available for analyzing wave interactions with offshore platforms and other structures or vessels.

**WAMIT®**  was developed by **Professor Newman** and coworkers at **MIT** in 1987, and it has gained widespread recognition for its ability to analyze the complex structures with a high degree of accuracy and efficiency.

![](images/c5f09a38f6936d2222804ab8ae29808dfe059c4eb04e9993e799faa14bf1b065.png)

3D Panelization of

a Supply Vessel

Over the past 20 years WAMIT has been licensed to more than 90 industrial and research organizations worldwide.

09/09/2007

11

One-day Tutorial, CAMS'07, Bol, Croatia

## Hydrodynamic Methods (MSS Hydro)

- Frequency-Dependent Hydrodynamic Added Mass, Potential Damping, and Restoring Forces:   Computed using:  WAMIT, ShipX (VERES), or Octopus SEAWAY
- Nonlinear Viscous Damping and Current Loads:
    - ITTC quadratic drag formulation/ added resistance in surge (includes current)
    - Nonlinear cross-flow drag in sway and yaw (includes currents)
    - Munk moment in yaw from potential coefficients
    - Higher order nonlinear damping terms in heave, roll, and pitch (manually added)
    - Maneuvering coefficients (manually added)

- Nonlinear Frequency-Dependent Damping in Roll due to Bilge Keels and Anti-Rolling Tanks: Can be computed in ShipX (VERES) and Octopus (SEAWAY)
- Frequency-Dependent Linear Viscous Damping in DOFs 1,2,6:  Manually added using exponential decaying functions for skin friction
- Wave Loads:  1st-order (Froude-Krylov and diffraction) and 2nd-order wave loads (wave drift) are computed using 2D/3D potential theory
- Wind Loads:  Computed using wind coefficient tables

09/09/2007

12

One-day Tutorial, CAMS'07, Bol, Croatia

## Output (Ascii-files) from Hydrodynamic Codes

- VERES
    - \*.re1
    - \*.re2

- SeaWay
    - \*.out
- WAMIT
    - \*.x

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

13

## Postprocessing of the Hydrodynamic Data Files to the MSS vessel structure

- Extract necessary information from the ASCII files generated by the hydrodynamic code
- Scaling of data
- Change and translate coordinate frames for hydrodynamic coefficients, RAOs, transfer functions etc.
- Add viscous effects (hydrodynamic codes are non-viscous/potential theory)
- Process data for time-domain simulation

Notice that the *MSS vessel structure* is independent of the hydrodynamic code!

**MSS Hydro toolbox commands:** >> veres2vessel.m

>> wamit2vessel.m

>> seaway2vessel.m

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

14

## MSS Hydro Vessel Structure

- xxx

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

15

## Example: Adding Viscous Damping

Damping B44, B55, B66

Added mass A44, A55, A66

![](images/7cf73e5db3581bd0b6ad1ead138fb105a50d5da66f1d6a4bef54d630b6e3f2ae.png)

Peak is due

to IKEDA

roll damping

theory for

bilge keels

Linear viscous

skin friction

(ramps)

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

16

## **Vectorial Vessel Model Representation for Marine Vessels**

From Robotics to Ship Modeling (Fossen 1991, PhD thesis)

Consider the classical robot manipulator model:

\- **q** is a vector of joint angles

\-     is a vector of torque

\- **M** and **C** are the system inertia and Coriolis matrices

This model structure can be used as foundation to write the 6 DOF marine vessel equations of motion in a compact <em>vectorial</em> setting (<strong>Fossen 1994, 2002</strong>):

\- body velocities:

\- position and Euler angles:

- **M, C** and **D** denote the system inertia,    Coriolis and damping matrices
- **g is a vector of gravitational and buoyancy**    **forces and moments**

![](images/48fea1834a89ef3c00d3de04946fe2171616d0297d80559c63c3aa220a55d356.jpg)

![](images/375547676fd0ff01ed8568b255d20c46389845ea3b127683bbfede0b2fc40b91.jpg)

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

17

## Unified Time-Domain Model for Different Speeds and Different Sea States

The *Force-Transfer-Functions* are computed using hydrodynamic SW

e.g. **WAMIT**, **VERES** or **SEAWAY**

![](images/a9eacf6ae97b3ee384cea112d6fab52ec7b8801d63db5616e5ebf4cf8caaef54.png)

![](images/f20ee8f59ee386dd66951c4830e8be655e924ff52f07c05506e36c24f94e0e43.jpg)

*For 6 DOF this model will typically be represented by* *6 + 6 + 90 = 102 ODEs*

*which are computed using*

<em>hydrodynamic e.g.</em> <em><strong>WAMIT</strong>,</em> <em><strong>VERES</strong></em> <em>or</em> <em><strong>SEAWAY</strong></em>

*These terms are found using experimental results/curve fitting or*

*semi-empirical methods*

09/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

18