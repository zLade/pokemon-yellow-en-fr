#!/usr/bin/env python3
"""Temporary-file integration tests for ``chr_asset_pipeline.py``."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import chr_asset_pipeline as pipeline  # noqa: E402


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_mapper163_rom() -> bytes:
    header = bytearray(16)
    header[:4] = b"NES\x1A"
    header[4] = 1
    header[5] = 0
    header[6] = 0x33
    header[7] = 0xA0
    prg = bytes((index * 17 + 3) & 0xFF for index in range(0x4000))
    return bytes(header) + prg


class ChrAssetPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source_data = synthetic_mapper163_rom()
        self.rom_path = self.root / "source.nes"
        self.rom_path.write_bytes(self.source_data)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_manifest(
        self,
        assets: list[dict[str, object]],
        *,
        name: str = "manifest.json",
        source_hash: str | None = None,
        ips_base_hash: str | None = None,
    ) -> Path:
        manifest = {
            "schema": pipeline.SCHEMA,
            "source_sha256": source_hash or sha256(self.source_data),
            "ips_base_sha256": (
                ips_base_hash
                if ips_base_hash is not None
                else sha256(self.source_data)
            ),
            "assets": assets,
        }
        path = self.root / name
        path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def single_asset() -> list[dict[str, object]]:
        return [
            {
                "id": "asset_a",
                "path": "title/a.chr",
                "offset": "0x0100",
                "length": 64,
                "kind": "chr",
            }
        ]

    @staticmethod
    def overlapping_assets() -> list[dict[str, object]]:
        return [
            {
                "id": "asset_a",
                "path": "title/a.chr",
                "offset": "0x0100",
                "length": 64,
                "kind": "chr",
            },
            {
                "id": "asset_b",
                "path": "title/b.chr",
                "offset": "0x0130",
                "length": 64,
                "kind": "chr",
            },
        ]

    def export(
        self,
        assets: list[dict[str, object]],
        *,
        name: str,
    ) -> tuple[Path, Path]:
        manifest = self.write_manifest(
            assets,
            name=f"{name}.manifest.json",
        )
        pack = self.root / f"{name}.pack"
        report = pipeline.export_pack(manifest, self.rom_path, pack)
        self.assertEqual(report["result"], "PASS")
        return manifest, pack

    def test_noop_export_verify_roundtrip_and_compile(self) -> None:
        manifest, pack = self.export(self.single_asset(), name="noop")

        baseline = pack / "baseline" / "title" / "a.chr"
        work = pack / "work" / "title" / "a.chr"
        preview = pack / "previews" / "title" / "a.chr.png"
        self.assertEqual(baseline.read_bytes(), work.read_bytes())
        self.assertTrue(preview.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

        verify = pipeline.verify_pack(manifest, pack, self.rom_path)
        self.assertEqual(verify["logical_changed_bytes"], 0)
        self.assertEqual(verify["physical_changed_bytes"], 0)
        self.assertEqual(verify["output_sha256"], sha256(self.source_data))

        roundtrip = pipeline.roundtrip_pack(
            manifest,
            pack,
            self.rom_path,
        )
        self.assertTrue(roundtrip["roundtrip"]["assets"])
        self.assertTrue(roundtrip["roundtrip"]["ips"])
        self.assertTrue(roundtrip["roundtrip"]["noop"])

        out_rom = self.root / "noop-output.nes"
        out_ips = self.root / "noop-output.ips"
        report_path = self.root / "noop-output.json"
        report = pipeline.compile_pack(
            manifest,
            pack,
            self.rom_path,
            self.rom_path,
            out_rom,
            out_ips,
            report_path,
        )
        self.assertEqual(out_rom.read_bytes(), self.source_data)
        self.assertEqual(out_ips.read_bytes(), b"PATCHEOF")
        self.assertEqual(
            pipeline.apply_ips(self.source_data, out_ips.read_bytes()),
            out_rom.read_bytes(),
        )
        self.assertEqual(
            json.loads(report_path.read_text(encoding="utf-8"))["output"],
            report["output"],
        )

    def test_export_falls_back_when_directory_rename_is_locked(self) -> None:
        manifest = self.write_manifest(
            self.single_asset(),
            name="onedrive-lock.manifest.json",
        )
        pack = self.root / "onedrive-lock.pack"
        real_replace = pipeline.os.replace

        def replace_with_locked_directory(
            source: object,
            destination: object,
        ) -> None:
            if Path(destination) == pack:
                raise PermissionError("simulated OneDrive scan lock")
            real_replace(source, destination)

        with (
            mock.patch.object(
                pipeline.os,
                "replace",
                side_effect=replace_with_locked_directory,
            ),
            mock.patch.object(pipeline.time, "sleep"),
        ):
            report = pipeline.export_pack(
                manifest,
                self.rom_path,
                pack,
            )

        self.assertEqual(report["result"], "PASS")
        self.assertTrue((pack / "pack.lock.json").is_file())
        self.assertEqual(
            (pack / "baseline" / "title" / "a.chr").read_bytes(),
            self.source_data[0x0100:0x0140],
        )
        self.assertFalse(
            any(
                item.name.startswith(".onedrive-lock.pack.")
                for item in self.root.iterdir()
            )
        )

    def test_simple_edit_and_exact_ips_output(self) -> None:
        manifest, pack = self.export(self.single_asset(), name="simple")
        work_path = pack / "work" / "title" / "a.chr"
        work = bytearray(work_path.read_bytes())
        work[7] ^= 0xFF
        work_path.write_bytes(work)

        out_rom = self.root / "simple-output.nes"
        out_ips = self.root / "simple-output.ips"
        report_path = self.root / "simple-output.json"
        report = pipeline.compile_pack(
            manifest,
            pack,
            self.rom_path,
            self.rom_path,
            out_rom,
            out_ips,
            report_path,
        )

        expected = bytearray(self.source_data)
        expected[0x0107] ^= 0xFF
        self.assertEqual(out_rom.read_bytes(), bytes(expected))
        self.assertEqual(report["logical_changed_bytes"], 1)
        self.assertEqual(report["physical_changed_bytes"], 1)
        self.assertEqual(
            report["changed_ranges"],
            [{"offset": "0x000107", "length": 1}],
        )
        self.assertEqual(
            pipeline.apply_ips(self.source_data, out_ips.read_bytes()),
            bytes(expected),
        )
        self.assertEqual(
            out_ips.read_bytes(),
            b"PATCH\x00\x01\x07\x00\x01"
            + bytes([expected[0x0107]])
            + b"EOF",
        )

    def test_overlap_edit_from_one_alias_is_accepted_and_propagated(self) -> None:
        manifest, pack = self.export(
            self.overlapping_assets(),
            name="alias",
        )
        first_work = pack / "work" / "title" / "a.chr"
        changed = bytearray(first_work.read_bytes())
        changed[0x35] ^= 0xFF
        first_work.write_bytes(changed)

        report = pipeline.verify_pack(manifest, pack, self.rom_path)
        by_id = {item["id"]: item for item in report["assets"]}
        self.assertEqual(report["logical_changed_bytes"], 1)
        self.assertEqual(report["physical_changed_bytes"], 1)
        self.assertEqual(by_id["asset_a"]["propagated_alias_bytes"], 0)
        self.assertEqual(by_id["asset_b"]["logical_changed_bytes"], 0)
        self.assertEqual(by_id["asset_b"]["output_changed_bytes"], 1)
        self.assertEqual(by_id["asset_b"]["propagated_alias_bytes"], 1)

        prepared = pipeline.prepare_pack(manifest, pack, self.rom_path)
        merged = pipeline.merge_pack(prepared).patched
        self.assertEqual(merged[0x0135], changed[0x35])
        self.assertEqual(
            merged[0x0130:0x0170][5],
            changed[0x35],
        )

    def test_contradictory_overlap_edits_are_rejected(self) -> None:
        manifest, pack = self.export(
            self.overlapping_assets(),
            name="conflict",
        )
        first_path = pack / "work" / "title" / "a.chr"
        second_path = pack / "work" / "title" / "b.chr"
        first = bytearray(first_path.read_bytes())
        second = bytearray(second_path.read_bytes())
        original = self.source_data[0x0135]
        first[0x35] = (original + 1) & 0xFF
        second[5] = (original + 2) & 0xFF
        first_path.write_bytes(first)
        second_path.write_bytes(second)

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            r"conflit d'overlap à 0x000135",
        ):
            pipeline.verify_pack(manifest, pack, self.rom_path)

    def test_wrong_work_size_is_rejected(self) -> None:
        manifest, pack = self.export(self.single_asset(), name="bad-size")
        work_path = pack / "work" / "title" / "a.chr"
        work_path.write_bytes(work_path.read_bytes()[:-1])

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "taille work 63, attendue 64",
        ):
            pipeline.verify_pack(manifest, pack, self.rom_path)

    def test_corrupt_baseline_and_wrong_source_hash_are_rejected(self) -> None:
        manifest, pack = self.export(
            self.single_asset(),
            name="bad-baseline",
        )
        baseline_path = pack / "baseline" / "title" / "a.chr"
        baseline = bytearray(baseline_path.read_bytes())
        baseline[0] ^= 0xFF
        baseline_path.write_bytes(baseline)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "hash baseline incorrect",
        ):
            pipeline.verify_pack(manifest, pack, self.rom_path)

        wrong_manifest = self.write_manifest(
            self.single_asset(),
            name="wrong-hash.manifest.json",
            source_hash="0" * 64,
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "SHA-256 ROM source inattendu",
        ):
            pipeline.export_pack(
                wrong_manifest,
                self.rom_path,
                self.root / "wrong-hash.pack",
            )

    def test_unsafe_manifest_path_is_rejected(self) -> None:
        assets = self.single_asset()
        assets[0]["path"] = "../escape.chr"
        manifest = self.write_manifest(
            assets,
            name="unsafe.manifest.json",
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "sort du pack",
        ):
            pipeline.load_manifest(manifest)

    def test_compile_rejects_colliding_output_paths(self) -> None:
        manifest, pack = self.export(
            self.single_asset(),
            name="output-collision",
        )
        shared_output = self.root / "shared-output.bin"
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "sorties ROM et IPS identiques",
        ):
            pipeline.compile_pack(
                manifest,
                pack,
                self.rom_path,
                self.rom_path,
                shared_output,
                shared_output,
                self.root / "collision-report.json",
            )

        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "ne peut pas être écrite dans le pack",
        ):
            pipeline.compile_pack(
                manifest,
                pack,
                self.rom_path,
                self.rom_path,
                self.root / "safe-output.nes",
                self.root / "safe-output.ips",
                pack / "work" / "report.json",
            )


if __name__ == "__main__":
    unittest.main()
