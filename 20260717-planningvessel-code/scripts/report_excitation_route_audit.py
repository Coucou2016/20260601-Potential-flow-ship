"""Compare preserved excitation candidates without changing physical parameters."""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(baseline, candidate, audit, destination):
    baseline, candidate, audit, destination = map(Path, (baseline, candidate, audit, destination))
    destination.mkdir(parents=True, exist_ok=False)
    manifest, rows = {}, []
    for case in ("fn167", "fn226", "fn282"):
        old_path, new_path = baseline / case / "matrices.csv", candidate / case / "matrices.csv"
        old, new = pd.read_csv(old_path), pd.read_csv(new_path)
        np.testing.assert_allclose(old[["frequency_index", "omega_e_rad_s", "i", "j"]],
                                   new[["frequency_index", "omega_e_rad_s", "i", "j"]], rtol=1e-12)
        delta = float(np.max(np.abs(old[["M", "A", "B", "C"]].to_numpy()
                                    - new[["M", "A", "B", "C"]].to_numpy())))
        # Only attribute changed responses to excitation when all operator entries agree.
        if delta > 1e-10:
            raise ValueError(f"{case}: dynamic matrices differ; excitation-only attribution is invalid")
        f_old_path, f_new_path = baseline / case / "excitation.csv", candidate / case / "excitation.csv"
        f_old, f_new = pd.read_csv(f_old_path), pd.read_csv(f_new_path)
        np.testing.assert_allclose(f_old.omega_e_rad_s, f_new.omega_e_rad_s, rtol=1e-12)
        for mode in ("F3", "M5"):
            a = f_old[mode + "_real"].to_numpy() + 1j * f_old[mode + "_imag"].to_numpy()
            b = f_new[mode + "_real"].to_numpy() + 1j * f_new[mode + "_imag"].to_numpy()
            for omega, left, right in zip(f_new.omega_e_rad_s, a, b):
                rows.append(dict(case=case, mode=mode, omega_e_rad_s=omega,
                                 baseline_abs=abs(left), candidate_abs=abs(right),
                                 amplitude_ratio=abs(right) / abs(left) if abs(left) > 1e-12 else None,
                                 phase_change_deg=np.angle(right / left, deg=True) if abs(left) > 1e-12 else None,
                                 max_matrix_absolute_difference=delta))
        for path in (old_path, new_path, f_old_path, f_new_path):
            manifest[str(path.resolve())] = digest(path)
    diagnostic = pd.DataFrame(rows)
    diagnostic.to_csv(destination / "excitation_route_differences.csv", index=False)
    old_metrics = pd.read_csv(baseline / "evaluation/per_speed_metrics.csv")
    metrics = pd.read_csv(candidate / "evaluation/per_speed_metrics.csv")
    merged = old_metrics.merge(metrics, on=["scope", "metric"], suffixes=("_old", "_new"), validate="one_to_one")
    merged.to_csv(destination / "paired_metrics.csv", index=False)
    incident = json.loads((audit / "results.json").read_text(encoding="utf-8"))
    image_path = candidate / "evaluation/motion_comparison.png"
    for path in (baseline / "evaluation/per_speed_metrics.csv", candidate / "evaluation/per_speed_metrics.csv",
                 audit / "results.json", image_path, Path(__file__)):
        manifest[str(path.resolve())] = digest(path)
    (destination / "source_hashes.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    table_rows = []
    for _, r in merged.iterrows():
        motion = "升沉" if r.metric == "heave_motion" else "纵摇"
        table_rows.append(f"<tr><td>{html.escape(r.scope)}</td><td>{motion}</td>"
                          f"<td>{r.median_relative_error_old:.2%} / {r.nrmse_old:.2%}</td>"
                          f"<td>{r.median_relative_error_new:.2%} / {r.nrmse_new:.2%}</td>"
                          f"<td>{r.status_new}</td></tr>")
    amp = max(r["amplitude_error"] for r in incident["rows"])
    phase = max(r["phase_error_deg"] for r in incident["rows"])
    notes = [
        "(a) 最低航速升沉：计算曲线在约5米波长附近达到约2.4，而实验约为1。当前模型明显放大该频段响应；这不是误差条能够解释的差异。这里只能定位到整船频率响应异常，尚不能断言是某一阻尼项单独导致。",
        "(b) 中间航速升沉：计算点与实验多数接近，最长波附近仍偏低。该速度的升沉通过既定幅值指标，但不能据此宣称同速度纵摇或其他航速通过。",
        "(c) 最高航速升沉：计算曲线在较长波处约为0.6，实验约为1.2至1.3，表现为系统性低估。低速高估、高速低估说明不能用一个统一响应倍率来修正。",
        "(d) 最低航速纵摇：计算在约5米波长处出现接近3.9的离散峰值，实验约为1.1。偏差比同速度升沉更突出，后续需共同检查升沉与纵摇耦合及两个复数激励分量，而非仅查看单个力的绝对值。",
        "(e) 中间航速纵摇：短波段较接近，长波段计算持续上升，实验趋于平台。因此即使该速度升沉通过，纵摇的频率分布仍不正确。",
        "(f) 最高航速纵摇：计算随波长增加，但总体偏低，且没有在采样区间内复现实验的明显峰值。仅八个离散频率不能完成主峰频率验收，仍需独立的密集扫频。",
    ]
    content = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>规则迎浪直接激励核验与三航速回归</title><style>
body{{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;color:#202b32;background:#fff;margin:0;line-height:1.8}}
main{{max-width:1120px;margin:auto;padding:40px 24px}}h1{{font-size:28px}}h2{{font-size:21px;border-bottom:1px solid #ccd7db;padding-top:24px}}
img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border:1px solid #ccd7db;padding:10px;text-align:left}}th{{background:#edf3f4}}
.status{{border-left:5px solid #bd4932;padding:12px 18px;background:#faf2ef}}code{{overflow-wrap:anywhere}}p{{margin:12px 0}}.table{{overflow-x:auto}}
@media print{{main{{padding:0}}h2{{break-after:avoid}}tr{{break-inside:avoid}}}}
</style></head><body><main><h1>规则迎浪直接激励核验与三航速回归</h1>
<p>研究记录 · 2026-09-21 · 单体高速艇线性预测闭环</p>
<p class="status">阶段结论：未通过。程序可运行、入射载荷解析核验通过，但三航速六项运动指标仅一项通过；不得作为已验证生产模型。</p>
<h2>1. 目的与方法</h2><p>本轮不改变实验误差门槛，不用实验响应标定参数。先以规则V形棱柱的独立压力积分核查入射波载荷，再显式接入内外域匹配求解的入射及绕射激励，使用冻结的三航速24工况计算，最后由独立评估程序读取实验响应。21个适用点用于指标，3个预先标记的诊断点仍保留绘图。</p>
<p>入射载荷是未受船体扰动的波浪压力在湿表面的积分；绕射载荷则来自船体改变波浪后的附加压力。验证前者不等于验证后者。运动方程为 (−ω²(M+A)+iωB+C)q=F，其中ω为遭遇角频率，M为质量惯性，A为附加质量，B为辐射阻尼，C为恢复力系数，q为复数运动幅值，F为复数波浪激励。复数同时保存振幅和相位，两个自由度通过矩阵非对角项耦合。</p>
<h2>2. 修正依据与局部验证</h2><p>直接激励接口原来未完成“压力法向投影转船体受力”和“余弦波参考转正弦波参考”两步转换。两者的因子分别为−1及−i，合并为+i。这是符号约定适配，不是试验拟合。独立棱柱积分的12项检查全部通过，最大幅值相对误差为{amp:.4%}，最大相位误差为{phase:.4f}°；该结论仅覆盖此次入射压力、相位及长波测试。</p>
<h2>3. 实验对照</h2><p>表1比较原等效辐射激励与新直接激励。每格依次为相对误差中位数和归一化均方根误差；门槛分别为15%和20%，两项都满足才通过。原路线结果保留，不以新候选替换历史验收。</p>
<div class="table"><table><caption>表1　三航速逐运动误差对照</caption><thead><tr><th>工况</th><th>运动</th><th>原路线</th><th>直接激励</th><th>新候选状态</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>
<figure><img alt="三航速升沉纵摇计算与实验对照" src="data:image/png;base64,{base64.b64encode(image_path.read_bytes()).decode()}"><figcaption>图1　三航速运动幅值对照。上排为升沉，下排为纵摇；从左到右对应船宽弗劳德数1.67、2.26、2.82（航速除以重力加速度与船宽乘积的平方根）。</figcaption></figure>
<p>横轴是波长，越往右波越长；上排纵轴是升沉幅值除以波幅，下排是纵摇角幅值除以波面斜率幅值。蓝色圆点及连线表示计算，橙色三角表示实验数字化数据。误差条为数字化界限，不是实验置信区间。各子图纵轴刻度不同，不应只凭曲线视觉高度比较运动强弱；连线仅连接离散点，不是新求解的中间频率。</p>
{''.join('<p>'+n+'</p>' for n in notes)}
<h2>4. 分量诊断与边界</h2><p>逐元素检查确认两次运行所有工况的质量、附加质量、阻尼和恢复力矩阵差异不超过10⁻¹⁰。因此本次两路线之间的响应变化可定位到激励侧；这不证明这些共同使用的矩阵本身已经物理正确。48行逐频率、逐分量的激励幅相差异已输出供继续定位。</p>
<p>本轮全套回归为792项测试及11项子测试通过，存在1247条既有空切片均值警告。测试通过不能替代物理验证。三速度同核时频检查均通过，但采用单频冻结矩阵和精确稳态初值，不是含完整历史记忆的自由起振验证。船体是参数化平均湿表面，不是完整实测船壳；平均姿态为输入，不是自动平衡预测。六自由度中仅求解升沉、纵摇，其余为速度或对称约束。</p>
<h2>5. 下一步验收顺序</h2><ol><li>首先独立核查绕射载荷的边界条件、压力符号、前进速度项和艉部积分，不按实验幅值调倍率。</li><li>对交付频段的八个水动力系数及两个复数激励做三档离散，细两档关键量变化不超过5%；近零量使用求解前冻结的绝对容差。</li><li>在固定三速度数据上重新检验升沉、纵摇15%/20%指标，完成至少四个可解析主峰的10%频率指标，不以合并平均掩盖失败。</li><li>补齐Fridsma相位与加速度、频率相关稳定性及独立复核工况；全部完成后才允许阶段通过。</li></ol>
<p>本轮未交付多体干扰、水翼控制或水上飞机起降验证，入射载荷检查也不能代替这些模块。实验数据已参与历史诊断，属于回归集而非盲测集。</p>
<h2>6. 可追溯记录</h2><p>本页所有图片和表格均内嵌，无外部资源依赖。源文件路径及SHA-256摘要如下，便于与案例包核对。</p><details><summary>展开源文件摘要</summary><pre>{html.escape(json.dumps(manifest, indent=2))}</pre></details>
</main></body></html>"""
    (destination / "report.html").write_text(content, encoding="utf-8")
    print(destination / "report.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build(args.baseline, args.candidate, args.audit, args.out)
