# Delft 372 Catamaran Geometry Benchmark

日期：2026-07-30

## 数据来源

本目录保存从 `B2.md` 中 `TABLE OF OFFSETS` 提取的 Delft 372 双体船单片体几何。

原始 Markdown：

`D:/Projects/20260601-Potential-flow-ship/20260729-文献收集/md/B2.md`

对应 PDF：

`D:/Projects/20260601-Potential-flow-ship/20260729-文献收集/B2_Experimental Results of Motions and Structural Loads on the 372 Catamaran Model in Head and Oblique Waves.pdf`

## 文件说明

| 文件 | 用途 |
|---|---|
| `delft372_demihull_offsets.csv` | 可直接由 `load_station_offsets_csv` 读取的单片体湿剖面 offsets |
| `delft372_demihull_offsets_raw.csv` | 从 B2 表格提取的原始 `z/y` 表坐标 |
| `delft372_demihull_geometry_audit.csv` | 每个站位的水线半宽、吃水、剖面积和审计状态 |

## 坐标约定

B2 表格坐标按 0.1 m 缩放。程序采用如下换算：

```text
x_from_ap_m = (x_table + 15.0) * 0.1
y_m         = y_table * 0.1
z_down_m    = (1.5 - z_table) * 0.1
```

其中 `z_table = 1.5` 被视为设计水线，`x_table=-15` 对应 aft perpendicular，单片体长度取 `3.0 m`。表中最后一列 `x=bow` 是艏轮廓线，不是普通横剖面，未混入 offsets CSV。

## 几何复核

使用当前 `StationHull.hydrostatics()` 对 23 个站位积分，得到：

| 指标 | 当前积分值 | B2 报告值或预期 | 说明 |
|---|---:|---:|---|
| 单片体排水体积 | 0.043109 m^3 | 0.043535 m^3 | B2 总排水质量 87.07 kg、淡水密度 1000 kg/m^3 的一半 |
| 两片体总排水质量 | 86.219 kg | 87.070 kg | 相对误差约 0.98%，满足几何门槛 |
| 单片体浮心纵向位置 | 1.416 m | 1.410 m | 与报告 LCG 接近 |
| 两片体总水线面积 | 1.087 m^2 | 待补充 | 需要报告水线面积或人工复核 |

## 验证边界

该数据已经可以作为 Delft 372 的几何级验证输入。它还不能单独证明运动预报模型正确，后续仍需要：

1. 从 B1/B2 数字化 heave、pitch、横摇、横荡、艏摇、连接载荷等 benchmark 曲线。
2. 在多体 2.5D 求解器中实现同一横剖面内两片体共同边界积分，而不是简单独立片体相加。
3. 明确 Delft 与 MARIN 两套试验的 `KG`、转动惯量和航速/波长矩阵。

## 程序入口

单片体几何入口：

```python
from planing_seakeeping.geometry import make_delft372_demihull_from_offsets

component = make_delft372_demihull_from_offsets("benchmarks/delft372/delft372_demihull_offsets.csv")
```

整双体船组件入口：

```python
from planing_seakeeping.geometry import make_delft372_catamaran_from_offsets

components = make_delft372_catamaran_from_offsets("benchmarks/delft372/delft372_demihull_offsets.csv")
```

该双体船入口按 B2 主尺度中的片体中心距 `0.70 m` 装配左右片体，返回 `port_demihull` 和
`starboard_demihull` 两个 `HullComponent`。它通过的是几何/拓扑门槛，不代表多体水动力耦合已经完成。
