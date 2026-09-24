# 下一阶段目标与验收条件：线性 2.5D matched BIE Gate 1

日期：2026-08-02

## 当前进展

当前项目已经完成第一轮“可继续扩展、可测试、边界清楚”的升级：`planing_seakeeping` Python 包、命令行入口、示例配置、验证框架、Ma 2005 Wigley III 对照数据、诊断 CSV 输出、Markdown/HTML/PDF 报告和自动化测试体系均已建立。

当前主线固定为：

```python
LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")
```

当前验证路由固定为：

```python
metadata["provider_route"] == "matched_bie_station_sweep"
```

最新验证输出目录为：

```text
outputs/matched_bie_provider_stokes_end_lever_probe/results
```

最新验证统计为：

| 项目 | 当前状态 |
|---|---|
| 验证统计 | `PASS=65`，`INFO=51`，`NOT_EVALUATED=8`，`FAIL=15` |
| Ma 2005 Wigley III 八个水动力系数 | `B53` 通过；`A33/B33/A35/B35/A53/A55/B55` 未通过 |
| Gate 1 状态 | `PENDING` |
| 当前测试结果 | `python -m pytest -q` 通过，`169 passed` |

已经完成并保留的关键诊断包括：

| 诊断内容 | 当前结论 |
|---|---|
| A/B 符号、整体翻转、Eq.34 长度幂归一化 | 不能让八个系数同时通过，不能作为默认修正 |
| 单一全局比例、逐行/逐列/系数族共享比例 | 最优也只能通过 5/8，只能保留为 diagnostic-only |
| Eq.31 direct-gradient 路径 | 0/8 通过，不能替代默认路径 |
| Eq.32 Stokes body + end 路径 | 0/8 通过，不能替代默认路径 |
| 站位级 forward identity 审计 | 残差沿站位分布，不是单个端部项或单个首站错误 |
| A/B 复幅值截面力导数代理审计 | `pressure-gradient` 与 `U/(-i omega) dF_time/dx` 的差异仍沿站位分布 |
| 自由面 marching 与时间步候选审计 | 关闭 marching 可改善 6/8 行但仍只通过 1/8；`time_step_scale=0.25` 通过 0/8，不能作为默认修正 |
| Eq.30/Eq.32 四分量贡献审计 | `time-pressure` 主导 3/8，`forward-speed pressure-gradient` 主导 5/8；失败源分为 body-potential scale 与 station mapping/gradient 两类 |
| station mapping/gradient 审计 | 4 个 forward-gradient 主导失败全部为 high mapping risk；压力梯度峰值均在 `x/L=0.0375` 附近，峰值处最大相邻体势跳变约 `1.058`、最大水线宽/浸没面积跳变约 `0.487`、最大 `dphi/dx` 增益约 `98.28/L` |
| mapped-gradient 候选排除 | 新增 `mapped_fixed_y_*` 与 `mapped_normalized_y_*` 六个候选；全部为 `0/8` 通过，最好 `mapped_fixed_y_forward` 的最大 gate ratio 仍约 `130.24`，不能作为默认修正 |
| Stokes/end/lever 一致性审计 | heave 行 `m3=0` 为 `4/4` 通过，end-contour 力臂一致性为 `8/8` 通过；但 Eq.31/Eq.32 前进速度恒等式只有 `2/8` 闭合，最大残差约为有效容差的 `146.046` 倍，端部项不是端点 forward-gradient 贡献的简单替代 |
| 闭合性和数值健康 | Eq.30/Eq.32 分量装配残差约 `1e-15` 量级；关键 CSV 无 NaN/Inf |

当前最重要判断是：失败原因不能再简单归结为符号、归一化、端部项加减、单点首站尖峰、自由面时间步粗细、横向插值映射、经验比例、Stokes body 行漏项或端部力臂错位问题。最新四分量贡献审计显示，`A33/A53` 的核心是 Eq.30 time-derivative pressure 所依赖的开放截面 body potential 尺度偏大；`B33/A35/A55/B55` 的核心是 forward-speed pressure-gradient 与 station mapping/纵向导数链；`B35` 属于 time-pressure 与 forward-speed 项混合抵消。新增 station mapping/gradient 审计进一步把前进速度梯度失败定位到相邻站体势和几何映射跳变同位的问题；mapped fixed-y/normalized-y 候选仍不能通过八系数；新增 Stokes/end/lever 审计则说明端部力臂一致但 Eq.31/Eq.32 恒等式未闭合。下一阶段应集中检查 Ma--Duan--Song 线性高速 2.5D matched BIE 的真实公式链，特别是开放截面体势幅值、自由面已知势项进入内域方程的方式、相邻站体势映射、固定物面或固定控制面的纵向导数 `dphi/dx`、端部轮廓方向与整船积分形式。

## 下一阶段唯一目标

在不切换主模型、不引入经验调参、不使用逐系数拟合、不用 reduced-order 补偿替代物理公式的前提下，闭合 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的压力恢复与整船装配链，使默认 `matched_bie_station_sweep` 主线通过 Ma 2005 Wigley III 八个频域水动力系数验收。

更具体地说，下一阶段只解决一个核心问题：

> 找到并修正 Eq.30 压力恢复、Eq.32 前进速度等价项、端部项、广义力坐标、站位纵向导数、整船积分或 Eq.34 无量纲化之间的真实公式/坐标/积分错误，并用 Ma 2005 Wigley III 八系数证明修正后的默认主线是可追溯、可复现、可验证的。

## 必须完成的工作

| 编号 | 工作 | 产物 |
|---|---|---|
| 1 | 核查开放截面 heave/pitch body potential 的量级、相位和边界条件 | body-potential scale 审计 CSV 与结论 |
| 2 | 核查 Eq.30 中 `-rho*i*omega*phi` 和 `rho*U*dphi/dx` 的分量贡献 | time-pressure、pressure-gradient、station contribution 明细 CSV |
| 3 | 核查 Eq.32 中 Stokes body term 与 end-contour term 是否与 Eq.30 梯度项等价 | Eq.31/Eq.32 identity 审计 CSV 与排除/采用说明 |
| 4 | 核查相邻站不同剖面上的面元对应、体势插值和纵向导数计算 | station-to-station mapping 审计表 |
| 5 | 核查 Stokes body row、end-contour row、端部力臂和端点贡献比例 | stokes/end/lever consistency 审计表 |
| 6 | 修正且只修正可由方程、坐标、单位、边界条件或积分定义推出的真实错误 | 代码变更、公式说明、修正前后八系数对照 |
| 7 | 保留所有未采用候选为 diagnostic-only | 候选排除表，说明为什么不能进入默认主线 |
| 8 | 更新验证报告与文档 | Gate 1 状态、失败源或通过证据、剩余风险记录 |

## 硬验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 主线固定 | 必须使用 `linear_2p5d/matched_bie`，不得换成 legacy、reduced-order 或经验模型 | 输出中 `provider_route == matched_bie_station_sweep` |
| 八系数精度 | `A33/B33/A55/B55` 相对误差不超过 15%；`A35/B35/A53/B53` 相对误差不超过 30% | `gate_error_ratio <= 1.0` 且 `status == PASS` |
| 分量闭合 | 最终系数必须等于压力恢复、前进速度项、端部项等分量装配之和 | `current_force_closure_residual_value < 1e-9` |
| 数值健康 | 不允许 NaN、Inf、空矩阵伪通过或未报告的异常条件数 | 自动扫描验证 CSV，矩阵条件数、残差和站位贡献均保留 |
| 可追溯性 | 每个系数都能追溯到参考值、计算值、误差、压力分量、站位贡献、端部项和归一化尺度 | 生成 comparison、pressure balance、station audit、failure audit 等 CSV |
| 非调参 | 不允许逐系数比例、全局经验缩放、强行符号翻转或 reduced-order 补偿进入默认路径 | 所有此类候选必须标注 `diagnostic-only` |
| 回归测试 | 现有配置、求解、验证、诊断输出不回退 | `python -m pytest -q` 全部通过 |
| 文档同步 | 结果、原因、已排除路径和剩余风险必须同步记录 | 更新 `docs` 中 Gate 1 文档 |

固定验收命令：

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\gate1_final_validation\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

固定回归命令：

```powershell
python -m pytest -q
```

## 暂不纳入本阶段硬验收

| 内容 | 原因 |
|---|---|
| SL-7 | 仍缺可机器读取的真实 offsets，可作为趋势或 surrogate 验证，不能作为硬基准 |
| C1 三体船 | 仍缺主片体和侧片体真实 offsets，不能证明 cross-radiation 与 cross-diffraction |
| Delft 372 双体船 | 适合作为 Gate 2 多体船扩展，不替代当前单体 Wigley III Gate 1 |
| Fridsma/Katayama 运动响应 | 适合验证运动趋势和非线性响应，不替代 Ma 2005 水动力系数闭合 |
| Sun--Faltinsen 强非线性 2D+t BEM | 属于后续生产内核，应在线性 2.5D Gate 1 通过后再做硬验收 |
| 水翼控制闭环 | 需要真实水翼、舵机、控制器和试验数据，不能与当前 Gate 1 混合验收 |

## 完成判据

只有当固定验收命令在默认 `matched_bie_station_sweep` 主线下使 Ma 2005 Wigley III 八个系数全部通过，并且 `python -m pytest -q` 全部通过时，下一阶段才算完成。否则 Gate 1 继续保持 `PENDING`，但必须交付可追溯的失败来源、已排除候选和下一阻塞点。
