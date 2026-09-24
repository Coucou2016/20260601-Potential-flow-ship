# Hyd rodyna m ics for control eng i neers

( M od u l e 2)

## D r T ri sta n P e rez

Centre for Com plex Dynam ic Systems a nd Control (C DSC)

## P rof. Thor I Fosse n

De pa rtme nt of E ng i n ee ri ng Cybernetics

![](images/5b4d2828f8799e36b04747e547920307cece7eece144cf0735e7f08c5c720508.jpg)

THE UNIVERSITY OF NEWCASTLE

AUSTRALIA

![](images/8894eaf7bffdc7e4c2bc4a2e49a0b9561a71681543d14ef0be4ab5d3bea84210.jpg)

NTNU

Det skapendeuniversitet

## Ma ri ne hyd rodyna m ics

I n ord e r to stu dy the motion of ma ri n e stru ctu res a nd vessels , we n eed to u nd e rsta nd the effects the su rrou nd i ng fl u id has on the m .

Th is req u i res some basic con cepts of hyd rodynam ics— wh i ch is fl u id dyna m i cs u nd er special-case si m pl ifications and assu m ptions pa rti cu l a r of m a ri n e a p p l i cati o n s .

To solve problems related to sh i p motion we , need to know two th i ngs a bout the fl u id :

ve l ocity  
pressu re

## Fl u id flow d escri pti o n

T h e ve l o c i ty of th e fl u i d at th e l o cati o n

$$
\mathbf {x} = \left[ x _ {1}, x _ {2}, x _ {3} \right] ^ {\mathrm{T}}
$$

![](images/8288e75203f03bf8b7b67cbcdfc93b5994ee68aa2a251c8b6a2ceb257171066b.jpg)

<details>
<summary>flowchart</summary>

```mermaid
graph LR
  A["Input Vector x"] --> B["Vector v(x,t)"]
  B --> C["Final Output"]
```
</details>

i s g i ve n by th e fl u i d -fl ow ve l o ci ty ve cto r :

$$
\mathbf {v} (\mathbf {x}, t) = \left[ v _ {1} (\mathbf {x}, t), v _ {2} (\mathbf {x}, t), v _ {3} (\mathbf {x}, t) \right] ^ {\mathrm{T}}
$$

t h i s ve cto r i s u s u a l l y d e s c ri b e d re l at i ve to a n i n e rt i a l coord i n ate syste m with orig i n i n th e mea n free s u rfa ce ( h -fra m e , o r s-fra m e ) .

## I ncom pressi ble fl u id

For the flow velocities i nvolved i n sh i p motion , the fl u id ca n be consid e red incompressible , i. e. , consta nt d e nsity.

U nd e r th is assu m ption , the n et vol u me rate at a vol u me V en closed by a su rface S is

$$
\iint_ {S} \mathbf {v} \cdot \mathbf {n} d s = \iiint_ {V} \mathbf {d i v} (\mathbf {v}) d V = 0
$$

s i n ce t h i s i s va l i d fo r a l l t h e re g i o n s V i n t h e fl u i d , t h e n by assu m i ng that is conti n uous we obta i n the continuity equation for i n com pressi ble flows :

$$
\mathbf {d i v} (\mathbf {v}) = \nabla \cdot \mathbf {v} = \frac {\partial v _ {1}}{\partial x} + \frac {\partial v _ {2}}{\partial y} + \frac {\partial v _ {3}}{\partial z} = 0
$$

## M ateria l derivative

Let $f ( x , y , z , t )$ be a sca l a r fu n ction a nd $\mathbf { f } \left( t , x , y , z \right)$ a vector-va l u ed fu n ction ; th e n ,

$$
\begin{array}{l} \frac {d f}{d t} = \frac {\partial f}{\partial t} + \frac {\partial f}{\partial x} \frac {d x}{d t} + \frac {\partial f}{\partial y} \frac {d y}{d t} + \frac {\partial f}{\partial z} \frac {d z}{d t} \\ \frac {d \mathbf {f}}{d t} = \frac {\partial \mathbf {f}}{\partial t} + \frac {\partial \mathbf {f}}{\partial x} \frac {d x}{d t} + \frac {\partial \mathbf {f}}{\partial y} \frac {d y}{d t} + \frac {\partial \mathbf {f}}{\partial z} \frac {d z}{d t}. \\ \end{array}
$$

I f th es e a re ta ke n fo r th e fu n cti o n $\mathbf { x } ( t ) \mathrm { s . t . } \dot { \mathbf { x } } ( t ) = \mathbf { v } ( t )$ th e n we have a s pecia l notation—mate ria l d e rivative :

$$
\frac {D f}{D t} = \frac {\partial f}{\partial t} + \mathbf {v} \cdot \nabla f, \quad \frac {D \mathbf {f}}{D t} = \frac {\partial \mathbf {f}}{\partial t} + (\mathbf {v} \cdot \nabla) \mathbf {F}
$$

## Flow eq uations

The conservation of mome ntu m i n the flow is d escri bed by the

Navier-Stokes (N-S) Equation:

$$
\rho \frac {D \mathbf {v}}{D t} = \rho \mathbf {F} - \nabla p + \mu \nabla^ {2} \mathbf {v}
$$

F a re accel e rations d u e to vol u metri c forces : $\mathbf { F } = [ 0 0 - g ] ^ { \mathrm { T } }$ $p = p ( \mathbf { x } , t )$ is the pressu re , a nd $\mu$ i s th e v i s cos i ty of th e fl u i d .

U n knowns : v and $p$  
 N -S + Conti n u ity eq . form a syste m of N on l i n ea r P D E  
N o a n a l yti ca l so l u ti o n exi sts fo r re a l i sti c s h i p fl ows .  
N u m e ri ca l so l u ti o n s a re sti l l fa r fro m fe as i b l e  
Practical approaches : RAN S (C F D )

## Potentia l th eo ry

A fu rth e r s i m p l ifi cation is obta i n ed by assu m i ng th at th e fl u i d i s in viscid a n d th e fl ow i s irrota tional. I rrota ion a l mea ns th at

$$
\mathbf {c u r l} (\mathbf {v}) = \nabla \times \mathbf {v} = 0
$$

U nd e r th is assu m ption , th e n exists a sca l a r fu n ction ca l l ed potential su ch th at

$$
\mathbf {v} = \nabla \varPhi
$$

So , if we know th e pote nti a l , we ca n ca l cu l ate th e flow ve l ocity vecto r (th e g rad i e nt of th e pote nti a l ) .

## How do we obta i n the potentia l ?

I n pote ntia l theory, the conti n u ity eq u ation reve rts to the Laplacian of the pote ntia l eq u a l to ze ro :

$$
\nabla^ {2} \varPhi = \frac {\partial^ {2} \varPhi}{\partial x ^ {2}} + \frac {\partial^ {2} \varPhi}{\partial y ^ {2}} + \frac {\partial^ {2} \varPhi}{\partial z ^ {2}} = 0
$$

Th e pote nti a l is , th us , obta i n ed by solvi ng th is su bj ect to a p p rop ri ate bou nd a ry cond itions , i. e. , by solvi ng a bou ndary val u e problem (VB P) .

The La pl ace Eq u ation is l i n ea r ⇔ S u pe rposition of flows .

## Ex : Potentia l Flow Su perposition

U n iform  
![](images/616fdb58fd84e4feccf1bcc5765e2808f2656d3c2710b5f9e1912e1ed68c28e7.jpg)

<details>
<summary>text_image</summary>

y
U
x
</details>

Sou rce  
![](images/a7b8347612919059041112be805e3c777b29c21184a64e98a40f775243c76711.jpg)

<details>
<summary>text_image</summary>

y
SO
r
θ
x
</details>

S i n k  
![](images/2c45b6ea2b396e54a6aba4c67ee7d3942c090f3d4f06c1db5b6182781270deb9.jpg)

<details>
<summary>text_image</summary>

y
SK
r
θ
</details>

![](images/2837d456a37102860cf1d0be102fd778cc06dc19f8ee1ccaf77cec8337721287.jpg)

<details>
<summary>text_image</summary>

z
x
s
s
</details>

## How do we ca lcu late pressu re?

If we n eg l ect viscosity i n the N -S eq u ation , we o bta i n th e E u l e r Eq u ati o n of fl ow :

$$
\rho \frac {D \mathbf {v}}{D t} = \rho \mathbf {F} - \nabla p
$$

The n ,

$$
\frac {\partial \mathbf {v}}{\partial t} + (\mathbf {v} \cdot \nabla) \mathbf {v} = - \nabla \left(\frac {p}{\rho} + \gamma\right)
$$

where

$$
- \nabla \Upsilon = \mathbf {F}, i. e. \Upsilon = g z
$$

## I rrota i o n a l fl ow assu m ption

U si ng some vector cal cu l us

$$
\frac {\partial \mathbf {v}}{\partial t} + (\nabla \times \mathbf {v}) \times \mathbf {v} = - \nabla \left(\frac {p}{\rho} + \frac {1}{2} \mathbf {v} ^ {2} + \gamma\right)
$$

I f t h e fl ow i s i rrotat i o n a l , t h e n

$$
\nabla \left(\frac {p}{\rho} + \frac {\partial \varPhi}{\partial t} + \frac {1}{2} (\nabla \varPhi) ^ {2} + \mathcal {Y}\right) = 0
$$

## Bernou l l i eq uation

$$
\nabla \left(\frac {p}{\rho} + \frac {\partial \varPhi}{\partial t} + \frac {1}{2} (\nabla \varPhi) ^ {2} + \mathcal {Y}\right) = 0
$$

I f t h i s i s va l i d i n t h e w h o l e fl u i d , t h e n

$$
\frac {p}{\rho} + \frac {\partial \varPhi}{\partial t} + \frac {1}{2} (\nabla \varPhi) ^ {2} + g z = C
$$

wh i ch is the Bernou l l i eq u ation .

## Potentia l theory—su m ma ry

Pote n ti a l th eo ry offe rs a g re at s i m p l i fi cati o n : i f we kn ow th e pote n ti a l , th e n we know the velocity a nd the pressu re , from wh i ch we ca n ca l cu l ate the forces acti ng on a floati ng body by i nteg rati ng the pressu re ove r the su rface of the body.

![](images/85f63c6e204ff198a9375c69cc560b0b8c735d776b1e7ba29b0d265ff4e1d3f0.jpg)

for most probl e ms rel ated sh i p motion i n waves , pote ntia l theory is suffi cie nt for e ng i n ee ri ng pu rposes . Viscous effects a re ad d ed to the mod els usi ng e m p i ri ca l form u l ae or via syste m id e ntifi cation .

## Appl ications

Reg u lar waves  
M a ri n e stru ctu res i n waves

## Reg u la r waves i n deep water

![](images/631ad1118d64fd4ae3645b04b20cc61542bf0ade2ffba6d1e9c6d2c192f41bc1.jpg)

<details>
<summary>line</summary>

| Parameter | Description |
| --- | --- |
| t-fixed | Propagation distance |
| Propagation | Period (H) |
| Propagation | Amplitude (zh) |
| Propagation | Period (λ) |
| Propagation | Amplitude (z) |
| x-fixed | Propagation distance |
| x-fixed | Amplitude (z) |
| x-fixed | Period (T) |
| x-fixed | Amplitude (z) |
</details>

The sea surface elevation is denoted by $\zeta ( x , t )$

## Ki nematic free-su rface Cond ition

Ki n e m ati c fre e-s u rfa ce co n d i ti o n : A fl u i d pa rti cl e o n th e fre e su rface is assu med to re ma i n on th e free su rface .

Let the free su rface be d efi n ed as $z = \zeta ( x , y , t )$

T h e n , i f $F : = z - \zeta ( x , y , t )$

Th e ki n e mati c cond ition reve rts to $\frac { D F } { D t } = 0$

H ence ,

$$
\frac {\partial \zeta}{\partial t} + \frac {\partial \phi}{\partial x} \frac {\partial \zeta}{\partial x} + \frac {\partial \phi}{\partial y} \frac {\partial \zeta}{\partial y} - \frac {\partial \phi}{\partial z} = 0 \quad \text {on} \quad z = \zeta (x, y, t)
$$

## Dyna m ic free-su rface Cond itions

Dyn a m i c free-su rface cond ition : th e wate r p ressu re eq u a ls th e atmos p h e ri c p ressu re on th e free su rface .

![](images/64242b63d38068b47954caefc743e0953a89c35df20ecb915e8902f093d21f7f.jpg)

<details>
<summary>text_image</summary>

z
p = p₀ for z = ζ
h
</details>

If we choose the consta nt i n the Be rnou l l i eq u ation as $C = p _ { 0 } / \rho$ Th e n ,

$$
g \zeta + \frac {\partial \phi}{\partial t} + \frac {1}{2} \left[ \left(\frac {\partial \phi}{\partial x}\right) ^ {2} + \left(\frac {\partial \phi}{\partial y}\right) ^ {2} + \left(\frac {\partial \phi}{\partial z}\right) ^ {2} \right] = 0 \quad \text {on} \quad z = \zeta (x, y, t)
$$

## Li nea rised free-su rface cond itions

Th e free-su rface cond itions ca n be l i n ea rised a bout th e mea n free-su rface :

$$
\frac {\partial \zeta}{\partial t} - \frac {\partial \phi}{\partial z} = 0
$$

$$
g \zeta + \frac {\partial \phi}{\partial t} = 0
$$

$\begin{array} { r l r l } { \mathsf { o n } ~ } & { { } } & { } & { { } z = 0 } \end{array}$

Com bi ned :

$$
g \frac {\partial \phi}{\partial z} + \frac {\partial^ {2} \phi}{\partial t ^ {2}} = 0 \quad \text {on} \quad z = 0
$$

## Reg u la r Wave l i n ea r BVP

Hence, the boundary value problem (BVP) is to find the potential, $\Phi _ { w } ( { \bf x } , t )$ that satisfies

$$
\nabla^ {2} \Phi_ {w} = 0
$$

$$
s. t. \quad \frac {\partial \Phi_ {w}}{\partial z} = \frac {\partial \zeta}{\partial t} \quad \text {on} \quad z = 0,
$$

$$
\frac {\partial \Phi_ {w}}{\partial t} = - g \zeta \quad \text {on} \quad z = 0,
$$

$$
\frac {\partial \Phi_ {w}}{\partial z} = 0 \quad \text {on} \quad z = - h,
$$

$$
\zeta = \bar {\zeta} \sin (\omega t - k x + \varepsilon)
$$

The linear free-surface ⇒ solution will be valid for waves with small stepness, i.e., $\bar { \zeta } / \lambda \ll 1$

## Reg u la r Wave Potentia l

## Solution:

Deep water:

$$
\Phi_ {w} = \frac {g \bar {\zeta}}{\omega} e ^ {k z} \cos (\omega t - k x + \varepsilon)
$$

Shallow water:

$$
\Phi_ {w} = \frac {g \bar {\zeta}}{\omega} \frac {\cosh [ k (z + h) ]}{\cosh [ k h ]} \cos (\omega t - k x + \varepsilon)
$$

We then have the velocities and pressure in the whole fluid domain:

$$
[ u, v, w ] ^ {\intercal} = \nabla \Phi_ {w}, \qquad p - p _ {0} = - \rho g z - \rho \frac {\partial \Phi}{\partial t}.
$$

Reg u la r wave form u lae ( Fa lti nsen, 1 990)

<table><tr><td></td><td>Finite water depth</td><td>Infinite water depth</td></tr><tr><td>Velocity potential</td><td> $\phi = \frac{g\zeta_{a}}{\omega} \frac{\cosh k(z+h)}{\cosh kh} \cos(\omega t - kx)$ </td><td> $\phi = \frac{g\zeta_{a}}{\omega} e^{kz} \cos(\omega t - kx)$ </td></tr><tr><td>Connection between wave numberk and circular frequency  $\omega$ </td><td> $\frac{\omega^{2}}{g} = k \tanh kh$ </td><td> $\frac{\omega^{2}}{g} = k \quad C = \omega$ </td></tr><tr><td>Connection between wavelength $\lambda$  and wave period  $T$ </td><td> $\lambda = \frac{g}{2\pi} T^{2} \tanh \frac{2\pi}{\lambda} h$ </td><td> $\lambda = \frac{g}{2\pi} T^{2}$ </td></tr><tr><td>Wave profile</td><td> $\zeta = \zeta_{a} \sin(\omega t - kx)$ </td><td> $\zeta = \zeta_{a} \sin(\omega t - kx)$ </td></tr><tr><td>Dynamic pressure</td><td> $p_{D} = \rho g \zeta_{a} \frac{\cosh k(z+h)}{\cosh kh} \sin(\omega t - kx)$ </td><td> $p_{D} = \rho g \zeta_{a} e^{kz} \sin(\omega t - kx)$ </td></tr><tr><td>x-component of velocity</td><td> $u = \omega \zeta_{a} \frac{\cosh k(z+h)}{\sinh kh} \sin(\omega t - kx)$ </td><td> $u = \omega \zeta_{a} e^{kz} \sin(\omega t - kx)$ </td></tr><tr><td>z-component of velocity</td><td> $w = \omega \zeta_{a} \frac{\sinh k(z+h)}{\sinh kh} \cos(\omega t - kx)$ </td><td> $w = \omega \zeta_{a} e^{kz} \cos(\omega t - kx)$ </td></tr><tr><td>x-component of acceleration</td><td> $a_{1} = \omega^{2} \zeta_{a} \frac{\cosh k(z+h)}{\sinh kh} \cos(\omega t - kx)$ </td><td> $a_{1} = \omega^{2} \zeta_{a} e^{kz} \cos(\omega t - kx)$ </td></tr><tr><td>z-component of acceleration</td><td> $a_{3} = -\omega^{2} \zeta_{a} \frac{\sinh k(z+h)}{\sinh kh} \sin(\omega t - kx)$ </td><td> $a_{3} = -\omega^{2} \zeta_{a} e^{kz} \sin(\omega t - kx)$ </td></tr></table>

ω=2π/T， k =2π/𝜆， T=Waveperiod， λ= Wavelength, $\xi _ { \mathfrak { a } } = \mathfrak { W }$ ave amplitude，g= Acceleration of gravity, t=Timevariable,x=direction of wave propagation，z=vertical coordinate,positive upwards,=0 mean waterlevel,h =average waterdepth.Totalpressure in thefluid: $\begin{array} { r } { \hat { p } _ { \mathrm { D } } - \rho g z + \hat { p } _ { 0 } \left( \hat { p } _ { 0 } = \right. } \end{array}$ atmospheric pressure).

## Water pa rticl e traj ecto ri es

Deep water:

![](images/1aa0a0395040d89745feab9039cd816d2c2edefefbd2df2e2e701003a438753c.jpg)

<details>
<summary>flowchart</summary>

This diagram illustrates a cyclic process or flow pattern with multiple parallel paths and directional arrows indicating movement or flow between nodes.
</details>

S hal low water:

![](images/8cd0d886905d8bd28323e8f01ff85a98b4a70202d5725da8fddc7d3e6b053b41.jpg)

<details>
<summary>flowchart</summary>

This diagram illustrates a sequential process or workflow with multiple stages represented by vertical bars and circular arrows, showing a continuous path from top to bottom.
</details>

## Potentia l theory for sh i ps i n waves

Th e fl u id forces a re d u e to va riations i n p ressu re on th e su rface of t h e h u l l .

I t is norma l ly assu med that th e forces (p ressu re) ca n be mad e of d iffe re nt com pon e nts

Figure taken From  
Flatinsen 1993 Sea Loads on ship and Ofshore Strucutres.  
![](images/66d18dcfdffbb010d58ed5a6decc8f8199147cacefb7d90184b84792b5ebddce.jpg)

## Potentia l theory for sh i ps i n waves

U nd e r l i n ea rity assu m ptions , the hyd rodyna m i c probl e m is d ea lt as 2 separate problems a nd the sol utions then add ed :

![](images/71dcadb403caed668cc0f18ea9578c8d4b6550b3caf0da40366ec5e7169f05e6.jpg)

<details>
<summary>flowchart</summary>

```mermaid
graph LR
  A["Excitation Load"] --> B["Radiation Load"]
  B --> C["Total Load"]
```
</details>

 Rad iation p rob l e m : the sh i p is forced to osci l l ate i n ca l m wate r.  
 D iffracti o n p ro b l e m : th e s h i p i s restra i n ed fro m m ovi n g i n th e presen ce of a wave field .

P ote n t i a l s :

$$
\Phi_ {T o t a l} = \underbrace {\sum_ {j = 1} ^ {6} \Phi_ {j}} _ {R a d i a t i o n p r o b l e m} + \underbrace {\Phi_ {I n c i d e n t} + \Phi_ {S c a t t e r i n g}} _ {D i f f r a c t i o n p r o b l e m}
$$

\- d u e to t h e m ot i o n i n t h e j -t h D O F . Φ j

## Rad iation pote nti a l

Bou nd a ry cond itions :

$$
\frac {\partial^ {2} \Phi}{\partial t ^ {2}} + g \cdot \frac {\partial \Phi}{\partial z} = 0 \quad \text {for:} z = 0
$$

free su rface cond ition (dyn a m i c+ ki n e mati c cond iti ons)

$$
\frac {\partial \Phi}{\partial z} = 0 \quad \text {for:} z = - h
$$

sea bed cond ition

$$
\frac {\partial \Phi}{\partial n} = v _ {n} (x, y, z, t)
$$

dynam ic body cond ition

$$
\lim _ {R \to \infty} \Phi = 0
$$

rad i ation cond ition

$$
\Phi_ {r a d} = \sum_ {j = 1} ^ {6} \Phi_ {j}
$$

![](images/070a0a1a3f84bce671f9b83478d8eac5c5e7517835ccce1beab6021d6e1962d9.jpg)

<details>
<summary>text_image</summary>

Floating body
S
∇²Φrad = 0
R
S*
φ → 0
R → ∞
</details>

## Com puti ng forces

## Forces and moments are obtai ned by i nteg rati ng the pressu re ove r the ave rage wetted su rface Sw:

Rad iation forces and moments :

$$
\tau_ {\mathrm{r} i} ^ {h} = \left\{ \begin{array}{l} - \iint_ {S w} \left(\frac {\partial \Phi_ {\mathrm{r}}}{\partial t}\right) (\mathbf {n}) _ {i} d s \\ - \iint_ {S w} \left(\frac {\partial \Phi_ {\mathrm{r}}}{\partial t}\right) (\mathbf {r} \times \mathbf {n}) _ {i - 3} d s \end{array} \right.
$$

N otati on : i-th com po n e nt

$$
\begin{array}{l} i = 1, 2, 3. \\ i = 4, 5, 6. \end{array}
$$

D O F :

Excitatio n forces (d u e to i n cid e nt a nd scattered potenti als) a nd moments :

$$
\tau_ {1 \mathrm{w} i} ^ {h} = \left\{ \begin{array}{l l} - \iint_ {S w} \left(\frac {\partial \Phi_ {1 \mathrm{w}}}{\partial t}\right) (\mathbf {n}) _ {i} d s & i = 1, 2, 3. \\ - \iint_ {S w} \left(\frac {\partial \Phi_ {1 \mathrm{w}}}{\partial t}\right) (\mathbf {r} \times \mathbf {n}) _ {i - 3} d s & i = 4, 5, 6. \end{array} \right.
$$

1 -s u rg e  
2-sway  
3-heave  
4 - ro l l  
5 - p i tc h  
6-yaw

## References

Falti nsen , O . M . ( 1 990) Sea Loads on S h i ps and Ocean Structu res . Cam bridge U n ive rsity P ress .  
 J o u rn ée , J . M . J . a n d W . W . M ass i e (200 1 ) Offs hore Hyd romechan ics . Lectu re notes on offshore hyd romecha n ics for Offshore Tech nology students , code OT4620 . ( h tt p : //www . o c p . t u d e l ft . n l/m t/j o u rn e e/)