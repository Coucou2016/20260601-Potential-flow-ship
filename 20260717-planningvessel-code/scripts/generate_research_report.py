from __future__ import annotations

import base64
import html
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.config import load_config


VALIDATION_DIR = ROOT / "outputs" / "validation_report_source"
EXAMPLE_DIR = ROOT / "outputs" / "report_example"
REPORT_DATE = "2026-07-24"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def fmt_cell(value: object) -> str:
    if value is None:
        return "待补充/不适用"
    if isinstance(value, float) and math.isnan(value):
        return "待补充/不适用"
    try:
        if pd.isna(value):
            return "待补充/不适用"
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == 0:
            return "0"
        abs_value = abs(value)
        if abs_value >= 1000 or abs_value < 1.0e-3:
            return f"{value:.3e}"
        return f"{value:.4g}"
    text = str(value)
    return text if text else "待补充/不适用"


def select_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    available = [column for column in columns if column in df.columns]
    return df.loc[:, available].copy() if available else pd.DataFrame()


def format_df(df: pd.DataFrame, max_rows: int | None = None) -> pd.DataFrame:
    out = df.head(max_rows).copy() if max_rows is not None else df.copy()
    for column in out.columns:
        out[column] = out[column].map(fmt_cell)
    return out


def data_uri(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    suffix = path.suffix.lower().lstrip(".")
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{payload}"


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "\n待补充/不适用\n"
    formatted = format_df(df)
    headers = [str(column) for column in formatted.columns]
    rows = formatted.astype(str).values.tolist()
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    out.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(out)


@dataclass
class ReportBuilder:
    table_no: int = 0
    figure_no: int = 0

    def table(self, df: pd.DataFrame, title: str, note: str = "") -> tuple[str, str]:
        self.table_no += 1
        formatted = format_df(df)
        table_id = f"table-{self.table_no}"
        html_table = formatted.to_html(index=False, escape=True, classes="data-table", border=0)
        note_html = f'<p class="table-note">{html.escape(note)}</p>' if note else ""
        html_part = (
            f'<div class="table-wrap" id="{table_id}">'
            f'<p class="table-caption"><strong>表 {self.table_no}</strong> {html.escape(title)}</p>'
            f"{html_table}"
            f"{note_html}"
            "</div>"
        )
        md_part = f"\n**表 {self.table_no} {title}**\n\n{markdown_table(formatted)}\n"
        if note:
            md_part += f"\n说明：{note}\n"
        return html_part, md_part

    def figure(self, path: Path, title: str, explanation_html: str, explanation_md: str) -> tuple[str, str]:
        self.figure_no += 1
        fig_id = f"figure-{self.figure_no}"
        if not path.exists():
            placeholder = "待补充：图像文件未生成。"
            html_part = (
                f'<figure class="figure-card" id="{fig_id}">'
                f'<figcaption><strong>图 {self.figure_no}</strong> {html.escape(title)}</figcaption>'
                f'<div class="missing">{placeholder}</div>{explanation_html}</figure>'
            )
            md_part = f"\n**图 {self.figure_no} {title}**\n\n{placeholder}\n\n{explanation_md}\n"
            return html_part, md_part
        uri = data_uri(path)
        html_part = (
            f'<figure class="figure-card" id="{fig_id}">'
            f'<figcaption><strong>图 {self.figure_no}</strong> {html.escape(title)}</figcaption>'
            f'<img src="{uri}" alt="{html.escape(title)}">'
            f'<div class="figure-explain">{explanation_html}</div>'
            "</figure>"
        )
        md_part = (
            f"\n**图 {self.figure_no} {title}**\n\n"
            f'<img src="{uri}" alt="{html.escape(title)}" />\n\n'
            f"{explanation_md}\n"
        )
        return html_part, md_part


def paragraph(text: str) -> str:
    return f"<p>{html.escape(text)}</p>"


def html_list(items: Iterable[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def load_report_data() -> dict[str, pd.DataFrame]:
    data = {
        "inventory": read_csv(ROOT / "docs" / "materials_inventory.csv"),
        "example_summary": read_csv(EXAMPLE_DIR / "summary.csv"),
        "validation_status": read_csv(VALIDATION_DIR / "validation_status_by_benchmark.csv"),
        "faltinsen_eigen": read_csv(VALIDATION_DIR / "faltinsen_ch9_eigenvalues.csv"),
        "fridsma_residual": read_csv(VALIDATION_DIR / "fridsma_regular_wave_amplitudes_residual_summary.csv"),
        "fridsma_shape": read_csv(VALIDATION_DIR / "fridsma_regular_wave_amplitudes_shape_summary.csv"),
        "fridsma_response": read_csv(VALIDATION_DIR / "fridsma_regular_wave_amplitudes_response_model_summary.csv"),
        "katayama_quality": read_csv(VALIDATION_DIR / "katayama_qualitative_trends_summary.csv"),
        "wigley_coeff": read_csv(VALIDATION_DIR / "ma2005_wigley_iii_coefficients_status_by_coefficient.csv"),
        "sl7_coeff": read_csv(VALIDATION_DIR / "ma2005_sl7_coefficients_status_by_coefficient.csv"),
        "goal_gap": read_csv(VALIDATION_DIR / "goal_gap_audit.csv"),
    }
    return data


def inventory_tables(inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if inventory.empty:
        return pd.DataFrame(), pd.DataFrame()
    category = (
        inventory.groupby("category", dropna=False)
        .agg(files=("relative_path", "count"), size_mb=("size_bytes", lambda s: round(float(s.sum()) / 1_000_000.0, 3)))
        .reset_index()
        .sort_values(["files", "size_mb"], ascending=[False, False])
    )
    extension = (
        inventory.groupby(["category", "extension"], dropna=False)
        .agg(files=("relative_path", "count"), size_mb=("size_bytes", lambda s: round(float(s.sum()) / 1_000_000.0, 3)))
        .reset_index()
        .sort_values(["files", "size_mb"], ascending=[False, False])
        .head(12)
    )
    return category, extension


def example_parameters() -> pd.DataFrame:
    cfg = load_config(ROOT / "configs" / "report_quick_planing.yml")
    return pd.DataFrame(
        [
            ("船型", "深 V 单体滑行艇示例", "用于展示程序输入与输出链路；不是某一公开试验船的严格复刻。"),
            ("总长 L", f"{cfg.boat.length_m:.3g} m", "纵向坐标、波长比与纵摇力臂的基准尺度。"),
            ("型宽 B", f"{cfg.boat.beam_m:.3g} m", "梁宽弗劳德数 Fn_B 的基准尺度，也是滑行受力中常用的尺度。"),
            ("艉横剖面折角 beta", f"{cfg.boat.deadrise_deg:.3g} deg", "表示 V 形底斜升角；角度越大，入水冲击通常越柔和，但动升力分布也会改变。"),
            ("质量", f"{cfg.boat.mass_kg:.4g} kg", "本例按 Faltinsen 第 9 章同类无量纲质量量级设置。"),
            ("重心纵向位置", f"{cfg.boat.lcg_m:.4g} m from transom", "决定静水纵倾平衡和纵摇恢复力矩。"),
            ("迎浪规则波", f"H={cfg.waves.regular_height_m:.3g} m, T={cfg.waves.regular_period_s:.3g} s", "用于时域规则波响应示例。"),
            ("不规则海况", f"Hs={cfg.waves.significant_height_m:.3g} m, Tp={cfg.waves.peak_period_s:.3g} s, JONSWAP gamma={cfg.waves.gamma:.3g}", "用于均方根响应随航速变化的统计图。"),
            ("海流", f"{cfg.environment.current_speed_mps:.3g} m/s, heading={cfg.environment.current_heading_deg:.3g} deg", "作为相对速度修正进入遭遇频率和稳态速度。"),
            ("航速", ", ".join(f"Fn_B={x:.1f}" for x in cfg.simulation.speeds_fn_b), "对应约 9.3、13.9、18.6 m/s 的对比算例。"),
        ],
        columns=["项目", "数值", "说明"],
    )


def method_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            (
                "稳态滑行平衡",
                "Savitsky/Faltinsen 静水滑行平衡",
                "先求静水纵倾、湿长和升沉基准，再把波浪看作围绕该基准的小扰动。",
                "若静水姿态错，后续波浪运动会从错误的湿表面和力臂出发。",
            ),
            (
                "频域纵向运动",
                "2.5D（two-and-a-half-dimensional，二维横剖面沿船长积分并保留航速效应）",
                "解升沉和纵摇的线性矩阵方程，输出响应幅值算子和峰值位置。",
                "这是本阶段最可靠的核心通道，已用 Faltinsen 第 9 章进行对照。",
            ),
            (
                "时域运动",
                "非线性准稳态恢复力 + 常系数辐射/阻尼",
                "对规则波和不规则波进行时间积分，给出 6 自由度统一格式输出。",
                "它能展示冲击风险和湿表面丢失风险，但目前还不能代替实验幅值验证。",
            ),
            (
                "6 自由度输出",
                "[surge, sway, heave, roll, pitch, yaw]",
                "迎浪对称条件下重点求 heave 和 pitch，其余自由度置零并在结果中说明。",
                "保证接口完整，同时避免用未验证横向半经验公式填充结果。",
            ),
            (
                "完整 2.5D 扩展",
                "站点剖面辐射/绕射 + Ma 2005 系数对照",
                "将二维剖面水动力沿船长积分，验证 A33、B33、A55、B55 及耦合项。",
                "这是从“紧凑纵向模型”升级到“可验证完整 2.5D 模型”的硬门槛。",
            ),
        ],
        columns=["模块", "方法", "作用", "为什么需要"],
    )


def terms_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            (
                "响应幅值算子 RAO（Response Amplitude Operator）",
                "船体运动幅值与入射波幅值之比。",
                "在线性频域方程 [-omega_e^2(M+A)+i omega_e B+C] eta=F 中，eta 除以波幅得到响应幅值算子。",
                "它把“某个周期的波会让船动多少”变成可画曲线、可与文献图对比的量。",
            ),
            (
                "遭遇频率 omega_e（encounter frequency）",
                "船在航行中实际遇到波峰的频率。",
                "深水迎浪常写作 omega_e=omega-kUcos(mu)，其中 U 为航速、k 为波数、mu 为波向角。",
                "同一海浪周期在不同航速下会变成不同的激励频率，因此峰值会随航速移动。",
            ),
            (
                "附加质量 A（added mass）",
                "船体加速时必须一起推动周围水体，等效为额外惯性。",
                "出现在频域方程的惯性项 -omega_e^2(M+A) 中。",
                "如果附加质量偏差大，峰值频率和响应幅值都会错。",
            ),
            (
                "辐射阻尼 B（radiation damping）",
                "船体振荡向外辐射波浪并损失能量。",
                "出现在 i omega_e B 项中，主要控制峰值尖锐程度。",
                "Fridsma 和 Ma 2005 的失败很大程度上是在问：阻尼和压力传递的频率形状是否正确。",
            ),
            (
                "恢复矩阵 C（restoring matrix）",
                "升沉和纵摇偏离平衡后，浮力、动升力和力矩将其拉回的线性化刚度。",
                "出现在 C eta 项中。",
                "滑行艇的湿长和动升力随姿态变化，恢复矩阵不能简单照搬排水船。",
            ),
            (
                "梁宽弗劳德数 Fn_B（beam Froude number）",
                "U/sqrt(gB)，用梁宽 B 定义的高速滑行无量纲航速。",
                "用于 Faltinsen 第 9 章和示例船的速度标定。",
                "它把不同尺度的滑行艇放在同一速度相似框架下比较。",
            ),
            (
                "lambda/L（wavelength ratio）",
                "波长与船长之比。",
                "在规则波验证中作为横轴，帮助区分短波、中波和长波区间。",
                "短波误差常指向局部入射/压力积分，长波误差更像整体刚体运动问题。",
            ),
            (
                "A33、B33、A55、B55 等系数",
                "3 表示升沉自由度，5 表示纵摇自由度；A 为附加质量，B 为辐射阻尼。",
                "这些是完整 2.5D 站点积分的核心水动力系数。",
                "Faltinsen 响应可以过关，并不自动证明这些剖面积分系数过关；Ma 2005 正是用来卡住这一点。",
            ),
        ],
        columns=["术语/符号", "物理意义", "方程位置", "引入原因"],
    )


def validation_goal_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            (
                "第一层：Faltinsen 第 9 章",
                "升沉/纵摇特征值和响应幅值算子曲线",
                "当前通过",
                "说明紧凑纵向 2.5D 核心在规定运行姿态下具备基准可信度。",
            ),
            (
                "第二层：Fridsma/Katayama 规则波实验",
                "升沉、纵摇、重心加速度、艏部加速度及非线性趋势",
                "Fridsma 幅值失败；Katayama 定量幅值待补充",
                "说明仅靠线性 RAO 还不能完整解释滑行艇非线性湿表面、冲击和波高依赖。",
            ),
            (
                "第三层：Ma 2005 系数",
                "Wigley III 与 SL-7 的 A/B 水动力矩阵系数",
                "当前失败",
                "说明站点式完整 2.5D 辐射/绕射压力积分尚未验证完成。",
            ),
            (
                "第四层：用户工程算例",
                "给定船型、速度、海况后的 6 自由度统一输出、时域响应和统计图",
                "已能运行并出图",
                "用于工程流程展示；其可信度必须由前三层验证边界限定。",
            ),
        ],
        columns=["验证层级", "对照物/输出", "当前状态", "解释"],
    )


def combine_ma_status(wigley: pd.DataFrame, sl7: pd.DataFrame) -> pd.DataFrame:
    tables = []
    if not wigley.empty:
        tmp = wigley.copy()
        tmp.insert(0, "hull", "Wigley III")
        tables.append(tmp)
    if not sl7.empty:
        tmp = sl7.copy()
        tmp.insert(0, "hull", "SL-7")
        tables.append(tmp)
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def figure_texts() -> dict[str, tuple[str, str]]:
    def md_from_html(text: str) -> str:
        return (
            text.replace("<p>", "")
            .replace("</p>", "\n\n")
            .replace("<strong>", "**")
            .replace("</strong>", "**")
            .replace("<em>", "*")
            .replace("</em>", "*")
            .replace("&omega;", "omega")
            .replace("&lambda;", "lambda")
        )

    items: dict[str, str] = {
        "example_rao": """
<p><strong>生成背景与作用。</strong>该图来自报告专用短算例，横轴是入射波周期，三条颜色曲线对应约 9.3、13.9、18.6 m/s 三个航速。它回答的是一个最基本的工程问题：同一条艇在不同航速下，遇到不同周期的迎浪时，升沉、纵摇和艏部垂向加速度会在哪些周期附近被放大。</p>
<p><strong>如何阅读。</strong>上子图是升沉响应幅值算子，单位 m/m，意思是 1 m 波幅大约会激起多少 m 升沉幅值；中子图是纵摇响应幅值算子，单位 rad/m，意思是 1 m 波幅对应多少弧度纵摇；下子图是艏部垂向加速度响应幅值算子，单位 (m/s^2)/m，意思是每 1 m 波幅会带来多少艏部垂向加速度幅值。曲线越高，表示该波周期更容易激起该类响应；峰值越尖，表示模型阻尼越小、响应越集中。</p>
<p><strong>子图解释。</strong>升沉子图中，中、高速曲线在约 4.7 至 5.0 s 附近出现明显峰值，说明遭遇频率进入纵向耦合共振区；低速曲线峰值较低且更平缓。纵摇子图与升沉子图形状相近，说明本模型中的升沉和纵摇耦合较强，不能把二者完全分开看。艏部加速度子图比运动位移更尖锐，因为加速度相当于对位移做二阶时间变化，频率越高、峰值附近相位变化越快，加速度越容易被放大。</p>
<p><strong>结论。</strong>这张图说明程序能产生速度相关的频域响应，并且峰值位置随航速变化，这是遭遇频率和动水动力耦合作用的合理表现。但它只是模型输出，不等于最终验证通过；它需要后续 Faltinsen、Fridsma、Ma 2005 对照来限定可信范围。</p>
""",
        "example_time": """
<p><strong>生成背景与作用。</strong>该图展示 13.93 m/s 规则迎浪下的时域积分结果，是把频域思想落到实际时间序列后的检查。频域图告诉我们“哪个周期容易放大”，时域图则告诉我们“在一段具体波浪作用下船体怎样上下、俯仰、加速”。</p>
<p><strong>如何阅读。</strong>四个子图共用横轴时间。第一子图把入射波面和升沉放在一起，帮助观察相位和幅值；第二子图是纵摇角，单位为 deg；第三子图是重心与艏部垂向加速度，单位为 g；第四子图是其他自由度占位输出，包含 surge、sway、roll、yaw。</p>
<p><strong>子图解释。</strong>第一子图中，灰色波面幅值约为规则波半高，而蓝色升沉出现更大幅值，说明在该速度和周期组合下船体运动被放大。第二子图显示纵摇角具有明显周期性，且峰值可达到几十度量级，这已经提示该短算例处于强响应或模型舒适区之外。第三子图中，艏部加速度有尖峰，说明纵摇角加速度叠加到艏部后会显著放大；这种尖峰在真实滑行艇中常与拍击、再入水和湿表面快速变化有关，目前程序把它作为风险标记，而不是宣称已经精确捕捉冲击。第四子图保持零值，是因为本版迎浪对称模型只求解升沉和纵摇，横向与艏摇方向没有经过验证的激励通道。</p>
<p><strong>结论。</strong>该图适合说明程序接口已经给出 6 自由度统一格式，但也清楚暴露了边界：本版主要可信输出是 heave 和 pitch，其他自由度在迎浪对称假设下为零；强加速度尖峰需要实验或更完整非线性冲击模型验证后才能用于设计判据。</p>
""",
        "example_rms": """
<p><strong>生成背景与作用。</strong>该图来自 JONSWAP 不规则波短时域样本，用均方根量比较不同航速的统计响应。均方根不是最大值，而是把一段时间内上下波动的能量平均后开方，因此更适合描述海况中的典型响应强度。</p>
<p><strong>如何阅读。</strong>上子图的蓝线是升沉均方根，橙线是纵摇均方根且已换成角度；下子图的蓝线是重心垂向加速度均方根，橙线是艏部垂向加速度均方根。横轴航速越往右越高，点越高说明该速度下统计响应越强。</p>
<p><strong>子图解释。</strong>运动均方根子图中，升沉均方根约在 1 m 量级，纵摇均方根随速度总体下降，表示在该短样本里最高速没有产生最大的平均纵摇角。加速度均方根子图则不同，中速点艏部加速度显著升高，说明加速度更敏感于峰值频率和艏部力臂，不一定与位移均方根同步变化。</p>
<p><strong>结论。</strong>这张图把“运动幅值”和“加速度风险”分开了：一条艇可能位移看起来并非最大，但艏部加速度已经很大。工程上这很重要，因为乘员舒适性、结构冲击和设备固定通常更关心加速度峰值与均方根，而不只看升沉位移。</p>
""",
        "faltinsen": """
<p><strong>生成背景与作用。</strong>该图是当前模型最重要的正向验证证据之一。蓝/橙计算曲线分别与 Faltinsen 第 9 章中数字化的升沉和纵摇响应点对照，横轴是波长与船长之比。它不是随便挑一个算例，而是用文献给定的运行姿态、质量参数和梁宽弗劳德数复现参考图。</p>
<p><strong>如何阅读。</strong>上子图看升沉响应幅值算子，下子图看纵摇响应幅值算子；黑点是数字化参考值，连续线是程序计算值。若线穿过或贴近黑点，表示模型不仅能算出有限结果，而且在峰值位置、峰值高度和长波衰减段都接近文献。</p>
<p><strong>子图解释。</strong>升沉子图中，峰值出现在 lambda/L 约 3.5 至 4.0 附近，计算曲线与黑点在峰前上升、峰值附近和峰后衰减均保持一致。纵摇子图中，峰值也在相近波长比附近，计算曲线同样跟随数字化点。两个子图共同说明本版紧凑纵向模型对 Faltinsen 规定状态下的主要纵向响应是可复现的。</p>
<p><strong>结论。</strong>Faltinsen 对照通过后，可以说“迎浪升沉/纵摇的核心线性频域框架是合理的”。但这并不自动推出完整 2.5D 已完成，因为 Faltinsen 图主要检验紧凑纵向响应，不足以检验站点剖面压力积分、非线性拍击和完整 6 自由度耦合。</p>
""",
        "fridsma": """
<p><strong>生成背景与作用。</strong>Fridsma 幅值对照用于回答“结果看起来像，是否真的接近实验”。图中蓝色为数字化实验点，橙色为频域模型，绿色虚线为时域诊断，红圈表示超出容许误差的点。四个子图覆盖运动和加速度，是判断滑行艇波浪响应合理性的关键证据。</p>
<p><strong>如何阅读。</strong>横轴是 lambda/L，即波长与船长之比。左上是升沉，右上是纵摇，左下是重心垂向加速度，右下是艏部垂向加速度。若橙/绿曲线贴近蓝点且没有红圈，说明该波长处通过；若红圈密集，说明该指标在对应波长带仍不可信。</p>
<p><strong>子图解释。</strong>升沉子图显示 lambda/L=1 的短波点明显低估，lambda/L=2 到 3 的中波区又高估，lambda/L=4 到 6 接近一些。这说明误差不是一个常数比例问题，而是曲线形状问题。纵摇子图也在短波低估、中波高估，说明升沉/纵摇耦合恢复与阻尼仍需改进。重心加速度子图在短波低估、中波高估，表明只用线性位移响应重构加速度并不稳。艏部加速度子图在 lambda/L=1 的短波处低估很严重，而艏部加速度正是最容易受拍击和再入水影响的量。</p>
<p><strong>结论。</strong>这张图给出的不是“模型失败”这么简单，而是指出下一步该修哪里：短波需要更好的入射/绕射压力积分，中波峰值需要非线性湿长变化和响应饱和机制，艏部加速度需要动升力、冲击和局部再入水模型。报告中的结论因此会把当前模型定位为基线，而不是完整实验级 2.5D。</p>
""",
        "katayama": """
<p><strong>生成背景与作用。</strong>Katayama 图不是完整幅值验证替代品，而是从文献文字趋势出发，检查模型是否能表现波长趋势、峰值存在性以及波高依赖。它的作用是把“缺少数字化曲线”的部分仍然变成可追踪的开发目标。</p>
<p><strong>如何阅读。</strong>四个子图按速度和运动量分组。左上和右上为低速 Fn_L=1.21 的升沉与纵摇，左下和右下为高速 Fn_L=3.63 的升沉与纵摇。不同颜色表示不同 H/d，即波高与吃水之比；若三条颜色重合，说明当前模型没有体现波高对响应峰值的影响。</p>
<p><strong>子图解释。</strong>低速升沉和低速纵摇子图中，曲线并非严格随波长单调增加，这与文献文字趋势不一致，因此相关趋势行失败。高速升沉子图出现峰值，说明线性频域模型能表现“某个波长附近响应最大”的基本现象。高速纵摇子图也有峰值或平台，但不同波高曲线几乎重合，说明当前线性模型没有捕捉“大波高降低峰值并将峰值推向更长波长”的非线性现象。</p>
<p><strong>结论。</strong>Katayama 结果告诉我们：峰值存在性可以作为当前模型的合理性支持，但波高依赖趋势未通过，不能把该模型用于强非线性跳跃、飞航、再入水等判断。定量曲线仍标注为待补充。</p>
""",
        "ma_wigley": """
<p><strong>生成背景与作用。</strong>Ma 2005 系数对照是完整站点式 2.5D 的硬验证。前面的 Faltinsen 和 Fridsma主要看运动响应，这里直接看水动力系数：A 表示附加质量，B 表示辐射阻尼，下标 3 表示升沉，下标 5 表示纵摇。因此 A33、B33 是升沉自身项，A55、B55 是纵摇自身项，A35、A53、B35、B53 是升沉与纵摇耦合项。</p>
<p><strong>如何阅读。</strong>每个子图横轴是无量纲频率 omega sqrt(L/g)，蓝线是 Ma 2005 参考，橙线是当前站点开发模型。红圈标出未通过容差的点。对完整 2.5D 而言，不能只看一个子图过关；对角项、耦合项、附加质量和阻尼都要同时合理。</p>
<p><strong>子图解释。</strong>A33 和 B33 子图贴合较好，说明升沉对角项已有较强基线。A55 也较接近，说明纵摇附加质量对角项在 Wigley III 上不是主要矛盾。A53 与 A35 是耦合附加质量，图中部分频率偏离，表示升沉力矩与纵摇力之间的压力积分关系还没有完全闭合。B53 和 B35 的差距更明显，尤其 B53 整体偏离参考阻尼曲线，说明耦合辐射阻尼是当前完整 2.5D 的重点阻塞项。B55 则显示形状和尺度都仍需修正。</p>
<p><strong>结论。</strong>这张图把完整 2.5D 的问题定位到“站点剖面辐射/压力传递/前进速度耦合”的系数层面。也就是说，当前程序已经不是没有模型，而是已经有了能被 Ma 2005 指出具体差距的开发模型；下一步必须让这些系数通过容差，才能称为完整可验证的 2.5D 求解器。</p>
""",
    }
    return {key: (value, md_from_html(value)) for key, value in items.items()}


def build_report() -> tuple[str, str]:
    data = load_report_data()
    builder = ReportBuilder()
    fig_text = figure_texts()

    inv_category, inv_extension = inventory_tables(data["inventory"])
    example_summary = select_columns(
        data["example_summary"],
        [
            "speed_mps",
            "speed_kn",
            "fn_b",
            "trim_deg",
            "z_wl_m",
            "heave_m_rms",
            "pitch_rad_rms",
            "bow_vertical_accel_mps2_rms",
            "stable_linear_hp",
            "irregular_model_limit_note",
        ],
    )
    if not example_summary.empty and "pitch_rad_rms" in example_summary.columns:
        example_summary["pitch_deg_rms"] = pd.to_numeric(example_summary["pitch_rad_rms"], errors="coerce") * 180.0 / math.pi
        example_summary = example_summary.drop(columns=["pitch_rad_rms"])
    example_summary = example_summary.rename(
        columns={
            "speed_mps": "航速 (m/s)",
            "speed_kn": "航速 (kn)",
            "fn_b": "Fn_B",
            "trim_deg": "纵倾 (deg)",
            "z_wl_m": "基准升沉 z_wl (m)",
            "heave_m_rms": "升沉均方根 (m)",
            "pitch_deg_rms": "纵摇均方根 (deg)",
            "bow_vertical_accel_mps2_rms": "艏部加速度均方根 (m/s^2)",
            "stable_linear_hp": "线性升沉/纵摇稳定",
            "irregular_model_limit_note": "模型边界提示",
        }
    )

    validation_status = data["validation_status"].rename(
        columns={
            "benchmark": "验证对象",
            "gate_status": "门控状态",
            "pass_checks": "通过",
            "fail_checks": "失败",
            "not_evaluated_checks": "待评价",
            "info_checks": "信息",
        }
    )
    faltinsen_eigen = select_columns(
        data["faltinsen_eigen"],
        [
            "mode",
            "actual_eigenvalue_nondim",
            "expected_real_part",
            "actual_real_part",
            "real_part_rel_error",
            "expected_imaginary_abs",
            "actual_imaginary_abs",
            "imaginary_abs_rel_error",
            "mode_status",
        ],
    ).rename(
        columns={
            "mode": "模态",
            "actual_eigenvalue_nondim": "计算特征值",
            "expected_real_part": "参考实部",
            "actual_real_part": "计算实部",
            "real_part_rel_error": "实部相对误差",
            "expected_imaginary_abs": "参考频率",
            "actual_imaginary_abs": "计算频率",
            "imaginary_abs_rel_error": "频率相对误差",
            "mode_status": "状态",
        }
    )
    fridsma_residual = select_columns(
        data["fridsma_residual"],
        [
            "summary_type",
            "metric",
            "wavelength_band",
            "case_count",
            "pass_checks",
            "fail_checks",
            "median_computed_over_reference",
            "median_abs_relative_error",
            "max_abs_relative_error",
            "dominant_bias",
            "recommendation",
        ],
    ).head(10).rename(
        columns={
            "summary_type": "汇总类型",
            "metric": "指标",
            "wavelength_band": "波长区间",
            "case_count": "样本数",
            "pass_checks": "通过",
            "fail_checks": "失败",
            "median_computed_over_reference": "计算/参考中位数",
            "median_abs_relative_error": "绝对相对误差中位数",
            "max_abs_relative_error": "最大绝对相对误差",
            "dominant_bias": "主导偏差",
            "recommendation": "诊断建议",
        }
    )
    fridsma_shape = select_columns(
        data["fridsma_shape"],
        [
            "metric",
            "prediction_model",
            "case_count",
            "pass_checks",
            "fail_checks",
            "signed_shape_correlation",
            "best_fit_normalized_shape_rmse",
            "predicted_minus_reference_log_slope",
            "shape_status",
            "recommendation",
        ],
    ).rename(
        columns={
            "metric": "指标",
            "prediction_model": "预测通道",
            "case_count": "样本数",
            "pass_checks": "通过",
            "fail_checks": "失败",
            "signed_shape_correlation": "曲线相关",
            "best_fit_normalized_shape_rmse": "最优缩放后形状误差",
            "predicted_minus_reference_log_slope": "对数斜率差",
            "shape_status": "形状状态",
            "recommendation": "诊断建议",
        }
    )
    ma_status = combine_ma_status(data["wigley_coeff"], data["sl7_coeff"]).rename(
        columns={
            "hull": "船型/基准",
            "coefficient": "系数",
            "PASS": "通过",
            "FAIL": "失败",
            "NOT_EVALUATED": "待评价",
            "total": "总数",
            "pass_fraction": "通过率",
        }
    )
    katayama_quality = select_columns(
        data["katayama_quality"],
        ["metric", "expected", "actual", "status", "note"],
    ).head(10).rename(
        columns={"metric": "趋势检查", "expected": "期望", "actual": "当前结果", "status": "状态", "note": "说明"}
    )
    goal_gap = select_columns(data["goal_gap"], ["benchmark", "metric", "expected", "actual", "status", "note"])
    if not goal_gap.empty:
        gap_focus = goal_gap[goal_gap["status"].astype(str).isin(["FAIL", "NOT_EVALUATED"])].head(10).rename(
            columns={
                "benchmark": "验证对象",
                "metric": "缺口/失败项",
                "expected": "目标",
                "actual": "当前",
                "status": "状态",
                "note": "说明",
            }
        )
    else:
        gap_focus = pd.DataFrame()

    tables: dict[str, tuple[str, str]] = {}
    tables["inventory_category"] = builder.table(
        inv_category,
        "early stage materials 资料索引按类别汇总",
        "资料索引来自 docs/materials_inventory.csv；虚拟环境、缓存和日志不作为文献证据解读。",
    )
    tables["inventory_extension"] = builder.table(
        inv_extension,
        "资料索引按类别与扩展名的前 12 项",
        "该表用于说明实际阅读和解析工作的对象范围，而不是把每个工具环境文件都当作文献。",
    )
    tables["terms"] = builder.table(
        terms_table(),
        "核心术语、符号、方程位置与引入原因",
        "正文首次出现的关键缩写和符号在此统一解释，避免只给缩写不说明物理含义。",
    )
    tables["method"] = builder.table(
        method_table(),
        "模型模块、方法来源与作用",
        "本表把研究计划中的模块拆成可验证的程序功能，便于判断每一步是否有对照物。",
    )
    tables["goal"] = builder.table(
        validation_goal_table(),
        "完整 2.5D 运动预报模型的可验证目标",
        "这是回答“怎么判断结果合理”的核心：只有通过对照基准，结果才从可运行变成可信。",
    )
    tables["example_parameters"] = builder.table(
        example_parameters(),
        "报告示例船型、海况与仿真参数",
        "该示例用于展示程序输入/输出链路，不替代文献基准验证。",
    )
    tables["example_summary"] = builder.table(
        example_summary,
        "短算例不同航速下的主要输出摘要",
        "模型边界提示若显示跳跃、湿表面丢失或冲击风险，表示该点应用于设计前需要更高保真验证。",
    )
    tables["validation_status"] = builder.table(
        validation_status,
        "综合验证按基准分组的通过/失败/待评价统计",
        "该表来自 outputs/validation_report_source/validation_status_by_benchmark.csv；综合验证返回失败码是因为仍有硬失败，不是因为程序崩溃。",
    )
    tables["faltinsen_eigen"] = builder.table(
        faltinsen_eigen,
        "Faltinsen Table 9.2 无量纲特征值对照",
        "两个模态均通过实部和频率容差，是线性纵向基线可信的关键证据。",
    )
    tables["fridsma_residual"] = builder.table(
        fridsma_residual,
        "Fridsma 幅值残差按指标与波长区间汇总",
        "残差汇总用于定位失败模式，不改变硬门控结论。",
    )
    tables["fridsma_shape"] = builder.table(
        fridsma_shape,
        "Fridsma 幅值曲线形状审计",
        "曲线形状审计先做最优常数缩放，再比较相关性、斜率与归一化误差，用于区分尺度问题和频率形状问题。",
    )
    tables["katayama_quality"] = builder.table(
        katayama_quality,
        "Katayama 定性趋势检查摘要",
        "该表只来自文献文字趋势，不替代待补充的 Fig. 9/Fig. 10 定量幅值曲线。",
    )
    tables["ma_status"] = builder.table(
        ma_status,
        "Ma 2005 Wigley III 与 SL-7 系数门控按系数统计",
        "A 为附加质量，B 为辐射阻尼；3 为升沉，5 为纵摇。完整 2.5D 必须让对角和耦合项同时过关。",
    )
    tables["gap_focus"] = builder.table(
        gap_focus,
        "当前仍需关闭的主要失败项与待补充项",
        "表中待补充项不以推测数据填充；必须由源文献数字化、真实 offsets 或已验证求解器补齐。",
    )

    figures: dict[str, tuple[str, str]] = {}
    figures["example_rao"] = builder.figure(
        EXAMPLE_DIR / "figures" / "rao.png",
        "示例船不同航速下的升沉、纵摇与艏部加速度响应幅值算子",
        *fig_text["example_rao"],
    )
    figures["example_time"] = builder.figure(
        EXAMPLE_DIR / "figures" / "timeseries_regular_speed_13p93.png",
        "13.93 m/s 规则迎浪时域 6 自由度统一输出示例",
        *fig_text["example_time"],
    )
    figures["example_rms"] = builder.figure(
        EXAMPLE_DIR / "figures" / "rms_by_speed.png",
        "JONSWAP 不规则波短样本均方根响应随航速变化",
        *fig_text["example_rms"],
    )
    figures["faltinsen"] = builder.figure(
        VALIDATION_DIR / "figures" / "faltinsen_ch9_rao.png",
        "Faltinsen 第 9 章升沉与纵摇响应幅值算子验证",
        *fig_text["faltinsen"],
    )
    figures["fridsma"] = builder.figure(
        VALIDATION_DIR / "figures" / "fridsma_regular_wave_amplitudes_comparison.png",
        "Fridsma 规则波运动与加速度幅值对照",
        *fig_text["fridsma"],
    )
    figures["katayama"] = builder.figure(
        VALIDATION_DIR / "figures" / "katayama_qualitative_trends.png",
        "Katayama 文献定性趋势探针",
        *fig_text["katayama"],
    )
    figures["ma_wigley"] = builder.figure(
        VALIDATION_DIR / "figures" / "ma2005_wigley_iii_coefficients_comparison.png",
        "Ma 2005 Wigley III 水动力系数对照",
        *fig_text["ma_wigley"],
    )

    sections: list[tuple[str, str, str, str]] = []
    sections.append(
        (
            "abstract",
            "摘要",
            """
<p>本报告整理了高速滑行艇在波浪中运动预报程序的研究背景、方法路线、实现过程、示例计算、验证对照和后续目标。当前程序已经形成 Python 包与命令行接口，能够读取船型、船体参数、规则波/不规则波、海流和风等配置，输出不同航速下的 6 自由度统一时间序列，其中迎浪对称条件下以升沉和纵摇为核心，其余自由度作为零占位并在结果中明确标注。</p>
<p>验证结论必须分层理解：Faltinsen 第 9 章规定运行状态的特征值和响应幅值算子已经通过，说明紧凑纵向 2.5D 频域核心具备基准可信度；Fridsma 规则波幅值对照仍失败，说明短波压力积分、中波非线性湿表面变化以及艏部加速度冲击机制尚未充分；Katayama 定量幅值曲线仍待补充，只能用文献定性趋势作为开发探针；Ma 2005 的 Wigley III 与 SL-7 系数门控仍失败，说明完整站点式 2.5D 辐射/绕射压力积分还不能宣布完成。</p>
<p>因此，本报告的核心结论是：当前结果在“Faltinsen 纵向线性基线”和“工程流程演示”层面合理，但在“完整 2.5D 模型可验证实现”层面尚未完成。下一阶段的具体目标不是继续增加外观功能，而是让 Fridsma/Katayama 幅值、Ma 2005 水动力系数和真实船型站点数据逐项通过可复现门控。</p>
""",
            """
本报告整理了高速滑行艇在波浪中运动预报程序的研究背景、方法路线、实现过程、示例计算、验证对照和后续目标。当前程序已经形成 Python 包与命令行接口，能够读取船型、船体参数、规则波/不规则波、海流和风等配置，输出不同航速下的 6 自由度统一时间序列，其中迎浪对称条件下以升沉和纵摇为核心，其余自由度作为零占位并在结果中明确标注。

验证结论必须分层理解：Faltinsen 第 9 章规定运行状态的特征值和响应幅值算子已经通过，说明紧凑纵向 2.5D 频域核心具备基准可信度；Fridsma 规则波幅值对照仍失败，说明短波压力积分、中波非线性湿表面变化以及艏部加速度冲击机制尚未充分；Katayama 定量幅值曲线仍待补充，只能用文献定性趋势作为开发探针；Ma 2005 的 Wigley III 与 SL-7 系数门控仍失败，说明完整站点式 2.5D 辐射/绕射压力积分还不能宣布完成。

因此，本报告的核心结论是：当前结果在“Faltinsen 纵向线性基线”和“工程流程演示”层面合理，但在“完整 2.5D 模型可验证实现”层面尚未完成。下一阶段的具体目标不是继续增加外观功能，而是让 Fridsma/Katayama 幅值、Ma 2005 水动力系数和真实船型站点数据逐项通过可复现门控。
""",
        )
    )
    sections.append(
        (
            "background",
            "研究背景与目的",
            f"""
<p>高速滑行艇与常规排水船不同。排水船的主要支撑来自静浮力，而滑行艇在高航速下有显著动升力，湿表面长度、纵倾、压力中心和艏部入水状态都会随速度和波浪快速变化。也就是说，同一条艇在静水中看起来稳定，并不意味着进入迎浪后仍然可以用简单线性排水船模型解释。</p>
<p>本研究选择 2.5D 方法作为主线，是因为它位于经验公式和全三维高保真计算之间。所谓 2.5D（two-and-a-half-dimensional，二维横剖面沿船长积分并保留前进速度影响）并不是“半个三维”，而是把船长方向分成许多站点，在每个横剖面上求二维水动力，再沿纵向积分成整体升沉、纵摇和耦合水动力。这样做的原因是：滑行艇很细长、航速高，横剖面局部流动和沿船长变化都重要，纯二维或纯经验公式都不够。</p>
<p>本报告的目的不是把所有图画得漂亮就结束，而是回答用户提出的关键问题：如何判断当前结果是否合理，有没有案例可对照，以及怎样把“完整实现 2.5D 模型”写成具体、可验证的目标。为此，本报告把程序结果拆成四层证据：资料索引与方法溯源、示例船运行结果、Faltinsen/Fridsma/Katayama 运动验证、Ma 2005 水动力系数验证。</p>
{tables["goal"][0]}
""",
            f"""
本研究选择 2.5D 方法作为主线，是因为它位于经验公式和全三维高保真计算之间。所谓 2.5D（two-and-a-half-dimensional，二维横剖面沿船长积分并保留前进速度影响）并不是“半个三维”，而是把船长方向分成许多站点，在每个横剖面上求二维水动力，再沿纵向积分成整体升沉、纵摇和耦合水动力。

{tables["goal"][1]}
""",
        )
    )
    sections.append(
        (
            "materials",
            "资料、术语与方法",
            f"""
<p>资料整理分两步进行：第一步是建立 materials inventory（资料清单，记录文件类别、大小和路径，目的是确认研究对象范围）；第二步是从与滑行艇、2.5D、规则波试验、运动控制和势流条带法直接相关的资料中提取可实现方法。需要特别说明的是，清单中的工具代码、开源参考和缓存文件不是同等级文献证据，真正用于验证结论的仍是可追溯的文献基准和程序生成数据。</p>
{tables["inventory_category"][0]}
{tables["inventory_extension"][0]}
<p>方法上，本研究以 Faltinsen 第 9 章为核心，补充 Savitsky 静水滑行平衡、Fridsma/Savitsky-Brown 规则波试验思想、Katayama 跳跃与波高趋势、Ma 2005 站点式 2.5D 系数对照，以及 Fossen 船舶 6 自由度环境载荷表达。开源代码方面，OpenPlaning、MSS/PythonVehicleSimulator、waveresponse、Capytaine 和本地 PDSTRIP 源码主要作为结构和验证思路参考；报告不把这些开源库的结果当作未经复核的最终真值。</p>
{tables["terms"][0]}
{tables["method"][0]}
""",
            f"""
资料整理分两步进行：第一步是建立 materials inventory（资料清单，记录文件类别、大小和路径，目的是确认研究对象范围）；第二步是从与滑行艇、2.5D、规则波试验、运动控制和势流条带法直接相关的资料中提取可实现方法。

{tables["inventory_category"][1]}

{tables["inventory_extension"][1]}

{tables["terms"][1]}

{tables["method"][1]}
""",
        )
    )
    sections.append(
        (
            "process",
            "研究过程",
            f"""
<p>程序实现遵循“先能算、再能对照、最后能解释失败”的顺序。首先建立配置读取和命令行接口，使船型、质量、航速、波浪、海流、风和仿真长度都进入统一配置。随后实现 Savitsky/Faltinsen 静水平衡，得到纵倾、湿长和基准升沉。接着实现频域响应幅值算子和时域积分，并把结果包装成 6 自由度统一输出。最后建立验证命令，自动写出 CSV、图和 Markdown 报告。</p>
<p>这一路径的关键不是只追求一次性跑通，而是每个层级都有对照物。Faltinsen 用于验证线性纵向响应；Fridsma 和 Katayama 用于验证规则波运动、加速度和非线性趋势；Ma 2005 用于验证站点式 2.5D 的附加质量与阻尼矩阵；数值 sanity check（数值合理性检查，指有限性、矩阵正定性、时间步收敛等基础检查）用于防止程序在没有物理意义的情况下给出漂亮曲线。</p>
<p>本报告所用综合验证命令为：<code>python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\\validation_report_source --ma-compare-hydro-models --ma-compare-row-limit 1 --ma-bem-free-surface-panels 3 --ma-bem-body-panels 8</code>。该命令写出验证结果后返回失败码，原因是仍有 83 个硬失败和 4 个待参考数据项；这不是运行异常，而是验证门控如实报告模型尚未完成。</p>
""",
            """
程序实现遵循“先能算、再能对照、最后能解释失败”的顺序。首先建立配置读取和命令行接口，使船型、质量、航速、波浪、海流、风和仿真长度都进入统一配置。随后实现 Savitsky/Faltinsen 静水平衡，得到纵倾、湿长和基准升沉。接着实现频域响应幅值算子和时域积分，并把结果包装成 6 自由度统一输出。最后建立验证命令，自动写出 CSV、图和 Markdown 报告。

本报告所用综合验证命令为：`python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\\validation_report_source --ma-compare-hydro-models --ma-compare-row-limit 1 --ma-bem-free-surface-panels 3 --ma-bem-body-panels 8`。该命令写出验证结果后返回失败码，原因是仍有 83 个硬失败和 4 个待参考数据项；这不是运行异常，而是验证门控如实报告模型尚未完成。
""",
        )
    )
    sections.append(
        (
            "example",
            "示例算例与程序输出",
            f"""
<p>为了展示程序如何从输入参数走到图表结果，本报告采用一个深 V 单体滑行艇示例。示例船不是某个公开试验的严格复刻，因此它只能说明程序工作流和典型响应形式，不能单独作为验证结论。示例运行命令为：<code>python -m planing_seakeeping run configs\\report_quick_planing.yml --out outputs\\report_example</code>。</p>
{tables["example_parameters"][0]}
{tables["example_summary"][0]}
{figures["example_rao"][0]}
{figures["example_time"][0]}
{figures["example_rms"][0]}
""",
            f"""
为了展示程序如何从输入参数走到图表结果，本报告采用一个深 V 单体滑行艇示例。示例船不是某个公开试验的严格复刻，因此它只能说明程序工作流和典型响应形式，不能单独作为验证结论。

{tables["example_parameters"][1]}

{tables["example_summary"][1]}

{figures["example_rao"][1]}

{figures["example_time"][1]}

{figures["example_rms"][1]}
""",
        )
    )
    sections.append(
        (
            "validation",
            "验证结果展示",
            f"""
<p>本节是报告的核心，因为它直接回答“现在结果合不合理”。合理性不靠主观判断，而靠多层对照。表中 PASS 表示该门控通过，FAIL 表示有明确硬失败，PENDING_REFERENCE_OR_IMPLEMENTATION 表示缺少参考数据或实现尚未完成，不能用推测数据补齐。</p>
{tables["validation_status"][0]}
{tables["faltinsen_eigen"][0]}
{figures["faltinsen"][0]}
{tables["fridsma_residual"][0]}
{tables["fridsma_shape"][0]}
{figures["fridsma"][0]}
{tables["katayama_quality"][0]}
{figures["katayama"][0]}
{tables["ma_status"][0]}
{figures["ma_wigley"][0]}
{tables["gap_focus"][0]}
""",
            f"""
本节是报告的核心，因为它直接回答“现在结果合不合理”。合理性不靠主观判断，而靠多层对照。

{tables["validation_status"][1]}

{tables["faltinsen_eigen"][1]}

{figures["faltinsen"][1]}

{tables["fridsma_residual"][1]}

{tables["fridsma_shape"][1]}

{figures["fridsma"][1]}

{tables["katayama_quality"][1]}

{figures["katayama"][1]}

{tables["ma_status"][1]}

{figures["ma_wigley"][1]}

{tables["gap_focus"][1]}
""",
        )
    )
    sections.append(
        (
            "discussion",
            "分析与讨论",
            """
<p><strong>第一，为什么 Faltinsen 结果可以认为合理。</strong>Faltinsen 图和特征值表同时通过，说明当前线性频域模型在规定姿态、规定速度、规定质量参数下，能够复现升沉和纵摇的主要模态、峰值位置和响应衰减。这一层验证回答的是“核心方程是否写对、量纲是否一致、遭遇频率和响应幅值算子是否合理”。因此，在相近假设范围内，程序输出的迎浪 heave/pitch 频域响应可以作为可信基线。</p>
<p><strong>第二，为什么 Fridsma 失败不能简单归结为参数没调好。</strong>残差表和形状审计显示，短波、中波和长波的误差方向不同。短波低估说明入射/绕射压力积分或局部湿表面响应不足；中波高估说明线性峰值缺少非线性饱和；艏部加速度低估则指向拍击、再入水和局部动升力变化。若只是一个尺度系数错，最优缩放后曲线形状应能贴合；但加速度项被归为 frequency_shape_gap（频率形状差距，表示不同频率处误差不是同一比例），所以需要改物理模型，而不是只改单位换算。</p>
<p><strong>第三，为什么 Katayama 只能作为趋势探针。</strong>当前有跳跃分类和文献文字趋势，但缺少 Fig. 9/Fig. 10 的源支持定量幅值曲线。报告必须把这一点标为待补充。现有图显示线性模型能产生高航速峰值，却不能表现波高增大导致峰值下降和峰值移向更长波长的趋势。这个失败是有价值的，因为它把后续非线性湿长、飞航/再入水和冲击模型的目标写清楚了。</p>
<p><strong>第四，为什么 Ma 2005 是完整 2.5D 的硬门槛。</strong>Faltinsen 纵向响应通过，只能说明紧凑模型在一个规定状态下合理；完整 2.5D 还要求剖面附加质量、辐射阻尼、前进速度耦合和压力传递沿船长积分后能复现公开系数。Wigley III 的 A33、B33 和 A55 表现较好，但 B35、B53、B55 及部分耦合项仍失败；SL-7 还叠加真实 offsets 待补充问题。因此，当前程序应被称为“带完整验证框架的 2.5D 开发模型”，不应称为“完整验证通过的 2.5D 求解器”。</p>
<p><strong>第五，示例算例如何使用。</strong>示例图可用于演示输入、求解、输出和可视化流程，也可帮助工程人员理解速度、波周期和加速度风险之间的关系。但只要示例中的模型边界提示出现 possible_jump_or_wetted_surface_loss 或 outside_linear_2p5d_comfort_zone，就应把结果视为预警信号，而不是最终设计载荷。</p>
""",
            """
**第一，为什么 Faltinsen 结果可以认为合理。**Faltinsen 图和特征值表同时通过，说明当前线性频域模型在规定姿态、规定速度、规定质量参数下，能够复现升沉和纵摇的主要模态、峰值位置和响应衰减。

**第二，为什么 Fridsma 失败不能简单归结为参数没调好。**残差表和形状审计显示，短波、中波和长波的误差方向不同。若只是一个尺度系数错，最优缩放后曲线形状应能贴合；但加速度项被归为 frequency_shape_gap，所以需要改物理模型，而不是只改单位换算。

**第三，为什么 Katayama 只能作为趋势探针。**当前有跳跃分类和文献文字趋势，但缺少 Fig. 9/Fig. 10 的源支持定量幅值曲线。报告必须把这一点标为待补充。

**第四，为什么 Ma 2005 是完整 2.5D 的硬门槛。**完整 2.5D 要求剖面附加质量、辐射阻尼、前进速度耦合和压力传递沿船长积分后能复现公开系数。当前 Wigley III 和 SL-7 仍有硬失败，因此不能称为完整验证通过。
""",
        )
    )
    sections.append(
        (
            "conclusion",
            "主要结论、不足与展望",
            """
<p><strong>主要结论。</strong>当前程序已经实现从配置读取、静水滑行平衡、频域响应幅值算子、规则波/不规则波时域积分，到 6 自由度统一输出和验证报告的完整工程流程。Faltinsen 第 9 章基准通过，说明核心迎浪升沉/纵摇线性响应是合理的。示例算例能够产生频域、时域和均方根图，说明程序作为研究和开发工具已经可用。</p>
<p><strong>尚未完成的部分。</strong>Fridsma 幅值门控仍失败，Katayama 定量幅值曲线待补充，Ma 2005 Wigley III 和 SL-7 系数门控仍失败，完整站点式 2.5D 求解器仍标为待实现/待验证。报告没有用猜测值填补这些空白，因为这样会破坏研究结论的可复现性。</p>
<p><strong>下一步目标。</strong>第一，补齐 Katayama Fig. 9/Fig. 10 的源支持数字化幅值数据。第二，针对 Fridsma 的短波、中波和加速度差异分别改进入射/绕射压力积分、非线性湿长变化和冲击加速度通道。第三，把 Ma 2005 的 B35、B53、B55 等耦合阻尼项作为优先目标，完善剖面边界积分、压力传递和前进速度站点装配。第四，为 SL-7 接入真实 offsets_file（船体站点型值文件，用于还原真实横剖面几何），避免用替代几何评价完整模型。</p>
<p><strong>最终判据。</strong>当 Faltinsen、Fridsma/Katayama 和 Ma 2005 三类基准均通过，且示例船强响应点的模型边界提示得到实验或更高保真计算支持后，才可以把该程序升级表述为“可验证的完整 2.5D 高速滑行艇运动预报模型”。在此之前，最严谨的说法是：当前版本是一个已经具备验证框架、核心纵向基线通过、但完整 2.5D 水动力和非线性加速度仍在开发中的科研原型。</p>
""",
            """
**主要结论。**当前程序已经实现从配置读取、静水滑行平衡、频域响应幅值算子、规则波/不规则波时域积分，到 6 自由度统一输出和验证报告的完整工程流程。Faltinsen 第 9 章基准通过，说明核心迎浪升沉/纵摇线性响应是合理的。

**尚未完成的部分。**Fridsma 幅值门控仍失败，Katayama 定量幅值曲线待补充，Ma 2005 Wigley III 和 SL-7 系数门控仍失败，完整站点式 2.5D 求解器仍标为待实现/待验证。

**下一步目标。**补齐 Katayama 定量曲线；改进 Fridsma 短波、中波和加速度差异；以 Ma 2005 B35、B53、B55 等耦合阻尼项作为优先目标；为 SL-7 接入真实 offsets_file。
""",
        )
    )

    toc_html = '<nav class="toc"><h2>目录</h2><ol>' + "".join(
        f'<li><a href="#{section_id}">{html.escape(title)}</a></li>' for section_id, title, _, _ in sections
    ) + "</ol></nav>"
    body_sections_html = "\n".join(
        f'<section id="{section_id}"><h2>{html.escape(title)}</h2>{content}</section>'
        for section_id, title, content, _ in sections
    )
    toc_md = "\n".join(f"- [{title}](#{section_id})" for section_id, title, _, _ in sections)
    body_sections_md = "\n\n".join(f"## {title}\n\n{content}" for section_id, title, _, content in sections)

    css = """
:root {
  --ink: #17202a;
  --muted: #5c6670;
  --line: #d8dde3;
  --accent: #1f5f8b;
  --accent-2: #9a5a1a;
  --paper: #ffffff;
  --soft: #f5f7fa;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background: #eef1f5;
  font-family: "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", "Source Han Sans SC", Arial, sans-serif;
  line-height: 1.72;
  letter-spacing: 0;
}
.page {
  max-width: 1120px;
  margin: 0 auto;
  background: var(--paper);
  min-height: 100vh;
  box-shadow: 0 12px 40px rgba(20, 32, 48, 0.12);
}
.cover {
  padding: 72px 72px 54px;
  border-bottom: 6px solid var(--accent);
  background: linear-gradient(180deg, #ffffff 0%, #f6f9fc 100%);
}
.kicker {
  color: var(--accent);
  font-weight: 700;
  text-transform: uppercase;
  font-size: 13px;
}
h1 {
  margin: 18px 0 18px;
  font-size: 36px;
  line-height: 1.25;
  font-weight: 800;
}
.subtitle {
  font-size: 18px;
  color: var(--muted);
  max-width: 820px;
}
.meta-grid {
  margin-top: 32px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 28px;
  color: var(--muted);
  font-size: 14px;
}
.meta-grid strong { color: var(--ink); }
.toc {
  padding: 32px 72px 18px;
  border-bottom: 1px solid var(--line);
}
.toc h2, section h2 {
  font-size: 24px;
  margin: 0 0 16px;
  color: var(--accent);
}
.toc ol {
  columns: 2;
  margin: 0;
  padding-left: 22px;
}
.toc a {
  color: var(--ink);
  text-decoration: none;
}
section {
  padding: 34px 72px;
  border-bottom: 1px solid var(--line);
}
section p { margin: 0 0 14px; }
code {
  background: #eef3f7;
  padding: 2px 5px;
  border-radius: 4px;
  font-family: Consolas, "Liberation Mono", monospace;
  font-size: 0.92em;
}
.table-wrap {
  margin: 22px 0 28px;
  overflow-x: auto;
}
.table-caption {
  font-weight: 600;
  margin-bottom: 8px;
}
.table-note {
  margin-top: 8px;
  color: var(--muted);
  font-size: 13px;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th {
  background: #e9f1f7;
  color: #12384f;
  text-align: left;
  border: 1px solid var(--line);
  padding: 8px;
  vertical-align: top;
}
.data-table td {
  border: 1px solid var(--line);
  padding: 8px;
  vertical-align: top;
}
.data-table tr:nth-child(even) td { background: #fafbfc; }
.figure-card {
  margin: 28px 0 34px;
  padding: 16px 16px 18px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}
.figure-card figcaption {
  font-weight: 700;
  margin-bottom: 12px;
}
.figure-card img {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto 14px;
  border: 1px solid #e2e6ea;
}
.figure-explain {
  color: #27323b;
  font-size: 14px;
}
.missing {
  background: #fff7e8;
  color: var(--accent-2);
  border: 1px solid #f0cf9a;
  padding: 14px;
  border-radius: 6px;
}
.footer-note {
  padding: 20px 72px 42px;
  color: var(--muted);
  font-size: 13px;
}
@media (max-width: 760px) {
  .cover, .toc, section, .footer-note { padding-left: 22px; padding-right: 22px; }
  h1 { font-size: 28px; }
  .meta-grid { grid-template-columns: 1fr; }
  .toc ol { columns: 1; }
}
@media print {
  body { background: #fff; }
  .page { box-shadow: none; max-width: none; }
  section, .figure-card { break-inside: avoid; }
  a { color: inherit; }
}
"""
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>高速滑行艇 2.5D 运动预报模型验证研究报告</title>
  <style>{css}</style>
</head>
<body>
<main class="page">
  <header class="cover">
    <div class="kicker">Research Report / Self-contained HTML</div>
    <h1>高速滑行艇 2.5D 运动预报模型验证研究报告</h1>
    <p class="subtitle">围绕 Faltinsen 第 9 章、Fridsma/Katayama 规则波实验与 Ma 2005 水动力系数，对当前 Python 模型的实现过程、示例结果、验证边界和后续目标进行系统整理。</p>
    <div class="meta-grid">
      <div><strong>项目目录：</strong>{html.escape(str(ROOT))}</div>
      <div><strong>报告日期：</strong>{REPORT_DATE}</div>
      <div><strong>示例输出：</strong>{html.escape(str(EXAMPLE_DIR))}</div>
      <div><strong>验证输出：</strong>{html.escape(str(VALIDATION_DIR))}</div>
      <div><strong>报告形式：</strong>单文件 HTML，CSS 与图片均内嵌</div>
      <div><strong>未知数据处理：</strong>缺失或未验证信息均标注“待补充/不适用”</div>
    </div>
  </header>
  {toc_html}
  {body_sections_html}
  <div class="footer-note">本报告由本地程序输出、验证 CSV 和图像生成。HTML 中所有图片均为 Base64 内嵌；表格均为直接写入的 HTML 表格；未引用外部 CSS、JavaScript 或网络图片。</div>
</main>
</body>
</html>
"""
    md_doc = f"""# 高速滑行艇 2.5D 运动预报模型验证研究报告

报告日期：{REPORT_DATE}

项目目录：`{ROOT}`

示例输出：`{EXAMPLE_DIR}`

验证输出：`{VALIDATION_DIR}`

## 目录

{toc_md}

{body_sections_md}
"""
    return html_doc, md_doc


def main() -> None:
    html_doc, md_doc = build_report()
    (ROOT / "report.html").write_text(html_doc, encoding="utf-8")
    (ROOT / "report.md").write_text(md_doc, encoding="utf-8")
    print(f"Wrote {ROOT / 'report.html'}")
    print(f"Wrote {ROOT / 'report.md'}")


if __name__ == "__main__":
    main()
