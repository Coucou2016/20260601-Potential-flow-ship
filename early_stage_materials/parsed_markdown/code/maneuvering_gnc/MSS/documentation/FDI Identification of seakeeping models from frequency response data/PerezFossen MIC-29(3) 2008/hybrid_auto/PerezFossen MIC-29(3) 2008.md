# Joint Identification of Infinite-Frequency Added Mass and Fluid-memory Models of Marine Structures

Tristan Perez 1, 3 Thor I. Fossen 2, 3

1Centre for Complex Dynamic Systems and Control—CDSC, The University of Newcastle, AUSTRALIA. E-mail: Tristan.Perez@newcastle.edu.au  
2Department of Engineering Cybernetics, Norwegian University of Science and Technology—NTNU, Norway. E-mail: fossen@ieee.org  
3Centre for Ships and Ocean Structures (CeSOS), Norwegian University of Science and Technology—NTNU, Norway.

## Abstract

This paper addresses the problem of joint identification of infinite-frequency added mass and fluid memory models of marine structures from finite frequency data. This problem is relevant for cases where the code used to compute the hydrodynamic coefficients of the marine structure does not give the infinite-frequency added mass. This case is typical of codes based on 2D-potential theory since most 3D-potential-theory codes solve the boundary value associated with the infinite frequency. The method proposed in this paper presents a simpler alternative approach to other methods previously presented in the literature. The advantage of the proposed method is that the same identification procedure can be used to identify the fluid-memory models with or without having access to the infinite-frequency added mass coefficient. Therefore, it provides an extension that puts the two identification problems into the same framework. The method also exploits the constraints related to relative degree and low-frequency asymptotic values of the hydrodynamic coefficients derived from the physics of the problem, which are used as prior information to refine the obtained models.

Keywords: Identification, Frequency-domain, Marine Structure Models.

## 1 Introduction

Time-domain models for rigid-body motion simulation of marine structures are of paramount importance for the development of training simulators, hardware-inthe loop testing simulators, wave energy converters and motion control systems. One way to develop these models consist of using hydrodynamic codes based on potential theory to compute frequency frequencydependent coefficients, and then use these data to obtain time-domain models via system identification. Two approaches can be followed for the latter part. One approach consists of using the Cummins equation (Cummins, 1962). The other approach consists of using the force-to-motion data directly (Perez and Lande, 2006). In this paper, we concentrate on the first approach.

The Cummins Equation relates the motion of the marine structure to the wave-induced forces in time domain under the assumption of linearity. This equation is an integro-differential equation that contains a convolution term representing fluid-memory effects associated with the dynamics of the radiation forces. This convolution term is inconvenient for simulation and also for the analysis and design of motion control systems. A linear-time-invariant model can be used to approximate the convolution in the Cummins equation. To obtain such a linear model, one can apply system identification. The identification problem can be posed either in the time or in the frequency domain. Due to these alternative problem formulations, there has been a great deal of work reported in the literature—see, for example, Jefferys et al. (1984), Jefferys and Goheen (1992), Yu and Falnes (1995), Holappa and Falzarano (1999), Hjulstad et al. (2004), Kristansen and Egeland (2003), Kristiansen et al. (2005), Jordan and Beltran-Aguedo (2004), McCabe et al. (2005), and Sutulo and Guedes-Soares (2005). Taghipour et al. (2008) provide a review and a summary of some of the methods.

Perez and Fossen (2008) compared and discussed the advantages and disadvantages of time- and frequency domain methods for the identification of the fluid memory models. It is argued that the frequency-domain identification results in estimation algorithms that are easier to implement and use than those resulting from time-domain formulations. Also, the quality of the models obtained is, in general, superior to those obtained with the time-domain methods proposed in the literature. The simplicity of the identification stems from the fact that the solution to the parameter estimation problem can be based on iterative linear Least Square (LS) optimisation. Prior knowledge derived from the hydrodynamics of the problem can be used to set constraints on the parameters, and the use of constraints in LS estimation leads, in general, to more accurate estimates—see $\mathrm { e . g . }$ , (Gourieroux and Monfort, 1995). On the negative side, It has also been discussed that the frequency-domain identification approach can be sensitive to the estimate of the infinitefrequency added mass coefficient provided by the 3Dhydrodynamic codes. The need of a reliable estimate of the infinite-frequency coefficients poses a bigger problem when using 2D-hydrodynamic codes, since these codes do not provide such estimate.

In this paper, we present a procedure that extends the application of frequency-domain identification of seakeeping models to the case where the hydrodynamic data does not include the infinite-frequency added mass coefficient (or one choses not to use it). That is, only finite frequency data is considered. The model identified relates the total radiation forces to the velocities, and it allows identifying the infinite-frequency added mass together with a fluid memory model. The proposed method is motivated by the work of Kaasen and Mo (2004), but provides a simpler alternative.

## 2 A Linear Model based on Cummins Equation

The equations of motion of a rigid marine structure in body-fixed coordinates can be linearised about an equilibrium point and heading and be expressed as

$$
\mathbf {M} _ {R B} \ddot {\boldsymbol {\xi}} = \boldsymbol {\tau}, \tag {1}
$$

where ξ represents the generalised perturbation position-orientation vector, $\tau$ is the vector of generalised forces and moments, and ${ \bf { M } } _ { R B }$ is the positivedefinite rigid-body generalised inertia matrix. The generalised force vector τ can be separated into three components:

$$
\boldsymbol {\tau} = \boldsymbol {\tau} _ {r a d} + \boldsymbol {\tau} _ {r e s} + \boldsymbol {\tau} _ {e x c}, \tag {2}
$$

where the first component corresponds to the radiation forces arising from the change in momentum of the fluid due to the motion of the structure, the second are restoring forces due to gravity and buoyancy, and the third component represents the pressure forces due to the incoming waves. For further background information about these models see for example Newman (1977) and Faltinsen (1990).

Cummins (1962) studied the radiation hydrodynamic problem in an ideal fluid in the time-domain and found the following representation for the linear pressure forces:

$$
\boldsymbol {\tau} _ {r a d} = - \mathbf {A} \ddot {\boldsymbol {\xi}} - \int_ {0} ^ {t} \mathbf {K} (t - t ^ {\prime}) \dot {\boldsymbol {\xi}} (t ^ {\prime}) d t ^ {\prime}. \tag {3}
$$

The first term in (3) represents forces due the accelerations of the structure, and A is the constant positive definite added inertia matrix. The second term represents fluid memory effects that incorporate the energy dissipation due the radiated waves consequence of the motion of the structure. The kernel of the convolution term, K(t), is the matrix of retardation or memory functions (impulse responses).

By renaming the variables and combining (1), (2), and (3), we obtain the Cummins Equation:

$$
(\mathbf {M} + \mathbf {A}) \ddot {\boldsymbol {\xi}} + \int_ {0} ^ {t} \mathbf {K} (t - t ^ {\prime}) \dot {\boldsymbol {\xi}} (t ^ {\prime}) d t ^ {\prime} + \mathbf {G} \boldsymbol {\xi} = \boldsymbol {\tau} _ {e x c}, \tag {4}
$$

Equation (4) describes the motion of the structure for any wave excitation $\tau _ { e x c } ( t )$ provided the linearity assumption is satisfied; and it forms the basis of more complex models, which can be obtained by adding nonlinear terms to represent different physical effects.

Table 1: Properties of Retardation Functions

<table><tr><td>Property</td><td>Implication on Parametric Models  $K_{ik}(s) = P_{ik}(s)/Q_{ik}(s)$ </td></tr><tr><td>1)  $\lim_{\omega \to 0} \mathbf{K}(j\omega) = \mathbf{0}$ </td><td>There are zeros at  $s = 0$ .</td></tr><tr><td>2)  $\lim_{\omega \to \infty} \mathbf{K}(j\omega) = \mathbf{0}$ </td><td>Strictly proper.</td></tr><tr><td>3)  $\lim_{t \to 0^+} \mathbf{K}(t) \neq \mathbf{0}$ </td><td>Relative degree 1.</td></tr><tr><td>4)  $\lim_{t \to \infty} \mathbf{K}(t) = \mathbf{0}$ </td><td>BIBO stable.</td></tr><tr><td>5) The mapping  $\dot{\boldsymbol{\xi}} \mapsto \boldsymbol{\mu}$  is passive</td><td> $\mathbf{K}(j\omega)$  is positive real (diagonal entries  $K_{ii}(j\omega)$  are positive real.</td></tr></table>

## 2.1 Frequency-domain Representation of the Radiation Forces

When (3) is considered in the frequency domain, it takes the following form (Newman, 1977; Faltinsen, 1990):

$$
\boldsymbol {\tau} _ {r a d} (j \omega) = - \mathbf {A} (\omega) \ddot {\boldsymbol {\xi}} (j \omega) - \mathbf {B} (\omega) \dot {\boldsymbol {\xi}} (j \omega). \tag {5}
$$

The parameters $\mathbf { A } ( \omega )$ and $\mathbf { B } ( \omega )$ are the frequencydependent added mass and damping respectively. Hydrodynamic codes based on potential theories (2D and 3D) are nowadays readily available for the computation of the frequency-dependent added mass $\mathbf { A } ( \omega )$ and potential damping $\mathbf { B } ( \omega )$ . These data are computed for a reduced set of frequencies of interest.

Ogilvie (1964) showed using the Fourier Transform of (4), that the following frequency-domain representation holds for the retardation functions:

$$
\mathbf {K} (j \omega) = \mathbf {B} (\omega) + j \omega [ \mathbf {A} (\omega) - \mathbf {A} ]. \tag {6}
$$

and also that

$$
\mathbf {A} = \lim _ {\omega \rightarrow \infty} \mathbf {A} (\omega), \tag {7}
$$

from which the name infinite-frequency added mass follows.

## 2.2 Frequency-domain Identification of the Convolution Terms

Expression (6) provides a way to compute the frequency response function $\mathbf { K } ( j \omega )$ for a finite set of frequencies. These data is the basis for the frequencydomain identification methods that seek a transfer function approximation to each entry of $\mathbf { K } ( j \omega )$ :

$$
\hat {K} _ {i k} (s) = \frac {P _ {i k} (s)}{Q _ {i k} (s)}, i = 1, \dots , 6, k = 1, \dots , 6. \tag {8}
$$

Apart from the non-parametric frequency-response data $K _ { i k } ( j \omega )$ , there is prior information that should be used as much as possible to refine the search for the appropriate model and its parameters. This is an important aspect of any identification problem since, in general, using prior information to set constraints on the model structure and parameters leads to more accurate estimates.

Table 1 summarizes the properties of the retardation functions and their implications on the parametric models (8). The left column shows properties in frequency- and time-domain that derive from the hydrodynamics of the problem under considerations. For example, the first and second property are the are consequence of no waves being generated due to the motion of the structure at zero and infinite frequency. The third property derives from the fact that ${ \bf K } ( 0 ^ { + } )$ equals the area under the curve of $\mathbf { B } ( \omega )$ . The fifth property is related to the dissipative characteristics of the radiation forces. For further discussion of these properties and their derivations see Perez and Fossen (2008) and references therein.

The properties shown on the left column of Table 1 have consequences on the models (8), and these are shown in the right column of the table. These properties are related to the structure of the models. Indeed, we can express the models (8) as

$$
\hat {K} _ {i k} (s) = \frac {P _ {i k} (s)}{Q _ {i k} (s)} = \frac {p _ {r} s ^ {r} + p _ {r - 1} s ^ {r - 1} + \dots + p _ {0}}{s ^ {n} + q _ {n - 1} s ^ {n - 1} + \dots + q _ {0}}. \tag {9}
$$

From Table 1, it is known that these transfer functions have a zero at $s = 0$ , hence, this information can be taken into account by writing the models as

$$
\begin{array}{l} \hat {K} _ {i k} (s) = \frac {s ^ {l} P _ {i k} ^ {\prime} (s)}{Q _ {i k} (s)} \tag {10} \\ = \frac {s ^ {l} (p _ {m} s ^ {m} + p _ {m - 1} s ^ {m - 1} + \ldots + p _ {0})}{s ^ {n} + q _ {n - 1} s ^ {n - 1} + \ldots + q _ {0}}, \\ \end{array}
$$

with the constraint on the order of the polynomials

$$
n = m + l + 1. \tag {11}
$$

Since, in general, $\mathbf { A } ( 0 ) \neq \mathbf { A } ( \infty )$ , it follows from (6) that there is unique zero of $K _ { i k } ( s )$ ar $s { = } 0$ . Therefore, $l = 1$ , and $m = n - 2$ . This is simple to verify from the non-parametric data since the phase of $K _ { i k } ( j \omega )$ at low frequencies tends to $l \pi / 2$ .

One way to exploit this information in the identification process is to consider

$$
\tilde {K} _ {i k} (j \omega) = \frac {K _ {i k} (j \omega)}{j \omega} \tag {12}
$$

as data for the identification of $P _ { i k } ^ { \prime } ( s )$ and $Q _ { i k } ( s )$ with the constraints

• deg $Q _ { i k } ( s ) = n ,$  
• deg $P _ { i k } ^ { \prime } ( s ) = m = n - 2 \ ( l { = } 1 )$

The identification problem can be posed as a complex curve fitting problem:

$$
\boldsymbol {\theta} ^ {\star} = \arg \min _ {\boldsymbol {\theta}} \sum_ {l} w _ {l} \left(\epsilon_ {l} ^ {*} \epsilon_ {l}\right), \tag {13}
$$

with

$$
\epsilon_ {l} = \tilde {K} _ {i k} (j \omega_ {l}) - \frac {P _ {i k} ^ {\prime} (j \omega_ {l} , \boldsymbol {\theta})}{Q _ {i k} (j \omega_ {l} , \boldsymbol {\theta})}. \tag {14}
$$

and the vector of parameters , θ is defined as

$$
\boldsymbol {\theta} = \left[ p _ {m}, \dots , p _ {0}, q _ {n - 1}, \dots , q _ {0} \right] ^ {T}. \tag {15}
$$

The weights wl can be exploited to select how important is the fit at different frequency ranges.

The above parameter estimation problem is a nonlinear LS problem in the parameters, which can be solved using a Gauss-Newton algorithm, or it can be linearized as indicated in the next section.

## 2.3 A Linear Iterative Solution

Levy (1959), proposed a linearisation of (13)

$$
\boldsymbol {\theta} ^ {\prime \star} = \arg \min _ {\boldsymbol {\theta}} \sum_ {l} w _ {l} ^ {\prime} \left(\epsilon_ {l} ^ {\prime *} \epsilon_ {l} ^ {\prime}\right), \tag {16}
$$

with

$$
\epsilon_ {l} ^ {\prime} = Q _ {i k} (j \omega_ {l}, \boldsymbol {\theta}) \tilde {K} _ {i k} (j \omega_ {l}) - P _ {i k} (j \omega_ {l}, \boldsymbol {\theta}). \tag {17}
$$

This problem is linear in the parameters, and thus easy to solve. Indeed, using a matrix form we can write

$$
\boldsymbol {\theta} ^ {\prime \star} = \arg \min _ {\boldsymbol {\theta}} \boldsymbol {\epsilon} ^ {\prime *} \mathbf {W} \boldsymbol {\epsilon} ^ {\prime}, \tag {18}
$$

with

$$
\boldsymbol {\epsilon} ^ {\prime} = \left[ \epsilon_ {1} ^ {\prime}, \dots , \epsilon_ {N} ^ {\prime} \right] ^ {T}, \quad \mathbf {W} = \operatorname{diag} \left(w _ {1} ^ {\prime}, w _ {2} ^ {\prime}, \dots , w _ {n} ^ {\prime}\right). \tag {19}
$$

Using this notation, we can write

$$
\boldsymbol {\epsilon} ^ {\prime} = \boldsymbol {\Gamma} - \boldsymbol {\Phi} \boldsymbol {\theta}, \tag {20}
$$

with the obvious definition for the matrices Φ and Γ.

The solution to (18)–(20) is then given by

$$
\boldsymbol {\theta} ^ {\prime \star} = \left(\boldsymbol {\Phi} ^ {T} \mathbf {W} \boldsymbol {\Phi}\right) ^ {- 1} \boldsymbol {\Phi} ^ {T} \mathbf {W} \boldsymbol {\Gamma}. \tag {21}
$$

The linearised problem (16) derives from the non-linear problem (13) by choosing

$$
w _ {l} = w _ {l} ^ {\prime} \left| Q (j \omega_ {l}, \boldsymbol {\theta}) \right| ^ {2}. \tag {22}
$$

This means that solving (16) can be thought of as solving (13) with the weights as given in (22). The weights $w _ { l } ^ { \prime }$ normally correspond to a rectangular window.

A problem with this linear formulation is that the identified transfer function does not in general give a good fitting. For example, when the data extends over a large range of frequencies or when $Q ( s )$ has poorly damped complex roots close to the imaginary axis, the weighting coefficients wl in (22) will weight the fit more heavily at high frequencies, and also at frequencies close to the resonant roots. This may give a bias in the parameter estimates.

Sanathanan and Koerner (1963) proposed a method to compensate for the bias introduced by the linearisation. This method consists in solving (18)–(20) iteratively using as weighting coefficients the inverse of the denominator $Q ( j \omega , \pmb \theta )$ evaluated at the previous estimate. This algorithm can be summarised in the following:

1. Set $\mathbf { W _ { 0 } } = \mathbf { I } .$  
2. Solve $\begin{array} { r } { \pmb { \theta } _ { k } ^ { \star } = \arg \operatorname* { m i n } _ { \pmb { \theta } } \ \epsilon ^ { \prime \ast } \mathbf { W } _ { \mathbf { k } } \epsilon ^ { \prime } , } \end{array}$  
3. Set $\mathbf { W _ { k + 1 } } = \mathrm { d i a g } ( | Q _ { i k } ( j \omega _ { l } , \pmb { \theta } _ { k } ) | ^ { - 2 } )$ go to 2 until convergence.

This choice of weighting coefficients in step 3 results in the following problem at each step k of the iteration:

$$
\begin{array}{l} \boldsymbol {\theta} _ {k} ^ {\star} = \arg \min _ {\boldsymbol {\theta}} \\ \sum_ {l} \left| \frac {Q _ {i k} (j \omega_ {l} , \boldsymbol {\theta}) \tilde {K} _ {i k} (j \omega_ {l})}{Q _ {i k} (j \omega_ {l} , \boldsymbol {\theta} _ {k - 1} ^ {\star})} - \frac {P _ {i k} (j \omega_ {l} , \boldsymbol {\theta})}{Q _ {i k} (j \omega_ {l} , \boldsymbol {\theta} _ {k - 1} ^ {\star})} \right| ^ {2}, \tag {23} \\ \end{array}
$$

Normally, after a few iterations (10 to 20), $\theta _ { k } ^ { \star } \approx \theta _ { k - 1 } ^ { \star }$ ; and thus, the original non-linear LS problem (13) is approximately recovered.

## 2.4 Order Selection, Stability, and Passivity

## 2.4.1 Oder selection

The order of the transfer functions depends on the hydrodynamic characteristics of the vessel; i.e., it depends on the hull shape. Based on the properties of the convolution terms given in Table 1, it follows that the minimum order transfer function that satisfies all the properties is a second order one:

$$
\hat {K} _ {i k} ^ {m i n} (s, \pmb {\theta}) = \frac {p _ {0} s}{s ^ {2} + q _ {1} s + q _ {0}}.
$$

Therefore, one can start with this minimum order transfer function $\scriptstyle ( n = 2 )$ , and increase the order while monitoring that the LS cost decreases—or simply by visual inspection of the fitted frequency response. If the order of the proposed model is too large, there will be over-fitting and therefore, the cost will increase; however before this happens, the value of the cost normally remains unchanged as one increments the order of the system.

## 2.4.2 Stability

The resulting model from the LS minimization may not necessarily be stable because stability is not enforced as a constraint in the optimisation. This can be addressed by reflecting the unstable poles about the imaginary axis and re-computing the denominator polynomial. That is,

• Compute the roots of $\lambda _ { 1 } , . . . , \lambda _ { n } \ \mathrm { o f } \ Q _ { i k } ( s , \hat { \pmb \theta } _ { i k } )$ .  
• If $\mathrm { R e } \{ \lambda _ { i } \} > 0$ , then set ${ \mathrm { R e } } \{ \lambda _ { i } \} = - { \mathrm { R e } } \{ \lambda _ { i } \}$ ,  
• Reconstruct the polynomial: $Q _ { i k } ( s ) ~ = ~ ( s ~ -$ $\lambda _ { 1 } ) ( s - \lambda _ { 1 } ) \cdot \cdot \cdot ( s - \lambda _ { n } )$ .

## 2.4.3 Passivity

It also follows from the properties given in Table 1, that the diagonal terms $K _ { i i } ( j \omega )$ are passive; i.e., the real part $B _ { i i } ( \omega )$ must me positive for all frequencies. For the off-diagonal terms $K _ { i k } ( j \omega )$ this may not be the case however.

The method of LS curve fitting is that it does not enforce passivity. If passivity is required $( \mathrm { i . e . , } B _ { i k } ( \omega ) >$ 0), a simple way to ensure it is to try different order approximations and choose the one that is passive. The approximation is passive if

$$
\operatorname{Re} \left\{\frac {P _ {i k} \left(j \omega_ {l} , \boldsymbol {\theta}\right)}{Q _ {i k} \left(j \omega_ {l} , \boldsymbol {\theta}\right)} \right\} > 0. \tag {24}
$$

When this is checked, one should evaluate the transfer function at low and high frequencies—below and above the frequencies used for the parameter estimation.

Normally, the low-order approximations models of the convolution terms given by this method are passive. Therefore, one can reduce the order and trade-off fitting accuracy for passivity. A different approach would be optimise the numerator of the obtained non passive model to obtain a passive approximation—this goes beyond the scope of this paper, but the reader is referred to Damaren (2000) and references therein.

## 3 Joint Identification of Infinite-frequency Added Mass and Fluid Memory Models

Hydrodynamic codes based on 2-D potential theory normally do not provide the value of the infinite frequency added mass coefficient $\begin{array} { r } { \mathbf { A } = \operatorname* { l i m } _ { \omega \to \infty } \mathbf { A } ( \omega ) } \end{array}$ . In these cases, we cannot form $\mathbf { K } ( j \omega )$ as indicated in (6).

Kaasen and Mo (2004) addressed this problem by making a partial-fraction expansion of the real part of $\hat { K } _ { i k } ( s )$ in terms of $\omega ^ { 2 }$ . The poles and residuals of this expansion can be estimated using Least-squares and the damping data $B _ { i k } ( \omega )$ . Then $\hat { K } _ { i k } ( s )$ can be obtained by mapping poles and the residuals of the partial-fraction expansion of its real part into the poles and residuals of a partial fraction expansion of $\hat { K } _ { i k } ( s )$ in terms jω.

In this section, we propose a simpler alternative to the method of Kaasen and Mo (2004). The proposed method exploits the knowledge and methods used in the identification of $\hat { K } _ { i k } ( s )$ discussed in the Section 2.2, and therefore, it provides an extension of those results putting the two identification problems into the same framework.

On the one hand, the radiation forces in the frequency-domain given in (5) can be expressed

$$
\tau_ {r a d, i} (j \omega) = - \left[ \frac {B _ {i k} (\omega)}{j \omega} + A _ {i k} (\omega) \right] \ddot {\xi} _ {k} (s), \tag {25}
$$

where the expression in brackets gives the complex coefficient

$$
\tilde {A} (j \omega) \triangleq \frac {B _ {i k} (\omega)}{j \omega} + A _ {i k} (\omega). \tag {26}
$$

On the other hand, taking the Laplace transform of (3), and assuming a rational approximation for the convolution term we obtain

$$
\begin{array}{l} \hat {\tau} _ {r a d, i} (s) = - \left[ A _ {i k} s + \frac {P _ {i k} (s)}{Q _ {i k} (s)} \right] \dot {\xi} _ {k} (s), (27) \\ = - \left[ A _ {i k} + \frac {P _ {i k} ^ {\prime} (s)}{Q _ {i k} (s)} \right] \ddot {\xi} _ {k} (s) (28) \\ \end{array}
$$

This representation can be traced back to the work of S¨oding (1982), and it has been used by Xia et al. (1998) and Sutulo and Guedes-Soares (2005), but with a different approach to that presented in this paper.

The transfer function in brackets in (28) can be further expressed as

$$
\hat {\tilde {A}} _ {i k} (s) = \frac {R _ {i k} (s)}{S _ {i k} (s)} = \frac {A _ {i k} Q _ {i k} (s) + P _ {i k} ^ {\prime} (s)}{Q _ {i k} (s)}. \tag {29}
$$

Thus, we can follow the same approach as in Section 2.2 and use Least-squares optimisation to estimate the parameters of the approximation (29) given the frequency-respose data (26):

$$
\boldsymbol {\theta} ^ {\star} = \arg \min _ {\boldsymbol {\theta}} \sum_ {l} w _ {l} \left(\epsilon_ {l} ^ {*} \epsilon_ {l}\right), \tag {30}
$$

with

$$
\epsilon_ {l} = \tilde {A} _ {i k} (j \omega_ {l}) - \frac {R _ {i k} (j \omega_ {l} , \boldsymbol {\theta})}{Q _ {i k} (j \omega_ {l} , \boldsymbol {\theta})}, \tag {31}
$$

and the constraint that $n = \deg R _ { i k } ( s ) = \deg R _ { i k } ( s )$ . We also know from Section 2.4 that the minimum order approximation is of $n = 2$ . Therefore, we can start with this order and increment to improve the fit if necessary.

It should be noted as well that since we have normalised the polynomial $Q _ { i k } ( s )$ to be monic, then

$$
\hat {A} _ {i k} = \lim _ {\omega \rightarrow \infty} \frac {R _ {i k} (s , \boldsymbol {\theta} ^ {\star})}{S _ {i k} (s , \boldsymbol {\theta} ^ {\star})}, \tag {32}
$$

that is, the infinite-frequency added mass $A _ { i k }$ is the coefficient of the highest order term of $R _ { i k } ( s , \pmb \theta ^ { \star } )$ . Also, after obtaining $R _ { i k } ( s , \pmb \theta ^ { \star } )$ and $S _ { i k } ( s , \pmb \theta ^ { \star } )$ , we can recover the polynomials for the fluid-memory model:

$$
\begin{array}{l} Q _ {i k} (s, \boldsymbol {\theta} ^ {\star}) = S _ {i k} (s, \boldsymbol {\theta} ^ {\star}), \\ D _ {i k} (s, \boldsymbol {\theta} ^ {\star}) = D _ {i k} (s, \boldsymbol {\theta} ^ {\star}) = \hat {s} _ {i k} (s, \boldsymbol {\theta} ^ {\star}). \end{array} \tag {33}
$$

$$
P _ {i k} (s, \boldsymbol {\theta} ^ {\star}) = R _ {i k} (s, \boldsymbol {\theta} ^ {\star}) - \hat {A} _ {i k} S _ {i k} (s, \boldsymbol {\theta} ^ {\star}).
$$

## 4 Model Quality Assessment

In order to assess the quality of the model, one can compare the frequency-dependant added mass $A _ { i k } ( \omega )$ and damping coefficients $B _ { i k } ( \omega )$ provided by the hydrodynamic code, with those reconstructed from the estimated retardation function:

$$
\hat {B} _ {i k} (\omega) = \Re \{\hat {K} _ {i k} (s = j \omega) \},
$$

$$
\hat {A} _ {i k} (\omega) = \frac {\Im \{\hat {K} _ {i k} (s = j \omega) \}}{\omega} + \hat {A} _ {i k}. \tag {34}
$$

Good fitting of these coefficients give confidence in the estimated values of $\hat { K } _ { i k } ( s )$ and $\hat { A } _ { i k }$ .

## 5 Case Studies

To illustrate the use of the method proposed in the previous section, we consider the hydrodynamic data of three different vessels:

• Containership,  
• FPSO,  
• Semi-submersible.

The hydrodynamic data for all vessels is computed with WAMIT. This code gives an estimate of the value of the infinite-frequency added mass; and therefore, we have means to validate the estimated parameters if we assume the values given by the code are close to the true parameters.

The containership vessel is the same vessel used in (Taghipour et al., 2008) (Perez and Fossen, 2008). The FPSO and the Semi-submersible are the example demos provided with the Marine Systems Simulator (www.marinecontrol.org).

For the containership vessel, we have computed only the part of the model corresponding the vertical-plane motion (heave and pitch). Table 2 shows the results of the estimated infinite-frequency added mass coefficients, together with the true values and the absolute relative error. Figure 1 shows the fitting of the complex coefficient $\tilde { A } _ { 3 3 } ( j \omega )$ , the reconstruction of the added mass and damping based on (34). As we can see from this figure, the fitting is relatively good.

Tables 3 and 4 show the estimation results in six degrees of freedom for the FPSO and Semi-submersible respectively. Note that since the semi-submesible hull has fore-aft and port-starboard symmetry, there are less couplings. Figures 2, 3, and 4 show the fit for particular couplings.

As we can see from the examples used in this section, the method is able to estimate the infinite-frequency added mass coefficient with good accuracy and also to provide high-order fittings as those shown for semisubmersible.

Table 2: True and Identified Added Mass Coefficients for a Containership

<table><tr><td>True Value</td><td>Identified</td><td>Rel. Err.</td></tr><tr><td> $A_{33} = 1.0397e08$ </td><td> $\hat{A}_{33} = 1.0401e08$ </td><td>0.03 %</td></tr><tr><td> $A_{35} = 1.1785e09$ </td><td> $\hat{A}_{35} = 1.1148e09$ </td><td>5.4 %</td></tr><tr><td> $A_{55} = 3.9617e11$ </td><td> $\hat{A}_{55} = 3.8841e11$ </td><td>1.95 %</td></tr></table>

## 6 Conclusions

This paper addresses the problem of joint identification of infinite-frequency added mass and fluid memory models from finite-frequency data. This problem is particularly relevant to the cases where the hydrodynamic code used to compute the coefficients does not give the infinite frequency added mass coefficient. This is the case for codes based on 2D potential theory.

This problem has been previously addressed via partial-fraction expansions by Kaasen and Mo (2004). The method proposed in this paper presents simpler alternative to the existing proposal. The advantage of the method is that the same identification procedure can be used to identify $\hat { K } _ { i k } ( s )$ when the $A _ { i k }$ is given and $\hat { K } _ { i k } ( s )$ and $\hat { A } _ { i k }$ when the latter is not given. The method also exploits the information related to relative degree and low-frequency asymptotic values of the hydrodynamic coefficients derived from the physics of the problem. This information is used to impose constraints on the model structure.

Table 3: Infinite-Freq. Coefficients for the FPSO.

<table><tr><td>True Value</td><td>Identified</td><td>Rel. Err.</td></tr><tr><td> $A_{11} = 3.045e06$ </td><td> $\hat{A}_{11} = 3.036e06$ </td><td>0.3 %</td></tr><tr><td> $A_{22} = 2.124e07$ </td><td> $\hat{A}_{22} = 2.182e07$ </td><td>2.8 %</td></tr><tr><td> $A_{33} = 1.7283e08$ </td><td> $\hat{A}_{33} = 1.731e08$ </td><td>1.5 %</td></tr><tr><td> $A_{44} = 9.516e9$ </td><td> $\hat{A}_{44} = 9.508e09$ </td><td>0.1 %</td></tr><tr><td> $A_{55} = 3.915e11$ </td><td> $\hat{A}_{55} = 3.919e11$ </td><td>0.1 %</td></tr><tr><td> $A_{66} = 5.461e10$ </td><td> $\hat{A}_{66} = 5.584e10$ </td><td>2.2 %</td></tr><tr><td> $A_{13} = -2.351e06$ </td><td> $\hat{A}_{13} = -2.304e06$ </td><td>2.0 %</td></tr><tr><td> $A_{15} = -3.316e08$ </td><td> $\hat{A}_{15} = -3.304e08$ </td><td>0.4 %</td></tr><tr><td> $A_{24} = -2.375e07$ </td><td> $\hat{A}_{24} = -2.5490e07$ </td><td>7.3 %</td></tr><tr><td> $A_{26} = 3.478e07$ </td><td> $\hat{A}_{26} = 3.498e07$ </td><td>0.6 %</td></tr><tr><td> $A_{35} = -3.566e07$ </td><td> $\hat{A}_{35} = -3.749e07$ </td><td>5.1 %</td></tr><tr><td> $A_{46} = -2.139e08$ </td><td> $\hat{A}_{46} = -1.989e08$ </td><td>6.9 %</td></tr></table>

Table 4: Infinite-Freq. Coefficients for the Semisubmersible.

<table><tr><td>True Value</td><td>Identified</td><td>Rel. Err.</td></tr><tr><td> $A_{11} = 7.363e06$ </td><td> $\hat{A}_{11} = 7.546e06$ </td><td>2.5 %</td></tr><tr><td> $A_{22} = 3.393e07$ </td><td> $\hat{A}_{22} = 3.589e07$ </td><td>5.8 %</td></tr><tr><td> $A_{33} = 5.929e07$ </td><td> $\hat{A}_{33} = 6.023e07$ </td><td>1.6 %</td></tr><tr><td> $A_{44} = 6.065e10$ </td><td> $\hat{A}_{44} = 6.083e10$ </td><td>0.3 %</td></tr><tr><td> $A_{55} = 5.021e10$ </td><td> $\hat{A}_{55} = 4.975e10$ </td><td>0.9 %</td></tr><tr><td> $A_{66} = 3.756e10$ </td><td> $\hat{A}_{66} = 3.729e10$ </td><td>0.7 %</td></tr><tr><td> $A_{13} = 8.663e07$ </td><td> $\hat{A}_{13} = 9.570e7$ </td><td>10 %</td></tr><tr><td> $A_{24} = -4.624e08$ </td><td> $\hat{A}_{24} = -5.075e8$ </td><td>9.7 %</td></tr></table>

## References

Ag¨uero, J. C. System Identification Methodologies $I n \textmd { - }$ croporating Constraints. Ph.D. thesis, Department of Elec. Eng. and Comp. Sc., The Univeristy of Newcastle, Australia, 2005.  
Cummins, W. The impulse response function and ship  
motion. Technical Report 1661, David Taylor Model Basin–DTNSRDC, 1962.  
Damaren, C. Time-domain floating body dynamics by rational approximations of the radiation impedance and diffraction mapping. Ocean Engineering, 2000. 27:687–705.  
Faltinsen, O. Sea Loads on Ships and Offshore Structures. Cambridge University Press, 1990.  
Gourieroux, C. and Monfort, A. Statistics and Econometric Models: General Concepts, Estimation, Prediction and Algorithms, volume 1 of Themes in Modern Econometrics. Cambridge Univ. Press, 1995.  
Hjulstad, A., Kristansen, E., and Egeland, O. Statespace representation of frequency-dependant hydrodynamic coefficients. In Proc. IFAC Confernce on Control Applications in Marine Systems. 2004 .  
Holappa, K. and Falzarano, J. Application of extended state space to nonlinear ship rolling. Ocean Engineering, 1999. 26:227–240.  
Jefferys, E., Broome, D., and Patel, M. A transfer function method of modelling systems with frequency depenant coefficients. Journal of Guidance Control and Dynamics, 1984. 7(4):490–494.  
Jefferys, E. and Goheen, K. Time domain models from frequency domain descriptions: Application to marine structures. International Journal of Offshore and Polar Engineering, 1992. 2:191–197.  
Jordan, M. and Beltran-Aguedo, R. Optimal identification of potential-radiation hydrodynamics of moored floating stuctures. Ocean Engineering, 2004. 31:1859–1914.  
Kaasen, K. and Mo, K. Efficient time-domain model for frequency-dependent added mass and damping. In 23rd Conference on Offshore Mechanics and Artic Engineering (OMAE), Vancouver, Canada. 2004 .  
Kristansen, E. and Egeland, O. Frequency dependent added mass in models for controller design for wave motion ship damping. In 6th IFAC Conference on Manoeuvring and Control of Marine Craft MCMC’03, Girona, Spain. 2003 .  
Kristiansen, E., Hjuslstad, A., and Egeland, O. Statespace representation of radiation forces in timedomain vessel models. Ocean Engineering, 2005. 32:2195–2216.  
Levy, E. Complex curve fitting. IRE Trans. Autom. Control, 1959. AC-4:37–43.  
McCabe, A., Bradshaw, A., and Widden, M. A timedoamin model of a floating body usign transforms. In Proc. of 6th European Wave and Tidal energy Conference. University of Strathclyde, Glasgow, U.K., 2005 .  
Newman, J. Marine Hydrodynamics. MIT Press, 1977.  
Ogilvie, T. Recent progress towards the understanding and prediction of ship motions. In 6th Symposium on Naval Hydrodynamics. 1964 .  
Perez, T. and Fossen, T. I. Time-domain vs. frequencydomain identification of parametric radiation force models for marine structures at zero speed. Modeling Identification and Control, published by The Norwegian Society of Automatic Control., 2008. 29(1):1– 19.  
Perez, T. and Lande, Ø. A frequency-domain approach to modelling and identification of the force to motion vessel response. In Proc. of 7th IFAC Conference on Manoeuvring and Control of marine Craft, Lisbon, Portugal. 2006 .  
Sanathanan, C. and Koerner, J. Transfer function synthesis as a ratio of two complex polynomials. IEEE Trnas. of Autom. Control, 1963.  
S¨oding, H. Leckstabilit¨at im seegang. Technical report, Report 429 of the Institue f¨ur Schiffbau, Hamburg, 1982.  
Sutulo, S. and Guedes-Soares, C. An implementation of the method of auxiliary state variables for solving seakeeping problems. Int. Ship Buildg. Progress, 2005. 52(4):357–384.  
Taghipour, R., Perez, T., and Moan, T. Hybrid frequency–time domain models for dynamic response analysis of marine structrues. Ocean Engineering, 2008. doi:10.1016/j.oceaneng.2007.11.002.  
Verhaegen, M. and Verdult, V. Filtering and System Identification. Cambridge, 2007.  
Xia, J., Wang, Z., and Jensen, J. Nonlinear wave-loads and ship responses by a time-domain strip theory. Marine strcutures, 1998. 11:101–123.  
Yu, Z. and Falnes, J. Spate-space modelling of a vertical cylinder in heave. Applied Ocean Research, 1995. 17:265–275.

![](images/cc43808c11d12790a3c9fae03913efd13cbbd8607e5120faec44b98efd44f586.jpg)  
Figure 1: Fitting results for the containership. Left column: Frequency response $\tilde { A } _ { 3 3 } ( j \omega )$ and estimate. Right column: Reconstruction of added mass and damping from the identified fluid memory function $\hat { K } _ { 3 3 } ( j \omega )$ based on an 3rd order approximation.

![](images/41e111fc1a2a7fa6976ab6d547566554ac3106ec4061a93cad31db7c4e9cfc19.jpg)  
Figure 2: Fitting results for the FPSO. Left column: Frequency response $\tilde { A } _ { 3 3 } ( j \omega )$ and estimate. Right column: Reconstruction of added mass and damping from the identified fluid memory function $\hat { K } _ { 3 3 } ( j \omega )$ based on an 2nd order approximation.

![](images/1ae4a2812f1315b21a541285b0209abf21fecc98aedf51d1304859f67377b250.jpg)  
Figure 3: Fitting results for the FPSO. Left column: Frequency response $\tilde { A } _ { 2 4 } ( j \omega )$ and estimate. Right column: Reconstruction of added mass and damping from the identified fluid memory function $\hat { K } _ { 2 4 } ( j \omega )$ based on an 6th order approximation.

![](images/03172b2584cb271a7ed652b41a97ca00c61792973aba2e356c15b45b89bd2d1c.jpg)  
Figure 4: Fitting results for the semi-submersible. Left column: Frequency response $\tilde { A } _ { 3 3 } ( j \omega )$ and estimate. Right column: Reconstruction of added mass and damping from the identified fluid memory function $\hat { K } _ { 3 3 } ( j \omega )$ based on an 10th order approximation.