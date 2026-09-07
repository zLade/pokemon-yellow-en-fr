#!/usr/bin/env python3
"""Synthetic, ROM-free tests for the English release orchestrator."""

from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.build_english_release import (
    CHINESE_BPS_FILENAME,
    ENGLISH_BPS_FILENAME,
    EXPECTED_CATALOG_COUNTS,
    EXPECTED_FRENCH_NON_REGRESSION_SHA256,
    EXPECTED_MESEN_SHA256,
    EXPECTED_MESEN_SCENARIOS,
    EXPECTED_ROM_SHA256,
    EXPECTED_ROUTE1_INPUT_SHA256,
    EXPECTED_RUNTIME_REGIONS,
    EXPECTED_RUNTIME_STEPS_PER_REGION,
    IPS_FILENAME,
    ROM_FILENAME,
    VALIDATION_LIMITS,
    EnglishReleaseError,
    _copy_evidence_tree,
    _documentation,
    assert_no_complete_images,
    assert_portable_text_tree,
    assistant_build_arguments,
    create_verified_ips,
    publish_transactionally,
    normalize_log_paths,
    validate_catalogue,
    validate_mesen_evidence,
    write_sha256sums,
)


CATALOG_FIELDS = (
    "stable_key",
    "record_type",
    "category",
    "chinese_text",
    "english_v2",
    "editorial_origin",
    "source_resolution",
    "review_status",
    "compression",
    "compression_justification",
)


def write_reviewed_catalogue(path: Path, *, pending_first: bool = False) -> None:
    rows: list[dict[str, str]] = []
    for index in range(1844):
        if index < 967:
            category = "In-game dialogue"
        elif index < 970:
            category = "Introduction"
        elif index < 1129:
            category = "Pokédex"
        else:
            category = "Ordinary text"
        rows.append(
            {
                "stable_key": f"MAIN:0x{index:06X}",
                "record_type": "MAIN",
                "category": category,
                "chinese_text": f"中文{index}",
                "english_v2": f"Reviewed {index}",
                "editorial_origin": "chinese_source_review",
                "source_resolution": "pointer_table",
                "review_status": "approved",
                "compression": "",
                "compression_justification": "",
            }
        )
    for index in range(85):
        rows.append(
            {
                "stable_key": f"RESTORED:0x{index:06X}",
                "record_type": "RESTORED",
                "category": "Restored dialogue",
                "chinese_text": f"恢复{index}",
                "english_v2": f"Restored {index}",
                "editorial_origin": "chinese_source_review",
                "source_resolution": "restored_pointer",
                "review_status": "approved",
                "compression": "",
                "compression_justification": "",
            }
        )
    if pending_first:
        rows[0]["review_status"] = "pending"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_runtime_evidence(root: Path, rom_hash: str) -> None:
    runtime_lines = [
        "Suite: NJ046 English Fidelity 2.0 runtime",
        f"Candidate SHA-256: {rom_hash}",
        "Regions: " + ",".join(EXPECTED_RUNTIME_REGIONS),
    ]
    step_names = [
        f"{region}/{name}"
        for region in EXPECTED_RUNTIME_REGIONS
        for name in EXPECTED_RUNTIME_STEPS_PER_REGION
    ]
    runtime_lines.append(f"Executed steps: {len(step_names)}")
    runtime_lines.extend(
        f"Step {index:02d}: PASS | {name} | 1.0s"
        for index, name in enumerate(step_names, start=1)
    )
    runtime_lines.append("Result: PASS")
    (root / "english_runtime_manifest.txt").write_text(
        "\n".join(runtime_lines) + "\n", encoding="utf-8"
    )

    for region in EXPECTED_RUNTIME_REGIONS:
        region_root = root / region.casefold()
        for scenario_name, (
            script_name,
            expected_marker,
            input_policy,
        ) in EXPECTED_MESEN_SCENARIOS.items():
            scenario = region_root / scenario_name
            scenario.mkdir(parents=True)
            script_hash = hashlib.sha256(
                Path(__file__).with_name(script_name).read_bytes()
            ).hexdigest()
            if input_policy == "critical":
                input_hash = "a" * 64
                input_path = "critical-restoration-targets.tsv"
            elif input_policy == "route1":
                input_hash = EXPECTED_ROUTE1_INPUT_SHA256
                input_path = "route1.inputs.bin"
            else:
                input_hash = ""
                input_path = ""
            (scenario / "mesen_run_manifest.txt").write_text(
                "\n".join(
                    (
                        f"Mesen executable SHA-256: {EXPECTED_MESEN_SHA256}",
                        f"ROM SHA-256 before: {rom_hash}",
                        f"ROM SHA-256 after: {rom_hash}",
                        "iNES mapper: 163",
                        f"Region: {region}",
                        f"Expected effective region: {region}",
                        "Strict hardware profile: True",
                        "Full NES debug-stop profile: True",
                        f"Lua scenario: tools/{script_name}",
                        f"Lua scenario SHA-256 before: {script_hash}",
                        f"Lua scenario SHA-256 after: {script_hash}",
                        f"Scenario input: {input_path}",
                        f"Scenario input SHA-256 before: {input_hash}",
                        f"Scenario input SHA-256 after: {input_hash}",
                        f"Expected marker: {expected_marker}",
                        "Expected marker observed: True",
                        "Timed out: False",
                        "Result: PASS",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
        (region_root / "battery_persistence_manifest.txt").write_text(
            "\n".join(
                (
                    f"ROM SHA-256: {rom_hash}",
                    "iNES mapper: 163",
                    f"Region: {region}",
                    "Strict hardware profile: True",
                    "Full NES debug-stop profile: True",
                    "Primary corruption restored from valid backup: true",
                    "Primary-corrupt CONT equals valid resumed room: true",
                    "Backup-corrupt CONT equals fresh fallback: true",
                    "Corruption scenarios use memory injection: false",
                    "Result: PASS",
                )
            )
            + "\n",
            encoding="utf-8",
        )


class EnglishReleaseWrapperTests(unittest.TestCase):
    def test_rom_source_hashes_are_exactly_pinned(self) -> None:
        self.assertEqual(
            EXPECTED_ROM_SHA256,
            {
                "chinese_nj046": (
                    "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e6"
                    "5271e2f7b40c65ed"
                ),
                "english_2015": (
                    "d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac"
                    "112509d658a9943b"
                ),
                "yellow_canonical": (
                    "69520103102677b33b47c15fae804dc1a742347a9ee1b02a"
                    "9195e795eb6e431b"
                ),
            },
        )

    def test_french_non_regression_goldens_are_pinned_and_built(self) -> None:
        self.assertEqual(
            EXPECTED_FRENCH_NON_REGRESSION_SHA256["final_rom"],
            "1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b",
        )
        source = Path(__file__).with_name("build_english_release.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("self.verify_french_non_regression()", source)
        self.assertIn("french_non_regression.json", source)

    def test_builder_uses_the_declared_english_profile_and_one_catalogue(self) -> None:
        args = assistant_build_arguments(
            assistant=Path("assistant.py"),
            catalog=Path("catalog.csv"),
            pointer_variants=Path("pointer_variants.csv"),
            english_rom=Path("english.nes"),
            output_rom=Path("target.nes"),
            output_ips=Path("build.ips"),
            allocation_csv=Path("allocation.csv"),
        )
        strings = [str(value) for value in args]
        self.assertEqual(strings[:4], ["assistant.py", "build-repacked", "--profile", "en-US"])
        self.assertEqual(strings[strings.index("--csv") + 1], "catalog.csv")
        self.assertEqual(
            strings[strings.index("--restorations-csv") + 1],
            "catalog.csv",
        )
        self.assertEqual(
            strings[strings.index("--pointer-variants-csv") + 1],
            "pointer_variants.csv",
        )
        self.assertEqual(
            strings[strings.index("--allocation-output") + 1],
            "allocation.csv",
        )
        self.assertIn("--bank-budget-output", strings)
        self.assertIn("--fixed-overflow-output", strings)

    def test_release_wrapper_runs_english_static_gates_it_publishes(self) -> None:
        source = (
            Path(__file__).with_name("build_english_release.py")
            .read_text(encoding="utf-8")
        )
        for tool in (
            "validate_english_catalog.py",
            "validate_english_repacked.py",
            "validate_mapper163.py",
            "validate_english_bank_budget.py",
            "validate_english_glyph_residue.py",
            "validate_english_runtime_text_reads.py",
            "prepare_critical_restoration_runtime.py",
            "english_pointer_manifest.py",
        ):
            with self.subTest(tool=tool):
                self.assertIn(tool, source)
        self.assertIn(
            '"tools.validate_english_runtime_text_reads"',
            source,
        )

    def test_final_wrapper_requires_complete_external_patcher_matrix(self) -> None:
        source = Path(__file__).with_name("build_english_release.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("if not all(external):", source)
        self.assertIn("The final release requires Lunar IPS", source)

    def test_internal_ips_generator_round_trips_synthetic_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base.dat"
            target = root / "target.dat"
            patch = root / "target.ips"
            base.write_bytes(bytes(range(256)) * 2)
            changed = bytearray(base.read_bytes())
            changed[7:14] = b"ENGLISH"
            changed[-1] ^= 0xFF
            target.write_bytes(changed)
            digest = create_verified_ips(base, target, patch)
            self.assertTrue(patch.read_bytes().startswith(b"PATCH"))
            self.assertTrue(patch.read_bytes().endswith(b"EOF"))
            self.assertEqual(digest, hashlib.sha256(patch.read_bytes()).hexdigest())

    def test_direct_script_bootstraps_project_root_for_lazy_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base.dat"
            target = root / "target.dat"
            patch = root / "target.ips"
            base.write_bytes(bytes(range(64)))
            changed = bytearray(base.read_bytes())
            changed[17:21] = b"EN2!"
            target.write_bytes(changed)
            wrapper = Path(__file__).with_name("build_english_release.py").resolve()
            code = (
                "import runpy\n"
                f"namespace = runpy.run_path({str(wrapper)!r})\n"
                "from pathlib import Path\n"
                f"namespace['create_verified_ips'](Path({str(base)!r}), "
                f"Path({str(target)!r}), Path({str(patch)!r}))\n"
            )
            process = subprocess.run(
                [sys.executable, "-I", "-c", code],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout)
            self.assertTrue(patch.is_file())

    def test_catalogue_gate_accepts_only_complete_reviewed_1929_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog.csv"
            write_reviewed_catalogue(catalog)
            summary = validate_catalogue(catalog)
            self.assertEqual(summary.as_dict(), dict(EXPECTED_CATALOG_COUNTS))

            write_reviewed_catalogue(catalog, pending_first=True)
            with self.assertRaisesRegex(EnglishReleaseError, "unreviewed"):
                validate_catalogue(catalog)

    def test_mesen_gate_binds_every_strict_region_run_to_target_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target_hash = "ab" * 32
            write_runtime_evidence(root, target_hash)
            summary = validate_mesen_evidence(root, target_hash)
            self.assertEqual(summary["result"], "PASS")
            self.assertEqual(summary["scenario_manifests"], 48)
            self.assertEqual(summary["battery_manifests"], 3)

            first = next(root.rglob("mesen_run_manifest.txt"))
            first.write_text(
                first.read_text(encoding="utf-8").replace(
                    target_hash, "cd" * 32, 1
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EnglishReleaseError, "different ROM SHA"):
                validate_mesen_evidence(root, target_hash)

            first.write_text(
                first.read_text(encoding="utf-8").replace(
                    "cd" * 32, target_hash, 1
                ),
                encoding="utf-8",
            )
            title_manifest = next(
                path
                for path in root.rglob("mesen_run_manifest.txt")
                if path.parent.name == "06-title-and-new-load"
            )
            title_manifest.write_text(
                title_manifest.read_text(encoding="utf-8").replace(
                    "Expected marker: TITLE_YELLOW_VERSION_PASS",
                    "Expected marker: GENERIC_PASS",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EnglishReleaseError, "marker"):
                validate_mesen_evidence(root, target_hash)

    def test_patch_only_scan_rejects_extension_and_disguised_ines_magic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / CHINESE_BPS_FILENAME).write_bytes(b"BPS1fixture")
            (root / IPS_FILENAME).write_bytes(b"PATCHEOF")
            (root / "README.md").write_text("patch only\n", encoding="utf-8")
            assert_no_complete_images(root)

            forbidden = root / "complete.nes"
            forbidden.write_bytes(b"not even a real ROM")
            with self.assertRaisesRegex(EnglishReleaseError, "Complete ROM image"):
                assert_no_complete_images(root)
            forbidden.unlink()

            disguised = root / "innocent.txt"
            disguised.write_bytes(b"NES\x1a" + b"\0" * 32)
            with self.assertRaisesRegex(EnglishReleaseError, "Complete ROM image"):
                assert_no_complete_images(root)

    def test_private_evidence_accepts_small_snapshots_but_rejects_roms(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            (source / "palette.bin").write_bytes(b"\0" * 32)
            (source / "battery.sav").write_bytes(b"\0" * 8192)
            _copy_evidence_tree(source, destination)
            self.assertEqual((destination / "palette.bin").stat().st_size, 32)
            self.assertEqual((destination / "battery.sav").stat().st_size, 8192)

            (source / "headerless-rom.bin").write_bytes(b"\0" * (8192 + 1))
            with self.assertRaisesRegex(EnglishReleaseError, "Complete ROM image"):
                _copy_evidence_tree(source, destination)
            (source / "headerless-rom.bin").unlink()

            (source / "disguised.bin").write_bytes(b"NES\x1a" + b"\0" * 28)
            with self.assertRaisesRegex(EnglishReleaseError, "Complete ROM image"):
                _copy_evidence_tree(source, destination)

    def test_bundle_text_scan_rejects_local_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / "report.json"
            report.write_text(
                '{"source": "C:\\\\Users\\\\alice\\\\private.nes"}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EnglishReleaseError, "Absolute path"):
                assert_portable_text_tree(root)
            report.write_text('{"source": "$ROOT/yellow.nes"}\n', encoding="utf-8")
            assert_portable_text_tree(root)

    def test_log_paths_use_portable_placeholders(self) -> None:
        original = (
            "/workspace/project/file.csv\n"
            "C:\\Users\\alice\\Desktop\\rom.nes\n"
            "/mnt/c/Users/alice/private/rom.nes\n"
        )
        normalized = normalize_log_paths(original, {"/workspace/project": "$ROOT"})
        self.assertIn("$ROOT/file.csv", normalized)
        self.assertNotIn("alice", normalized)
        self.assertNotIn("/mnt/c/Users", normalized)
        self.assertNotIn("C:\\Users", normalized)

    def test_transactional_promotion_refuses_existing_and_moves_both(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_stage = root / "private-stage"
            dist_stage = root / "dist-stage"
            private_destination = root / "private" / "2.0.0"
            dist_destination = root / "dist" / "2.0.0"
            private_stage.mkdir()
            dist_stage.mkdir()
            (private_stage / "private.txt").write_text("private", encoding="utf-8")
            (dist_stage / "patch.bps").write_bytes(b"BPS1fixture")
            publish_transactionally(
                private_stage,
                private_destination,
                dist_stage,
                dist_destination,
            )
            self.assertTrue((private_destination / "private.txt").is_file())
            self.assertTrue((dist_destination / "patch.bps").is_file())

            another_private = root / "another-private"
            another_dist = root / "another-dist"
            another_private.mkdir()
            another_dist.mkdir()
            with self.assertRaisesRegex(EnglishReleaseError, "already exists"):
                publish_transactionally(
                    another_private,
                    private_destination,
                    another_dist,
                    root / "fresh-dist",
                )

    def test_second_promotion_failure_rolls_the_private_directory_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_stage = root / "private-stage"
            dist_stage = root / "dist-stage"
            private_destination = root / "private" / "2.0.0"
            dist_destination = root / "dist" / "2.0.0"
            private_stage.mkdir()
            dist_stage.mkdir()
            (private_stage / "target.dat").write_bytes(b"private")
            (dist_stage / "target.bps").write_bytes(b"BPS1fixture")

            import tools.build_english_release as module

            real_replace = module.os.replace
            calls = 0

            def fail_second(source: Path | str, destination: Path | str) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated dist promotion failure")
                real_replace(source, destination)

            with patch(
                "tools.build_english_release.os.replace",
                side_effect=fail_second,
            ):
                with self.assertRaisesRegex(OSError, "simulated"):
                    publish_transactionally(
                        private_stage,
                        private_destination,
                        dist_stage,
                        dist_destination,
                    )
            self.assertTrue(private_stage.is_dir())
            self.assertTrue(dist_stage.is_dir())
            self.assertFalse(private_destination.exists())
            self.assertFalse(dist_destination.exists())

    def test_documentation_states_exact_limits_and_no_rom_is_an_output(self) -> None:
        target_hash = "a" * 64
        documents = _documentation(
            target_hash,
            external_patcher_status="not_run_no_complete_pinned_external_tool_matrix",
        )
        joined = "\n".join(documents.values())
        self.assertIn(VALIDATION_LIMITS["hardware_validation"], joined)
        self.assertIn(VALIDATION_LIMITS["ram_quirk"], joined)
        self.assertIn(VALIDATION_LIMITS["harmlessness"], joined)
        self.assertIn(VALIDATION_LIMITS["editorial_status"], joined)
        self.assertIn("HZK16", joined)
        self.assertIn("No complete ROM is included", joined)
        self.assertIn(ROM_FILENAME, joined)
        self.assertIn(CHINESE_BPS_FILENAME, joined)
        self.assertIn(ENGLISH_BPS_FILENAME, joined)

    def test_checksums_cover_every_file_but_not_themselves(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("a", encoding="utf-8")
            nested = root / "review"
            nested.mkdir()
            (nested / "b.csv").write_text("b\n", encoding="utf-8")
            write_sha256sums(root)
            lines = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertTrue(any(line.endswith("  a.txt") for line in lines))
            self.assertTrue(any(line.endswith("  review/b.csv") for line in lines))
            self.assertFalse(any(line.endswith("SHA256SUMS") for line in lines))


if __name__ == "__main__":
    unittest.main()
