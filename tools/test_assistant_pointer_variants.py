#!/usr/bin/env python3
"""Focused tests for the reviewed English pointer-variant build path."""

from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import rom_traduction_assistant as assistant
from tools.locales.profiles import ENGLISH_TEXT_PROFILE
from tools.restoration_topology import RESTORATION_REFERENCES


ROOT = Path(__file__).resolve().parent.parent
ASSISTANT = ROOT / "rom_traduction_assistant.py"
ENGLISH_BASE = ROOT / "Pokemon Yellow English 9-23-2015.nes"
FRENCH_BUILD_CSV = ROOT / "traduction_base.csv"

GROUP_TEXTS = {
    0x0302FA: (" was badly poisoned!", " flinched!"),
    0x03162C: ("Curse", "Strength"),
    0x031A15: ("Catch a Ball", "Great Ball", "Ultra Ball"),
}


def write_pointer_variants(
    path: Path,
    *,
    group_texts: dict[int, tuple[str, ...]] | None = None,
    status: str = "reviewed",
) -> None:
    texts = group_texts or GROUP_TEXTS
    fieldnames = [
        "variant_key",
        "stable_key",
        "pointer_reference_hex",
        "shared_english_2015_target",
        "english_v2",
        "review_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for main_offset, refs in (
            assistant.EXPECTED_POINTER_VARIANT_REFERENCES.items()
        ):
            stable_key = f"MAIN:0x{main_offset:06X}"
            for ref, text in zip(refs, texts[main_offset], strict=True):
                writer.writerow(
                    {
                        "variant_key": f"{stable_key}@0x{ref:06X}",
                        "stable_key": stable_key,
                        "pointer_reference_hex": f"0x{ref:06X}",
                        "shared_english_2015_target": (
                            f"0x{main_offset:06X}"
                        ),
                        "english_v2": text,
                        "review_status": status,
                    }
                )


def pointer_target(data: bytes, ref: int) -> int:
    address = int.from_bytes(data[ref:ref + 2], "little")
    target = assistant.offset_for_cpu_addr(
        assistant.pair_for_offset(ref),
        address,
        len(data),
    )
    if target is None:
        raise AssertionError(f"invalid pointer at 0x{ref:06X}")
    return target


def terminated_payload(data: bytes, offset: int) -> bytes:
    end = data.index(0x0D, offset)
    return data[offset:end]


@unittest.skipUnless(ENGLISH_BASE.is_file(), "canonical English base absent")
class PointerVariantUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = ENGLISH_BASE.read_bytes()

    def _load(
        self,
        directory: str,
        *,
        group_texts: dict[int, tuple[str, ...]] | None = None,
        status: str = "reviewed",
    ) -> dict[int, tuple[assistant.PointerVariant, ...]]:
        path = Path(directory) / "pointer_variants.csv"
        write_pointer_variants(
            path,
            group_texts=group_texts,
            status=status,
        )
        return assistant.load_pointer_variants_csv(
            path,
            text_profile=ENGLISH_TEXT_PROFILE,
        )

    def _row_info(self) -> list[tuple[assistant.TranslationRow, int, bytes]]:
        return [
            (
                assistant.TranslationRow(
                    0x0302FA,
                    " was badly poisoned!",
                    9,
                ),
                9,
                b" was badly poisoned!",
            ),
            (
                assistant.TranslationRow(0x03162C, "Curse", 8),
                8,
                b"Curse",
            ),
            (
                assistant.TranslationRow(0x031A15, "Catch a Ball", 14),
                14,
                b"Catch a Ball",
            ),
        ]

    def _row_pointer_refs(
        self,
    ) -> dict[int, list[tuple[int, list[int]]]]:
        return {
            0x0302FA: [
                (0x0302FB, [0x03006B, 0x03006D]),
            ],
            0x03162C: [
                (0x03162C, [0x0310F5, 0x0310F7]),
            ],
            0x031A15: [
                (0x031A15, [0x031971, 0x031973, 0x031975]),
            ],
        }

    def test_exact_groups_detach_only_four_secondary_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            variants = self._load(temporary)
        owners = self._row_pointer_refs()
        payloads = assistant.prepare_pointer_variant_payloads(
            self.original,
            self._row_info(),
            owners,
            variants,
            RESTORATION_REFERENCES,
            text_profile=ENGLISH_TEXT_PROFILE,
        )

        self.assertEqual(
            payloads,
            {
                0x03006D: b" flinched!",
                0x0310F7: b"Strength",
                0x031973: b"Great Ball",
                0x031975: b"Ultra Ball",
            },
        )
        self.assertEqual(owners[0x0302FA][0][1], [0x03006B])
        self.assertEqual(owners[0x03162C][0][1], [0x0310F5])
        self.assertEqual(owners[0x031A15][0][1], [0x031971])

    def test_poison_primary_pointer_targets_structural_join_space(self) -> None:
        translated = b" was badly poisoned!"
        without_policy = assistant.relocated_text_target(
            self.original,
            0x0302FA,
            9,
            translated,
            0x0302FB,
            0x1000,
            collapse_ascii_padding_interior=True,
        )
        with_policy = assistant.relocated_text_target(
            self.original,
            0x0302FA,
            9,
            translated,
            0x0302FB,
            0x1000,
            collapse_ascii_padding_interior=True,
            preserve_leading_separator=(
                0x03006B
                in assistant.SEMANTIC_LEADING_SEPARATOR_POINTER_REFS
            ),
        )
        self.assertEqual(without_policy, 0x1001)
        self.assertEqual(with_policy, 0x1000)
        self.assertEqual(translated[with_policy - 0x1000], 0x20)

    def test_stat_limit_pointer_keeps_join_space_after_source_control(self) -> None:
        translated = b" won't rise!"
        without_policy = assistant.relocated_text_target(
            self.original,
            0x0303A9,
            6,
            translated,
            0x0303AA,
            0x1000,
            collapse_ascii_padding_interior=True,
        )
        with_policy = assistant.relocated_text_target(
            self.original,
            0x0303A9,
            6,
            translated,
            0x0303AA,
            0x1000,
            collapse_ascii_padding_interior=True,
            preserve_leading_separator=(
                0x030083
                in assistant.SEMANTIC_LEADING_SEPARATOR_POINTER_REFS
            ),
        )
        self.assertEqual(without_policy, 0x1001)
        self.assertEqual(with_policy, 0x1000)
        self.assertEqual(translated[with_policy - 0x1000], 0x20)

    def test_immunity_pointer_targets_reviewed_leading_line_break(self) -> None:
        translated = b"\x0ACan't be poisoned!"
        without_policy = assistant.relocated_text_target(
            self.original,
            0x0307B9,
            10,
            translated,
            0x0307BA,
            0x1000,
            collapse_ascii_padding_interior=True,
        )
        with_policy = assistant.relocated_text_target(
            self.original,
            0x0307B9,
            10,
            translated,
            0x0307BA,
            0x1000,
            collapse_ascii_padding_interior=True,
            preserve_leading_control=(
                0x030173
                in assistant.SEMANTIC_LEADING_CONTROL_POINTER_REFS
            ),
        )
        self.assertEqual(without_policy, 0x1001)
        self.assertEqual(with_policy, 0x1000)
        self.assertEqual(translated[with_policy - 0x1000], 0x0A)

    def test_poison_and_flinch_variants_require_join_space(self) -> None:
        texts = dict(GROUP_TEXTS)
        texts[0x0302FA] = (" was badly poisoned!", "flinched!")
        with tempfile.TemporaryDirectory() as temporary:
            variants = self._load(temporary, group_texts=texts)
        with self.assertRaisesRegex(ValueError, "join space"):
            assistant.prepare_pointer_variant_payloads(
                self.original,
                self._row_info(),
                self._row_pointer_refs(),
                variants,
                text_profile=ENGLISH_TEXT_PROFILE,
            )

    def test_pending_status_is_rejected_before_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "review_status"):
                self._load(temporary, status="pending")

    def test_first_variant_must_equal_main_payload_without_detaching(self) -> None:
        texts = dict(GROUP_TEXTS)
        texts[0x0302FA] = (" Different", " flinched!")
        with tempfile.TemporaryDirectory() as temporary:
            variants = self._load(temporary, group_texts=texts)
        owners = self._row_pointer_refs()
        with self.assertRaisesRegex(ValueError, "first variant"):
            assistant.prepare_pointer_variant_payloads(
                self.original,
                self._row_info(),
                owners,
                variants,
                text_profile=ENGLISH_TEXT_PROFILE,
            )
        self.assertEqual(
            owners[0x0302FA][0][1],
            [0x03006B, 0x03006D],
        )

    def test_source_pointer_target_is_verified_before_detaching(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            variants = self._load(temporary)
        modified = bytearray(self.original)
        modified[0x03006D:0x03006F] = (0x9000).to_bytes(2, "little")
        owners = self._row_pointer_refs()
        with self.assertRaisesRegex(ValueError, "English source target"):
            assistant.prepare_pointer_variant_payloads(
                bytes(modified),
                self._row_info(),
                owners,
                variants,
                text_profile=ENGLISH_TEXT_PROFILE,
            )
        self.assertEqual(
            owners[0x0302FA][0][1],
            [0x03006B, 0x03006D],
        )

    def test_reserved_at_is_rejected_as_strict_english(self) -> None:
        texts = dict(GROUP_TEXTS)
        texts[0x0302FA] = (" was badly poisoned!", " Bad@text")
        with tempfile.TemporaryDirectory() as temporary:
            variants = self._load(temporary, group_texts=texts)
        with self.assertRaisesRegex(ValueError, "reserved punctuation"):
            assistant.prepare_pointer_variant_payloads(
                self.original,
                self._row_info(),
                self._row_pointer_refs(),
                variants,
                text_profile=ENGLISH_TEXT_PROFILE,
            )

    def test_synthetic_key_collision_is_rejected_without_detaching(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            variants = self._load(temporary)
        owners = self._row_pointer_refs()
        with self.assertRaisesRegex(ValueError, "collision"):
            assistant.prepare_pointer_variant_payloads(
                self.original,
                self._row_info(),
                owners,
                variants,
                {0x03006D},
                text_profile=ENGLISH_TEXT_PROFILE,
            )
        self.assertEqual(
            owners[0x0302FA][0][1],
            [0x03006B, 0x03006D],
        )


@unittest.skipUnless(
    ENGLISH_BASE.is_file() and FRENCH_BUILD_CSV.is_file(),
    "canonical local build inputs absent",
)
class PointerVariantBuildTests(unittest.TestCase):
    def _write_catalogue(self, path: Path) -> None:
        fieldnames = [
            "record_type",
            "stable_key",
            "source_offset_or_pointer",
            "source_capacity_bytes",
            "layout",
            "english_v2",
            "review_status",
        ]
        with FRENCH_BUILD_CSV.open(
            newline="",
            encoding="utf-8-sig",
        ) as source, path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as destination:
            reader = csv.DictReader(source)
            writer = csv.DictWriter(destination, fieldnames=fieldnames)
            writer.writeheader()
            for source_row in reader:
                offset = int(source_row["offset_hex"], 16)
                text = GROUP_TEXTS.get(offset, ("A",))[0]
                writer.writerow(
                    {
                        "record_type": "MAIN",
                        "stable_key": f"MAIN:0x{offset:06X}",
                        "source_offset_or_pointer": f"0x{offset:06X}",
                        "source_capacity_bytes": source_row["max_len"],
                        "layout": source_row["layout"],
                        "english_v2": text,
                        "review_status": "reviewed",
                    }
                )
            for reference in sorted(RESTORATION_REFERENCES):
                writer.writerow(
                    {
                        "record_type": "RESTORED",
                        "stable_key": f"RESTORED:0x{reference:06X}",
                        "source_offset_or_pointer": f"0x{reference:06X}",
                        "source_capacity_bytes": "",
                        "layout": "dialogue_19_19",
                        "english_v2": "B",
                        "review_status": "reviewed",
                    }
                )

    def test_english_repacked_smoke_repoints_exactly_four_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            catalogue = directory / "catalog.csv"
            variants = directory / "pointer_variants.csv"
            output_rom = directory / "english.nes"
            output_ips = directory / "english.ips"
            overflow = directory / "overflow.csv"
            self._write_catalogue(catalogue)
            write_pointer_variants(variants)

            process = subprocess.run(
                (
                    sys.executable,
                    str(ASSISTANT),
                    "build-repacked",
                    "--profile",
                    "en-US",
                    "--csv",
                    str(catalogue),
                    "--pointer-variants-csv",
                    str(variants),
                    "--input-rom",
                    str(ENGLISH_BASE),
                    "--output-rom",
                    str(output_rom),
                    "--output-ips",
                    str(output_ips),
                    "--fixed-overflow-output",
                    str(overflow),
                ),
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout)
            self.assertIn(
                "English pointer variants : 4",
                process.stdout,
            )
            candidate = output_rom.read_bytes()

        expected_by_ref = {
            0x03006B: b" was badly poisoned!",
            0x03006D: b" flinched!",
            0x0310F5: b"Curse",
            0x0310F7: b"Strength",
            0x031971: b"Catch a Ball",
            0x031973: b"Great Ball",
            0x031975: b"Ultra Ball",
        }
        targets = {
            ref: pointer_target(candidate, ref)
            for ref in expected_by_ref
        }
        for ref, expected in expected_by_ref.items():
            self.assertEqual(
                terminated_payload(candidate, targets[ref]),
                expected,
            )
            self.assertEqual(
                assistant.pair_for_offset(targets[ref]),
                assistant.pair_for_offset(ref),
            )
        for ref in (
            assistant.SEMANTIC_LEADING_SEPARATOR_POINTER_REFS & targets.keys()
        ):
            self.assertEqual(candidate[targets[ref]], 0x20)
        self.assertNotEqual(targets[0x03006B], targets[0x03006D])
        self.assertNotEqual(targets[0x0310F5], targets[0x0310F7])
        self.assertEqual(
            len(
                {
                    targets[0x031971],
                    targets[0x031973],
                    targets[0x031975],
                }
            ),
            3,
        )

    def test_french_profile_ignores_unreadable_variant_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            output_rom = directory / "french.nes"
            output_ips = directory / "french.ips"
            overflow = directory / "overflow.csv"
            process = subprocess.run(
                (
                    sys.executable,
                    str(ASSISTANT),
                    "build-repacked",
                    "--profile",
                    "fr-FR",
                    "--pointer-variants-csv",
                    str(directory / "does-not-exist.csv"),
                    "--output-rom",
                    str(output_rom),
                    "--output-ips",
                    str(output_ips),
                    "--fixed-overflow-output",
                    str(overflow),
                ),
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout)
            self.assertEqual(
                hashlib.sha256(output_rom.read_bytes()).hexdigest(),
                "fe01711d751243f0afd9937691a1f080587eb97d83bf90587b83c49dabca032f",
            )


if __name__ == "__main__":
    unittest.main()
