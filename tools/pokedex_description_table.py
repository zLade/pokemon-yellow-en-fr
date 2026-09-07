#!/usr/bin/env python3
"""Canonical mapping for the Pokédex description pointer table.

The in-game Kanto Pokédex indexes 151 little-endian pointers starting at file
offset 0x03201E.  Eight additional pointers follow the accessible range; they
are decoded separately so their existing layouts can be validated without
mistaking them for entries #152..#159 of the Kanto UI.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
DEFAULT_POINTER_ROM = (
    ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
)
DEFAULT_POINTER_ROM_SHA256 = (
    "d5c308b5862ccbe4647d4255a11bb0f1"
    "cb6817c4b107feac112509d658a9943b"
)

POKEDEX_DESCRIPTION_TABLE_OFFSET = 0x03201E
POKEDEX_POINTER_FILE_BIAS = 0x028010
POKEDEX_ACCESSIBLE_COUNT = 151
POKEDEX_EXTENDED_POINTER_COUNT = 8

POKEDEX_ACCESSIBLE_OFFSET_FINGERPRINT = (
    "9c4c02f1b1eb250b3eee64ffb52d201b"
    "6148038009f283a2e68794ff645b6620"
)
POKEDEX_EXTENDED_OFFSET_FINGERPRINT = (
    "8fd1b7690425ceb4ecae9ea341b02c761"
    "29e55cb630b98a6decf0661ea0f2cf9"
)

POKEDEX_ACCESSIBLE_ANCHORS = {
    1: 0x030898,
    2: 0x036950,
    3: 0x036978,
    4: 0x03217A,
    151: 0x03789A,
}


@dataclass(frozen=True)
class PokedexDescriptionPointer:
    """One decoded entry of the description pointer table."""

    table_index: int
    pointer_file_offset: int
    cpu_pointer: int
    description_offset: int
    accessible: bool


def offset_fingerprint(
    records: tuple[PokedexDescriptionPointer, ...],
) -> str:
    payload = "\n".join(
        f"{record.table_index}:{record.description_offset:06X}"
        for record in records
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def decode_pokedex_description_table(
    rom: bytes,
) -> tuple[
    tuple[PokedexDescriptionPointer, ...],
    tuple[PokedexDescriptionPointer, ...],
]:
    """Decode and verify the accessible and following pointer ranges."""
    total = POKEDEX_ACCESSIBLE_COUNT + POKEDEX_EXTENDED_POINTER_COUNT
    table_end = POKEDEX_DESCRIPTION_TABLE_OFFSET + total * 2
    if len(rom) < table_end:
        raise ValueError(
            "ROM too short for the Pokédex table at 0x03201E"
        )

    records: list[PokedexDescriptionPointer] = []
    for zero_based_index in range(total):
        pointer_file_offset = (
            POKEDEX_DESCRIPTION_TABLE_OFFSET + zero_based_index * 2
        )
        cpu_pointer = int.from_bytes(
            rom[pointer_file_offset : pointer_file_offset + 2],
            "little",
        )
        if not 0x8000 <= cpu_pointer <= 0xFFFF:
            raise ValueError(
                f"invalid Pokédex pointer #{zero_based_index + 1}: "
                f"0x{cpu_pointer:04X}"
            )
        description_offset = cpu_pointer + POKEDEX_POINTER_FILE_BIAS
        records.append(
            PokedexDescriptionPointer(
                table_index=zero_based_index + 1,
                pointer_file_offset=pointer_file_offset,
                cpu_pointer=cpu_pointer,
                description_offset=description_offset,
                accessible=zero_based_index < POKEDEX_ACCESSIBLE_COUNT,
            )
        )

    if len({record.description_offset for record in records}) != total:
        raise ValueError("duplicate Pokédex offset(s) in the table")

    accessible = tuple(records[:POKEDEX_ACCESSIBLE_COUNT])
    extended = tuple(records[POKEDEX_ACCESSIBLE_COUNT:])
    for species_id, expected_offset in POKEDEX_ACCESSIBLE_ANCHORS.items():
        actual = accessible[species_id - 1].description_offset
        if actual != expected_offset:
            raise ValueError(
                f"Pokédex anchor #{species_id}: 0x{actual:06X}, "
                f"expected 0x{expected_offset:06X}"
            )

    accessible_fingerprint = offset_fingerprint(accessible)
    if (
        accessible_fingerprint
        != POKEDEX_ACCESSIBLE_OFFSET_FINGERPRINT
    ):
        raise ValueError(
            "noncanonical mapping of the 151 Pokédex descriptions: "
            f"{accessible_fingerprint}"
        )
    extended_fingerprint = offset_fingerprint(extended)
    if extended_fingerprint != POKEDEX_EXTENDED_OFFSET_FINGERPRINT:
        raise ValueError(
            "noncanonical extended Pokédex mapping: "
            f"{extended_fingerprint}"
        )
    return accessible, extended


def load_pokedex_description_table(
    rom_path: str | Path = DEFAULT_POINTER_ROM,
) -> tuple[
    tuple[PokedexDescriptionPointer, ...],
    tuple[PokedexDescriptionPointer, ...],
]:
    """Load the pinned English ROM and return both verified table ranges."""
    path = Path(rom_path)
    if not path.is_absolute():
        path = ROM_DIR / path
    rom = path.read_bytes()
    digest = hashlib.sha256(rom).hexdigest()
    if digest != DEFAULT_POINTER_ROM_SHA256:
        raise ValueError(
            f"noncanonical Pokédex table ROM: {digest} "
            f"instead of {DEFAULT_POINTER_ROM_SHA256}"
        )
    return decode_pokedex_description_table(rom)


def accessible_description_offsets(
    rom_path: str | Path = DEFAULT_POINTER_ROM,
) -> tuple[int, ...]:
    accessible, _ = load_pokedex_description_table(rom_path)
    return tuple(record.description_offset for record in accessible)


def extended_description_offsets(
    rom_path: str | Path = DEFAULT_POINTER_ROM,
) -> tuple[int, ...]:
    _, extended = load_pokedex_description_table(rom_path)
    return tuple(record.description_offset for record in extended)
