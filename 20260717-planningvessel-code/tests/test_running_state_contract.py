import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import audit_running_state_sensitivity as audit


def test_contract_precedes_equilibrium_and_nonconvergence_is_rejected(tmp_path, monkeypatch):
    config = Path(__file__).resolve().parents[1] / "benchmarks/longitudinal_refined_20260921/run.json"
    destination = tmp_path / "diagnostic"
    def fail_equilibrium(*args):
        contract = json.loads((destination / "contract.json").read_text())
        assert contract["recorded_before_solving"] is True
        assert (destination / "source_hashes.json").is_file()
        assert (destination / "input_snapshot.json").is_file()
        return SimpleNamespace(converged=False, residual=(1, 1))
    monkeypatch.setattr(audit, "solve_equilibrium", fail_equilibrium)
    with pytest.raises(ValueError, match="did not converge"):
        audit.run(config, destination)
    assert not (destination / "summary.json").exists()
