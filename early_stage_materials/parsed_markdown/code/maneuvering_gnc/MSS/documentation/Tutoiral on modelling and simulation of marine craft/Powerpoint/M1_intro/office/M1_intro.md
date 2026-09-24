## Modelling and Simulation of Marine Surface Vessel Dynamics (Module 1: Motivation and Overview)

Dr Tristan Perez

Centre for Complex Dynamic Systems and Control (CDSC)

Professor Thor I Fossen

Department of Engineering Cybernetics

![](images/8962ba0bc872ad077847583e2841494ce51a6476cb145d28b6251702cc8e12a0.jpg)

![](images/e29b613ed08a3f4363bdbd18f84ff9baef4b407f0950166ce6b405c5c0a30cbe.jpg)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

1

## Tutorial Goals

Model vessels and environmental loads in 6 DOF.

Use state-of-the-art hydrodynamic codes to compute model parameters: added mass, potential damping, 1st and 2nd-order wave loads.

Derive control plant models by postprocessing data from hydrodynamic codes (Matlab GNC toolbox).

Use system identification to fit hydrodynamic data to state-space models.

Add viscous effects/manoeuvring terms.

Time-domain simulation in Matlab Simulink.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

2

## Applications

![](images/4eba21ce1689e05c3983a8fbd45d44ebe4ee128c40a387dca78237538dfdf9c3.jpg)

![](images/e621c7609da9b52fbfadd7a64e9c7c0d9284d563e6849d1e5452c9f125701e25.jpg)

![](images/86742121ff1605b6fcf966b2ca709191ba516e7ccb32fa036846539bf97f1a4b.jpg)

![](images/4b832569d5fb64f98ba1065894d97448b6f1629236cf75d8bdd05894935e4a1f.jpg)

![](images/db74f6b04134f436d8a3e55526532e4fbd46680951b8d9ebddf4586e18216b4a.jpg)

![](images/4756ac32911bb1bc07082a0526c51eed3d56b2a4ef7db471a82a989dbd2c39f5.jpg)

![](images/dd3c1b60471b789c2f3e45ecff93e0ff655fba48ba093a2ccfe8ddf5f243d32b.jpg)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

3

## Modelling and Control

- System designers make decisions to satisfy conflicting requirements based on some knowledge of the system they intend to design: this knowledge is represented in a mathematical model.
- Modelling is an essential part of control design and preliminary testing, which can consume up to 60% of effort in these tasks.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

4

## Modelling of Marine Structures

- Models of marine structures are complex.
- Control engineers often base their models on models used by naval architects, which sometimes are not control-design oriented.
- In this tutorial, we will look at the models commonly used in naval architecture and ship theory from the control system’s perspective.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

5

## Obtaining Models

Data-base

Model testing

Scaling

System

Identification

Main focus of this tutorial

**Mathematical**

**Models**

(Simulation,GNC-design

HIL-testing, Diagnosis)

System

Identification

System

Identification

Numerical

Hydrodynamics

Full-scale

Experiments

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

6

## Manoeuvring and Seakeeping

Ship theory has traditionally been separated into two main areas

<table>
  <tr>
    <th>Manoeuvring
The aim is to study steering characteristics of vessels with forward speed and the response to the command of propulsion systems and control surfaces. This is done in calm water.</th>
    <th>Sea-keeping
The aim is to study the behavior of the vessel in waves while keeping a constant speed and course.</th>
  </tr>
</table>

Although both areas are concerned with the study of *motion*, *stability* and *control*, the separation allows one making assumptions that simplify the study in each case.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

7

## Manoeuvring Models

- Nonlinear parametric models (classical and Lagrangian):

- Obtained by fitting data from scaled model experiments.
- Calm water models.
- Horizontal motion models (surge-sway-yaw).
- Not commonly available.
- Restricted to a few speeds/loading conditions of the experiment.

![](images/1f3d48bc41896fbfe654affbd377c431aa6343eae1d22889ec0ba5e636a26492.png)

![](images/8f19b17499289a9c24d513a2fdfc61bb550a0b4599a2ad3b8cb3671008227cdb.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

8

## Seakeeping Models

![](images/4003be491fbc8e6b6eb38bbe59bf682c6599d10c14568bb274de8d6fe3258e35.jpg)

Linear non-parametric models

Obtained from hydrodynamic calculations based on simplifying assumptions:

- Constant course and speed.
- Linear wave loads.
- Potential theory.
- Viscous effects can be added.

For the design of control systems, seakeeping models are very useful.

They provide preliminary models based on little data of the ship.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

9

## Recent Results on a Unified Manoeuvring and Seakeeping Model

- <strong>Fossen, T. I. and Ø. N. Smogeli.</strong> Nonlinear Time-Domain Strip Theory Formulation for Low-Speed Manoeuvring and Station-Keeping, <em>Modelling, Identification and Control,</em> <strong>MIC-25</strong>(4):201:221, 2004.
- <strong>Fossen, T. I.</strong> A Nonlinear Unified State-Space Model for Ship Manoeuvring and Control in a Seaway, <em>Journal of Bifurcation and Chaos</em>, September 2005. (Plenary Talk ENOC'05, Eindhoven, The Netherlands).
- **Perez, T. and T. I. Fossen.**  Kinematic Models for Sea-keeping and Manoeuvring of Marine Vessels. Modelling, Identification and Control, **MIC-28**(1):1-12, 2007.
- <strong>Perez, T. and T. I. Fossen.</strong> Time-Domain Models of Marine Surface Vessels for Simulation and Control Design Based on Sea-keeping Computations (Plenary Talk). <em>Proc. of the IFAC MCMC'06, Lisbon, Portugal, September 20-22, 2006.</em>
- **Ross, A., T. Perez and T. I. Fossen .** A Novel Manoeuvring Model Based on Low-Aspect Ratio Lift Theory and Lagrangian Mechanics. Proc. of the IFAC CAMS'07, Croatia.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

10

## Unified Manoeuvring and Seakeeping Model for Time-Domain Simulation

<strong>The</strong> <em><strong>Force-Transfer-Functions</strong></em> <strong>are computed using hydrodynamic SW (WAMIT, VERES or SEAWAY )</strong>

![](images/f20ee8f59ee386dd66951c4830e8be655e924ff52f07c05506e36c24f94e0e43.jpg)

![](images/a9eacf6ae97b3ee384cea112d6fab52ec7b8801d63db5616e5ebf4cf8caaef54.png)

*For 6 DOF this model will typically be represented by* *6 + 6 + 90 = 102 ODEs*

*which are computed using*

***hydrodynamic SW (WAMIT, VERES or SEAWAY )***

*These terms are found using experimental results/curve fitting or semi-empirical methods*

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

11

## Speed–Environment Envelope

Hull supported by mostly by hydrostatic pressure (forces)

![](images/4756ac32911bb1bc07082a0526c51eed3d56b2a4ef7db471a82a989dbd2c39f5.jpg)

![](images/e621c7609da9b52fbfadd7a64e9c7c0d9284d563e6849d1e5452c9f125701e25.jpg)

![](images/6ace22c5dc2d9d0441bbe154d32ee2af26100ad6cbee4b96e1859f53227b7f58.jpg)

![](images/745c78c6f1c10005c8bafafb8a7af9ab4cb43c8b2ae82304d3842e743b7a82d2.jpg)

Hydrostatic and hydrodynamic forces; Lift

![](images/6a5ab88da1f8f2ad36abc706ae7eab14e716565a807d367bee24c3e550f8e692.jpg)

Aero and hydrodynamic forces; strong flow separation

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

12

The 3 Speed Regimes for Control

**Dynamic positioning systems**

- 3D potential theory
- 2D potential theory (strip theory)

**Manoeuvring/motion damping**

- 2D potential theory (strip theory) up to *Froude numbers* of 0-3-0.4
- 2.5 D potential theory for high-speed craft

![](images/e621c7609da9b52fbfadd7a64e9c7c0d9284d563e6849d1e5452c9f125701e25.jpg)

![](images/1ad3eb9d37c4f77ffc1aa8eebc6193f965fe3ac62aae440a7275d519fd442254.jpg)

![](images/2be45ccc87066e09559e9f0209a5d88d1814bdd5b1104a45eae6b3210b147ac7.jpg)

Manoeuvring at moderate speed

(transit)

Manoeuvring at high speed

(high-speed craft)

Low-speed

maneuvering

Station-keeping

0

03/09/2007

1.5 m/s (3 knots)

….

One-day Tutorial, CAMS'07, Bol, Croatia

…..

*Speed*

13

## Motion in Waves

Motions and loads of floating structures due to waves can be separated into

- Wave-frequency: linearly excitations and motion in the wave frequency range. Periods in the range 5-20s
- Higher than wave frequency (ringing & springing): nonlinear effects, which can produce resonance in TLPs, with natural periods of 2-4s.

- Slow and mean drift: nonlinear effects with mean value and sub harmonic excitation that can produce oscillations with natural periods of 20-30s.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

14

## Motion and Control

Then, motion control problems can have different objectives:

- ***Control only the non-oscillatory  motion (wave filtering needed)***
    - Autopilots,
    - Dynamic positioning (DP)
    - Thruster assisted position mooring (TAPMOOR)
- ***Control only the oscillatory motion***
    - Ride control of high speed vessels (roll and pitch stabilisation)
    - Heave compensation of offshore structures
- ***Control both***
    - Dynamic positioning in extreme seas (DP + roll & pitch stabilisation)
    - Autopilots with rudder roll stabilisation
    - Unmanned Surface Vehicles USV

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

15

## The Road Ahead

<table>
  <tr>
    <th>Time</th>
    <th>Topic</th>
    <th>Presenter</th>
  </tr>
  <tr>
    <td>09:00</td>
    <td>M1: Motivation and overview</td>
    <td>TIF</td>
  </tr>
  <tr>
    <td>09:20</td>
    <td>M2: Hydrodynamics for control engineers</td>
    <td>TP</td>
  </tr>
  <tr>
    <td>10:00</td>
    <td>M3: Kinematics and kinetic models of marine vessels</td>
    <td>TP</td>
  </tr>
  <tr>
    <td>10:45</td>
    <td>Coffee break</td>
    <td></td>
  </tr>
  <tr>
    <td>11:00</td>
    <td>M4: Manoeuvring in calm water</td>
    <td>TIF</td>
  </tr>
  <tr>
    <td>11:30</td>
    <td>M5: Environmental disturbances</td>
    <td>TP</td>
  </tr>
  <tr>
    <td>12:00</td>
    <td>Lunch break</td>
    <td></td>
  </tr>
  <tr>
    <td>13:00</td>
    <td>M6: Motion in waves a frequency-domain approach</td>
    <td>TP</td>
  </tr>
  <tr>
    <td>13:30</td>
    <td>M7: Motion in waves a time-domain approach</td>
    <td>TP</td>
  </tr>
  <tr>
    <td>14:00</td>
    <td>M8: Manoeuvring in a seaway</td>
    <td>TP</td>
  </tr>
  <tr>
    <td>14:30</td>
    <td>M9: Models and marine control problems</td>
    <td>TIF</td>
  </tr>
  <tr>
    <td>15:00</td>
    <td>M10: Software, and rapid model prototyping</td>
    <td>TIF</td>
  </tr>
</table>

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

16