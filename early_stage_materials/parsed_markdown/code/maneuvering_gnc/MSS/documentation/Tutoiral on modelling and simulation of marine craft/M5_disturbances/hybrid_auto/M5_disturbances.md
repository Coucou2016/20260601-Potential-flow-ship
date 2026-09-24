# Model l i ng a nd Si m u lation of Envi ron menta l Distu rba nces

## ( M od u l e 5)

## D r T ri sta n P e rez

Centre for Com plex Dynam ic Systems a nd Control (C DSC)

![](images/19914350d5586cf9d5b6833456b855899795ffec511634887619bca4939a4e6e.jpg)

THE UNIVERSITY OF

NEWCASTLE

AUSTRALIA

## P rof. Thor I Fosse n

De pa rtme nt of E ng i n ee ri ng Cybernetics

![](images/2fb15707aa552ef5f8b32e5f889c8bd60b1f886a78b8bd9ffbf6347ddaf05e58.jpg)

NTNU

Det skapende universitet

## Reg u la r waves i n deep wate r

The sea su rface elevation is d escri bed by:

$$
\zeta (x, y, t) = \bar {\zeta} \sin [ \omega t + \varepsilon - k x \cos (\chi) - k y \sin (\chi) ]
$$

![](images/dc03e6baba51afd86b9b29c9563580fe86e9f93949127b22f9673b9d9fd791e5.jpg)

<details>
<summary>text_image</summary>

y
C
λ
χ
x
</details>

where

$$
\omega = \frac {2 \pi}{T}
$$

$$
k = \frac {\omega^ {2}}{g}
$$

$$
\lambda = \frac {g}{2 \pi} T ^ {2}
$$

$$
c = \sqrt {\frac {g \lambda}{2 \pi}} = \frac {\lambda}{T}
$$

Wave freq u e n cy ( ra d /s )

Wave n u m ber ( ra d /m )

Wave l e ngth ( m )

Phase velocity ( m/s e c )

These expressions are on ly val id i n d eep water $h \geq \lambda / 2 ,$ w h e re h i s t h e wate r d e pt h .

## Sa i l i ng co nd itio n

The sa i l i ng cond ition of a vessel is g ive n by its forwa rd s peed U a nd its e n cou nte r a ng l e , i . e . , the head i ng a ng l e re l ative to th e waves .

![](images/2d81a595ec3dcdfe89cc28478e841e6a9a1948d11df3d0f91ad607b0cab50529.jpg)

<details>
<summary>text_image</summary>

Wave profile
λ
Quartering seas
c
Following seas χ
0deg
Beam seas
90deg
Bow seas
Head seas
U
180deg
x_h
y_h
</details>

E n cou nte r a ng l e

## Encou nter freq uency

If the waves a re obse rved from a refe re n ce fra me th at moves at a consta nt s peed , th e freq u e n cy observed is cal l ed E n cou nte r F req u e n cy.

![](images/97f676fec2cd03cf91a36541d045ad8d0bacb3afd88370e41ab283988d15728a.jpg)

<details>
<summary>line</summary>

| Feature | Description |
| --- | --- |
| Y-axis | \(\omega e\) |
| X-axis | \(\omega\) |
| Point 1 | \(\omega = (g/2U cos(\chi))\) |
| Point 2 | \(\omega = (g/4U cos(\chi))\) |
| Point 3 | \(\omega = (g/U cos(\chi))\) |
</details>

N egative encou nter freq uency => vessel overtakes the waves

$$
\boxed {\omega_ {e} = \omega - \frac {\omega^ {2} U}{g} \cos (\chi)}
$$

Th is is a Doppl er effect

## Ocea n waves

Ocea n waves prese nt, i n ge n e ra l , i rreg u l a rity i n ti me and space and can not be pred icted exactly: Stochastic P rocess .

![](images/06fb53412d482de23627bf6938294d8bb0643caee479e258b761c5525972dcf1.jpg)

<details>
<summary>text_image</summary>

ζ(0,0,t)
t
ζ(x,y,0)
200
180
160
140
120
100
80
60
40
20
0
x [m]
y [m]
</details>

## Ga ussia n waves

![](images/e919f7e682f14072486d6b1df30265e8b64bc0ffb1b6d3a950d6ae315eadddbb.jpg)

<details>
<summary>text_image</summary>

p(ζ)
ζ(x,y,y,t)
The elevation of the sea surface can
be thought as being generated as
the sum of many sinusoidal
waves with different amplitudes,
frequencies, and phases.
</details>

## How good a re these hypotheses?

F rom d ata col lected at sea ( H averre & M oa n , 1 985) , it ca n be stated that

 For low and mod erate seas (< 4 m ) , the sea can be consid ered stationary for periods over 20 m i n . For more severe sea states , stationa rity ca n be q u estion ed eve n for pe riods of 20 m i n .  
For med i u m seas (4 m to 8 m ) , Gaussia n mod els are sti l l accu rate , but d eviations from Ga ussia n ity sl ig htly i n crease with the i n creasi ng seve rity of th e sea state .  
 If the wate r is suffi cie ntly d ee p , wave el evation ca n be consid e r Gaussia n regard less of the sea state .

## Ra ndom sea cha racterization

U nd e r th e Ga uss ia n ity assu m ption , th e p rocess is com pletely descri bed by

M ean  
Va ri a n ce

The sea su rface el evation is d escri bed rel ative to the mea n free su rface ; th e refore th e mea n of th e S P is ze ro .

The va ria n ce is d escri bed i n terms of a sea power spectral d e nsity or sea spectru m .

## Power spectra l density defi n ition

If we use th e freq u e n cy i n Hz to d efi n e th e FT, th e n

$$
S _ {x x} (f) = \int_ {- \infty} ^ {+ \infty} R _ {x x} (\tau) e ^ {- j 2 \pi f \tau} d \tau
$$

$$
R _ {x x} (\tau) = \int_ {- \infty} ^ {+ \infty} S _ {x x} (f) e ^ {j 2 \pi f \tau} d f
$$

and

$$
\operatorname{var} [ x ] = R _ {x x} (0) = \int_ {- \infty} ^ {+ \infty} S _ {x x} (f) d f
$$

from wh i ch the na me powe r spectra l d e nsity fol lows .

Th is d efi n ition is com mon i n the l ite ratu re of el ectri ca l com m u n i cations a nd sig nal processi ng .

## PSD a lternative defi n ition

Wh e n we use th e ci rcu l a r freq u e n cy (rad/s) to d efi n e t h e F T ,

$$
S _ {x x} (\omega) = a \int_ {- \infty} ^ {+ \infty} R _ {x x} (\tau) e ^ {- j \omega \tau} d \tau
$$

$$
R _ {x x} (\tau) = b \int_ {- \infty} ^ {+ \infty} S _ {x x} (\omega) e ^ {j \omega \tau} d \omega
$$

$$
a b = \frac {1}{2 \pi}
$$

We need to be carefu l on how we com pute power! ! !

## Ra ndom sea cha racterization

$$
\mathbf {E} [ \zeta (t) ] = 0, \qquad \mathbf {E} [ \zeta (t) ^ {2} ] = \int_ {0} ^ {\infty} \mathbf {S} _ {\zeta \zeta} (\omega) d \omega
$$

The spectral moments of ord er n are d efi ned as :

$$
m _ {\zeta} ^ {n} = \int_ {0} ^ {\infty} \omega^ {n} \mathbf {S} _ {\zeta \zeta} (\omega) d \omega
$$

The n the va ria n ce a nd sta nd a rd d eviation ( RM S va l u e) a re

$$
\mathbf {v a r} [ \zeta ] = \mathbf {E} [ \zeta^ {2} ] = \mathbf {R} _ {\zeta \zeta} [ 0 ] = m _ {\zeta} ^ {0}
$$

$$
\sigma = \sqrt {m _ {\zeta} ^ {0}}.
$$

## Statistics of wave period

Average Wave period (1/average frequencyof the spectrum)

$$
T \quad \text {or} \quad T _ {1} = 2 \pi m _ {\zeta} ^ {0} / m _ {\zeta} ^ {1},
$$

Zero-crossing Wave period (average periodofzero up-crossings)

$$
T _ {z} = 2 \pi \sqrt {m _ {\zeta} ^ {0} / m _ {\zeta} ^ {2}},
$$

Average period between response maxima (crests)

$$
T _ {c} = 2 \pi \sqrt {m _ {\zeta} ^ {2} / m _ {\zeta} ^ {4}}.
$$

Notethatthe2πfactor intheexpressionsaboveappearsonlyifthemomentsarecalculated in the circular frequency domain.

## Stati stics of wave heig ht

Assuming narrow bandness,

mean value of wave amplitude

$$
\overline {{\zeta}} = 1. 5 \sqrt {m _ {\zeta} ^ {0}}.
$$

Significant wave amplitude

$$
\zeta_ {1 / 3} = 2 \sqrt {m _ {\zeta} ^ {0}}.
$$

Significant wave height

$$
H _ {1 / 3} = 4 \sqrt {m _ {\zeta} ^ {0}}.
$$

## Stati stics of Maxi ma

In marine applications $\epsilon \leq 0 . 6$ , and the assumption of narrow bandness is usually made. 08

![](images/9ea95c17c0906414e6f60d97b8261eb92c9bb75ca33dbbb5c6d639ebb363dcf6.jpg)

<details>
<summary>line</summary>

| Random Variable \(\xi\) | Probability Density (0.2) | Probability Density (0.4) | Probability Density (0.6) | Probability Density (0.8) | Probability Density (1.0) |
| --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 0 | 0 | 0 |
| 0.5 | ~0.5 | ~0.5 | ~0.5 | ~0.5 | ~0.5 |
| 1.0 | ~0.6 | ~0.6 | ~0.6 | ~0.6 | ~0.6 |
| 1.5 | ~0.4 | ~0.4 | ~0.4 | ~0.4 | ~0.4 |
| 2.0 | ~0.2 | ~0.2 | ~0.2 | ~0.2 | ~0.2 |
| 2.5 | ~0.1 | ~0.1 | ~0.1 | ~0.1 | ~0.1 |
| 3.0 | 0 | 0 | 0 | 0 | 0 |
</details>

(This holds not only for wave elevation, but also for wave induced motion of ships.)

## Long - a nd short-crested Seas

 Afte r the wi nd has blown consta ntly for a ce rta i n pe riod of ti me , the sea el evation ca n be assu med statisti ca l ly sta bl e . I n th is case , the sea is referred to as fully-developed.  
 I f th e i rreg u l a rity of th e o bse rved waves a re o n ly i n th e dom i na nt wi nd d i rection , so that there a re ma i n ly u n i-d i rectional wave crests with va ryi ng se pa ration but re ma i n i ng pa ral l el to each othe r, the sea is refe rred to as a long-crested i rreg u la r s e a .  
 Whe n i rreg u la rities a re a ppa re nt al ong the wave crests at rig ht a n g l es to th e d i re cti o n of th e wi n d , th e se a i s refe rred to as short crested or confused sea.

## Long -crested Seas

![](images/fbb9f8eaadb1d6c4a35e2ccf224affff2bfda9963a754b944ea1d6e9a3bdea7c.jpg)

<details>
<summary>surface_3d</summary>

| x [m] | y [m] | z [m] |
| --- | --- | --- |
| 0~200 | 0~200 | -2~2 |
</details>

## Short-crested Seas

![](images/3332de1d8b44f3c1f4823cfe13893c99e9346eb0eae50fc4db91cb94db097c55.jpg)

<details>
<summary>surface_3d</summary>

| x [m] | y [m] | z [m] |
| --- | --- | --- |
| 0~200 | 0~200 | -2~2 |
</details>

## Idea l ised spectra Long -crested seas

I n cases where no wave records are ava i lable , sta nd ard , id ea l ized , form u l ae ca n be used . O n e fa m i ly of id ea l ized spectra is the Bretschneither fa m i ly wh ich was d eveloped i n ea rly 1 950s :

$$
\mathbf {S} _ {\zeta \zeta} (\omega) = \frac {A}{\omega^ {5}} \exp \left(\frac {- B}{\omega^ {4}}\right)
$$

Modal freq uency

$$
\left. \frac {d S}{d \omega} \right| _ {\omega = \omega_ {0}} = 0; \quad \omega_ {0} = \left(\frac {4 B}{5}\right) ^ {\frac {1}{4}},
$$

S pectral moments

$$
m _ {\zeta} ^ {0} = \frac {A}{4 B} \qquad m _ {\zeta} ^ {1} = 0. 3 \frac {A}{B ^ {3 / 4}} \qquad m _ {\zeta} ^ {2} = \sqrt {\frac {\pi A ^ {2}}{1 6 B}}.
$$

(Th is fa m i ly ca n be used to re prese nt risi ng a nd fa l l i ng seas , as wel l as fu l ly d eveloped seas wi th n o swe l l a n d u n l i m i ted fetch . )

## Idea l ised Spectra

I n the 1 960’s , the Pierson-Moskowitz fa m i ly was d eveloped to forecast storm waves at a si ng l e poi nt i n fu l ly d eve loped seas with no swe l l us i ng wi nd d ata . Th is fa m i ly rel ates the pa ra mete rs A a nd B to the average wi nd speed at 1 9 . 5m above the sea su rface :

$$
A = 8. 1 \times 1 0 ^ {- 3} g ^ {2} \quad B = \frac {0 . 7 4 g}{\bar {V} _ {1 9 . 5}}
$$

The I TTC recom mends the use of the Modified Pierson-Moskowitz fa m i ly; sig n ifi ca nt wave he ig ht a nd ze rocrossi ng period or the average wave period is used :

$$
A = \frac {4 \pi^ {3} H _ {1 / 3} ^ {2}}{T _ {z} ^ {4}}; \quad B = \frac {1 6 \pi^ {3}}{T _ {z} ^ {4}} \quad \text {or} \quad A = \frac {1 7 2 . 7 5 H _ {1 / 3} ^ {2}}{T _ {1} ^ {4}}; \quad B = \frac {6 9 1}{T _ {1} ^ {4}}
$$

## Exa m ple ITTC spectra

![](images/13f3c8e55e1ce0cf12bd182c17911c1569842f2d0718d5b70c290a0826a44183.jpg)

<details>
<summary>line</summary>

| \(\omega\) | \(S\zeta(\omega) (T=7sec)\) | \(S\zeta(\omega) (T=9sec)\) | \(S\zeta(\omega) (T=10sec)\) |
| --- | --- | --- | --- |
| 0.5 | ~0.1 | ~2.6 | ~3.0 |
| 0.7 | ~2.0 | ~1.8 | ~1.5 |
| 1.0 | ~0.8 | ~0.4 | ~0.3 |
| 1.5 | ~0.2 | ~0.1 | ~0.05 |
| 2.0 | ~0.05 | ~0.02 | ~0.01 |
| 2.5 | ~0.01 | ~0.005 | ~0.002 |
| 3.0 | ~0.002 | ~0.001 | ~0.0005 |
| 3.5 | ~0.0005 | ~0.0002 | ~0.0001 |
</details>

## Other Spectra

## Ot h e r fa m i l i e s :

 The J O N SWAP spectral fa m i ly accou nts for the case of l i m ited fetch wi nd waves  
 The TMA spectra l fa m i ly is a n exte nsion of the J O N SWAP for fi n i te wate r d e pt h ,  
 The dou ble-peak Torsethaugen spectral fa m i ly accou nts for both swel l and wi nd waves ,  
The Och i six-pa ra mete r spectra l fa m i ly ca n be fitted to a l most a ny wave record (it cou ld accou nt for swel l a nd wi nd waves . )

For fu rth er d etai ls see Och i , K. ( 1 998 ) Ocea n Waves : The Stochasti c Approach , Ca m bridge U n iversity P ress . Ocea n Tech . Seri es .

## Spectra for Short-crested Seas

D i rectiona l spectra a re more rea l isti c a nd a re ve ry i m porta nt to ca l cu l ate loads on ma ri n e stru ctu res si n ce the motion response d e pe nds h ig h ly on the e n cou nte r a ng l e . For si m u l ation , it is com mon to se pa rate the d i rectiona l spectru m as a prod u ct of two fu n ctions :

$$
\mathbf {S} _ {\zeta \zeta} (\omega , \chi) = \mathbf {S} (\omega) M (\chi)
$$

is the s p read i ng fu n ction

![](images/220878cbfd45f5a296ec99479d496c7312211fd22d71405cdfa38f3b02592b0f.jpg)

<details>
<summary>surface_3d</summary>

| \(\omega\) | \(S\zeta(\omega, \chi)\) |
| --- | --- |
| ~0 | 0 |
| ~0.5 | ~0.05 |
| ~0.8 | ~0.25 |
| ~1.0 | ~0.05 |
| ~1.5 | 0 |
</details>

## Spread i ng Fu nction

$$
M (\chi) = \left\{ \begin{array}{l l} \frac {2 ^ {(2 s - 1)} s ! (s - 1) !}{\pi (2 s - 1) !} \cos^ {2 s} (\chi - \chi_ {0}) & \text {for} - \frac {\pi}{2} <   \chi - \chi_ {0} <   \frac {\pi}{2} \\ 0 & \text {Otherwise} \end{array} \right.
$$

wh e re χ0 is the dom i na nt wave propagation d i rection , a n d th e va l u es of s = 1 , 2 are com mon ly used . See L l oyd ( 1 9 8 9 ) fo r a m o re ge n e ra l form whe re |χ − χ0 | < α ; with α n ot n ecessa ri ly eq u al to π/2

![](images/02da830ad1117def48349271e5763b167733fbed1a31adbbb7bda3db60f3dadf.jpg)

<details>
<summary>line</summary>

| \(\chi - \chi0\) | \(M(\chi) (s=2)\) | \(M(\chi) (s=1)\) |
| --- | --- | --- |
| -1.5 | 0 | ~0.01 |
| -1.0 | ~0.05 | ~0.18 |
| -0.5 | ~0.45 | ~0.48 |
| 0 | ~0.85 | ~0.64 |
| 0.5 | ~0.45 | ~0.48 |
| 1.0 | ~0.05 | ~0.18 |
| 1.5 | 0 | ~0.01 |
</details>

## Ti me-doma i n Si m u lations

I f ζ(t) i s stat i o n a ry a n d G a u ss i a n o n t i m e i n te rva l [ 0 , T] , its real izations ca n be a pproxi mated to a ny d eg ree of

accu racy by

$$
\boxed {\zeta (t) = \sum_ {n = 1} ^ {N} \underbrace {\sqrt {2} \sigma_ {n}} _ {\bar {\zeta} _ {n}} \cos (\omega_ {n} t + \varepsilon_ {n}),}
$$

wi th N s u ffi ci e n tl y l a rg e ; wh e re $\sigma _ { \mathrm { n } }$ a re consta nts a nd the phases $\mathfrak { E } _ { \mathrm { n } }$ a re i nd e pe nd e nt id e nti ca l ly d istri b uted ra nd om va ri a b l e s w i t h u n i fo rm d i st ri b u t i o n i n [ 0 , 2π] .

The a utocorrel ation is g ive n by

$$
\mathbf {R} _ {\zeta \zeta} (\tau) = \mathbf {E} [ \zeta (t) \zeta (t + \tau) ] = \sum_ {n = 1} ^ {N} \sigma_ {n} ^ {2} \cos (\omega_ {n} \tau).
$$

## Why is it done th is way?

Since the autocorrelation for T=O gives the energy of n(t), it follows that

$$
\int_ {0} ^ {\infty} \mathbf {S} _ {\zeta \zeta} (\omega) d \omega \approx \sum_ {n = 1} ^ {N} \sigma_ {n} ^ {2},
$$

and we can write

$$
\sum_ {n = 1} ^ {N} \int_ {\omega_ {n} - \Delta \omega / 2} ^ {\omega_ {n} + \Delta \omega / 2} \mathbf {S} _ {\zeta \zeta} (\omega) d \omega = \sum_ {n = 1} ^ {N} \sigma_ {n} ^ {2},
$$

and take

$$
\sigma_ {n} ^ {2} = \int_ {\omega_ {n} - \Delta \omega / 2} ^ {\omega_ {n} + \Delta \omega / 2} \mathbf {S} _ {\zeta \zeta} (\omega) d \omega = \mathbf {S} _ {\zeta \zeta} (\omega_ {n}) \Delta \omega
$$

## Ti me-doma i n Si m u lations

$$
\boxed {\zeta (t) = \sum_ {n = 1} ^ {N} \underbrace {\sqrt {2} \sigma_ {n}} _ {\bar {\zeta} _ {n}} \cos (\omega_ {n} t + \varepsilon_ {n}),}
$$

![](images/c8666e5b1938d61809fd8bb8f2d1abc773046ad5596c4883ec7bd63d805d2b59.jpg)

<details>
<summary>area</summary>

| Feature | Description |
| --- | --- |
| Area | \(S\zeta\zeta(\omega n)\Delta\omega = \frac{1}{2}\bar{\zeta}_n^2\) |
| Integral | \(\Delta\omega = \omega_{j+1} - \omega_j = \frac{2\pi}{T_\)sim} |
| Function | j, n = 1, ..., N - 1; N = \(\omega_max - \omega_min / \Delta\omega\) |
| Function | \(\omega_n \in [\omega_j, \omega_{j+1}]\) |
| X-axis | \(\omega_min\) to \(\omega_max\) |
| Y-axis | \(S\zeta\zeta(\omega)\) |
</details>

# Form u lae fo r Ti me-da m i n Si m u lations

Long Crested Sea:

$$
\zeta (x, y, t) = \sum_ {n = 1} ^ {N} \sqrt {2 \mathbf {S} _ {\zeta \zeta} (\omega_ {n}) \Delta \omega} \cos (\omega_ {n} t + \varepsilon_ {n} - k _ {n} (x \cos \chi - y \sin \chi))
$$

Short Crested Sea:

$$
\begin{array}{l} \zeta (x, y, t) = \sum_ {n = 1} ^ {N} \sum_ {m = 1} ^ {M} \sqrt {2 \mathbf {S} _ {\zeta \zeta} (\omega_ {n} , \chi_ {m}) \Delta \omega \Delta \chi} \\ \cos (\omega_ {n} t + \varepsilon_ {n, m} - k _ {n} (x \cos \chi_ {m} - y \sin \chi_ {m})). \\ \end{array}
$$

## Spectra l Factorization Approach

The real izations of a sea su rface el evation a re mod el l ed by fi ltered wh ite n o i se :

$$
\mathbf {S} _ {\zeta \zeta} (\omega) \approx | H (j \omega) | ^ {2} \mathbf {S} _ {w w}
$$

A typical model is a $2 ^ { \mathsf { n d } } .$ -o rd e r syste m :

$$
H (s) = \frac {s}{s ^ {2} + 2 \xi \omega_ {n} s + \omega_ {n} ^ {2}}
$$

The para meters ca n be adj usted as fol lows ( Perez, 2005) :

$\pmb { \mathsf { S } } _ { \mathsf { w w } } = \mathsf { m a x } \ \pmb { \mathsf { S } } _ { \zeta \zeta }$  
${ \mathfrak { O } } _ { \mathfrak { n } }$ chose n to be the mod a l freq u e n cy.  
 $\xi$ is chose to the va ria n ce is the sa me ; a nd th us the RM S va l u e .

## Wi nd

Wi nd is com mon ly d ivid ed i n two com ponents ; a mean val u e and a fl u ctu ati ng com pon e nt, or g ust.

I t is a 3 D p he nome non , but i n ma ri n e a p pl i cations we restri ct it to 2 D , a nd velocities a re consid ered on ly i n the horizontal pla ne .

Wi nd is pa ra meterized by the velocity U a nd the d i rection ψ. The d i rection is ta ke n with respect to the N orth- East.

N ote th at , i n g e n e ra l , th e d i re cti o n of th e w i n d i s th e d i re cti o n fro m where the wi nd is com i ng from , e . g . , a S E wi nd blows from the S E towards NW.

## Wi nd Mea n-velocity Com ponent

S lowly-va ryi ng fl u ctu ations i n the mea n wi nd velocity ca n be mod eled by a 1 st ord er Gauss-M arkov Process :

$$
\boxed {\dot {\bar {U}} + \mu \bar {U} = w}
$$

wh e re w is Ga ussia n wh ite noise a nd $\mu \geq 0$ i s a co n sta n t .

The mag n itu d e of the velocity shou ld be restri cted by satu ration e l e me nts

$$
0 \leq \bar {U} _ {\min} \leq \bar {U} \leq \bar {U} _ {\max}
$$

## Wi nd Mea n-d i rection com ponent

S lowly-va ryi ng fl u ctu ations i n the mea n wi nd d i rection ca n also be i m plemented by a 1 st ord er Gauss-M arkov P rocess (Sore nse n , 2005) :

$$
\begin{array}{l} \dot {\psi} + \mu_ {2} \psi = w _ {2} \\ \psi_ {\min} \leq \psi \leq \psi_ {\max} \\ \end{array}
$$

T h e d i re cti o n i s ta ke n wi th res p e ct to th e ( n -fra m e ) .

N OTE : Th is d i rection is ofte n the d i rection from where the wi nd is blowi ng : N orth- East ( N E ) wi nd blows from the N E

## Wi nd velocity a nd d i rection

Sorensen , (2005)  
![](images/56173fd3a4e0c5e61e91697d6c69bf31c7777d123a4ed0121bfe653f12bbbfb0.jpg)

## Wi nd G ust

The wi nd g ust is mod el as a real ization of a stochasti c process with a pa rti cu la r spectru m (Sore nse n , 2005) .

![](images/24ee1b0fd2ff307ebbcf8b762430283faee620a61e688d8505391be33f5d3e66.jpg)

<details>
<summary>line</summary>

| f [Hz] | Harris \((m^{2}/s^{2}/Hz)\) | \(NORSOK, z=3 (m^{2}/s^{2}/\)Hz) | \(NORSOK, z=6 (m^{2}/s^{2}/\)Hz) | \(NORSOK, z=10 (m^{2}/s^{2}/\)Hz) |
| --- | --- | --- | --- | --- |
| \(10^{-4}\) | ~105 | ~130 | ~165 | ~190 |
| \(10^{-3}\) | ~105 | ~80 | ~90 | ~100 |
| \(10^{-2}\) | ~40 | ~20 | ~20 | ~20 |
| \(10^{-1}\) | ~0 | ~0 | ~0 | ~0 |
</details>

## Cu rrent

We may divide current modelling in two levels of detail:

Surface current, for use in modelling of surface vessel response  
·Full current profile, for use in modelling of risers,anchor lines etc.

## S u rface C u rrent

C u rre n t ve l ocity mag n itu d e :

$$
\dot {V} _ {c} + \mu V _ {c} = w.
$$

$$
V _ {c, \min} \leq V _ {c} \leq V _ {c, \max}
$$

Cu rre nt d i rection :

$$
\begin{array}{l} \dot {\psi} _ {c} + \mu_ {2} \psi_ {c} = w _ {2} \\ \psi_ {c, \min} \leq \psi_ {c} \leq \psi_ {c, \max} \\ \end{array}
$$

Th e d i rection is ta ke n with res pect to th e (n -fra me) . N OTE : Th is d i rection is th e d i rection to wh e re th e cu rre n t fl ows : N o rth - E ast ( N E ) cu rre n t fl ow towa rd s th e N E . (T h i s i s d i ffe re n t fro m th e co n ve n ti o n fo r wi n d )

## References

 Pe rez, T . (2005) S h i p M oti o n Co ntro l . S p ri nge r.  
 Och i , M . (2005) Ocean Waves : the stochastic approach . Cam bridge U n iversity Press .  
 Sorensen , A. J . (2005) “Marine Cybernetics. ” Lectu re notes , De pt. of M a ri ne Tech nology NTN U , NORWAY.