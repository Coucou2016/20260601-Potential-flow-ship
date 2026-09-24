# 高速滑行艇 2.5D 运动预报理论、公式与实现备查手册

项目：`20260717-planningvessel-code`

整理日期：2026-07-26

用途：本文件把此前实现高速滑行艇运动预报程序时使用到的理论、公式、资料提取结果、代码实现约定、验证目标和当前边界统一整理成一份可长期查阅的 Markdown 手册。它不是论文原文摘录，而是面向本项目代码实现与后续研究复用的“理论到程序”说明书。

> 重要说明：此前任务中提到的 `planning whistle` 章节，按上下文理解为 Faltinsen 书中第 9 章 `Planing Vessels`，即滑行艇章节。本项目第一版以其中的高速滑行艇纵向 2.5D/二维加时间思想为核心，重点实现迎浪下升沉、纵摇、垂向加速度、频域响应幅值算子和时域响应。

---

## 0. 本手册如何使用

这份手册按“资料来源 -> 物理约定 -> 静水平衡 -> 线性运动方程 -> 波浪激励 -> 频域响应 -> 时域响应 -> 六自由度输出 -> 完整 2.5D 升级路线 -> 验证判据”的顺序组织。

以后如果需要回顾某个公式从哪里来、代码里对应哪一步、为什么当前结果只能说“部分合理”而不能说“完整 2.5D 已验证”，可以从以下几个入口快速定位：

| 查阅目的 | 推荐章节 |
|---|---|
| 想知道参考了哪些文献和开源代码 | 第 1 章 |
| 想统一坐标、自由度、符号 | 第 2 章 |
| 想理解 Savitsky/Faltinsen 静水滑行平衡 | 第 4 章 |
| 想查升沉/纵摇线性方程和矩阵 | 第 5 章 |
| 想查规则波、遭遇频率、谱模型 | 第 6 章 |
| 想查频域响应幅值算子计算 | 第 7 章 |
| 想查非线性时域方程 | 第 8 章 |
| 想判断结果是否合理、能否对照文献 | 第 11、12 章 |
| 想知道完整 2.5D 还差什么 | 第 10、13 章 |
| 想快速找到代码位置 | 第 15 章 |

---

## 1. 资料来源与提取结论

### 1.1 本地资料目录

资料主要来自：

- `D:\Projects\20260601-Potential-flow-ship\early_stage_materials`
- `D:\Projects\20260601-Potential-flow-ship\20260717-planningvessel-code\docs`
- `D:\Projects\20260601-Potential-flow-ship\20260717-planningvessel-code\planing_seakeeping`

其中 `early_stage_materials` 已用 `docs/materials_inventory.csv` 做系统索引。索引时排除了虚拟环境、缓存、日志等工具性文件，保留文献、解析后的 Markdown、开源程序、数据和验证资料。

### 1.2 核心文献和用途

| 来源 | 在本项目中的作用 | 当前实现状态 |
|---|---|---|
| Faltinsen, *Hydrodynamics of High-Speed Marine Vehicles*, Chapter 9 | 滑行艇静水几何、升沉/纵摇线性运动方程、波浪激励、频域响应幅值算子、非线性时域方程、特征值验证算例 | 已作为纵向核心模型实现 |
| Savitsky 1964 | 滑行艇静水升力、压力中心、纵倾平衡的半经验公式 | 已用于稳态平衡求解 |
| Savitsky & Brown 1976 | 粗水滑行艇增阻、冲击加速度、实用工程统计 | 当前作为扩展和对照背景，未作为主响应公式 |
| Fridsma 1969/1971 | 系统粗水滑行艇试验，可对照规则波/不规则波运动幅值和加速度 | 1969 线性长波运动与重心加速度 Gate 2 子项已通过；非线性冲击峰值和 1971 不规则波仍待后续验证 |
| Sun & Faltinsen 2010 | Fridsma configuration A 的规定运行状态和对照背景 | 已用于规定 trim、wetted length 的开发基准 |
| Katayama, Hinami & Ikeda | 超高速滑行艇规则迎浪运动、跳跃/非跳跃现象 | 定性趋势和分类已接入，幅值曲线仍需补齐数字化数据 |
| Ma 2005 2.5D | Wigley III 与 SL-7 的 2.5D 水动力系数对照，是完整站位式 2.5D 的硬验证 | Wigley III Gate 1 已于 2026-08-16 通过；SL-7 真实 offsets 与独立扩展验证仍待补齐 |
| Fossen marine craft 6DOF 表述 | 六自由度向量、相对速度、海流/风载荷建模框架 | 已用于统一输出和环境速度约定 |

### 1.3 开源代码和程序模型参考

| 开源或本地程序 | 用途 | 是否作为生产依赖 |
|---|---|---|
| OpenPlaning | 参考 Savitsky/Faltinsen 静水平衡、湿长、矩阵、porpoising 检查的实现思路 | 否；本项目自包含实现 |
| PDSTRIP | 参考 strip theory、截面水动力、外部程序 smoke test 和 sectionresults 解析 | 否；作为诊断和升级路径 |
| Capytaine / Nemoh / HAMS | 势流边界元和辐射/绕射求解的潜在参考 | 否；当前未作为核心依赖 |
| MSS / PythonVehicleSimulator | Fossen 风格 6DOF 船舶运动建模参考 | 否；只借鉴表述和相对速度思想 |
| waveresponse 等谱响应工具 | 频域响应与波谱积分工作流参考 | 否；当前自写波谱与时域叠加 |

### 1.4 当前程序的真实定位

当前程序可以概括为：

> 一个以 Faltinsen 第 9 章与 Savitsky 静水滑行平衡为核心的高速滑行艇纵向运动预报程序，输出格式统一为六自由度，但迎浪对称工况下重点可信自由度是升沉、纵摇和垂向加速度。

它还不能被称为“完整且已验证的整船 2.5D 运动预报系统”。原因是：

1. 纵向 Faltinsen prescribed-state 特征值基准已通过。
2. 数值 sanity 和部分物理趋势检查已通过。
3. Ma 2005 Wigley III 水动力 Gate 1 已通过，说明线性高速 2.5D 核心水动力链已经获得来源独立的系数验证。
4. 规则迎浪整船 Gate 2 当前为 `17/20 PASS`；Begovic 三航速升沉幅值、纵摇幅值和已解析主峰频率仍失败。
5. Fridsma 线性长波子集已通过，但艏部砰击峰值、Katayama 非线性跳跃和不规则波统计不属于当前已验证范围。
6. SL-7 真实 offsets、完整二维入水压力、Sun--Troesch 五频率八系数和后续多船型验证仍待闭合。
7. 因此当前模型适合作为经 Gate 1 验证的线性高速 2.5D 开发基线，但不能把全部整船输出解释为已经通过独立运动试验验证。

---

## 2. 符号、坐标和自由度约定

### 2.1 六自由度向量

船舶运动通常写成六自由度形式：

$$
\boldsymbol{\eta} =
\begin{bmatrix}
x & y & z & \phi & \theta & \psi
\end{bmatrix}^T
$$

其中：

- $x$：surge（纵荡，船沿纵向前后移动）。
- $y$：sway（横荡，船沿横向左右移动）。
- $z$：heave（升沉，船整体上下移动）。
- $\phi$：roll（横摇，绕纵轴转动）。
- $\theta$：pitch（纵摇，绕横轴转动）。
- $\psi$：yaw（艏摇，绕竖轴转动）。

本项目代码输出列采用：

$$
[surge,\ sway,\ heave,\ roll,\ pitch,\ yaw]
$$

但 v1 的主计算模型只对迎浪对称工况下的 heave（升沉）和 pitch（纵摇）进行水动力求解。head sea（迎浪）且船型左右对称时，sway、roll、yaw 的一阶线性响应按对称性置零，并在输出元数据中标注原因。

### 2.2 本项目纵向坐标约定

为了和 Faltinsen 第 9 章及当前代码一致，本项目纵向运动核心采用以下局部约定：

- $x$：沿船长方向，代码中正方向按 aft（向艉）处理。
- $z$ 或 $\eta_3$：升沉位移。
- $\eta_5$：纵摇角，小角度时可近似等于 $\theta$。
- $L$：船长。
- $B$：船宽，尤其是 chine beam（舷宽或折角宽度）。
- $\beta$：deadrise angle（底升角，即 V 型底横剖面与水平面的夹角）。
- $\tau$：trim angle（静态纵倾角）。
- $M$：质量。
- $I_{55}$：纵摇转动惯量，代码中用 $I_{55}=M r_{55}^2$。
- $r_{55}$：纵摇回转半径。
- $lcg$：重心到参考点的纵向位置。
- $vcg$：重心高度。
- $\rho$：水密度。
- $g$：重力加速度。

### 2.3 速度与无量纲数

船速：

$$
U
$$

基于船宽的 Froude 数：

$$
Fn_B = \frac{U}{\sqrt{gB}}
$$

基于船长的 Froude 数：

$$
Fn_L = \frac{U}{\sqrt{gL}}
$$

对滑行艇，$Fn_B$ 很常用，因为滑行升力和湿宽/湿长关系与船宽强相关。资料中常见经验判断为：

- $Fn_B < 0.5$：更多接近排水或过渡低速状态。
- $0.5 < Fn_B < 1.5$：半滑行或过渡滑行。
- $Fn_B \gtrsim 1.5$：更接近真正滑行状态。

更本质的判据不是只看 Froude 数，而是看船重中有多大比例由 hydrodynamic lift（动升力，来自底部高速流动压力）承担。当动升力成为主要支撑力时，船进入滑行物理状态。

### 2.4 湿长和平均湿长

滑行艇底部与水接触的长度常用：

- $L_K$：wetted keel length（龙骨湿长）。
- $L_C$：wetted chine length（舷侧折角湿长）。
- $\lambda_W$：无量纲平均湿长。

本项目采用：

$$
\lambda_W = \frac{L_K + L_C}{2B}
$$

这个量连接几何、升力、水动力矩阵和验证算例。Faltinsen 表 9.2 的规定状态使用 $\lambda_W=4$，是本项目纵向特征值验证的重要基准。

---

## 3. 滑行艇运动预报的物理背景

### 3.1 为什么滑行艇不能简单按普通排水船处理

普通排水船的浮力主要来自静水排水体积；高速滑行艇在高航速下，船底相对水面产生强烈动压力，支撑力中有显著甚至主要部分来自动升力。此时有几个重要变化：

1. 湿表面变短，船体只有后部和部分底面与水接触。
2. 静水浮力不再是唯一主要支撑项。
3. 纵倾角直接影响底部迎角，进而改变升力、压力中心和纵摇力矩。
4. 波浪中会出现周期性入水、出水、拍击、跳跃等强非线性现象。
5. 前进速度很高，遭遇频率会显著不同于波浪自身频率。

因此，滑行艇运动预报必须同时处理：

- steady running attitude（稳态航行姿态）：trim、sinkage、湿长。
- hydrodynamic lift（动升力）：高速水流产生的垂向支撑。
- dynamic coefficients（动力系数）：附加质量、阻尼、恢复力。
- wave excitation（波浪激励）：Froude-Krylov 力、绕射力和前进速度修正。
- impact and dry-out limits（冲击和出水限制）：线性模型之外的风险标记。

### 3.2 为什么采用 2.5D 方法

2.5D 方法又常称为 2D+t 方法，其基本思想是：

> 船以高速前进时，水流经过船体各横剖面的时间很短。可把三维船体问题近似为一系列二维横剖面入水/出水问题，再沿船长方向积分得到三维广义力。

这里的 “2.5D” 含义是：

- 截面水动力按二维问题求解。
- 船长方向通过高速前进速度和站位积分恢复三维效应。
- 它比纯二维模型多了纵向变化，又比完整三维非定常自由面势流模型低成本。

对于高速细长体、滑行艇、波浪遭遇频率较高的工况，2.5D 是一个合理的工程级路径。不过它仍有局限：

1. 低速、大幅横浪、强三维分离流下误差可能很大。
2. 拍击、飞离水面、重新入水需要额外非线性模型。
3. 完整站位式 2.5D 需要经过截面 radiation/diffraction 系数的文献级验证，不能只靠曲线看起来平滑。

---

## 4. 静水滑行平衡：Savitsky / Faltinsen 框架

### 4.1 静水平衡要解什么

高速滑行艇在平静水中稳定航行时，需要满足：

$$
F_3^{calm} - Mg = 0
$$

$$
F_5^{calm} = 0
$$

其中：

- $F_3^{calm}$：平静水中垂向水动力。
- $Mg$：船重。
- $F_5^{calm}$：关于重心的纵摇力矩。

未知量通常取为：

- $z_{wl}$：水线相对重心/参考点的位置，等价于 sinkage 描述。
- $\tau$：trim angle（纵倾角）。

程序中 `solve_equilibrium` 通过非线性最小二乘求解这两个未知量，使垂向力和纵摇力矩残差同时接近零。

### 4.2 Faltinsen 静水几何关系

Faltinsen 第 9 章中，静态水线位置与重心、纵倾、龙骨湿长之间的关系可写为：

$$
z_{wl} = vcg\cos\tau - (L_K-lcg)\sin\tau
$$

这相当于把船体以 trim angle $\tau$ 倾斜后，水面与船底/龙骨交点的位置几何化。它告诉我们：

- trim 增大时，龙骨湿长通常变化明显。
- 重心纵向位置 $lcg$ 会影响水线与船底的交点。
- $vcg$ 越高，纵摇几何耦合越强。

在有运动扰动时，Faltinsen 给出动态几何关系：

$$
L_K =
lcg + \frac{vcg}{\tan(\tau+\eta_5)}
- \frac{z_{wl}+\eta_3}{\sin(\tau+\eta_5)}
$$

这里 $\eta_3$ 是升沉扰动，$\eta_5$ 是纵摇扰动。它的物理含义很直接：

- 船整体上移或下移会改变湿长。
- 船头抬高或压低会改变底面入水长度。
- 当 $\tau+\eta_5$ 过小甚至接近零时，几何关系会变得奇异，这也是实际计算中需要限制最小有效纵倾角的原因。

在 Faltinsen wave-rise 形式中，chine 湿长可通过：

$$
L_C = L_K - x_s
$$

$$
x_s =
\frac{0.5 B \tan\beta}{(1+z_{max}/(Vt))(\tau+\eta_5)}
$$

于是平均湿长为：

$$
\lambda_W = \frac{L_K+L_C}{2B}
$$

当前代码中 `compute_geometry` 提供三种湿长模式：

| 模式 | 来源/含义 | 代码用途 |
|---|---|---|
| `wetted_lengths_type=1` | Faltinsen wave-rise 形式 | 默认方法 |
| `wetted_lengths_type=2` | Savitsky 1964 形式 | 备选经验几何 |
| `wetted_lengths_type=3` | Savitsky 1976 / Brown 风格修正 | 备选经验几何 |

### 4.3 Savitsky 零底升升力系数

Savitsky 1964 给出了滑行面升力的半经验表达。本项目采用的零底升升力系数为：

$$
C_{L0} =
\tau_{deg}^{1.1}
\left[
0.0120\lambda_W^{0.5}
+ 0.0055\frac{\lambda_W^{2.5}}{Fn_B^2}
\right]
$$

注意这里 $\tau_{deg}$ 用角度制，而不是弧度制。这一点非常重要，因为指数 $1.1$ 是按经验公式的角度输入建立的。如果把弧度误代进去，升力会严重偏小。

其中：

- 第一项 $0.0120\lambda_W^{0.5}$ 代表高速极限下湿长对升力的影响。
- 第二项 $0.0055\lambda_W^{2.5}/Fn_B^2$ 代表速度有限时的修正；速度越高，$Fn_B$ 越大，这项越小。
- $\tau_{deg}^{1.1}$ 表明 trim 是升力的主控变量之一。纵倾角稍微变化，升力会明显变化。

### 4.4 底升角修正

V 型底的 deadrise angle $\beta$ 会降低垂向升力。当前代码采用：

$$
C_{L\beta}
= C_{L0} - 0.0065\beta C_{L0}^{0.6}
$$

其中 $\beta$ 用角度制。物理上，底升角越大，船底越像深 V，入水冲击更柔和，但同等 trim 和速度下垂向动升力会下降。因此深 V 船型通常需要更高速度或更大湿长/纵倾来承担相同重量。

### 4.5 垂向力和阻力近似

动升力写为：

$$
F_z =
C_{L\beta}
\frac{1}{2}\rho U^2 B^2
$$

其中 $\frac{1}{2}\rho U^2$ 是动压，$B^2$ 是 Savitsky 公式使用的特征面积尺度。

若把垂向力沿倾斜底面分解，可得到近似轴向阻力或水平分量：

$$
F_x = F_z\tan\tau
$$

法向力：

$$
F_n = \frac{F_z}{\cos\tau}
$$

这些量主要用于平衡和输出诊断。当前 v1 的核心 seakeeping 关注垂向/纵摇响应，未把阻力增量作为主验证指标。

### 4.6 压力中心

压力中心到尾部/参考湿区的经验位置可写为：

$$
l_p =
\lambda_W B
\left[
0.75 -
\frac{1}{5.21(Fn_B/\lambda_W)^2+2.39}
\right]
$$

这个公式表达了高速滑行压力分布的经验规律：

- $Fn_B/\lambda_W$ 较小时，压力中心偏后。
- 速度相对湿长越高，压力中心趋向湿长的约 $75\%$ 位置。
- 压力中心与重心的相对位置决定纵摇力矩。

关于重心的纵摇力矩可写为：

$$
M_5 = -F_n(lcg-l_p)
$$

符号取决于项目坐标约定。当前代码采用这一表达并通过平衡残差检查判断静水姿态是否成立。

### 4.7 静水平衡残差和数值求解

程序把静水平衡写为广义力向量：

$$
\mathbf{F}^{calm}(\eta_3,\eta_5)
=
\begin{bmatrix}
F_3^{calm}-Mg \\
F_5^{calm}
\end{bmatrix}
$$

在平衡点：

$$
\mathbf{F}^{calm}(0,0) \approx \mathbf{0}
$$

为避免力和力矩量纲差异造成优化不稳定，代码用 $Mg$ 和 $MgB$ 对残差缩放。收敛判据采用小的相对残差阈值。若平衡失败，后续 RAO 或时域结果即使数值上能算出，也不应解释为可靠物理结果。

---

## 5. 升沉/纵摇线性运动方程与水动力矩阵

### 5.1 Faltinsen 第 9 章线性方程

迎浪对称工况下，滑行艇的一阶主要运动是升沉 $\eta_3$ 和纵摇 $\eta_5$。Faltinsen 给出的线性自由运动方程可写为：

$$
(M+A_{33})\ddot{\eta}_3
+ B_{33}\dot{\eta}_3
+ C_{33}\eta_3
+ A_{35}\ddot{\eta}_5
+ B_{35}\dot{\eta}_5
+ C_{35}\eta_5
=0
$$

$$
A_{53}\ddot{\eta}_3
+ B_{53}\dot{\eta}_3
+ C_{53}\eta_3
+ (I_{55}+A_{55})\ddot{\eta}_5
+ B_{55}\dot{\eta}_5
+ C_{55}\eta_5
=0
$$

矩阵形式为：

$$
(\mathbf{M}+\mathbf{A})\ddot{\boldsymbol{\eta}}
+ \mathbf{B}\dot{\boldsymbol{\eta}}
+ \mathbf{C}\boldsymbol{\eta}
= \mathbf{0}
$$

其中：

$$
\boldsymbol{\eta} =
\begin{bmatrix}
\eta_3\\
\eta_5
\end{bmatrix}
$$

$$
\mathbf{M}
=
\begin{bmatrix}
M & 0\\
0 & I_{55}
\end{bmatrix}
$$

$$
\mathbf{A}
=
\begin{bmatrix}
A_{33} & A_{35}\\
A_{53} & A_{55}
\end{bmatrix},
\quad
\mathbf{B}
=
\begin{bmatrix}
B_{33} & B_{35}\\
B_{53} & B_{55}
\end{bmatrix},
\quad
\mathbf{C}
=
\begin{bmatrix}
C_{33} & C_{35}\\
C_{53} & C_{55}
\end{bmatrix}
$$

这些符号的物理含义如下：

| 系数 | 物理意义 |
|---|---|
| $A_{33}$ | 升沉附加质量：船上下加速时需要一起加速的水体惯性 |
| $A_{55}$ | 纵摇附加转动惯量：船绕横轴角加速时带动水体形成的惯性 |
| $A_{35}, A_{53}$ | 升沉与纵摇的惯性耦合 |
| $B_{33}$ | 升沉阻尼：升沉速度引起的耗散/辐射阻尼 |
| $B_{55}$ | 纵摇阻尼 |
| $B_{35}, B_{53}$ | 升沉-纵摇速度耦合 |
| $C_{33}$ | 升沉恢复系数：升沉位移引起的垂向回复力 |
| $C_{55}$ | 纵摇恢复系数：纵摇角引起的回复力矩 |
| $C_{35}, C_{53}$ | 升沉-纵摇静力/准静力耦合 |

### 5.2 恢复力矩阵的导数定义

Faltinsen 将恢复系数定义为平静水广义力对位移的负导数：

$$
C_{jk}
=
-\left.\frac{\partial F_j^c}{\partial \eta_k}\right|_0,
\quad
j,k=3,5
$$

这里 $F_j^c$ 是 calm-water generalized force（平静水广义力）。负号来自标准振动方程约定：当位移为正时，回复力应倾向于把系统拉回平衡点。

当前代码没有手写全部解析导数，而是用中心差分数值微分：

$$
\frac{\partial F_j^c}{\partial \eta_k}
\approx
\frac{
F_j^c(\eta_k+\Delta)
-F_j^c(\eta_k-\Delta)
}{2\Delta}
$$

这样做的优点是：

1. 可与 Savitsky 平衡、不同湿长模型、干湿舷判断共用同一套非线性力函数。
2. 避免复制复杂解析导数时引入符号错误。
3. 后续替换更完整的静水/滑行力模型时，恢复矩阵仍可自动计算。

缺点是：

1. 需要选择合适差分步长。
2. 在湿长发生不连续切换、chine wet/dry 状态变化附近，数值导数可能不光滑。

### 5.3 楔形截面附加质量因子

滑行艇 V 型底横剖面可近似成入水楔形。当前代码使用的楔形附加质量因子为：

$$
K(\beta)
=
\frac{
\frac{\pi}{\sin\beta}
\frac{
\Gamma(1.5-\beta/\pi)
}{
\Gamma(1-\beta/\pi)^2
\Gamma(0.5+\beta/\pi)
}
-1
}{\tan\beta}
$$

其中 $\Gamma(\cdot)$ 是 Gamma function（伽马函数，是阶乘函数在连续实数/复数上的推广）。它出现在楔形入水势流解析解中，用来描述不同底升角下水体附加惯性的变化。

物理解释：

- $\beta$ 小，底面更平，入水时推开水体更剧烈，附加质量较大。
- $\beta$ 大，V 型更深，入水更柔，附加质量和冲击倾向较小。

### 5.4 附加质量矩阵近似

当前实现把湿区分成两部分：

1. bow/keel wedge part（靠近龙骨湿长变化的楔形部分）。
2. chine-wetted part（舷侧折角已湿的部分）。

设：

$$
\kappa = (1+z_{max}/(Vt))\tau
$$

$$
x_g = L_K - lcg
$$

则第一部分附加质量近似为：

$$
A_{33}^{(1)}
=
\frac{1}{3}\rho \kappa^2 K x_s^3
$$

$$
A_{35}^{(1)}
=
A_{33}^{(1)}(x_g-0.75x_s)
$$

$$
A_{53}^{(1)}
=
A_{35}^{(1)}
$$

$$
A_{55}^{(1)}
=
A_{33}^{(1)}
\left(
x_g^2 - 1.5x_gx_s + 0.6x_s^2
\right)
$$

如果 chine wet（舷侧折角浸湿），还加入第二部分。令：

$$
c_1 = \frac{2\tan^2\beta}{\pi}K
$$

则：

$$
A_{33}^{(2)}
=
\rho B^3 c_1\frac{\pi}{8}\frac{L_C}{B}
$$

$$
A_{35}^{(2)}
=
\rho B^4
\left[
-c_1\frac{\pi}{16}
\left(
\left(\frac{L_K}{B}\right)^2
-
\left(\frac{x_s}{B}\right)^2
\right)
+
\frac{x_g}{B}
\frac{A_{33}^{(2)}}{\rho B^3}
\right]
$$

$$
A_{53}^{(2)}
=
A_{35}^{(2)}
$$

$$
A_{55}^{(2)}
=
\rho B^5
\left[
c_1\frac{\pi}{24}
\left(
\left(\frac{L_K}{B}\right)^3
-
\left(\frac{x_s}{B}\right)^3
\right)
-
c_1\frac{\pi}{8}\frac{x_g}{B}
\left(
\left(\frac{L_K}{B}\right)^2
-
\left(\frac{x_s}{B}\right)^2
\right)
+
\left(\frac{x_g}{B}\right)^2
\frac{A_{33}^{(2)}}{\rho B^3}
\right]
$$

总附加质量为：

$$
A_{ij}=A_{ij}^{(1)}+A_{ij}^{(2)}
$$

这些表达属于工程近似，服务于 Faltinsen 第 9 章滑行艇纵向模型。它们不是完整站位 BEM 求得的频率相关附加质量。

### 5.5 阻尼矩阵近似

当前代码的阻尼矩阵沿 Faltinsen/OpenPlaning 风格实现。核心思想是：

- 升沉阻尼 $B_{33}$ 来自动升力对 trim/入水状态变化的敏感性。
- 耦合阻尼 $B_{35},B_{53}$ 和纵摇阻尼 $B_{55}$ 与前进速度 $U$、附加质量、重心位置和截面附加质量有关。

用代码中的主要表达表示：

$$
B_{33}
=
\frac{1}{2}\rho U B^2
\frac{dC_{L\beta}}{d\tau}
$$

其中：

$$
C_{L0,\infty}
=
\tau_{deg}^{1.1}0.012\sqrt{\lambda_W}
$$

$$
\frac{dC_{L0}}{d\tau}
=
\left(\frac{180}{\pi}\right)^{1.1}
0.0132
\tau_{rad}^{0.1}
\sqrt{\lambda_W}
$$

$$
\frac{dC_{L\beta}}{d\tau}
=
\frac{dC_{L0}}{d\tau}
\left[
1-0.0039\beta C_{L0,\infty}^{-0.4}
\right]
$$

设二维截面附加质量近似为：

$$
a_{33}^{2D}
=
\rho d^2 K
$$

其中 $d$ 是有效剖面吃水或入水尺度。则代码中使用：

$$
B_{35}
=
-U(A_{33}+lcg\,a_{33}^{2D})
$$

$$
B_{53}
=
B_{33}(0.75\lambda_WB-lcg)
$$

$$
B_{55}
=
U\,lcg^2a_{33}^{2D}
$$

这些阻尼项体现前进速度效应：船越快，剖面相对水面的运动被转换成更强的辐射/动压变化，因此阻尼与 $U$ 强相关。

### 5.6 稳定性和 porpoising 检查

把二阶系统写成一阶状态方程：

$$
\frac{d}{dt}
\begin{bmatrix}
\boldsymbol{\eta}\\
\dot{\boldsymbol{\eta}}
\end{bmatrix}
=
\begin{bmatrix}
\mathbf{0} & \mathbf{I}\\
-(\mathbf{M}+\mathbf{A})^{-1}\mathbf{C}
&
-(\mathbf{M}+\mathbf{A})^{-1}\mathbf{B}
\end{bmatrix}
\begin{bmatrix}
\boldsymbol{\eta}\\
\dot{\boldsymbol{\eta}}
\end{bmatrix}
$$

系统矩阵的特征值为 $\lambda_i$。若所有特征值实部都小于零：

$$
\operatorname{Re}(\lambda_i)<0
$$

则线性小扰动是衰减的。若有特征值实部大于零，说明小扰动会增长，可能出现 porpoising（海豚运动，滑行艇纵向自激振荡，表现为艇体周期性抬头、落下、再抬头）。

Faltinsen 表 9.2 给出了一个用于验证的规定状态：

| 参数 | 值 |
|---|---|
| $\beta$ | 20 deg |
| $\lambda_W$ | 4 |
| $\tau$ | 4 deg |
| $Fn_B$ | 3 |
| $lcg/B$ | 2.13 |
| $vcg/B$ | 0.25 |
| $M/(\rho B^3)$ | 1.28 |
| $r_{55}/B$ | 1.3 |

对应特征值目标近似为：

| 模态 | 参考实部 | 参考虚部 |
|---|---:|---:|
| mode 1 | -0.12 | ±1.91 |
| mode 2 | -0.86 | ±0.67 |

本项目验证中该基准已通过，说明纵向线性矩阵和符号约定在该规定状态下是可信的。

---

## 6. 波浪、遭遇频率与海况建模

### 6.1 规则迎浪

Faltinsen 对迎浪规则波可写为：

$$
\zeta(x,t)
=
\zeta_a\sin(\omega_e t-kx)
$$

其中：

- $\zeta_a$：波幅，规则波波高 $H$ 对应 $\zeta_a=H/2$。
- $\omega_0$：波浪自身圆频率。
- $k$：深水波数。
- $\omega_e$：遭遇圆频率。

深水色散关系为：

$$
k=\frac{\omega_0^2}{g}
$$

迎浪时，船向波浪来向前进，遭遇频率为：

$$
\omega_e=\omega_0+kU
$$

本项目的通用 heading 公式写成：

$$
\omega_e=\omega_0-kU\cos\mu
$$

其中 $\mu$ 是 wave heading angle（波浪相对船首角）。代码约定：

- `wave_heading_deg=180` 表示迎浪。
- 此时 $\cos 180^\circ=-1$，所以 $\omega_e=\omega_0+kU$。

这项非常关键。高速滑行艇中 $kU$ 可能与 $\omega_0$ 同量级甚至更大，导致实际响应频率远高于海面固定点观察到的波浪频率。

### 6.2 长波近似

当船长范围内波面变化不太剧烈时，可对规则波做长波展开：

$$
\zeta(x,t)
\approx
\zeta_a\sin\omega_e t
-xk\zeta_a\cos\omega_e t
$$

第一项代表整个艇体随波面整体抬升/下降；第二项代表沿船长方向的波面斜率，相当于给纵摇施加外部扰动。

这就是为什么 Faltinsen 公式中波浪激励自然分成：

- 与 $\zeta_a\sin\omega_e t$ 相关的升沉型激励。
- 与 $k\zeta_a\cos\omega_e t$ 相关的纵摇/波坡型激励。

### 6.3 Pierson-Moskowitz 谱

Pierson-Moskowitz spectrum（皮尔逊-莫斯科维茨谱，描述充分发展海况的经验波谱）在程序中写为：

$$
S_{PM}(\omega)
=
\frac{5}{16}
H_s^2
\omega_p^4
\omega^{-5}
\exp
\left[
-1.25
\left(\frac{\omega_p}{\omega}\right)^4
\right]
$$

其中：

- $H_s$：significant wave height（有义波高，近似等于最高三分之一波高的平均值）。
- $T_p$：peak period（谱峰周期）。
- $\omega_p=2\pi/T_p$：谱峰圆频率。

波谱 $S(\omega)$ 的物理意义是“单位圆频率内的波面方差”。对谱积分可得到零阶谱矩：

$$
m_0=\int_0^\infty S(\omega)d\omega
$$

有义波高近似满足：

$$
H_s\approx4\sqrt{m_0}
$$

### 6.4 JONSWAP 谱

JONSWAP spectrum（联合北海波浪项目谱，描述未充分发展且谱峰更尖锐的风浪）可视为 PM 谱乘以峰值增强因子：

$$
S_J(\omega)
=
S_{PM}(\omega)
\gamma^{
\exp
\left[
-\frac{(\omega/\omega_p-1)^2}{2\sigma^2}
\right]
}
$$

其中：

$$
\sigma =
\begin{cases}
0.07, & \omega\le \omega_p\\
0.09, & \omega>\omega_p
\end{cases}
$$

$\gamma$ 是 peak enhancement factor（谱峰增强因子）。$\gamma$ 越大，能量越集中在峰频附近。代码会对离散波分量重新缩放，使离散谱对应的 $H_s$ 与输入尽量一致。

### 6.5 不规则波分量离散

不规则波可写为多个规则波分量叠加：

$$
\zeta(t)
=
\sum_i a_i\sin(\omega_{e,i}t+\varepsilon_i)
$$

离散波幅取：

$$
a_i=\sqrt{2S(\omega_i)\Delta\omega}
$$

其中 $\varepsilon_i$ 是随机相位。程序允许设置随机种子，使不规则波时域结果可复现。

### 6.6 海流处理

Fossen 风格的船舶运动方程强调 relative velocity（相对速度，即船体相对水体的速度）：

$$
\boldsymbol{\nu}_r
=
\boldsymbol{\nu}
-\boldsymbol{\nu}_c
$$

其中：

- $\boldsymbol{\nu}$：船体速度。
- $\boldsymbol{\nu}_c$：海流速度。

当前 v1 对海流的处理是工程简化：先把输入航速修正为 speed through water（相对水速度），再进入 Savitsky 平衡和波浪遭遇频率计算。

在代码中，若 current heading 为迎流方向，则相对水速度增大；若为顺流，则相对水速度减小。这个处理保留了海流对动压、升力、遭遇频率的主要影响，但还不是完整的六自由度海流载荷模型。

---

## 7. 波浪激励与频域响应幅值算子

### 7.1 Froude-Krylov 激励

Froude-Krylov force（弗劳德-克雷洛夫力，指未受船体扰动的入射波压力直接作用在船体上的力）在长波近似下可写为：

$$
F_3^{FK}
=
C_{33}\zeta_a\sin\omega_e t
+
C_{35}k\zeta_a\cos\omega_e t
$$

$$
F_5^{FK}
=
C_{53}\zeta_a\sin\omega_e t
+
C_{55}k\zeta_a\cos\omega_e t
$$

直观理解：

- 波面整体抬高相当于给升沉方向一个位移输入。
- 波面沿船长方向有坡度，相当于给纵摇方向一个角度输入。
- 恢复矩阵 $\mathbf{C}$ 把这些“等效波面位移/波坡”转化成广义力。

### 7.2 绕射激励与速度相关项

Diffraction force（绕射力，船体存在改变入射波流场后产生的附加载荷）在高速滑行艇中不能完全忽略。Faltinsen 第 9 章把入射波垂向速度近似写成：

$$
w
\approx
\omega_0\zeta_a\cos\omega_e t
+
\omega_0\zeta_a kx\sin\omega_e t
$$

也可整理成：

$$
w=V_3-xV_5
$$

其中：

$$
V_3=\omega_0\zeta_a\cos\omega_e t
$$

$$
V_5=-\omega_0 k\zeta_a\sin\omega_e t
$$

绕射势函数与二维升沉辐射势函数相关，可概括为：

$$
\phi_7=-(V_3-xV_5)\phi_3
$$

这说明：在长波、小扰动近似下，绕射问题可借助升沉/纵摇辐射问题的水动力系数来构造。

### 7.3 激励力的正弦/余弦分解

Faltinsen 将总波浪激励写成：

$$
F_3
=
F_{3s}\zeta_a\sin\omega_e t
+
F_{3c}\zeta_a\cos\omega_e t
$$

$$
F_5
=
F_{5s}\zeta_a\sin\omega_e t
+
F_{5c}\zeta_a\cos\omega_e t
$$

当前代码使用的激励系数形式为：

$$
F_{3s}
=
C_{33}
-A_{33}\omega_0\omega_e
-B_{35}^{d}\omega_0 k
$$

$$
F_{3c}
=
C_{35}k
-A_{35}\omega_0\omega_e k
+B_{33}^{d}\omega_0
$$

$$
F_{5s}
=
C_{53}
-A_{53}\omega_0\omega_e
-B_{55}^{d}\omega_0 k
$$

$$
F_{5c}
=
C_{55}k
-A_{55}\omega_0\omega_e k
+B_{53}^{d}\omega_0
$$

其中：

$$
B_{33}^{d}=B_{33}
$$

$$
B_{53}^{d}=B_{53}
$$

$$
B_{35}^{d}=B_{35}+UA_{33}
$$

$$
B_{55}^{d}=B_{55}+UA_{35}
$$

这些式子把 Froude-Krylov、绕射、附加质量、阻尼和前进速度项组合到同一个波浪激励向量中。它们是当前频域 RAO 的核心。

### 7.4 复数频域方程

对规则波，令运动响应写成复数形式：

$$
\eta_j
=
(\eta_{Rj}+i\eta_{Ij})e^{i\omega_e t}
$$

波浪力写成：

$$
F_j
=
\zeta_a(F_{jc}-iF_{js})e^{i\omega_e t}
$$

代入线性运动方程，得到：

$$
\left[
-\omega_e^2(\mathbf{M}+\mathbf{A})
+i\omega_e\mathbf{B}
+\mathbf{C}
\right]
\boldsymbol{\eta}
=
\zeta_a
\begin{bmatrix}
F_{3c}-iF_{3s}\\
F_{5c}-iF_{5s}
\end{bmatrix}
$$

定义动态刚度矩阵：

$$
\mathbf{D}(\omega_e)
=
-\omega_e^2(\mathbf{M}+\mathbf{A})
+i\omega_e\mathbf{B}
+\mathbf{C}
$$

则单位波幅响应为：

$$
\frac{\boldsymbol{\eta}}{\zeta_a}
=
\mathbf{D}^{-1}(\omega_e)
\begin{bmatrix}
F_{3c}-iF_{3s}\\
F_{5c}-iF_{5s}
\end{bmatrix}
$$

### 7.5 响应幅值算子

RAO 是 response amplitude operator（响应幅值算子，表示单位波幅输入下船体响应的幅值）。升沉 RAO：

$$
RAO_3
=
\frac{|\eta_3|}{\zeta_a}
=
\frac{\sqrt{\eta_{R3}^2+\eta_{I3}^2}}{\zeta_a}
$$

纵摇 RAO：

$$
RAO_5
=
\frac{|\eta_5|}{\zeta_a}
=
\frac{\sqrt{\eta_{R5}^2+\eta_{I5}^2}}{\zeta_a}
$$

工程上也常把纵摇按波坡归一：

$$
RAO_{5,slope}
=
\frac{|\eta_5|}{k\zeta_a}
$$

这样可以比较不同波长下“艇体纵摇角相对于波面坡度”的响应。

### 7.6 艏部响应与垂向加速度

如果某点相对重心的纵向坐标为 $x_p$，小角度下该点垂向位移为：

$$
z_p
=
\eta_3 - x_p\eta_5
$$

当前代码中 bow point（艏部点）默认：

$$
x_{bow}=-(L-lcg)
$$

所以艏部垂向位移：

$$
z_{bow}
=
\eta_3 - x_{bow}\eta_5
$$

垂向加速度幅值：

$$
a_3
=
\omega_e^2|\eta_3|
$$

艏部垂向加速度幅值：

$$
a_{bow}
=
\omega_e^2|z_{bow}|
$$

如果需要用 $g$ 归一：

$$
\frac{a}{g}
=
\frac{\omega_e^2|\eta|}{g}
$$

这个指标对高速艇特别重要，因为乘员舒适性、结构拍击风险和跳跃风险通常与垂向加速度高度相关。

---

## 8. 非线性时域运动方程

### 8.1 为什么需要时域

频域 RAO 适合小波幅、线性响应和稳态谐波分析。但滑行艇在波浪中可能出现：

- 瞬时湿长剧烈变化。
- 波峰上出水或接近出水。
- 艏部拍击。
- 响应峰值随波高变化而移动。
- 跳跃/非跳跃状态切换。

这些现象不能完全靠线性频域公式表达。因此 Faltinsen 给出了非线性时域写法。本项目 v1 实现了一个纵向非线性时域求解路径，用作工程预测和开发诊断。

### 8.2 Faltinsen 时域方程结构

非线性时域方程左侧保留惯性矩阵：

$$
(M+A_{33})\ddot{\eta}_3
+A_{35}\ddot{\eta}_5
=F_3
$$

$$
A_{53}\ddot{\eta}_3
+(I_{55}+A_{55})\ddot{\eta}_5
=F_5
$$

与线性频域不同，右侧的 $F_3,F_5$ 包含非线性平静水广义力、波浪残余激励和阻尼项。

### 8.3 波面替代思想

在规则波中，Faltinsen 的非线性时域方法把船体相对波面的升沉和纵摇写为：

$$
\eta_3^{rel}
=
\eta_3-\zeta_a\sin\omega_e t
$$

$$
\eta_5^{rel}
=
\eta_5-k\zeta_a\cos\omega_e t
$$

它的含义是：

- 船不是相对静止水平面运动，而是相对瞬时波面运动。
- 波面高度影响等效升沉。
- 波面坡度影响等效纵摇。

然后用相对状态进入静水非线性滑行力函数：

$$
F_j^c(\eta_3^{rel},\eta_5^{rel})
$$

这保留了湿长、纵倾和压力中心随瞬时相对姿态变化的非线性。

### 8.4 右侧广义力

当前实现可概括为：

$$
\mathbf{F}(t)
=
\left[
\mathbf{F}^{calm}
(\eta_3-\zeta,\eta_5-\zeta_x)
-
\mathbf{F}^{calm}_0
\right]
+
\mathbf{F}^{wave}_{residual}(t)
-
\mathbf{B}\dot{\boldsymbol{\eta}}
$$

其中：

- $\mathbf{F}^{calm}_0$：平衡点的平静水广义力，用于去掉静态平衡值。
- $\zeta$：波面升沉输入。
- $\zeta_x$：波面斜率输入。
- $\mathbf{F}^{wave}_{residual}$：扣除准静力 Froude-Krylov 后的绕射/惯性/阻尼型波浪残余项。
- $\mathbf{B}\dot{\boldsymbol{\eta}}$：线性阻尼。

规则波下，Faltinsen 形式可写为：

$$
F_3 =
F_3^c-F_{03}^c
+
(F_{3s}-C_{33})\zeta_a\sin\omega_e t
+
(F_{3c}-C_{35}k)\zeta_a\cos\omega_e t
-
B_{33}\dot{\eta}_3
-
B_{35}\dot{\eta}_5
$$

$$
F_5 =
F_5^c-F_{05}^c
+
(F_{5s}-C_{53})\zeta_a\sin\omega_e t
+
(F_{5c}-C_{55}k)\zeta_a\cos\omega_e t
-
B_{53}\dot{\eta}_3
-
B_{55}\dot{\eta}_5
$$

### 8.5 一阶常微分方程

设：

$$
u_3=\dot{\eta}_3,\quad u_5=\dot{\eta}_5
$$

惯性矩阵行列式：

$$
D =
(M+A_{33})(I_{55}+A_{55})-A_{35}A_{53}
$$

则二阶系统可转成一阶系统：

$$
\frac{d\eta_3}{dt}=u_3
$$

$$
\frac{d\eta_5}{dt}=u_5
$$

$$
\frac{du_3}{dt}
=
\frac{
F_3(I_{55}+A_{55})-F_5A_{35}
}{D}
$$

$$
\frac{du_5}{dt}
=
\frac{
(M+A_{33})F_5-A_{53}F_3
}{D}
$$

程序使用 `scipy.solve_ivp` 进行常微分方程积分，也提供固定步长 RK4 诊断路径，用于检查短时时域趋势。

### 8.6 时域风险标记

非线性时域结果不仅输出响应，还输出物理风险诊断。重要指标包括：

| 指标 | 含义 |
|---|---|
| 最大重心垂向加速度 / $g$ | 乘员舒适性和结构载荷粗指标 |
| 最大艏部垂向加速度 / $g$ | 艏部拍击和跳跃风险更敏感 |
| 相对升沉超过尾部吃水比例 | 判断是否接近出水/干湿状态突变 |
| impact risk | 是否存在潜在拍击风险 |
| dry-out risk | 是否出现湿长过小或接近离水 |
| jump risk | 是否进入可能跳跃的速度-波浪组合 |

这些标记不是最终物理判决，而是提醒使用者：当标记出现时，线性 RAO 或当前非线性模型的外推可信度下降，需要更完整的入水、出水、拍击和自由飞行模型。

---

## 9. 六自由度统一输出

### 9.1 为什么输出六自由度

用户需求要求预报 6DOF 运动响应。当前 v1 为了保持接口完整，统一输出六自由度时间序列和统计量：

$$
[x,\ y,\ z,\ \phi,\ \theta,\ \psi]
$$

其中迎浪对称工况下：

$$
x=0,\quad y=0,\quad \phi=0,\quad \psi=0
$$

$$
z=\eta_3,\quad \theta=\eta_5
$$

这不是说真实船在所有情况下这些自由度都为零，而是说：

- 对称船型。
- 迎浪。
- 一阶线性势流/滑行艇纵向模型。
- 未输入横向半经验系数。

在这些假设下，横向自由度没有一阶激励。

### 9.2 斜浪、海流和风的扩展位置

oblique wave（斜浪）、current（海流）和 wind（风）会激发 sway、roll、yaw，并可能改变 surge。当前程序预留了线性/半经验通道：

$$
\mathbf{M}_{6}\dot{\boldsymbol{\nu}}
+\mathbf{C}_{6}(\boldsymbol{\nu})\boldsymbol{\nu}
+\mathbf{D}_{6}\boldsymbol{\nu}
+\mathbf{g}_{6}(\boldsymbol{\eta})
=
\boldsymbol{\tau}_{wave}
+\boldsymbol{\tau}_{current}
+\boldsymbol{\tau}_{wind}
$$

这里是 Fossen 风格的 6DOF 总方程：

- $\boldsymbol{\nu}$：body-fixed velocity（船体坐标系速度）。
- $\mathbf{M}_6$：六自由度质量和附加质量矩阵。
- $\mathbf{C}_6$：Coriolis and centripetal matrix（科氏和向心矩阵，描述旋转坐标系下的惯性耦合）。
- $\mathbf{D}_6$：阻尼矩阵。
- $\mathbf{g}_6$：恢复力/力矩。
- $\boldsymbol{\tau}$：环境载荷。

但 v1 没有声称完成斜浪六自由度高精度模型。只有当用户输入横向线性系数或未来接入完整 2.5D/3D 水动力后，sway、roll、yaw 才应被解释为物理预测。

---

## 10. 完整站位式 2.5D 目标

### 10.1 当前纵向模型与完整 2.5D 的区别

当前 Faltinsen/Savitsky 纵向模型直接使用经验/解析近似给出 heave-pitch 的矩阵和波浪激励。完整站位式 2.5D 则应当：

1. 读取真实或参数化船体 station offsets（站位横剖面型值）。
2. 对每个横剖面求二维 radiation（辐射）和 diffraction（绕射）问题。
3. 把截面压力或截面力沿船长积分。
4. 加入前进速度修正和遭遇频率。
5. 形成频率相关的六自由度或至少纵向多自由度矩阵：

$$
\mathbf{A}(\omega_e),\quad
\mathbf{B}(\omega_e),\quad
\mathbf{C},\quad
\mathbf{F}_{wave}(\omega_e)
$$

6. 用公开文献 benchmark 验证这些矩阵，而不是只验证最终曲线形状。

### 10.2 站位船型输入

完整 2.5D 需要船型以 station hull 形式输入。每个站位至少包含：

- 站位纵向坐标 $x_s$。
- 横向半宽 $y(z)$ 或 offset 点。
- 垂向坐标 $z$。
- 左右对称性信息。
- 水线、吃水、trim 后的局部入水几何。

读取站位后，需要对每个截面建立二维面元或解析截面模型，求解局部辐射/绕射水动力。

### 10.3 截面 radiation 与 diffraction

radiation problem（辐射问题）指船体剖面做单位振荡运动，在静水中向外辐射波，从而产生附加质量和阻尼。

diffraction problem（绕射问题）指入射波遇到固定船体剖面，被船体散射，产生绕射压力和绕射力。

对每个频率 $\omega$，二维截面可得到局部系数：

$$
a_{ij}^{2D}(\omega),\quad b_{ij}^{2D}(\omega)
$$

沿船长积分后得到船体级系数：

$$
A_{ij}(\omega)
=
\int a_{ij}^{2D}(x,\omega)\,dx
$$

$$
B_{ij}(\omega)
=
\int b_{ij}^{2D}(x,\omega)\,dx
$$

如果考虑前进速度，积分项还会出现与 $\partial/\partial x$ 有关的纵向梯度项。这也是 Ma 2005 benchmark 很关键的原因：它能检验程序是否真的正确处理了 2.5D 前进速度耦合，而不是只做零航速 strip theory。

### 10.4 Ma 2005 验证的意义

Ma 2005 中 Wigley III 与 SL-7 算例不是滑行艇，但它们非常适合验证完整 2.5D 水动力系数，因为：

1. 船型和前进速度效应明确。
2. 文献中有 added mass 和 damping 系数曲线。
3. 可检查 $A_{33},B_{33},A_{55},B_{55}$ 等对角项。
4. 更重要的是可检查 $A_{35},A_{53},B_{35},B_{53}$ 等耦合项。

如果一个站位式 2.5D 程序不能通过 Ma 2005 的系数对照，那么即使它能输出漂亮的 RAO 曲线，也不能说明完整 2.5D 水动力实现正确。

### 10.5 当前 station_2p5d 状态

当前代码中的 `station_2p5d` 是开发原型，状态应明确写为：

```text
frequency_forward_speed_prototype_not_validated
```

也就是说：

- 它能读入 hard-chine station hull、显式 offsets、offset CSV、Wigley/SL-7 surrogate。
- 它能计算水静力、装配 strip 矩阵、输出 station-frequency 长表。
- 它有 section BEM、pressure-transfer、PDSTRIP-style 和 external PDSTRIP 诊断路径。
- 但它还没有通过 Ma 2005 系数 gate。

因此，在报告或对外说明中，不能写“完整 2.5D 已实现并验证”。更准确的说法是：

> 当前已建立完整 2.5D 求解器的数据结构、诊断路径和验证 gate；纵向简化模型可运行且部分验证通过；完整站位式 2.5D 的水动力系数仍在验证和修正阶段。

---

## 11. 验证体系和合理性判断

### 11.1 为什么不能只看曲线顺滑

数值曲线顺滑只能说明程序没有明显崩溃，并不能说明模型物理正确。滑行艇运动预报至少要经过三层判断：

1. 数值合理：矩阵正定、无 NaN/Inf、时间积分稳定、谱离散收敛。
2. 物理合理：trim、湿长、RAO 峰值、加速度随速度/波高变化的趋势符合常识和文献。
3. 文献对照合理：与 Faltinsen、Fridsma、Katayama、Ma 2005 等公开 benchmark 的误差在门槛内。

只有第三层通过，才能说模型在对应适用范围内“可验证”。

### 11.2 Gate A：Faltinsen 第 9 章规定状态

用途：验证当前纵向 Faltinsen/Savitsky heave-pitch 线性模型的矩阵、符号和特征值。

验收内容：

- 使用 $\beta=20^\circ$。
- 使用 $\lambda_W=4$。
- 使用 $\tau=4^\circ$。
- 使用 $Fn_B=3$。
- 使用 $lcg/B=2.13$。
- 使用 $vcg/B=0.25$。
- 使用 $M/(\rho B^3)=1.28$。
- 使用 $r_{55}/B=1.3$。

验收门槛：

| 指标 | 门槛 |
|---|---|
| 特征频率误差 | 不超过约 10% |
| 衰减实部误差 | 不超过约 10% |
| RAO 峰值位置 | 不超过约 10% |
| RAO 峰值幅值 | 不超过约 20% |

当前状态：已通过。最近验证中得到的主要特征值与参考值非常接近，例如高频模态虚部约 $1.909$，参考约 $1.91$。

### 11.3 Gate B：Fridsma / Katayama 滑行艇规则波试验

用途：验证模型是否能复现真实高速滑行艇在规则波中的运动幅值、加速度和跳跃趋势。

对照量：

- heave amplitude（升沉幅值）。
- pitch amplitude（纵摇幅值）。
- CG vertical acceleration（重心垂向加速度）。
- bow vertical acceleration（艏部垂向加速度）。
- jumping / non-jumping classification（跳跃/非跳跃分类）。

验收门槛：

| 指标 | 门槛 |
|---|---|
| heave 幅值误差 | 不超过约 25% |
| pitch 幅值误差 | 不超过约 25% |
| CG/bow 加速度误差 | 不超过约 35% |
| 跳跃分类 | 应与试验分类一致 |

当前状态：

- Fridsma configuration A 幅值 gate 已接入，但当前仍有明显失败项。
- Katayama 定性趋势和跳跃分类已有检查，部分通过。
- Katayama 定量幅值曲线仍需要补齐数字化数据。

这意味着：当前模型可以作为开发基线，但不能说已经通过滑行艇粗水试验幅值验证。

### 11.4 Gate C：Ma 2005 Wigley III / SL-7 2.5D 系数

用途：验证完整站位式 2.5D radiation/diffraction 水动力求解器。

对照量：

$$
A_{33},\ B_{33},\ A_{55},\ B_{55},\ A_{35},\ A_{53},\ B_{35},\ B_{53}
$$

验收门槛：

| 系数类型 | 建议门槛 |
|---|---|
| 对角项 | 相对误差不超过约 15% |
| 耦合项 | 相对误差不超过约 30% |
| 接近零的参考值 | 使用保守绝对误差阈值，避免相对误差爆炸 |

当前状态：

- Wigley III development digitization 已接入，但仍有多个 coupling/damping 项失败。
- SL-7 development digitization 已接入，但真实 station offsets 仍需补齐，surrogate 结果不能作为最终几何验收。
- `complete_2p5d_solver` 仍处于 pending 或未通过状态。

### 11.5 内部数值 sanity

内部 sanity 用来发现明显程序错误：

| 检查 | 目的 |
|---|---|
| mass matrix determinant > 0 | 确保惯性矩阵可逆且物理上合理 |
| RAO 无 NaN/Inf | 确保频域求解没有崩溃 |
| time integration finite | 确保时域积分稳定 |
| RMS 随 $H_s$ 近似线性 | 小波幅线性范围内的谱响应检查 |
| 固定随机种子复现 | 确保不规则波结果可重复 |
| 增大速度时加速度趋势合理 | 检查高速遭遇频率和动压效应 |

这些检查能证明“程序没有明显数值坏掉”，但不能代替文献对照。

### 11.6 Fridsma 形状审计

由于当前 Fridsma 幅值 gate 失败，验证器增加了 shape audit（形状审计）。它的目标不是宽松放行，而是区分两种失败：

1. 曲线整体形状对，但幅值比例有偏差。
2. 曲线形状本身不对，峰值位置或频率趋势不对。

典型方法包括：

- 对预测曲线 $\mathbf{p}$ 和参考曲线 $\mathbf{r}$ 求最佳比例因子：

$$
s =
\frac{\mathbf{p}\cdot\mathbf{r}}{\mathbf{p}\cdot\mathbf{p}}
$$

- 计算缩放后的均方根误差。
- 计算相关系数。
- 比较对数幅值随频率或波长的斜率。

当前结论可概括为：

- heave/pitch 有部分形状相似性，但存在尺度和局部频段误差。
- CG/bow 加速度存在更明显的 frequency-shape gap。
- 短波下加速度偏低、中波下某些运动幅值偏高，说明当前线性/简化非线性模型缺少关键粗水物理。

---

## 12. 如何判断当前结果是否合理

### 12.1 最低限度合理

如果一个运行结果满足以下条件，可以认为它是“最低限度数值合理”的：

1. 平衡求解收敛。
2. trim 在滑行艇合理范围，例如约 $2^\circ$ 到 $8^\circ$，具体取决于船型和速度。
3. $\lambda_W$ 为正，且没有不合理巨大湿长。
4. 惯性矩阵行列式为正。
5. RAO 没有 NaN/Inf。
6. 时域响应没有发散。
7. 小波幅下时域幅值与频域 RAO 趋势一致。

这一级别只能说明程序输出“可看”，不能说明已经和试验吻合。

### 12.2 工程趋势合理

如果结果进一步满足以下趋势，可认为具有一定工程解释价值：

1. 迎浪中 heave/pitch 响应随波浪频率出现峰值，而不是单调乱变。
2. 峰值附近通常接近系统纵向模态频率。
3. 航速升高时，遭遇频率升高，垂向加速度通常变大。
4. 波高增大时，小幅线性范围内 RMS 近似按比例增大。
5. 艏部加速度通常大于或不小于重心加速度，尤其在纵摇显著时。
6. 当风险标记出现时，响应结果不应再按线性小扰动无条件解释。

### 12.3 文献可验证合理

只有满足以下条件，才能称为“可验证合理”：

1. Faltinsen prescribed-state 特征值和 RAO 对照通过。
2. Fridsma/Katayama 滑行艇波浪试验幅值和加速度通过。
3. Ma 2005 2.5D 水动力系数通过。
4. 验证报告中没有关键 `PENDING_REFERENCE_OR_IMPLEMENTATION`。
5. 所有失败项都有明确解释和修正计划。

当前项目状态仍处于第二层和第三层之间：纵向 Faltinsen 基准已可信，但完整 2.5D 和粗水幅值验证仍未完成。

---

## 13. 当前不足与不能越界的结论

### 13.1 当前模型不能声称的内容

不能声称：

1. 已完整实现并验证全部六自由度高速滑行艇 2.5D 模型。
2. 斜浪下 sway、roll、yaw 已有高精度预测能力。
3. Fridsma/Katayama 粗水试验幅值已经全部通过。
4. Ma 2005 Wigley III / SL-7 水动力系数已经通过。
5. 拍击、跳跃、出水、再入水已由高保真非线性模型解决。

### 13.2 当前可以声称的内容

可以谨慎声称：

1. 已实现可读取配置的高速滑行艇纵向运动预报程序。
2. 已实现 Savitsky/Faltinsen 静水滑行平衡。
3. 已实现 Faltinsen 第 9 章 heave-pitch 线性频域 RAO。
4. 已实现规则波和 PM/JONSWAP 不规则波时域响应。
5. 已统一输出六自由度格式，但迎浪对称工况下主自由度为 heave/pitch。
6. 已建立完整 2.5D 的站位输入、诊断和验证 gate 框架。
7. 已接入 Faltinsen、Fridsma、Katayama、Ma 2005 等对照路线，并明确当前通过/失败状态。

### 13.3 下一步理论与代码重点

为了达到“完整 2.5D 模型”目标，下一步应优先：

1. 人工复核 Fridsma configuration A 数字化数据，确认失败不是数据录入误差。
2. 补齐 Katayama heave、pitch、CG/bow acceleration 幅值曲线数字化。
3. 补齐 SL-7 真实 station offsets，避免 surrogate 几何误导。
4. 修正 Ma 2005 中失败的 $A_{35},A_{53},B_{35},B_{53},B_{55},A_{55}$ 等项。
5. 审计 PDSTRIP sectionresults 的单位、符号、转置、频率归一和 station 积分约定。
6. 将通过验证的 section pressure/radiation/diffraction 函数接入 forward-speed 2.5D 主求解。
7. 对强非线性滑行艇波浪响应增加拍击、离水、再入水和跳跃动力学模型。

---

## 14. 公式速查表

### 14.1 基本无量纲数

$$
Fn_B=\frac{U}{\sqrt{gB}}
$$

$$
Fn_L=\frac{U}{\sqrt{gL}}
$$

$$
\lambda_W=\frac{L_K+L_C}{2B}
$$

### 14.2 静水几何

$$
z_{wl}=vcg\cos\tau-(L_K-lcg)\sin\tau
$$

$$
L_K =
lcg+\frac{vcg}{\tan(\tau+\eta_5)}
-\frac{z_{wl}+\eta_3}{\sin(\tau+\eta_5)}
$$

$$
L_C=L_K-x_s
$$

### 14.3 Savitsky 升力

$$
C_{L0}
=
\tau_{deg}^{1.1}
\left[
0.0120\lambda_W^{0.5}
+0.0055\frac{\lambda_W^{2.5}}{Fn_B^2}
\right]
$$

$$
C_{L\beta}
=
C_{L0}-0.0065\beta C_{L0}^{0.6}
$$

$$
F_z=C_{L\beta}\frac{1}{2}\rho U^2B^2
$$

$$
l_p=
\lambda_WB
\left[
0.75-\frac{1}{5.21(Fn_B/\lambda_W)^2+2.39}
\right]
$$

### 14.4 线性 heave-pitch 方程

$$
(\mathbf{M}+\mathbf{A})\ddot{\boldsymbol{\eta}}
+\mathbf{B}\dot{\boldsymbol{\eta}}
+\mathbf{C}\boldsymbol{\eta}
=\mathbf{F}_{wave}
$$

$$
C_{jk}
=
-\left.\frac{\partial F_j^c}{\partial\eta_k}\right|_0
$$

### 14.5 遭遇频率

$$
k=\frac{\omega_0^2}{g}
$$

$$
\omega_e=\omega_0-kU\cos\mu
$$

迎浪：

$$
\omega_e=\omega_0+kU
$$

### 14.6 波浪激励

$$
F_3=
F_{3s}\zeta_a\sin\omega_e t
+F_{3c}\zeta_a\cos\omega_e t
$$

$$
F_5=
F_{5s}\zeta_a\sin\omega_e t
+F_{5c}\zeta_a\cos\omega_e t
$$

$$
\mathbf{D}(\omega_e)
=
-\omega_e^2(\mathbf{M}+\mathbf{A})
+i\omega_e\mathbf{B}
+\mathbf{C}
$$

$$
\frac{\boldsymbol{\eta}}{\zeta_a}
=
\mathbf{D}^{-1}
\begin{bmatrix}
F_{3c}-iF_{3s}\\
F_{5c}-iF_{5s}
\end{bmatrix}
$$

### 14.7 RAO 和加速度

$$
RAO_3=\frac{|\eta_3|}{\zeta_a}
$$

$$
RAO_5=\frac{|\eta_5|}{\zeta_a}
$$

$$
RAO_{5,slope}=\frac{|\eta_5|}{k\zeta_a}
$$

$$
z_{bow}=\eta_3-x_{bow}\eta_5
$$

$$
a=\omega_e^2|\eta|
$$

### 14.8 时域一阶系统

$$
D=(M+A_{33})(I_{55}+A_{55})-A_{35}A_{53}
$$

$$
\dot{\eta}_3=u_3,\quad
\dot{\eta}_5=u_5
$$

$$
\dot{u}_3=
\frac{F_3(I_{55}+A_{55})-F_5A_{35}}{D}
$$

$$
\dot{u}_5=
\frac{(M+A_{33})F_5-A_{53}F_3}{D}
$$

### 14.9 波谱

$$
S_{PM}(\omega)
=
\frac{5}{16}
H_s^2\omega_p^4\omega^{-5}
\exp
\left[
-1.25
\left(\frac{\omega_p}{\omega}\right)^4
\right]
$$

$$
a_i=\sqrt{2S(\omega_i)\Delta\omega}
$$

$$
H_s\approx4\sqrt{m_0}
$$

---

## 15. 代码实现位置索引

| 功能 | 文件 | 说明 |
|---|---|---|
| 配置读取 | `planing_seakeeping/config.py` | 读取 YAML/JSON 船型、质量、速度、波浪、海流、风、仿真参数 |
| 静水平衡 | `planing_seakeeping/equilibrium.py` | Savitsky/Faltinsen 平衡、湿长、升力、压力中心 |
| 水动力矩阵 | `planing_seakeeping/coefficients.py` | 附加质量、阻尼、恢复力、稳定性特征值 |
| 波浪和波谱 | `planing_seakeeping/waves.py` | 规则波、PM/JONSWAP、遭遇频率、随机相位 |
| 频域/时域求解 | `planing_seakeeping/solver.py` | RAO、非线性时域、线性叠加、诊断 |
| 六自由度输出 | `planing_seakeeping/sixdof.py` | 把 heave/pitch 转为 6DOF 表格和加速度 |
| 可视化 | `planing_seakeeping/viz.py` | RAO、时历、RMS、加速度图 |
| 完整站位 2.5D 原型 | `planing_seakeeping/station_2p5d.py` | station hull、section BEM、strip assembly 诊断 |
| 验证体系 | `planing_seakeeping/validation.py` | Faltinsen、Fridsma、Katayama、Ma 2005、sanity gates |
| CLI | `planing_seakeeping/cli.py` | `python -m planing_seakeeping ...` 命令入口 |

常用命令示例：

```powershell
python -m planing_seakeeping run configs/example_planing.yml --out outputs/example
```

```powershell
python -m planing_seakeeping validate --out outputs/validation_current
```

```powershell
python scripts/generate_research_report.py --source outputs/report_example --out report.html
```

---

## 16. 示例船型和海况的理论解释

此前示例使用深 V 单体滑行艇：

| 参数 | 示例值 | 理由 |
|---|---:|---|
| $B$ | 2.2 m | 小型高速艇典型宽度量级 |
| $L$ | 11 m | 长宽比约 5，适合高速细长滑行艇示例 |
| $\beta$ | 20 deg | 深 V 底，兼顾高速和耐波 |
| $M$ | 约 $1.28\rho B^3$ | 与 Faltinsen 表 9.2 无量纲质量一致，便于验证 |
| $lcg$ | $2.13B$ | 与 Faltinsen prescribed-state 对照一致 |
| $vcg$ | $0.25B$ | 与 Faltinsen prescribed-state 对照一致 |
| $r_{55}$ | $1.3B$ | 与 Faltinsen prescribed-state 对照一致 |
| $Fn_B$ | 2, 3, 4 | 覆盖典型滑行速度范围 |
| 规则波 | $H=0.5m, T=2-8s$ | 用于扫频 RAO 和响应峰值观察 |
| 不规则波 | $H_s=0.6m, T_p=4s$ | 用于 RMS 和时域统计 |
| 迎流 | 0.5 m/s | 展示海流对相对水速度的影响 |

为什么这些参数合理：

1. $Fn_B=2-4$ 已明显进入滑行艇高速范围。
2. $\beta=20^\circ$ 对应 deep-V 高速艇常见量级。
3. 质量、重心和回转半径与 Faltinsen 表 9.2 保持一致，方便做特征值验证。
4. 波高 $0.5-0.6m$ 对 11 m 小艇已足以产生可观响应，但仍可作为第一版小到中等波幅分析。

示例结果应重点读：

- heave RAO 是否在合理频段出现峰值。
- pitch RAO 是否随波长/频率变化平滑。
- bow acceleration 是否明显大于 CG acceleration。
- RMS 是否随航速、遭遇频率和波高变化合理。
- 是否出现 impact/dry-out/jump 风险标记。

---

## 17. 研究报告中应如何表述结果

为了避免过度声称，报告建议采用以下措辞。

### 17.1 可用表述

可以写：

> 本研究完成了基于 Faltinsen 第 9 章与 Savitsky 静水滑行平衡的高速滑行艇纵向运动预报程序。程序能够读取船型、质量、航速、规则波和不规则波海况，输出六自由度格式的时域响应，其中迎浪对称工况下主要有效自由度为升沉和纵摇。Faltinsen prescribed-state 特征值验证已通过，说明当前纵向线性模型具备可作为开发基线的可信度。

可以写：

> Ma 2005 Wigley III 线性高速 2.5D 水动力 Gate 1 已通过，基准与加密网格均为 `10/10 PASS`；规则迎浪整船运动 Gate 2 当前为 `17/20 PASS`，尚未通过 Begovic 三航速升沉、纵摇幅值和已解析主峰频率，因此整船响应仍处于独立验证闭合阶段。

### 17.2 不应写的表述

不应写：

> 本程序已经完整验证六自由度高速滑行艇 2.5D 运动预报。

不应写：

> 当前结果已经与 Fridsma 和 Katayama 试验完全一致。

不应写：

> station_2p5d 已经是生产级完整 2.5D 求解器。

这些表述会超过当前验证证据。

---

## 18. 参考资料清单

本项目主要参考和抽取内容来自以下资料。这里列出的是研究脉络和代码实现中实际用到的资料类型，具体文件可在 `docs/materials_inventory.csv` 中检索。

1. Odd M. Faltinsen, *Hydrodynamics of High-Speed Marine Vehicles*, Cambridge University Press, 2006. 重点使用第 9 章 Planing Vessels，尤其是静水几何、heave/pitch 线性方程、波浪激励、频域 RAO 和非线性时域方程。
2. Daniel Savitsky, 1964, Hydrodynamic Design of Planing Hulls. 重点使用滑行升力、底升角修正、压力中心和 trim 平衡相关公式。
3. Savitsky and Brown, 1976. 用于粗水阻力、冲击加速度和实用滑行艇工程背景。
4. Fridsma systematic rough-water planing craft experiments. 用于规则波/不规则波中运动和加速度幅值对照。
5. Sun and Faltinsen, 2010. 用于 Fridsma configuration A 的规定状态和开发验证背景。
6. Katayama, Hinami and Ikeda, longitudinal motion of super high-speed planing craft in regular head waves. 用于高 Froude 数规则迎浪、跳跃分类和幅值验证目标。
7. Ma 2005 2.5D method and Wigley III / SL-7 coefficient comparisons. 用于完整站位式 2.5D 水动力矩阵验证。
8. Fossen marine craft dynamics literature and PythonVehicleSimulator/MSS 思路。用于六自由度表述、相对速度和环境载荷框架。
9. OpenPlaning open-source code. 用于 Savitsky/Faltinsen 平衡、湿长、矩阵和 porpoising 结构参考。
10. PDSTRIP source and sectionresults. 用于 strip-theory 截面水动力、外部求解器 smoke test 和完整 2.5D 升级诊断。
11. Alessandro Iafrati, 2013, *A fully nonlinear iterative solution method for self-similar potential flows with a free boundary*. 用于自相似自由边界、远场偶极匹配、伪时间推进、控制面和浅水薄射流模型；Table 1 提供 Zhao--Faltinsen 压力峰值及峰位精确标量基准。

---

## 19. 一句话总结

当前项目的理论核心是：

> 用 Savitsky/Faltinsen 方法先求高速滑行艇的稳态 trim、sinkage 和湿长，再在该平衡点附近建立 Faltinsen 第 9 章 heave-pitch 线性系统，结合遭遇频率和波浪激励求 RAO；对于规则波/不规则波进一步进行时域积分和六自由度格式输出；最终用 Faltinsen、Fridsma、Katayama、Ma 2005 等公开对照逐层验证其合理性。

当前最重要的科学边界是：

> Ma 2005 水动力 Gate 1 已通过，但整船规则迎浪 Gate 2 仍为 `17/20 PASS`；只有二维入水压力、Sun--Troesch 源级系数及 Begovic 三航速运动门槛全部闭合后，才能称为经独立试验验证的线性高速 2.5D 纵向运动模型。

---

## 20. Iafrati 自相似楔形入水与浅水薄射流

这一部分是 Gate 2 二维压力先决门的最新理论补充。它用于解决标准时域边界元没有解析出“上射流--根部回折--下自由面”拓扑的问题，不替代 Ma 2005 整船 2.5D 方程。

### 20.1 自相似变量

对于楔体以恒速 $V$ 入水、忽略重力的早期阶段，引入

$$
\xi=\frac{x}{Vt},\qquad
\eta=\frac{y}{Vt},\qquad
\varphi=\frac{\Phi}{V^2t},\qquad
\rho^2=\xi^2+\eta^2.
$$

其中 $(\xi,\eta)$ 是随 $Vt$ 缩放后的空间坐标，$\Phi$ 是物理速度势，$\varphi$ 是无量纲自相似势。再定义修正势

$$
S=\varphi-\frac12\rho^2.
$$

引入 $S$ 的原因是把自由面运动学条件化为几何条件。最终自由面同时满足

$$
S_\nu=0,
\qquad
S_\tau=-\sqrt{-2S},
$$

其中 $\nu$、$\tau$ 分别表示自由面的法向和弧长切向。若弧长原点取在满足相容条件的交点，则 Iafrati 式 (34) 为

$$
S=-\frac12\tau^2.
$$

因而自由面 Dirichlet 条件可直接写成

$$
\varphi=\frac12\left(\rho^2-\tau^2\right).
$$

### 20.2 混合边值问题及法向约定

流体域内满足

$$
\nabla^2\varphi=0.
$$

对半域楔体，Iafrati 式 (20)--(22) 给出对称面、楔面和自由面条件。论文中的 $\nu$ 指向流体；本项目 `ClosedBoundary2D.panel_normal` 指向流体多边形外部，因此右侧楔面的实现值应进行方向转换：

$$
\left.\varphi_{\nu,\mathrm{code}}\right|_{S_B}=-\cos\gamma,
$$

其中 $\gamma$ 是斜升角。这个负号来自法向定义，不是经验修正。

### 20.3 远场偶极势与式 (30)

为缩小计算域，远场使用

$$
\varphi_D=\frac{\eta}{\xi^2+\eta^2},
\qquad
\varphi=C_D\varphi_D.
$$

偶极系数 $C_D$ 与边界未知量共同求解。额外方程不是全闭合边界零通量，而是 Iafrati 式 (30) 的**远场通量匹配**：

$$
-\sum_{j\in S_F}\varphi_{\nu,j}\Delta s_j
+C_D\sum_{j\in S_F}\varphi_{D,\nu,j}\Delta s_j=0.
$$

此前把它误写为全边界零通量会使 $C_D$ 和矩阵条件数异常增大。按原式修正后，`20 deg` 诊断的偶极系数由约 `119` 降至量级 `4--6`，条件数由约 $1.24\times10^7$ 降至约 $2\times10^3$。

### 20.4 自由面伪时间更新

Iafrati 式 (32) 用修正势梯度作为伪速度：

$$
\frac{D\boldsymbol{x}}{DT}=\nabla S.
$$

当 $S_\nu\to0$ 时，伪速度只剩切向分量，不再改变自由面形状。论文采用二阶 Runge--Kutta 方法，并限制单步质心位移小于局部面板长度的四分之一。当前代码已经实现式 (51) 偶极初态预迭代、二阶伪时间、按弧长重网格、船体角点约束、远场圆弧约束和位移拒绝；`10 deg` 射流接管采用步内二分定位，避免结果依赖整步越过事件。混合边界角点处的交点速度取船体侧 $\nabla S$ 的切向分量，因为自由面侧和船体侧的法向导数在角点不连续。

### 20.5 控制面薄射流近似

若切去最薄的射流，在截断点 $\tau^*$ 有

$$
S_\tau(\tau^*)=-\tau^*,
\qquad
\varphi_\tau=S_\tau+\rho\rho_\tau.
$$

控制面法向速度采用 Iafrati 式 (37)：

$$
\varphi_\nu=\varphi_\tau\cos\beta,
$$

其中 $\beta$ 是局部自由面切线与船体的夹角。代码使用切向速度向控制面外法向的向量投影实现该式，避免把正负号写成与坐标方向绑定的常数。

### 20.6 浅水薄射流方程

令 $\lambda$ 沿船体，$\mu=f(\lambda)$ 为局部射流厚度。忽略修正势跨厚度变化后，Iafrati 式 (41)--(42) 为

$$
\left(\widetilde S_\lambda f\right)_\lambda+2f=0,
\qquad
\widetilde S_\lambda=-\frac{S_\tau}{\sqrt{1+f_\lambda^2}}.
$$

离散空间推进采用式 (43)--(46)：

$$
f^k_{i+1}=\omega f^{k-1}_{i+1}
-(1-\omega)f_i
\frac{\Delta\lambda-\widetilde S_{\lambda,i}}
{\Delta\lambda+\widetilde S^{k-1}_{\lambda,i+1}},
$$

$$
f^k_{\lambda,i+1}=\frac{f^k_{i+1}-f_i}{\Delta\lambda},
$$

$$
S^k_{\tau,i+1}=S_{\tau,i}
+\sqrt{\Delta\lambda^2+\left(f^k_{i+1}-f_i\right)^2},
$$

$$
\widetilde S^k_{\lambda,i+1}
=-\frac{S^k_{\tau,i+1}}
{\sqrt{1+\left(f^k_{\lambda,i+1}\right)^2}}.
$$

特别注意，最后一式是**除以**根号项，不是乘以；PDF 原图已人工复核。松弛因子通常取 $\omega=0.9$，空间步长取与射流相接的第一个自由面面板长度的一半。当

$$
|S_{\lambda,i+1}|<\Delta\lambda
$$

时停止，表示到船体交点的剩余距离已经小于一个空间步长。

### 20.7 压力恢复

Iafrati 式 (47) 的无量纲压力函数为

$$
\psi=-\varphi
+\xi\varphi_\xi+\eta\varphi_\eta
-\frac12\left(\varphi_\xi^2+\varphi_\eta^2\right),
$$

图表使用

$$
C_p=2\psi=\frac{2p}{\rho_w V^2}.
$$

压力峰值必须同时检查幅值和位置。Iafrati Table 1 的 Zhao--Faltinsen 精确标量为：`10 deg: (77.85, 0.5556)`、`20 deg: (17.77, 0.5087)`、`30 deg: (6.927, 0.4243)`，括号内依次是 $(C_{p,\max},\eta_{\max})$。

### 20.8 当前实现与证据边界

公式与代码对应关系如下：

| 理论项 | 代码 |
| --- | --- |
| 式 (17)/(24) $S_\nu=0$ | `SelfSimilarWedgeBvpResult.kinematic_residual` |
| 式 (29)--(30) 偶极增广边值问题 | `solve_self_similar_wedge_bvp` |
| 式 (51) 偶极初态和预迭代 | `build_iafrati_dipole_initial_free_surface`、`solve_iafrati_dipole_preliminary_iterations` |
| 式 (31)--(34) 二阶伪时间 | `advance_self_similar_wedge_pseudo_time_rk2`、`solve_self_similar_wedge_pseudo_time` |
| 两种外域闭合 | `SelfSimilarWedgeConfig.jet_closure` |
| 式 (43)--(46) 浅水射流 | `march_iafrati_shallow_water_jet` |
| 根部量与方向资格检查 | `derive_shallow_water_jet_root_state` |
| 两步一面板的射流增广边界 | `solve_self_similar_wedge_with_shallow_jet` |
| 完整增广解根部回读与内迭代 | `derive_shallow_water_jet_root_state_from_coupled`、`iterate_shallow_jet_root_coupling` |
| 增广外域重复伪时间 | `solve_coupled_self_similar_wedge_pseudo_time` |
| 分布曲线后验评分 | `evaluate_self_similar_wedge_reference` |
| Table 1 精确标量评分 | `evaluate_self_similar_wedge_scalar_reference` |

旧的低分辨率控制面候选曾给出负 $S_\lambda$；`80` 个自由面板、根部最小面板约 `0.017` 的来源一致加密证明该符号是粗网格角点误差。加入 `10 deg` 事件定位后，`pseudo_cfl=0.20、0.10、0.05` 的根部厚度均约为 `0.00299`，$S_\lambda$ 均约为 `1.688`，浅水射流均可推进到约 `378` 个节点。

完整增广解的根部速度与截断外域仍不相同。固定外域的根部内迭代使 $S_\lambda$ 从 `1.6879` 收敛至 `3.0076`，最终相对变化为 `0.053%`；但根部一致增广解的自由面误差仍为 `30.6%`、压力分布误差为 `43.2%`、精确峰值和峰位误差为 `39.6%/66.0%`。一个包含根部内迭代的外域伪时间步也未使运动学残差下降。因此当前仍为诊断未验证状态，下一步必须证明重复增广伪时间在网格和时间步加密下收敛，再执行 `10/20/30 deg` 三角度压力与积分力硬门槛。

## 21. 近奇异直线面板解析核与动态射流接口

### 21.1 常单元直线面板闭式积分

设源面板弧坐标为 $s\in[0,L]$，场点相对面板起点在局部切向和法向的坐标分别为 $a$、$b$，并令 $u=s-a$。本项目二维 Green 函数省略公共常数后写为

$$
G(u,b)=\frac12\ln\left(u^2+b^2\right).
$$

单层核的原函数为

$$
F_G(u)=\frac12u\ln(u^2+b^2)-u
+|b|\operatorname{atan2}(u,|b|),
$$

因此

$$
\int_0^L G\,ds=F_G(L-a)-F_G(-a).
$$

双层核在代码外法向约定下为

$$
\frac{\partial G}{\partial n_q}=-\frac{b}{u^2+b^2},
$$

其积分由带符号的反正切端点差直接得到。共线不同面板取 Cauchy 主值零，自面板再加入与本项目边界方向一致的 $-\pi$ 跳跃项。自面板单层积分为

$$
L\left[\ln\left(\frac{L}{2}\right)-1\right].
$$

固定阶求积在 $|b|/L\ll1$ 时可能完全漏过双层核尖峰，同时离散线性系统残差仍很小；因此低残差不能证明薄射流两侧相互作用正确。

### 21.2 连续线性单元端点权重

线性形函数为

$$
N_L(s)=1-\frac{s}{L},\qquad N_R(s)=\frac{s}{L}.
$$

除零阶积分外，还需要单层核的一阶矩。令

$$
J_G(u)=\frac14(u^2+b^2)\left[\ln(u^2+b^2)-1\right],
$$

则

$$
I_G=F_G(u_1)-F_G(u_0),
$$

$$
M_G=J_G(u_1)-J_G(u_0)+aI_G,
$$

其中 $u_0=-a$、$u_1=L-a$。左右端点贡献分别为

$$
G_R=\frac{M_G}{L},\qquad G_L=I_G-G_R.
$$

双层核同理使用零阶反正切积分 $I_H$ 和一阶矩

$$
M_H=-\frac12b\ln\frac{u_1^2+b^2}{u_0^2+b^2}+aI_H,
$$

从而

$$
H_R=\frac{M_H}{L},\qquad H_L=I_H-H_R.
$$

这些端点贡献先按源面板计算，再装配到相邻公共节点。代码保留 `gauss_order` 仅为统一配置和输入校验，直线面板核本身不再依赖固定阶 Gauss 求积。

### 21.3 射流接口分辨率与拓扑事件

Iafrati 第 3.3 节指出，若边界积分仍直接描述薄层，面板长度应与局部厚度同量级。当前定义

$$
R_j=\frac{f_{root}}{\Delta s_{outer,1}}.
$$

当 $R_j<0.5$ 时，首段不再具有边界积分分辨率，应转交式 (43)--(46) 的浅水模型；迁移目标为 $R_j=1$。若该目标跨过自由面局部切向转折，则在 $[0.5,1]$ 内回退到仍保持首面板沿船体外向的最大可行位置。若首面板的船体切向投影本身变为非正，而后续面板仍外向，则只转交连续的前导非外向面板。

接口是数值匹配面而非物质点，因此这种迁移不改变物理自由面，只改变外域边界积分与浅水近似的责任边界。每次迁移后都必须：

1. 沿新外自由面重新计算弧长；
2. 由远场向根部重新积分式 (34) 的自由面势；
3. 用完整增广边界积分解回读根部 $S_\lambda$；
4. 逐点满足式 (43)--(46)，不得用压力参考值决定符号或倍率；
5. 保持偶极系数为正、首外域面板方向有效，并记录 $R_j$、根部船体坐标和矩阵条件数。

当前 `20 deg` 诊断证明该机制可把原先约第 `6` 步的根部塌陷延后并显著降低运动学残差，但压力峰位仍远低于 Iafrati Table 1 的 $\eta_{max}=0.5087$。当已有折线同时逼近分辨率下限和切向转折时，仅丢弃整面板仍会失去可行接口；下一步必须在根部邻域按曲率和厚度新增局部节点，并验证该重网格在不同基础网格下给出相同的根部轨迹和压力结果。

当前整面板迁移 `80` 步诊断进一步表明，避免程序中止并不等于收敛。运动学残差先由 `1.916` 降至 `0.693`，随后反弹至 `1.350`，同时条件数升至 $2.22\times10^5$，压力误差基本不变。因此不得选择中间最小残差状态作为结果；局部重建的接受条件必须同时要求最终残差下降、条件数受控、根部轨迹稳定以及压力后验误差改善。

对整条外自由面采用广义交叉验证三次平滑样条的候选虽然能消除面板级转角振荡，但改变了根部势流匹配，`20\ \mathrm{deg}` 算例在第 `18` 步触发式 (43) 奇点，残差和压力均未改善。因此该候选默认关闭。后续平滑或新增节点只能局限于根部邻域，并必须在同一步内重新积分式 (34)、重建浅水射流和重解增广边界积分问题。

### 21.4 连续线性增广边界积分与根状态兼容事件

常单元在厚度尺度的相邻射流面板上对根部切向梯度较敏感。当前新增的连续线性诊断分支将面板端点形函数贡献装配为

$$
\mathbf H\boldsymbol\phi-\sum_e
\left(\mathbf G^e_L q^e_L+\mathbf G^e_R q^e_R\right)=0,
$$

并保留船体、自由面、远场和对称面交界处法向导数不连续。远场势仍写为

$$
\phi_D=C_D\frac{\eta}{\xi^2+\eta^2},
$$

$C_D$ 与节点未知量在同一个增广系统中求解；最后一行按线性端点梯形积分执行远场通量匹配。自由面节点势由式 (34) 在新弧长上重算，面板切向速度直接取

$$
\phi_\tau^e=\frac{\phi_R^e-\phi_L^e}{L_e},
$$

不再把节点解作为常面板值二次差分。该分支状态明确标记为 `continuous_linear...unvalidated`，未通过三角度基准前不进入生产模型。

除厚度分辨率事件外，匹配面还必须满足两项来源一致的资格条件。第一，首外域面板与楔面夹角低于 `10 deg` 时，该前导薄层转交浅水模型。第二，若式 (43)--(46) 在首个空间步的正厚度区间没有解，则当前根状态不具备浅水匹配资格；算法外移匹配面并由新外域边界积分重新给出根值，不对 $S_\lambda$ 截断、取绝对值或按参考压力修正。固定点迭代跨越式 (43) 分母极点时，还使用同一四式消元后的标量方程做括区复核；括区同样无解才触发接口迁移。

固定 `12` 个根区面板的压缩重布点 `v50` 和增加 `24` 个局部节点的 `v51` 均被排除：二者虽使 $R_j\approx1$，却分别把条件数提高到约 $1.68\times10^5$ 和 $1.60\times10^5$，运动学残差增至 `4.83` 和 `4.25`，且不能维持正的后续根状态。这说明节点细化不能脱离单元插值与根值兼容单独启用。

连续线性、动态小夹角接管和首步兼容迁移组合的 `v59` 完成 `80` 个耦合伪时间步。运动学残差由 `1.391` 降至 `0.534`，条件数保持在约 $3.11\times10^4$ 至 $7.42\times10^4$；分布压力归一化均方根误差为 `39.29%`，精确压力峰值和峰位误差为 `28.60%/50.90%`。最终接口 $S_\lambda=3.787$，完整增广解回读值为 `4.118`，相对不一致为 `8.74%`。

固定 `v59` 末态外自由面后，新增的标量根相容求解将界面值收敛至 $S_\lambda=4.16328$，完整边界积分回读值为 `4.16444`，相对不一致降至 `0.0278%`；但压力分布误差仍为 `39.30%`，峰值和峰位误差仍为 `28.60%/50.90%`。这证明根不一致可以数值闭合，却不是当前压力误差的主因。将该内迭代强制用于每个 Runge--Kutta 阶段的 `v60` 在初始状态可收敛到 `0.0035%`，但动态重网格和匹配面迁移后，全部浅水物理解域内均有 $F(S_\lambda)-S_\lambda>0$，不存在固定点，首步无法接受。因此逐阶段强制固定点属于额外约束，当前只保留为诊断，不作为来源一致的默认伪时间算法。

连续节点梯度恢复进一步证明，最后一个主楔面面板与浅水射流楔面之间的压力跳变并非单纯由面板中点导数造成：该分支的压力分布误差仅由 `39.29%` 变为 `39.24%`，峰位反而更靠内，故同样保持默认关闭。

不施加根固定点、继续按当前完整解回读根状态的 `v61` 完成全部 `160` 步。运动学残差由 `1.391` 单调总体下降至 `0.350`，最终条件数约 $3.37\times10^4$，偶极系数为正；自由面和压力分布误差分别改善至 `27.56%` 和 `35.43%`，精确压力峰值和峰位误差改善至 `21.78%/38.11%`。匹配面船体纵坐标由 `0.1851` 外移至 `0.3572`，与压力峰逐步外移的趋势一致。该候选仍未满足压力 `<=10%`、峰位 `<=5%` 和运动学收敛门槛，不能判为通过；下一步必须先实现冻结末态检查点/恢复，再执行延长伪时间、时间步和网格的联合收敛，而不能从头盲目重复更长算例。

上述修改后的二维非线性定向回归为 `104 passed`，完整回归为 `495 passed`、`0 failed`。这证明诊断分支、配置和结果历史没有破坏既有软件行为，但不构成压力物理基准通过。

### 21.5 检查点、离散收敛与根点数值恢复

耦合伪时间末态不能只保存最终压力或最终节点。自由面式 (34) 的势由前一接受步的形状偶极系数推进，因此精确恢复还必须保存：完整外自由面节点、前一接受步偶极系数、当前接口根状态、累计伪时间、逐步接受步长及所有诊断历史。正式检查点采用版本化 JSON、外自由面 CSV 和历史 CSV，并分别记录 SHA-256。v61 的正式检查点重建后最大相对差约为 $5.95\times10^{-12}$；从同一状态直接推进两步与分两次各推进一步的外自由面最大绝对差为 $3.55\times10^{-15}$，机器等价检查为 `PASS`。

检查点普通恢复只允许覆盖 `pseudo_cfl`。楔角、单元类型、网格、匹配规则和根状态恢复算法不得借普通恢复静默改变；空间网格或算法变化必须作为显式状态变换单独记录。这一限制使时间步收敛只改变一个数值变量。

从同一 v61 冻结末态出发，使用 `pseudo_cfl=0.20、0.10、0.05`，分别推进 `4、8、16` 步，使新增伪时间的相对离散仅为 `0.033%`。最细两档之间：运动学残差变化 `0.0115%`，匹配面船体坐标变化 `0.0106%`，积分垂向力变化 `0.0129%`，压力峰值变化 `0.0096%`，整条压力曲线相对 $L_2$ 变化 `0.0124%`。时间步机器门为 `PASS`，但该结论只证明冻结网格上的时间离散稳定，不证明压力物理正确。

空间网格通过显式弧长重采样实现。为了不随面板数改变总体根部聚集程度，若源网格有 $N_s$ 个面板、增长率 $r_s$，目标 $N_t$ 个面板采用

$$
r_t=r_s^{N_s/N_t}.
$$

根点和远场端点保持不变，重采样后重新积分自由面势并重解增广边界积分。`80 -> 120` 面板的几何相对 $L_2$ 误差为 $5.34\times10^{-6}$。

第一次细网格试算暴露了一个实质性缺陷：浅水射流推进器固定 `maximum_points=500`。`80` 面板时空间步约为 `0.00838`，`444` 点可到尖端；`120` 面板时空间步约为 `0.00554`，旧算法在第 `500` 点仍有厚度 `0.0131`、$S_\lambda=0.956$，却被边界装配强制闭合成尖端。该伪尖端使浅射流压力曲线产生约 `10.7%` 的假网格差。现将保护上限提高，并规定未满足 $|S_\lambda|<\Delta\lambda$ 或厚度容差时必须显式失败。修正后的 `120` 面板射流用 `672` 点到达尖端，末端厚度约 $4.52\times10^{-5}$、$S_\lambda\approx0.00330$。

固定同一个根状态单独细化式 (43)--(46) 的空间步时，厚度曲线由粗到中、由中到细的相对变化分别为 `0.139%` 和 `0.067%`，说明射流空间推进器自身收敛。剩余网格敏感性来自根值的读取位置：边界积分速度定义在面板中点，而浅水匹配量属于根节点。旧方法直接取首个浅射流船体面板中点；新诊断候选用前三个同一平滑船体段的中点值，对弧长坐标作单侧二次外推到根点。它不同于此前被排除的“用式 (42) 外推代替 $i=1$ 的边界积分量”：新候选的三个样本全部来自完整增广边界积分解，只执行离散点到根节点的数值恢复，不引入式 (42)、参考压力或经验倍率。

在完全相同的 v61 冻结几何上，首面板中点根值随 `80/120/160` 网格为 `2.855/2.804/2.778`；三点二次根外推为 `2.673/2.680/2.684`，后两级变化约 `0.16%`。该方法作为 `quadratic_root_extrapolation` 显式候选保留，旧检查点继续使用 `first_panel_midpoint`，避免改变既有证据链。

采用同一二次根外推候选后，`80/120` 面板两级空间比较中：根测量值变化 `2.87%`，运动学残差变化 `0.99%`，积分力变化 `0.20%`，自由面曲线变化 `0.038%`，外域船体压力曲线变化 `0.25%`，公共物理坐标上的整条船体压力曲线变化 `0.90%`，均低于 `5%`，两级空间机器门为 `PASS`。浅射流低压子段按其自身能量归一化仍有 `11.28%`，保留为诊断，不用它替代全压力曲线、峰值和积分力的既定验收量；三网格观测阶仍待补充。

从二次根外推 `80` 面板检查点继续推进到累计局部第 `88` 步后，运动学残差由 `0.3500` 降至最低 `0.2534`、末态 `0.2544`；自由面和压力分布误差降至 `25.81%/31.66%`，压力峰值和峰位误差降至 `17.10%/29.86%`。约每五步发生一次匹配面迁移，残差短暂跳升后下降包络仍继续降低。该结果证明当前误差不是时间步或两级网格未收敛造成的，但自由边界迭代仍未达到 $10^{-3}$，二维压力先决门和 Gate 2 均保持 `FAIL/17/20 PASS`。下一最小任务是从 v75 检查点继续到残差包络收敛或被证实进入极限环，再以收敛末态执行第三网格和三角度硬门槛。

上述检查点、完整射流尖端资格、二次根外推候选和收敛分析器合入后的完整回归为 `505 passed`、`0 failed`，耗时 `736.93 s`。`1247` 条运行时警告仍全部来自既有 `tests/test_validation.py` 的空切片统计；`pytest-asyncio` 另有默认事件循环作用域弃用提示。软件回归通过不改变二维压力物理门 `FAIL`。
## 22. 连续法向形状更新、细网格周期与双参考边界

### 22.1 切向规范与法向形状速度

自由面伪时间方程

$$
\frac{D\boldsymbol{x}}{DT}=\nabla S
$$

包含切向和法向分量。连续曲线的切向速度只改变节点标签，形状演化由 $S_\nu$ 决定。为检验离散切向恢复是否制造平台，本项目实现了默认关闭的 `continuous_normal` 候选。设面板 $e=(i,j)$ 的长度为 $L_e$、常法向为 $\boldsymbol n_e$，端点残差为 $r_i,r_j$，节点连续法向为 $\boldsymbol n_i,\boldsymbol n_j$。令节点形状速度为 $c_i\boldsymbol n_i$，最小化逐面板向量误差的 $L_2$ 泛函，得到质量矩阵项

$$
M_{ii}^{(e)}=\frac{L_e}{3},\qquad
M_{ij}^{(e)}=\frac{L_e}{6}\boldsymbol n_i\cdot\boldsymbol n_j,
$$

以及载荷项

$$
b_i^{(e)}=\frac{L_e}{6}(2r_i+r_j)
(\boldsymbol n_i\cdot\boldsymbol n_e).
$$

装配并求解 $M\boldsymbol c=\boldsymbol b$ 后，以 $c_i\boldsymbol n_i$ 更新形状，节点切向分布由弧长重网格维护。上式载荷中的两个括号相乘，代码对应 `(2*r_i+r_j)*(n_i dot n_e)`。

该候选在直线线性场解析测试中精确，但在 v197 冻结状态的四倍时间步加密中没有突破 `K≈0.005` 平台，并略劣于完整梯度更新。因此它只证明切向规范不是平台主因，不能作为生产替代。

### 22.2 真正的空间加密必须继续演化

把粗网格末态插值到细网格只能测量同一几何的离散误差，不能代表细网格自由边界收敛解。当前 element 梯度、固定喷射拓扑的 `N=120/160/240` 冻结强式积分分别为 `0.003559/0.003065/0.002819`；N=240 继续演化后最低为 `0.00235752`，随后形成固定拓扑周期。半时间步共同伪时间差为 `1.67%`，排除粗时间步是周期主因。

光滑外自由面的线性法向导数已经共享全局节点；冻结 v203/v204 的相邻端点 $q$ 跳跃严格为零。强式端点分量来自多边形法向与连续曲率的离散差异，不是逐面独立通量未知量。

### 22.3 无重置稳态相位资格

向量 Aitken 原资格只允许至少三次匹配面重置后推断周期相位。固定拓扑细网格存在另一种可证明状态：不少于八个状态、预估和校正匹配面位移始终为零、边界面板数恒定、根部厚度与分辨率无联合跳变。该状态记为 `phase=0`、`period=1`、`reset_count=0`。缺失显式诊断或历史不足时仍拒绝。

v211/v212/v216 满足该资格，但其向量收敛因子为 `q=-1.31904`，不在冻结区间 $(0,0.9]$，故 Aitken 候选在重建前即被拒绝。无事件资格只允许进入后续物理检查，不保证加速成立。

### 22.4 Zhao--Faltinsen 与 Iafrati 双参考

v212 对 Iafrati 自由面的同横坐标和完整重叠区归一化均方根误差为 `2.69%/1.87%`，对 Zhao--Faltinsen 为 `11.10%`；两套冻结参考彼此差约 `17.33%`。这表明当前求解器已复现来源一致的 Iafrati 曲线，但尚未闭合独立理论差异。报告必须并列给出二者，不能选择较有利参考替代既定门槛。
## 23. 有限远场尾段与浅水射流尖端闭合审计

### 23.1 Iafrati 有限远场条件

Iafrati（2013）式（29）在有限边界 $S_F$ 上采用偶极势

$$
\phi=C_D\phi_D,\qquad \phi_D=\frac{\eta}{\xi^2+\eta^2},
$$

法向导数由边界积分方程求解；式（30）再施加总通量相等条件

$$
-\int_{S_F}\phi_\nu\,ds
+C_D\int_{S_F}\phi_{D\nu}\,ds=0.
$$

代码使用流体域外法向，原文使用指向流体域的法向；两项同时反号，故离散方程整体等价。不能在此基础上再额外同时指定点态法向导数，否则会把混合边值问题过约束。

### 23.2 式（51）和扩域口径

偶极远场给出的自由面渐近初值为

$$
\eta\simeq\frac{C_D}{3\xi^2}.
$$

扩大远域时必须区分三类变化：旧内域几何变化、旧内域边界积分解变化和新追加尾段自身的运动学积分。只有冻结旧节点并分别积分，才能判断误差是否向内传播。若旧端点尚未进入式（51）的渐近区，直接追加过渡尾段只能作为初始化，必须充分松弛后才有资格参与远域收敛比较。

### 23.3 正定伪时间预条件

实验预条件采用

$$
\frac{d\boldsymbol{x}_i}{d\tau}=p_i\nabla S_i,
\qquad p_i>0.
$$

正定 $p_i$ 不改变目标法向稳态 $S_\nu=0$，但会改变到达稳态的路径。它必须通过原始均匀伪时间推进在共同状态或共同伪时间上的交叉验证；残差降低速度本身不能作为物理通过证据。本轮面板长度预条件未改善 $K$，保持默认关闭。

### 23.4 射流尖端的两步配对

式（43）--（46）推进到 $|S_\lambda|<\Delta\lambda$ 时，剩余尖端距离小于一个空间步。为继续满足第 3.4 节“两步组成一个边界积分面板”，可将剩余区间划分为一个或两个子步，使总步数为偶数。该连续闭合消除了几何定义上的奇偶总长差，但本轮计算没有消除 $K$ 周期，因此它不是当前平台误差的充分解释，仍为显式实验模式。

## 24. 远场角点双通量与低模态稳态下降

### 24.1 几何角点的势连续与通量不连续

外自由面和有限远场圆弧在公共几何节点相交时，势函数应连续，但两侧法向不同，因此 $q_-=\nabla\phi\cdot\boldsymbol n_-$ 与 $q_+=\nabla\phi\cdot\boldsymbol n_+$ 一般不相等。实验分支以两个移入相邻面板内部的配点代替角点单一配点，并增加一个端点通量未知量，使系统维数仍保持方阵。该修正解除了一项不自然的公共通量约束，但 v228--v231 没有降低式（52）积分，故只保留为默认关闭的物理审计模式。

### 24.2 连续一次弱投影

设第 $e$ 个外自由面线性单元长度为 $L_e$，其两端残差为 $r_L^e,r_R^e$。将逐面可不连续残差弱投影到连续一次节点空间，装配

$$
M^e=\frac{L_e}{6}
\begin{bmatrix}2&1\\1&2\end{bmatrix},
\qquad
\boldsymbol b^e=M^e
\begin{bmatrix}r_L^e\\r_R^e\end{bmatrix},
\qquad
M\boldsymbol c=\boldsymbol b.
$$

投影能量为 $K_{P1}=\boldsymbol c^T M\boldsymbol c=\boldsymbol b^TM^{-1}\boldsymbol b$，不可表示分量为 $K_{unresolved}=K_{exact}-K_{P1}\ge0$。v212 得到 `0.00200748` 和 `0.00035005`；前两个离散余弦模态已占精确积分约 `82.78%`，说明平台主要含全局低阶误差，但同时存在稳定的非连续表示分量。

### 24.3 带保护的低模态线搜索

以低通投影 $\widetilde r_i$ 和节点角平分法向 $\boldsymbol n_i$ 构造

$$
\boldsymbol x_i^{trial}=\boldsymbol x_i+\alpha\widetilde r_i\boldsymbol n_i.
$$

每个候选必须重建自由面势、浅水射流和完整增广边界积分解；只在 $K$ 严格下降、面板相对位移不超过 `0.25`、条件数增长不超过 `5%`、偶极系数为正且根状态相容时接受。该搜索不读取任何参考压力或自由面。两模态由 `K=0.00235752` 降至 `0.00158537` 后全部正步长转为上升；四模态停在 `0.00200904`。因此简单的残差显式低通下降不是完整稳态求解器，不能替代低维雅可比/信赖域分析，更不能替代三角度独立物理验收。

## 25. 弱投影正交误差、检查点精确往返与单调射流分支

### 25.1 低模态 Jacobian 不是剩余平台的主解

对最低两个余弦形状模态构造有限差分 Jacobian $J=\partial\boldsymbol r/\partial\boldsymbol a$，阻尼 Gauss--Newton 步为

$$
(J^TJ+\lambda\,\mathrm{diag}(J^TJ))\Delta\boldsymbol a
=-J^T\boldsymbol r.
$$

v235 的 Jacobian 条件数为 `3.70`，预测与实际低模态下降比约 `0.9999`，但精确 $K$ 只由 `0.0015854` 降至 `0.0015771`，下一轮全部候选转为上升。这说明剩余平台不由低模态 Jacobian 病态造成。

### 25.2 正交误差分解

连续一次弱投影满足

$$
\|r\|_{L^2}^2=\|P_hr\|_{L^2}^2+\|r-P_hr\|_{L^2}^2.
$$

后项逐面板严格非负，可定位面板法向造成的端点不连续。同一冻结几何的 `N=120/160/240` 后项为 `0.00126937/0.00071847/0.00032115`，近似二阶下降；约 `95%` 始终位于外自由面首个弧长十分位。它是根区曲面法向的线性离散误差，但完整 $K$ 在末两级仍未满足 `5%` 收敛门。

### 25.3 浮点检查点必须逐位往返

射流空间推进包含整数点数和拓扑事件。外自由面坐标仅变化 $3.55\times10^{-15}$ 时，旧 CSV 解析可使射流点数由 `1674` 变为 `1676` 并切换增广解分支。因此正式节点表必须使用能够恢复原二进制浮点的解析模式；当前 Pandas 读取采用 `float_precision="round_trip"`，并以逐位相等测试验收。普通相对几何误差不足以证明这种混合连续/离散状态可恢复。

### 25.4 向尖端单调变薄是代数根资格

Iafrati 浅水射流由匹配面向尖端推进时，厚度应满足

$$
0\le f_i\le f_{i-1}.
$$

旧固定点迭代可能收敛到满足式（43）--（46）但使厚度突增的另一代数根，随后射流点数、尖端位置和增广通量发生分支跳变。当前固定点候选若违反单调变薄条件，必须转入标量括区求根，并只在非增厚正根中选择连续分支。修复后同一几何 `N=240–320` 的 $C_D$、压力、积分力和 $K$ 均连续，消除了 `N>=260` 的假高残差和 `N>=300` 的负偶极分支。

### 25.5 根相容不是剩余周期的充分条件

修复后的 `N=320` 状态推进 8 步，$K$ 仍先降后升。逐 Runge--Kutta 阶段强制根相容可把相对根不一致压至约 $10^{-5}$，但末态 $K$ 由无内迭代的 `0.002831` 变为 `0.002866`，没有消除周期。因此下一审计对象是原始形状速度与重网格维护所引入的净法向速度，而不是继续加密射流或收紧根容差。

## 26. 生产一致远域变换与端点局部精确残差信赖域

### 26.1 检查点变换必须落在生产几何流形上

检查点弧长重采样或远域延拓不能在样条插值后直接重建边界积分解。生产伪时间每一步还要施加约束、根区薄层转交、平滑、声明网格重采样、根部重构和匹配面分辨率迁移。记这一复合几何算子为 $\mathcal P_G$，显式变换后的节点必须先满足

$$
\boldsymbol x^{tr}=\mathcal P_G(\widetilde{\boldsymbol x}),
$$

并以再次投影的相对面板位移检验近似幂等性：

$$
d_G=\max_e
\frac{\left\|\boldsymbol m_e[\mathcal P_G(\boldsymbol x^{tr})]
-\boldsymbol m_e(\boldsymbol x^{tr})\right\|}{L_e}.
$$

若根部重构改变节点数，两条曲线先在归一化弧长上对齐，再计算位移。旧 `R=30,N=400` 变换的 $d_G\approx2.03$，说明它不是生产状态；修复后等密度 `R=30,N=600` 的再次投影为 $9.71\times10^{-9}$，`v290` 为 $9.60\times10^{-8}$。

### 26.2 远域比较必须同时保持面板密度与修正势常数

由自由面式 (34) 和有限远场偶极匹配，修正势弧长原点为

$$
\tau_*=\sqrt{R^2-\frac{2C_D\eta_R}{R^2}}-L_{FS}.
$$

扩大 $R$ 时，若新增曲线弧长与远场 $\tau$ 增量不相容，$\tau_*$ 会改变，从而同时改写旧内域上的自由面势。远域面板数还应按弧长近似同比增加；`R=20,N=400` 对照 `R=30,N=600`，而不是固定 `N=400`。等密度变换后两者 $\tau_*$ 仅差约 $8.34\times10^{-6}$，从而把积分常数和根部迁移从远场形状误差中分离出来。

### 26.3 精确端点残差向量

线性单元上残差从 $r_L$ 线性变化到 $r_R$，Iafrati 式（52）的单元精确积分为

$$
K_e=\frac{L_e}{3}\left(r_L^2+r_Lr_R+r_R^2\right).
$$

它可以严格写成二分量向量范数：

$$
\boldsymbol q_e=
\begin{bmatrix}
\sqrt{L_e/4}(r_L+r_R)\\
\sqrt{L_e/12}(r_L-r_R)
\end{bmatrix},
\qquad
K=\sum_e\|\boldsymbol q_e\|^2.
$$

因此有限差分 Jacobian 可以直接取 $J=\partial\boldsymbol q/\partial\boldsymbol a$，Gauss--Newton 预测目标与完整精确 $K$ 使用同一范数，避免只降低弱投影模态而遗漏端点不连续能量。

### 26.4 远端局部形状空间

远域延拓后的残差主要位于弧长末端时，纯全局余弦基会扰动已经稳定的根部和船体压力。当前诊断形状空间由 $n_g$ 个全局低阶模态与 $n_f$ 个远端紧支撑三角模态组成，并按连续线性弧长质量矩阵正交化：

$$
\mathbf B^T\mathbf M\mathbf B=\mathbf I,
\qquad
M^e=\frac{L_e}{6}
\begin{bmatrix}2&1\\1&2\end{bmatrix}.
$$

每个信赖域候选仍需完整重建自由面势、浅水射流和增广边界积分，并通过精确 $K$ 下降、面板位移、条件数、正偶极和根相容门。该方法不读取自由面或压力参考。`v290` 使用 `4` 个全局模态和 `8` 个远端局部模态，将等密度 `R=30,N=600` 的 $K$ 从 `0.00172922` 降至 `0.000810506`，实际/预测下降比为 `0.999951`，最大位移为 `0.05991` 个面板。

### 26.5 当前物理边界

`v290` 相对 `R=20,N=400` 的压力峰值和积分垂向力变化仅为 `0.0316%/0.0362%`，Iafrati 同横坐标自由面误差为 `2.67%`；但精确 $K$ 的远域相对变化为 `6.535%`，Zhao 自由面误差为 `10.84%`。因此该结果证明了远域算法路径和阈值内候选的可行性，不证明20°或三角度二维门已经通过。

## 27. 阈值内冻结态的强制固定步时间收敛

### 27.1 为什么默认停止逻辑不能直接用于该审计

若冻结态已满足 $K\le K_{tol}$，生产求解器应立即停止，避免对已收敛状态作无意义扰动。但时间步收敛要求从同一状态继续推进相同伪时间。为此只在显式诊断模式下令

$$
n_{step}=N_{requested},
$$

即使中途仍满足 $K\le K_{tol}$ 也完成指定步数。返回的 `converged` 仍按物理停止条件计算，而终止原因记录为达到指定步数；默认生产行为不变。

### 27.2 同一冻结态和共同伪时间

时间步比较必须固定几何、势、射流状态、网格、根部算法和所有物理参数，只改变伪时间步。取步长比例

$$
\Delta\tau_c:\Delta\tau_m:\Delta\tau_f=4:2:1,
$$

并分别推进 $1:2:4$ 步，使总推进时间

$$
T_j=\sum_{n=1}^{N_j}\Delta\tau_{j,n}
$$

近似相同。审计先验证三个源检查点哈希完全一致，再要求

$$
\frac{\max T_j-\min T_j}{\max T_j}\le0.005.
$$

### 27.3 共同时间上的轨迹与末态误差

对标量 $q$，最细两级末态变化定义为

$$
E_q=\frac{|q_f-q_m|}{\max(|q_f|,|q_m|,\epsilon)}.
$$

对不同时间节点的轨迹，先在共同伪时间区间插值，再计算相对二范数。除运动学均方根、匹配位置、偶极系数、压力峰值和积分垂向力外，必须把验收核心的精确线性单元积分

$$
K=\sum_e\frac{L_e}{3}(r_L^2+r_Lr_R+r_R^2)
$$

直接纳入比较，避免代理均方根稳定而主判据未稳定。

### 27.4 v292/v296 结果与边界

从正式 `v292` 检查点以 `CFL=0.25/0.125/0.0625` 分别推进 `1/2/4` 步，累计伪时间相对离散为 `0.00115%`。最细两级中，$K$ 变化 `0.0453%`，运动学均方根变化 `0.0212%`，积分垂向力变化 `0.000755%`，压力峰值变化 `0.0000407%`；所有末态与轨迹指标均低于 `5%`，故时间步子项为 `PASS`。

该结论只排除了冻结 `v292` 状态附近的粗时间步误差。远域 $K$ 变化 `6.535%`、Zhao 自由面误差 `10.84%` 及 `10/30\,deg` 缺失仍使二维先决门保持 `FAIL`，不得以时间收敛替代独立物理验证。

## 28. 趋零方程残差与远域物理输出收敛必须分门

### 28.1 相对残差差在零目标附近不适定

Iafrati 式（52）的

$$
K=\int_{S_S}S_\nu^2\,ds
$$

是非负方程残差，理论目标是 $K=0$。设两个离散解为 $K_1=\epsilon a$、$K_2=\epsilon b$，即使二者随 $\epsilon\to0$ 同时趋于精确方程，相对差

$$
\frac{|K_2-K_1|}{\max(K_1,K_2)}
=\frac{|a-b|}{\max(a,b)}
$$

也不趋零。因此，残差验收应要求每一级满足绝对 $K\le10^{-3}$；残差相对差用于诊断优化终态，不可替代自由面、压力和积分载荷的离散收敛。

### 28.2 曲线变化需要稳定的物理尺度

对共同坐标区间上的两条曲线 $q_c(x)$ 和 $q_f(x)$，采用

$$
E_{q,range}=\frac{
\sqrt{N^{-1}\sum_i[q_c(x_i)-q_f(x_i)]^2}
}{
\max\{\operatorname{range}(q_c),\operatorname{range}(q_f)\}
}.
$$

该定义与独立参考曲线的范围归一化均方根误差一致。普通相对二范数

$$
E_{q,L_2}=\frac{\|q_c-q_f\|_2}{\|q_f\|_2}
$$

仍作为诊断输出；当远场曲线整体接近零时，其分母可能很小，不能单独代表全曲线物理尺度。

### 28.3 v304/v301 等密度远域结果

`R=30,N=600` 的 `v304` 与 `R=40,N=800` 的 `v301` 具有相同非远域配置、相同最终 `16+1` 形状空间和共同检查点谱系。两级 $K$ 分别为 `0.000563798/0.000884020`，均通过绝对门；面板密度变化为零。自由面和压力曲线的范围归一化误差分别为 `1.852%/0.0561%`，压力峰值、积分垂向力和偶极系数变化为 `0.0089%/0.0464%/0.932%`，故 20° 远域数值子项为 `PASS`。

$K$ 相对差 `36.22%` 和自由面相对二范数 `13.40%` 均保留为诊断。该结论不改变 Zhao 自由面 `11.49%` 的失败，也不替代 `10/30\,deg` 验证。

### 28.4 已收敛检查点的恒等恢复

当源检查点已经满足绝对 $K$ 门时，普通恢复应在零接受步停止。零步输出必须显式记录 `identity_resume_at_converged_source`、源形状偶极系数、停止原因和配置覆盖，才能同时满足“状态未变”和“检查点变换可追溯”。`v303` 以 `KINEMATIC_CONVERGED` 停止，检查点重建误差除约 $4\times10^{-17}$ 的历史浮点舍入外均为零。

## 29. Iafrati 薄射流根的源级含义与端点重采样边界

### 29.1 根状态由主体流边界积分解提供

Iafrati 2013 第 13 页式（43）至式（46）建立薄射流浅水 marching，并说明第一个 marching 点的全部量来自边界积分表示。令根部状态为

$$
(f_1,S_{\lambda,1},S_{\tau,1},\Delta\lambda),
$$

其中 $f_1$ 是局部射流厚度，$S_{\lambda,1}$ 是沿射流方向的速度分量，$S_{\tau,1}$ 是相似势的时间型导数，$\Delta\lambda$ 是浅水 marching 步长。源算法要求这些量满足

$$
f_1>0,\qquad S_{\lambda,1}>0,\qquad S_{\tau,1}<0,
\qquad \Delta\lambda>0,
$$

并由主体流边界积分解在匹配面处直接给出。原论文未定义附加边界积分固定点

$$
F(S_{\lambda,1})=S_{\lambda,1}.
$$

因此该固定点迭代只能作为显式启用的诊断方法，不能在关闭根内迭代时仍覆盖源级根状态。生产源级模式必须令根预测种子为空，并在每个 Runge--Kutta 阶段重新读取主体流边界积分根量。

### 29.2 有限夹角条件不等于切向投影符号条件

Iafrati 2013 第 9--10 页的相似自由面更新使用完整伪速度梯度 $\nabla S$。法向分量决定自由面形状是否满足运动学条件，但切向分量仍参与拉格朗日节点推进。第 11 页的主体流--薄射流截断依据是自由面与艇体之间的夹角降到预设的小角度阈值，并要求截断处保持有限夹角以避免边界积分离散退化。

设主体自由面首面板为 $\Delta\boldsymbol{x}_1$，艇体外向单位切向为 $\boldsymbol{t}_b$。量

$$
\Delta\boldsymbol{x}_1\cdot\boldsymbol{t}_b
$$

只描述该面板沿艇体方向的投影符号。它既不是自由面与艇体夹角的充分条件，也不是原论文给出的物理可接受条件。只要面板长度、射流根厚度、边界方向和有限夹角均有效，夹角超过 $90\,\mathrm{deg}$ 所导致的负投影不能单独作为删除主体自由面面板或拒绝 Runge--Kutta 阶段的依据。

### 29.3 离散拓扑跳变的来源与修正

`v325-v327` 的逐阶段审计表明，第 54 步失败并非时间步过大：当首面板切向投影从极小正值跨到极小负值时，旧实现会一次删除两个主体自由面面板，使匹配根从约 `(2.2425, 0.2800)` 跳到 `(2.2606, 0.2471)`，并令浅水射流所需的 $S_{\lambda,1}$ 从正值突变为约 `-0.191`。减小时间步只能延迟跨越该人为分支，不能消除拓扑跳变。

因此生产实现已移除以下两项非源级约束：

1. 不再因主体自由面首面板的艇体切向投影非正而删除面板；
2. 不再以端点保持回退强制重采样后的投影符号为正。

仍保留的物理和数值检查包括：远场端点固定、根部位置和厚度有效、边界节点有序、自由面与艇体保持有限非退化夹角，以及浅水射流根量满足式（29.1）的符号要求。这里尤其要区分：浅水射流坐标中的 $S_{\lambda,1}>0$ 是沿射流 marching 方向的根状态条件，并不推出主体自由面首面板必须满足 $\Delta\boldsymbol{x}_1\cdot\boldsymbol{t}_b>0$。

### 29.4 修正后的数值证据边界

移除非源级投影约束后，`v333、v335-v343` 连续接受 `90` 个源级 Runge--Kutta 伪时间步且无拒步，绝对运动学积分由 `0.768622` 降至 `0.192179`；30° 自由面和压力曲线误差分别降至 `20.82%` 和 `27.94%`。这证明此前射流根符号失效来自实现制造的离散拓扑分支，但尚不能证明 30° 算例物理收敛或通过验证：阶段硬门仍为绝对 $K\le10^{-3}$、自由面误差不超过 `5%`、压力误差不超过 `10%`，且还必须完成网格、远域和时间步收敛审计。

## 30. 低斜升角负根与参考隔离同伦初始化

### 30.1 负根是匹配面淘汰条件，不是可放宽的符号约定

由 Iafrati 2013 式（42）

$$
\widetilde S_\lambda=-\frac{S_\tau}{\sqrt{1+f_\lambda^2}}
$$

以及自由面动态条件 $S_\tau=-\tau<0$，当前从主体流根部指向喷溅尖端的 $\lambda$ 方向必须有 $\widetilde S_\lambda>0$。因此 `S_lambda<=0` 不能取绝对值、反号或用经验正值覆盖。它表示当前主体流--薄射流匹配面不在空间 marching 的物理解支上。

数值搜索应将负根与“第一步非线性方程无物理解”统一处理：拒绝当前匹配面，向外转移主体自由面首段，重新求主体边界积分及全部根量；只有找到最小正根匹配面才接受。10° 默认初值在穷尽候选后仍无正根，证明问题来自初始自由面不在目标解邻域，而非单个面板位置。

### 30.2 根区纵向同伦

为避免用 10° 参考曲线构造初值，可从已收敛的相邻斜升角解出发。令源外自由面节点为 $(\xi(u),\eta(u))$，$u$ 为归一化弧长，构造

$$
\xi'(u)=\xi(u)\left[1+(s_x-1)(1-u)^p\right],
\qquad
\eta'(u)=\eta(u),
$$

其中 $s_x$ 是根区纵向尺度，$p>0$ 控制变换向远场衰减。该变换满足根节点按 $s_x$ 缩放、远场端点严格不动。它不是物理结果，只是目标斜升角边界积分的候选初值；每个候选仍必须重新求解主体流、浅水射流和增广边界积分。

候选资格只使用方程内量：正根、有限射流、边界积分残差、Iafrati 式（52）运动学积分和条件数。参考曲线只在目标斜升角存在冻结数据时于求解后评分。选中候选还必须接受直接伪时间步，并最终证明收敛到与同伦步长和初值路径无关的同一解。

### 30.3 当前 19.5° 证据

20° 到 19.5° 的 80 面板同伦候选在前 10 步经历接口重整，$K$ 从 `0.589986` 暂升至 `0.694790`；累计 40 步后降至 `0.422339`，累计 70 步后降至 `0.190611`。将射流边界积分面板由 256 改为 128 的零步变化中，$K$ 变化仅 `0.0030%`；再推进 10 步得到 $K=0.152775$，根不匹配为 `0.117%`。该结果证明同伦进入下降支，不代表 19.5° 或 10° 已通过验证。

## 31. 检查点加速的时间轴与信赖域边界

### 31.1 分段检查点时间不是全局时间戳

重网格续算检查点的历史从局部 `iteration=0`、`pseudo_time=0` 重新开始。若三个直接父子分段的局部时长为 $\Delta t_1$ 和 $\Delta t_2$，用于向量收敛因子的时间应重建为

$$
(t_0,t_1,t_2)=(0,\Delta t_1,\Delta t_1+\Delta t_2),
$$

而不能把三个分段末端的局部时长直接当作全局时间戳。只有检查点路径和父哈希证明直接父子关系时才允许该重建；没有谱系证据时继续使用报告的累计时间并执行严格间隔检查。

### 31.2 受限外推仍须通过物理解门

30° 晚期三段的向量收敛因子为 `q=0.936939`，高于冻结资格上限 `0.9`，原始 Aitken 因子会导致约 19 个局部面板的最大位移。显式信赖域截断虽可将位移限制为给定上限，但候选仍必须重新构建边界积分，并满足：

1. 浅水射流第一步存在物理解；
2. Iafrati 式（52）积分至少下降 10%；
3. 条件数不超过源状态的 5 倍；
4. 随后的直接伪时间步保持可行。

30° 的 `4/1/0.5/0.25/0.1` 面板截断候选全部在第一项被拒绝。因此全状态 Aitken 路线不能用于当前 30° 生产续算，配置允许上限 `pseudo_cfl=0.25` 的直接二阶 Runge--Kutta 推进仍是可信路线。

## 32. 端点精确运动学积分与冻结方向复用

### 32.1 线性面板残差的精确分解

若单个自由面板上的运动学残差按弧长坐标 $s\in[0,L]$ 线性变化，端点值为 $r_0,r_1$，则该面板对绝对运动学积分的精确贡献为

$$
K_e=\int_0^L\left(r_0+\frac{s}{L}(r_1-r_0)\right)^2\,\mathrm ds
=\frac{L}{3}\left(r_0^2+r_0r_1+r_1^2\right).
$$

中点平方近似为 $K_{e,m}=L[(r_0+r_1)/2]^2$。两者之差恒为

$$
K_e-K_{e,m}=\frac{L}{12}(r_1-r_0)^2\ge0,
$$

所以中点平方在端点近似反对称时会严重抵消，不能作为最终收敛门槛。19.5°、80面板审计中，面板内斜率项占精确积分的 `88.43%`，且主要集中在根区，说明需要解析端点平方积分和根区迹分辨率。程序中的 `_linear_residual_square_integral` 与验收量始终使用本式；绝对值积分不属于当前 Gate 2 定义。

### 32.2 曲率约束的角色

对折线自由面，设内节点转角为 $\theta_i$、对偶弧长为 $\ell_i$，定义离散曲率能量

$$
E_\kappa=\sum_i\frac{\theta_i^2}{\ell_i}.
$$

该量只用于拒绝通过高频折皱降低离散残差的信赖域候选；它不是自由面动力学方程，也不参与物理结果评分。候选还必须独立满足精确运动学积分下降、最大中点位移、边界积分条件数和根部匹配门槛。

### 32.3 冻结 Gauss--Newton 方向的适用边界

低模态残差向量记为 $\boldsymbol r$，形状系数为 $\boldsymbol a$，有限差分 Jacobian 为 $J=\partial\boldsymbol r/\partial\boldsymbol a$。带阻尼的方向由

$$
(J^\mathsf TJ+\mu D)\Delta\boldsymbol a=-J^\mathsf T\boldsymbol r
$$

求得，并投影到根部缺陷一阶保持约束的零空间。冻结方向复用不更新 $J$，因此只是一种廉价诊断；每一步都必须重建完整非线性边界积分并重新执行全部接受门。若所有允许步长均不能使精确积分下降，则方向已离开局部有效域，必须重新计算 Jacobian或缩小斜升角同伦步长，不能继续强推。

### 32.4 根缺陷闭合约束

主体流回读根速度与薄射流接口状态之间的有符号缺陷定义为

$$
d_r=\frac{S_{\lambda,m}-S_{\lambda,i}}{|S_{\lambda,i}|}.
$$

若只要求 $\nabla d_r^\mathsf T\Delta\boldsymbol a=0$，线性化会保持当前缺陷；当当前缺陷本身超过门槛时，应在KKT系统中改为

$$
\nabla d_r^\mathsf T\Delta\boldsymbol a=-d_r.
$$

这使未缩放的一阶步指向接口闭合。信赖域截断会相应缩小闭合量，因此实际候选仍必须用完整非线性重构后的 $|d_r|$ 判定。该约束来自同一物理接口量的两种计算表示必须一致，不使用参考曲线或经验根值。

### 32.5 连续节点通量与端点交替误差

在线性边界元中，节点法向通量沿面板线性插值且在相邻面板共享，而折线几何上的目标量 $\boldsymbol x\cdot\boldsymbol n_e$ 在每个直线面板内为常数、跨面板随法向变化。这会使节点通量围绕面板目标产生交替端点误差：中点平均可以接近零，但端点精确积分仍含显著面板内斜率项。

因此粗网格上的精确 $K$ 不能用中点 $K$ 替代，也不能只靠重复形状优化消除。正确判据是保持端点精确积分并进行空间细化，确认 $K$、自由面、压力和积分载荷共同稳定。19.0°的N160状态中，面板内斜率项占精确 $K$ 的 `98.03%`；重构到N320、N640和N1280后，精确 $K$ 依次降至 `9.29799e-4`、`3.15605e-4` 和 `1.96588e-4`，同时物理输出稳定，证明该项属于可收敛的离散迹误差，而非可删除的诊断噪声。

## 33. 联合根闭合映射与高维稳态自由面校正

### 33.1 根状态必须属于非线性候选映射

设自由面节点法向变量为 $\boldsymbol a$，浅水射流接口切向相似速度为 $S_{\lambda,i}$。若每次形状扰动只改变 $\boldsymbol a$、却冻结 $S_{\lambda,i}$，则优化器实际求解的是条件映射

$$
\boldsymbol r=\boldsymbol r(\boldsymbol a\mid S_{\lambda,i}^{old}),
$$

根一致性缺陷 $d_r$ 会迅速占满不等式裕度。物理一致的候选应在每次残差求值内部迭代

$$
S_{\lambda,i}^{(k+1)}
=(1-\omega_r)S_{\lambda,i}^{(k)}
+\omega_r S_{\lambda,m}(\boldsymbol a,S_{\lambda,i}^{(k)}),
$$

直到 $|d_r|\le\varepsilon_r$，再把闭合状态送入边界积分和运动学残差计算。这样求得的是约化映射

$$
\widehat{\boldsymbol r}(\boldsymbol a)
=\boldsymbol r\!\left(\boldsymbol a,S_{\lambda,i}^{*}(\boldsymbol a)\right).
$$

有限差分 Jacobian、Gauss--Newton方向及冻结方向复用必须使用同一个根内迭代次数、容差和匹配面策略。它们是非线性映射定义的一部分，不能只当运行参数；摘要缺失或不一致时必须拒绝复用。

### 33.2 12.75°三层证据对算法方向的约束

0.25°小步同伦与8次根内迭代把12.75°根缺陷稳定在 $10^{-9}$ 至 $10^{-8}$量级。经过DCT16、DCT32和前20%弧段局部余弦基校正，同一冻结形状的精确积分为

$$
(K_{320},K_{640},K_{1280})
=(3.77975,\ 3.39322,\ 3.36923)\times10^{-3}.
$$

640到1280面板仅变化约 `0.71%`，而三层都高于 $10^{-3}$。因此该平台不能再归因于根约束、粗网格端点误差或同伦步长。320面板残差中，前16面板约为 `1.65e-4`，去除两端窗口后的内部约为 `3.52e-3`；连续一次弱投影可表示量约为 `3.08e-3`，不可表示量约为 `7.10e-4`。下一算法应优先处理前30%弧段的可表示平滑残差。

一种可审计的后续形式是以独立节点法向位移 $\delta\boldsymbol n$ 为未知量，使用矩阵无关Newton--Krylov方法求解

$$
J(\boldsymbol a)\,\delta\boldsymbol a=-\boldsymbol r(\boldsymbol a),
$$

其中Jacobian向量积通过参考隔离的有限差分获得，根状态在每次函数求值内部闭合。线性子问题可用弧长质量矩阵和曲率算子预条件，但非线性接受仍必须检查未加权精确 $K$、真实根缺陷、条件数、最大位移和曲率能量。只有320/640/1280面板同时满足 $K\le10^{-3}$，该高维校正才具有数值闭合信用。

## 34. 矩阵自由全节点校正与精确端点Krylov子空间

### 34.1 归一化Jacobian向量积

设弧长质量正交形状基为$B$、系数方向为$\boldsymbol v$、最大面板中点位移比算子为$D(\cdot)$。为避免不同高维方向产生不同几何扰动尺度，先令$\widehat{\boldsymbol v}=\boldsymbol v/\|\boldsymbol v\|$，再取

$$
h=\frac{\varepsilon_d}{D(B\widehat{\boldsymbol v})},\qquad
J\boldsymbol v\approx
\|\boldsymbol v\|\frac{\widehat{\boldsymbol r}(\boldsymbol a+hB\widehat{\boldsymbol v})-\widehat{\boldsymbol r}(\boldsymbol a)}{h}.
$$

若正向扰动没有物理浅水根，则使用相同绝对值的负向扰动并保留有符号分母。根状态、匹配面策略和边界积分拓扑在每次函数求值中保持同一映射合同。12.75°代表方向在$\varepsilon_d=5\times10^{-4}$至$5\times10^{-3}$范围内的`Jv`变化小于`0.53%`，表明$10^{-3}$是当前可用的有限差分尺度。

### 34.2 全节点连续弱式空间

除冻结端点外，以每个自由节点的单位向量组成种子矩阵$E_f$。设连续一次弧长质量矩阵为$M$，通过

$$
G=E_f^\mathsf TME_f=LL^\mathsf T,\qquad
B=E_fL^{-\mathsf T}
$$

得到$B^\mathsf TMB=I$的全节点基。320面板、冻结远端两个节点时，未知量维数为319。弱投影节点残差$\boldsymbol c$的基系数为$B^\mathsf TM\boldsymbol c$；与64模态截断相比，该空间保留了几乎全部连续一次可表示残差。

### 34.3 精确端点残差向量

每个面板的精确积分可写成两个正交分量

$$
e_{2j}=\sqrt{\frac{L_j}{4}}(r_{j,0}+r_{j,1}),\qquad
e_{2j+1}=\sqrt{\frac{L_j}{12}}(r_{j,0}-r_{j,1}),
$$

从而$K=\|\boldsymbol e\|_2^2$。第一项代表面板平均残差，第二项代表端点跳跃或面板内斜率残差。连续一次弱投影只能完整表示其中的连续部分，因此仅降低弱投影范数可能同时增大第二项。

### 34.4 Krylov方向内的矩形Gauss--Newton

矩阵自由GMRES已计算一组系数方向$D=[\boldsymbol d_1,\ldots,\boldsymbol d_m]$。在同一次非线性扰动中额外记录精确端点残差导数

$$
G_e=[J_e\boldsymbol d_1,\ldots,J_e\boldsymbol d_m].
$$

不再丢弃这些已计算信息，而是在Krylov子空间中求解

$$
\min_{\boldsymbol\alpha}
\left\|\boldsymbol e+G_e\boldsymbol\alpha\right\|_2^2
+\mu\left\|D\boldsymbol\alpha\right\|_2^2,
\qquad
\Delta\boldsymbol a=D\boldsymbol\alpha.
$$

该步骤直接最小化正式未加权积分，同时仍由完整非线性候选检查真实$K$、根失配、条件数、位移和曲率。12.75°的32维子空间条件数约为`69.0`，预测与实际信赖比约为`0.94`，证明线性子空间稳定；但重新线性化后的边际下降仅`0.162%`，说明下一步必须把端点跳跃分量纳入专用块预条件或改变迹离散，而不能继续重复相同子空间。
## 35. 精确端点平均--跳跃块残差（2026-08-28）

对于面板长度`L`上作线性插值的端点运动学残差`r_0,r_1`，有

```text
integral_panel r(s)^2 ds
  = L/4  * (r_0 + r_1)^2
  + L/12 * (r_0 - r_1)^2.
```

因此定义

```text
e_avg  = sqrt(L/4)  * (r_0 + r_1),
e_jump = sqrt(L/12) * (r_0 - r_1),
q = [DCT(e_avg)[0:n_avg], DCT(e_jump)[0:n_jump]].
```

`e_avg`表示面板平均运动学缺陷，`e_jump`表示同一面板两端离散迹不能由平均值表达的斜率或跳跃缺陷。当前320面板、319个自由形状节点使用`n_avg=287`、`n_jump=32`，方向由截断块`q`生成，但非线性接受、停止和物理门始终使用完整精确积分`K=||e_avg||^2+||e_jump||^2`。

从v824到v826，`K`由`3.481652e-3`降至`3.408829e-3`；平均分量由`2.768491e-3`降至`2.686825e-3`，跳跃分量却由`7.131607e-4`升至`7.220033e-4`。这一区分很重要：连续弱式投影、正式端点平均分量和正式跳跃分量不是同一指标。总量下降不能被误写为跳跃分量下降，也不能据此判定二维物理门通过。

## 36. 跨网格方向映射与细网格独立修正（2026-08-28）

设粗网格冻结Newton方向为法向物理位移`d(s_i)`，粗、细网格节点分别具有归一化弧长坐标

$$
\hat s_i=\frac{\sum_{j<i}\|\boldsymbol x_{j+1}-\boldsymbol x_j\|}
{\sum_j\|\boldsymbol x_{j+1}-\boldsymbol x_j\|}.
$$

跨网格只执行分片线性插值`d_f(\hat s_f)=I[d_c](\hat s_f)`，不按节点数缩放位移幅值。该场仅作为细网格搜索方向；细网格候选仍重新求解边界积分、闭合射流根并以本层完整精确`K`验收。因此它不同于把粗网格残差或解直接当成细网格收敛证据。

12.75°直接重网格时，640到1280面板`K`变化为`11.255%`。定位表明首根面板贡献随加密显著增加，故在1280面板上另取根起前5%弧段的16维余弦基，求解矩形精确残差Gauss--Newton问题。最终

$$
(K_{320},K_{640},K_{1280})=
(9.53012,7.07236,7.40675)\times10^{-4},
$$

最后两级`K`与积分垂向力变化分别为`4.5146%`和`0.03086%`。这证明三网格数值门已闭合，但只是12.75°同伦源资格；不能外推为12.5°桥接、三斜升角压力或整船响应已经验证。

## 37. 12.5°同伦桥接的多尺度形状空间与三网格门（2026-08-29）

12.5°从已通过的12.75°检查点按单步`0.25 deg`同伦获得。320面板推进表明，剩余运动学缺陷会随全局校正重新集中到射流根，单一固定形状空间不足以持续下降。因此按同一正式目标交替使用：

1. 64/128/192模态全局离散余弦基，处理整条自由面的低至中高阶形状误差；
2. 根起前5%、10%和1.25%弧长的局部余弦基，诊断并校正首面板及邻近区域；
3. 冻结Newton方向的连续复用，在每步重新闭合根状态、重算边界积分并检查完整精确`K`；
4. 归一化弧长插值，将粗网格法向物理位移只作为细网格搜索方向。

局部支撑试验说明，残差空间占比高不等于该区域可由任意局部基有效消除。前10%弧长32模态和前1.25%弧长16模态的边际下降分别仅约`0.10%`和`0.45%`；192模态全局方向则同时降低`K`、曲率能量和最大转角，使320面板首次过门。该结果要求形状空间选择同时考虑残差位置、Jacobian可达性和非线性几何约束，不能只按残差热区截断。

最终三网格结果为

$$
(K_{320},K_{640},K_{1280})=
(9.828191,9.757449,9.969301)\times10^{-4}.
$$

根部相对失配分别为

$$
(9.82\times10^{-7},1.11\times10^{-7},1.90\times10^{-8}),
$$

640到1280面板的`K`与积分垂向力变化为`2.1250%`和`0.03969%`。机器门同时检查声明斜升角、三层面板数、有限性、参考隔离、绝对残差、根失配、最后两级变化以及`1e-12`检查点重载。该门通过只证明12.5°是可继续延拓到10°的数值桥接点；由于没有独立物理参考，其压力、自由面和载荷精度仍为`NOT_EVALUATED`。
