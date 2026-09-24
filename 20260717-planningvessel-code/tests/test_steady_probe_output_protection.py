import pytest
from scripts import probe_sun2007_steady_planing_convergence as probe


def test_existing_output_rejected_before_solving(tmp_path, monkeypatch):
    monkeypatch.setattr('sys.argv', ['probe', '--out', str(tmp_path)])

    def forbidden(**kwargs):
        raise AssertionError('Solver must not run when output already exists')

    monkeypatch.setattr(probe, '_run_case', forbidden)
    with pytest.raises(FileExistsError):
        probe.main()
    assert list(tmp_path.iterdir()) == []
