#!/usr/bin/env python3
"""Unit and mutation tests for the official external-patcher proof builder."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from tools.generate_external_patcher_proof import (
    FLIPS_SOURCE,
    ProofConfig,
    ProofError,
    ToolPins,
    atomic_write_json,
    canonical_verified_utc,
    generate_and_write,
    generate_proof,
    sha256_file,
)


def write_file(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def write_fixed_zip(path: Path, member: str, payload: bytes) -> Path:
    info = zipfile.ZipInfo(member, date_time=(2022, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, payload)
    return path


@dataclass
class FakePatcherRunner:
    target_bytes: bytes
    corrupt_call: int | None = None
    fail_call: int | None = None
    mutate_after_call: tuple[int, Path] | None = None

    def __post_init__(self) -> None:
        self.commands: list[list[str]] = []
        self.work_directories: list[Path] = []

    def __call__(
        self, command: Sequence[str], cwd: Path, timeout: float
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        self.commands.append(list(command))
        self.work_directories.append(cwd)
        call_number = len(self.commands)
        if self.fail_call == call_number:
            return subprocess.CompletedProcess(
                list(command), 7, stdout="", stderr="simulated failure"
            )
        if "-ApplyIPS" in command:
            output = Path(command[3])
        else:
            output = Path(command[4])
        payload = self.target_bytes
        if self.corrupt_call == call_number:
            payload += b"\x00"
        output.write_bytes(payload)
        if self.mutate_after_call is not None:
            wanted_call, source = self.mutate_after_call
            if call_number == wanted_call:
                source.write_bytes(source.read_bytes() + b"mutated")
        return subprocess.CompletedProcess(
            list(command), 0, stdout="simulated", stderr=""
        )


class ExternalPatcherProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.target_bytes = b"NES\x1a-certified-target-ROM"
        self.target = write_file(self.root / "target.nes", self.target_bytes)
        self.ips_base = write_file(self.root / "yellow.nes", b"canonical base")
        self.ips_patch = write_file(self.root / "target.ips", b"PATCHEOF")
        self.chinese_base = write_file(
            self.root / "chinese.nes", b"chinese base"
        )
        self.chinese_bps = write_file(self.root / "chinese.bps", b"BPS1chinese")
        self.english_base = write_file(
            self.root / "english.nes", b"english base"
        )
        self.english_bps = write_file(self.root / "english.bps", b"BPS1english")
        self.lunar = write_file(self.root / "Lunar IPS.exe", b"lunar fixture")
        self.flips = write_file(self.root / "flips.exe", b"flips fixture")
        self.archive = write_fixed_zip(
            self.root / "flips-windows.zip", "windows/flips.exe", self.flips.read_bytes()
        )
        self.output = self.root / "build/external-patcher-proof.json"
        self.config = ProofConfig(
            root=self.root,
            target_rom=self.target,
            ips_base=self.ips_base,
            ips_patch=self.ips_patch,
            chinese_base=self.chinese_base,
            chinese_bps=self.chinese_bps,
            english_base=self.english_base,
            english_bps=self.english_bps,
            lunar_executable=self.lunar,
            flips_executable=self.flips,
            flips_archive=self.archive,
            output=self.output,
            temp_parent=self.root / "scratch",
            verified_utc="2026-08-09T16:00:00Z",
            timeout_seconds=9,
        )
        self.pins = ToolPins(
            lunar_executable_sha256=sha256_file(self.lunar),
            flips_executable_sha256=sha256_file(self.flips),
            flips_archive_sha256=sha256_file(self.archive),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def identity_path(path: Path) -> str:
        return str(path)

    def _source_hashes(self) -> dict[Path, str]:
        return {
            path: sha256_file(path)
            for path in (
                self.target,
                self.ips_base,
                self.ips_patch,
                self.chinese_base,
                self.chinese_bps,
                self.english_base,
                self.english_bps,
                self.lunar,
                self.flips,
                self.archive,
            )
        }

    def test_three_real_command_shapes_produce_a_complete_atomic_proof(self) -> None:
        before = self._source_hashes()
        runner = FakePatcherRunner(self.target_bytes)
        proof = generate_and_write(
            self.config,
            pins=self.pins,
            runner=runner,
            path_converter=self.identity_path,
        )

        self.assertEqual(proof["result"], "PASS")
        self.assertEqual(proof["target"]["sha256"], sha256_file(self.target))
        self.assertEqual(proof["tools"]["floating_ips"]["source"], FLIPS_SOURCE)
        self.assertEqual(
            proof["tools"]["floating_ips"]["executable_archive_members"],
            ["windows/flips.exe"],
        )
        self.assertEqual(len(proof["roundtrips"]), 3)
        self.assertEqual(
            [(row["format"], row["tool"]) for row in proof["roundtrips"]],
            [
                ("IPS", "lunar_ips"),
                ("BPS", "floating_ips"),
                ("BPS", "floating_ips"),
            ],
        )
        self.assertTrue(
            all(row["byte_identical_to_target"] for row in proof["roundtrips"])
        )
        self.assertEqual(runner.commands[0][1], "-ApplyIPS")
        self.assertEqual(runner.commands[1][1], "--apply")
        self.assertEqual(runner.commands[2][1], "--apply")
        self.assertEqual(before, self._source_hashes())
        self.assertEqual(
            json.loads(self.output.read_text(encoding="utf-8")), proof
        )
        self.assertFalse(
            any(self.config.temp_parent.glob(".external-patcher-proof-*"))
        )

    def test_each_mutated_patcher_output_is_rejected_without_publication(self) -> None:
        for corrupt_call in (1, 2, 3):
            with self.subTest(corrupt_call=corrupt_call):
                self.output.parent.mkdir(parents=True, exist_ok=True)
                self.output.write_text("existing certified proof\n", encoding="utf-8")
                runner = FakePatcherRunner(
                    self.target_bytes, corrupt_call=corrupt_call
                )
                with self.assertRaisesRegex(ProofError, "non identique"):
                    generate_and_write(
                        self.config,
                        pins=self.pins,
                        runner=runner,
                        path_converter=self.identity_path,
                    )
                self.assertEqual(
                    self.output.read_text(encoding="utf-8"),
                    "existing certified proof\n",
                )
                self.assertFalse(
                    any(self.config.temp_parent.glob(".external-patcher-proof-*"))
                )

    def test_nonzero_external_process_is_rejected_without_publication(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text("keep me", encoding="utf-8")
        runner = FakePatcherRunner(self.target_bytes, fail_call=2)
        with self.assertRaisesRegex(ProofError, "code 7"):
            generate_and_write(
                self.config,
                pins=self.pins,
                runner=runner,
                path_converter=self.identity_path,
            )
        self.assertEqual(self.output.read_text(encoding="utf-8"), "keep me")

    def test_official_tool_hash_pin_rejects_an_executable_mutation(self) -> None:
        self.lunar.write_bytes(self.lunar.read_bytes() + b"tampered")
        runner = FakePatcherRunner(self.target_bytes)
        with self.assertRaisesRegex(ProofError, "Lunar IPS 1.03 x64"):
            generate_proof(
                self.config,
                pins=self.pins,
                runner=runner,
                path_converter=self.identity_path,
            )
        self.assertEqual(runner.commands, [])

    def test_archive_must_really_contain_the_pinned_flips_executable(self) -> None:
        write_fixed_zip(self.archive, "windows/flips.exe", b"different executable")
        pins = ToolPins(
            lunar_executable_sha256=sha256_file(self.lunar),
            flips_executable_sha256=sha256_file(self.flips),
            flips_archive_sha256=sha256_file(self.archive),
        )
        runner = FakePatcherRunner(self.target_bytes)
        with self.assertRaisesRegex(ProofError, "n'existe pas octet pour octet"):
            generate_proof(
                self.config,
                pins=pins,
                runner=runner,
                path_converter=self.identity_path,
            )
        self.assertEqual(runner.commands, [])

    def test_source_mutation_during_execution_invalidates_the_whole_proof(self) -> None:
        original = self.ips_patch.read_bytes()
        runner = FakePatcherRunner(
            self.target_bytes, mutate_after_call=(3, self.ips_patch)
        )
        with self.assertRaisesRegex(ProofError, "patch IPS"):
            generate_proof(
                self.config,
                pins=self.pins,
                runner=runner,
                path_converter=self.identity_path,
            )
        self.assertNotEqual(self.ips_patch.read_bytes(), original)

    def test_atomic_writer_leaves_no_partial_file_when_replace_fails(self) -> None:
        path = self.root / "atomic.json"
        path.write_text("old", encoding="utf-8")
        import tools.generate_external_patcher_proof as module

        real_replace = module.os.replace

        def fail_replace(source: Path | str, destination: Path | str) -> None:
            del source, destination
            raise OSError("simulated replace failure")

        module.os.replace = fail_replace
        try:
            with self.assertRaisesRegex(OSError, "replace failure"):
                atomic_write_json(path, {"new": True})
        finally:
            module.os.replace = real_replace
        self.assertEqual(path.read_text(encoding="utf-8"), "old")
        self.assertEqual(list(self.root.glob(".atomic.json.*.tmp")), [])

    def test_timestamp_validation_is_strict_and_calendar_aware(self) -> None:
        self.assertEqual(
            canonical_verified_utc("2026-08-09T16:00:00Z"),
            "2026-08-09T16:00:00Z",
        )
        for invalid in (
            "2026-08-09 16:00:00Z",
            "2026-02-30T16:00:00Z",
            "2026-08-09T16:00:00+00:00",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ProofError):
                    canonical_verified_utc(invalid)

    def test_tool_hashes_in_proof_are_hashes_of_supplied_files(self) -> None:
        runner = FakePatcherRunner(self.target_bytes)
        proof = generate_proof(
            self.config,
            pins=self.pins,
            runner=runner,
            path_converter=self.identity_path,
        )
        self.assertEqual(
            proof["tools"]["lunar_ips"]["sha256"], sha256_file(self.lunar)
        )
        self.assertEqual(
            proof["tools"]["floating_ips"]["executable_sha256"],
            sha256_file(self.flips),
        )
        self.assertEqual(
            proof["tools"]["floating_ips"]["archive_sha256"],
            sha256_file(self.archive),
        )
        for row in proof["roundtrips"]:
            self.assertEqual(row["output_sha256"], hashlib.sha256(self.target_bytes).hexdigest())


if __name__ == "__main__":
    unittest.main()
