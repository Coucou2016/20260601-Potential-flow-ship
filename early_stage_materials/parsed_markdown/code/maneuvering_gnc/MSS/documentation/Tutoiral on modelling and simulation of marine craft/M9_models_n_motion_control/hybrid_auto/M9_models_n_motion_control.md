# Sh i p Motion Control a nd Models

## ( M od u l e 9)

## D r Tri sta n P e rez

Centre for Com plex Dynam ic Systems a nd Control (C DSC)

## P rof. Thor I Fosse n

De pa rtme nt of E ng i n ee ri ng Cybernetics

![](images/d433f6cf333559f1ebebeae994efbcd2591950ae0068bf05208834cce20e96ec.jpg)

THEUNIVERSITYOF

NEWCASTLE

AUSTRALIA

![](images/204195144f087a261417572189cf8cdd7c591534c526d7997608670d10f9f943.jpg)

NTNU

Det skapende universitet

## G u ida nce, Navigation a nd Control

## (GNC)

# G u ida nce, Navigation a nd

# Motion Control

G u idance : is the action or the system that continuously computes the reference (desired) position, velocity and acceleration of a vessel to be used by the control system. These data are usually provided to the human operator and the navigation system.

N avi gati o n is d e rived from th e Lati n n avis , " ship , " a n d a g e re , " to drive . " I t o ri g i n a l l y d e noted th e a rt of s h i p d rivi ng , i n cl u d i ng stee ri ng a nd setti ng th e sa i ls . Th is i n cl u d es pl a n n i ng a nd execution of safe , ti me ly, a nd econom i ca l ope ration of s h i ps , u nd e rwate r ve h i cl es , a i rcraft, a nd s pacecraft.

Co ntro l : is the action of determining the necessary control forces and moments to be provided by the vessel in order to satisfy a certain control objective.

![](images/fd985251e2ed497dcac56fc55ff18f932f3f7ecfe1f437da9fdcb317ec22b876.jpg)

<details>
<summary>flowchart</summary>

```mermaid
graph TD
  subgraph Plant
  A["Environmental disturbances\n(wind, waves and current)"] -->|Forces| B["Actuators"]
  B -->|Forces Control action| A
  B -->|Motion| C["Sensors"]
  C --> D["Signal quality checking"]
  D --> E["Reference frame transformation"]
  end

  subgraph Navigation system
  F["Sensors"] --> G["Signal quality checking"]
  G --> H["Reference frame transformation"]
  end

  subgraph Control system
  I["Control allocation solver"] --> J["Actuator command"]
  J --> K["Controller (autopilot, DP, stabiliser)"]
  K --> L["Wave filter (observer)"]
  L --> K
  K --> M["Desired control action"]
  M --> K
  M --> N["State estimation"]
  end

  subgraph Guidance system
  O["Reference computing algorithms"] --> P["Power available"]
  Q["Waypoint management"] --> R["Mission requirements, Operator decision, Weather information, Fleet operation, Power available etc."]
  S["Waypoint generation"] --> T["Mission requirements, Operator decision, Weather information, Fleet operation, Power available etc."]
  U["Power available"] --> O
  V["Position and speed measurements"] --> O
  W["Desired setting (Reference trajectory)"] --> K
  end

  A -.->|Inflow| I
  B -.->|Inflow| I
  I -.->|Inflow| J
  J -.->|Inflow| K
  K -.->|Inflow| L
  L -.->|Inflow| M
  M -.->|Inflow| N
  N -.->|Inflow| K
  K -.->|Inflow| Q
  Q -.->|Inflow| R
  R -.->|Inflow| S
  S -.->|Inflow| T
  T -.->|Inflow| U
  U -.->|Inflow| V
  V -.->|Inflow| W
  W -.->|Inflow| K
```
</details>

## G u ida nce system

Ge n e rates the d esi red traj ectories (position , velocity a nd accel e ration ) .

 The waypoint generator establ ishes the d esi red waypon its accord i ng to m ission , operator d ecision , weather, fl eet operations , a mou nt of power ava i la bl e etc.  
 The waypoint management system u pdates the active waypoi nt based on the cu rre n t pos i ti o n of th e s h i p .  
The reference computing algorithms generate a smooth feasi ble trajectory based on a refere n ce mod el , the sh i p actu al position , a mou nt of power ava i la bl e , a nd the active way poi nt.

![](images/a86bc1fdb2a2a8a97c381a17359c9361ec19929bf9519ff73c814ac9f0833e5b.jpg)

NT

Det skapende universitet

## Navigation System

## Generates appropriate feed back sig nals

 Sensors Satel l ite navigation systems , G PS , radar, gyros , accelerometers , com pass , H P R, etc.  
 Signal quality checking Statisti c a na lysis , fa u lt d etection , voti ng , d ata fusion .  
Reference frame transformatio the orig i n of the adopted refere n ce

![](images/8d1d4f03fe34badac2ec68687842cbca926136248fbe7b03563c9069c16953ff.jpg)

<details>
<summary>flowchart</summary>

```mermaid
graph TD
  A["Sensors"] --> B["Signal quality checking"]
  B --> C["Reference frame transformation"]
```
</details>

![](images/8e8a85b850b6ba50c7ec2df29180c5c3365753c1ee4d84af690e3d455a5a15c7.jpg)

<details>
<summary>text_image</summary>

n translate the motion to that of
e frame.
SURFACE
REFERENCE
SYSTEM
SATELLITE
NAVIGATION
SYSTEM
(DGPS / GLONAS)
HYDROACOUSTIC
POSITIONING
SYSTEM
TAUT
WIRE
VRU
GPS
ANTENNA
HPR
TRANSDUCER
</details>

## Set- poi nt Reg u lation, Trajectory Tracki ng Control or Path Fol lowi ng Co ntro l ?

Set-Po i nt Reg u lati o n : The most basi c g u id a n ce syste m is a consta nt i n put (set-poi nt) provid ed by a h u ma n operator. The correspond i ng control l er wi l l the n be a reg u lator. Exa m pl es of set-poi nt reg u lation a re consta nt d e pth , tri m , heel a nd speed control , etc.

Trajectory Tracki n g Co ntro l : The objective is for the position a nd velocity of the vessel to track g iven d esi red ti me-varyi ng pos ition and velocity reference sig nals . The correspond i ng feed back control l er m ust the n be a traj ectory tracki ng control l e r. Tracki ng control can be used for cou rse-chang i ng maneuvers , speed chang i ng , attitud e control , etc. An advanced g u idance system com putes opti mal ti me-varyi ng trajectories from a dyna m i c mod el a nd a pred efi ned control objective . If a consta nt set- po i n t i s u sed as i n p u t to a l ow- pass fi l te r ( refe re n ce m od e l ) th e o u tp u ts of th e fi l te r wi l l be smooth ti me-va ryi ng refe re n ce traj ectories for position , velocity a nd accel eration ( PVA) .

Path Fo l l owi n g Co ntro l : Fol low a path i n 3 D i nd e pe nd e nt of ti me (geometri c assig n me nt) . I n ad d ition , a dyna m i c assig n me nt (speed/accel eration ) along the path ca n be assig ned . The correspond i ng control l er is a path fol lowi ng/ma neuveri ng co n t ro l l e r .

## Sh i p M otion Contro l

The task of a sh i p motion control syste m consists of ma ki ng the sh i p to track/fol low a desired trajectory or path. Someti mes th is a lso i n cl u d es motion d a m p i ng .

I n most sh i p ope rationa l cond itions , the d esi red traj ectory is slowly va ryi ng motion ( L F motion ) com pa red to the osci l l atory motion i nd u ced by the waves (WF motion ) .

![](images/28fdcd9139eb1f25f77b118540438be8afdb63c6d89df22d595712df5df3f521.jpg)

<details>
<summary>line</summary>

| X | Y |
| --- | --- |
| 1 | ~2.5 |
| 2 | ~3.0 |
| 3 | ~2.0 |
| 4 | ~2.5 |
| 5 | ~3.0 |
| 6 | ~2.0 |
| 7 | ~2.5 |
| 8 | ~3.0 |
| 9 | ~2.0 |
| 10 | ~2.5 |
| 11 | ~3.0 |
| 12 | ~2.0 |
| 13 | ~2.5 |
| 14 | ~3.0 |
| 15 | ~2.0 |
| 16 | ~2.5 |
| 17 | ~3.0 |
| 18 | ~2.0 |
| 19 | ~2.5 |
| 20 | ~3.0 |
| 21 | ~2.0 |
| 22 | ~2.5 |
| 23 | ~3.0 |
| 24 | ~2.0 |
| 25 | ~2.5 |
| 26 | ~3.0 |
| 27 | ~2.0 |
| 28 | ~2.5 |
| 29 | ~3.0 |
| 30 | ~2.0 |
| 31 | ~2.5 |
| 32 | ~3.0 |
| 33 | ~2.0 |
| 34 | ~2.5 |
| 35 | ~3.0 |
| 36 | ~2.0 |
| 37 | ~2.5 |
| 38 | ~3.0 |
| 39 | ~2.0 |
| 40 | ~2.5 |
| 41 | ~3.0 |
| 42 | ~2.0 |
| 43 | ~2.5 |
| 44 | ~3.0 |
| 45 | ~2.0 |
| 46 | ~2.5 |
| 47 | ~3.0 |
| 48 | ~2.0 |
| 49 | ~2.5 |
| 50 | ~3.0 |
| 51 | ~2.0 |
| 52 | ~2.5 |
| 53 | ~3.0 |
| 54 | ~2.0 |
| 55 | ~2.5 |
| 56 | ~3.0 |
| 57 | ~2.0 |
| 58 | ~2.5 |
| 59 | ~3.0 |
| 60 | ~2.0 |
| 61 | ~2.5 |
| 62 | ~3.0 |
| 63 | ~2.0 |
| 64 | ~2.5 |
| 65 | ~3.0 |
| 66 | ~2.0 |
| 67 | ~2.5 |
| 68 | ~3.0 |
| 69 | ~2.0 |
| 70 | ~2.5 |
| 71 | ~3.0 |
| 72 | ~2.0 |
| 73 | ~2.5 |
| 74 | ~3.0 |
| 75 | ~2.0 |
| 76 | ~2.5 |
| 77 | ~3.0 |
| 78 | ~2.0 |
| 79 | ~2.5 |
| 80 | ~3.0 |
| 81 | ~2.0 |
| 82 | ~2.5 |
| 83 | ~3.0 |
| 84 | ~2.0 |
| 85 | ~2.5 |
| 86 | ~3.0 |
| 87 | ~2.0 |
| 88 | ~2.5 |
| 89 | ~3.0 |
| 90 | ~2.0 |
| 91 | ~2.5 |
| 92 | ~3.0 |
| 93 | ~2.0 |
| 94 | ~2.5 |
| 95 | ~3.0 |
| 96 | ~2.0 |
| 97 | ~2.5 |
| 98 | ~3.0 |
| 99 | ~2.0 |
| 100 | ~2.5 |
</details>

Total motion

![](images/ec05b341d5411e52c75443bced98055425cdab49dd065538c4dc471775c0a8b8.jpg)  
Osci l l ato ry m oti o n  
(d u e to 1 st o rd e r Wave i nd u ced loads)

![](images/82288db0b5713f149a9efa711a1a50fc16ff1bef599318f0711ada504b8ec8f0.jpg)

<details>
<summary>line</summary>

| X | Y |
| --- | --- |
| Start | ~1.5 |
| End | ~3.5 |
</details>

S lowly varyi ng motion  
(d ue to 2 nd Wave loads cu rre n t , wi n d )

## Sh i p Motion Control Objectives

D u e to th e motion of s h i ps , motion control p rob l e ms ca n have d iffe re nt obj ectives :

 Con trol only th e LF m o tions (Autopi lots , Dynam ic Position i ng ( D P) , Position moori ng systems)  
Con trol only th e WF m o tions ( H eave , rol l and pitch stabi l isation , rid e control )  
 Con trol bo th ( D P with rol l a nd pitch sta b i l isation i n h ig h seas , cou rse kee p i ng a nd rol l sta b i l isation )

Dyna m ic Position i ng  
![](images/c2973eb9c1bca96e074eb4123d5cc07195f0107cc2c9f64330dfbe1835fd38f9.jpg)

<details>
<summary>natural_image</summary>

Illustration of a cargo ship with a red container and red hull, floating on water with a yellow spray trail (no text or symbols)
</details>

Au to p i l ot  
![](images/228e2700235d9d03daaa9ff4ddcd7a29605384acc936288d9109add552725a27.jpg)

<details>
<summary>natural_image</summary>

Illustration of a naval ship with a red circular arrow and arrowhead, no text or symbols present
</details>

Rol l sta b i l isation  
![](images/92c1537eab56c88af0da32dab6d121da5c7d2da9f7903bfc3a18e41c8c12d7f1.jpg)

<details>
<summary>natural_image</summary>

3D rendered image of a ship floating on blue water, no text or symbols visible
</details>

## Pla nt Control System

Generates appropriate actuator com mands .

 Wave filter (observer) : Recover slowly varyi ng motion sig nals from the total measu rements  
Controller: Generates force com ma nds (d esi red control action )  
Control allocation: Translate force com mands i nto actuator com mands ( RP M , PWR, Torq ue) .

![](images/82ae63b600584f67f24fe59fd661c2c93150525ba688bd6d778831d90b44e28d.jpg)

<details>
<summary>flowchart</summary>

```mermaid
graph LR
  subgraph ControlSystem
  A["Control allocation solver"] -->|Actuator command| B["Actuator"]
  B -->|Desired control action| C["Controller (autopilot,DP,stabiliser)"]
  C -->|Desired setting Reference trajectory| D["Desired setting (Reference trajectory)"]
  E["Wave filter (observer)"] -->|State estimation| C
  end
  subgraph Feedback
  F["Position and speed measurements"] -->|Position and speed measurements| E
  end
```
</details>

## Wave F i l te r i n g

Removes fi rst ord er (osci l latory) wave-i nd u ced motion

Exa m pl e cou rse a utop i lot wave fi lte ri ng

Perez (2005) :

H ead i ng ang le

![](images/ddccf3637974744b3e4efc177709f85efb162e52da477fcf198d21e7a329f2dc.jpg)

H ead i ng rate

Rudder ang le

## Control Al l ocati o n

Some ma ri n e control syste ms a re ove r-actu ated to g u a ra ntee rel ia b i l ity a nd h ig h pe rforma n ce – opti m ization probl e m

![](images/f1b6c05234171562a19218f531fe8c577c96995ab617d546a22645610120dcae.jpg)

## Ma ri ne Control Problems a nd Models

![](images/fa366df93d6f24d0b48da6dc9c805a1a68f7c78c76e24a3a543a94d26a266151.jpg)

<details>
<summary>natural_image</summary>

3D rendering of a large green and red cargo ship floating above a yellow trajectory line with yellow cables, underwater with ocean background (no text or symbols)
</details>

mo o r i n g  
P ip e and c ab l e l a y i n g

![](images/41f23805230109d6a7d334222a038c7c0a093d426afefeed394d33a639ee8bc0.jpg)

<details>
<summary>text_image</summary>

Geological
survey
</details>

![](images/abed2ac39d71322a047b831863d9a7bbb012c70b5faa4a58150bf5f91f962e25.jpg)

<details>
<summary>natural_image</summary>

Yellow HiROV 3000 underwater vehicle with visible internal components and structural supports (no text or symbols on the device itself)
</details>

![](images/6a13ee07ab04f8b345d5a72155a28ae874d6e4cec10c18a45fb8d5875e912429.jpg)

<details>
<summary>natural_image</summary>

Aerial view of two oil rigs operating in a coastal area with water and floating structures (no visible text or symbols)
</details>

![](images/4ad72ff9a33ab7cf7b1f38aa6b87f0b13d2e0daeeb59b1145d0a1044468a6d04.jpg)

<details>
<summary>text_image</summary>

Heavy lift
operations
</details>

![](images/7ba23e6ff25f5a949e2fee97165025cc4a6e90c958bf731c37388f345f45976a.jpg)

<details>
<summary>text_image</summary>

ROV operations
Cerigy se
Pipe laying vessel
</details>

![](images/7a87516d16ae1525c790883fc06bed97f3f68d1082cd2ae2831be6f22f2d12c6.jpg)

<details>
<summary>text_image</summary>

Cable laying
vessel
</details>

Vib r a t i o n c o n t r o l o f ma r i n e r i s e r s

# Trajectory Tracki ng & Ma neuveri ng Control

![](images/33478c5f774b75f5c71fb58ed9bcbd0a23b6f46f14d677ac31a2de531a98685c.jpg)

<details>
<summary>natural_image</summary>

Large red and white research vessel with yellow crane on open sea (no visible text or symbols)
</details>

Fully actuated supply ship cruising at low speed.

![](images/e92ac0e62a2b4c40cfb206aff1bed983de6c4a4fa5ec6bd0e4755bbc553aefb1.jpg)

<details>
<summary>natural_image</summary>

Large blue container ship named 'MAERSK LINE' sailing on open sea, no visible text or symbols on the vessel itself
</details>

Underactuated container ship in transit.

![](images/011c72b5376cf6488d1547392bf80cb4b228f0a6a7a57e8ef2632140b687ac4c.jpg)

<details>
<summary>natural_image</summary>

Two naval ships sailing on open sea, hull numbers visible, no text or symbols present
</details>

Italian supply ship Vesuvio refueling two ship s at sea.

Courtesy: Hepburn Eng. Inc .

## Formation Control/U nderway Replen ish ment

![](images/8036fc35d82248d59b116288624a8a7bf2575dba6e4c77c7f8809fbcbff050b7.jpg)

## I nte rd isci pl i na ry: Rocket La u n ch / D P syste m / TH CS

Launch Platform  
![](images/46aca80b9d481de2396fea71910168855ca8fa4cb25d2599b62f9e987dee633c.jpg)

<details>
<summary>natural_image</summary>

Illustration of a rocket launch on an offshore platform with smoke plumes and a distant vessel, no text or symbols present.
</details>

Assembly Command Ship

![](images/04238b4ef715926a2dca76fc9f249b8ac45ea80d204e9dd1a6e4a1eb120f3a0f.jpg)

<details>
<summary>natural_image</summary>

Large white sea launch vessel named 'SEA LAUNCH' sailing on open sea, no visible text or symbols on the vessel itself.
</details>

![](images/4925b0f1002004ce162ae8ca1344af58b98d279c968d48f34168cf4554b9da10.jpg)

<details>
<summary>natural_image</summary>

Abstract logo design with blue and yellow curved shapes and an arrow (no text or symbols)
</details>

SEA LAUNCH SM M arin e S e gm en t

## Tri m & H eel Correction System (TH CS )

![](images/0e0290c854d74e9af1ddaa9e72ef5dd3d9fd08e6268b9d1b05ff7699963e3500.jpg)

<details>
<summary>flowchart</summary>

This diagram illustrates the control system architecture for a trim controller, showing the flow of torque and pressure inputs through various pumps (Heel, Trim, CST) to the engine body.
</details>

Process Control  
o r  
Mari ne Control ?

![](images/cd24d4498a3a891195ff73bb384bddc640fddc6a8d0bf627a867f1e98d9c7875.jpg)

<details>
<summary>text_image</summary>

Ches1
0.0 %
401
3h
SBA LAUNCH
SBA LAUNCH
</details>

## Dyna m ic Position i ng

D ri l l i ng vessel ( Reg u lation )  
![](images/4732c592fafcf878e8f3eb1c4a6870ed06241a533ff6d14640ff483db81bef3e.jpg)

<details>
<summary>natural_image</summary>

Illustration of a cargo ship with a red-and-white structure floating on water, emitting a yellow spray trail (no text or symbols)
</details>

ROV operations (tracki ng )  
![](images/5d22acbca357f8a93bf79527044d107daedf9a73b12fd1af1160bf6d96863a99.jpg)

<details>
<summary>flowchart</summary>

```mermaid
graph LR
  A["Top Platform"] --> B["Bottom Platform"]
  B --> C["Flow Arrow 1"]
  B --> D["Flow Arrow 2"]
  C --> E["End Node"]
  D --> E
```
</details>

Control obj ective : Kee p position ; fol low slow cha nges i n set poi nt.  
 DO F : 1 , 2 , 6 (su rge , sway a nd yaw) [p itch a nd rol l ca n be i n corporated i n h ig h sea states i n offs h o re ri g s]  
 M od el : ti me-doma i n mod el wh i ch i n cl u d es cross-flow d rag effects . The M u n k mome nt, wh i ch is i n the ad d ed mass Coriol l is-ce ntri petal te rms shou ld be ad d ed . Alte rnatively, use cu rre nt coeffi cie nts (expe ri me ntal d ata) .  
 D istu rba n ces : Wi nd , cu rre nt, mea n wave d rift a nd slowly va ryi ng wave forces .

## Cou rse a nd Head i ng Auto p i l ots

H ead i ng  
![](images/e0053a8ba8394a3a6738326d4073b1970e2c268a158a98de771233df65d4b6f6.jpg)

<details>
<summary>natural_image</summary>

Illustration of a ship with a red circular arrow and arrowhead, symbolizing economic or operational growth (no text or symbols present)
</details>

Cou rse keepi ng  
![](images/7c49b125fb5b73f2eff7527771e274af45420dcda1726de794fbff40cad99493.jpg)

<details>
<summary>natural_image</summary>

3D rendering of a naval warship with red and beige hull, no visible text or symbols
</details>

 Control O bj ective : Kee p head i ng or cou rse . For cou rse kee p i ng a utop i lots , position i ng control a nd g u id a n ce systems m ust also be d esig ned (outer loop) .  
 DO F : 2 , [4] , 6 (sway, rol l , yaw) The re is strong cou pl i ng betwee n sway a nd yaw wh i ch is not conve n ie nt to ig nore , a nd rol l a lso affect these mod es .  
 M od el : M a noeuvri ng mod el ; at h ig h speed l ift-d rag effects a re sig n ifi ca nt. The mod el ca n be l i n ea rised for control d esig n beca use the m ust ope rate close to eq u i l i b ri u m cond itions .  
 D istu rba n ces : Wi nd , waves (the re m ust be a wave fi lte r) ; for a cou rse kee p i ng a utop i lot, cu rre nt is a lso a d istu rba n ce .

## Ma noeuvri ng Control

![](images/71bf4550f72d79f9027310c70306440a38583c9724654f21f1c676fda05c2a10.jpg)

<details>
<summary>natural_image</summary>

3D rendering of a boat hull with red and beige hull, no visible text or symbols
</details>

 Control obj ective : geometri c a nd dyna m i c cond itions for path fo l l ow i n g , way- p o i n t o r t raj e cto ry t ra c ki n g .  
D O F : 1 , 2 , [4 ] , 6 .  
M od e l : non l i nea r ma noeuvri ng mod el .  
 D istu rba n ces : wi nd , waves , cu rre nt.

## Ride Control

![](images/eee75f488129a728a820f483a74d229d381f4ea4e823658110b400e2e610d3d0.jpg)

<details>
<summary>natural_image</summary>

Military naval vessel sailing on open sea, creating visible wake (no text or symbols)
</details>

![](images/9468f138b811af977c32fe34fb7edfd72ca2c7994cd22d486410003f3bac77b2.jpg)

<details>
<summary>natural_image</summary>

Large white and blue cargo ship named 'BENCAUGA EXPRESS' sailing on open sea under clear sky (no visible text or symbols on vessel body)
</details>

Control obj ectives : red u ce rol l a nd p itch .  
D O F : 4 , 5 .  
 M od el : l i n ea r ti me-d oma i n mod e l , with viscous corrections for rol l .  
 D istu rba n ces : 1 st ord e r wave i nd u ced motion ; wi nd , tri m va riations with speed .

## Heave Com pensation

![](images/c35b68945ec72ee87e6261a1a1fba7b9a7c124fcef7a72a5246dd935bcc82330.jpg)

 Control obj ective : red u ce the effect of heave motion i n d iffe re nt com pon e nts of the syste m .  
D O F : 3 , [ 5 ] .  
M od el : l i n ea r ti me-doma i n mod el + non l i n ea r viscous effects a nd stru ctu ra l sti ffn ess .  
D istu rba n ces : 1 st ord e r wave-i nd u ced motion , a nd ra p id ly-va ryi ng $2 ^ { \mathsf { n d } }$ o rd e r wave-i nd uced motions

## Sh i p-to-Sh i p Operations

![](images/474cbc6998a54d7389ec08e825c4aa26b2cc0e0a9672cf3cbe8fff54cde1c146.jpg)

Control obj ective : kee p formation .  
D O F : 1 , 2 , 6 .  
M od el : ti me-doma i n mod el with sh i p-to-sh i p hyd rodyna m ic i nteraction if vessels are too close .  
D istu rba n ces : waves , wi nd , cu rre nt

# M odel l i ng Distu rba nces for Control Desig n

If a mod el-based control d esig n req u i res d istu rba n ce mod el l i ng ,

## Waves :

 1 st-ord er wave loads (d u e to wave spectru m ) ca n be mod el led usi ng m u lti-si n ces with ra ndom p hases or fi lte red wh ite noise (wave spectru m ) .  
 M ea n wave d rift loads ca n be mod el led as a 1 st-ord er Wiener process ( 1 st-o rd e r syste m d ri ve n by w h i te n o i s e . )

## C u rre nts :

 Cu rre nt loads ca n be i n cl u d ed usi ng the con ce pt of re l ative ve locity i n su rge , sway a nd yaw (i n D P cu rre nt coeffi cie nts ca n a lso be used )

## Wi nd :

 Wi nd loads a re i n cl u d ed usi ng wi nd coeffi cie nt ta bl es .

## Wi nd Loads

Wi nd a reas a nd ce ntroids from d ig itized GA  
 For best resu lts expe ri me nta l d ata from wi nd tu n n e ls s hou l d be used .

Transverse/frontal projected area (Viking Poseidon MPSV) [Twaerline =5.5 m]  
![](images/a6b462a675df6296f6ab98ed7417f7a8d7350915a5f4225fab89625a5d0fbadc.jpg)

<details>
<summary>scatter</summary>

| Category | Value (m) |
| --- | --- |
| AF,wind | 520.6 |
| AF,current | 118 |
| c_wind | 17.7 |
| c_current | 2.8 |
</details>

Windcoefices:955).A()..).H9 (m)  
![](images/43d8b9174d32dc0424d8a1288c0130502d0407bacb3ce11b7bab72bacd5520c0.jpg)

<details>
<summary>line</summary>

| Angle of wind \(\gamma r\) (deg) | \(Cx = X/(q*A\Gamma)\) | \(Cy = Y/(q*AL)\) | \(Ck = K/(q*AL*HM)\) | \(CN = N/(q*AL*Lva)\) |
| --- | --- | --- | --- | --- |
| 0 | -0.8 | 0 | 0 | 0 |
| 10 | -0.8 | ~-0.15 | ~-0.12 | ~-0.05 |
| 20 | -0.8 | ~-0.32 | ~-0.27 | ~-0.1 |
| 30 | ~-0.78 | ~-0.5 | ~-0.42 | ~-0.14 |
| 40 | ~-0.71 | ~-0.68 | ~-0.56 | ~-0.16 |
| 50 | -0.6 | -0.8 | ~-0.68 | ~-0.16 |
| 60 | ~-0.45 | ~-0.88 | ~-0.74 | ~-0.15 |
| 70 | ~-0.29 | ~-0.9 | ~-0.75 | ~-0.13 |
| 80 | ~-0.14 | ~-0.9 | ~-0.75 | ~-0.1 |
| 90 | 0 | ~-0.9 | ~-0.75 | ~-0.07 |
| 100 | ~0.14 | ~-0.9 | ~-0.75 | ~-0.04 |
| 110 | ~0.29 | ~-0.9 | ~-0.75 | ~-0.01 |
| 120 | ~0.45 | ~-0.88 | ~-0.73 | 0.02 |
| 130 | 0.6 | -0.8 | ~-0.67 | 0.04 |
| 140 | ~0.72 | ~-0.68 | ~-0.56 | 0.06 |
| 150 | ~0.78 | ~-0.5 | ~-0.42 | 0.06 |
| 160 | 0.8 | ~-0.32 | ~-0.27 | 0.05 |
| 170 | 0.8 | ~-0.15 | ~-0.12 | 0.03 |
| 180 | 0.8 | 0 | 0 | 0 |
</details>

Lateral projected area (Viking Poseidon MPSV)  
![](images/00cbb903cdf8638d7d87ea3a46311ddef065bc38ba3f69911cee45c12fbd601a.jpg)

<details>
<summary>area</summary>

| Series | x (m) | z (m) |
| --- | --- | --- |
| A_L,wind | -45 | 12.5 |
| A_L,wind | -15 | 20.5 |
| A_L,wind | -5 | 19 |
| A_L,wind | 0 | 20.5 |
| A_L,wind | 5 | 15.5 |
| A_L,wind | 10 | 15.5 |
| A_L,wind | 15 | 19.5 |
| A_L,wind | 20 | 12.5 |
| A_L,wind | 22 | 27.5 |
| A_L,wind | 23 | 40 |
| A_L,wind | 25 | 28 |
| A_L,wind | 30 | 28 |
| A_L,wind | 35 | 20 |
| A_L,wind | 40 | 17.5 |
| A_L,wind | 45 | 17.5 |
| A_L,current | -45 | 5 |
| A_L,current | -35 | 0 |
| A_L,current | 0 | 3 |
| A_L,current | 45 | 4.5 |
</details>

## Exa m ple : Si m u lation of Wave Loads i n DP

![](images/ccaf3fd36e0722675e6fd3c070e35beac5f7bd201b330b0364ac2679d343cd6c.jpg)

<details>
<summary>flowchart</summary>

This flowchart illustrates a multi-stage motion control system architecture, showing the process from modelled Wiener process through to oscillatory wave-induced motion, and finally to guidance navigation control.
</details>

Th is mod el is typi cal ly used to d esig n control a nd observers .

## Usefu l References

 Fossen , T. I . (1 994) . Guidance and Control of Ocean Vehicles, Joh n W i l e y  
 Fossen , T. I . (2002) . Marine Control Systems. Mari ne Cybernetics .  
 Perez, T. (2005) . Ship Motion Control. S pri nge r Ve rl ag .  
 Sørensen , A.J . (2005) . “Marine Cybernetics”. Lectu re N otes Dept. of Mari ne Tech nology, NTN U , Norway