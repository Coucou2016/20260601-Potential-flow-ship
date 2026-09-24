"""Data-bound longitudinal animation: linear computed motion, prescribed waves."""
import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd


def write_animation(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    from matplotlib.patches import Polygon

    out=Path(out)
    model=json.loads((out/"model.json").read_text(encoding="utf-8"))
    snapshot=json.loads((out/"input_snapshot.json").read_text(encoding="utf-8"))
    raw,base=snapshot["workflow"],snapshot["base"]
    data=pd.read_csv(out/"regular.csv")
    cg=np.array(model["mass"]["cg_m"])
    with np.load(out/"geometry.npz") as mesh:
        vertices=mesh["vertices_m"]
    # Longitudinal envelope comes from the exported mesh; keep both step sides.
    # At each x, use the lowest and highest vertices. No invented airframe outline.
    xs=np.unique(vertices[:,0])
    lower=np.array([vertices[vertices[:,0]==x,2].min() for x in xs])
    upper=np.array([vertices[vertices[:,0]==x,2].max() for x in xs])
    # Use all centerline bottom vertices in original order to preserve F/A jumps.
    center=vertices[np.abs(vertices[:,1])<1e-10]
    center=center[center[:,2]<np.interp(center[:,0],xs,upper)-1e-9]
    order=np.argsort(center[:,0],kind="stable")
    bottom=center[order][:,[0,2]]
    outline=np.vstack([bottom,np.column_stack([xs[::-1],upper[::-1]])])
    period=raw["regular_wave_period_s"]
    omega=2*np.pi/period
    k=omega**2/base["environment_assumed"]["gravity_m_s2"]
    amplitude=raw["regular_wave_height_m"]/2
    times=np.linspace(data.time_s.iloc[-1]-2*period,data.time_s.iloc[-1],61)[:-1]
    # Frames sample the existing time integration by linear interpolation.
    heave=np.interp(times,data.time_s,data.heave_m)
    pitch=np.interp(times,data.time_s,data.pitch_rad)
    def project(h,theta):
        x=cg[0]-outline[:,0]
        z=outline[:,1]-cg[2]
        return np.column_stack([np.cos(theta)*x-np.sin(theta)*z,
            model["equilibrium"]["cg_height_m"]+h+np.sin(theta)*x+np.cos(theta)*z])
    initial=project(heave[0],model["equilibrium"]["pitch_rad"]+pitch[0])
    with plt.rc_context({"font.family":"sans-serif","font.sans-serif":["Microsoft YaHei","SimHei","DejaVu Sans"],
                         "axes.unicode_minus":False,"font.size":11}):
        fig,ax=plt.subplots(figsize=(10,3.8),layout="constrained")
        patch=Polygon(initial,facecolor="#7ab1ae",edgecolor="#34565d",lw=1)
        ax.add_patch(patch)
        wave_x=np.linspace(initial[:,0].min()-.5,initial[:,0].max()+.5,250)
        wave_line,=ax.plot(wave_x,amplitude*np.cos(k*wave_x+omega*times[0]),color="#397caf",lw=1.5)
        cg_point,=ax.plot([0],[model["equilibrium"]["cg_height_m"]+heave[0]],"o",color="#b44040")
        ax.axhline(0,color="#666666",lw=.6,ls="--")
        ax.set(xlim=(wave_x.min(),wave_x.max()),ylim=(initial[:,1].min()-.1,model["equilibrium"]["cg_height_m"]+.2),
               xlabel="相对重心前向距离 [m]",ylabel="高于平均水面的高度 [m]")
        ax.set_aspect("equal",adjustable="box")
        def frame(i):
            patch.set_xy(project(heave[i],model["equilibrium"]["pitch_rad"]+pitch[i]))
            wave_line.set_ydata(amplitude*np.cos(k*wave_x+omega*times[i]))
            cg_point.set_ydata([model["equilibrium"]["cg_height_m"]+heave[i]])
            ax.set_title(f"同源时域结果：t={times[i]:.2f} s，升沉={heave[i]*1000:.1f} mm，纵摇扰动={np.rad2deg(pitch[i]):.3f}°")
            return patch,wave_line,cg_point
        animation=FuncAnimation(fig,frame,frames=len(times),interval=100,blit=False)
        filename=out/"figures/motion.gif"
        animation.save(filename,writer=PillowWriter(fps=10),dpi=100)
        plt.close(fig)
    encoded=base64.b64encode(filename.read_bytes()).decode("ascii")
    description=("该动画取regular.csv最后两个周期的实际计算位移，按真实尺度移动网格纵向投影，不夸大波高或运动。"
        "外轮廓由导出的合成闭合网格提取，断阶保留；不是完整真实飞机外形。红点为重心，蓝线为同一输入规则波，"
        "不是求出的扰动自由面。升沉、纵摇来自线性方程；没有计算前进、起飞、着水冲击、飞溅或通气。"
        "显示帧间插值只用于播放，求解数据未被改变。")
    block=f"<section><h2>同源动态过程：零航速规则波</h2><p>{description}</p><img alt='由时域结果驱动的纵向过程' src='data:image/gif;base64,{encoded}'></section>"
    html=out/"report.html"
    html.write_text(html.read_text(encoding="utf-8").replace("</main>",block+"</main>"),encoding="utf-8")
    md=out/"report.md"
    md.write_text(md.read_text(encoding="utf-8")+"\n\n## 同源动态过程\n\n"+description+f"\n\n![时域动画](figures/motion.gif)\n",encoding="utf-8")
    return filename
