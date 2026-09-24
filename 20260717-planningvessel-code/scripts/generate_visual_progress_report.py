from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
GATE1_DIR = ROOT / "outputs" / "audit_20260831_gate1_current_source"
GATE2_DIR = ROOT / "outputs" / "audit_20260831_gate2_current_source"
GATE2_CANDIDATE_DIR = ROOT / "outputs" / "gate2_frequency_candidate_v2_20260913" / "aggregate"
DELFT372_DIR = ROOT / "outputs" / "delft372_full_mesh_20260913"
WEDGE_VALIDATION_DIR = ROOT / "outputs" / "wedge_entry_public_validation_20260913"
WEDGE_DIR = (
    ROOT
    / "outputs"
    / "self_similar_wedge_12p375deg_n320_globaldct16_syncmap_relinearized_v949"
)
WEDGE_CASE_DIRS = {
    "12.75": (
        ROOT
        / "outputs"
        / "self_similar_wedge_12p75deg_n1280_rootcos16_direction_reuse2_v844"
    ),
    "12.5": (
        ROOT
        / "outputs"
        / "self_similar_wedge_12p5deg_n1280_mapped_v872_direction_reuse_pass_v882"
    ),
    "12.375": WEDGE_DIR,
}
OUT_DIR = ROOT / "outputs" / "visual_progress_report_20260913"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def numeric_rows(path: Path, columns: list[str]) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for source in read_csv(path):
        row: dict[str, float] = {}
        for column in columns:
            value = source[column]
            if value.lower() in {"true", "false"}:
                row[column] = value.lower() == "true"  # type: ignore[assignment]
            else:
                row[column] = round(float(value), 10)
        rows.append(row)
    return rows


def text_rows(path: Path, columns: list[str]) -> list[dict[str, str]]:
    return [{column: row[column] for column in columns} for row in read_csv(path)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_data_url(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def html_table(headers: list[str], rows: list[list[str]], note: str = "") -> str:
    head = "".join(f"<th>{item}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{item}</td>" for item in row) + "</tr>"
        for row in rows
    )
    note_html = f'<p class="table-note">{note}</p>' if note else ""
    return f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{note_html}'


def wedge_case_payload(directory: Path) -> dict[str, object]:
    checkpoint_path = directory / "coupled_checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    config = checkpoint["config"]
    nodes = numeric_rows(
        directory / "coupled_boundary_nodes.csv", ["xi", "eta", "node_index"]
    )
    counts = [
        ("outer_free_surface", int(config["free_surface_panels"])),
        ("far_field", int(config["far_field_panels"])),
        ("symmetry", int(config["symmetry_panels"])),
        ("wetted_wedge", int(config["body_panels"])),
        ("shallow_jet_body", int(config["coupled_jet_bie_panel_count"])),
        ("shallow_jet_free_surface", int(config["coupled_jet_bie_panel_count"])),
    ]
    segments: list[dict[str, object]] = []
    start = 0
    for name, panel_count in counts:
        segments.append(
            {
                "name": name,
                "start_node": start,
                "end_node": start + panel_count,
                "panel_count": panel_count,
            }
        )
        start += panel_count
    if start != len(nodes) - 1:
        raise ValueError(
            f"Wedge boundary segmentation mismatch in {directory}: "
            f"{start} panels for {len(nodes) - 1} node intervals."
        )
    closure_error = math.hypot(
        nodes[-1]["xi"] - nodes[0]["xi"],
        nodes[-1]["eta"] - nodes[0]["eta"],
    )
    expected = checkpoint.get("expected_state", {})
    return {
        "angle_deg": float(config["deadrise_deg"]),
        "nodes": nodes,
        "segments": segments,
        "node_count": len(nodes),
        "panel_count": len(nodes) - 1,
        "closure_error": closure_error,
        "kinematic_integral": expected.get("kinematic_integral_linear_exact"),
        "status": checkpoint["status"],
        "source": directory.relative_to(ROOT).as_posix(),
    }


def motion_case_payload(response: list[dict[str, float]]) -> dict[str, object]:
    from planing_seakeeping.config import BoatConfig, PrescribedRunningStateConfig
    from planing_seakeeping.equilibrium import make_prescribed_equilibrium

    boat = BoatConfig(
        length_m=6.5,
        beam_m=1.0,
        deadrise_deg=20.0,
        mass_kg=1.28 * 1025.0,
        lcg_m=2.13,
        vcg_m=0.25,
        pitch_radius_gyration_m=1.3,
        rho_water_kg_m3=1025.0,
        gravity_m_s2=9.80665,
        wetted_lengths_type=1,
    )
    prescribed = PrescribedRunningStateConfig(
        enabled=True, trim_deg=4.0, lambda_w=4.0
    )
    speed = 3.0 * math.sqrt(boat.gravity_m_s2 * boat.beam_m)
    equilibrium = make_prescribed_equilibrium(boat, speed, prescribed)
    frequency_row = next(
        row
        for row in response
        if row["fn_b"] == 3.0 and row["lambda_over_l"] == 6.0
    )
    geometry = equilibrium.geometry
    return {
        "length_m": boat.length_m,
        "beam_m": boat.beam_m,
        "deadrise_deg": boat.deadrise_deg,
        "mass_kg": boat.mass_kg,
        "lcg_from_transom_m": boat.lcg_m,
        "trim_deg": equilibrium.trim_deg,
        "fn_b": equilibrium.fn_b,
        "speed_mps": equilibrium.speed_mps,
        "wave_amplitude_m": 0.01,
        "wavelength_m": frequency_row["wavelength_m"],
        "wavenumber_rad_m": frequency_row["wavenumber_rad_m"],
        "omega_e_rad_s": frequency_row["omega_e_rad_s"],
        "keel_wetted_length_m": geometry.keel_wetted_length_m,
        "chine_wetted_length_m": geometry.chine_wetted_length_m,
        "side_chine_wetted_length_m": geometry.side_chine_wetted_length_m,
        "mean_wetted_length_over_b": geometry.lambda_w,
        "transom_draft_m": geometry.transom_draft_m,
        "running_state_source": "prescribed_trim_and_mean_wetted_length",
        "calm_water_equilibrium_converged": equilibrium.converged,
        "calm_water_residual": list(equilibrium.residual),
    }


def build_payload() -> dict[str, object]:
    response_columns = [
        "omega0_rad_s",
        "omega_e_rad_s",
        "wavenumber_rad_m",
        "wavelength_m",
        "heave_rao_m_per_m",
        "pitch_rao_rad_per_m",
        "pitch_rao_rad_per_wave_slope",
        "cg_accel_g",
        "point_accel_g",
        "fn_b",
        "speed_mps",
        "lambda_over_l",
    ]
    time_columns = [
        "time_s",
        "wave_elevation_m",
        "heave_m",
        "pitch_rad",
        "heave_velocity_mps",
        "pitch_rate_rad_s",
        "heave_accel_mps2",
        "pitch_accel_rad_s2",
        "point_vertical_m",
        "point_vertical_accel_mps2",
        "fn_b",
        "lambda_over_l",
    ]
    begovic_columns = [
        "fn_b",
        "lambda_over_l",
        "reference_heave_rao_m_per_m",
        "heave_rao_m_per_m",
        "reference_pitch_rao_rad_per_wave_slope",
        "pitch_rao_rad_per_wave_slope",
        "wave_steepness_ka",
        "linear_gate_eligible",
    ]
    fridsma_columns = [
        "configuration",
        "lambda_over_l",
        "reference_heave_rao_m_per_m",
        "heave_rao_m_per_m",
        "reference_pitch_rao_rad_per_wave_slope",
        "pitch_rao_rad_per_wave_slope",
        "linear_gate_eligible",
    ]
    response = numeric_rows(
        GATE2_DIR / "three_speed_frequency_response.csv", response_columns
    )
    delft_audit = json.loads(
        (DELFT372_DIR / "delft372_catamaran_mesh_audit.json").read_text(encoding="utf-8")
    )
    delft_manifest = json.loads((DELFT372_DIR / "manifest.json").read_text(encoding="utf-8"))
    wedge_validation = json.loads(
        (WEDGE_VALIDATION_DIR / "wedge_entry_public_validation.json").read_text(encoding="utf-8")
    )
    gate2_candidate = json.loads(
        (GATE2_CANDIDATE_DIR / "gate2_frequency_candidate_summary.json").read_text(encoding="utf-8")
    )
    return {
        "response": response,
        "time": numeric_rows(
            GATE2_DIR / "representative_regular_wave_timeseries.csv", time_columns
        ),
        "begovic": numeric_rows(
            GATE2_DIR / "begovic_efd_comparison.csv", begovic_columns
        ),
        "fridsma": [
            {
                **{
                    key: round(float(row[key]), 10)
                    for key in fridsma_columns
                    if key not in {"configuration", "linear_gate_eligible"}
                },
                "configuration": row["configuration"],
                "linear_gate_eligible": row["linear_gate_eligible"].lower() == "true",
            }
            for row in read_csv(GATE2_DIR / "fridsma_table2_comparison.csv")
        ],
        "gate1": [
            {
                "grid": row["grid_label"],
                "coefficient": row["coefficient"],
                "frequency": round(float(row["omega_e_sqrt_l_over_g"]), 4),
                "reference": round(float(row["reference_value"]), 9),
                "computed": round(float(row["computed_value"]), 9),
                "relative_error": round(float(row["rel_error"]), 9),
                "status": row["status"],
            }
            for row in read_csv(GATE1_DIR / "gate1_coefficients_comparison.csv")
        ],
        "wedge_cases": {
            angle: wedge_case_payload(directory)
            for angle, directory in WEDGE_CASE_DIRS.items()
        },
        "motion_case": motion_case_payload(response),
        "delft372": {
            "vertices": numeric_rows(
                DELFT372_DIR / "delft372_catamaran_full_vertices.csv",
                ["vertex_id", "x_m", "y_m", "z_up_m"],
            ),
            "faces": numeric_rows(
                DELFT372_DIR / "delft372_catamaran_full_faces.csv",
                ["face_id", "vertex_0", "vertex_1", "vertex_2"],
            ),
            "time": numeric_rows(
                DELFT372_DIR / "delft372_test_8720_measured_first_harmonic.csv",
                [
                    "time_s",
                    "wave_elevation_at_cg_m",
                    "surge_m",
                    "sway_m",
                    "heave_m",
                    "roll_deg",
                    "pitch_deg",
                    "yaw_deg",
                ],
            ),
            "audit": delft_audit,
            "selected_test": delft_manifest["selected_test"],
            "lcg_from_ap_m": 1.41,
        },
        "wedge_validation": wedge_validation,
        "wedge_validation_image": image_data_url(
            WEDGE_VALIDATION_DIR / "wedge_entry_public_validation.png"
        ),
        "gate2_candidate": gate2_candidate,
        "gate2_candidate_points": numeric_rows(
            GATE2_CANDIDATE_DIR / "candidate_begovic_comparison.csv",
            [column for column in begovic_columns if column != "wave_steepness_ka"],
        ),
    }


def build_summary_tables(payload: dict[str, object]) -> dict[str, str]:
    response = payload["response"]
    time = payload["time"]
    gate1 = payload["gate1"]
    begovic = payload["begovic"]
    assert isinstance(response, list)
    assert isinstance(time, list)
    assert isinstance(gate1, list)
    assert isinstance(begovic, list)
    delft = payload["delft372"]
    wedge_validation = payload["wedge_validation"]
    gate2_candidate = payload["gate2_candidate"]
    assert isinstance(delft, dict)
    assert isinstance(wedge_validation, dict)
    assert isinstance(gate2_candidate, dict)

    gate_rows = [
        [
            "Gate 1",
            "线性高速2.5D水动力系数复现门",
            "Ma 2005 Wigley III；选定10条 A/B 系数；基准与加密网格",
            "10/10 + 10/10 通过",
            "证明限定系数实现和网格一致性；不代表完整Wigley、SL-7或整船运动通过",
        ],
        [
            "Gate 2",
            "规则迎浪整船升沉-纵摇响应门",
            "Faltinsen标准三航速、Fridsma 1969 A/B、Begovic三航速",
            "17/20项通过；总体FAIL",
            "内部数值闭合；Begovic升沉、纵摇和主峰频率三项未达到试验误差门槛",
        ],
    ]
    gate_table = html_table(
        ["名称", "检查对象", "对应案例", "当前结果", "正确理解"], gate_rows
    )

    angle_rows = [
        ["12.75°", "二维对称楔形底面与静水面夹角", "三网格数值门通过", "非线性2D+t入水求解器的较稳健起点"],
        ["12.50°", "同一楔形参数连续减小后的检查点", "三网格数值门通过", "证明延续算法可以向更平底、冲击更尖锐区域推进"],
        ["12.375°", "当前连续合格分支前沿", "K=9.6643×10⁻⁴≤10⁻³，通过", "当前可重载、可复算的最后正式合格检查点"],
        ["12.3625°", "下一细分步，不是新船型", "K=1.03968×10⁻³，超限约3.97%", "说明数值前沿仍停在12.375°，不能写成已经到12.25°"],
        ["12.25° / 10°", "后续目标角度", "尚未到达/尚未完成物理验证", "用于逐步逼近更典型的低斜升角高速滑行冲击问题"],
    ]
    angle_table = html_table(
        ["角度", "物理量", "当前状态", "在研究路线中的作用"], angle_rows
    )

    speed_rows = []
    for fn in (2.0, 3.0, 4.0):
        group = [row for row in response if row["fn_b"] == fn]
        max_heave = max(group, key=lambda row: row["heave_rao_m_per_m"])
        max_pitch = max(group, key=lambda row: row["pitch_rao_rad_per_wave_slope"])
        speed_rows.append(
            [
                f"{fn:.0f}",
                f"{group[0]['speed_mps']:.3f}",
                str(len(group)),
                f"{max_heave['heave_rao_m_per_m']:.3f} @ λ/L={max_heave['lambda_over_l']:.2f}",
                f"{max_pitch['pitch_rao_rad_per_wave_slope']:.3f} @ λ/L={max_pitch['lambda_over_l']:.2f}",
                f"{max(row['point_accel_g'] for row in group):.4f}",
            ]
        )
    speed_table = html_table(
        ["Fn_B", "航速(m/s)", "频率点", "最大升沉RAO", "最大纵摇RAO/波面斜率", "最大艏部加速度(g)"],
        speed_rows,
        "这些最大值只在本报告扫频范围 λ/L=4–12 内成立；表中波幅为0.01 m，因此加速度g值不能直接代表实船恶劣海况。",
    )

    def rms(column: str) -> float:
        return math.sqrt(sum(float(row[column]) ** 2 for row in time) / len(time))

    time_table = html_table(
        ["量", "最小值", "最大值", "均方根", "物理说明"],
        [
            ["入射波面(m)", f"{min(row['wave_elevation_m'] for row in time):.5f}", f"{max(row['wave_elevation_m'] for row in time):.5f}", f"{rms('wave_elevation_m'):.5f}", "规则波输入，幅值0.01 m"],
            ["升沉(m)", f"{min(row['heave_m'] for row in time):.5f}", f"{max(row['heave_m'] for row in time):.5f}", f"{rms('heave_m'):.5f}", "重心垂向平移，正负号按程序坐标约定"],
            ["纵摇(rad)", f"{min(row['pitch_rad'] for row in time):.6f}", f"{max(row['pitch_rad'] for row in time):.6f}", f"{rms('pitch_rad'):.6f}", "绕船体横向轴转动；图中另换算为度"],
            ["重心垂向加速度(m/s²)", f"{min(row['heave_accel_mps2'] for row in time):.4f}", f"{max(row['heave_accel_mps2'] for row in time):.4f}", f"{rms('heave_accel_mps2'):.4f}", "由升沉二阶导数得到"],
            ["艏部点垂向加速度(m/s²)", f"{min(row['point_vertical_accel_mps2'] for row in time):.4f}", f"{max(row['point_vertical_accel_mps2'] for row in time):.4f}", f"{rms('point_vertical_accel_mps2'):.4f}", "升沉加速度与纵摇角加速度按艏部力臂合成"],
        ],
    )

    gate1_base = [row for row in gate1 if row["grid"] == "base"]
    gate1_refined = [row for row in gate1 if row["grid"] == "refined"]
    base_map = {(row["coefficient"], row["frequency"]): row for row in gate1_base}
    refined_map = {(row["coefficient"], row["frequency"]): row for row in gate1_refined}
    coefficient_rows = []
    for key, base in base_map.items():
        refined = refined_map[key]
        change = abs(refined["computed"] - base["computed"]) / max(abs(base["computed"]), 1e-12)
        coefficient_rows.append(
            [
                key[0],
                f"{key[1]:.2f}",
                f"{base['reference']:.5g}",
                f"{base['computed']:.5g}",
                f"{refined['computed']:.5g}",
                f"{100.0 * change:.3f}%",
                "PASS",
            ]
        )
    coefficient_table = html_table(
        ["系数", "ωₑ√(L/g)", "文献值", "基准网格", "加密网格", "两网格变化", "状态"],
        coefficient_rows,
        "相对文献容差为15%，网格变化容限为2%。选定行全部通过，但这里没有覆盖Ma 2005的全部曲线。",
    )

    eligible = [row for row in begovic if row["linear_gate_eligible"]]
    heave_errors = [
        abs(row["heave_rao_m_per_m"] - row["reference_heave_rao_m_per_m"])
        / max(abs(row["reference_heave_rao_m_per_m"]), 1e-12)
        for row in eligible
    ]
    pitch_errors = [
        abs(row["pitch_rao_rad_per_wave_slope"] - row["reference_pitch_rao_rad_per_wave_slope"])
        / max(abs(row["reference_pitch_rao_rad_per_wave_slope"]), 1e-12)
        for row in eligible
    ]
    experiment_table = html_table(
        ["对照", "有效点", "升沉中位相对误差", "纵摇中位相对误差", "判定"],
        [
            ["Fridsma 1969 线性长波子集", "4/11", "8.23%", "12.70%", "运动幅值通过；加速度仅作诊断"],
            ["Begovic kA≤0.055 子集", f"{len(eligible)}/24", f"{100*median(heave_errors):.2f}%", f"{100*median(pitch_errors):.2f}%", "两项均未达到15%门槛"],
            ["Begovic 已解析主峰", "4个", "—", "—", "最大频率误差31.88%，未达到10%门槛"],
        ],
    )

    mesh_audit = delft["audit"]
    assert isinstance(mesh_audit, dict)
    mesh_table = html_table(
        ["检查项", "结果", "验收含义"],
        [
            ["顶点 / 三角面", f"{mesh_audit['vertex_count']} / {mesh_audit['face_count']}", "由23个公开横剖面与艏轮廓放样"],
            ["开边", str(mesh_audit["boundary_edge_count"]), "为0表示不存在未连接的外轮廓裂口"],
            ["非流形边", str(mesh_audit["nonmanifold_edge_count"]), "为0表示每条封闭边恰由两个三角面共享"],
            ["退化面", str(mesh_audit["degenerate_face_count"]), "为0表示没有零面积三角形"],
            ["连通分量", str(mesh_audit["connected_component_count"]), "两个分量分别对应左右片体"],
            ["外形范围", "x=0–3.0435 m；y=±0.47 m；z=-0.15–0.05 m", "与Delft 372公开主尺度一致"],
        ],
    )

    wedge_metrics = wedge_validation["metrics"]
    wedge_table = html_table(
        ["验证量", "误差", "限值", "状态"],
        [
            ["外自由面形状NRMSE", f"{100*wedge_metrics['free_surface']['nrmse_by_reference_range']:.2f}%", "10%", "PASS"],
            ["压力分布NRMSE", f"{100*wedge_metrics['pressure_distribution']['nrmse_by_reference_range']:.2f}%", "15%", "PASS"],
            ["压力峰值", f"{100*wedge_metrics['pressure_peak_relative_error']:.2f}%", "10%", "PASS"],
            ["压力峰位置", f"{100*wedge_metrics['pressure_peak_location_relative_error']:.2f}%", "10%", "PASS"],
            ["积分垂向力系数", f"{100*wedge_metrics['vertical_force_relative_error']:.2f}%", "10%", "PASS"],
        ],
        "NRMSE为按参考曲线变化范围归一化的均方根误差；积分力参考值由公开压力曲线独立数值积分得到。",
    )

    candidate_motion = {
        row["metric"]: row for row in gate2_candidate["global_motion_metrics"]
    }
    candidate_table = html_table(
        ["模型", "升沉中位误差 / NRMSE", "纵摇中位误差 / NRMSE", "最大已解析峰频误差", "总状态"],
        [
            ["冻结Gate 2基线", "29.79% / 84.40%", "34.16% / 81.66%", "31.88%", "FAIL"],
            [
                "频率相关固定候选",
                f"{100*candidate_motion['heave_motion']['median_relative_error']:.2f}% / {100*candidate_motion['heave_motion']['nrmse']:.2f}%",
                f"{100*candidate_motion['pitch_motion']['median_relative_error']:.2f}% / {100*candidate_motion['pitch_motion']['nrmse']:.2f}%",
                f"{100*gate2_candidate['resolved_peak_max_relative_error']:.2f}%",
                "FAIL",
            ],
        ],
        "候选在三个航速使用完全相同的理论与离散参数，未使用经验响应倍率；改善是真实进展，但尚未达到全部门槛。",
    )

    return {
        "gate_table": gate_table,
        "angle_table": angle_table,
        "speed_table": speed_table,
        "time_table": time_table,
        "coefficient_table": coefficient_table,
        "experiment_table": experiment_table,
        "mesh_table": mesh_table,
        "wedge_table": wedge_table,
        "candidate_table": candidate_table,
    }


HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>高速船型运动预报系统：真实几何与定量验证进展报告</title>
<style>
:root{--ink:#16212b;--muted:#5a6873;--line:#d8e0e4;--paper:#fff;--wash:#f3f7f6;--teal:#087e78;--coral:#d95f47;--gold:#bc872f;--blue:#3569a8;--green:#4f8a58;--red:#b43c3c;--mono:Consolas,"SFMono-Regular",monospace}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#e8eeec;color:var(--ink);font-family:"Microsoft YaHei","Noto Sans CJK SC","PingFang SC",Arial,sans-serif;line-height:1.78;letter-spacing:0}
main{max-width:1220px;margin:0 auto;background:var(--paper);box-shadow:0 0 34px rgba(20,42,48,.12)}
.cover{min-height:78vh;padding:72px 8% 56px;display:grid;align-content:center;background:linear-gradient(115deg,#f8fbfa 0 68%,#e1efec 68%);border-bottom:6px solid var(--teal);position:relative;overflow:hidden}
.cover:after{content:"";position:absolute;right:-90px;bottom:-110px;width:450px;height:270px;border:2px solid rgba(8,126,120,.25);transform:skewX(-24deg) rotate(-9deg)}
.eyebrow{font-weight:700;color:var(--teal);font-size:.95rem}.cover h1{font-size:clamp(2.25rem,5vw,4.7rem);line-height:1.12;max-width:900px;margin:.35em 0 .3em;letter-spacing:0}.cover .lead{max-width:780px;font-size:1.18rem;color:#344650}.stamp{display:inline-block;border:1px solid var(--ink);padding:7px 12px;margin-top:24px;font-family:var(--mono);font-size:.86rem;background:#fff}
.content{padding:36px 7% 80px}nav.toc{border-left:5px solid var(--teal);background:var(--wash);padding:22px 26px;margin:0 0 48px}nav.toc a{color:var(--ink);text-decoration:none;margin-right:18px;white-space:nowrap}nav.toc a:hover{color:var(--teal);text-decoration:underline}
section{padding:36px 0;border-top:1px solid var(--line)}section:first-of-type{border-top:0}h2{font-size:1.9rem;line-height:1.25;margin:0 0 18px}h3{font-size:1.28rem;margin:28px 0 10px;color:#253842}h4{font-size:1.05rem;margin:20px 0 8px}.section-kicker{color:var(--teal);font-weight:700;font-size:.9rem;margin-bottom:7px}.intro{font-size:1.08rem;max-width:960px;color:#35454e}.plain-note{border-left:4px solid var(--gold);padding:12px 18px;background:#fffaf0;margin:20px 0}.warning{border-left-color:var(--coral);background:#fff6f3}.success{border-left-color:var(--green);background:#f4faf4}
.status-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:26px 0}.status-strip>div{background:#fff;padding:18px}.status-strip strong{display:block;font-size:1.55rem;color:var(--teal)}.status-strip span{font-size:.84rem;color:var(--muted)}
.figure{margin:28px 0 42px;border:1px solid var(--line);border-radius:6px;overflow:hidden;background:#fff}.figure-head{padding:17px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:16px;align-items:center}.figure-title{font-weight:700}.figure-no{color:var(--teal);margin-right:8px}.canvas-wrap{position:relative;background:#f7faf9;min-height:360px}.canvas-wrap canvas{display:block;width:100%;height:460px}.canvas-wrap.tall canvas{height:540px}.figure-explain{padding:20px 24px 24px;color:#344650}.figure-explain p{margin:.6em 0}.figure-explain strong{color:var(--ink)}
.embedded-figure{display:block;width:100%;height:auto;background:#fff}.evidence-badge{display:inline-block;padding:3px 7px;border-radius:3px;background:#e4f2ef;color:#076a64;font-size:.76rem;font-weight:700}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.toolbar label{font-size:.86rem;color:var(--muted)}select,input[type=range],button{font:inherit}select,button{border:1px solid #aebbc0;background:#fff;color:var(--ink);padding:7px 10px;border-radius:4px}button{cursor:pointer}button:hover{border-color:var(--teal);color:var(--teal)}input[type=range]{accent-color:var(--teal);max-width:240px}.readout{font-family:var(--mono);font-size:.82rem;background:#fff;border:1px solid var(--line);padding:6px 9px;border-radius:4px}
.split{display:grid;grid-template-columns:1fr 1fr;gap:22px}.mini-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.mini-panel{border:1px solid var(--line);border-radius:5px;padding:12px;background:#fff}.mini-panel canvas{width:100%;height:145px}.mini-panel h4{margin:0 0 4px;font-size:.95rem}.placeholder-tag{display:inline-block;font-size:.72rem;background:#f5e3df;color:#8d2f26;padding:2px 6px;border-radius:3px;margin-left:5px}.solved-tag{display:inline-block;font-size:.72rem;background:#dcefeb;color:#096761;padding:2px 6px;border-radius:3px;margin-left:5px}
.table-scroll{overflow-x:auto;margin:18px 0}table{width:100%;border-collapse:collapse;font-size:.88rem}th{background:#eaf2f0;text-align:left;color:#22343c}th,td{border:1px solid var(--line);padding:9px 10px;vertical-align:top}tbody tr:nth-child(even){background:#fafcfc}.table-note{font-size:.83rem;color:var(--muted);margin-top:-10px}.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.83rem;color:var(--muted)}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}
.equation{font-family:Cambria,"Times New Roman",serif;text-align:center;padding:14px;background:#f7f8f7;border:1px solid var(--line);overflow:auto}.callout-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:22px 0}.callout{border-top:4px solid var(--teal);padding:16px;background:var(--wash)}.callout b{display:block;margin-bottom:6px}.small{font-size:.84rem;color:var(--muted)}code{font-family:var(--mono);font-size:.88em}.source{font-family:var(--mono);font-size:.75rem;color:#68757d;word-break:break-all;border-top:1px dashed var(--line);padding-top:9px;margin-top:12px}
footer{background:#203037;color:#e4eeeb;padding:32px 7%;font-size:.86rem}footer strong{color:#fff}
@media(max-width:820px){.content{padding:26px 5% 55px}.cover{padding:55px 6%}.split,.callout-grid{grid-template-columns:1fr}.status-strip{grid-template-columns:1fr 1fr}.mini-grid{grid-template-columns:1fr}.table-scroll table{min-width:720px}.canvas-wrap canvas{height:390px}.figure-head{align-items:flex-start;flex-direction:column}}
@page{size:A4;margin:12mm}
@media print{body{background:#fff}main{box-shadow:none;max-width:none}.cover{min-height:0;page-break-after:always}.content{padding:20px 16px}.figure{break-before:page;break-inside:auto;border-radius:0;overflow:visible}.figure-head{break-after:avoid}.canvas-wrap,.mini-panel{break-inside:avoid}.toolbar,nav.toc{display:none}.canvas-wrap canvas{height:390px}.figure-explain{font-size:9pt;line-height:1.55}.figure-explain p{margin:.45em 0}h2{page-break-after:avoid}.table-scroll{overflow:visible}.table-scroll table,table{display:table;width:100%;min-width:0!important;table-layout:fixed;font-size:8pt}th,td{overflow-wrap:anywhere;word-break:normal;padding:6px 7px}footer{display:none}}
</style>
</head>
<body>
<main>
<header class="cover">
  <div class="eyebrow">高速船型运动预报系统 · 阶段性科研报告</div>
  <h1>当前结果<br>直观可视化报告</h1>
  <p class="lead">把 Gate 1、Gate 2、楔形入水、Delft 372公开数字型线、真实封闭网格、规则波时间动画和六自由度试验谐波放在同一条证据链里。每一幅图都由计算文件或公开试验表直接生成，不再用示意船体代替真实几何。</p>
  <div class="stamp">基线冻结：2026-08-31　新增证据：2026-09-13　全部图像与数据内嵌</div>
</header>

<div class="content">
<nav class="toc"><strong>目录：</strong>
  <a href="#terms">先说清 Gate 与角度</a><a href="#mesh">真实网格</a><a href="#surface">三维频域响应</a><a href="#motion">三维动态过程</a><a href="#sixdof">六自由度</a><a href="#validation">试验对照</a><a href="#conclusion">结论</a>
</nav>

<section id="terms">
  <div class="section-kicker">01 · 先消除概念混淆</div>
  <h2>Gate 到底是什么？</h2>
  <p class="intro"><strong>Gate（阶段验收闸门）不是一种水动力模型，也不是某一条公式。</strong>它是一组预先写死的检查条件：只有本阶段规定的对象、误差、网格独立性和参考隔离全部满足，程序才允许把该阶段标成“通过”。因此，Gate 1通过不能自动推出Gate 2通过；软件测试通过也不能替代实验验证。</p>
  __GATE_TABLE__
  <div class="status-strip">
    <div><strong>10/10 × 2</strong><span>Gate 1：选定10条系数在基准/加密网格均通过</span></div>
    <div><strong>1.1465%</strong><span>Gate 1：最大两网格变化，小于2%限值</span></div>
    <div><strong>17/20</strong><span>Gate 2：规则迎浪阶段机器检查</span></div>
    <div><strong>3项未过</strong><span>均来自Begovic实验精度与主峰频率</span></div>
  </div>
  <div class="status-strip">
    <div><strong>0 / 0 / 0</strong><span>Delft网格：开边 / 非流形边 / 退化面</span></div>
    <div><strong>3096</strong><span>Delft 372封闭片体三角面</span></div>
    <div><strong>5 / 5</strong><span>20°楔形自由面、压力与积分力公开参考检查</span></div>
    <div><strong>15.4%</strong><span>频率相关候选升沉中位误差，仍未总体通过</span></div>
  </div>
  <div class="plain-note warning"><strong>最重要的边界：</strong>Gate 1是“选定的线性2.5D系数复现门”，Gate 2是“整船规则迎浪升沉-纵摇响应门”。前者不是完整SL-7验证，后者目前明确未通过最终验收。</div>

  <h3>12.75°、12.5°、12.375°是什么？</h3>
  <p>这三个数字都是<strong>二维对称楔形的斜升角 β（deadrise angle，V形底单侧底面与未扰动水平水面的夹角）</strong>。它们不是船的纵倾角，不是波浪方向，也不是船体横摇角。把一个V形船底横剖面切出来看，β越小，底越平；同样入水速度下，水被迫在更短时间内向两侧加速，冲击压力更集中，喷溅根附近的自由面和薄射流也更难计算。</p>
  <div class="equation">几何关系：η = −|ξ| tan β　；　β↓ ⇒ 底面更平、冲击峰更尖、自由面根区更难离散</div>

  <div class="figure" id="fig-angle">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 1</span>三个已计算斜升角的真实求解边界根区</div><div class="toolbar"><label>已计算检查点 <select id="angleSelect"><option>12.75</option><option>12.5</option><option selected>12.375</option></select></label><span id="angleReadout" class="readout"></span></div></div>
    <div class="canvas-wrap"><canvas id="angleCanvas"></canvas></div>
    <div class="figure-explain"><p><strong>图的来源：</strong>这里已经删除解析楔形示意图。画布逐点读取三个正式检查点各自的 <code>coupled_boundary_nodes.csv</code>，显示求解后实际得到的湿楔面、外自由面和薄射流上下表面。水平虚线是相似坐标中的未扰动静水基准 <code>η=0</code>；它不是拿来代替瞬时自由面的直线。蓝色曲线才是计算所得自由面，黑色曲线才是求解器中的湿楔面。</p><p><strong>如何判断斜升角：</strong>楔尖位于 <code>(ξ,η)=(0,−1)</code>，从楔尖向右上延伸的黑色节点链是单侧湿楔面。斜升角由这条真实节点链的几何斜率决定。图中只显示当前已生成并通过相应数值门的12.75°、12.5°和12.375°；12.3625°与10°没有合格边界文件，因此不再画成好像已经算出的几何。</p><p><strong>水面与入水关系：</strong>楔尖在静水基准以下，楔面向右上穿过根区；水沿楔面向外加速，在喷溅根处分成很薄的射流。青色与蓝色两条非常接近的节点链分别是射流贴体侧与自由面侧，二者之间是实际计算出的有限厚度，不是绘图线宽造成的重影。随着斜升角降低，根区和薄射流更难离散，所以连续延拓步长从0.25°缩小到0.0125°。</p></div>
  </div>
  __ANGLE_TABLE__
</section>

<section id="mesh">
  <div class="section-kicker">02 · 几何与离散对象</div>
  <h2>“真实网格”需要分成两种</h2>
  <p class="intro">当前项目同时有线性2.5D整船站位几何和非线性二维楔形边界元网格。二者解决的问题不同，不能把二维剖面边界画成一艘已经完成的三维滑行艇。下面两幅图分别展示它们真实的计算对象。</p>

  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 2</span>Wigley III 线性2.5D基准船体三维站位网格</div><div class="toolbar"><span class="readout">L=3.0 m　B=0.3 m　T=0.1875 m</span><button data-reset="wigleyCanvas">重置视角</button></div></div>
    <div class="canvas-wrap tall"><canvas id="wigleyCanvas"></canvas></div>
    <div class="figure-explain"><p><strong>图的来源：</strong>这是Gate 1对应的Wigley III解析船型，不是示意性随手画出的船。网格节点由项目中实际采用的解析式 <code>2y/B=(1−(z/T)²)(1−ξ²)(1+0.2ξ²)</code> 生成，ξ=2x/L−1。横向闭合曲线代表各纵向站位剖面，纵向线代表相同吃水层上的节点连接。</p><p><strong>如何阅读：</strong>拖动鼠标可旋转。船艏和船艉处半宽收敛到零，中部水线最宽；竖直方向从静水面到龙骨。线性2.5D模型在每个站位上解二维横剖面水动力，再按高速局部时间关系沿船长装配，所以这张图展示的是“站位传播”的空间骨架。</p><p><strong>能得出什么：</strong>它证明当前Gate 1不是无几何的矩阵拟合，而是由明确的站位网格驱动。不过Wigley III是排水型光顺基准船，不能代替带折角、艉板和喷溅的真实滑行艇几何验证。</p></div>
  </div>

  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 3</span>12.375°楔形入水真实闭合边界与水面关系</div><div class="toolbar"><label>检查范围 <select id="wedgeMode"><option value="full">完整闭合计算域</option><option value="root">入水根区与薄射流</option></select></label><span id="wedgeReadout" class="readout"></span></div></div>
    <div class="canvas-wrap tall"><canvas id="wedgeCanvas"></canvas></div>
    <div class="figure-explain"><p><strong>外轮廓到底有没有封闭：</strong>有。12.375°文件含921个节点和920个面板，首节点与末节点完全重合，欧氏闭合误差为 <code>0.0</code>。此前看起来“没有封闭”，是因为把所有边界画成同色线，又把二维边界复制成了并不存在于求解器中的单位跨度三维带。新版严格按面板索引把闭合链分为六段，并用不同颜色显示。</p><p><strong>六段边界如何连接：</strong>从喷溅根附近的首节点出发，依次经过外自由面320个面板、远场24个面板、对称边界16个面板、湿楔面48个面板、射流贴体侧256个面板和射流自由面侧256个面板，最后回到首节点。楔形固体外轮廓本来就不会在这个半域流体模型里单独封成一个实心多边形；真正必须闭合的是用于边界积分的<strong>流体计算域边界</strong>，它已闭合。</p><p><strong>如何检查：</strong>“完整闭合计算域”显示所有节点，淡蓝填充就是这条闭合链围成的流体域；“入水根区与薄射流”放大楔尖、湿楔面、瞬时自由面和射流。灰色虚线为未扰动静水基准，蓝色边界为实际瞬时自由面。切换两种范围后，右上角仍显示同一组节点数、面板数和闭合误差。</p><p><strong>能得出什么：</strong>该检查点的积分运动学残差K为9.6643×10⁻⁴，低于10⁻³数值门槛；这只证明当前离散边界在规定指标上自洽。检查点状态仍为 <code>unvalidated</code>，压力分布、自由面形状和积分力尚未完成独立实验闭环。</p><div class="source">节点：outputs/self_similar_wedge_12p375deg_n320_globaldct16_syncmap_relinearized_v949/coupled_boundary_nodes.csv</div></div>
  </div>

  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 3A</span>20°楔形入水：计算几何、自由面、压力与积分力的统一定量验证</div><span class="evidence-badge">公开数值基准 5/5 PASS</span></div>
    <img class="embedded-figure" src="__WEDGE_VALIDATION_IMAGE__" alt="20度楔形入水公开参考验证四联图">
    <div class="figure-explain"><p><strong>产生背景与作用：</strong>前面的12.375°图回答“边界是否闭合、数值残差是否达到门槛”，但不能回答“自由面和压力是否物理正确”。因此另选已经具备公开曲线和标量表的20°自相似楔形作为验证角度。求解过程中没有读取参考数据，计算结束后才对照，避免把参考曲线偷偷变成边界条件。</p><p><strong>子图(a)如何阅读：</strong>灰色区域是斜升角20°、顶部显式封口的有限刚性楔形外轮廓；黑色斜边是实际入水底面，蓝绿色曲线是求解器输出的瞬时自由面，蓝灰虚线是入水前未扰动水面。红点是喷溅根。楔尖位于无量纲深度−1附近，自由面沿楔面上升后向远场衰减到0，完整显示了“楔体在水下、水沿两侧爬升并形成喷溅根”的空间关系；顶部封口也使刚体轮廓不再产生视觉歧义。</p><p><strong>子图(b)如何阅读：</strong>横轴是距楔体中心的无量纲横向距离，纵轴是自由面高度。黑线为Iafrati 2013公开非线性解，虚线为本程序。两线从喷溅根附近的高曲率区逐渐贴合并向远场归零；归一化均方根误差为7.31%，说明主要外自由面形状已复现。根部最大点差仍较明显，因此它不是“零误差真值”。</p><p><strong>子图(c)如何阅读：</strong>横轴沿湿楔面以垂向相似坐标表示，纵轴是压力系数。两条曲线都从较平缓的体面压力上升到喷溅根前的尖峰，再迅速降到自由面零压力。压力分布误差为9.98%，峰值误差3.26%，峰位置误差5.69%；这三项分别检查整条曲线、最危险压力幅值和冲击位置，不能互相替代。</p><p><strong>子图(d)如何阅读：</strong>柱高是压力沿湿楔面积分并投影到垂向后的无量纲力系数。本程序为41.05，公开压力曲线独立积分为42.71，误差3.89%。它证明压力不是“曲线看起来像”而已，积分后的总载荷也保持一致。该闭环属于公开非线性数值基准，不是实验流体动力学闭环；Aarsnes 30°自由落体试验仍列为后续独立实验门。</p></div>
  </div>
  __WEDGE_TABLE__
</section>

<section id="surface">
  <div class="section-kicker">03 · 传播响应网格</div>
  <h2>三航速 × 二十五频率点的三维响应面</h2>
  <p class="intro">“传播响应网格”在这里指规则迎浪频域扫频结果：横轴是波长与船长之比λ/L，纵轴是梁宽弗劳德数Fn_B，竖轴可以切换为升沉响应幅值算子、纵摇响应幅值算子或艏部加速度。每个曲面节点都是机器CSV中的真实计算行。</p>
  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 4</span>频域响应三维曲面</div><div class="toolbar"><label>竖轴 <select id="surfaceMetric"><option value="heave_rao_m_per_m">升沉RAO (m/m)</option><option value="pitch_rao_rad_per_wave_slope">纵摇RAO/波面斜率</option><option value="point_accel_g">艏部加速度 (g)</option></select></label><button data-reset="surfaceCanvas">重置视角</button></div></div>
    <div class="canvas-wrap tall"><canvas id="surfaceCanvas"></canvas></div>
    <div class="figure-explain"><p><strong>如何读曲面：</strong>沿λ/L方向移动相当于改变波长或频率；沿Fn_B方向移动相当于提高航速；曲面越高，单位波幅引起的响应越大。三条带色的航速剖面对应Fn_B=2、3、4，半透明网格只是连接已有离散点，不能理解成额外计算数据。</p><p><strong>当前趋势：</strong>在本次λ/L=4–12扫频区间内，三种航速的最大升沉与纵摇响应都出现在短端λ/L=4。航速增加后，艏部加速度明显增大，这是因为迎浪遭遇频率随前进速度增加，而点加速度还包含纵摇角加速度乘以艏部力臂。这个趋势有明确的运动学原因，但峰值是否与实测一致必须看后面的Begovic对照。</p><p><strong>不能过度解释：</strong>本图使用的是Faltinsen第9章降阶滑行模型通道，而不是完整Ma外域历史Green函数2.5D内核直接产生的整船波浪响应。因此它能展示当前规则波模块已经连通，却不能作为“完整2.5D已闭合”的证据。</p></div>
  </div>
  __SPEED_TABLE__
</section>

<section id="motion">
  <div class="section-kicker">04 · 动态应用过程</div>
  <h2>规则迎浪中的三维时间动画</h2>
  <p class="intro">代表对象已替换为公开基准Delft 372双体船。两个片体的封闭外壳由B2报告23个数字横剖面和艏轮廓放样；报告没有给出连接桥和上层建筑的数字型线，因此本轮不虚构这些结构。动态采用同一报告180°迎浪试验8720的六自由度一阶谐波：航速3.347 m/s、入射波圆频率3.583 rad/s、遭遇圆频率7.964 rad/s、波长船长比1.601、波幅1.79 cm。船、波和运动现在属于同一个案例。</p>
  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 5</span>Delft 372真实封闭船体网格与实测六自由度迎浪谐波</div><div class="toolbar"><button id="playButton">播放</button><label>时间 <input id="timeSlider" type="range" min="0" max="360" value="24"></label><label>运动显示倍率 <select id="motionScale"><option value="1" selected>1×物理比例</option><option value="2">2×</option><option value="4">4×</option></select></label><button data-reset="motionCanvas">重置视角</button><span id="motionReadout" class="readout"></span></div></div>
    <div class="canvas-wrap tall"><canvas id="motionCanvas"></canvas></div>
    <div class="figure-explain"><p><strong>图中每一部分的真实来源：</strong>两个片体的1552个顶点和3096个三角面直接来自Delft 372 offsets；艉封板、片体甲板封口和艏轮廓共同形成两个水密外壳。连接桥和上层建筑没有公开数字型线，故没有建模。蓝色网格是试验8720的规则迎浪，波长由λ/L=1.601和Lpp=3.0 m得到。灰色细网格是平均静水面，便于判断瞬时波峰、波谷和船体位置。</p><p><strong>如何检查湿表面：</strong>每一帧都把三角面中心与同一位置的瞬时波面比较。低于波面的面显示为蓝绿色，表示该时刻的几何湿面；高于波面的面显示为浅灰色，表示露出水面的外壳。这是几何浸没判定，不等于已经计算出的非线性湿面压力，但能够直观看出水线是否切过封闭船体、左右片体是否连续、船艏和艉板是否存在裂口。</p><p><strong>动态过程怎么看：</strong>按播放或拖动滑块，波面从船艏向船艉传播，船体同时执行试验给出的纵荡、横荡、升沉、横摇、纵摇和艏摇一阶谐波。1×为物理比例；2×和4×只放大六自由度位移与转角，船体尺寸和波幅不放大。右上读数始终显示未放大的物理值。</p><p><strong>证据边界：</strong>这里的运动时间序列由公开幅值与相位重构，不是MARIN原始采样时序，也没有加入报告未给出的平均姿态。因此它可以验证几何、单位、相位和六自由度显示链路，不能当作本程序已经预测出Delft 372运动。当前多体cross-radiation（交叉辐射，即一个片体运动引起另一片体受力）与cross-diffraction（交叉绕射，即两片体共同改变入射波散射场）仍需后续求解器闭合。</p></div>
  </div>
  __MESH_TABLE__
</section>

<section id="sixdof">
  <div class="section-kicker">05 · 六自由度统一输出</div>
  <h2>同一公开试验的六自由度幅值与相位</h2>
  <p class="intro">六自由度依次为纵荡、横荡、升沉、横摇、纵摇和艏摇。下图不再画四条程序零占位，而是采用Delft 372试验8720发表的六组响应幅值算子与相位，重构三个遭遇周期。迎浪下横向响应很小但不完全为零，能够检验显示链路是否保留了真实试验中的微小非对称与测量分量。</p>
  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 6</span>Delft 372试验8720六自由度一阶谐波总览</div><div class="legend"><span><i class="dot" style="background:#087e78"></i>B2公开幅值与相位重构</span></div></div>
    <div class="mini-grid" id="sixGrid"></div>
    <div class="figure-explain"><p><strong>每个子图怎么看：</strong>横轴都是时间，三个平移自由度统一换算为毫米，三个转动自由度以度显示。纵荡、横荡和升沉的幅值由“cm/cm响应幅值算子×1.79 cm波幅”得到；横摇、纵摇和艏摇由“deg/cm×1.79 cm”得到。每条曲线的峰值位置由B2相位决定。</p><p><strong>能看出什么：</strong>升沉幅值约50.2 mm，是最显著平移；纵摇幅值约1.55°，是最显著转动。横荡和横摇远小于纵向运动，符合180°迎浪与双体船近似对称性，但试验结果并非数学上的绝对零。纵荡和艏摇也被保留，因此六个面板现在都来自真实数据。</p><p><strong>不能得出什么：</strong>这些曲线证明公开试验数据已被正确解析并接入三维显示，不证明当前2.5D求解器已经复现它们。真正的预测验收仍要把模型曲线与这些试验曲线逐点比较。</p></div>
  </div>

  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 7</span>当前降阶滑行模型规则波时域：运动与垂向加速度</div><div class="toolbar"><label>显示量 <select id="timeMetric"><option value="motion">波面/升沉/纵摇</option><option value="accel">重心/艏部加速度</option></select></label></div></div>
    <div class="canvas-wrap"><canvas id="timeCanvas"></canvas></div>
    <div class="figure-explain"><p><strong>数据身份：</strong>本图不是Delft 372试验曲线，而是当前单体滑行艇降阶模型的小波幅规则波复算，用于检查频域解与时域积分是否相互一致。</p><p><strong>运动模式：</strong>波面和升沉换算为毫米，纵摇换算为度。三条曲线放在同一画布中是为了观察峰谷错开的相位关系，不应用其共同纵坐标直接比较不同单位的数值大小；定量幅值应回到六自由度子图和汇总表读取。</p><p><strong>加速度模式：</strong>重心加速度只含升沉二阶导数；艏部点加速度还叠加纵摇角加速度与纵向力臂，所以艏部曲线幅值更高。本算例的艏部加速度均方根为约0.0792 m/s²，属于小波幅线性复算，不能外推为砰击冲击峰。</p></div>
  </div>
</section>

<section id="validation">
  <div class="section-kicker">06 · 频域结果与可验证性</div>
  <h2>内部一致性通过，外部试验仍指出关键差距</h2>
  <p class="intro">频域曲线负责回答“波长和航速变化时响应如何变化”；试验散点负责回答“这种变化是否与真实船一致”。两者缺一不可。仅看平滑曲线容易产生已经验证完成的错觉，所以本节把系数复现、模型扫频与试验对照放在一起。</p>

  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 8</span>三航速频域响应曲线</div><div class="toolbar"><label>响应量 <select id="frequencyMetric"><option value="heave_rao_m_per_m">升沉RAO</option><option value="pitch_rao_rad_per_wave_slope">纵摇RAO/波面斜率</option><option value="point_accel_g">艏部加速度(g)</option></select></label></div></div>
    <div class="canvas-wrap"><canvas id="frequencyCanvas"></canvas></div>
    <div class="figure-explain"><p><strong>读法：</strong>每条线代表一个航速，横轴λ/L越小表示相对短波。响应幅值算子RAO（Response Amplitude Operator，单位输入波幅引起的稳态响应幅值）越高，表示该波长下船体越敏感。纵摇选项已除以波面斜率，便于不同波长比较。</p><p><strong>趋势：</strong>在当前长波适用范围内，升沉响应大体接近1，表示重心升沉幅值与波幅同量级；纵摇和艏部加速度对航速更敏感。曲线在λ/L=4处仍向上，意味着真实主峰可能位于当前扫频边界之外，或模型的频率相关水动力不足。后者正是Begovic主峰误差没有通过的重要信号。</p></div>
  </div>

  <h3>Gate 1选定系数明细</h3>
  __COEFFICIENT_TABLE__

  <div class="figure">
    <div class="figure-head"><div class="figure-title"><span class="figure-no">图 9</span>Begovic试验、锁定基线与频率相关候选对照</div><div class="toolbar"><label>响应量 <select id="comparisonMetric"><option value="heave">升沉RAO</option><option value="pitch">纵摇RAO/波面斜率</option></select></label></div></div>
    <div class="canvas-wrap"><canvas id="comparisonCanvas"></canvas></div>
    <div class="figure-explain"><p><strong>如何读图：</strong>每个航速同时显示三类证据：圆点为公开试验，灰色虚线为2026-08-31锁定的第9章降阶基线，彩色实线为本轮固定参数的频率相关候选。空心试验点表示波陡kA&gt;0.055，仅保留诊断。候选在所有三种航速都使用相同的内外域匹配边界积分、完整压力项、0.5倍梁宽艉部修正和站位相位激励，未使用试验响应倍率。</p><p><strong>升沉结果：</strong>基线有效21点的中位误差约29.79%、归一化均方根误差84.40%；候选降至15.40%和23.83%。Fn_B=2.26与2.82的升沉幅值分项通过，Fn_B=1.67仍有明显峰高偏差。中位误差只比15%门槛高0.40个百分点，但归一化均方根仍高3.83个百分点，所以不能四舍五入成通过。</p><p><strong>纵摇结果：</strong>基线中位误差约34.16%、归一化均方根81.66%；候选降至22.05%和40.40%。Fn_B=2.82已通过，Fn_B=2.26的中位误差仍为约22.05%，低速峰值则偏高。说明频率相关辐射与站位相位改善了高速响应，但低速排水—滑行过渡和纵摇耦合仍未闭合。</p><p><strong>主峰与Gate 2结论：</strong>四个可解析峰中，候选最大频率误差降至11.60%，接近但仍高于10%门槛；同时matched-BIE内核自己的完整基准验证状态仍标为未完成。因此Gate 2继续保持FAIL，锁定基线没有被替换。下一步应处理过渡工况的载荷分层和纵摇端部项，而不是继续调响应倍率。</p></div>
  </div>
  __CANDIDATE_TABLE__
  __EXPERIMENT_TABLE__
</section>

<section id="conclusion">
  <div class="section-kicker">07 · 结论与下一步</div>
  <h2>这份图目前能证明什么，不能证明什么</h2>
  <div class="callout-grid">
    <div class="callout"><b>已经做实</b>Delft 372公开offsets已形成零开边、零非流形边、零退化面的完整双体船外壳；20°楔形自由面、压力、峰值位置与积分力五项公开参考验收通过；Gate 1保持通过。</div>
    <div class="callout" style="border-color:#bc872f"><b>已经明显推进但未验收完</b>频率相关候选把Begovic升沉整体误差大幅压低，高航速升沉/纵摇通过，最大已解析峰频误差降到11.60%；Gate 2仍为FAIL。</div>
    <div class="callout" style="border-color:#d95f47"><b>尚不能这样宣称</b>Delft六自由度图是试验谐波重构，不是当前模型预测；20°楔形是公开数值基准而非实验闭环；完整Ma 2.5D、多体干扰和自由航行2D+t仍未完成。</div>
  </div>
  <p><strong>最合理的下一阶段硬目标：</strong>在不使用响应标定的前提下，完成matched-BIE频率相关内核自身的Wigley/椭球双网格基准门；建立排水—半排水—滑行过渡载荷分层和纵摇端部项，使Begovic三航速升沉、纵摇的中位误差≤15%、NRMSE≤20%，四个已解析主峰误差全部≤10%；随后再把同一内核接入Delft 372双体共同边界系统。</p>
  <p class="plain-note success"><strong>一句话记忆：</strong>真实几何和楔形定量闭环已经从“可视化缺口”变成可复算成果；当前离最终目标最近、也最关键的一步，是让频率相关2.5D内核先通过自身基准，再让Gate 2从接近门槛变成真正20/20。</p>
  <h3>数据可追溯性</h3>
  <p class="small">本报告不从网络加载任何脚本、字体、图片或数据。HTML中的数组由下列冻结CSV直接嵌入；刷新或复制到另一台电脑仍可显示全部图形和动画。</p>
  <div class="source">__HASHES__</div>
</section>
</div>
<footer><strong>高速船型运动预报系统</strong><br>本文件是阶段性可视化解释报告。所有“通过”均限定于对应Gate的验收合同；未通过项与证据边界在正文中明确保留。</footer>
</main>

<script>
const DATA = __DATA__;
const COLORS = {teal:'#087e78', coral:'#d95f47', gold:'#bc872f', blue:'#3569a8', green:'#4f8a58', ink:'#16212b', muted:'#66747c', grid:'#d9e2e3'};
const SPEED_COLORS = {'2':'#087e78','3':'#d95f47','4':'#3569a8','1.67':'#087e78','2.26':'#d95f47','2.82':'#3569a8'};

function setupCanvas(canvas){
  const r=canvas.getBoundingClientRect(), dpr=Math.min(window.devicePixelRatio||1,2);
  const w=Math.max(320,r.width), h=Math.max(200,r.height);
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr)}
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return {ctx,w,h};
}
function extent(a){return [Math.min(...a),Math.max(...a)]}
function padExtent(e,p=.08){const d=(e[1]-e[0])||1;return [e[0]-d*p,e[1]+d*p]}
function map(v,a,b,c,d){return c+(v-a)*(d-c)/((b-a)||1)}
function nice(v,d=3){return Number(v).toFixed(d)}

function make3D(canvas, drawer, initial={yaw:-.75,pitch:.38,zoom:1}){
  const state={...initial,drag:false,px:0,py:0}; canvas._sceneState=state; canvas._sceneDraw=()=>drawer(state);
  canvas.addEventListener('pointerdown',e=>{state.drag=true;state.px=e.clientX;state.py=e.clientY;canvas.setPointerCapture(e.pointerId)});
  canvas.addEventListener('pointermove',e=>{if(!state.drag)return;state.yaw+=(e.clientX-state.px)*.008;state.pitch=Math.max(-1.3,Math.min(1.3,state.pitch+(e.clientY-state.py)*.008));state.px=e.clientX;state.py=e.clientY;drawer(state)});
  canvas.addEventListener('pointerup',()=>state.drag=false);canvas.addEventListener('wheel',e=>{e.preventDefault();state.zoom=Math.max(.55,Math.min(2.3,state.zoom*Math.exp(-e.deltaY*.001)));drawer(state)},{passive:false});
  drawer(state);return state;
}
function project3(p,state,w,h,scale=1,center=[0,0,0]){
  let x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2];
  const cy=Math.cos(state.yaw),sy=Math.sin(state.yaw),cp=Math.cos(state.pitch),sp=Math.sin(state.pitch);
  const x1=cy*x-sy*y,y1=sy*x+cy*y;const y2=cp*y1-sp*z,z2=sp*y1+cp*z;
  return [w*.5+x1*scale*state.zoom,h*.53-z2*scale*state.zoom,y2];
}
function drawPolyline3(ctx,pts,state,w,h,scale,center,color,width=1,alpha=1){
  if(!pts.length)return;ctx.beginPath();pts.forEach((p,i)=>{const q=project3(p,state,w,h,scale,center);i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1])});ctx.strokeStyle=color;ctx.globalAlpha=alpha;ctx.lineWidth=width;ctx.stroke();ctx.globalAlpha=1;
}
function resetScene(id,defaults){const c=document.getElementById(id),s=c._sceneState;if(!s)return;Object.assign(s,defaults);c._sceneDraw()}
document.querySelectorAll('[data-reset]').forEach(b=>b.addEventListener('click',()=>{const id=b.dataset.reset;const defaults=id==='surfaceCanvas'?{yaw:-.72,pitch:.52,zoom:1}:id==='wigleyCanvas'?{yaw:-.72,pitch:.34,zoom:1.25}:id==='motionCanvas'?{yaw:-.68,pitch:.42,zoom:1}:{yaw:-.55,pitch:.35,zoom:1};resetScene(id,defaults)}));

const WEDGE_STYLE={
  outer_free_surface:{label:'外自由面',color:'#3569a8'},
  far_field:{label:'远场边界',color:'#9a7a35'},
  symmetry:{label:'对称边界',color:'#7c8790'},
  wetted_wedge:{label:'湿楔面',color:'#203037'},
  shallow_jet_body:{label:'射流贴体侧',color:'#087e78'},
  shallow_jet_free_surface:{label:'射流自由面侧',color:'#d95f47'}
};
function wedgeSegments(c){return c.segments.map(s=>({...s,points:c.nodes.slice(s.start_node,s.end_node+1)}))}
function plot2D(ctx,w,h,segments,limits,options={}){
  const m={l:66,r:24,t:34,b:52},sx=x=>map(x,limits.x[0],limits.x[1],m.l,w-m.r),sy=y=>map(y,limits.y[0],limits.y[1],h-m.b,m.t);
  ctx.fillStyle='#f7faf9';ctx.fillRect(0,0,w,h);
  if(options.fill){const pts=segments.flatMap((s,i)=>i? s.points.slice(1):s.points);ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(sx(p.xi),sy(p.eta)):ctx.moveTo(sx(p.xi),sy(p.eta)));ctx.closePath();ctx.fillStyle='rgba(53,105,168,.075)';ctx.fill()}
  ctx.strokeStyle='#d6dfe1';ctx.lineWidth=1;ctx.setLineDash([6,5]);ctx.beginPath();ctx.moveTo(m.l,sy(0));ctx.lineTo(w-m.r,sy(0));ctx.stroke();ctx.setLineDash([]);
  ctx.fillStyle=COLORS.muted;ctx.font='12px Microsoft YaHei';ctx.fillText('未扰动静水基准 η=0',m.l+8,sy(0)-8);
  segments.forEach(s=>{ctx.beginPath();s.points.forEach((p,i)=>i?ctx.lineTo(sx(p.xi),sy(p.eta)):ctx.moveTo(sx(p.xi),sy(p.eta)));ctx.strokeStyle=WEDGE_STYLE[s.name].color;ctx.lineWidth=(s.name==='wetted_wedge'||s.name.includes('jet'))?2.7:2;ctx.stroke();const stride=Math.max(1,Math.ceil(s.points.length/90));ctx.fillStyle=WEDGE_STYLE[s.name].color;s.points.filter((_,i)=>i%stride===0).forEach(p=>{ctx.fillRect(sx(p.xi)-1.2,sy(p.eta)-1.2,2.4,2.4)})});
  ctx.strokeStyle=COLORS.ink;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(m.l,m.t);ctx.lineTo(m.l,h-m.b);ctx.lineTo(w-m.r,h-m.b);ctx.stroke();
  for(let i=0;i<=5;i++){const x=limits.x[0]+(limits.x[1]-limits.x[0])*i/5;ctx.fillStyle=COLORS.muted;ctx.fillText(nice(x,1),sx(x)-10,h-m.b+18)}
  for(let i=0;i<=4;i++){const y=limits.y[0]+(limits.y[1]-limits.y[0])*i/4;ctx.fillStyle=COLORS.muted;ctx.fillText(nice(y,1),8,sy(y)+4)}
  ctx.fillStyle=COLORS.ink;ctx.fillText('相似横坐标 ξ',w/2-35,h-14);ctx.save();ctx.translate(18,h/2+30);ctx.rotate(-Math.PI/2);ctx.fillText('相似竖坐标 η',0,0);ctx.restore();
  if(options.markers){options.markers.forEach(v=>{const x=sx(v.point.xi),y=sy(v.point.eta);ctx.beginPath();ctx.arc(x,y,4.5,0,Math.PI*2);ctx.fillStyle=v.color||COLORS.coral;ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.stroke();ctx.fillStyle=COLORS.ink;ctx.font='12px Microsoft YaHei';ctx.fillText(v.label,x+(v.dx??7),y+(v.dy??-7))})}
  return {sx,sy,m};
}
function rootLimits(c){const segs=wedgeSegments(c);const rootPts=segs.filter(s=>['outer_free_surface','wetted_wedge','shallow_jet_body','shallow_jet_free_surface'].includes(s.name)).flatMap(s=>s.points).filter(p=>p.xi<=10.2);return {x:[-.4,10.2],y:padExtent(extent(rootPts.map(p=>p.eta)),.10)}}

// Figure 1: actual solved wedge/free-surface roots only.
const angleCanvas=document.getElementById('angleCanvas'),angleReadout=document.getElementById('angleReadout');
function drawAngle(){const {ctx,w,h}=setupCanvas(angleCanvas),key=document.getElementById('angleSelect').value,c=DATA.wedge_cases[key],all=wedgeSegments(c),names=['outer_free_surface','wetted_wedge','shallow_jet_body','shallow_jet_free_surface'],segments=all.filter(s=>names.includes(s.name));ctx.clearRect(0,0,w,h);const body=all.find(s=>s.name==='wetted_wedge'),jetBody=all.find(s=>s.name==='shallow_jet_body'),jetFree=all.find(s=>s.name==='shallow_jet_free_surface');plot2D(ctx,w,h,segments,rootLimits(c),{markers:[{point:body.points[0],label:'楔尖'},{point:body.points.at(-1),label:'湿楔面根部',color:COLORS.teal,dx:-92,dy:-12},{point:jetBody.points.at(-1),label:'射流尖端',color:COLORS.coral},{point:jetFree.points.at(-1),label:'自由面闭合点',color:COLORS.blue,dx:9,dy:21}]});angleReadout.textContent=`β=${c.angle_deg}° | ${c.node_count}节点 | K=${Number(c.kinematic_integral).toExponential(3)}`;}
document.getElementById('angleSelect').addEventListener('change',drawAngle);

// Figure 2: analytical Wigley III station mesh.
const wigleyCanvas=document.getElementById('wigleyCanvas');
function wigleyPoint(x,z,side){const L=3,B=.3,T=.1875,xi=2*x/L-1,half=.5*B*(1-(z/T)**2)*(1-xi**2)*(1+.2*xi**2);return [x-L/2,side*half,-z]}
function drawWigley(state){const {ctx,w,h}=setupCanvas(wigleyCanvas);ctx.clearRect(0,0,w,h);const center=[0,0,-.08],scale=Math.min(w/4.3,h/1.2);ctx.fillStyle='#f7faf9';ctx.fillRect(0,0,w,h);for(let i=0;i<=30;i++){const x=3*i/30,section=[];for(let j=0;j<=12;j++)section.push(wigleyPoint(x,.1875*j/12,1));for(let j=12;j>=0;j--)section.push(wigleyPoint(x,.1875*j/12,-1));drawPolyline3(ctx,section,state,w,h,scale,center,i%5===0?COLORS.teal:'#79aaa6',i%5===0?1.5:.7)}for(let j=0;j<=12;j++){for(const side of [-1,1]){const line=[];for(let i=0;i<=60;i++)line.push(wigleyPoint(3*i/60,.1875*j/12,side));drawPolyline3(ctx,line,state,w,h,scale,center,j===0?COLORS.coral:'#3569a8',j===0?2:1,.85)}}ctx.fillStyle=COLORS.ink;ctx.font='13px Microsoft YaHei';ctx.fillText('拖动旋转 · 滚轮缩放',18,27);}
make3D(wigleyCanvas,drawWigley,{yaw:-.72,pitch:.34,zoom:1.25});

// Figure 3: exact, segmented and closed 2D BEM boundary.
const wedgeCanvas=document.getElementById('wedgeCanvas'),wedgeReadout=document.getElementById('wedgeReadout');
function drawWedge(){const {ctx,w,h}=setupCanvas(wedgeCanvas),c=DATA.wedge_cases['12.375'],segments=wedgeSegments(c),mode=document.getElementById('wedgeMode').value;ctx.clearRect(0,0,w,h);let limits;if(mode==='root'){limits=rootLimits(c)}else{limits={x:padExtent(extent(c.nodes.map(p=>p.xi)),.04),y:padExtent(extent(c.nodes.map(p=>p.eta)),.06)}}const body=segments.find(s=>s.name==='wetted_wedge'),jetBody=segments.find(s=>s.name==='shallow_jet_body');plot2D(ctx,w,h,segments,limits,{fill:mode==='full',markers:mode==='root'?[{point:body.points[0],label:'楔尖'},{point:body.points.at(-1),label:'湿楔面根部',color:COLORS.teal,dx:-92,dy:-12},{point:jetBody.points.at(-1),label:'射流尖端',color:COLORS.coral},{point:c.nodes[0],label:'首末重合点',color:COLORS.blue,dx:9,dy:21}]:[{point:c.nodes[0],label:'首节点=末节点',color:COLORS.coral}]});let x=72,y=21;segments.forEach(s=>{ctx.fillStyle=WEDGE_STYLE[s.name].color;ctx.fillRect(x,y-8,14,4);ctx.fillStyle=COLORS.ink;ctx.font='11px Microsoft YaHei';ctx.fillText(`${WEDGE_STYLE[s.name].label} ${s.panel_count}`,x+19,y);x+=ctx.measureText(`${WEDGE_STYLE[s.name].label} ${s.panel_count}`).width+48;if(x>w-180){x=72;y+=18}});wedgeReadout.textContent=`${c.node_count}节点 / ${c.panel_count}面板 | 闭合误差=${Number(c.closure_error).toExponential(1)}`;}
document.getElementById('wedgeMode').addEventListener('change',drawWedge);

// Figure 4: 3D response surface.
const surfaceCanvas=document.getElementById('surfaceCanvas');
const metricLabels={heave_rao_m_per_m:'升沉RAO (m/m)',pitch_rao_rad_per_wave_slope:'纵摇RAO/波面斜率',point_accel_g:'艏部加速度 (g)'};
function drawSurface(state){
  const {ctx,w,h}=setupCanvas(surfaceCanvas);ctx.clearRect(0,0,w,h);
  const metric=document.getElementById('surfaceMetric').value,rows=DATA.response;
  const xE=[4,12],yE=[2,4],zE=padExtent(extent(rows.map(r=>r[metric])),.12);
  const conv=r=>[map(r.lambda_over_l,...xE,-1.8,1.8),map(r.fn_b,...yE,-1.1,1.1),map(r[metric],...zE,0,2.2)];
  const center=[0,0,1],scale=Math.min(w/5.4,h/4.2);
  const groups=[2,3,4].map(fn=>rows.filter(r=>r.fn_b===fn).sort((a,b)=>a.lambda_over_l-b.lambda_over_l));
  for(let s=0;s<2;s++)for(let i=0;i<groups[s].length-1;i++){
    const poly=[conv(groups[s][i]),conv(groups[s][i+1]),conv(groups[s+1][i+1]),conv(groups[s+1][i])].map(p=>project3(p,state,w,h,scale,center));
    ctx.beginPath();poly.forEach((q,j)=>j?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]));ctx.closePath();
    ctx.fillStyle=s===0?'rgba(8,126,120,.10)':'rgba(53,105,168,.10)';ctx.fill();ctx.strokeStyle='rgba(80,105,112,.24)';ctx.stroke();
  }
  groups.forEach((g,i)=>drawPolyline3(ctx,g.map(conv),state,w,h,scale,center,[COLORS.teal,COLORS.coral,COLORS.blue][i],2.8));
  const axes=[[[ -1.8,-1.1,0],[1.8,-1.1,0]], [[-1.8,-1.1,0],[-1.8,1.1,0]], [[-1.8,-1.1,0],[-1.8,-1.1,2.2]]];
  axes.forEach(a=>drawPolyline3(ctx,a,state,w,h,scale,center,COLORS.ink,1.3));
  const xLabel=project3([1.8,-1.1,0],state,w,h,scale,center),yLabel=project3([-1.8,1.1,0],state,w,h,scale,center),zLabel=project3([-1.8,-1.1,2.2],state,w,h,scale,center);
  ctx.fillStyle=COLORS.ink;ctx.font='13px Microsoft YaHei';ctx.fillText('拖动旋转 · 滚轮缩放',18,27);ctx.fillText(`竖轴：${metricLabels[metric]}，范围 ${nice(zE[0])}–${nice(zE[1])}`,18,50);
  ctx.fillText('λ/L',xLabel[0]+7,xLabel[1]+3);ctx.fillText('Fn_B',yLabel[0]-8,yLabel[1]-8);ctx.fillText('响应',zLabel[0]-12,zLabel[1]-9);
  ctx.fillStyle=COLORS.teal;ctx.fillText('Fn_B=2',w-210,28);ctx.fillStyle=COLORS.coral;ctx.fillText('Fn_B=3',w-140,28);ctx.fillStyle=COLORS.blue;ctx.fillText('Fn_B=4',w-70,28);
}
make3D(surfaceCanvas,drawSurface,{yaw:-.72,pitch:.52,zoom:1});document.getElementById('surfaceMetric').addEventListener('change',()=>surfaceCanvas._sceneDraw());

// Generic 2D chart helpers.
function chartFrame(ctx,w,h,xLabel,yLabel){const m={l:64,r:26,t:58,b:50};ctx.strokeStyle=COLORS.grid;ctx.lineWidth=1;for(let i=0;i<=5;i++){const y=m.t+(h-m.t-m.b)*i/5;ctx.beginPath();ctx.moveTo(m.l,y);ctx.lineTo(w-m.r,y);ctx.stroke()}ctx.strokeStyle=COLORS.ink;ctx.beginPath();ctx.moveTo(m.l,m.t);ctx.lineTo(m.l,h-m.b);ctx.lineTo(w-m.r,h-m.b);ctx.stroke();ctx.fillStyle=COLORS.muted;ctx.font='12px Microsoft YaHei';ctx.fillText(xLabel,w/2-35,h-13);ctx.save();ctx.translate(16,h/2+35);ctx.rotate(-Math.PI/2);ctx.fillText(yLabel,0,0);ctx.restore();return m}
function drawSeriesChart(canvas,series,xKey,yLabel){const {ctx,w,h}=setupCanvas(canvas);ctx.clearRect(0,0,w,h);const all=series.flatMap(s=>s.data),xE=padExtent(extent(all.map(r=>r[xKey])),.02),yE=padExtent(extent(all.map(r=>r.y)),.12),m=chartFrame(ctx,w,h,xKey==='time_s'?'时间 (s)':'λ/L',yLabel);const sx=x=>map(x,...xE,m.l,w-m.r),sy=y=>map(y,...yE,h-m.b,m.t);series.forEach(s=>{ctx.beginPath();s.data.forEach((r,i)=>i?ctx.lineTo(sx(r[xKey]),sy(r.y)):ctx.moveTo(sx(r[xKey]),sy(r.y)));ctx.strokeStyle=s.color;ctx.lineWidth=s.width||2;ctx.stroke();if(s.points){s.data.forEach(r=>{ctx.beginPath();ctx.arc(sx(r[xKey]),sy(r.y),r.open?4:3,0,Math.PI*2);ctx.fillStyle=r.open?'#fff':s.color;ctx.fill();ctx.strokeStyle=s.color;ctx.stroke()})}});ctx.font='11px Microsoft YaHei';ctx.fillStyle=COLORS.muted;for(let i=0;i<=4;i++){const x=xE[0]+(xE[1]-xE[0])*i/4;ctx.fillText(nice(x,1),sx(x)-9,h-m.b+18)}for(let i=0;i<=5;i++){const y=yE[0]+(yE[1]-yE[0])*i/5;ctx.fillText(nice(y,Math.abs(yE[1])<.1?3:2),5,sy(y)+4)}let lx=m.l+8,ly=21;series.filter(s=>s.name).forEach(s=>{const width=25+ctx.measureText(s.name).width+28;if(lx+width>w-m.r){lx=m.l+8;ly+=18}ctx.strokeStyle=s.color;ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(lx,ly);ctx.lineTo(lx+20,ly);ctx.stroke();ctx.fillStyle=COLORS.ink;ctx.fillText(s.name,lx+25,ly+4);lx+=width})}

// Figure 5: closed Delft 372 offsets mesh and matching B2 measured first harmonic.
const motionCanvas=document.getElementById('motionCanvas'),timeSlider=document.getElementById('timeSlider'),motionScale=document.getElementById('motionScale'),motionReadout=document.getElementById('motionReadout');let playing=false,lastTick=0;
function fillPolygon3(ctx,points,state,w,h,scale,center,color,stroke='rgba(255,255,255,.16)'){const q=points.map(p=>project3(p,state,w,h,scale,center));ctx.beginPath();q.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fillStyle=color;ctx.fill();ctx.strokeStyle=stroke;ctx.lineWidth=.35;ctx.stroke();return q.reduce((sum,p)=>sum+p[2],0)/q.length}
function delftWaveZ(x,t){const c=DATA.delft372.selected_test,lambda=c.wavelength_over_lpp*3,k=2*Math.PI/lambda;return .01*c.wave_amplitude_cm*Math.cos(c.omega_encounter_rad_s*t+k*x)}
function delftPoint(vertex,row,mult){let x=vertex.x_m-DATA.delft372.lcg_from_ap_m,y=vertex.y_m,z=vertex.z_up_m;const rx=row.roll_deg*Math.PI/180*mult,ry=row.pitch_deg*Math.PI/180*mult,rz=row.yaw_deg*Math.PI/180*mult;const cx=Math.cos(rx),sx=Math.sin(rx),cy=Math.cos(ry),sy=Math.sin(ry),cz=Math.cos(rz),sz=Math.sin(rz);let y1=cx*y-sx*z,z1=sx*y+cx*z;let x2=cy*x+sy*z1,z2=-sy*x+cy*z1;let x3=cz*x2-sz*y1,y3=sz*x2+cz*y1;return [x3+row.surge_m*mult,y3+row.sway_m*mult,z2+row.heave_m*mult]}
function drawMotion(state){
  const {ctx,w,h}=setupCanvas(motionCanvas);ctx.clearRect(0,0,w,h);ctx.fillStyle='#f7faf9';ctx.fillRect(0,0,w,h);
  const row=DATA.delft372.time[+timeSlider.value],mult=+motionScale.value,scale=Math.min(w/6.6,h/2.8),center=[.12,0,-.03],xMin=-2.8,xMax=3.2,yMin=-1.35,yMax=1.35;
  for(let j=0;j<=4;j++){const y=map(j,0,4,yMin,yMax);drawPolyline3(ctx,[[xMin,y,0],[xMax,y,0]],state,w,h,scale,center,'rgba(93,108,116,.20)',.8)}
  for(let j=0;j<=6;j++){const x=map(j,0,6,xMin,xMax);drawPolyline3(ctx,[[x,yMin,0],[x,yMax,0]],state,w,h,scale,center,'rgba(93,108,116,.18)',.7)}
  const wx=32,wy=10,wave=[];for(let ix=0;ix<=wx;ix++){const x=map(ix,0,wx,xMin,xMax),line=[];for(let iy=0;iy<=wy;iy++){const y=map(iy,0,wy,yMin,yMax);line.push([x,y,delftWaveZ(x,row.time_s)])}wave.push(line)}
  for(let ix=0;ix<wx;ix++)for(let iy=0;iy<wy;iy++)fillPolygon3(ctx,[wave[ix][iy],wave[ix+1][iy],wave[ix+1][iy+1],wave[ix][iy+1]],state,w,h,scale,center,'rgba(53,105,168,.10)','rgba(53,105,168,.16)');
  wave.forEach((line,ix)=>{if(ix%4===0)drawPolyline3(ctx,line,state,w,h,scale,center,'rgba(53,105,168,.72)',.9)});for(let iy=0;iy<=wy;iy+=2)drawPolyline3(ctx,wave.map(line=>line[iy]),state,w,h,scale,center,'rgba(53,105,168,.72)',.9);
  const transformed=DATA.delft372.vertices.map(v=>delftPoint(v,row,mult)),polys=DATA.delft372.faces.map(f=>{const tri=[transformed[f.vertex_0],transformed[f.vertex_1],transformed[f.vertex_2]],centroid=[(tri[0][0]+tri[1][0]+tri[2][0])/3,(tri[0][1]+tri[1][1]+tri[2][1])/3,(tri[0][2]+tri[1][2]+tri[2][2])/3],depth=tri.map(p=>project3(p,state,w,h,scale,center)[2]).reduce((a,b)=>a+b,0)/3;return {tri,depth,wet:centroid[2]<=delftWaveZ(centroid[0],row.time_s)}});
  polys.sort((a,b)=>a.depth-b.depth).forEach(p=>fillPolygon3(ctx,p.tri,state,w,h,scale,center,p.wet?'rgba(6,105,113,.86)':'rgba(197,205,208,.94)',p.wet?'rgba(215,240,238,.28)':'rgba(55,67,73,.32)'));
  ctx.font='12px Microsoft YaHei';ctx.fillStyle=COLORS.blue;ctx.fillText('蓝色：试验8720瞬时规则波面',18,25);ctx.fillStyle=COLORS.teal;ctx.fillText('蓝绿色：三角面中心位于波面以下',18,45);ctx.fillStyle=COLORS.muted;ctx.fillText('浅灰色：三角面中心位于波面以上',18,65);ctx.fillStyle=COLORS.ink;ctx.fillText(`真实网格 ${DATA.delft372.audit.vertex_count}顶点 / ${DATA.delft372.audit.face_count}三角面；运动显示 ${mult}×`,18,h-17);
  motionReadout.textContent=`t=${row.time_s.toFixed(3)} s | wave=${(1000*row.wave_elevation_at_cg_m).toFixed(1)} mm | heave=${(1000*row.heave_m).toFixed(1)} mm | pitch=${row.pitch_deg.toFixed(2)}° | roll=${row.roll_deg.toFixed(2)}°`;
}
make3D(motionCanvas,drawMotion,{yaw:-.68,pitch:.42,zoom:1});timeSlider.addEventListener('input',()=>motionCanvas._sceneDraw());motionScale.addEventListener('change',()=>motionCanvas._sceneDraw());document.getElementById('playButton').addEventListener('click',()=>{playing=!playing;document.getElementById('playButton').textContent=playing?'暂停':'播放';if(playing){lastTick=performance.now();requestAnimationFrame(animate)}});function animate(now){if(!playing)return;const dt=now-lastTick;if(dt>32){timeSlider.value=(+timeSlider.value+1)%DATA.delft372.time.length;lastTick=now;motionCanvas._sceneDraw()}requestAnimationFrame(animate)}

// Figure 6: six DOF mini panels.
const sixDefs=[['纵荡 surge','mm','surge_m',1000],['横荡 sway','mm','sway_m',1000],['升沉 heave','mm','heave_m',1000],['横摇 roll','deg','roll_deg',1],['纵摇 pitch','deg','pitch_deg',1],['艏摇 yaw','deg','yaw_deg',1]];const sixGrid=document.getElementById('sixGrid');sixDefs.forEach((d,i)=>{const div=document.createElement('div');div.className='mini-panel';div.innerHTML=`<h4>${d[0]} <span class="solved-tag">B2实测谐波</span></h4><canvas id="dof${i}"></canvas>`;sixGrid.appendChild(div)});
function drawSix(){sixDefs.forEach((d,i)=>{const arr=DATA.delft372.time.map(r=>({time_s:r.time_s,y:d[3]*r[d[2]]}));drawSeriesChart(document.getElementById(`dof${i}`),[{name:d[1],color:COLORS.teal,data:arr}], 'time_s',d[1])})}

// Figure 7: detailed time series.
const timeCanvas=document.getElementById('timeCanvas');
function drawTime(){const mode=document.getElementById('timeMetric').value;if(mode==='motion'){drawSeriesChart(timeCanvas,[{name:'波面 mm',color:COLORS.blue,data:DATA.time.map(r=>({time_s:r.time_s,y:1000*r.wave_elevation_m}))},{name:'升沉 mm',color:COLORS.teal,data:DATA.time.map(r=>({time_s:r.time_s,y:1000*r.heave_m}))},{name:'纵摇 deg',color:COLORS.coral,data:DATA.time.map(r=>({time_s:r.time_s,y:r.pitch_rad*180/Math.PI}))}], 'time_s','混合显示：mm / deg')}else{drawSeriesChart(timeCanvas,[{name:'重心加速度',color:COLORS.teal,data:DATA.time.map(r=>({time_s:r.time_s,y:r.heave_accel_mps2}))},{name:'艏部点加速度',color:COLORS.coral,data:DATA.time.map(r=>({time_s:r.time_s,y:r.point_vertical_accel_mps2}))}], 'time_s','加速度 (m/s²)')}}document.getElementById('timeMetric').addEventListener('change',drawTime);

// Figure 8: frequency curves.
const frequencyCanvas=document.getElementById('frequencyCanvas');
function drawFrequency(){const metric=document.getElementById('frequencyMetric').value;const series=[2,3,4].map(fn=>({name:`Fn_B=${fn}`,color:SPEED_COLORS[String(fn)],data:DATA.response.filter(r=>r.fn_b===fn).sort((a,b)=>a.lambda_over_l-b.lambda_over_l).map(r=>({lambda_over_l:r.lambda_over_l,y:r[metric]}))}));drawSeriesChart(frequencyCanvas,series,'lambda_over_l',metricLabels[metric])}document.getElementById('frequencyMetric').addEventListener('change',drawFrequency);

// Figure 9: model vs experiment.
const comparisonCanvas=document.getElementById('comparisonCanvas');
function drawComparison(){const metric=document.getElementById('comparisonMetric').value;const series=[];[1.67,2.26,2.82].forEach(fn=>{const rows=DATA.begovic.filter(r=>r.fn_b===fn).sort((a,b)=>a.lambda_over_l-b.lambda_over_l),candidate=DATA.gate2_candidate_points.filter(r=>r.fn_b===fn).sort((a,b)=>a.lambda_over_l-b.lambda_over_l),color=SPEED_COLORS[String(fn)],baseKey=metric==='heave'?'heave_rao_m_per_m':'pitch_rao_rad_per_wave_slope',refKey=metric==='heave'?'reference_heave_rao_m_per_m':'reference_pitch_rao_rad_per_wave_slope';series.push({name:`基线 ${fn}`,color:'#8a949b',width:1.2,data:rows.map(r=>({lambda_over_l:r.lambda_over_l,y:r[baseKey]}))});series.push({name:`候选 ${fn}`,color,width:2.5,data:candidate.map(r=>({lambda_over_l:r.lambda_over_l,y:r[baseKey]}))});series.push({name:`试验 ${fn}`,color,points:true,width:0,data:rows.map(r=>({lambda_over_l:r.lambda_over_l,y:r[refKey],open:!r.linear_gate_eligible}))})});drawSeriesChart(comparisonCanvas,series,'lambda_over_l',metric==='heave'?'升沉RAO':'纵摇RAO/波面斜率')}document.getElementById('comparisonMetric').addEventListener('change',drawComparison);

function redrawAll(){drawAngle();wigleyCanvas._sceneDraw();drawWedge();surfaceCanvas._sceneDraw();motionCanvas._sceneDraw();drawSix();drawTime();drawFrequency();drawComparison()}
window.addEventListener('resize',()=>requestAnimationFrame(redrawAll));redrawAll();
</script>
</body>
</html>'''


def build_html(payload: dict[str, object]) -> str:
    tables = build_summary_tables(payload)
    source_files = [
        GATE1_DIR / "gate1_coefficients_comparison.csv",
        GATE2_DIR / "three_speed_frequency_response.csv",
        GATE2_DIR / "representative_regular_wave_timeseries.csv",
        GATE2_DIR / "begovic_efd_comparison.csv",
        GATE2_DIR / "fridsma_table2_comparison.csv",
        *[
            directory / filename
            for directory in WEDGE_CASE_DIRS.values()
            for filename in ("coupled_boundary_nodes.csv", "coupled_checkpoint.json")
        ],
        DELFT372_DIR / "delft372_catamaran_full_vertices.csv",
        DELFT372_DIR / "delft372_catamaran_full_faces.csv",
        DELFT372_DIR / "delft372_catamaran_mesh_audit.json",
        DELFT372_DIR / "delft372_head_sea_180deg_motions.csv",
        DELFT372_DIR / "delft372_test_8720_measured_first_harmonic.csv",
        WEDGE_VALIDATION_DIR / "wedge_entry_public_validation.json",
        WEDGE_VALIDATION_DIR / "wedge_entry_public_validation.png",
        GATE2_CANDIDATE_DIR / "candidate_begovic_comparison.csv",
        GATE2_CANDIDATE_DIR / "gate2_frequency_candidate_summary.json",
    ]
    hash_lines = "<br>".join(
        f"{path.relative_to(ROOT).as_posix()}　SHA-256={sha256(path)}" for path in source_files
    )
    data_payload = {key: value for key, value in payload.items() if key != "wedge_validation_image"}
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(data_payload, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__WEDGE_VALIDATION_IMAGE__", str(payload["wedge_validation_image"]))
    for key, value in tables.items():
        html = html.replace(f"__{key.upper()}__", value)
    return html.replace("__HASHES__", hash_lines)


def build_markdown() -> str:
    return """# 高速船型运动预报系统：真实几何与定量验证进展报告

日期：2026-09-13  
主报告：`report.html`（完全自包含，含真实网格、三维动画、六自由度、频域与定量验证）

## 1. 本轮完成的三项工作

| 工作包 | 数据或案例 | 当前结果 | 证据边界 |
| --- | --- | --- | --- |
| 真实船型 | Delft 372双体船，B2公开23个横剖面及艏轮廓 | 两个封闭片体共1552顶点、3096三角面；开边、非流形边、退化面均为0 | 片体外壳真实；连接桥/上层建筑无公开offsets，当前尚未由多体2.5D求解器预测运动 |
| 楔形入水 | 20°自相似楔形，Iafrati与Zhao–Faltinsen公开参考 | 自由面、压力、峰值、峰位置、积分力5/5通过 | 属于公开数值基准，不冒充实验验证 |
| Gate 2推进 | Begovic三航速规则迎浪 | 升沉中位误差29.79%→15.40%；纵摇34.16%→22.05%；最大已解析峰频误差31.88%→11.60% | 明显改善但总体仍为FAIL |

## 2. Delft 372真实船体与运动数据

船体网格由B2报告offsets直接放样，坐标范围为`x=0–3.0435 m`、`y=±0.47 m`、`z=-0.15–0.05 m`。左右片体中心线间距0.70 m，总宽0.94 m。拓扑审计为：开边0、非流形边0、退化面0、连通分量2。这里的“封闭”专指两个片体均为水密三角网格；报告没有给出连接桥和上层建筑的数字型线，因此本轮没有虚构这些结构。

图5使用同一B2报告180°迎浪试验8720：航速3.347 m/s、波幅1.79 cm、遭遇圆频率7.964 rad/s。六自由度曲线由公开一阶谐波幅值和相位重构，不是原始采样时序，也不是当前模型预测。

## 3. 20°楔形入水定量结果

| 验证量 | 误差 | 限值 | 结果 |
| --- | ---: | ---: | --- |
| 外自由面形状NRMSE | 7.31% | 10% | PASS |
| 压力分布NRMSE | 9.98% | 15% | PASS |
| 压力峰值 | 3.26% | 10% | PASS |
| 压力峰位置 | 5.69% | 10% | PASS |
| 积分垂向力系数 | 3.89% | 10% | PASS |

参考垂向力系数由公开压力曲线独立积分得到42.71，程序结果为41.05。Aarsnes 30°自由落体实验仍是下一道实验验证门；现有文献明确说明其压力测量质量不足，不能据此编造压力对照。

## 4. Gate 2频率相关候选

候选固定采用Ma型内外域匹配边界积分、完整压力项、0.5倍梁宽艉部修正、站位相位激励与实测遭遇频率坐标，三个航速参数完全一致，不使用经验响应倍率。高航速`Fn_B=2.82`的升沉和纵摇均通过；但低速过渡工况、纵摇耦合、内核自身基准验证以及峰频10%门槛仍未闭合，因此不会替换17/20的锁定基线。

## 5. 下一阶段验收目标

1. matched-BIE频率相关内核通过Wigley/椭球双网格独立基准。
2. Begovic三航速升沉与纵摇中位相对误差均不超过15%，NRMSE均不超过20%。
3. 四个已解析主峰频率误差全部不超过10%。
4. 全过程不得使用响应倍率或从目标响应反推系数。
5. 通过后再接入Delft 372双体共同边界系统，计算cross-radiation与cross-diffraction。
"""


def main() -> None:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUT_DIR / "report.html"
    markdown_path = OUT_DIR / "report.md"
    html_path.write_text(build_html(payload), encoding="utf-8")
    markdown_path.write_text(build_markdown(), encoding="utf-8")
    print(html_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
