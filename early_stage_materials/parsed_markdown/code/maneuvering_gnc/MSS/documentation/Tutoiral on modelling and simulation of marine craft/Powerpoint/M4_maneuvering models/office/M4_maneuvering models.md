## Manoeuvring Models  (Module 4)

Prepared together with Andrew Ross

Dr Tristan Perez

Centre for Complex Dynamic Systems and Control (CDSC)

Professor Thor I Fossen

Department of Engineering Cybernetics

![](images/8962ba0bc872ad077847583e2841494ce51a6476cb145d28b6251702cc8e12a0.jpg)

![](images/e29b613ed08a3f4363bdbd18f84ff9baef4b407f0950166ce6b405c5c0a30cbe.jpg)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

1

Vectorial Representation for Ships

From robotics to ship modeling (Fossen 1991)

It is here assumed that the hydrodynamic coefficients are <u>frequency independent.</u>

This will be relaxed later!

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

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

2

## Rigid-Body Equations of Motion

![](images/a6987b94b8d7d60990362601d447b2456e37823fdba7825363bc8579bf93f798.png)

Newtonian Formulation (Body Frame)

where

<em><strong>M</strong>RB</em> rigid-body system inertia matrix

<em><strong>C</strong>RB</em>  rigid-body Coriolis/centripetal matrix

*Rigid-body system inertia matrix*

<em>See</em> <em><strong>Fossen (1994, 2002</strong>) for parameterizations of</em> <em><strong>C</strong>RB</em>

The generalized forces on a floating vessel are <u>superpositioned</u>:

Hydrodynamic radiation-induced forces + viscous damping

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

3

## Radiation-Induced Hydrodyn. Forces

- Forces on the body when the body is forced to oscillate with the wave excitation frequency and there are <u>no incident waves</u> (Faltinsen 1990):
    1. *Added mass* due to the inertia of the surrounding fluid
    2. Radiation-induced (linear) *potential damping* due to the energy carried away by generated surface waves
    3. Restoring forces due to *Archimedes* (weight and buoyancy)

<strong>Faltinsen (1990).</strong> <em>Sea Loads on Ships and Offshore Structures</em>, Cambridge.

“hydrodynamic mass-damper-spring”

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

4

## Added Mass and Inertia

![](images/ddec99524292799410562b7651887c57732bc723c4b09d6a2386f219b369d11b.png)

- Fluid Kinetic Energy
- The concept of fluid kinetic energy:
- can be used to derive the added mass terms.
- Any motion of the vessel will induce a motion in the otherwise stationary fluid. In order to allow the vessel to pass through the fluid, it must move aside and then close behind the vessel.
- Consequently, the fluid motion possesses kinetic energy that it would lack otherwise (**Lamb 1932**).

03/09/2007

5

One-day Tutorial, CAMS'07, Bol, Croatia

## 6 DOF Body-Fixed Representation for Added Mass  (Includes Coriolis/Centripetal Terms due to Added Mass)

![](images/fe5edd48c16864c15bf03657441bec50309f8fbec9d69779d768c7e87674fd88.png)

**Kirchhoff's Equations (1869)**

kinetic energy due

to the fluid

![](images/23aa4e2096c95f900320caa1a583f1c2a42be99f1f5eb93f99afb6cdc417ea27.png)

***CA(n)***

***MA***

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

6

## Viscous Hydrodynamic Damping

- In addition to potential damping we have to include other <u>dissipative viscous terms</u> like <em>skin friction, wave drift damping etc</em>:

- Total *hydrodynamic* *damping matrix*:

- The hydrodynamic forces and moments       can be now be written as the sum of                 :

![](images/5299b380797de2e38067d694178aeb935d9b4a6607b4d9eb088bf9033d7b15d3.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

7

## Equations of Motion

The resulting model is (frequency-independent coefficients):

![](images/65007c983de27876f8293d2abe4c3121f8fde1bd299e2684d95a9b7c59c4445d.png)

![](images/f20ee8f59ee386dd66951c4830e8be655e924ff52f07c05506e36c24f94e0e43.jpg)

*System inertia matrix including added mass*

Linear mass-damper-spring

(frequency-independent)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

8

## Manoeuvring Hydrodynamics

In <u>classical manoeuvring theory</u>, the forces are modelled at a general non-linear function:

A particular affine parameterization is then used, and the coefficients are estimated linear regression from the data.

The disadvantage of this model representation to a energy-based (Lagrangian) approach is that model reduction, symmetry/skew-symmetry properties, positive matrices, etc.  are difficult to exploit in simulation and control design.

This model can, however, be related to the <u>Lagrangian model</u>: as shown by Ross et al. 2007:

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

9

## Parameterisations

Two types of parameterisations for the hydrodynamic forces are generally used in classical manoeuvring theory:

- Truncated Taylor-series expansions:
    - Davison and Shiff (1946): 1st-order (linear) terms.
    - Abkowitz (1964): odd terms up to 3rd  order.

- 2nd -order modulus
    - Fedyaevsky and Sobolev (1963)
    - Norrbin (1970)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

10

## Parameterisations

- 2nd -order modulus

- Taylor-series

![](images/7a5d402ca911efd4501750db78570273a2c67dd883f129bd8e3484292f1d4e6e.png)

![](images/fcc54bf569d57da36fe2b710a67b89f0b13c4cd852196dc94ce4469d192a0913.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

11

## Parameterisations

As commented by *Clarke (2003),*

- Taylor expansions give rise to a smooth representation of the forces, but have no physical meaning.

- 2nd-order modulus expansions represent well the hydrodynamic forces at angles of incidence: <u>cross-flow drag</u>.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

12

## Taylor-Series Expansions

Where the partial derivatives are taken at an equilibrium:

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

13

## Model of Abkowitz (1964)

![](images/7c554036bec048d92472ada092e1af6cbdff031ccd51a8b01d636c47997000aa.png)

The coefficients are called hydrodynamic derivatives.

Many terms are set to zero by exploiting physically properties. If not, there will thousands of coefficients.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

14

## Model of Norrbin (1970)

![](images/8b5584736a385803dbe01c1abc211764ad74959dcb014963ce0259e0b7f3268b.jpg)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

15

## 2nd-Order Modulus

From Blanke and Christiansen (1986):

![](images/be2163bfe56b5768fe4a5566a3edf724d1da128f3fa9b5868a11dd03851033b9.jpg)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

16

## Measurement of Hydrodynamic Derivatives

PMM

- Experiments with model tests.
- Full scale sea trials and system identification.
- Theoretical prediction methods.
- Regression analysis results from similar designs.

Model tests that can be performed

- Straight line in a towing tank,
- Rotating arm,
- Planar motion mechanism PMM,
- Oscillator tests,
- Free running (radio controlled).

![](images/1f3d48bc41896fbfe654affbd377c431aa6343eae1d22889ec0ba5e636a26492.png)

![](images/c36f79d29b43da48dc3bba1ae5cae85c4a320433816c3aa8f61608e55a6e7a14.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

17

## Experimental Methods

***Model testing in Peerlesspool in London***

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

18

## Measurement of Hydrodynamic Derivatives

![](images/2a540eed895eb60e5116e33c9192556290f830df44c078c1494a7c3245214369.png)

Rotating arm

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

19

## Typical Tests

![](images/640d95e7c1de9d908ec4bb3515e630b888457b7f36e0beb976ae3f0bc4c94750.png)

Pure Sway:

Pure yaw:

Drift and yaw:

Different tests are used to fit different parts of the model.

![](images/093f78a36ebd3d1a6f594a784acfb3f410a20dcc179c1795d2b06f15118d9366.jpg)

![](images/6b897eab7e60e10c81fb806daed4e794754d078a768bdb760ba36b743e116258.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

20

## Measurement of Hydrodynamic Derivatives

During the model tests, the model is forces to move and forces velocities and accelerations are recorded.

Then the hydrodynamic derivatives are estimated from regression analysis.

![](images/8f19b17499289a9c24d513a2fdfc61bb550a0b4599a2ad3b8cb3671008227cdb.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

21

## A Novel 4 DOF Manoeuvring Model

Ross et. al. (2007)  has reassessed the manoeuvring models in the literature, and formulated a novel 4 DOF (surge, sway, roll, yaw) <u>Lagrangian model</u> using first principles and superposition of:

- Potential (added mass)
- Circulation effects: lift and drag
- Effect of roll on circulation effects
- Cross-flow drag.

The advantage of the Lagrangian model is its vector representation which is tailor made for <u>energy-based control design (Lyapunov)</u>.

![](images/2781b4720365103c9164e4d429e6beb224b09cf84dc85de5b9767c692daa7532.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

22

## Added Mass and Coriollis

The 4 DOF solution of Kirchhoff’s equations can be expressed as (Fossen, 2002)

![](images/ff2c39c2903f75d348db1ce724087b8316130b0e7df24817655815f3c96ccf76.png)

Added mass

Added mass Coriollis and Centripetal terms

![](images/703c3b2327a2dc6c9841f35c1ae1ca29d0a286c2cf33fc5ca1e92f8a14d2f820.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

23

## Model of Ross et al. (2007)

Circulation effects (lift and drag), effect of roll on circulation effects and cross-flow drag (modulus representation) are derived in Ross et al. (2007):

where the components are:

![](images/5a406a4d1195ae67e8da7c78bd70f61a8f6ab59c7e98269a4c7df6c6c9f83b23.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

24

## Manoeuvring Model

Combining all the terms in a matrix  for, we obtain the manoeuvring equations in Lagrangian form (Fossen 1994, 2002).

![](images/2781b4720365103c9164e4d429e6beb224b09cf84dc85de5b9767c692daa7532.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

25

## Model Validation with PMM Data

To validate the model, Ross et al. (2007) used data of several PMM tests, and perform a regression based on the model structure derived.

Then compared the fit with that of a model fitted by a tank testing facility to the same dataset.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

26

## Fitting Using PMM Data @ 30kt

![](images/725d97fcc5cda614de0d090a11aa289c819da83f60c9abb5fe21ab8d993d2501.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

27

## Validation in Full Scale (Perez et al.,2007)

Perez et al. (2007) fitted a simplified model to data recorded on full scale manoeuvres of Austal’s Trimaran Hull 260.

![](images/baec1babc4e209fd51f08aadbe6330b248b8de34aec293dc7ece65af30777d5c.png)

The parameters were fitted with data of a 20-20 zig-zag test, and then the model validated with data of a 10-10 zig-zag test.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

28

## Simplified Model

The model was simplified according to the that of Blanke (1981). This was done because the excitation signal was not rich enough to estimate all the parameters—the zig-zag test is not designed for system identification!

![](images/a09378a2d9997adedad82491323ae7c5c34cce02f690f38e6ddff0afd3a02ca7.png)

![](images/8522382e6e3ef9dc6a000ab0a796f0bd88337dff25abaa5e929c26164e27d8fe.png)

![](images/9a1a28321278b6d56110a001375dcc18812f8962f2f62a39f5af2e8e65349857.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

29

## Model Fitting (20-20 ZZ)

![](images/baec1babc4e209fd51f08aadbe6330b248b8de34aec293dc7ece65af30777d5c.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

30

## Model Validation (10-10 ZZ)

![](images/baec1babc4e209fd51f08aadbe6330b248b8de34aec293dc7ece65af30777d5c.png)

![](images/fefda89748f4986584a3fcc7097c2f25c393741ea92464dd520eee8a9e6c56bf.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

31

## Effects of Currents

In some applications, where positioning is important, the effects of current must be considered:

The current has to effects, which are represented with the velocity of the vessel relative to the current velocity:

- Potential: The Munk moment is incorporated in the added mass Coriollis-Centripetal terms.
- Viscous: eddy making and skin friction. These are incorporated in the cross-flow drag.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

32

## References

- Davidson, K. S. M. and L. I. Schiff (1946). “Turning and Course Keeping Qualities.” Transactions of SNAME.

- Abkowitz, M. A. (1964). “Lectures on Ship Hydrodynamics - Steering and Manoeuvrability.” Technical Report Hy-5. Hydro- and Aerodynamic Laboratory. Lyngby, Denmark.
- Fedayevsky, K.K. and G.V. Sobolev (1963). “Control and Stability in Ship Design.” State Union Shipbuilding Publishing House. Leningrad, USSR.

- Norrbin, N. (1971). “Theory and observations on the use of a mathematical model for ship manoeuvring in deep and conned water.” Technical Report 63.Swedish State Shipbuilding Experimental Tank. Gothenburg.

- Clarke, D. (2003). “The foundations of steering and manoeuvring.” In: Proceedings of the IFAC Conference on Control Applications. Plenary talk.
- Ross, A., T. Perez, and T. Fossen  (2007) "A Novel Manoeuvring Model based on Low-aspect-ratio Lift Theory and Lagrangian Mechanics." IFAC Conference on Control Applications in Marine Systems (CAMS). Bol, Croatia, Sept.
- Blanke, M. (1981). Ship Propulsion Losses Related to Automated Steering and Prime Mover Control. PhD thesis. The Technical University of Denmark, Lyngby.
- Christensen, A. and M. Blanke (1986). A Linearized State-Space Model in Steering and Roll of a High-Speed Container Ship. Technical Report 86-D-574.Servolaboratoriet, Technical University of Denmark. Denmark.

- Perez,T., T, Mak, T. Armstrong, A.Ross, T. I. Fossen (2007) “Validation of a 4DOF Manoeuvring Model of a High-speed Vehicle-Passenger Trimaran." In Proc. 9th International conference on Fast Transportation. Shanghai, China Sept.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

33