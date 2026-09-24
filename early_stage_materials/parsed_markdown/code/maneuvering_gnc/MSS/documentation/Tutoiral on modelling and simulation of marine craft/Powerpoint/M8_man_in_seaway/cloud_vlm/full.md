## Manoeuvring in a Seaway  (Module 8)

Dr Tristan Perez

Centre for Complex Dynamic Systems and Control (CDSC)

![](images/8962ba0bc872ad077847583e2841494ce51a6476cb145d28b6251702cc8e12a0.jpg)

Prof. Thor I Fossen

Department of Engineering Cybernetics

![](images/e29b613ed08a3f4363bdbd18f84ff9baef4b407f0950166ce6b405c5c0a30cbe.jpg)

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## State of the art

- Manoeuvres are generally performed in calm waters close to ports, but some times are also performed at sea in higher sea states.

- This requires models which can handle manoeuvring and seakeeping.

- The hydrodynamic problem is very complex, and we may still be a long time away from a solution.

- The state of the art uses a combination of manoeuvring and seakeeping models via either

- Motion superposition
- Force superposition

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Frequency-domain seakeeping models

These models can be used to simulate wave-induced ship motion time series:

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Motion superposition model

![](images/2f9ca280f07042b6ff08fc0260a6f691a425a15a368e830b635ecf2f576c77e5.jpg)

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Motion superposition model

- Commonly used in control applications: autopilot, manoeuvring, formation control, rudder roll stabilisation.

- The rationale behind this is that a wave filter rejects the 1st order wave induced motion, and no memory effects are then considered.

- It can be a good assumption in lower sea states.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Force superposition model

Time-domain SK model + nonlinearities.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Force superposition model

- This is an attempt to obtain a unified model for manoeuvring in a seaway.

- Fluid memory effects are incorporated, together with other non-linear effects characteristic of manoeuvring: lift-drag, cross-flow drag.

- These models are based on the Cummins Equation expressed in terms of body-fixed coordinates, and the nonlinear effects are added.

- The Centripetal-Coriollis terms still remain an issue.

- This model is valid provided that the vessel manoeuvres slowly—because part of the model is based on a seakeeping model.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Kinematic transformations {s}-{b}

Following Perez & Fossen (2007)

In {n},

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Kinematic transformations {s}-{b}

Taking the time-derivative

Taking it to {b},

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Kinematic transformations {s}-{b}

Let

Then

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Kinematic transformations {s}-{b}

The angular velocities are related by

$\Leftrightarrow$

In {b}

Combining results

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Kinematic transformations {s}-{b}

Taking small angle approximations

$\Rightarrow$

Hence, we obtain the sought transformation:

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Kinematic transformations {s}-{b}

To relate the accelerations

where

![](images/801af0349b0aff4e5515bf3b2c63f0c9deadac39ad5098b2ffad6848b59a73e4.jpg)

Taking small angle approximations and considering only linear terms

![](images/1fd2d9d82e57f6511e1a691f853d20cf865d2a7ac79950e786d5ea6602ff873a.jpg)

Which is consistent with

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Kinematic transformations {s}-{b}

Velocities:

Accelerations:

![](images/37363954bf1975efe1b97c187f32cb979b54980d9ac1616ee5d3971edd7c8b63.jpg)

Generalised Positions:

Now we can transform the Cummins Equation to {b}.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## RB seakeeping Eq. of motion in {s}

Using the body-fixed perturbation coordinates we have

linear

Non-linear

![](images/56fc4151c8dd2b9e3749e372e5a60009e37fb48dba964cf019e95c4b217dda88.jpg)

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## RB seakeeping Eq. of motion in {s}

We can think the linear-seakeeping equations of motion

as obtained from the body-fixed perturbation equations considering

![](images/f9b09c3ce1132e5d96b3a8056a4424f98ab9db9621b13fce7724a5f336ff45dc.jpg)

NOTE: In the literature, it is commonly said that the seakeeping eq of motion is formulated in {s}, but this would imply that the inertias are time varying.

In our derivation, we formulate them in body-fixed coordinated and then ignore the nonlinear terms; this way, the inertias are constant because we are in body-fixed coordinates.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Cummins Equation in {b}

![](images/4be09e444f53f961847ccb1a0e7219e7275605b4fba8f7dac36ed4badc855aa0.jpg)

$\Updownarrow$

![](images/f9b09c3ce1132e5d96b3a8056a4424f98ab9db9621b13fce7724a5f336ff45dc.jpg)

This model describes deviations from the equilibrium state in {b} within a linear framework and small angles.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Cummins Equation in {b}

Expressed in terms of absolute (instead of incremental) variables:

NOTE: This equation valid provided the manoeuvring is very slow—because of the seakeeping assumptions under which the Cummins eq. was derived.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## Summary

- The problem of manoeuvring in a seaway is still an open problem in ship theory.

- A step towards a unified model for manoeuvring in a sea way consists of expressing Cummins Equation in {b}.

- This is still a seakeeping model, which assumes a state of equilibrium from which the vessel is disturbed; and therefore, it may be use it for slow manoeuvring.

- For slow manoeuvring, we can add Lift-Drag effects as a first approximation.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>

## References

- Perez, T. and T. I. Fossen (2006) “Time-domain Models of Marine Surface Vessels  Based on Seakeeping Computations.” 7th IFAC Conference on Manoeuvring and Control of Marine Vessels MCMC, Portugal, September.

- Perez T., and T. I. Fossen (2007) “Kinematic Models for Seakeeping and Manoeuvring of Marine Vessels at Zero and Forward Speed.” To appear in Modeling Identification and Control (MIC), Norwegian Research Bulletin, Trondheim. MIC Vol 28, 2007, No 1.

06/06/26

One-day Tutorial, CAMS'07, Bol, Croatia

<number>