# 浮筒剖面辐射接入审计

本轮将EDO配平后的浸水剖面接入严格模式剖面辐射求解，保留原始正负号。每个频率装配升沉/纵摇附加质量与阻尼，与原假设模型比较。三档同时加密纵向与剖面离散，检验细两档变化。空白响应表示候选未满足基本数值准入，不是零运动。即使筛查通过，也只属于零航速条带研究；未完成前进速度2.5D、绕射激励或真实飞机验证。

```json
{
  "numerical_screen": "FAIL",
  "physical_validation": "NOT_VALIDATED",
  "enabled_in_default_workflow": false,
  "forward_speed_2p5d": false,
  "experiments_read": false,
  "grid_checks": [
    {
      "period_s": 1.6,
      "matrix": "A",
      "scaled_change": 0.04941442952756529,
      "passed": true
    },
    {
      "period_s": 1.6,
      "matrix": "B",
      "scaled_change": 0.025957838873286617,
      "passed": true
    },
    {
      "period_s": 2.0,
      "matrix": "A",
      "scaled_change": 0.05810332007614666,
      "passed": false
    },
    {
      "period_s": 2.0,
      "matrix": "B",
      "scaled_change": 0.02133522457976652,
      "passed": true
    },
    {
      "period_s": 3.0,
      "matrix": "A",
      "scaled_change": 0.0754518112486485,
      "passed": false
    },
    {
      "period_s": 3.0,
      "matrix": "B",
      "scaled_change": 0.021670026921589643,
      "passed": true
    },
    {
      "period_s": 5.0,
      "matrix": "A",
      "scaled_change": 0.10149150498047875,
      "passed": false
    },
    {
      "period_s": 5.0,
      "matrix": "B",
      "scaled_change": 0.0874625880925899,
      "passed": false
    },
    {
      "period_s": 8.0,
      "matrix": "A",
      "scaled_change": 0.09852357177158158,
      "passed": false
    },
    {
      "period_s": 8.0,
      "matrix": "B",
      "scaled_change": 0.2026998446534141,
      "passed": false
    }
  ],
  "negative_section_damping_occurrences": 1133,
  "notes": [
    "No sign flipping, coefficient clipping or least-squares fallback in strict mode.",
    "The kernel still averages two near/far panel split choices; independent reference validation remains pending.",
    "Response candidate is withheld when effective mass, damping or solve diagnostics fail.",
    "Hydrostatic excitation has NOT been replaced by a diffraction solution."
  ]
}
```
