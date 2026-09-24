"""Post-solve experimental evaluation, deliberately separate from prediction."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.run_regular_head_sea_gate2_acceptance import _motion_metrics

REFERENCE_SHA256 = "13df2dd6346f4930d101211b9bf839a0f891e2b418b4f1ec909a9d8b15c91a33"


def plot_comparison(comparison, destination):
    """Quantitative grid: speed-dependent failures persist, despite a connected workflow."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                         "font.size": 10, "pdf.fonttype": 42, "svg.fonttype": "none",
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 3, figsize=(12, 6), layout="constrained")
    definitions = [("heave_rao_m_per_m", "heave_digitization_uncertainty_abs", "Heave / wave amplitude"),
                   ("pitch_rao_rad_per_wave_slope", "pitch_digitization_uncertainty_abs", "Pitch / wave slope")]
    for col, (name, group) in enumerate(comparison.groupby("configuration", sort=True)):
        group = group.sort_values("wavelength_m")
        for row, (value, uncertainty, label) in enumerate(definitions):
            ax = axes[row, col]
            ax.plot(group.wavelength_m, group[value], "o-", color="#007c91", label="Computed (8 points)")
            ax.errorbar(group.wavelength_m, group["reference_" + value], yerr=group[uncertainty],
                        fmt="^", color="#bd4932", capsize=3, label="Experiment + digitization bounds")
            ax.set_title(f"({chr(97 + row * 3 + col)}) {name}")
            ax.set_xlabel("Dispersion-consistent wavelength (m)")
            ax.set_ylabel(label)
            ax.grid(alpha=.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=2, frameon=False)
    fig.savefig(destination / "motion_comparison.png", dpi=300)
    fig.savefig(destination / "motion_comparison.pdf")
    fig.savefig(destination / "motion_comparison.svg")
    plt.close(fig)


def evaluate(run, frozen):
    run, frozen = Path(run), Path(frozen)
    contract = json.loads((frozen / "contract.json").read_text(encoding="utf-8"))
    for name, key in (("run.json", "input_sha256"), ("conditions.csv", "conditions_sha256")):
        if hashlib.sha256((frozen / name).read_bytes()).hexdigest() != contract[key]:
            raise ValueError(f"Frozen input mismatch: {name}")
    config = json.loads((frozen / "run.json").read_text(encoding="utf-8"))
    if config != json.loads((run / "input_snapshot.json").read_text(encoding="utf-8")):
        raise ValueError("Run does not match frozen configuration")
    conditions = pd.read_csv(frozen / "conditions.csv")
    root = Path(__file__).resolve().parents[1]
    reference_path = root / "benchmarks/begovic2020/begovic2020_mono_efd_motion_digitized.csv"
    if hashlib.sha256(reference_path.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Frozen experimental reference hash mismatch")
    reference = pd.read_csv(reference_path)
    comparisons = []
    metrics = []
    groups = list(conditions.groupby("fn_b", sort=True))
    if len(config["cases"]) != 3 or len(groups) != 3 or len(conditions) != 24:
        raise ValueError("Incomplete three-speed contract")
    for case, (fn, group) in zip(config["cases"], groups):
        rao = pd.read_csv(run / case["id"] / "rao.csv")
        if len(rao) != 8 or not np.allclose(rao.omega_e_rad_s, group.omega_e_rad_s, rtol=1e-9):
            raise ValueError("Missing or mismatched computed conditions")
        ref = reference[np.isclose(reference.fn_b, fn)].set_index("case_code").loc[group.case_code].reset_index()
        for key in ("heave_rao_m_per_m", "pitch_rao_rad_per_wave_slope"):
            rao["reference_" + key] = ref[key].to_numpy()
        rao["configuration"] = case["id"]
        for column in ("heave_digitization_uncertainty_abs", "pitch_digitization_uncertainty_abs"):
            rao[column] = ref[column].to_numpy()
        rao["case_code"] = group.case_code.to_numpy()
        rao["linear_gate_eligible"] = group.linear_eligible.to_numpy()
        comparisons.append(rao)
        metrics.append(_motion_metrics(rao, scope=case["id"]))
    comparison = pd.concat(comparisons, ignore_index=True)
    result = pd.concat(metrics, ignore_index=True)
    destination = run / "evaluation"
    if destination.exists():
        raise ValueError("Evaluation exists; preserve prior evidence")
    destination.mkdir()
    comparison.to_csv(destination / "experimental_comparison.csv", index=False)
    result.to_csv(destination / "per_speed_metrics.csv", index=False)
    _motion_metrics(comparison, scope="all_three_speeds").to_csv(destination / "global_metrics.csv", index=False)
    status = {"stage_acceptance": "NOT_PASSED", "per_speed_motion_pass": bool(result.status.eq("PASS").all()),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "reference_role": "experimental_regression_set_not_blind_holdout",
        "missing_gates": ["full_band_three_grid", "independent_excitation_reference", "dense_peak_scan",
                          "Fridsma_phase_acceleration", "independent_time_integration", "stability"]}
    (destination / "acceptance.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    plot_comparison(comparison, destination)
    (destination / "figure_notes.md").write_text(
        "# Figure 1: Three-speed experimental regression comparison\n\n"
        "Panels a/b/c show heave at FnB 1.67/2.26/2.82; d/e/f show pitch at the same speeds. "
        "Blue circles are this run, orange triangles the frozen experimental digitization. "
        "Bars are digitization bounds, not experimental confidence intervals. All 24 conditions are shown; "
        "the predeclared source kA>0.055 points remain visible but are excluded only from linear metrics. "
        "The horizontal coordinate is derived consistently from source encounter frequency and speed, "
        "not a new experimental wavelength measurement. Lines only connect eight computed points and "
        "must not be interpreted as a resolved peak scan. Low-speed disagreement remains substantial; "
        "software integration is not experimental validation. Source values and eligibility are in experimental_comparison.csv.\n",
        encoding="utf-8")
    print(result.to_string(index=False))
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(evaluate(args.run, args.frozen))
