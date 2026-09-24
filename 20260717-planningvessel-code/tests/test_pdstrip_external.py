import tempfile
import unittest
from pathlib import Path

from planing_seakeeping.pdstrip_external import (
    PDSTRIP_SMOKE_FREQUENCY_COUNT,
    PDSTRIP_SMOKE_SECTION_COUNT,
    parse_pdstrip_geometry,
    parse_sectionresults,
    parse_sectionresults_metadata,
    pdstrip_section_bem_comparison_rows,
    pdstrip_sectionresults_convention_rows,
    pdstrip_sectionresults_rows,
    run_pdstrip_station_hull_sections,
    write_simple_full_v_case,
    write_station_hull_section_case,
)
from planing_seakeeping.station_2p5d import (
    HardChineStation,
    PDSTRIP_EXTERNAL_SECTIONS_STATUS,
    StationHull,
    assemble_external_pdstrip_section_6dof_matrices,
    make_wigley_iii_hull,
)
from planing_seakeeping.validation import validate_pdstrip_external_smoke


class PDStripExternalTests(unittest.TestCase):
    def test_simple_full_v_case_files_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            write_simple_full_v_case(work_dir)
            self.assertTrue((work_dir / "pdstrip.inp").exists())
            self.assertTrue((work_dir / "geomet.out").exists())
            geometry = (work_dir / "geomet.out").read_text(encoding="ascii")
            self.assertIn("5 F 0.30", geometry)
            self.assertEqual(geometry.count(" 3 0"), PDSTRIP_SMOKE_SECTION_COUNT)

    def test_sectionresults_metadata_counts_frequency_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            sectionresults = work_dir / "sectionresults"
            lines = ["Synthetic PDSTRIP smoke", f"{PDSTRIP_SMOKE_FREQUENCY_COUNT}"]
            for idx in range(PDSTRIP_SMOKE_SECTION_COUNT * PDSTRIP_SMOKE_FREQUENCY_COUNT):
                lines.append(f"{0.1 + idx * 0.01:.6f} 1 0.0")
                lines.append("(1.0,0.0)")
            lines.append("123.0")
            sectionresults.write_text("\n".join(lines), encoding="ascii")
            pdstrip_out = work_dir / "pdstrip.out"
            pdstrip_out.write_text("normal completion", encoding="ascii")
            metadata = parse_sectionresults_metadata(sectionresults, pdstrip_out)
            self.assertEqual(metadata.frequency_count, PDSTRIP_SMOKE_FREQUENCY_COUNT)
            self.assertEqual(metadata.frequency_block_count, PDSTRIP_SMOKE_SECTION_COUNT * PDSTRIP_SMOKE_FREQUENCY_COUNT)
            self.assertTrue(metadata.is_complete)

    def test_parse_sectionresults_infers_sections_and_recovers_added_mass(self):
        with tempfile.TemporaryDirectory() as tmp:
            sectionresults = Path(tmp) / "sectionresults"
            lines = ["Synthetic coefficients", "2"]
            omegas = [2.0, 4.0, 2.0, 4.0]
            for block_index, omega in enumerate(omegas):
                lines.append(f"{omega:.6f} 1 0.0")
                scale = omega**2
                radiation = [scale * complex(block_index + 1 + item, 0.1 * item) for item in range(9)]
                diffraction = [complex(100 + block_index + item, -item) for item in range(3)]
                froude_krylov = [complex(200 + block_index + item, item) for item in range(3)]
                for chunk in (radiation, diffraction, froude_krylov):
                    lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in chunk))
            lines.append("123.456")
            sectionresults.write_text("\n".join(lines), encoding="ascii")

            parsed = parse_sectionresults(sectionresults)
            self.assertEqual(parsed.frequency_count, 2)
            self.assertEqual(parsed.section_count, 2)
            self.assertEqual(len(parsed.blocks), 4)
            self.assertEqual(parsed.blocks[0].station_index, 1)
            self.assertEqual(parsed.blocks[1].frequency_index, 2)
            self.assertEqual(parsed.blocks[2].station_index, 2)
            self.assertAlmostEqual(parsed.blocks[0].added_mass_matrix_per_m[0, 0], 1.0)
            self.assertAlmostEqual(parsed.blocks[0].damping_over_omega_matrix_per_m[0, 1], 0.1)
            self.assertAlmostEqual(parsed.blocks[0].pdstrip_convention_damping_matrix_per_m[0, 1], -0.2)

            rows = pdstrip_sectionresults_rows(parsed)
            radiation_rows = [row for row in rows if row["quantity"] == "radiation"]
            excitation_rows = [row for row in rows if row["quantity"] != "radiation"]
            self.assertEqual(len(radiation_rows), 4 * 9 * 2)
            self.assertEqual(len(excitation_rows), 4 * 6)
            self.assertIn("pdstrip_internal_transposed", {row["orientation"] for row in radiation_rows})
            self.assertIn("pdstrip_convention_damping_per_m", radiation_rows[0])
            self.assertIn("radiation_storage_convention", radiation_rows[0])
            self.assertEqual(
                radiation_rows[0]["radiation_storage_convention"],
                "radiation_force_matrix = omega**2 * complex_added_mass_matrix",
            )

            convention_rows = pdstrip_sectionresults_convention_rows(sectionresults)
            conventions = {row["convention"]: row for row in convention_rows}
            self.assertIn("radiation_storage", conventions)
            self.assertIn("om(i)**2*addedm", conventions["radiation_storage"]["source_evidence"])
            self.assertIn("complex_added_mass_recovery", conventions)

    def test_pdstrip_geometry_parser_and_section_bem_comparison_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            write_simple_full_v_case(work_dir)
            geometry = parse_pdstrip_geometry(work_dir / "geomet.out")
            self.assertEqual(geometry.section_count, PDSTRIP_SMOKE_SECTION_COUNT)
            first_offsets = geometry.sections[0].to_section_offsets()
            self.assertAlmostEqual(first_offsets.beam_m, 0.10)
            self.assertAlmostEqual(first_offsets.draft_m, 0.15)

            sectionresults = work_dir / "sectionresults"
            omega = 2.0
            radiation = [omega**2 * complex(1.0 if row == col else 0.0, 0.05) for row in range(3) for col in range(3)]
            diffraction = [complex(1.0 + idx, 0.0) for idx in range(3)]
            froude_krylov = [complex(2.0 + idx, 0.0) for idx in range(3)]
            lines = [
                "Synthetic coefficients",
                "1",
                f"{omega:.6f} 1 0.0",
                " ".join(f"({value.real:.6f},{value.imag:.6f})" for value in radiation),
                " ".join(f"({value.real:.6f},{value.imag:.6f})" for value in diffraction),
                " ".join(f"({value.real:.6f},{value.imag:.6f})" for value in froude_krylov),
                "123.456",
            ]
            sectionresults.write_text("\n".join(lines), encoding="ascii")
            parsed = parse_sectionresults(sectionresults)
            rows = pdstrip_section_bem_comparison_rows(
                parsed,
                geometry,
                station_indices=(1,),
                frequency_indices=(1,),
                free_surface_panel_count_per_side=2,
                body_panel_count=4,
            )
            self.assertEqual(len(rows), 9)
            self.assertIn("added_mass_rel_error_vs_pdstrip", rows[0])
            self.assertIn("damping_rel_error_sign_adjusted_vs_pdstrip", rows[0])

    def test_station_hull_section_case_writes_parseable_pdstrip_geometry(self):
        hull = StationHull(
            length_m=2.0,
            stations=(
                HardChineStation(x_m=0.0, beam_m=0.4, draft_m=0.12, deadrise_deg=20.0),
                HardChineStation(x_m=2.0, beam_m=0.2, draft_m=0.08, deadrise_deg=25.0),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            write_station_hull_section_case(work_dir, hull, point_count_per_side=3)
            self.assertTrue((work_dir / "pdstrip.inp").exists())
            geometry = parse_pdstrip_geometry(work_dir / "geomet.out")
            self.assertEqual(geometry.section_count, 2)
            self.assertFalse(geometry.symmetric)
            self.assertGreater(geometry.reference_draft_m, 0.0)
            self.assertAlmostEqual(geometry.sections[0].to_section_offsets().beam_m, 0.4)

    def test_station_hull_section_case_skips_wigley_zero_area_end_sections(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=41)
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            write_station_hull_section_case(work_dir, hull, point_count_per_side=8)
            geometry = parse_pdstrip_geometry(work_dir / "geomet.out")
            self.assertEqual(geometry.section_count, 39)
            self.assertGreater(geometry.sections[0].x_m, 0.0)
            self.assertGreater(geometry.sections[0].to_section_offsets().beam_m, 0.01)

    def test_station_hull_section_runner_missing_source_is_not_evaluated(self):
        hull = StationHull(
            length_m=1.0,
            stations=(
                HardChineStation(x_m=0.0, beam_m=0.2, draft_m=0.08, deadrise_deg=20.0),
                HardChineStation(x_m=1.0, beam_m=0.2, draft_m=0.08, deadrise_deg=20.0),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pdstrip_station_hull_sections(
                Path(tmp) / "work",
                hull,
                source_dir=Path(tmp) / "missing_source",
                compiler="definitely_missing_fortran",
            )
            self.assertEqual(result.status, "NOT_EVALUATED")
            self.assertIsNone(result.parsed)

    def test_external_pdstrip_sections_assemble_zero_speed_6dof_matrices(self):
        hull = StationHull(
            length_m=1.0,
            lcg_from_transom_m=0.5,
            stations=(
                HardChineStation(x_m=0.0, beam_m=0.2, draft_m=0.08, deadrise_deg=20.0),
                HardChineStation(x_m=1.0, beam_m=0.2, draft_m=0.08, deadrise_deg=20.0),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            sectionresults = Path(tmp) / "sectionresults"
            omega = 2.0
            lines = ["Synthetic coefficients", "1"]
            for _station in range(2):
                section_added = [
                    4.0,
                    0.0,
                    0.0,
                    0.0,
                    8.0,
                    0.0,
                    0.0,
                    0.0,
                    2.0,
                ]
                radiation = [omega**2 * complex(value, -0.1 * value) for value in section_added]
                diffraction = [complex(1.0 + idx, 0.0) for idx in range(3)]
                froude_krylov = [complex(2.0 + idx, 0.0) for idx in range(3)]
                lines.append(f"{omega:.6f} 1 0.0")
                lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in radiation))
                lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in diffraction))
                lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in froude_krylov))
            lines.append("123.456")
            sectionresults.write_text("\n".join(lines), encoding="ascii")
            parsed = parse_sectionresults(sectionresults)
            matrices = assemble_external_pdstrip_section_6dof_matrices(hull, parsed, omega_rad_s=omega)
            self.assertEqual(matrices.status, PDSTRIP_EXTERNAL_SECTIONS_STATUS)
            self.assertEqual(matrices.added_mass.shape, (6, 6))
            self.assertAlmostEqual(matrices.added_mass[2, 2], 8.0)
            self.assertGreater(matrices.damping[2, 2], 0.0)
            self.assertTrue((matrices.added_mass.T == matrices.added_mass).all())

    def test_external_pdstrip_sections_assemble_with_wigley_active_station_subset(self):
        hull = make_wigley_iii_hull(length_m=1.0, beam_m=0.1, draft_m=0.0625, station_count=5)
        with tempfile.TemporaryDirectory() as tmp:
            sectionresults = Path(tmp) / "sectionresults"
            omega = 2.0
            lines = ["Synthetic active Wigley coefficients", "1"]
            for _station in range(3):
                section_added = [
                    4.0,
                    0.0,
                    0.0,
                    0.0,
                    8.0,
                    0.0,
                    0.0,
                    0.0,
                    2.0,
                ]
                radiation = [omega**2 * complex(value, -0.1 * value) for value in section_added]
                diffraction = [complex(1.0 + idx, 0.0) for idx in range(3)]
                froude_krylov = [complex(2.0 + idx, 0.0) for idx in range(3)]
                lines.append(f"{omega:.6f} 1 0.0")
                lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in radiation))
                lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in diffraction))
                lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in froude_krylov))
            lines.append("123.456")
            sectionresults.write_text("\n".join(lines), encoding="ascii")
            parsed = parse_sectionresults(sectionresults)
            matrices = assemble_external_pdstrip_section_6dof_matrices(hull, parsed, omega_rad_s=omega)
            self.assertEqual(matrices.status, PDSTRIP_EXTERNAL_SECTIONS_STATUS)
            self.assertAlmostEqual(matrices.added_mass[2, 2], 6.0)
            self.assertGreater(matrices.damping[2, 2], 0.0)

    def test_pdstrip_external_smoke_missing_source_is_not_evaluated(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            missing_source = Path(tmp) / "missing_pdstrip"
            summary = validate_pdstrip_external_smoke(
                out_dir,
                source_dir=missing_source,
                compiler="definitely_missing_fortran",
            )
            self.assertTrue((out_dir / "pdstrip_external_smoke.csv").exists())
            self.assertIn("NOT_EVALUATED", set(summary["status"]))
            self.assertFalse(summary["status"].eq("PASS").all())


if __name__ == "__main__":
    unittest.main()
