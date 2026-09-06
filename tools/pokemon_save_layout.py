#!/usr/bin/env python3
"""Verified persistent-state layout for the Nanjing mapper-163 Pokémon ROM."""

from __future__ import annotations

from dataclasses import dataclass

PRIMARY_SIZE = 0x800
SAVE_SIZE = 0x2000
BACKUP_OFFSET = 0x0C00
SAVE_MAGIC_OFFSET = 0x1C21
SAVE_MAGIC = bytes.fromhex("AA 55 A5 5A")

POKEDEX_UNLOCK_OFFSET = 0x0000
POKEDEX_UNLOCK_MASK = 0x20
PARTY_COUNT_OFFSET = 0x0030
SEEN_COUNT_OFFSET = 0x0031
CAUGHT_COUNT_OFFSET = 0x0032
PARTY_SPECIES_OFFSET = 0x0033
PARTY_LEVEL_OFFSET = 0x0039
PARTY_FIELD_STRIDE = 6
PARTY_FIELD_COUNT = 18
PARTY_ORDER_OFFSET = 0x00C9
PARTY_CAPACITY = 6

CAUGHT_BITS_OFFSET = 0x009F
SEEN_BITS_OFFSET = 0x00B3
POKEDEX_STORAGE_BYTES = 20
POKEDEX_STANDARD_BYTES = 19
POKEDEX_STANDARD_COUNT = 151
BADGES_OFFSET = 0x00C7
HIGHEST_SEEN_OFFSET = 0x00C8


class SaveLayoutError(ValueError):
    """Raised when a save image or species ID is outside the verified layout."""


def _primary_view(data: bytes | bytearray | memoryview) -> memoryview:
    view = memoryview(data)
    if len(view) == PRIMARY_SIZE:
        return view
    if len(view) == SAVE_SIZE:
        return view[:PRIMARY_SIZE]
    raise SaveLayoutError(
        f"expected a {PRIMARY_SIZE}-byte primary block or {SAVE_SIZE}-byte "
        f".sav, got {len(view)} bytes"
    )


def _species_location(species_id: int) -> tuple[int, int]:
    if not 1 <= species_id <= POKEDEX_STANDARD_COUNT:
        raise SaveLayoutError(
            f"standard Pokédex species must be 1..151, got {species_id}"
        )
    zero_based = species_id - 1
    return zero_based >> 3, 1 << (zero_based & 7)


def decode_species_bits(
    data: bytes | bytearray | memoryview,
    offset: int,
) -> list[int]:
    """Decode the verified standard #001..#151 LSB-first bitmap."""

    primary = _primary_view(data)
    result: list[int] = []
    for species_id in range(1, POKEDEX_STANDARD_COUNT + 1):
        byte_index, mask = _species_location(species_id)
        if primary[offset + byte_index] & mask:
            result.append(species_id)
    return result


def caught_species(data: bytes | bytearray | memoryview) -> list[int]:
    return decode_species_bits(data, CAUGHT_BITS_OFFSET)


def seen_species(data: bytes | bytearray | memoryview) -> list[int]:
    return decode_species_bits(data, SEEN_BITS_OFFSET)


def apply_complete_standard_pokedex(primary: bytearray) -> None:
    """Mark exactly #001..#151 seen/caught without touching extension bits."""

    if len(primary) != PRIMARY_SIZE:
        raise SaveLayoutError(
            f"completion expects the {PRIMARY_SIZE}-byte primary block"
        )
    primary[POKEDEX_UNLOCK_OFFSET] |= POKEDEX_UNLOCK_MASK
    primary[SEEN_COUNT_OFFSET] = POKEDEX_STANDARD_COUNT
    primary[CAUGHT_COUNT_OFFSET] = POKEDEX_STANDARD_COUNT
    for offset in (CAUGHT_BITS_OFFSET, SEEN_BITS_OFFSET):
        primary[offset : offset + 18] = b"\xFF" * 18
        primary[offset + 18] = 0x7F
        # Physical storage has a twentieth byte, but the UI hard-stops before
        # #152.  Keep all unverified extension IDs clear.
        primary[offset + 19] = 0x00
    primary[HIGHEST_SEEN_OFFSET] = POKEDEX_STANDARD_COUNT


def synchronize_save(save: bytearray) -> None:
    """Copy primary state to the verified backup and restore the save marker."""

    if len(save) != SAVE_SIZE:
        raise SaveLayoutError(f"expected an 8192-byte .sav, got {len(save)}")
    save[BACKUP_OFFSET : BACKUP_OFFSET + PRIMARY_SIZE] = save[:PRIMARY_SIZE]
    save[SAVE_MAGIC_OFFSET : SAVE_MAGIC_OFFSET + len(SAVE_MAGIC)] = SAVE_MAGIC


def save_magic_valid(save: bytes | bytearray | memoryview) -> bool:
    """Return whether an exact 8 KiB save carries the verified marker."""

    view = memoryview(save)
    if len(view) != SAVE_SIZE:
        raise SaveLayoutError(f"expected an 8192-byte .sav, got {len(view)}")
    return bytes(
        view[SAVE_MAGIC_OFFSET : SAVE_MAGIC_OFFSET + len(SAVE_MAGIC)]
    ) == SAVE_MAGIC


def primary_backup_matches(save: bytes | bytearray | memoryview) -> bool:
    """Return whether the verified primary and backup blocks are identical."""

    view = memoryview(save)
    if len(view) != SAVE_SIZE:
        raise SaveLayoutError(f"expected an 8192-byte .sav, got {len(view)}")
    return view[:PRIMARY_SIZE] == view[
        BACKUP_OFFSET : BACKUP_OFFSET + PRIMARY_SIZE
    ]


def validate_save_image(
    save: bytes | bytearray | memoryview,
) -> list[str]:
    """Validate the proven save invariants without guessing recovery policy.

    A mismatched primary/backup pair is reported rather than repaired: the
    ROM's selection policy after an interrupted write still needs a dedicated
    runtime trace before either block can safely be declared authoritative.
    """

    view = memoryview(save)
    if len(view) != SAVE_SIZE:
        return [f"save size={len(view)}, expected={SAVE_SIZE}"]
    errors: list[str] = []
    if not save_magic_valid(view):
        errors.append("save magic is absent or corrupt")
    if not primary_backup_matches(view):
        errors.append("primary and backup blocks differ")
    errors.extend(validate_standard_pokedex(view[:PRIMARY_SIZE]))
    try:
        party_summary(view[:PRIMARY_SIZE])
    except SaveLayoutError as exc:
        errors.append(str(exc))
    return errors


@dataclass(frozen=True)
class PartySummary:
    count: int
    order: tuple[int, ...]
    species: tuple[int, ...]
    levels: tuple[int, ...]


def party_summary(data: bytes | bytearray | memoryview) -> PartySummary:
    """Decode the high-confidence party count/order/species/level fields."""

    primary = _primary_view(data)
    count = primary[PARTY_COUNT_OFFSET]
    if count > PARTY_CAPACITY:
        raise SaveLayoutError(f"invalid party count {count}")
    order = tuple(primary[PARTY_ORDER_OFFSET + index] for index in range(count))
    if any(index >= PARTY_CAPACITY for index in order):
        raise SaveLayoutError(f"invalid party order {order}")
    return PartySummary(
        count=count,
        order=order,
        species=tuple(primary[PARTY_SPECIES_OFFSET + index] for index in order),
        levels=tuple(primary[PARTY_LEVEL_OFFSET + index] for index in order),
    )


def validate_standard_pokedex(data: bytes | bytearray | memoryview) -> list[str]:
    """Return consistency errors for the standard 151-entry Pokédex."""

    primary = _primary_view(data)
    seen = seen_species(primary)
    caught = caught_species(primary)
    errors: list[str] = []
    if primary[SEEN_COUNT_OFFSET] != len(seen):
        errors.append(
            f"seen counter={primary[SEEN_COUNT_OFFSET]}, bitmap={len(seen)}"
        )
    if primary[CAUGHT_COUNT_OFFSET] != len(caught):
        errors.append(
            f"caught counter={primary[CAUGHT_COUNT_OFFSET]}, "
            f"bitmap={len(caught)}"
        )
    if not set(caught).issubset(seen):
        errors.append("caught bitmap is not a subset of seen bitmap")
    if primary[CAUGHT_BITS_OFFSET + 18] & 0x80:
        errors.append("unverified caught #152 bit is set")
    if primary[SEEN_BITS_OFFSET + 18] & 0x80:
        errors.append("unverified seen #152 bit is set")
    if primary[CAUGHT_BITS_OFFSET + 19] != 0:
        errors.append("unverified caught extension byte is nonzero")
    if primary[SEEN_BITS_OFFSET + 19] != 0:
        errors.append("unverified seen extension byte is nonzero")
    return errors
