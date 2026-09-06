#!/usr/bin/env python3
"""Resolve Pierre's contradictory CT34/CT35 dialogue from ROM data.

The Chinese receipt says CT34, while the immediately following source line
describes CT35/Armure.  This audit follows the executable CT-to-move table and
the move-name pointer table instead of choosing one sentence by intuition.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import parse_patch_entries


SOURCE_ROM = ROM_DIR / "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"
ENGLISH_ROM = ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
SOURCE_INVENTORY = (
    ROM_DIR
    / "data"
    / "source"
    / "chinese-english-fidelity"
    / "chinese_french_dialogue_inventory.csv"
)

TM_MOVE_TABLE_OFFSET = 0x06AA7B
TM_COUNT = 40
MOVE_NAME_POINTER_TABLE_OFFSET = 0x030F99
MOVE_NAME_BANK_FILE_BASE = 0x030010
MOVE_NAME_CPU_BASE = 0x8000
BROCK_ENGLISH_RECEIPT_OFFSET = 0x038F82
BROCK_SOURCE_RECEIPT_POINTER = 0x0382B5
BROCK_SOURCE_EXPLANATION_POINTER = 0x0382B7


@dataclass(frozen=True)
class BrockTmAudit:
    source_receipt_tm: int
    source_explanation_tm: int
    english_runtime_receipt_tm: int
    resolved_tm: int
    resolved_move: str
    tm34_move: str
    source_receipt_is_typo: bool


def move_name_record_offset(rom: bytes, tm_number: int) -> int:
    if not 1 <= tm_number <= TM_COUNT:
        raise ValueError(f"numéro de CT hors plage : {tm_number}")
    move_index = rom[TM_MOVE_TABLE_OFFSET + tm_number - 1]
    pointer_offset = MOVE_NAME_POINTER_TABLE_OFFSET + 2 * move_index
    pointer = int.from_bytes(rom[pointer_offset : pointer_offset + 2], "little")
    target = MOVE_NAME_BANK_FILE_BASE + pointer - MOVE_NAME_CPU_BASE
    if not MOVE_NAME_BANK_FILE_BASE <= target < MOVE_NAME_BANK_FILE_BASE + 0x8000:
        raise ValueError(
            f"CT{tm_number:02d}: pointeur de capacité hors banque 0x{pointer:04X}"
        )
    return target


def canonical_french_move_names() -> dict[int, str]:
    return {
        entry.offset: entry.text
        for entry in parse_patch_entries(
            ROM_DIR / "script.py",
            apply_dialogue_inventory=False,
        )
        if not entry.layout.startswith("dialogue_")
    }


def french_move_for_tm(rom: bytes, tm_number: int) -> str:
    target = move_name_record_offset(rom, tm_number)
    try:
        return canonical_french_move_names()[target]
    except KeyError as exc:
        raise ValueError(
            f"CT{tm_number:02d}: capacité 0x{target:06X} absente du script"
        ) from exc


def ascii_record(rom: bytes, offset: int) -> str:
    end = rom.index(b"\r", offset)
    payload = rom[offset:end]
    if any(value < 0x20 or value > 0x7E for value in payload):
        raise ValueError(f"record non ASCII à 0x{offset:06X}")
    return payload.decode("ascii")


def source_dialogues() -> dict[int, str]:
    with SOURCE_INVENTORY.open(newline="", encoding="utf-8-sig") as handle:
        return {
            int(row["pointer_reference_hex"], 16): row["chinese_text"].strip()
            for row in csv.DictReader(handle)
            if row.get("pointer_reference_hex")
        }


def first_number(pattern: str, text: str, *, label: str) -> int:
    match = re.search(pattern, text)
    if match is None:
        raise ValueError(f"{label} absent de {text!r}")
    return int(match.group(1))


def audit_brock_tm_reward() -> BrockTmAudit:
    source = SOURCE_ROM.read_bytes()
    english = ENGLISH_ROM.read_bytes()
    dialogues = source_dialogues()
    source_receipt_tm = first_number(
        r"技能机器(\d+)",
        dialogues[BROCK_SOURCE_RECEIPT_POINTER],
        label="numéro de CT reçu",
    )
    explanation = dialogues[BROCK_SOURCE_EXPLANATION_POINTER]
    source_explanation_tm = first_number(
        r"特技(\d+)是变硬",
        explanation,
        label="numéro de la capacité Armure",
    )
    english_runtime_receipt_tm = first_number(
        r"Recieved TM(\d+)!",
        ascii_record(english, BROCK_ENGLISH_RECEIPT_OFFSET),
        label="numéro reçu dans la ROM anglaise",
    )

    # The English patch changed text, but it did not change either of these
    # executable CT mappings. This makes its receipt label independently
    # checkable against the original mechanics.
    for tm_number in (source_receipt_tm, source_explanation_tm):
        source_entry = source[TM_MOVE_TABLE_OFFSET + tm_number - 1]
        english_entry = english[TM_MOVE_TABLE_OFFSET + tm_number - 1]
        if source_entry != english_entry:
            raise ValueError(f"CT{tm_number:02d}: mapping mécanique modifié")

    # French fixed-text offsets inherit the English ROM's variable-length
    # move-name table; its executable TM indices are identical to the source.
    tm34_move = french_move_for_tm(english, source_receipt_tm)
    resolved_move = french_move_for_tm(english, source_explanation_tm)
    if source_explanation_tm != english_runtime_receipt_tm:
        raise ValueError("la source explicative et la réception anglaise divergent")
    if resolved_move != "Armure" or tm34_move == resolved_move:
        raise ValueError("la table exécutable ne départage pas CT34 et CT35")
    return BrockTmAudit(
        source_receipt_tm=source_receipt_tm,
        source_explanation_tm=source_explanation_tm,
        english_runtime_receipt_tm=english_runtime_receipt_tm,
        resolved_tm=source_explanation_tm,
        resolved_move=resolved_move,
        tm34_move=tm34_move,
        source_receipt_is_typo=True,
    )


def main() -> int:
    result = audit_brock_tm_reward()
    print(
        f"CT résolue : CT{result.resolved_tm:02d} / {result.resolved_move}; "
        f"CT{result.source_receipt_tm:02d} enseigne {result.tm34_move}."
    )
    print("Conclusion : le « 34 » de la réception chinoise est une coquille.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
