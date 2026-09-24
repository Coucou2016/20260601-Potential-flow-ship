# 下一阶段目标、验收条件与需精确转换 Markdown 的资料清单

日期：2026-07-29

## 1. 需要优先转换为高精度 Markdown 的文件

转换要求：公式必须保留为 LaTeX，表格必须转成 Markdown 表或 CSV 友好表格，图号、页码、坐标轴、单位、无量纲化方式必须保留；凡是图中曲线数据无法直接成表，应至少保留清晰图像编号、坐标轴范围和曲线图例，后续再数字化。

### 第一优先级：直接决定完整 2.5D 是否可验收

1. `A1_An efficient numerical method for solving ‘2.5D’ ship seakeeping problem.pdf`
   - 目的：Ma-Duan-Song 型线性高速 2.5D 内外域匹配、自由面 marching、压力积分、Wigley III / SL-7 系数验证。
   - 必须准确保留：式 (1) 到式 (28) 左右的控制方程、边界条件、匹配积分方程、压力公式、A/B 系数组装、无量纲规则、Table 1、Table 2、Wigley III 与 SL-7 所有 coefficient figures。

2. `C1_Verification of application of the 2.5D method in high-speed trimaran vertical motion and added resistance prediction.pdf`
   - 目的：三体船主片体和侧片体干扰、四布局、heave/pitch、added resistance 验证。
   - 必须准确保留：主尺度表、主片体/侧片体体线图、四种布局参数、式 (1) 到式 (6) 的耦合 2.5D 方程、增阻五项分解、Fn=0.353 和 Fn=0.471 的所有对比曲线。

3. `B2_Experimental Results of Motions and Structural Loads on the 372 Catamaran Model in Head and Oblique Waves.pdf`
   - 目的：Delft 372 真实双体船几何、斜浪 6DOF、连接载荷。
   - 必须准确保留：第 14 页 offsets 表、第 15 页型线图、质量惯性、KG、LCG、航向 180/195/225 deg、连接载荷六分量换算公式、所有 6DOF 和连接载荷 benchmark 图表。

4. `B1_Experimental Results of Motions, Hydrodynamic Coefficients and Wave Loads on the 372 Catamaran Model.pdf`
   - 目的：Delft 372 迎浪运动、水动力系数、波浪载荷。
   - 必须准确保留：迎浪 RAO、强迫升沉/纵摇水动力系数、restrained wave forces、Fn=0.30/0.45/0.60/0.75 对应测试矩阵。

### 第二优先级：决定非线性 2D+t 与滑行艇波浪验证

5. `A3_A Boundary Element Method.pdf`
   - 目的：Sun 博士论文中的强非线性二维自由面 BEM。
   - 必须准确保留：势函数 BVP、压力辅助函数 BVP、Wagner/von Karman 初始化、jet cut、spray cut、重网格、分离、数值消波、验证算例。

6. `A4_1_The influence of gravity on the performance of planing vessels in calm water.pdf`
   - 目的：含重力稳态滑行、喷溅根、硬折角分离、艉部三维修正。

7. `A4_2_Numerical study of planing vessels in waves.pdf`
   - 目的：波浪中移动地固横剖面、前部近似力、波浪 2D+t 实施细节。

8. `A4_3_Dynamic motions of planing vessels in head seas.pdf`
   - 目的：动态升沉/纵摇、Fridsma 对比、艉部修正和数值稳定。

9. `A5_Fridsma_1969_Rough_Water_Performance_Planing_Boats.pdf`
   - 目的：规则波 heave、pitch、CG/艏部加速度和增阻验证。

10. `A6_Fridsma_1971_Irregular_Waves_Part_II.pdf`
    - 目的：PM 不规则波、超越概率、峰值和非高斯统计。

11. `A7_LONGITUDINAL MOTION OF A SUPER HIGH-SPEED PLANING CRAFT IN REGULAR HEAD WAVES.pdf`
    - 目的：Katayama 无跳跃、规则跳跃、不规则跳跃和波高相关峰值移动。

### 第三优先级：水翼与试验规程

12. `B3_A design of T-foil and trim tab for fast catamaran based on NSGA-II.pdf`
    - 目的：T 型翼和艉压浪板线性系数、稳定性、控制量影响。

13. `D1_Montero_Minerva_2020_Foiling_Crafts.pdf`
    - 目的：水翼船验证阶梯、控制器敏感性、模型试验要求。

14. `D2_ITTC_HSMV_Seakeeping_Tests_2024.pdf`
    - 目的：高速船非线性随机波试验程序、不确定度、最少遭遇波数量、传感器要求。

## 2. SL-7 与 C1 三体船几何可行性判断

### SL-7

当前结论：没有找到可直接用于程序验证的机器可读真实 station offsets。

可用信息：

- A1 中有 SL-7 主尺度、验证曲线和型线/体线图信息。
- 本地代码已有 `make_sl7_surrogate_hull`，可做数值流程和趋势诊断。
- 公开网络检索可以找到 SL-7 相关论文、SL-7 体线图或软件示例痕迹，但未发现可直接下载的 offsets 表。

验收态度：

- SL-7 surrogate 不能用于通过 Ma 2005 SL-7 geometry gate。
- 若没有真实 offsets，SL-7 只能作为“趋势和数值稳定诊断”。
- 真正验收必须满足：真实 offsets 文件、来源页码或数据来源、坐标/水线/单位审计、几何水静力复核。

可替代对象：

- Wigley III：解析船型，适合先验收 Ma 型 2.5D 的核心水动力系数。
- 潜没椭球：适合验证 Ma 型内外域匹配和自由面历史项的基础正确性。
- Delft 372：有真实 offsets 表，适合作为双体船几何和 6DOF benchmark。

### C1 三体船

当前结论：没有找到可直接用于程序验证的主片体和侧片体机器可读 offsets。

可用信息：

- C1 论文提供主尺度、主/侧片体布局、四种布局参数、速度点、运动和增阻曲线。
- 文中核心是主片体与侧片体水动力干扰，不能用三个独立片体简单相加替代。
- 当前代码提供 `make_trimaran2019_surrogate`，只适合流程 smoke test 和多体 API 开发。

验收态度：

- C1 surrogate 不能作为 C1 验证几何。
- 如无真实 offsets，C1 不能作为硬验收 benchmark。
- 真正验收必须满足：主片体 offsets、侧片体 offsets、纵向错位 a/L、横向间距 p/L、四布局输入文件、heave/pitch/added-resistance 数字化曲线。

可替代对象：

- Delft 372 双体船：真实 offsets 可重建，适合先完成多体共同边界积分、cross-radiation/cross-diffraction 的第一阶段验证。
- 解析三体 surrogate：用 Wigley/NPL/S60 类解析片体组合，只能做算法自洽、收敛性和干扰项趋势检查，不能替代 C1 论文验证。

## 3. 下一阶段具体目标

### 总目标

把当前“可扩展、可测试、边界清楚”的第一轮架构，推进到“一个可被文献数据逐项验收的最小完整模型”。

更具体地说：下一阶段不追求一次性完成全部高速船、水翼船和多体船，而是优先打通三个硬链条：

1. Ma-Duan-Song 线性 2.5D：从 station geometry 到频率相关 A/B 矩阵。
2. Delft 372 多体几何：从真实 offsets 到双体船 6DOF benchmark 输入。
3. Sun-Faltinsen 2D+t 最小闭环：从二维入水 BEM 到 Fridsma/Katayama 前的基础验证。

## 4. 下一阶段必须满足的验收条件

### Gate 1：资料与数据条件

必须具备：

1. A1、B1、B2、C1 的高精度 Markdown。
2. Delft 372 第 14 页 offsets 的机器可读 CSV。
3. Wigley III、Delft 372、Fridsma、Katayama 的 benchmark 曲线数字化数据。
4. 每份数据必须有来源页码、图号、单位、坐标轴、无量纲化说明。
5. SL-7 和 C1 若无真实 offsets，必须继续标为 `SURROGATE_NOT_FOR_VALIDATION`。

### Gate 2：线性 2.5D 内核条件

必须实现：

1. `Matched2p5DSectionSolver` 不再是 placeholder。
2. 内域简单 Green 函数边界积分可解。
3. 外域瞬态自由面 Green 函数和历史卷积可解。
4. 内外控制面势/法向导数匹配矩阵可解。
5. 自由面 marching 在站位推进中稳定。
6. 压力、前进速度梯度项和端部项进入整船装配。
7. 输出频率相关 `A(omega)`、`B(omega)`、`F_wave(omega)`。

验收门槛：

- Wigley III 对角项误差不超过 15%。
- Wigley III 耦合项误差不超过 30%。
- 潜没椭球基础算例收敛趋势正确。
- SL-7 只有在真实 offsets 接入后才参与硬验收。

### Gate 3：Delft 372 双体船条件

必须实现：

1. `delft372_demihull_offsets.csv` 通过几何审计。
2. 左右片体按中心距 0.70 m 装配。
3. 同一横剖面内同时求解两个片体边界，而不是只做独立片体相加。
4. cross-radiation 和 cross-diffraction 至少在频域矩阵中可见。
5. B1 迎浪 heave/pitch RAO 可复现。
6. B2 斜浪 6DOF 和连接载荷完成数据接口。

验收门槛：

- 几何水静力误差不超过 2% 到 5%。
- 主要迎浪 RAO 峰值位置误差不超过 10%。
- 主要 RAO 幅值误差不超过 15% 到 20%。
- 连接载荷先完成单位和符号闭合，再进入幅值验收。

### Gate 4：非线性 2D+t 最小闭环条件

必须实现：

1. 二维势函数 BVP。
2. 压力辅助函数 BVP。
3. Wagner 或 von Karman 初始化。
4. jet cut 和 spray cut。
5. 自由面平滑和重网格。
6. 地固横剖面创建、删除和状态继承。
7. 二维入水基础算例通过后，再接滑行艇波浪。

验收门槛：

- 楔形恒速入水压力/力趋势正确。
- V 型柱自由落水能稳定积分。
- Fridsma 规则波 heave/pitch 幅值误差目标不超过 25%。
- CG/艏部加速度误差目标不超过 35%。
- Katayama 跳跃分类正确。

### Gate 5：代码工程条件

必须满足：

1. 所有 provider 都必须声明 `ModelCapabilities`。
2. 所有输出都必须附 `ValidityReport`。
3. placeholder 或 surrogate 不能在 `production=true` 下运行。
4. 验证失败不能被隐藏，必须输出 FAIL/PENDING/NOT_EVALUATED。
5. 全量测试必须通过。
6. 新增 benchmark 必须能一条命令复现。

## 5. 下一步执行顺序

1. 先转换 A1、B2、B1、C1。
2. 用 B2 生成 Delft 372 offsets CSV 和几何审计。
3. 用 A1 完成 Ma-Duan-Song 线性 2.5D 第一版真实 section solver。
4. 用 Wigley III 作为第一个硬验收，不先纠缠 SL-7。
5. 用 Delft 372 作为第一个真实多体几何验收。
6. 再转换 A3/A4/A5/A6/A7，推进 Sun-Faltinsen 2D+t 和滑行艇粗水验证。
## 2026-07-30 更新：已收到并处理的 Markdown 资料

用户已提供 A1、A3、A4_1、A4_2、A4_3、A5、A6、A7、B1、B2、B3、C1、D1、D2 共 14 份高精度 Markdown。
本轮优先使用 B2，因为它包含可以直接转成计算几何的 Delft 372 第 14 页 offsets 表。

### 已完成的硬成果

| 项目 | 结果 |
|---|---|
| B2 Delft 372 offsets | 已生成 `benchmarks/delft372/delft372_demihull_offsets.csv` |
| 原始表格追溯 | 已生成 `benchmarks/delft372/delft372_demihull_offsets_raw.csv` |
| 几何审计 | 已生成 `benchmarks/delft372/delft372_demihull_geometry_audit.csv` |
| 示例配置 | 已生成 `configs/delft372_demihull_offsets.yml` |
| 静水复核 | 两片体排水质量 `86.219 kg`，对 B2 报告 `87.07 kg` 误差约 `0.98%` |

### 当前判断

1. Delft 372：已经具备真实几何输入，可进入多体 2.5D 几何级和静水级验收；运动响应验收仍需 B1/B2 曲线数字化。
2. SL-7：仍未获得可直接验证的真实 machine-readable offsets；现有 `make_sl7_surrogate_hull` 只能做算法流程、趋势和稳定性 smoke test。
3. C1 三体船：C1 Markdown 提供主尺度、布局、速度点、运动和增阻曲线，但未提供主片体和侧片体的 machine-readable offsets；当前 surrogate 不能作为 C1 论文级验收几何。

### 下一步具体验收目标

| Gate | 必须完成的条件 | 验收口径 |
|---|---|---|
| Gate 1：A1 线性 2.5D | `Matched2p5DSectionSolver` 从 placeholder 变为可计算内外域匹配、自由面 marching、压力积分和端部项 | Wigley III 对角水动力系数误差目标 ≤15%，耦合项误差目标 ≤30% |
| Gate 2：Delft 372 多体几何 | 左右片体按中心距 `0.70 m` 装配，同一横剖面内共同求解边界积分 | 几何静水误差 ≤2%，多体 cross-radiation/cross-diffraction 在矩阵中显式可见 |
| Gate 3：B1/B2 曲线数字化 | heave、pitch、主要 6DOF、连接载荷曲线转成 CSV，并记录图号、坐标轴和单位 | 每条 benchmark 曲线可一条命令复现实验-计算对照图 |
| Gate 4：C1 三体船 | 若拿不到真实 offsets，则改用解析三体 surrogate，仅用于干扰项趋势验证 | C1 不能作为硬验收；只允许标记 `SURROGATE_NOT_FOR_VALIDATION` |
| Gate 5：2D+t 最小闭环 | 先完成二维楔形入水势函数与压力辅助函数边界元，再接移动剖面管理器 | Wagner/von Karman 趋势正确后，再进入 Fridsma/Katayama |
