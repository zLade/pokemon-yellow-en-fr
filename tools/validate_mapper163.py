#!/usr/bin/env python3
"""Validate the mapper 163 cartridge contract used by the translated ROM."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path

try:
    from .title_screen_tools import (
        JAUNE_TILES,
        ENGLISH_TITLE_CREDITS,
        MENU_FR_TILES,
        MENU_TILE_IDS,
        TITLE_LOGO_TILE_IDS,
        TITLE_PT0_FILE,
        TITLE_PT1_FILE,
        patch_english_yellow_title,
        patch_title_credits,
    )
    from .french_font import (
        ASCII_FONT_OFFSET,
        extract_ascii_font,
        french_font_tiles,
    )
    from .move_label_graphics import (
        DEFAULT_EXCLUDED_EVEN_SLOTS,
        GRAPHIC_ATLAS_OFFSET,
        GRAPHIC_ATLAS_SLOT_SIZE,
        IncompleteMoveLabelPatch,
        MoveLabelError,
        ascii_text_encoder,
        french_text_encoder,
        graphic_code,
        load_move_label_csv,
        patch_move_labels,
        read_move_records,
    )
except ImportError:  # Direct ``python tools/validate_mapper163.py`` execution.
    from title_screen_tools import (
        JAUNE_TILES,
        ENGLISH_TITLE_CREDITS,
        MENU_FR_TILES,
        MENU_TILE_IDS,
        TITLE_LOGO_TILE_IDS,
        TITLE_PT0_FILE,
        TITLE_PT1_FILE,
        patch_english_yellow_title,
        patch_title_credits,
    )
    from french_font import (
        ASCII_FONT_OFFSET,
        extract_ascii_font,
        french_font_tiles,
    )
    from move_label_graphics import (
        DEFAULT_EXCLUDED_EVEN_SLOTS,
        GRAPHIC_ATLAS_OFFSET,
        GRAPHIC_ATLAS_SLOT_SIZE,
        IncompleteMoveLabelPatch,
        MoveLabelError,
        ascii_text_encoder,
        french_text_encoder,
        graphic_code,
        load_move_label_csv,
        patch_move_labels,
        read_move_records,
    )


INES_HEADER_SIZE = 16
PRG_SIZE = 2 * 1024 * 1024
MAPPER = 163
PRG_BANK_SIZE = 0x8000
ROOT = Path(__file__).resolve().parent.parent
PAIR8_START = INES_HEADER_SIZE + 8 * PRG_BANK_SIZE
PAIR8_END = PAIR8_START + PRG_BANK_SIZE
# Exact pair-4 text-renderer changes shared by the reviewed FR/EN builds.
# Each tuple is (file offset, source bytes, reviewed bytes); no other pair-4
# difference is permitted by the mapper-level validator.
BATTLE_TEXT_CONTROL_REGIONS = (
    (0x020986, bytes.fromhex("C9 0D F0 4F"), bytes.fromhex("4C 33 F4 EA")),
    (0x0231C1, b"\x18", b"\x19"),
    (0x02480D, bytes.fromhex("A9 00 85"), bytes.fromhex("4C 0C C8")),
    (
        0x027443,
        bytes(39),
        bytes.fromhex(
            "C9 0D F0 07 C9 0A F0 06 4C 7A 89 4C C9 89 "
            "A5 0F C9 23 B0 F7 A5 0E 29 E0 18 69 44 85 "
            "0E A5 0F 69 00 85 0F C8 4C 69 89"
        ),
    ),
)
RESET_STUB_OFFSET = 0x1FFFF7
RESET_STUB = bytes.fromhex(
    # LDA #$04 / STA $5300 / LDA #$00 / STA $5000 / STA $5200 /
    # JMP ($FFFC)
    "A9048D0053A9008D00508D00526CFCFF"
)
EXPECTED_VECTORS = bytes.fromhex("F9FFC0FFF9FF")
PLAYER_MENU_PT0_FILE = 0x0288D5
PLAYER_MENU_PT0_SIZE = 0x1000
PLAYER_MENU_PT0_SHA256 = (
    "8b56d2126e60574cf0c2a4ce75319cd4"
    "83ccbe5b51a726ffd560de039f4cc3fd"
)
BATTLE_MENU_CHR_START_LOW_OFFSET = 0x02321B
BATTLE_MENU_CHR_START_LOW_EXPECTED = 0x60
TRANSLATION_BASE_SHA256 = (
    "d5c308b5862ccbe4647d4255a11bb0f1"
    "cb6817c4b107feac112509d658a9943b"
)
DOJO_DEPUTY_SPRITE_START = 0x1CA271
DOJO_DEPUTY_SPRITE_END = 0x1CA47C
DOJO_DEPUTY_SPRITE_SHA256 = (
    "abb3b8cb27f8d383412c1620bcb23d11996afbc3aa73aa17"
    "2af6062057ee9dd6"
)
PLAYER_MENU_FR_TILE_IDS = {
    0x25, 0x29, 0x2B, 0x2F, 0x26, 0x2A, 0x2C, 0x30,
    0x31, 0x33, 0x35, 0x32, 0x34, 0x36,
    0x4C, 0x4E, 0x5B, 0x4D, 0x4F, 0x5C,
    0x5D, 0x7B, 0x7D, 0x84, 0x5E, 0x7C, 0x7E, 0x85,
}


class MoveLabelCertificationError(ValueError):
    """The live two-line move records do not match their reviewed CSV."""


@dataclass(frozen=True)
class MoveLabelCertification:
    catalogue: Path | None
    requested_count: int
    used_even_slots: tuple[int, ...]
    allowed_pair8_offsets: frozenset[int]
    changed_pair8_offsets: frozenset[int]


def default_move_label_catalogue(profile: str) -> Path:
    return ROOT / "translation" / "move_labels_two_line.csv"


def resolve_move_label_catalogue(
    profile: str,
    configured: str | Path | None,
) -> Path | None:
    """Resolve an explicit catalogue, or the profile-local reviewed default."""
    if configured is not None:
        candidate = Path(configured)
        return candidate if candidate.is_absolute() else ROOT / candidate
    default = default_move_label_catalogue(profile)
    return default if default.is_file() else None


def certify_move_label_graphics(
    *,
    base: bytes,
    candidate: bytes,
    profile: str,
    catalogue: str | Path | None,
) -> MoveLabelCertification:
    """Prove pair 8 and every live graphical move payload are declarative.

    Reapplying :func:`patch_move_labels` must be byte-idempotent.  This proves
    both the assigned codes and their composite atlas cells.  The separate
    pair-8 allow-list then rejects unrelated graphics changes, even if a future
    caller broadens the set of accepted PRG pairs.
    """
    if profile not in {"en-US", "fr-FR"}:
        raise MoveLabelCertificationError(
            f"Uncertified move-name profile: {profile}"
        )
    if len(base) != len(candidate):
        raise MoveLabelCertificationError(
            "Base/candidate sizes differ for graphics certification"
        )
    catalogue_path = Path(catalogue) if catalogue is not None else None
    if catalogue_path is None:
        specs = ()
    else:
        if not catalogue_path.is_file():
            raise MoveLabelCertificationError(
                f"Missing move-name catalogue: {catalogue_path}"
            )
        encoder = ascii_text_encoder if profile == "en-US" else french_text_encoder
        try:
            specs = load_move_label_csv(catalogue_path, encoder=encoder)
        except MoveLabelError as exc:
            raise MoveLabelCertificationError(str(exc)) from exc

    pair8_changes = frozenset(
        offset
        for offset in changed_offsets(base, candidate)
        if PAIR8_START <= offset < PAIR8_END
    )
    if not specs:
        if pair8_changes:
            preview = ", ".join(
                f"0x{offset:06X}" for offset in sorted(pair8_changes)[:8]
            )
            raise MoveLabelCertificationError(
                "Bank 8 changes without a certified catalogue: " + preview
            )
        return MoveLabelCertification(
            catalogue=catalogue_path,
            requested_count=0,
            used_even_slots=(),
            allowed_pair8_offsets=frozenset(),
            changed_pair8_offsets=frozenset(),
        )

    try:
        live_records = read_move_records(candidate)
    except MoveLabelError as exc:
        raise MoveLabelCertificationError(str(exc)) from exc
    selected_indexes = {spec.move_index for spec in specs}
    overlaps: list[tuple[int, int]] = []
    for selected in live_records:
        if selected.move_index not in selected_indexes:
            continue
        selected_start = selected.target
        selected_end = selected.target + len(selected.payload)
        for other in live_records:
            if other.move_index == selected.move_index:
                continue
            other_start = other.target
            other_end = other.target + len(other.payload)
            if max(selected_start, other_start) < min(selected_end, other_end):
                pair = tuple(sorted((selected.move_index, other.move_index)))
                if pair not in overlaps:
                    overlaps.append(pair)
    if overlaps:
        preview = ", ".join(
            f"{left:03d}/{right:03d}" for left, right in sorted(overlaps)[:8]
        )
        raise MoveLabelCertificationError(
            "Overlapping graphical move payloads: " + preview
        )

    try:
        result = patch_move_labels(candidate, base, specs, require_all=True)
    except IncompleteMoveLabelPatch as exc:
        raise MoveLabelCertificationError(str(exc)) from exc
    except MoveLabelError as exc:
        raise MoveLabelCertificationError(str(exc)) from exc

    report = result.report
    if result.rom != candidate:
        differences = changed_offsets(candidate, result.rom)
        preview = ", ".join(
            f"0x{offset:06X}" for offset in sorted(differences)[:8]
        )
        raise MoveLabelCertificationError(
            "Non-idempotent move composites/payloads: " + preview
        )
    if not report.complete or report.applied_count != len(specs):
        raise MoveLabelCertificationError(
            f"Incomplete composites: {report.applied_count}/{len(specs)}"
        )
    if (
        report.candidate_target_count != 177
        or report.candidate_unique_target_count != 177
    ):
        raise MoveLabelCertificationError(
            "Move table does not have 177 distinct live targets"
        )
    if report.pool_mode != "source":
        raise MoveLabelCertificationError(
            f"Uncertified graphics pool: {report.pool_mode}"
        )
    if set(report.excluded_even_slots) != set(DEFAULT_EXCLUDED_EVEN_SLOTS):
        raise MoveLabelCertificationError(
            "Noncanonical excluded graphical cell list"
        )
    used_slots = report.used_even_slots
    if len(used_slots) != len(set(used_slots)) or any(slot % 2 for slot in used_slots):
        raise MoveLabelCertificationError(
            "Duplicate or odd-numbered graphical move cells"
        )
    forbidden = sorted(set(used_slots) & set(DEFAULT_EXCLUDED_EVEN_SLOTS))
    if forbidden:
        raise MoveLabelCertificationError(
            "Excluded graphical cells in use: "
            + ", ".join(str(slot) for slot in forbidden)
        )

    records = {record.move_index: record for record in live_records}
    entries = {entry.move_index: entry for entry in report.entries}
    for spec in specs:
        entry = entries[spec.move_index]
        expected_payload = b"".join(
            graphic_code(slot) for slot in entry.code_slots
        ) + b"\x0D"
        record = records[spec.move_index]
        if entry.status != "applied" or record.payload != expected_payload:
            raise MoveLabelCertificationError(
                f"Unexpected graphical payload for move {spec.move_index:03d}"
            )
        if record.graphical_slots != entry.code_slots:
            raise MoveLabelCertificationError(
                f"Unexpected graphical codes for move {spec.move_index:03d}"
            )

    allowed_pair8: set[int] = set()
    for slot in used_slots:
        start = GRAPHIC_ATLAS_OFFSET + slot * GRAPHIC_ATLAS_SLOT_SIZE
        end = start + 2 * GRAPHIC_ATLAS_SLOT_SIZE
        if not PAIR8_START <= start < end <= PAIR8_END:
            raise MoveLabelCertificationError(
                f"Graphical cell {slot} outside bank 8"
            )
        allowed_pair8.update(range(start, end))
    unexpected = sorted(pair8_changes - allowed_pair8)
    if unexpected:
        preview = ", ".join(f"0x{offset:06X}" for offset in unexpected[:8])
        if len(unexpected) > 8:
            preview += ", ..."
        raise MoveLabelCertificationError(
            "Bank 8 changes outside certified move cells: "
            + preview
        )

    return MoveLabelCertification(
        catalogue=catalogue_path,
        requested_count=len(specs),
        used_even_slots=used_slots,
        allowed_pair8_offsets=frozenset(allowed_pair8),
        changed_pair8_offsets=pair8_changes,
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_header(data: bytes) -> dict[str, int | bool]:
    if len(data) < INES_HEADER_SIZE or data[:4] != b"NES\x1A":
        raise ValueError('Missing iNES header')
    header = data[:INES_HEADER_SIZE]
    return {
        "mapper": (header[6] >> 4) | (header[7] & 0xF0),
        "prg_size": header[4] * 0x4000,
        "chr_size": header[5] * 0x2000,
        "vertical": bool(header[6] & 0x01),
        "battery": bool(header[6] & 0x02),
        "trainer": bool(header[6] & 0x04),
        "four_screen": bool(header[6] & 0x08),
        "nes2": (header[7] & 0x0C) == 0x08,
        "region_byte": header[9] & 0x01,
    }


def changed_pairs(base: bytes, candidate: bytes) -> dict[int, int]:
    counts: dict[int, int] = {}
    for offset, (left, right) in enumerate(zip(base, candidate)):
        if left == right:
            continue
        pair = -1 if offset < INES_HEADER_SIZE else (
            offset - INES_HEADER_SIZE
        ) // PRG_BANK_SIZE
        counts[pair] = counts.get(pair, 0) + 1
    return counts


def changed_offsets(base: bytes, candidate: bytes) -> set[int]:
    return {
        offset
        for offset, (left, right) in enumerate(zip(base, candidate))
        if left != right
    }


def validate(args: argparse.Namespace) -> int:
    rom_path = Path(args.rom)
    base_path = Path(args.base_rom)
    rom = rom_path.read_bytes()
    base = base_path.read_bytes()
    failures: list[str] = []
    base_hash = sha256(base)
    if base_hash != TRANSLATION_BASE_SHA256:
        failures.append(
            "Noncanonical English base: "
            f"{base_hash} instead of {TRANSLATION_BASE_SHA256}"
        )

    try:
        info = parse_header(rom)
    except ValueError as exc:
        print(f"Mapper 163 validation: FAILED ({exc})")
        return 1

    expected_length = INES_HEADER_SIZE + PRG_SIZE
    if len(rom) != expected_length:
        failures.append(
            f'ROM size {len(rom)} instead of {expected_length}'
        )
    if info["mapper"] != MAPPER:
        failures.append(f"mapper {info['mapper']} instead of {MAPPER}")
    if info["prg_size"] != PRG_SIZE:
        failures.append(f"PRG {info['prg_size']} instead of {PRG_SIZE}")
    if info["chr_size"] != 0:
        failures.append('Nonzero CHR-ROM; this board must use CHR-RAM')
    if not info["vertical"]:
        failures.append('Missing vertical mirroring')
    if not info["battery"]:
        failures.append('Missing battery/save-RAM bit')
    if info["trainer"]:
        failures.append("Unexpected iNES trainer")
    if info["four_screen"]:
        failures.append("Unexpected four-screen mirroring")
    if info["nes2"]:
        failures.append("Unexpected NES 2.0 header; the base is iNES 1.0")

    if len(base) != len(rom):
        failures.append(
            f'Base size differs: {len(base)} instead of {len(rom)}'
        )
    elif base[:INES_HEADER_SIZE] != rom[:INES_HEADER_SIZE]:
        failures.append("Header differs from the English base")

    stub = rom[RESET_STUB_OFFSET:RESET_STUB_OFFSET + len(RESET_STUB)]
    if stub != RESET_STUB:
        failures.append(
            "Mapper 163 RESET trampoline changed: "
            f"{stub.hex()} instead of {RESET_STUB.hex()}"
        )
    if rom[-6:] != EXPECTED_VECTORS:
        failures.append(
            "NMI/RESET/IRQ vectors changed: "
            f"{rom[-6:].hex()} instead of {EXPECTED_VECTORS.hex()}"
        )

    profile = getattr(args, "profile", "fr-FR")
    if profile == "en-US" and args.title_logo not in (
        "english",
        "yellow-version",
    ):
        failures.append("The en-US profile requires an English title")

    same_size = len(base) == len(rom)
    pairs = changed_pairs(base, rom) if same_size else {}
    all_changed_offsets = changed_offsets(base, rom) if same_size else set()
    move_label_catalogue = resolve_move_label_catalogue(
        profile,
        getattr(args, "move_labels_csv", None),
    )
    try:
        move_label_certification = certify_move_label_graphics(
            base=base,
            candidate=rom,
            profile=profile,
            catalogue=move_label_catalogue,
        )
    except (MoveLabelCertificationError, OSError) as exc:
        failures.append(f"Graphical move names: {exc}")
        move_label_certification = MoveLabelCertification(
            catalogue=move_label_catalogue,
            requested_count=0,
            used_even_slots=(),
            allowed_pair8_offsets=frozenset(),
            changed_pair8_offsets=frozenset(),
        )
    expected_changed_pairs = (
        (
            {6, 7, 14, 57}
            if args.title_logo == "yellow-version"
            else {6, 7, 57}
        )
        if profile == "en-US"
        else {5, 6, 7, 14, 15, 57}
    )
    if move_label_certification.changed_pair8_offsets:
        expected_changed_pairs.add(8)
    expected_changed_pairs.add(4)
    unexpected_pairs = sorted(set(pairs) - expected_changed_pairs)
    if unexpected_pairs:
        failures.append(
            "Changes outside translation/title/player-menu banks: "
            + ", ".join(str(item) for item in unexpected_pairs)
        )
    missing_pairs = sorted(expected_changed_pairs - set(pairs))
    if missing_pairs:
        failures.append(
            "Unchanged translation/graphics bank(s): "
            + ", ".join(str(item) for item in missing_pairs)
        )

    if profile == "en-US":
        bank4_start = INES_HEADER_SIZE + 4 * PRG_BANK_SIZE
        bank4_end = bank4_start + PRG_BANK_SIZE
        bank4_changed_offsets = {
            offset
            for offset in all_changed_offsets
            if bank4_start <= offset < bank4_end
        }
        allowed_bank4_offsets: set[int] = set()
        for start, source, patched in BATTLE_TEXT_CONTROL_REGIONS:
            end = start + len(source)
            if base[start:end] != source:
                failures.append(
                    f'Unexpected battle-text control source at 0x{start:06X}'
                )
            if rom[start:end] != patched:
                failures.append(
                    f'Unexpected battle-text control patch at 0x{start:06X}'
                )
            allowed_bank4_offsets.update(
                start + index
                for index, (before, after) in enumerate(zip(source, patched))
                if before != after
            )
        unexpected_bank4_offsets = sorted(
            bank4_changed_offsets - allowed_bank4_offsets
        )
        missing_bank4_offsets = sorted(
            allowed_bank4_offsets - bank4_changed_offsets
        )
        if unexpected_bank4_offsets or missing_bank4_offsets:
            failures.append(
                "Unexpected changes in bank 4: extra="
                + ", ".join(
                    f"0x{offset:06X}" for offset in unexpected_bank4_offsets
                )
                + "; missing="
                + ", ".join(
                    f"0x{offset:06X}" for offset in missing_bank4_offsets
                )
            )
        if rom[BATTLE_MENU_CHR_START_LOW_OFFSET] != (
            BATTLE_MENU_CHR_START_LOW_EXPECTED
        ):
            failures.append(
                "Unexpected battle-menu CHR start: "
                f"0x{rom[BATTLE_MENU_CHR_START_LOW_OFFSET]:02X} instead of "
                f"0x{BATTLE_MENU_CHR_START_LOW_EXPECTED:02X}"
            )

    dojo_deputy_sprite_hash = sha256(
        rom[DOJO_DEPUTY_SPRITE_START:DOJO_DEPUTY_SPRITE_END]
    )
    if dojo_deputy_sprite_hash != DOJO_DEPUTY_SPRITE_SHA256:
        failures.append(
            f'Dojo deputy sprite differs from the Chinese ROM: {dojo_deputy_sprite_hash} instead of {DOJO_DEPUTY_SPRITE_SHA256}'
        )
    bank57_start = INES_HEADER_SIZE + 57 * PRG_BANK_SIZE
    bank57_end = bank57_start + PRG_BANK_SIZE
    bank57_changed_offsets = {
        offset
        for offset in all_changed_offsets
        if bank57_start <= offset < bank57_end
    }
    allowed_bank57_offsets = set(
        range(DOJO_DEPUTY_SPRITE_START, DOJO_DEPUTY_SPRITE_END)
    )
    unexpected_bank57_offsets = sorted(
        bank57_changed_offsets - allowed_bank57_offsets
    )
    if unexpected_bank57_offsets:
        failures.append(
            "Bank 57 changes outside the dojo deputy sprite: "
            + ", ".join(
                f"0x{offset:06X}" for offset in unexpected_bank57_offsets[:8]
            )
        )

    allowed_player_menu_offsets = {
        PLAYER_MENU_PT0_FILE + tile_id * 16 + byte_index
        for tile_id in PLAYER_MENU_FR_TILE_IDS
        for byte_index in range(16)
    } if profile == "fr-FR" else set()
    bank5_start = INES_HEADER_SIZE + 5 * PRG_BANK_SIZE
    bank5_end = bank5_start + PRG_BANK_SIZE
    bank5_changed_offsets = {
        offset
        for offset in all_changed_offsets
        if bank5_start <= offset < bank5_end
    }
    unexpected_bank5_offsets = sorted(
        bank5_changed_offsets - allowed_player_menu_offsets
    )
    if unexpected_bank5_offsets:
        preview = ", ".join(
            f"0x{offset:06X}" for offset in unexpected_bank5_offsets[:8]
        )
        if len(unexpected_bank5_offsets) > 8:
            preview += ", ..."
        failures.append(
            "Bank 5 changes outside player-menu tiles: " + preview
        )

    expected_title_rom = None
    if profile == "en-US" and args.title_logo == "yellow-version":
        title_reference = Path(args.title_reference_rom).read_bytes()
        expected_title_rom = bytearray(base)
        patch_english_yellow_title(
            expected_title_rom,
            title_reference,
            args.title_credits,
        )
        expected_title_rom = bytes(expected_title_rom)
        expected_logo_tiles = {
            TITLE_PT0_FILE + tile_id * 16: expected_title_rom[
                TITLE_PT0_FILE + tile_id * 16
                : TITLE_PT0_FILE + (tile_id + 1) * 16
            ]
            for tile_id in TITLE_LOGO_TILE_IDS
        }
        title_logo_label = "YELLOW VERSION + custom credits"
    elif profile == "en-US":
        expected_logo_tiles = {
            TITLE_PT0_FILE + tile_id * 16: base[
                TITLE_PT0_FILE + tile_id * 16
                : TITLE_PT0_FILE + (tile_id + 1) * 16
            ]
            for tile_id in TITLE_LOGO_TILE_IDS
        }
        title_logo_label = "Preserved English YELLOW"
    elif args.title_logo == "english":
        expected_logo_tiles = {
            TITLE_PT0_FILE + tile_id * 16: base[
                TITLE_PT0_FILE + tile_id * 16
                : TITLE_PT0_FILE + (tile_id + 1) * 16
            ]
            for tile_id in TITLE_LOGO_TILE_IDS
        }
        title_logo_label = "English YELLOW"
    else:
        expected_logo_tiles = {
            TITLE_PT0_FILE + tile_id * 16: tile
            for tile_id, tile in zip(
                TITLE_LOGO_TILE_IDS,
                JAUNE_TILES,
                strict=True,
            )
        }
        title_logo_label = "French JAUNE"

    expected_menu_tiles = (
        {
            TITLE_PT1_FILE + tile_id * 16: base[
                TITLE_PT1_FILE + tile_id * 16
                : TITLE_PT1_FILE + (tile_id + 1) * 16
            ]
            for tile_id in MENU_TILE_IDS
        }
        if profile == "en-US"
        else {
            TITLE_PT1_FILE + tile_id * 16: tile
            for tile_id, tile in zip(
                MENU_TILE_IDS,
                MENU_FR_TILES,
                strict=True,
            )
        }
    )
    expected_title_tiles = {**expected_logo_tiles, **expected_menu_tiles}
    bank14_start = INES_HEADER_SIZE + 14 * PRG_BANK_SIZE
    bank14_end = bank14_start + PRG_BANK_SIZE
    if expected_title_rom is not None:
        allowed_bank14_offsets = {
            offset
            for offset in range(bank14_start, bank14_end)
            if expected_title_rom[offset] != base[offset]
        }
    else:
        allowed_bank14_offsets = {
            offset + byte_index
            for offset in expected_title_tiles
            for byte_index in range(16)
        }
    if (
        getattr(args, "title_credits_mode", "original") == "shared"
        and expected_title_rom is None
    ):
        credits_reference = bytearray(base)
        patch_title_credits(
            credits_reference,
            getattr(args, "title_credits", ENGLISH_TITLE_CREDITS),
        )
        credit_offsets = {
            offset
            for offset in range(bank14_start, bank14_end)
            if credits_reference[offset] != base[offset]
        }
        allowed_bank14_offsets |= credit_offsets
        for offset in sorted(credit_offsets):
            if rom[offset] != credits_reference[offset]:
                failures.append(
                    f"Unexpected title-credit byte at 0x{offset:06X}"
                )
    bank14_changed_offsets = {
        offset
        for offset in all_changed_offsets
        if bank14_start <= offset < bank14_end
    }
    unexpected_bank14_offsets = sorted(
        bank14_changed_offsets - allowed_bank14_offsets
    )
    if unexpected_bank14_offsets:
        preview = ", ".join(
            f"0x{offset:06X}"
            for offset in unexpected_bank14_offsets[:8]
        )
        if len(unexpected_bank14_offsets) > 8:
            preview += ", ..."
        failures.append(
            "Bank 14 changes outside title/menu tiles: " + preview
        )
    if expected_title_rom is not None and rom[bank14_start:bank14_end] != (
        expected_title_rom[bank14_start:bank14_end]
    ):
        failures.append(
            'Bank 14 differs from the expected YELLOW VERSION title and credits'
        )

    if profile == "en-US":
        expected_font_offsets = {
            ASCII_FONT_OFFSET + tile_index * 16: base[
                ASCII_FONT_OFFSET + tile_index * 16
                : ASCII_FONT_OFFSET + (tile_index + 1) * 16
            ]
            for tile_index in range(96)
        }
        font_label = "Preserved English font"
    else:
        expected_french_font_tiles = french_font_tiles(
            extract_ascii_font(base)
        )
        expected_font_offsets = {
            ASCII_FONT_OFFSET + (code - 0x20) * 16: tile
            for code, tile in expected_french_font_tiles.items()
        }
        font_label = "French font"
    allowed_bank15_offsets = {
        offset + byte_index
        for offset in expected_font_offsets
        for byte_index in range(16)
    }
    bank15_start = INES_HEADER_SIZE + 15 * PRG_BANK_SIZE
    bank15_end = bank15_start + PRG_BANK_SIZE
    bank15_changed_offsets = {
        offset
        for offset in all_changed_offsets
        if bank15_start <= offset < bank15_end
    }
    unexpected_bank15_offsets = sorted(
        bank15_changed_offsets - allowed_bank15_offsets
    )
    if unexpected_bank15_offsets:
        preview = ", ".join(
            f"0x{offset:06X}"
            for offset in unexpected_bank15_offsets[:8]
        )
        if len(unexpected_bank15_offsets) > 8:
            preview += ", ..."
        failures.append(
            "Bank 15 changes outside French glyphs: " + preview
        )

    for offset, expected_tile in expected_font_offsets.items():
        actual_tile = rom[offset : offset + 16]
        if actual_tile != expected_tile:
            failures.append(
                f"Unexpected {profile} profile glyph at 0x{offset:06X}: "
                f"{sha256(actual_tile)} instead of {sha256(expected_tile)}"
            )

    wrong_title_tiles = []
    for offset, expected_tile in expected_title_tiles.items():
        actual_tile = rom[offset:offset + 16]
        if actual_tile != expected_tile:
            wrong_title_tiles.append(
                (offset, sha256(actual_tile), sha256(expected_tile))
            )
    for offset, actual_hash, expected_hash in wrong_title_tiles:
        failures.append(
            f"Unexpected title/menu tile at 0x{offset:06X}: "
            f"{actual_hash} instead of {expected_hash}"
        )

    title_graphics_block = b"".join(
        rom[offset:offset + 16]
        for offset in sorted(expected_title_tiles)
    )
    expected_title_graphics_block = b"".join(
        expected_title_tiles[offset]
        for offset in sorted(expected_title_tiles)
    )
    title_graphics_hash = sha256(title_graphics_block)
    expected_title_graphics_hash = sha256(
        expected_title_graphics_block
    )

    player_menu_pt0 = rom[
        PLAYER_MENU_PT0_FILE
        : PLAYER_MENU_PT0_FILE + PLAYER_MENU_PT0_SIZE
    ]
    player_menu_pt0_hash = sha256(player_menu_pt0)
    expected_player_menu_hash = (
        sha256(
            base[
                PLAYER_MENU_PT0_FILE
                : PLAYER_MENU_PT0_FILE + PLAYER_MENU_PT0_SIZE
            ]
        )
        if profile == "en-US"
        else PLAYER_MENU_PT0_SHA256
    )
    if player_menu_pt0_hash != expected_player_menu_hash:
        failures.append(
            "Unexpected player-menu CHR: "
            f"{player_menu_pt0_hash} instead of {expected_player_menu_hash}"
        )

    print("Mapper 163 cartridge validation")
    print(f"- ROM : {rom_path.resolve()}")
    print(f"- SHA-256 : {sha256(rom)}")
    print(
        f"- Header : mapper={info['mapper']} PRG={info['prg_size']} "
        f"CHR-ROM={info['chr_size']} vertical={info['vertical']} "
        f"battery={info['battery']}"
    )
    print(
        "- Model : 64 switchable 32 KiB PRG banks, "
        "8 KiB CHR-RAM"
    )
    print(
        "- Region header : "
        + ("PAL" if info["region_byte"] else "NTSC")
        + " (Mesen DB classifies the source Chinese ROM as Dendy)"
    )
    print(
        "- Banks changed from base: "
        + ", ".join(f"{pair}={count}" for pair, count in sorted(pairs.items()))
    )
    print(
        "- Chinese dojo deputy sprite : "
        f"SHA-256={dojo_deputy_sprite_hash}"
    )
    print(
        f'- Bank 8 graphical move names: {move_label_certification.requested_count} composites, {len(move_label_certification.used_even_slots)} cells, {len(move_label_certification.changed_pair8_offsets)} bytes changed'
    )
    if profile == "en-US":
        print(
            f'- Bank 4 battle-menu CHR window (stock): 0x{BATTLE_MENU_CHR_START_LOW_OFFSET:06X}=0x{rom[BATTLE_MENU_CHR_START_LOW_OFFSET]:02X}'
        )
    print(
        f'- Bank 5 player-menu graphics: {len(bank5_changed_offsets)} bytes changed, CHR PT0 SHA-256={player_menu_pt0_hash}'
    )
    print(
        f'- Bank 14 title/menu graphics: {len(bank14_changed_offsets)} bytes changed, target block SHA-256={title_graphics_hash}'
    )
    print(f'- Expected title logo: {title_logo_label}')
    print(
        f'- Bank 15 {font_label}: {len(bank15_changed_offsets)} bytes changed, {len(expected_font_offsets)} glyphs verified'
    )
    print(
        "- RESET trampoline $5300/$5000/$5200 : "
        + ("OK" if stub == RESET_STUB else "FAILED")
    )
    print(
        "- NMI/RESET/IRQ vectors : "
        + ("OK" if rom[-6:] == EXPECTED_VECTORS else "FAILED")
    )

    if failures:
        print("- Result: FAILED")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("- Result: OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the iNES mapper 163 hardware contract."
    )
    parser.add_argument(
        "--rom",
        default="Pokemon_Jaune_FR_repacked_title.nes",
    )
    parser.add_argument(
        "--base-rom",
        default="Pokemon Yellow English 9-23-2015.nes",
    )
    parser.add_argument(
        "--title-logo",
        choices=("english", "yellow-version", "french"),
        default="english",
        help=(
            'expected logo: English YELLOW (default) or French JAUNE'
        ),
    )
    parser.add_argument(
        "--title-reference-rom",
        default="yellow.nes",
        help="Canonical ROM providing YELLOW VERSION",
    )
    parser.add_argument(
        "--title-credits",
        default=ENGLISH_TITLE_CREDITS,
    )
    parser.add_argument(
        "--title-credits-mode",
        choices=("original", "shared"),
        default="original",
        help="original credit line or shared FR/EN credits",
    )
    parser.add_argument(
        "--profile",
        choices=("fr-FR", "en-US"),
        default="fr-FR",
        help="Expected graphics/font policy (legacy default: FR).",
    )
    parser.add_argument(
        "--move-labels-csv",
        type=Path,
        help=(
            'explicit two-line move-name catalogue; defaults to locales/<profile>/move_labels_two_line.csv if available'
        ),
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(validate(build_parser().parse_args()))
