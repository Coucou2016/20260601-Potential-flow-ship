## Ship Motion Control and Models   (Module 9)

Dr Tristan Perez

Centre for Complex Dynamic Systems and Control (CDSC)

Prof. Thor I Fossen

Department of Engineering Cybernetics

![](images/8962ba0bc872ad077847583e2841494ce51a6476cb145d28b6251702cc8e12a0.jpg)

![](images/e29b613ed08a3f4363bdbd18f84ff9baef4b407f0950166ce6b405c5c0a30cbe.jpg)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

1

## Guidance, Navigation and Control  (GNC)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

2

## Guidance, Navigation and Motion Control

<strong>Guidance:</strong> <em>is the action or the system that continuously computes the reference (desired) position, velocity and acceleration of a vessel to be used by the control system. These data are usually provided to the human operator and the navigation system.</em>

<strong>Navigation</strong> is derived from the Latin navis, "<em>ship</em>," and agere, "<em>to drive</em>." It originally denoted the art of ship driving, including steering and setting the sails.  This includes planning and execution of safe, timely, and economical operation of ships, underwater vehicles, aircraft, and spacecraft.

<strong>Control:</strong> <em>is the action of determining the necessary control forces and moments to be provided by the vessel in order to satisfy a certain control objective.</em>

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

3

## Guidance system

Generates the desired trajectories (position, velocity and acceleration).

- <em><strong>The waypoint generator</strong></em>  establishes the desired wayponits according to mission, operator decision, weather, fleet operations, amount of power available <em>etc.</em>
- ***The waypoint management system*** updates the active waypoint based on the current position of the ship.
- ***The reference computing algorithms*** generate a smooth feasible trajectory based on a reference model, the ship actual position, amount of power available, and the active way point.

![](images/9c55aec9185fc0fd38ff365cf00aa50e7afd97d618362e5f8749b2d6bc9e2de2.png)

![](images/7ec29c60278047120712320a401fe8d5cd8fb5f3fc12eb5bb8d0ad2722ca29a4.png)

03/09/2007

4

One-day Tutorial, CAMS'07, Bol, Croatia

## Navigation System

Generates appropriate feedback signals

- <em><strong>Sensors</strong></em>  Satellite navigation systems, GPS, radar, gyros, accelerometers,      compass, HPR, <em>etc.</em>
- ***Signal quality checking***  Statistic analysis, fault detection, voting, data fusion.
- ***Reference frame transformation***  translate the motion to that of    the origin of the adopted reference frame.

**SATELLITE**

**NAVIGATION**

**SYSTEM**

**(DGPS / GLONAS)**

**SURFACE**

**REFERENCE**

**SYSTEM**

***VRU***

**TAUT**

**WIRE**

**HYDROACOUSTIC**

**POSITIONING**

**SYSTEM**

***GPS ANTENNA***

03/09/2007

***HPR TRANSDUCER***

One-day Tutorial, CAMS'07, Bol, Croatia

5

## Set-point Regulation, Trajectory Tracking Control or Path Following Control?

- <strong>Set-Point Regulation:</strong> The most basic guidance system is a <u>constant input_</u>(<u>set-point</u>) provided by a human operator. The corresponding controller will then be a regulator. Examples of set-point regulation are constant depth, trim, heel and speed control, etc.
- <strong>Trajectory Tracking Control:</strong> The objective is for the position and velocity of the vessel to track given desired time-varying position and velocity reference signals. The corresponding feedback controller must then be a trajectory tracking controller. Tracking control can be used for course-changing maneuvers, speed changing, attitude control, etc. An advanced guidance system computes optimal time-varying trajectories from a dynamic model and a predefined control objective. If a constant set-point is used as input to a low-pass filter (<u>reference model</u>) the outputs of the filter will be smooth time-varying reference trajectories for position, velocity and acceleration (PVA).
- **Path Following Control:** Follow a path in 3D independent of time (geometric assignment). In addition, a dynamic assignment (speed/acceleration) along the path can be assigned. The corresponding controller is a path following/maneuvering controller.

03/09/2007

6

One-day Tutorial, CAMS'07, Bol, Croatia

## Ship Motion Control

The  task of a ship motion control system consists of making the ship to track/follow a *desired trajectory* or *path.* Sometimes this also includes motion damping.

In most ship operational conditions, the desired trajectory is slowly varying motion  (LF motion) compared to the oscillatory motion induced by the waves (WF motion).

+

=

Total motion

Oscillatory motion

(due to 1st order Wave induced loads)

Slowly varying motion

(due to 2nd Wave loads, current, wind)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

7

## Ship Motion Control Objectives

Due to the motion of ships, motion control problems can have different objectives:

- <em><strong>Control only the LF motions</strong></em>  <strong>(Autopilots, Dynamic Positioning (DP), Position mooring systems)</strong>

- <em><strong>Control only the WF motions</strong></em>  <strong>(Heave, roll and pitch stabilisation, ride control)</strong>

- ***Control both  (DP with roll and pitch stabilisation in high seas, course keeping and roll stabilisation)***

Roll stabilisation

Dynamic Positioning

Autopilot

![](images/68b59d399442ef45dd3c34236db4161128701deebcf18a8c2bbaf1068fa75a2d.png)

![](images/57ec0edf6328c00b7ddb63768a387b0fd628257141d4b0d13cfddc1c6bd6dc76.jpg)

![](images/22a4e6a9990d36f640b64d2e84b8f1ad0d92e02a77ab165e929c737aaa5f712f.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

8

## Plant Control System

Generates appropriate actuator commands.

- <em><strong>Wave filter (observer):</strong></em>  <em>Recover slowly varying motion signals from the total measurements</em>
- ***Controller:***    Generates force commands (desired control action)
- ***Control allocation:***  Translate force commands into actuator commands (RPM, PWR, Torque).

![](images/2486077c0f74209b4edb9c86da809c61684b324b4abadb8baa3d796851eb3676.jpg)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

9

## Wave Filtering

Removes first order (oscillatory) wave-induced motion

Example course autopilot wave filtering Perez (2005):

![](images/3dd4a495989ec54bb600810664faf51df3936240db4e4122203927175cab578f.png)

Heading angle

Heading rate

Rudder angle

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

10

## Control Allocation

Some marine control systems are over-actuated to guarantee reliability and high performance – optimization problem

Force and moments

Actuator command

Control demand

![](images/a4155339028d943258565de4b7d6ebd83ed0f7972da46ae404bcfe62aa55c1ba.jpg)

Actual control action

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

11

## Marine Control Problems and Models

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

12

Geological

survey

Heavy lift

**operations**

Pipe and cable

**laying**

Position

**mooring**

![](images/a67ceadd2f474c2b49642916cb0a25e981eb5f936ceaf0180f524f1fda45f13c.jpg)

![](images/2fb3330fb4eb9dc6df2cd5fc9aa1d9b864161ebdede84b35d02ae1a88d60600c.jpg)

ROV operations

Cable laying

vessel

Vibration

control

of marine

risers

Pipe laying vessel

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

13

## Trajectory Tracking & Maneuvering Control

![](images/4422ecdd03d302fea4dfd1162fc75d9540e369bfadc619faef85d669d2d62f13.jpg)

![](images/4756ac32911bb1bc07082a0526c51eed3d56b2a4ef7db471a82a989dbd2c39f5.jpg)

Fully actuated supply ship cruising at low speed.

Underactuated container ship in transit.

![](images/dd3c1b60471b789c2f3e45ecff93e0ff655fba48ba093a2ccfe8ddf5f243d32b.jpg)

Italian supply ship **Vesuvio** refueling two ships at sea.

Courtesy: Hepburn Eng. Inc.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

14

## Formation Control/Underway Replenishment

![](images/0b6f5e1949756f0fe409653b839e999297b0a9f5fda400ac226f1629a163da3e.jpg)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

15

## Interdisciplinary: Rocket Launch / DP system / THCS

*Assembly Command Ship*

*Launch Platform*

![](images/a05f0d60901f974e5179cfd52d70983f51930afd4bfeac3c61f574d09054bbaa.jpg)

![](images/c2a07c2daea83a9056d884bf4884376bc8cb1a4794fd0874f5dfff13eb328528.jpg)

03/09/2007

16

One-day Tutorial, CAMS'07, Bol, Croatia

## Trim & Heel Correction System (THCS)

### **Process Control**

### **or**

### **Marine Control?**

![](images/352fe0e9e4a1d5307a6c96179881c9590a67261634ae1599c31be05e94fc797d.png)

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

17

## Dynamic Positioning

Drilling vessel (Regulation)

ROV operations (tracking)

![](images/a444c850a72bced32a8361924ae853e55758b618af1d001d771ee0c8b991b0c8.jpg)

![](images/68b59d399442ef45dd3c34236db4161128701deebcf18a8c2bbaf1068fa75a2d.png)

- Control objective: Keep position; follow slow changes in set point.

- DOF: 1,2,6 (surge, sway and yaw) [pitch and roll can be incorporated in high sea states in offshore rigs]
- Model: time-domain model which includes cross-flow drag effects. The Munk moment, which is in the added mass Coriollis-centripetal terms should be added. Alternatively, use current coefficients (experimental data).

- Disturbances: Wind, current, mean wave drift and slowly varying wave forces.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

18

## Course and Heading Autopilots

Course keeping

Heading

![](images/9c55aec9185fc0fd38ff365cf00aa50e7afd97d618362e5f8749b2d6bc9e2de2.png)

![](images/22a4e6a9990d36f640b64d2e84b8f1ad0d92e02a77ab165e929c737aaa5f712f.png)

- Control Objective: Keep heading or course. For course keeping autopilots, positioning control and guidance systems must also be designed (outer loop).

- DOF: 2,[4], 6  (sway, roll, yaw) There is strong coupling between sway and yaw which is not convenient to ignore, and roll also affect these modes.

- Model: Manoeuvring model; at high speed lift-drag effects are significant. The model can be linearised for control design because the must operate close to equilibrium conditions.

- Disturbances: Wind, waves (there must be a wave filter); for a course keeping autopilot, current is also a disturbance.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

19

## Manoeuvring Control

![](images/7ec29c60278047120712320a401fe8d5cd8fb5f3fc12eb5bb8d0ad2722ca29a4.png)

- Control objective: geometric and dynamic conditions for path following, way-point or trajectory tracking.

- DOF: 1,2,[4],6.

- Model: nonlinear manoeuvring model.
- Disturbances: wind, waves, current.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

20

## Ride Control

![](images/0b975d8a69bfae6d36799f59fbcbe56ef02e814ccf757006739a54299cb7fdc6.jpg)

![](images/6ace22c5dc2d9d0441bbe154d32ee2af26100ad6cbee4b96e1859f53227b7f58.jpg)

- Control objectives: reduce roll and pitch.

- DOF: 4,5.

- Model: linear time-domain model, with viscous corrections for roll.

- Disturbances: 1st order wave induced motion; wind, trim variations with speed.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

21

## Heave Compensation

![](images/f3076d4ffc890a815f1b8fb179655de7ef7b90e1621ba825f343d9b8cb21c864.png)

![](images/88f62ee458ff4956946671c56b51ad6127ddea0f263786ef34e2679fd98aeb05.png)

![](images/d360bf10ae97efd45272de638755a566c38db1f3e4fa2987a7099c57e2a9daf0.png)

- Control objective: reduce the effect of heave motion in different components of the system.

- DOF: 3,[5].

- Model: linear time-domain model + nonlinear viscous effects and structural stiffness.

- Disturbances: 1st order wave-induced motion, and rapidly-varying 2nd order wave-induced motions

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

22

## Ship-to-Ship Operations

![](images/3c5a997fe935f53d290d5b9bdd8458fda700948a9ee4a46d070af930c99b48ab.jpg)

![](images/edc42f55babc3a383f45ed669e9ebddbfc435d7d727c1e17fb88a8014bb1ecf8.jpg)

- Control objective: keep formation.
- DOF: 1,2,6.
- Model: time-domain model with <u>ship-to-ship hydrodynamic interaction if vessels are too close.</u>
- Disturbances: waves, wind, current

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

23

## Modelling Disturbances for Control Design

If a model-based control design requires disturbance modelling,

### **Waves:**

- 1st-order wave loads (due to wave spectrum) can be modelled using multi-sinces with random phases or filtered white noise (wave spectrum).
- Mean wave drift loads can be modelled as a 1st-order Wiener process (1st-order system driven by white noise.)

### **Currents:**

- Current loads can be included using the concept of relative velocity in surge, sway and yaw (in DP current coefficients can also be used)

### **Wind:**

- Wind loads are included using wind coefficient tables.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

24

## Wind Loads

- Wind areas and centroids from digitized GA
- For best results experimental data from wind tunnels should be used.

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

25

## Example: Simulation of Wave Loads in DP

Modelled as filtered white noise

Modelled as a Wiener process

For position mooring we need to add the restoring forces due to the mooring lines

![](images/36084cedf12586e2e16b27091b140c68771277419fd81fe9a5f2d456ed180897.png)

### **Osclillatory wave-induced motion**

### **total motion**

## **GNC**

### **Guidance Navigation Control**

### **Measurement noise**

Modelled as Gaussian white noise

This model is typically used to design control and observers.

03/09/2007

26

One-day Tutorial, CAMS'07, Bol, Croatia

## Useful References

- <strong>Fossen, T. I. (1994).</strong> <em>Guidance and Control of Ocean Vehicles</em><strong>,</strong> John Wiley
- <strong>Fossen, T.I. (2002)</strong>. <em>Marine Control Systems</em>. Marine Cybernetics.

- <strong>Perez, T. (2005).</strong> <em>Ship Motion Control</em>. Springer Verlag.

- <strong>Sørensen, A.J. (2005).</strong> <em>“Marine Cybernetics”.</em> Lecture Notes Dept. of Marine Technology, NTNU, Norway

03/09/2007

One-day Tutorial, CAMS'07, Bol, Croatia

27