from __future__ import annotations

from scripts.probe_begovic_direct_wave_2dt import _parser


def test_direct_wave_cli_defaults_to_uncorrected_2dt() -> None:
    args = _parser().parse_args(["--out", "output"])

    assert args.transom_correction is False


def test_direct_wave_cli_accepts_source_transom_correction() -> None:
    args = _parser().parse_args(["--out", "output", "--transom-correction"])

    assert args.transom_correction is True
