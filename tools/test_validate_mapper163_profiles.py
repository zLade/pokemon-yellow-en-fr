#!/usr/bin/env python3
"""Profile-specific mapper 163 mutation tests."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from tools.validate_mapper163 import (
    BATTLE_TEXT_CONTROL_REGIONS,
    DOJO_DEPUTY_SPRITE_END,
    DOJO_DEPUTY_SPRITE_START,
    INES_HEADER_SIZE,
    MoveLabelCertificationError,
    PAIR8_END,
    PRG_BANK_SIZE,
    build_parser,
    certify_move_label_graphics,
    validate,
)
from tools.move_label_graphics import (
    GRAPHIC_ATLAS_OFFSET,
    GRAPHIC_ATLAS_SLOT_SIZE,
    MOVE_NAME_BANK_CPU_BASE,
    MOVE_NAME_BANK_FILE_BASE,
    MOVE_NAME_POINTER_TABLE_OFFSET,
    load_move_label_csv,
    patch_move_labels,
    read_move_records,
)


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "Pokemon Yellow English 9-23-2015.nes"
CHINESE = ROOT / "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"


@unittest.skipUnless(
    BASE.is_file() and CHINESE.is_file(),
    "canonical English/Chinese bases absent",
)
class Mapper163ProfileTests(unittest.TestCase):
    def _candidate(
        self,
        *,
        mutate_pair14: bool = False,
    ) -> tuple[Path, Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        directory = Path(temporary.name)
        path = directory / "candidate.nes"
        move_labels = directory / "move_labels.csv"
        move_labels.write_text(
            "move_index,full_name,line_1,line_2\n",
            encoding="utf-8",
        )
        data = bytearray(BASE.read_bytes())
        data[INES_HEADER_SIZE + 6 * PRG_BANK_SIZE + 0x100] ^= 0x01
        data[INES_HEADER_SIZE + 7 * PRG_BANK_SIZE + 0x100] ^= 0x01
        for start, source, patched in BATTLE_TEXT_CONTROL_REGIONS:
            self.assertEqual(bytes(data[start:start + len(source)]), source)
            data[start:start + len(source)] = patched
        chinese = CHINESE.read_bytes()
        data[DOJO_DEPUTY_SPRITE_START:DOJO_DEPUTY_SPRITE_END] = chinese[
            DOJO_DEPUTY_SPRITE_START:DOJO_DEPUTY_SPRITE_END
        ]
        if mutate_pair14:
            data[INES_HEADER_SIZE + 14 * PRG_BANK_SIZE + 0x100] ^= 0x01
        path.write_bytes(data)
        return path, move_labels, temporary

    def test_cli_default_remains_french(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(args.profile, "fr-FR")

    def test_english_accepts_only_text_pairs_and_preserved_assets(self) -> None:
        candidate, move_labels, temporary = self._candidate()
        try:
            args = argparse.Namespace(
                rom=str(candidate),
                base_rom=str(BASE),
                title_logo="english",
                profile="en-US",
                move_labels_csv=move_labels,
            )
            self.assertEqual(validate(args), 0)
        finally:
            temporary.cleanup()

    def test_english_rejects_any_title_bank_mutation(self) -> None:
        candidate, move_labels, temporary = self._candidate(mutate_pair14=True)
        try:
            args = argparse.Namespace(
                rom=str(candidate),
                base_rom=str(BASE),
                title_logo="english",
                profile="en-US",
                move_labels_csv=move_labels,
            )
            self.assertEqual(validate(args), 1)
        finally:
            temporary.cleanup()


@unittest.skipUnless(BASE.is_file(), "canonical English base absent")
class MoveLabelCertificationTests(unittest.TestCase):
    def _patched_candidate(
        self,
        *,
        profile: str = "en-US",
    ) -> tuple[bytes, bytes, Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        path = Path(temporary.name) / "move_labels.csv"
        row = (
            "019,Thunder Boom,Thunder,Boom\n"
            if profile == "en-US"
            else "019,Éclair Fou,Éclair,Fou\n"
        )
        path.write_text(
            "move_index,full_name,line_1,line_2\n" + row,
            encoding="utf-8",
        )
        base = BASE.read_bytes()
        if profile == "en-US":
            specs = load_move_label_csv(path)
        else:
            from tools.move_label_graphics import french_text_encoder

            specs = load_move_label_csv(path, encoder=french_text_encoder)
        candidate = patch_move_labels(base, base, specs).rom
        return base, candidate, path, temporary

    def test_certifies_exact_english_composites_and_live_payload(self) -> None:
        base, candidate, catalogue, temporary = self._patched_candidate()
        try:
            report = certify_move_label_graphics(
                base=base,
                candidate=candidate,
                profile="en-US",
                catalogue=catalogue,
            )
            self.assertEqual(report.requested_count, 1)
            self.assertEqual(report.used_even_slots, (94, 96, 98, 100))
            self.assertTrue(report.changed_pair8_offsets)
            self.assertLessEqual(
                report.changed_pair8_offsets,
                report.allowed_pair8_offsets,
            )
        finally:
            temporary.cleanup()

    def test_rejects_profile_outside_reviewed_english_and_french(self) -> None:
        base = BASE.read_bytes()
        with self.assertRaisesRegex(
            MoveLabelCertificationError,
            "Uncertified move-name profile",
        ):
            certify_move_label_graphics(
                base=base,
                candidate=base,
                profile="de-DE",
                catalogue=None,
            )

    def test_rejects_pair8_byte_outside_certified_cells(self) -> None:
        base, candidate, catalogue, temporary = self._patched_candidate()
        try:
            damaged = bytearray(candidate)
            damaged[PAIR8_END - 1] ^= 0x01
            with self.assertRaisesRegex(
                MoveLabelCertificationError,
                "outside certified move cells",
            ):
                certify_move_label_graphics(
                    base=base,
                    candidate=bytes(damaged),
                    profile="en-US",
                    catalogue=catalogue,
                )
        finally:
            temporary.cleanup()

    def test_rejects_damaged_certified_composite(self) -> None:
        base, candidate, catalogue, temporary = self._patched_candidate()
        try:
            damaged = bytearray(candidate)
            damaged[GRAPHIC_ATLAS_OFFSET + 94 * GRAPHIC_ATLAS_SLOT_SIZE] ^= 0x01
            with self.assertRaisesRegex(
                MoveLabelCertificationError,
                "Non-idempotent",
            ):
                certify_move_label_graphics(
                    base=base,
                    candidate=bytes(damaged),
                    profile="en-US",
                    catalogue=catalogue,
                )
        finally:
            temporary.cleanup()

    def test_rejects_live_record_overlapping_selected_payload(self) -> None:
        base, candidate, catalogue, temporary = self._patched_candidate()
        try:
            damaged = bytearray(candidate)
            selected = read_move_records(candidate)[19]
            nested_target = selected.target + 2
            nested_pointer = (
                MOVE_NAME_BANK_CPU_BASE
                + nested_target
                - MOVE_NAME_BANK_FILE_BASE
            )
            damaged[
                MOVE_NAME_POINTER_TABLE_OFFSET : MOVE_NAME_POINTER_TABLE_OFFSET + 2
            ] = nested_pointer.to_bytes(2, "little")
            with self.assertRaisesRegex(
                MoveLabelCertificationError,
                "Overlapping graphical move payloads: 000/019",
            ):
                certify_move_label_graphics(
                    base=base,
                    candidate=bytes(damaged),
                    profile="en-US",
                    catalogue=catalogue,
                )
        finally:
            temporary.cleanup()

    def test_certification_uses_french_encoder(self) -> None:
        base, candidate, catalogue, temporary = self._patched_candidate(
            profile="fr-FR"
        )
        try:
            report = certify_move_label_graphics(
                base=base,
                candidate=candidate,
                profile="fr-FR",
                catalogue=catalogue,
            )
            self.assertEqual(report.requested_count, 1)
            self.assertEqual(report.used_even_slots, (94, 96, 98))
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
