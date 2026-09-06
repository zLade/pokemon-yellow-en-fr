#!/usr/bin/env python3
"""Mutation tests for the final Route 1 Mesen matrix verifier."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.verify_mesen_route1_matrix import (
    EXPECTED_INPUT_SHA256,
    EXPECTED_MARKER,
    EXPECTED_PROBE_SHA256,
    EXPECTED_REGIONS,
    EXPECTED_ROM_SHA256,
    build_matrix_report,
    verify_run_files,
    verify_manifest_text,
    write_report,
)


ROOT = Path(__file__).resolve().parents[1]
REAL_MATRIX_DIR = ROOT / "build" / "runtime-proof-final-1fefecbf-route1"


def valid_manifest(region: str = "Dendy") -> str:
    return "\n".join(
        (
            "Pokemon Yellow NES - test manifest",
            f"ROM SHA-256 before: {EXPECTED_ROM_SHA256}",
            f"ROM SHA-256 after: {EXPECTED_ROM_SHA256}",
            f"Region: {region}",
            f"Expected effective region: {region}",
            "Strict hardware profile: True",
            "Full NES debug-stop profile: True",
            f"Lua scenario SHA-256 before: {EXPECTED_PROBE_SHA256}",
            f"Lua scenario SHA-256 after: {EXPECTED_PROBE_SHA256}",
            f"Scenario input SHA-256 before: {EXPECTED_INPUT_SHA256}",
            f"Scenario input SHA-256 after: {EXPECTED_INPUT_SHA256}",
            f"Expected marker: {EXPECTED_MARKER}",
            "Expected marker observed: True",
            "Expected effective region observed: True",
            "Mesen process exit code: 0",
            f"Mesen stdout SHA-256: {'a' * 64}",
            f"Mesen stderr SHA-256: {'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}",
            (
                f"Mesen terminal output: {EXPECTED_MARKER} "
                f"mapper=163 region={region} frames=7108 dialogues=none "
                "writes_to_game=0 bootstrap=campaign_prototype "
                "state_driven=true battle_recoveries=1 "
                "viridian_aligned=true alignment_dialogues_dismissed=0 "
                "campaign_dialogues_dismissed=0 parcel_route_done=false"
            ),
            "Timed out: False",
            "Screenshots: 1",
            "Result: PASS",
            "",
        )
    )


def mutate_field(text: str, key: str, value: str) -> str:
    prefix = f"{key}:"
    lines = text.splitlines()
    matches = [index for index, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {key!r} field")
    lines[matches[0]] = f"{key}: {value}"
    return "\n".join(lines) + "\n"


class ManifestMutationTests(unittest.TestCase):
    def verify(self, text: str) -> dict[str, object]:
        return verify_manifest_text(
            text,
            slug="dendy",
            expected_region="Dendy",
        )

    def test_valid_manifest_passes_every_check(self) -> None:
        record = self.verify(valid_manifest())
        self.assertEqual(record["result"], "PASS")
        self.assertTrue(all(record["checks"].values()))
        self.assertEqual(record["errors"], [])

    def test_each_required_semantic_mutation_is_rejected(self) -> None:
        mutations = (
            ("Result", "FAIL", "result_pass"),
            ("ROM SHA-256 before", "0" * 64, "rom_sha256"),
            ("ROM SHA-256 after", "0" * 64, "rom_sha256"),
            ("Lua scenario SHA-256 before", "0" * 64, "probe_sha256"),
            ("Lua scenario SHA-256 after", "0" * 64, "probe_sha256"),
            ("Scenario input SHA-256 before", "0" * 64, "input_sha256"),
            ("Scenario input SHA-256 after", "0" * 64, "input_sha256"),
            ("Region", "Pal", "region_expected"),
            ("Expected effective region", "Pal", "region_expected"),
            (
                "Expected effective region observed",
                "False",
                "region_observed",
            ),
            ("Expected marker", "WRONG_PASS", "marker_observed"),
            ("Expected marker observed", "False", "marker_observed"),
            ("Mesen process exit code", "1", "exit_code_zero"),
            ("Timed out", "True", "not_timed_out"),
            ("Screenshots", "0", "screenshots_positive"),
            ("Strict hardware profile", "False", "strict_hardware"),
            ("Full NES debug-stop profile", "False", "full_debug"),
            (
                "Mesen stderr SHA-256",
                "f" * 64,
                "recorded_stream_hashes",
            ),
        )
        baseline = valid_manifest()
        for key, value, failed_check in mutations:
            with self.subTest(key=key, value=value):
                record = self.verify(mutate_field(baseline, key, value))
                self.assertEqual(record["result"], "FAIL")
                self.assertFalse(record["checks"][failed_check])
                self.assertTrue(record["errors"])

    def test_equal_but_noncanonical_hash_pair_is_rejected(self) -> None:
        mutated = mutate_field(
            valid_manifest(), "ROM SHA-256 before", "f" * 64
        )
        mutated = mutate_field(mutated, "ROM SHA-256 after", "f" * 64)
        record = self.verify(mutated)
        self.assertTrue(record["checks"]["before_after_equal"])
        self.assertFalse(record["checks"]["rom_sha256"])
        self.assertEqual(record["result"], "FAIL")

    def test_terminal_claims_are_checked_independently(self) -> None:
        no_marker = mutate_field(
            valid_manifest(),
            "Mesen terminal output",
            "mapper=163 region=Dendy frames=7108",
        )
        wrong_region = mutate_field(
            valid_manifest(),
            "Mesen terminal output",
            f"{EXPECTED_MARKER} mapper=163 region=Pal frames=7108",
        )
        self.assertFalse(self.verify(no_marker)["checks"]["marker_observed"])
        self.assertFalse(self.verify(wrong_region)["checks"]["region_observed"])

        overclaimed = mutate_field(
            valid_manifest(),
            "Mesen terminal output",
            (
                f"{EXPECTED_MARKER} mapper=163 region=Dendy frames=7108 "
                "dialogues=all writes_to_game=0 bootstrap=campaign_prototype "
                "state_driven=true battle_recoveries=1 viridian_aligned=true "
                "alignment_dialogues_dismissed=0 "
                "campaign_dialogues_dismissed=0 parcel_route_done=true"
            ),
        )
        self.assertFalse(
            self.verify(overclaimed)["checks"]["diagnostic_scope_qualified"]
        )

    def test_missing_and_duplicate_required_fields_are_rejected(self) -> None:
        missing = "\n".join(
            line
            for line in valid_manifest().splitlines()
            if not line.startswith("Screenshots:")
        )
        duplicate = valid_manifest() + "Result: PASS\n"
        for text, fragment in (
            (missing, "missing required field: Screenshots"),
            (duplicate, "duplicate required field: Result"),
        ):
            with self.subTest(fragment=fragment):
                record = self.verify(text)
                self.assertEqual(record["result"], "FAIL")
                self.assertIn(fragment, record["errors"])

    def test_malformed_numeric_and_boolean_values_are_rejected(self) -> None:
        for key, value in (
            ("Screenshots", "many"),
            ("Mesen process exit code", "zero"),
            ("Strict hardware profile", "true"),
        ):
            with self.subTest(key=key):
                record = self.verify(mutate_field(valid_manifest(), key, value))
                self.assertEqual(record["result"], "FAIL")


class MatrixReportTests(unittest.TestCase):
    def test_three_region_matrix_is_consolidated_and_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            matrix_dir = Path(directory)
            for slug, region in EXPECTED_REGIONS:
                manifest = matrix_dir / slug / "mesen_run_manifest.txt"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(valid_manifest(region), encoding="utf-8")

            report = build_matrix_report(matrix_dir, verify_files=False)
            self.assertEqual(report["result"], "PASS")
            self.assertEqual(report["summary"]["regions_passed"], 3)
            self.assertEqual(report["summary"]["screenshots"], 3)
            self.assertEqual(set(report["regions"]), {"dendy", "ntsc", "pal"})

            output = matrix_dir / "route1_matrix.json"
            write_report(report, output)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")), report
            )

    def test_missing_region_manifest_fails_the_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = build_matrix_report(Path(directory))
        self.assertEqual(report["result"], "FAIL")
        self.assertEqual(report["summary"]["regions_passed"], 0)
        self.assertIn("cannot read manifest", report["regions"]["dendy"]["errors"][0])

    def test_real_final_matrix_passes(self) -> None:
        if os.environ.get("POKEMON_VERIFY_FR_200_ARCHIVE") != "1":
            self.skipTest("matrice Route 1 historique liée à la ROM FR 2.0.0")
        report = build_matrix_report(REAL_MATRIX_DIR)
        self.assertEqual(
            report["result"],
            "PASS",
            {slug: record["errors"] for slug, record in report["regions"].items()},
        )
        self.assertEqual(report["summary"]["regions_passed"], 3)
        self.assertGreater(report["summary"]["screenshots"], 0)
        self.assertEqual(report["project_artifacts"]["result"], "PASS")
        self.assertEqual(
            report["summary"]["scope"],
            "route1_viridian_alignment_only",
        )
        self.assertFalse(report["summary"]["parcel_route_done"])

    def test_mutated_real_stdout_is_rejected(self) -> None:
        source = REAL_MATRIX_DIR / "dendy"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "dendy"
            shutil.copytree(source, target)
            stdout = target / "mesen.stdout.txt"
            stdout.write_bytes(stdout.read_bytes() + b"changed\n")
            text = (target / "mesen_run_manifest.txt").read_text(
                encoding="utf-8-sig"
            )
            record = verify_manifest_text(
                text,
                slug="dendy",
                expected_region="Dendy",
            )
            verify_run_files(
                target,
                record,
                slug="dendy",
                project_root=ROOT,
            )
        self.assertEqual(record["result"], "FAIL")
        self.assertFalse(record["checks"]["actual_stream_hashes"])


if __name__ == "__main__":
    unittest.main()
