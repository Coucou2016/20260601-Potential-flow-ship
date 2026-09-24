"""Freeze and compare the Python section port with unchanged Fortran routines."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from planing_seakeeping.pdstrip_external import default_pdstrip_source_dir
from planing_seakeeping.section_bem import SectionOffsets, _pdstrip_half_section, _solve_heave_radiation_pdstrip_near_count
from planing_seakeeping.float_radiation_audit import wetted_section
from planing_seakeeping.seaplane_workflow import load_workflow, FloatHydrostatics, build_model
from planing_seakeeping.float_offsets import read_float_offsets


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(out, station_index=None):
    out.mkdir(parents=True, exist_ok=False)
    source = default_pdstrip_source_dir() / "pdstrip.f90"
    raw, base, path = load_workflow(ROOT / "configs/edo106k_workflow.json")
    model = build_model(FloatHydrostatics(read_float_offsets(path), 2), base, raw)
    index = int(np.argmax(model["static"]["width"])) if station_index is None else station_index
    if not 0 <= index < len(model["hydro"].x):
        raise ValueError("Invalid station index")
    edo = wetted_section(model, index)
    if edo is None:
        raise ValueError("Selected EDO station is dry")
    sections = {"analytic_v": SectionOffsets(np.array([.5, 0., -.5]), np.array([0., .3, 0.])),
                "edo_selected_wet_section": edo}
    contract = {"periods_s": [1.6, 2., 3., 5., 8.], "body_panels_half": 48,
                "free_surface_panels": 64, "near_counts": [25, 28], "rho": 1025., "g": 9.80665,
                "relative_limit": .05, "absolute_a_kg_m": 1e-3, "absolute_b_kg_m_s": 1e-3,
                "zero_speed_negative_b_tolerance": 1e-8,
                "source_path": str(source), "source_sha256": digest(source),
                "geometry_source_sha256": digest(path), "edo_station_index": index,
                "precision": "original routines compiled with default real/complex promoted to 64-bit",
                "sections": {k: {"y": s.y_m.tolist(), "z": s.z_down_m.tolist()} for k, s in sections.items()}}
    (out / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    (out / "contract.sha256").write_text(digest(out / "contract.json"), encoding="ascii")


def run(out, label):
    report_path = out / f"comparison_{label}.json"
    if report_path.exists():
        raise ValueError("Comparison already exists; choose a new label")
    contract_path = out / "contract.json"
    if digest(contract_path) != (out / "contract.sha256").read_text().strip():
        raise ValueError("Frozen contract hash mismatch")
    c = json.loads(contract_path.read_text())
    source = Path(c["source_path"])
    if digest(source) != c["source_sha256"]:
        raise ValueError("Fortran reference source hash mismatch")
    src = source.read_text(encoding="latin-1")
    fragments = []
    for kind, name in [("function", n) for n in ("pq", "pqn", "pqs", "pqsn")] + [
        ("subroutine", "addedmassexcitations"), ("subroutine", "simqcd")]:
        match = re.search(rf"^{kind} {name}\(.*?^end {kind} {name}\s*$", src, re.M | re.S | re.I)
        if match is None:
            raise ValueError(f"Missing original routine {name}")
        fragments.append(match.group(0))
    header = """module reference
implicit none
integer, parameter :: nofmax=512,nmumax=1
integer :: nfs=64,nmu=0,ngap=0,gap(1)=0
real :: zbot=1.e6,zwl=0.,g=9.80665,rho=1025.,pi=acos(-1.),wangl(1)=0.,waven
contains
subroutine stop1(message)
character(*) :: message
print *, message
stop 1
end subroutine stop1
"""
    driver = """
end module reference
program verify
use reference
implicit none
integer :: n,i
real :: y(nofmax),z(nofmax),omega
complex :: am(1,1),df(1,0),fk(1,0)
read(*,*)n,omega
do i=1,n
read(*,*)y(i),z(i)
enddo
call addedmassexcitations(n,y,z,omega,1,am,df,fk)
write(*,'(2ES26.17)')real(am(1,1)),aimag(am(1,1))
end program verify
"""
    wrapper = out / "reference.f90"
    wrapper.write_text(header + "\n".join(fragments) + driver, encoding="ascii")
    exe = (out / "reference.exe").resolve()
    command = ["gfortran", "-std=legacy", "-O2", "-fdefault-real-8", "-fdefault-double-8", "-o", str(exe), str(wrapper)]
    compiled = subprocess.run(command, cwd=out, capture_output=True, text=True)
    (out / "compile.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
    compiled.check_returncode()
    rows = []
    for name, coords in c["sections"].items():
        section = SectionOffsets(np.array(coords["y"]), np.array(coords["z"]))
        half = _pdstrip_half_section(section).resample_by_arclength(c["body_panels_half"])
        for period in c["periods_s"]:
            omega = 2 * np.pi / period
            stdin = f"{len(half.y_m)} {omega:.17g}\n" + "\n".join(f"{y:.17g} {z:.17g}" for y,z in zip(half.y_m,half.z_down_m)) + "\n"
            result = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, check=True)
            values = list(map(float, result.stdout.split()))
            if len(values) != 2:
                raise ValueError(result.stdout)
            reference = complex(*values)
            candidates = [_solve_heave_radiation_pdstrip_near_count(section, omega, c["rho"], c["g"],
                          c["free_surface_panels"], c["body_panels_half"], nf, strict=True)
                          for nf in c["near_counts"]]
            candidate = np.mean([v[0] for v in candidates])
            a_ref, b_ref = reference.real, -omega * reference.imag
            a, b = candidate.real, -omega * candidate.imag
            a_limit = max(c["absolute_a_kg_m"], c["relative_limit"] * abs(a_ref))
            b_limit = max(c["absolute_b_kg_m_s"], c["relative_limit"] * abs(b_ref))
            rows.append(dict(section=name, period_s=period, a_reference=a_ref, b_reference=b_ref,
                             a_python=a, b_python=b, a_error=abs(a-a_ref), b_error=abs(b-b_ref),
                             passed=bool(abs(a-a_ref)<=a_limit and abs(b-b_ref)<=b_limit and
                                         b>=-c["zero_speed_negative_b_tolerance"] and
                                         b_ref>=-c["zero_speed_negative_b_tolerance"])))
    report = {"passed": all(r["passed"] for r in rows), "cases": rows,
              "contract_sha256": digest(contract_path), "wrapper_sha256": digest(wrapper),
              "python_sha256": digest(ROOT / "planing_seakeeping/section_bem.py"),
              "command": command, "scope": "matched discretization implementation check; not experiment validation"}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["freeze", "run"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", choices=["corrected", "repeat"], default="corrected")
    parser.add_argument("--edo-station", type=int)
    args = parser.parse_args()
    if args.phase == "freeze":
        freeze(args.out.resolve(), args.edo_station)
    else:
        raise SystemExit(run(args.out.resolve(), args.label))
