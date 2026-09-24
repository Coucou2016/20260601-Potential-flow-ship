"""Reproduce a source-offset geometry audit, not a seaplane simulation.

Figure contract: actual tabulated bottom points reveal the two step breaks.
Panels: reconstructed mesh, longitudinal keel/chine profile. Python only.
All 24 stations are included; no inferred waterline, pressure, or motion.
"""
from pathlib import Path
import sys
import hashlib
import json
import base64

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from planing_seakeeping.float_offsets import read_float_offsets, bottom_mesh


def main():
    source = ROOT/"benchmarks/seaplane_edo/106k_offsets_inches.csv"
    out = ROOT/"outputs/edo106k_geometry_20260916"
    out.mkdir(parents=True, exist_ok=True)
    stations = read_float_offsets(source)
    v, f = bottom_mesh(stations)
    np.savez(out/"bottom_mesh.npz", vertices_m=v, triangles=f)
    with (out/"bottom_mesh.obj").open("w", encoding="ascii") as stream:
        stream.write("# Source-derived OPEN bottom; not a complete aircraft\n")
        for p in v:
            stream.write("v " + " ".join(map(str,p)) + "\n")
        for face in f+1:
            stream.write("f " + " ".join(map(str,face)) + "\n")
    plt.rcParams.update({"font.family":"sans-serif", "font.sans-serif":["Arial", "DejaVu Sans"], "font.size":10,
                         "pdf.fonttype":42, "svg.fonttype":"none"})
    fig = plt.figure(figsize=(10,7), layout="constrained")
    ax = fig.add_subplot(211, projection="3d")
    ax.add_collection3d(Poly3DCollection(v[f], facecolor="#80b9c5", edgecolor="#40535a", linewidth=.25))
    ax.auto_scale_xyz(v[:,0],v[:,1],v[:,2])
    ax.set_box_aspect((8.509,1.143,1.0), zoom=0.9)
    ax.view_init(25,-65)
    ax.set_axis_off()
    ax.set_title("a  EDO 106-K: open bottom, true proportions; length 8.509 m")
    ax2=fig.add_subplot(212)
    x=np.array([s.x_aft_m for s in stations])
    for values, label, color in (([s.height_up_m[0] for s in stations],"Keel","#267f98"),
                                  ([s.height_up_m[-1] for s in stations],"Chine","#b15c37")):
        ax2.plot(x,values,"o-",ms=3,label=label,color=color)
    ax2.set(xlabel="Distance aft (m)",ylabel="Height above source datum (m)",
            title="b  Original stations; vertical joins denote step offsets")
    ax2.legend(frameon=False)
    fig.savefig(out/"geometry.png", dpi=300)
    fig.savefig(out/"geometry.pdf")
    fig.savefig(out/"geometry.svg")
    plt.close(fig)
    manifest={"status":"source_offsets_reconstruction_not_hydrodynamically_validated",
              "source":"https://ntrs.nasa.gov/citations/19930092989", "pdf_page":6,
              "original_unit":"inch_full_size", "length_m":8.509,"max_chine_beam_m":1.143,
              "station_count":len(stations),"vertices":len(v),"triangles":len(f),
              "sha256_offsets":hashlib.sha256(source.read_bytes()).hexdigest(),
              "sha256_pdf":hashlib.sha256((source.parent/"source/naca_wr_l_722.pdf").read_bytes()).hexdigest(),
              "limitations":["Piecewise-linear bottom only; flutes not fully resolved", "No deck, side, step-face or full aircraft reconstruction", "No mass, CG, inertia, aircraft aerodynamic polar or takeoff validation"]}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    image=base64.b64encode((out/"geometry.png").read_bytes()).decode()
    html='''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>真实浮筒几何核查</title><style>body{max-width:1000px;margin:40px auto;padding:0 24px;font:17px/1.8 system-ui;color:#24343b}img{max-width:100%}h1,h2{line-height:1.4}aside{border-left:4px solid #b15c37;padding:12px;background:#f4f5f5}</style></head><body><h1>EDO 106-K 水上飞机浮筒：真实型值重建</h1><p>来源：NACA-WR-L-722，1942，表 I，PDF 第6页。该浮筒用于 SB2U-3 水上飞机。原表为实尺度英寸，按 0.0254 转为米。全长8.509米，最大折角宽1.143米，共24条站位记录。</p><aside>这是公开原始型值支撑的分段线性底面重建，不是完整整机，不是起降仿真结果，也不证明水动力准确。原报告为气动试验报告，不能代替着水载荷试验。</aside><h2>图1：底面和断阶</h2><img alt="原始型值重建的底面网格和纵向轮廓" src="data:image/png;base64,'''+image+'''"><p>上图每个三角形来自表中龙骨、折角及有记录的内纵骨坐标。在站间与横向已知点之间采用直线连接，左右镜像。原表不足以完整解析浅槽曲率、舷侧和甲板宽度，所以没有把缺失部分凭想象封闭。开口是明确保留的数据边界，不是一个已完成封闭船体的漏面。</p><p>下图横轴从浮筒首部向后量取距离，纵轴从报告原始基准线向上量取高度，不是吃水。蓝线为龙骨，橙线为折角。179英寸与325英寸各有前、后两个不同高度的记录，对应两个断阶。下图竖直连线用于显示跳变；上图网格不跨断阶插值，也尚未构造断阶立面。水面位置取决于姿态和浸深，当前没有独立工况，故不画任意水面冒充计算结果。</p><h2>如何接着使用</h2><p>底面可作为后续剖面裁剪与接触定位的数据源；真正接入求解前还需机体质量、重心惯性、瞬时姿态及接触水面，并解决断阶分离与通气。首阶段应做规定速度、规定姿态的湿面与载荷核查，再做自由着水和加速滑跑。双浮筒与三浮体几何装配接口已提供，但任意布置不是原飞机布置，也不包含片体干扰。</p></body></html>'''
    (out/"report.html").write_text(html,encoding="utf-8")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    main()
