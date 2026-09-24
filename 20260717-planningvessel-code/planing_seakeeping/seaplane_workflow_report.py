"""Offline, data-driven reporting for the bounded zero-speed seaplane case."""

import base64
import csv
import html
import json
from pathlib import Path

import numpy as np


SCOPE = (
    "EDO106k原表底部偏移约束插值的参数化假设闭合模型，非实测密集网格或真实完整浮筒；"
    "垂直舷侧与平甲板为明确假设；"
    "合成质量模型；零航速纵向线性静水条带降阶研究闭环。"
    "不是完整2.5D水动力、完整起降或实验验证。"
    "六自由度中仅升沉与艏升纵摇参与计算，其余纵荡、横荡、横摇、艏摇受约束，非预测结果。"
)
TIME_COLUMNS = (
    "time_s", "wave_m", "heave_m", "pitch_rad", "cg_accel_mps2", "bow_accel_mps2", "energy_J",
)


def _format(value) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (float, np.floating)):
        return f"{value:.6g}"
    return str(value)


def _table(headers, rows) -> str:
    head = "".join(f"<th>{html.escape(str(item))}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(_format(item))}</td>" for item in row) + "</tr>"
        for row in rows
    )
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _read_csv(path: Path, columns, text_columns=()) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(columns).issubset(reader.fieldnames):
            raise ValueError(f"{path.name}: missing required columns {columns!r}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path.name}: empty data")
    data = {}
    for name in columns:
        data[name] = [row[name] for row in rows] if name in text_columns else np.asarray(
            [float(row[name]) for row in rows], dtype=float,
        )
        if name not in text_columns and not np.isfinite(data[name]).all():
            raise ValueError(f"{path.name}: nonfinite {name}")
    if "time_s" in data and (len(data["time_s"]) < 2 or np.any(np.diff(data["time_s"]) <= 0)):
        raise ValueError(f"{path.name}: time must strictly increase with at least two samples")
    return data


def _finite_array(value, shape, name):
    array = np.asarray(value, dtype=float)
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError(f"{name}: expected finite shape {shape}")
    return array


def _rms(data, key):
    return float(np.sqrt(np.mean(data[key] ** 2)))


def write_report(out: Path) -> dict[str, Path]:
    """Read the supplied workflow contract and write reports and static figures.

    All source files must already exist. No solver, acceptance threshold, source
    data, or historical output is modified. Statistics include every input row;
    they are full-record sample RMS, not transient-discarded steady-state fits.
    """

    out = Path(out)
    required = ("model.json", "acceptance.json", "geometry.npz", "regular.csv",
                "irregular.csv", "decay.csv", "rao.csv", "sensitivity.csv", "input_snapshot.json")
    missing = [name for name in required if not (out / name).is_file()]
    if missing:
        raise FileNotFoundError("Report inputs missing: " + ", ".join(missing))
    model = json.loads((out / "model.json").read_text(encoding="utf-8"))
    acceptance = json.loads((out / "acceptance.json").read_text(encoding="utf-8"))
    snapshot = json.loads((out / "input_snapshot.json").read_text(encoding="utf-8"))
    wave_height = float(snapshot["workflow"]["regular_wave_height_m"])
    wave_period = float(snapshot["workflow"]["regular_wave_period_s"])
    gravity = float(snapshot["base"]["environment_assumed"]["gravity_m_s2"])
    if not np.isfinite([wave_height, wave_period, gravity]).all() or wave_height < 0 or min(wave_period, gravity) <= 0:
        raise ValueError("Snapshot wave height must be nonnegative; period/gravity must be finite and positive")
    wave_amplitude = wave_height / 2
    omega = 2*np.pi/wave_period
    k = omega**2/gravity
    cg = _finite_array(model["mass"]["cg_m"], (3,), "cg_m")
    inertia = _finite_array(model["mass"]["inertia_cg_kg_m2"], (3, 3), "inertia")
    matrices = {name: _finite_array(model[name], (2, 2), name) for name in ("M", "A", "B", "C")}
    equilibrium = model["equilibrium"]
    theta, cgheight = float(equilibrium["pitch_rad"]), float(equilibrium["cg_height_m"])
    if not np.isfinite([theta, cgheight, model["mass"]["mass_kg"], *equilibrium.values()]).all():
        raise ValueError("Model mass/equilibrium must be finite")
    periods = np.asarray(model["natural_periods_s"], dtype=float)
    if periods.ndim != 1 or not len(periods) or not np.isfinite(periods).all() or np.any(periods <= 0):
        raise ValueError("Natural periods must be finite and positive")
    with np.load(out / "geometry.npz", allow_pickle=False) as geometry:
        vertices = np.asarray(geometry["vertices_m"], dtype=float)
        triangles = np.asarray(geometry["triangles"])
        kinds = np.asarray(geometry["face_kind"])
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices) or not np.isfinite(vertices).all():
        raise ValueError("Invalid geometry vertices")
    if (triangles.ndim != 2 or triangles.shape[1] != 3 or not len(triangles)
            or not np.issubdtype(triangles.dtype, np.integer)
            or np.any(triangles < 0) or np.any(triangles >= len(vertices))
            or kinds.shape != (len(triangles),) or not np.isin(kinds, [0, 1]).all()):
        raise ValueError("Invalid triangles/face_kind")
    records = {name: _read_csv(out / f"{name}.csv", TIME_COLUMNS) for name in ("regular", "irregular", "decay")}
    rao = _read_csv(out / "rao.csv", ("period_s", "heave_m_per_m", "pitch_rad_per_m", "heave_phase_deg", "pitch_phase_deg"))
    sensitivity = _read_csv(out / "sensitivity.csv", ("case", "mass_kg", "heave_rms_m", "pitch_rms_rad", "cg_accel_rms_mps2"), ("case",))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.patches import Patch
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    figures = out / "figures"
    figures.mkdir(exist_ok=True)
    sections = []
    title = "EDO106k底部约束参数化假设闭合模型：零航速纵向研究闭环"

    def section(heading, text, table=""):
        sections.append((heading, f"<p>{html.escape(text)}</p>{table}", text + "\n\n" + table))

    def save_figure(fig, stem, heading, explanation):
        png_path = figures / f"{stem}.png"
        pdf_path = figures / f"{stem}.pdf"
        svg_path = figures / f"{stem}.svg"
        try:
            fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
            fig.savefig(pdf_path, dpi=300, bbox_inches="tight", facecolor="white")
            fig.savefig(svg_path, dpi=300, bbox_inches="tight", facecolor="white")
        finally:
            plt.close(fig)
        encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
        image = f"<img alt='{html.escape(heading, quote=True)}' src='data:image/png;base64,{encoded}'>"
        body = image + f"<p class='caption'>{html.escape(explanation)}</p>"
        sections.append((heading, body, body))

    checks = acceptance["checks"]
    passed_count = sum(check["passed"] is True for check in checks)
    section("研究范围与状态", SCOPE + " 报告仅转述输入验收状态，不新增或改变验收门槛。", _table(
        ("状态项", "输入值"), (
            ("数值状态", acceptance["numerical_status"]),
            ("物理验证状态", acceptance["physical_validation_status"]),
            ("输入检查通过数", f"{passed_count}/{len(checks)}"),
        ),
    ))
    section("参数缺口如何补入", "采用明确假设让这个受约束子问题可计算，不采用响应倍率拟合。质量、重心和惯性来自同一六部件模型；静水姿态通过力和力矩平衡求解；附加质量和阻尼仅是研究近似。基础配置中的高速入水、气动、推进字段未在零航速子问题调用，不能将其配置存在理解为整机起降已求解。", _table(
        ("缺口", "处理", "身份"), (
            ("侧面、甲板和封口", "原型值折角处垂直向上，至表列甲板高度封平；保留断阶", "几何假设"),
            ("总质量、重心、惯性", "六部件等效长方体，按平行轴定理装配", "合成研究机，非实测"),
            ("平均姿态、浸深", "解浮力等于重量及重心处纵摇力矩为零", "该假设壳体的计算结果"),
            ("附加质量", "每米条带 πρc²/2，c为平衡水线半宽", "未验证近似，不是边界元输出"),
            ("阻尼", "模态阻尼比取配置值，并作参数敏感性", "假设，不是试验拟合"),
            ("波浪载荷", "入射波高产生的静水增量，保留纵向相位", "无完整绕射/辐射记忆"),
        ),
    ))
    section("实际模型与静水平衡", "CG和惯性来自合成分量模型；原表CG坐标与平衡后的CG高度分别列出，不能混用。", _table(
        ("量", "实际值", "单位/解释"), (
            ("质量", model["mass"]["mass_kg"], "kg"), ("原表CG", cg.tolist(), "m；x艉/y右/z上"),
            ("平衡CG高度", cgheight, "m；静水面z=0"), ("平衡艏升角", np.degrees(theta), "度"),
            ("排水体积", equilibrium["volume_m3"], "m³"),
            ("竖向力相对残差", equilibrium["force_residual_rel"], "输入定义"),
            ("俯仰矩相对残差", equilibrium["moment_residual_rel"], "输入定义"),
            ("自然周期", periods.tolist(), "s；模态周期，不强行标为独立升沉/纵摇周期"),
        ),
    ) + _table(("CG惯性行", "Ixx/Ixy/Ixz或对应行 [kg·m²]"), enumerate(inertia.tolist(), 1)))
    section("矩阵与假设", "自由度顺序为升沉向上、艏升纵摇。M为刚体广义质量；A、B必须按输入假设理解，不表示已计算真实航速水动力。C为平衡附近恢复矩阵。", "".join(
        _table((name, "升沉列", "纵摇列"), (("升沉行", *matrix[0]), ("纵摇行", *matrix[1])))
        for name, matrix in matrices.items()
    ) + _table(("假设编号", "输入假设"), enumerate(model["assumptions"], 1))
    + _table(("矩阵", "四元素单位（按行）"), (
        ("M/A", "kg, kg·m; kg·m, kg·m²"), ("B", "kg/s, kg·m/s; kg·m/s, kg·m²/s"),
        ("C", "N/m, N/rad; N·m/m, N·m/rad"),
    )))
    section("本示例数值检查：独立于既有实验门", "下表完整保留本示例的检查值、预设门槛与passed布尔值；数值PASS不等于物理或实验验证，不替代也不改变旧线性、整船或楔形实验门。", _table(
        ("检查", "值", "预设门槛", "通过"), ((c["name"], c["value"], c["limit"], c["passed"]) for c in checks),
    ))
    section("坐标与可复核变换", f"原表xs向艉、ys向右舷、zs向上：X=cgx-xs，Z=zs-cgz；earthXe=cos(theta)X-sin(theta)Z；earthZe=cgheight+sin(theta)X+cos(theta)Z；可视化y=-ys，形成右手x前/y左/z上坐标。图采用平衡姿态，q为其上的扰动。规定波参数来自input_snapshot.json：H={wave_height:.6g} m、T={wave_period:.6g} s、g={gravity:.6g} m/s²；omega=2π/T，k=omega²/g={k:.6g} 1/m，eta=(H/2)cos(k·earthXe+omega·t)，本图t=0；它不是计算扰动自由面。")
    section("全记录统计", "所有时历统计使用完整输入记录，包含启动瞬态；RMS为样本sqrt(mean(x²))，不是去均值标准差，也不是稳态拟合误差。", _table(
        ("记录", "样本数", "时段 [s]", "升沉RMS [m]", "纵摇RMS [度]", "CG加速度RMS [m/s²]", "艏加速度最大绝对值 [m/s²]"),
        ((name, len(d["time_s"]), [float(d["time_s"][0]), float(d["time_s"][-1])], _rms(d, "heave_m"),
          np.degrees(_rms(d, "pitch_rad")), _rms(d, "cg_accel_mps2"), float(np.max(np.abs(d["bow_accel_mps2"]))))
         for name, d in records.items()),
    ))

    with plt.rc_context({"font.family": "sans-serif", "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                         "axes.unicode_minus": False, "svg.fonttype": "none", "pdf.fonttype": 42,
                         "font.size": 10, "axes.spines.top": False, "axes.spines.right": False}):
        x = cg[0] - vertices[:, 0]
        z = vertices[:, 2] - cg[2]
        earth = np.column_stack((np.cos(theta)*x - np.sin(theta)*z, -vertices[:, 1],
                                 cgheight + np.sin(theta)*x + np.cos(theta)*z))
        span = np.ptp(earth, axis=0)
        low, high = earth.min(axis=0), earth.max(axis=0)
        wave_x = np.linspace(low[0] - 0.1*span[0], high[0] + 0.1*span[0], 160)
        wave_y = np.linspace(low[1] - 0.15*max(span[1], .1), high[1] + 0.15*max(span[1], .1), 35)
        wx, wy = np.meshgrid(wave_x, wave_y)
        wz = wave_amplitude*np.cos(k*wx)
        fig = plt.figure(figsize=(12, 8), layout="constrained")
        ax = fig.add_subplot(211, projection="3d")
        side = fig.add_subplot(212)
        colors = {0: "#23836e", 1: "#c99354"}
        for kind in (0, 1):
            faces = earth[triangles[kinds == kind]]
            if len(faces):
                ax.add_collection3d(Poly3DCollection(faces, facecolors=colors[kind], edgecolors="#555555", linewidths=.15, alpha=.85))
                side.add_collection(PolyCollection(faces[:, :, [0, 2]], facecolors=colors[kind], edgecolors="none", alpha=.55))
        ax.plot_surface(wx, wy, wz, color="#609dcc", alpha=.32, linewidth=0)
        ax.scatter([0], [-cg[1]], [cgheight], color="#b52f38", s=30)
        ax.set(xlabel="相对CG前向位置 [m]", ylabel="左舷位置 y=-ys [m]", zlabel="静水面以上高度 [m]")
        ax.set_xlim(wave_x[0], wave_x[-1]); ax.set_ylim(wave_y[0], wave_y[-1])
        zmin, zmax = min(low[2], -wave_amplitude), max(high[2], cgheight, wave_amplitude)
        ax.set_zlim(zmin, zmax)
        ax.set_box_aspect([wave_x[-1]-wave_x[0], wave_y[-1]-wave_y[0], zmax-zmin])
        ax.view_init(elev=18, azim=-58)
        ax.set_axis_off()
        ax.set_title(f"(a) 全长{np.ptp(vertices[:, 0]):.3f} m，真实米制比例；同源规定波与假设封闭面", fontsize=11)
        side.plot(wave_x, wave_amplitude*np.cos(k*wave_x), color="#3d7daa", label="同源规定入射波 t=0")
        side.axhline(0, color="#444444", ls="--", lw=.8, label="静水面")
        side.scatter([0], [cgheight], color="#b52f38", label="平衡CG")
        side.autoscale_view(); side.set_aspect("equal", adjustable="box")
        side.set(xlabel="相对CG前向位置 [m]", ylabel="高度 [m]")
        side.set_title("(b) 完整纵向投影：米制尺寸、平衡CG与同源规定波", fontsize=11)
        side.legend(handles=[Patch(color=colors[0], label="原表约束插值底面"), Patch(color=colors[1], label="假设封闭面"), *side.get_legend_handles_labels()[0]], ncol=3, fontsize=9)
        save_figure(fig, "geometry_water", "图1：底部约束参数化假设闭合模型、假设面与同源规定波", f"(a) 完整静态三维全景，全长{np.ptp(vertices[:, 0]):.3f} m，不放大裁切；隐藏三维轴以避免刻度拥挤。(b) 完整纵向米制投影，尺寸可由下图坐标读取，CG红点采用平衡后的高度。显示全部{len(vertices)}个顶点、{len(triangles)}个三角面，其中底面{int(np.sum(kinds == 0))}个、假设面{int(np.sum(kinds == 1))}个。绿色为原表偏移约束的插值底面，非实测密集网格；棕色为假设封闭面，这不是真实完整浮筒。几何未人为变形以匹配水线，三维范围按实际米制等比例设置，不夸张z高度，也不添加无来源机翼或飞机外形。蓝色水面使用快照中的H={wave_height:.6g} m、T={wave_period:.6g} s、g={gravity:.6g} m/s²规定入射波；未计算绕射、辐射、砰击或扰动自由面。")

        fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout="constrained")
        for ax, key, label in zip(axes.flat, ("heave_m_per_m", "pitch_rad_per_m", "heave_phase_deg", "pitch_phase_deg"),
                                  ("升沉RAO [m/m]", "纵摇RAO [rad/m]", "升沉相位 [度]", "纵摇相位 [度]")):
            ax.plot(rao["period_s"], rao[key], color="#23836e", marker="."); ax.set(xlabel="周期 [s]", ylabel=label); ax.grid(alpha=.2)
        for ax, label in zip(axes.flat, ("(a) 升沉幅值", "(b) 纵摇幅值", "(c) 升沉相位", "(d) 纵摇相位")):
            ax.set_title(label)
        peak = int(np.argmax(rao["heave_m_per_m"]))
        save_figure(fig, "rao", "图2：降阶模型频域响应", f"(a) 单位波幅下的升沉响应幅值；(b) 单位波幅下的艏升纵摇幅值，单位rad/m，不能与升沉幅值直接比较大小。(c) 升沉响应相位；(d) 纵摇响应相位，均直接读取输入相位定义，相位变化描述响应与规定激励的相对时序。若存在角度包络跳变，不应解释为运动幅值突变；本报告不自行展开相位或改变正负约定。展示rao.csv全部{len(rao['period_s'])}个周期点。样本内升沉RAO最大值为{rao['heave_m_per_m'][peak]:.6g} m/m，发生于{rao['period_s'][peak]:.6g} s；这只是离散扫频峰，不是连续共振频率的独立验证。相位时频一致性以acceptance.json的原检查为准。")
        for name, label in (("regular", "规则波"), ("irregular", "不规则波"), ("decay", "自由衰减")):
            d = records[name]
            fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True, layout="constrained")
            axes[0].plot(d["time_s"], d["wave_m"], label="规定波面", color="#3d7daa")
            axes[0].plot(d["time_s"], d["heave_m"], label="升沉扰动", color="#23836e"); axes[0].set_ylabel("位移 [m]"); axes[0].legend()
            axes[1].plot(d["time_s"], np.degrees(d["pitch_rad"]), color="#a36337"); axes[1].set_ylabel("艏升纵摇扰动 [度]")
            axes[2].plot(d["time_s"], d["cg_accel_mps2"], label="CG", color="#23836e")
            axes[2].plot(d["time_s"], d["bow_accel_mps2"], label="艏部", color="#b52f38"); axes[2].set_ylabel("垂向加速度 [m/s²]"); axes[2].legend()
            axes[3].plot(d["time_s"], d["energy_J"], color="#555555"); axes[3].set(xlabel="时间 [s]", ylabel="振动机械能 [J]")
            for ax, panel in zip(axes, ("(a) 波面与升沉", "(b) 艏升纵摇", "(c) CG与艏部垂向加速度", "(d) 机械能")):
                ax.set_title(panel)
            for ax in axes: ax.grid(alpha=.2)
            save_figure(fig, name, f"{label}：平衡姿态上的纵向扰动", f"(a) 规定波面与升沉位移的时序；(b) 艏升纵摇角；(c) CG及艏部垂向加速度，艏部结果包含纵摇的运动学贡献；(d) 输入机械能历程。完整显示{len(d['time_s'])}个输入样本，不剔除瞬态。升沉与纵摇是平衡上的扰动，不是绝对吃水与绝对姿态；图中度数由pitch_rad转换。升沉全记录RMS为{_rms(d, 'heave_m'):.6g} m，纵摇RMS为{np.degrees(_rms(d, 'pitch_rad')):.6g}度。CG和艏部加速度直接读取，不在报告中二次差分。输入能量从{d['energy_J'][0]:.6g} J至{d['energy_J'][-1]:.6g} J；受迫记录不应要求能量单调下降，自由衰减稳定性仅依据原验收。规定波面不代表计算扰动自由面。")

        fig, axes = plt.subplots(3, 1, figsize=(11, 8), layout="constrained")
        positions = np.arange(len(sensitivity["case"]))
        for ax, key, label in zip(axes, ("heave_rms_m", "pitch_rms_rad", "cg_accel_rms_mps2"),
                                  ("升沉RMS [m]", "纵摇RMS [rad]", "CG加速度RMS [m/s²]")):
            ax.bar(positions, sensitivity[key], color="#23836e"); ax.set_ylabel(label)
            ax.set_xticks(positions, sensitivity["case"], rotation=25, ha="right", rotation_mode="anchor"); ax.grid(axis="y", alpha=.2)
        for ax, panel in zip(axes, ("(a) 升沉集合谱RMS", "(b) 纵摇集合谱RMS", "(c) CG加速度集合谱RMS")):
            ax.set_title(panel)
        save_figure(fig, "sensitivity", "敏感性：集合谱RMS案例间比较", "(a) 各假设案例的升沉集合谱RMS；(b) 纵摇集合谱RMS；(c) CG垂向加速度集合谱RMS。每个输入案例均保留，以case标签比较已有ensemble_spectral_not_single_record集合谱RMS结果；它不是单条时历的全记录RMS，不能与上文时历统计直接相减解释为误差。这里展示指定质量/参数变化下的数值敏感性，不是置信区间、实验误差或不确定度覆盖率。详细质量和响应见下表；本报告不补算案例，也不解释未提供的参数变化。")
    section("敏感性实际数值", "以下直接读取sensitivity.csv，统计口径为ensemble_spectral_not_single_record（集合谱RMS），不等同于规则/不规则时历的全记录样本RMS，两者不直接比较成误差。案例定义由主工作流负责。", _table(
        ("案例", "质量 [kg]", "升沉RMS [m]", "纵摇RMS [rad]", "CG加速度RMS [m/s²]"),
        zip(*(sensitivity[name] for name in ("case", "mass_kg", "heave_rms_m", "pitch_rms_rad", "cg_accel_rms_mps2"))),
    ))
    section("结论边界", "本交付支持可运行、可复核的数值研究链。是否数值自洽只依输入numerical_status和逐项检查，不因报告生成成功而自动PASS。原表约束插值底面不使假设舷侧、甲板、质量、附加质量或阻尼成为实测参数；该模型不能推出真实飞机起降性能、多浮体干扰或完整六自由度运动。", _table(("读取的源文件",), ((name,) for name in required)))
    css = """body{font-family:'Microsoft YaHei',SimHei,sans-serif;color:#242424;margin:0;background:white;line-height:1.7}main{max-width:1100px;margin:auto;padding:24px}h1{font-size:26px}h2{font-size:20px;border-bottom:1px solid #ddd;padding-bottom:6px}img{max-width:100%;height:auto;display:block;margin:auto}.caption{color:#444}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px;border:1px solid #ddd;text-align:left;overflow-wrap:anywhere}th{background:#f1f4f2}.table-wrap{overflow-x:auto;margin:14px 0}section{margin-bottom:28px}@media print{main{padding:0}img{max-height:230mm;object-fit:contain}tr{break-inside:avoid}h2{break-after:avoid}}"""
    html_path, md_path = out / "report.html", out / "report.md"
    html_path.write_text("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                         f"<title>{title}</title><style>{css}</style></head><body><main><h1>{title}</h1>"
                         + "".join(f"<section><h2>{html.escape(h)}</h2>{body}</section>" for h, body, _ in sections)
                         + "</main></body></html>", encoding="utf-8")
    md_path.write_text(f"# {title}\n\n" + "\n\n".join(f"## {h}\n\n{body}" for h, _, body in sections), encoding="utf-8")
    return {"html": html_path, "markdown": md_path, "figures": figures}
