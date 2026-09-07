#!/usr/bin/env python3
"""Negative tests for the Mesen battery-corruption evidence verifier."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_mesen_battery_corruption import (
    BACKUP_OFFSET,
    MESEN_SHA256,
    MUTATION_RELATIVE_OFFSET,
    PHASES,
    PRIMARY_SIZE,
    ROOT,
    SAVE_MAGIC,
    SAVE_MAGIC_OFFSET,
    SAVE_SIZE,
    differing_offsets,
    sha256_bytes,
    sha256_path,
    verify_run,
)


class BatteryCorruptionEvidenceTests(unittest.TestCase):

    def test_corruption_probe_observes_without_memory_injection(self) -> None:
        source = (
            ROOT / "tools" / "mesen_battery_corruption_probe.lua"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "emu.write(",
            "emu.setMemory",
            "emu.loadSavestate",
            "emu.rewind",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("emu.setInput(desiredInput, 0)", source)

    def test_runner_builds_both_exact_one_byte_cases(self) -> None:
        source = (
            ROOT / "tools" / "run-mesen-battery-persistence.ps1"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("$MutationRelativeOffset = 0x0050", source)
        self.assertIn("$BackupOffset = 0x0C00", source)
        self.assertIn("-MutationOffset $MutationRelativeOffset", source)
        self.assertIn(
            "-MutationOffset ($BackupOffset + $MutationRelativeOffset)",
            source,
        )
        self.assertIn("$Differences -ne 1", source)

    def _write_phase(
        self,
        run_dir: Path,
        slug: str,
        marker: str,
        script: str,
        rom_hash: str,
    ) -> None:
        phase = run_dir / slug
        phase.mkdir(parents=True)
        extra = " memoryInjection=false" if slug.endswith("corrupt") else ""
        stdout = f"{marker} region=Dendy{extra}\n".encode()
        stderr = b""
        (phase / "mesen.stdout.txt").write_bytes(stdout)
        (phase / "mesen.stderr.txt").write_bytes(stderr)
        script_hash = sha256_path(ROOT / "tools" / script)
        lines = [
            "Pokemon Yellow NES - Mesen 2.2.1 scenario manifest",
            f"Mesen executable SHA-256: {MESEN_SHA256}",
            f"ROM SHA-256 before: {rom_hash}",
            f"ROM SHA-256 after: {rom_hash}",
            "iNES mapper: 163",
            "Region: Dendy",
            "Expected effective region: Dendy",
            "Strict hardware profile: True",
            "Full NES debug-stop profile: True",
            f"Expected marker: {marker}",
            "Expected marker observed: True",
            "Expected effective region observed: True",
            "Mesen process exit code: 0",
            f"Mesen stdout SHA-256: {sha256_bytes(stdout)}",
            f"Mesen stderr SHA-256: {sha256_bytes(stderr)}",
            f"Mesen terminal output: {stdout.decode().strip()}",
            "Timed out: False",
            f"Lua scenario: C:\\fixture\\tools\\{script}",
            f"Lua scenario SHA-256 before: {script_hash}",
            f"Lua scenario SHA-256 after: {script_hash}",
            "Result: PASS",
        ]
        (phase / "mesen_run_manifest.txt").write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    def _fixture(self) -> tuple[Path, Path, tempfile.TemporaryDirectory]:
        temporary = tempfile.TemporaryDirectory()
        base = Path(temporary.name)
        run_dir = base / "run"
        run_dir.mkdir()
        rom_path = base / "fixture.nes"
        rom_path.write_bytes(b"NES\x1a" + bytes(64))
        rom_hash = sha256_path(rom_path)
        for slug, (marker, script) in PHASES.items():
            self._write_phase(run_dir, slug, marker, script, rom_hash)

        baseline = bytearray(SAVE_SIZE)
        baseline[SAVE_MAGIC_OFFSET : SAVE_MAGIC_OFFSET + 4] = SAVE_MAGIC
        primary = bytearray(baseline)
        backup = bytearray(baseline)
        primary[MUTATION_RELATIVE_OFFSET] ^= 1
        backup[BACKUP_OFFSET + MUTATION_RELATIVE_OFFSET] ^= 1
        evidence = run_dir / "evidence"
        evidence.mkdir()
        (evidence / "created-save-before-reload.sav").write_bytes(baseline)
        (evidence / "primary-corrupt-before-launch.sav").write_bytes(primary)
        (evidence / "backup-corrupt-before-launch.sav").write_bytes(backup)

        resumed = b"PNG-resumed-room"
        fallback = b"PNG-new-game-fallback"
        (run_dir / "02-create-save" / "battery_create_4000.png").write_bytes(
            resumed
        )
        (
            run_dir / "03-reload-save" / "battery_load_resumed_room.png"
        ).write_bytes(resumed)
        (run_dir / "01-fresh-control" / "battery_control_final.png").write_bytes(
            fallback
        )
        for slug, fixture, screen in (
            ("04-primary-corrupt", primary, resumed),
            ("05-backup-corrupt", backup, fallback),
        ):
            phase = run_dir / slug
            (phase / "battery_corruption_initial_sram.bin").write_bytes(fixture)
            (phase / "battery_corruption_final_sram.bin").write_bytes(baseline)
            (phase / "battery_corruption_final.png").write_bytes(screen)

        top_lines = [
            "Pokemon Yellow NES - Mesen 2.2.1 battery persistence suite",
            f"ROM SHA-256: {rom_hash}",
            "iNES mapper: 163",
            f"Battery/save-RAM bytes: {SAVE_SIZE}",
            "Region: Dendy",
            "Strict hardware profile: True",
            "Full NES debug-stop profile: True",
            f"Created save SHA-256 before reload: {sha256_bytes(baseline)}",
            (
                "Primary-corrupt fixture SHA-256: "
                f"{sha256_bytes(primary)}"
            ),
            f"Backup-corrupt fixture SHA-256: {sha256_bytes(backup)}",
            f"Corruption relative offset: 0x{MUTATION_RELATIVE_OFFSET:04X}",
            "Corruption fixture changed bytes per case: 1",
            "Primary-corrupt initial SRAM equals fixture: true",
            "Backup-corrupt initial SRAM equals fixture: true",
            "Primary corruption restored from valid backup: true",
            "Primary-corrupt CONT equals valid resumed room: true",
            "Backup-corrupt CONT equals fresh fallback: true",
            "Corruption scenarios use memory injection: false",
            "Result: PASS",
        ]
        (run_dir / "battery_persistence_manifest.txt").write_text(
            "\n".join(top_lines) + "\n",
            encoding="utf-8",
        )
        return run_dir, rom_path, temporary

    def test_valid_synthetic_evidence_passes(self) -> None:
        run_dir, rom_path, temporary = self._fixture()
        self.addCleanup(temporary.cleanup)
        report, errors = verify_run(run_dir, rom_path)
        self.assertEqual(errors, [])
        self.assertEqual(report["result"], "PASS")

    def test_mutated_backup_outcome_is_rejected(self) -> None:
        run_dir, rom_path, temporary = self._fixture()
        self.addCleanup(temporary.cleanup)
        path = run_dir / "05-backup-corrupt" / "battery_corruption_final.png"
        path.write_bytes(b"different outcome")
        _, errors = verify_run(run_dir, rom_path)
        self.assertTrue(any("fresh fallback" in error for error in errors))

    def test_corruption_must_be_one_byte_in_the_selected_block(self) -> None:
        run_dir, rom_path, temporary = self._fixture()
        self.addCleanup(temporary.cleanup)
        path = run_dir / "evidence" / "backup-corrupt-before-launch.sav"
        data = bytearray(path.read_bytes())
        data[BACKUP_OFFSET + MUTATION_RELATIVE_OFFSET + 1] ^= 1
        path.write_bytes(data)
        _, errors = verify_run(run_dir, rom_path)
        self.assertTrue(any("exact one-byte case" in error for error in errors))

    def test_differing_offsets_reports_exact_positions(self) -> None:
        first = bytes(8)
        second = bytearray(first)
        second[2] = 1
        second[7] = 2
        self.assertEqual(differing_offsets(first, second), [2, 7])


if __name__ == "__main__":
    unittest.main()
