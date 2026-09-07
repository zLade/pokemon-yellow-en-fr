#!/usr/bin/env python3
"""
Translation assistant for Lei Dian Huang Bi Ka Qiu Chuan Shuo / Pokemon Yellow NES.

Checks the English IPS against the Chinese ROM, exports script.py to CSV,
audits untranslated text, and rebuilds a ROM and IPS from the CSV.
Offsets include the iNES header, as in script.py.





"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from itertools import combinations
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from tools.french_font import (
    FRENCH_GLYPH_LABELS,
    encode_game_text,
    export_font_pair,
    literal_slot_conflicts,
    patch_french_font,
)
from tools.dialogue_layout import (
    DIALOGUE_LAYOUT,
    SUPPORTED_LAYOUTS,
    format_game_text,
)
from tools.dialogue_inventory import reviewed_dialogue_override
from tools.locales.profiles import (
    ENGLISH_TEXT_PROFILE,
    FRENCH_TEXT_PROFILE,
    TextProfile,
    get_release_profile,
)
from tools.move_label_graphics import (
    MOVE_COUNT,
    MOVE_NAME_POINTER_TABLE_OFFSET,
    MoveLabelPatchReport,
    MoveLabelSpec,
    ascii_text_encoder,
    french_text_encoder,
    load_move_label_csv,
    patch_move_labels,
)
from tools.restoration_topology import (
    RESTORATION_REFERENCES,
    RESTORATION_TOPOLOGY,
    RestorationKind,
    validate_restoration_catalogue,
)


ROOT = Path(__file__).resolve().parent

CHINESE_ROM = "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"
ENGLISH_IPS = "Pokemon Yellow English 9-23-2015.ips"
CANONICAL_ENGLISH_ROM = "yellow.nes"
TRANSLATION_BASE_ROM = "Pokemon Yellow English 9-23-2015.nes"
TRANSLATION_BASE_SHA256 = (
    "d5c308b5862ccbe4647d4255a11bb0f1"
    "cb6817c4b107feac112509d658a9943b"
)
FRENCH_ROM = "Pokemon_Jaune_FR.nes"
FRENCH_IPS = "Pokemon_Jaune_FR.ips"
FINAL_ROM = "Pokemon_Jaune_FR_repacked_title.nes"
FINAL_IPS = "Pokemon_Jaune_FR_repacked_title.ips"
PATCH_SCRIPT = "script.py"
DEFAULT_PROFILE = "fr-FR"
PROFILE_CHOICES = ("fr-FR", "en-US")

FRENCH_TRANSLATION_COLUMNS = (
    "fr_text",
    "french",
    "french_text",
    "translation",
)
ENGLISH_TRANSLATION_COLUMNS = (
    "en_v2",
    "english_v2",
    "new_english_v2",
    "new_english",
    "en_text",
    "english_text",
    "translation",
)

# Seven source pointer slots in the 2015 English patch collapse distinct
# Chinese messages onto three shared English records.  The first slot in each
# group remains owned by the normal MAIN row; the other four receive their
# own reviewed English payload and pointer target.
EXPECTED_POINTER_VARIANT_REFERENCES: dict[int, tuple[int, ...]] = {
    0x0302FA: (0x03006B, 0x03006D),
    0x03162C: (0x0310F5, 0x0310F7),
    0x031A15: (0x031971, 0x031973, 0x031975),
}
EXPECTED_POINTER_VARIANT_COUNT = 7
EXPECTED_SECONDARY_POINTER_VARIANT_COUNT = 4

# Both status suffixes are appended to a runtime Pokemon name.  The 2015
# source pointers skip their shared record's leading blank, but the reviewed
# English payloads deliberately own that separator.  The primary pointer is
# relocated through the ordinary MAIN path while the secondary pointer gets a
# detached allocation, so both references must be named explicitly here.
SEMANTIC_LEADING_SEPARATOR_POINTER_REFS = frozenset(
    {0x03006B, 0x03006D, 0x030083}
)
# These immunity payloads deliberately begin with the reviewed 0x0A battle
# line-break control.  Their source pointers historically skip a one-byte
# graphical prefix, so the relocation logic must point at the new control
# itself rather than collapsing to the first visible character.
SEMANTIC_LEADING_CONTROL_POINTER_REFS = frozenset(
    {0x030173, 0x030175, 0x030177}
)

TEXT_RE = re.compile(rb"[ -~]{4,}")

ENGLISH_HINTS = {
    "the", "you", "your", "are", "is", "not", "yes", "no", "item", "shop",
    "trainer", "leader", "badge", "gym", "pokemon", "pok@mon", "pikachu",
    "attack", "battle", "fight", "run", "route", "city", "town", "oak",
    "prof", "team", "rocket", "level", "evolve", "learn", "got", "lost",
    "won", "buy", "sell", "leave", "heal", "save", "game", "enemy",
    "none", "hello", "welcome", "world", "name", "people", "blocked",
    "effective", "experience", "escaped", "caught", "poison", "burn",
}

SAFE_TEXT_FILL_VALUE = 0x30
SAFE_TEXT_FILL_PREFIX = 0x0D
DEFAULT_MIN_FREE_RUN = 32
INES_HEADER_SIZE = 16
PRG_BANK_SIZE = 0x8000
PROTECTED_BANK_TAIL_SIZE = 64
STRUCTURED_GLYPH_RECORD_COUNT = 317
STRUCTURED_GLYPH_PAIR_COUNT = 2707
STRUCTURED_GLYPH_PAYLOAD_SIZE = 6711
STRUCTURED_GLYPH_RECORDS_SHA256 = (
    "5a9a4ab9e7f98d1ba0d21fe508a0056a"
    "70544977ee5a6cf5c7aad9343b8585c2"
)

# The stock battle-command renderer reserves 16 dynamic glyphs from $0960.
# Longer localized menus may use the verified unused $0920 start, which adds
# two glyphs before the message pane begins at $0B60.  English remains on the
# stock start once its structural Bag separator restores the original total.
BATTLE_MENU_LABEL_OFFSETS = (0x030588, 0x03058E, 0x030594, 0x030599)
BATTLE_MENU_STOCK_GLYPHS = 16
BATTLE_MENU_EXPANDED_GLYPHS = 18
BATTLE_MENU_CHR_START_LOW_OFFSET = 0x02321B
BATTLE_MENU_CHR_START_LOW_ORIGINAL = 0x60
BATTLE_MENU_CHR_START_LOW_EXPANDED = 0x20

# This one fixed Bag-list label is outside the catalogued pointer corpus.  The
# renderer writes a two-digit quantity after an eight-cell name field; using
# six visible cells preserves the item identity and leaves a real separator.
FIXED_ANTIDOTE_LABEL_OFFSET = 0x03172E
FIXED_ANTIDOTE_LABEL_SOURCE = b"Antidote\x0D"
FIXED_ANTIDOTE_LABEL_PATCH = b"Antid.\x0D00"

# The stock text loop treats every byte except 0x0D as a glyph.  A small,
# verified code cave gives reviewed battle fragments one explicit 0x0A line
# break.  It resets the nametable cursor to column 4 two tile rows lower; CHR
# allocation continues normally, so the following word remains intact.
BATTLE_TEXT_CONTROL_HOOK_OFFSET = 0x020986
BATTLE_TEXT_CONTROL_HOOK_SOURCE = b"\xC9\x0D\xF0\x4F"
BATTLE_TEXT_CONTROL_HOOK_PATCH = b"\x4C\x33\xF4\xEA"
BATTLE_TEXT_CONTROL_CAVE_OFFSET = 0x027443
BATTLE_TEXT_CONTROL_CAVE_SOURCE = bytes(39)
BATTLE_TEXT_CONTROL_CAVE_PATCH = bytes.fromhex(
    "C9 0D F0 07 C9 0A F0 06 4C 7A 89 4C C9 89 "
    "A5 0F C9 23 B0 F7 A5 0E 29 E0 18 69 44 85 "
    "0E A5 0F 69 00 85 0F C8 4C 69 89"
)
# When a status move targets an already-affected Pokémon, both battle-side
# branches converge after rendering table entry 0x86.  The stock code then
# renders the normal status payload as well, producing joins such as
# ``alreadyis paralyzed``.  Entry 0x86 is now a complete localized sentence;
# this jump keeps the normal status paths untouched and skips only that second
# payload on the already-affected path.
BATTLE_STATUS_UNCHANGED_SKIP_OFFSET = 0x02480D
BATTLE_STATUS_UNCHANGED_SKIP_SOURCE = b"\xA9\x00\x85"
BATTLE_STATUS_UNCHANGED_SKIP_PATCH = b"\x4C\x0C\xC8"
# The battle window has 25 interior cells (nametable columns 4 through 28),
# but the stock clear rectangle covers only 24.  Clearing the real interior
# prevents cell 25 from surviving into the following message; column 29 is the
# border and remains untouched.
BATTLE_TEXT_CLEAR_WIDTH_OFFSET = 0x0231C1
BATTLE_TEXT_CLEAR_WIDTH_SOURCE = b"\x18"
BATTLE_TEXT_CLEAR_WIDTH_PATCH = b"\x19"

# Four live graphical dialogue records begin immediately after pointer tables.
# The generic bank scanner intentionally rejects the bytes preceding them, so
# they are verified independently instead of changing the historical
# fingerprint of the 317 standalone graphical records.  Entries are
# ``(start, end_exclusive, pair, glyph_count, payload_sha256)``.
VERIFIED_FIELD_GRAPHICAL_TEXT_RECORDS: tuple[
    tuple[int, int, int, int, str],
    ...,
] = (
    (
        0x034927,
        0x03492D,
        6,
        3,
        "f919a566b7e34b42622c4e0b294efff"
        "bb9ef1a90852be94bceec5661ef9e189a",
    ),
    (
        0x034C03,
        0x034C08,
        6,
        2,
        "8a1fe0c044d882c23c051bd77aa64c9"
        "235a55c00fd9a6e8e4264c631bc410efe",
    ),
    (
        0x038445,
        0x0384F6,
        7,
        83,
        "b8360969bbc699edd6cd0957a2027231e"
        "ec87a2660647c4fda30127f5ceccb7c",
    ),
    (
        0x03D088,
        0x03D0A6,
        7,
        13,
        "b079bacbe7f019ceb2a7cfd44bcd89ec"
        "d157608151dd55e3932e50d4f3915db5",
    ),
)

# Exact padding arenas introduced by the canonical English patch. New runs are
# never accepted automatically. The fixed 0x03F033-0x03F26A run is
# intentionally absent because it belongs to a non-relocatable text record.
VERIFIED_TEXT_PADDING_ARENAS: tuple[tuple[int, int], ...] = (
    (0x030AF4, 0x030F83),
    (0x033002, 0x033025),
    (0x033EAA, 0x033EDD),
    (0x035CC1, 0x035CEA),
    (0x037C28, 0x037FCF),
    (0x03EE33, 0x03F008),
    (0x03F626, 0x03FFCD),
)

# Short padding slots reviewed byte-for-byte.  They are deliberately separate
# from the large arenas because their safety comes from their exact context,
# not from a generic minimum run length:
# - 0x030284/0x030431 precede live text targets at their exclusive end;
# - 0x031642/0x03312E follow terminated graphical records and stop before FF
#   sentinels.
VERIFIED_TEXT_MICRO_ARENAS: tuple[tuple[int, int], ...] = (
    (0x030284, 0x03028D),
    (0x030431, 0x030439),
    (0x031642, 0x031647),
    (0x03312E, 0x033133),
)

# Short or interrupted pointer tables that were verified against the English
# ROM. These references are required only for translations that exceed their
# original slots. Keeping them explicit avoids the old contextual heuristic,
# which could mistake two-byte glyph data inside unused Chinese text blocks
# for pointers.
VERIFIED_POINTER_OVERRIDES: dict[int, tuple[int, ...]] = {
    0x0301EB: (0x030031,),
    0x03041D: (0x03002D,),
    0x0303A1: (0x03007F,),
    0x030417: (0x030099,),
    0x03070B: (0x03014F,),
    0x03076D: (0x030161,),
    0x030966: (0x0301B1,),
    0x0310FB: (0x030F99,),
    0x031126: (0x030FA5,),
    0x03112C: (0x030FA7,),
    0x031196: (0x030FC3,),
    0x0311BC: (0x030FCD,),
    0x0311CD: (0x030FD1,),
    0x031238: (0x030FED,),
    0x031252: (0x030FF3,),
    0x03126B: (0x030FF9,),
    0x031274: (0x030FFB,),
    0x03127D: (0x030FFD,),
    0x031313: (0x031021,),
    0x031318: (0x031023,),
    0x03132B: (0x031029,),
    0x031368: (0x03103B,),
    0x0313B9: (0x03104F,),
    0x0313BE: (0x031051,),
    0x031402: (0x031065,),
    0x03144A: (0x031075,),
    0x03146A: (0x03107D,),
    0x03146F: (0x03107F,),
    0x0314D2: (0x031099,),
    0x0314D7: (0x03109B,),
    0x031506: (0x0310A7,),
    0x031523: (0x0310AF,),
    0x031584: (0x0310CB,),
    0x0315B9: (0x0310D9,),
    0x0315BF: (0x0310DB,),
    0x03159C: (0x0310D1,),
    0x0315E1: (0x0310E3,),
    0x03160A: (0x0310EF,),
    0x033B7F: (0x033187,),
    0x033D67: (0x033191,),
    0x033E5F: (0x03319B,),
    0x0343EF: (0x0331CB,),
    0x03492F: (0x0348DF,),
    0x03495F: (0x0348E7,),
    0x034975: (0x0348EB,),
    0x03499D: (0x0348F1,),
    0x0349A9: (0x0348F3,),
    0x0349B5: (0x0348F5,),
    0x0349CD: (0x0348F9,),
    0x0349DB: (0x0348FB,),
    0x034E8B: (0x034B15,),
    0x034F18: (0x034B77,),
    0x0350D6: (0x034B39,),
    0x035154: (0x034B43,),
    0x035206: (0x034B4F,),
    0x03523F: (0x034B51,),
    0x035500: (0x034B75,),
    0x035C48: (0x034BE5,),
    0x0367EA: (0x034B3B,),
    0x037AB1: (0x0331CF,),
    0x0381AF: (0x03803B,),
    0x0381D3: (0x03803F,),
    0x038230: (0x038049,),
    0x03BEE1: (0x03AFAE,),
    0x03C33F: (0x03B002,),
    0x03DCAA: (0x03D084,),
}

# Four post-battle pointers in the English patch were wired to unrelated
# Route 25/Charmander strings.  They all correspond to the same canonical
# Nugget Bridge reply already stored at 0x039AF5.  The tuple is
# ``(incorrect_base_target, reviewed_replacement_target)``.
VERIFIED_POINTER_REDIRECTS: dict[int, tuple[int, int]] = {
    0x038347: (0x039D3B, 0x039AF5),
    0x03834B: (0x039D74, 0x039AF5),
    0x03834F: (0x039DB8, 0x039AF5),
    0x038353: (0x039DF5, 0x039AF5),
}

# The 2015 English move-name table packed its last three live records one
# and two slots earlier than the reviewed Chinese table.  These two ownership
# corrections expose Transform and Curse to the proper catalogue rows; the
# shared Strength source is then split through pointer_variants.csv.
VERIFIED_SOURCE_ALIGNMENT_POINTER_REDIRECTS: dict[
    int, tuple[int, int]
] = {
    0x0310F3: (0x031619, 0x031624),
    0x0310F5: (0x031624, 0x03162C),
    0x0310F7: (0x03162C, 0x03162C),
}
_TOPOLOGY_POINTER_REDIRECTS = {
    reference: (
        int(slot.observed_english_target),
        int(slot.reviewed_replacement_target),
    )
    for reference, slot in RESTORATION_TOPOLOGY.items()
    if slot.kind is RestorationKind.MISWIRED
}
if VERIFIED_POINTER_REDIRECTS != _TOPOLOGY_POINTER_REDIRECTS:
    raise AssertionError(
        "verified redirects differ from the restoration topology"
    )

# Exact pointer slots selected by the overworld/NPC text dispatcher at
# CPU $8D42.  The common renderer reached by these seven tables consumes
# 19 columns on every line.  Ranges are inclusive and every slot is a
# little-endian 16-bit pointer in the same 32 KiB PRG pair as its target.
VERIFIED_FIELD_DIALOGUE_POINTER_RANGES: tuple[tuple[int, int], ...] = (
    (0x033143, 0x033191),
    (0x03319B, 0x0331B1),
    (0x0331CB, 0x0331CF),
    (0x0331D3, 0x0331ED),
    (0x0348DD, 0x034925),
    (0x034AE9, 0x034BFF),
    (0x03801B, 0x038049),
    (0x038249, 0x038311),
    (0x038327, 0x038443),
    (0x03AE60, 0x03AF92),
    (0x03AFAE, 0x03AFAE),
    (0x03AFB4, 0x03AFE8),
    (0x03B002, 0x03B002),
    (0x03B008, 0x03B056),
    (0x03CE8C, 0x03CF3C),
    (0x03CF5A, 0x03D072),
    (0x03D076, 0x03D078),
    (0x03D082, 0x03D086),
)
VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT = 972
VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS = 968

# Exact dummy/sentinel words that resemble text pointers but are outside every
# live dispatcher range.  0x03D074 targets the middle of a 567-byte ASCII
# ``0`` padding prefix, so repointing it as dialogue would manufacture an
# invalid interior target.
VERIFIED_NON_DIALOGUE_POINTER_REFS: dict[int, int] = {
    0x03D074: 0x03F186,
}


@dataclass(frozen=True)
class IpsRecord:
    offset: int
    data: bytes
    rle: bool = False


@dataclass(frozen=True)
class PatchEntry:
    offset: int
    text: str
    line: int
    layout: str = ""


@dataclass
class TranslationRow:
    offset: int
    text: str
    max_len: int | None
    layout: str = ""


@dataclass(frozen=True)
class PointerVariant:
    variant_key: str
    stable_key: str
    main_offset: int
    pointer_reference: int
    shared_source_target: int
    text: str


@dataclass
class FreeSpan:
    start: int
    length: int


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_text_profile(
    profile: str | TextProfile | None = None,
) -> TextProfile:
    """Resolve a CLI/profile value while preserving the historical FR default."""
    if isinstance(profile, TextProfile):
        return profile
    return get_release_profile(profile or DEFAULT_PROFILE).text


def text_profile_from_args(args: argparse.Namespace) -> TextProfile:
    """Return the selected text profile for old and new ``Namespace`` values."""
    return resolve_text_profile(getattr(args, "profile", DEFAULT_PROFILE))


def format_profile_text(
    text: str,
    layout: str = "",
    *,
    text_profile: TextProfile | None = None,
) -> bytes:
    """Format text through a profile, delegating FR to the legacy function."""
    profile = resolve_text_profile(text_profile)
    if profile is FRENCH_TEXT_PROFILE:
        return format_game_text(text, layout)
    return profile.format_text(text, layout)


def profile_literal_slot_conflicts(
    text: str,
    *,
    text_profile: TextProfile | None = None,
) -> set[str]:
    """Return literal source characters reserved by the selected font."""
    profile = resolve_text_profile(text_profile)
    if profile is FRENCH_TEXT_PROFILE:
        return literal_slot_conflicts(text)
    return {
        character
        for character in text
        if character in profile.reserved_ascii_literals
    }


def apply_french_font_and_export(
    original: bytes,
    rom: bytearray,
    output_rom: Path,
) -> tuple[Path, int]:
    """Patch the runtime font and archive editable before/after CHR files."""
    before = bytes(rom)
    tiles = patch_french_font(rom)
    after = bytes(rom)
    changed = sum(
        left != right
        for left, right in zip(before, after)
    )
    digest = sha256(after)[:12]
    export_directory = (
        ROOT
        / "build"
        / "chr-exports"
        / f"{output_rom.stem}-french-font-{digest}"
    )
    before_path, after_path = export_font_pair(
        original,
        after,
        export_directory,
    )
    native_characters = " ".join(
        character
        for _, character in (
            FRENCH_GLYPH_LABELS[code]
            for code in sorted(FRENCH_GLYPH_LABELS)
        )
    )
    manifest = "\n".join(
        [
            "Pokemon Yellow NES - French font export",
            f"Planned output ROM: {output_rom.resolve()}",
            f"ROM with font SHA-256: {sha256(after)}",
            f"French tiles: {len(tiles)}",
            f"Changed font bytes: {changed}",
            f"Before CHR: {before_path.resolve()}",
            f"French CHR: {after_path.resolve()}",
            f"Native French characters: {native_characters}",
            "Note: é reuses the @ glyph already present in the English base.",
            "Trade-off: œ/Œ remain oe/OE to preserve all ASCII letters "
            "in entered names.",
            "Result: PASS",
            "",
        ]
    )
    (export_directory / "font_export_manifest.txt").write_text(
        manifest,
        encoding="utf-8",
    )
    return export_directory, changed


def apply_profile_font_and_export(
    original: bytes,
    rom: bytearray,
    output_rom: Path,
    *,
    text_profile: TextProfile | None = None,
) -> tuple[Path | None, int]:
    """Apply locale font policy without changing the historical FR path.

    The English 2015 base already contains the required printable font and its
    ``@`` tile is the ``é`` glyph.  The English profile must therefore perform
    no write and create no French CHR export directory.
    """
    profile = resolve_text_profile(text_profile)
    if profile is FRENCH_TEXT_PROFILE:
        return apply_french_font_and_export(original, rom, output_rom)
    return None, 0


def default_move_label_catalog(
    text_profile: TextProfile | None,
) -> Path | None:
    """Return the locale-owned two-line move plan when this checkout has one."""
    profile = resolve_text_profile(text_profile)
    locale = "fr-FR" if profile is FRENCH_TEXT_PROFILE else "en-US"
    candidate = ROOT / "locales" / locale / "move_labels_two_line.csv"
    return candidate if candidate.is_file() else None


def resolve_move_label_catalog(
    requested: str | Path,
    *,
    text_profile: TextProfile | None,
) -> Path | None:
    if requested:
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if not candidate.is_file():
            raise ValueError(f'Missing two-line move plan: {candidate}')
        return candidate
    return default_move_label_catalog(text_profile)


def apply_profile_move_label_graphics(
    original: bytes,
    rom: bytearray,
    *,
    text_profile: TextProfile | None,
    catalogue: Path | None,
    specs: tuple[MoveLabelSpec, ...] | None = None,
) -> MoveLabelPatchReport | None:
    """Install locale graphics after the final ASCII font has been patched."""
    if catalogue is None:
        return None
    profile = resolve_text_profile(text_profile)
    encoder = (
        french_text_encoder
        if profile is FRENCH_TEXT_PROFILE
        else ascii_text_encoder
    )
    if specs is None:
        specs = load_move_label_csv(catalogue, encoder=encoder)
    result = patch_move_labels(
        bytes(rom),
        original,
        specs,
        pool_mode="source",
        require_all=True,
    )
    rom[:] = result.rom
    return result.report


def load_profile_move_label_specs(
    *,
    text_profile: TextProfile | None,
    catalogue: Path | None,
) -> tuple[MoveLabelSpec, ...]:
    if catalogue is None:
        return ()
    profile = resolve_text_profile(text_profile)
    encoder = (
        french_text_encoder
        if profile is FRENCH_TEXT_PROFILE
        else ascii_text_encoder
    )
    return load_move_label_csv(catalogue, encoder=encoder)


def move_graphic_reservation_payload(
    move_index: int,
    required_payload_size: int,
) -> bytes:
    """Return a suffix-pooling-proof placeholder for one graphical move.

    The normal allocator stores identical strings and suffixes only once.
    Graphical labels cannot share those bytes because their final two-byte
    codes differ from the temporary ASCII text.  Every reservation therefore
    ends with its own non-printable length byte, while equal-length markers
    carry a distinct safe move byte.  Consequently no reservation is a suffix
    of another reservation or of any printable translation payload.
    """
    if not 0 <= move_index < MOVE_COUNT:
        raise ValueError(f"move index out of range: {move_index}")
    content_length = required_payload_size - 1
    if content_length not in {2, 4, 6, 8}:
        raise ValueError(
            f'Invalid graphics reservation size: {required_payload_size}'
        )
    safe_identity_bytes = tuple(
        value
        for value in range(0x100)
        if value != 0x0D and not 0xB0 <= value <= 0xBF
    )
    identity = safe_identity_bytes[move_index]
    return (
        bytes((identity,))
        + b"\0" * (content_length - 2)
        + bytes((content_length,))
    )


def read_bytes(path: str | Path) -> bytes:
    return (ROOT / path).read_bytes() if not Path(path).is_absolute() else Path(path).read_bytes()


def parse_ips(path: str | Path) -> tuple[list[IpsRecord], int | None]:
    data = read_bytes(path)
    if not data.startswith(b"PATCH"):
        raise ValueError(f"{path} is not a valid IPS")

    records: list[IpsRecord] = []
    i = 5
    truncate: int | None = None
    found_eof = False
    while i < len(data):
        if data[i:i + 3] == b"EOF":
            i += 3
            found_eof = True
            remaining = len(data) - i
            if remaining == 3:
                truncate = int.from_bytes(data[i:i + 3], "big")
            elif remaining != 0:
                raise ValueError(
                    f"{path} contains {remaining} unexpected byte(s) after EOF"
                )
            break

        if i + 5 > len(data):
            raise ValueError(f"IPS truncated near 0x{i:X}")

        offset = int.from_bytes(data[i:i + 3], "big")
        i += 3
        size = int.from_bytes(data[i:i + 2], "big")
        i += 2

        if size == 0:
            if i + 3 > len(data):
                raise ValueError(f"IPS RLE truncated near 0x{i:X}")
            rle_size = int.from_bytes(data[i:i + 2], "big")
            i += 2
            value = data[i]
            i += 1
            records.append(IpsRecord(offset, bytes([value]) * rle_size, True))
        else:
            if i + size > len(data):
                raise ValueError(f"IPS record truncated near 0x{i:X}")
            records.append(IpsRecord(offset, data[i:i + size], False))
            i += size

    if not found_eof:
        raise ValueError(f"{path} has no IPS EOF marker")

    return records, truncate


def apply_ips(data: bytes, records: Iterable[IpsRecord], truncate: int | None = None) -> bytes:
    out = bytearray(data)
    for record in records:
        end = record.offset + len(record.data)
        if end > len(out):
            out.extend(b"\0" * (end - len(out)))
        out[record.offset:end] = record.data
    if truncate is not None:
        if truncate < len(out):
            del out[truncate:]
        elif truncate > len(out):
            out.extend(b"\0" * (truncate - len(out)))
    return bytes(out)


def make_ips(original: bytes, modified: bytes) -> bytes:
    max_offset = 0xFFFFFF
    max_record_size = 0xFFFF
    eof_record_offset = int.from_bytes(b"EOF", "big")
    if len(modified) != len(original) and len(modified) > max_offset:
        raise ValueError(
            f'Final IPS size exceeds the 24-bit limit: {len(modified)} > {max_offset}'
        )

    ips = bytearray(b"PATCH")

    def append_block(offset: int, block: bytes) -> None:
        while block:
            # A record beginning at ASCII ``EOF`` is indistinguishable from
            # the end marker. Include the preceding target byte so that the
            # record starts at a representable offset instead.
            if offset == eof_record_offset:
                offset -= 1
                block = modified[offset : offset + 1] + block
            if offset > max_offset:
                raise ValueError(
                    f'IPS offset exceeds 24 bits: 0x{offset:X}'
                )
            chunk = block[:max_record_size]
            ips.extend(offset.to_bytes(3, "big"))
            ips.extend(len(chunk).to_bytes(2, "big"))
            ips.extend(chunk)
            offset += len(chunk)
            block = block[len(chunk):]

    limit = len(modified)
    original_limit = len(original)
    i = 0
    while i < limit:
        while (
            i < limit
            and i < original_limit
            and original[i] == modified[i]
        ):
            i += 1
        if i >= limit:
            break

        start = i
        while i < limit and (
            i >= original_limit or original[i] != modified[i]
        ):
            i += 1
        append_block(start, modified[start:i])

    if len(modified) != len(original):
        ips.extend(b"EOF")
        ips.extend(len(modified).to_bytes(3, "big"))
    else:
        ips.extend(b"EOF")
    return bytes(ips)


def printable_len(data: bytes, offset: int) -> int:
    length = 0
    while offset + length < len(data) and 0x20 <= data[offset + length] <= 0x7E:
        length += 1
    return length


def decode_ascii(data: bytes) -> str:
    return data.decode("ascii", errors="replace")


# These records are sentence fragments immediately followed by a runtime
# value (Trainer, Pokemon, move, item, level or money amount).  Their final
# blank is semantic punctuation, not obsolete source-layout padding.  Keep
# exactly one separator so repacking cannot produce joins such as
# ``Gary sent outEevee`` or ``Pikachu usedThunderShock``.
TRAILING_SEPARATOR_OFFSETS = frozenset(
    {
        0x0301EB,  # Go! <Pokemon>
        0x0301F0,  # Wild <Pokemon>
        0x030221,  # Ash used <item>
        0x03022A,  # Gotcha! <Pokemon>
        0x030230,  # Oh no! <Pokemon>
        0x030262,  # <Trainer> sent out <Pokemon>
        0x0302BF,  # <Pokemon> used <move>
        0x030417,  # Congrats! <Pokemon>
        0x03041D,  # Oh! A wild <Pokemon>
        0x030458,  # <Pokemon> wants to learn <move>
        0x03045F,  # <Pokemon> completely forgot how to use <move>
        0x03049A,  # <Pokemon> and learned <move>
        0x0304AB,  # <Pokemon> did not learn <move>
        0x030567,  # <Pokemon> ate <Pokemon>'s dream
        0x03062E,  # Wild <Pokemon>
        0x030634,  # Foe <Pokemon>
        0x03067D,  # <Pokemon> grew to level <number>
        0x03075C,  # Got <item>
        0x030765,  # Paid <amount>
        0x03076B,  # <Player> lost to <Trainer>
        0x03077A,  # Requires <Badge>
        0x030ADB,  # Defeated <Trainer>
        0x035F3D,  # Battle result: <amount>
        0x035F57,  # evolved into <Pokemon>
        0x035FAE,  # Give up on learning <move>
        0x035FB6,  # Opponent will use <Pokemon>
    }
)


def normalize_repacked_payload(
    source: bytes,
    source_offset: int,
    source_length: int,
    translated: bytes,
    live_targets: Iterable[int],
    *,
    graphical: bool = False,
    preserve_runtime_separator: bool = False,
) -> bytes:
    """Remove obsolete source-layout padding from a relocated translation.

    The English patch uses literal ``0`` bytes as invisible prefix padding and
    many records retain spaces after their last visible character.  A repacked
    string has its own terminator, so those bytes need not consume the scarce
    text bank.  Prefix removal is allowed only when every live ASCII target is
    the record start or its reviewed visible-text start.  Suffix removal is
    allowed only when every relocated target still lands inside visible data.
    Leading spaces are never stripped because several battle fragments rely on
    them when concatenated with a Pokémon name.
    """
    targets = tuple(sorted(set(live_targets)))
    source_prefix = reviewed_text_prefix_len(
        source[source_offset:source_offset + source_length]
    )
    deltas = tuple(target - source_offset for target in targets)
    payload = translated

    if graphical or all(delta in (0, source_prefix) for delta in deltas):
        payload = payload.lstrip(b"0")

    keep_trailing_separator = (
        preserve_runtime_separator
        and source_offset in TRAILING_SEPARATOR_OFFSETS
        and payload.endswith(b" ")
    )
    trimmed = payload.rstrip(b" ")
    if keep_trailing_separator and trimmed:
        trimmed += b" "
    if not trimmed:
        return payload

    translated_prefix = reviewed_text_prefix_len(payload)
    relocated_deltas: list[int] = []
    for delta in deltas:
        if graphical and delta > 0:
            relocated_deltas.append(translated_prefix)
        elif source_prefix > 0 and delta == source_prefix:
            relocated_deltas.append(translated_prefix)
        else:
            relocated_deltas.append(delta)

    if all(delta < len(trimmed) for delta in relocated_deltas):
        payload = trimmed
    return payload


def expand_battle_menu_chr_slots(
    source: bytes,
    candidate: bytearray,
    translated_labels: Iterable[bytes],
) -> bool:
    """Expand the battle-menu CHR window only when labels need it."""
    glyph_count = sum(len(label) for label in translated_labels)
    if glyph_count <= BATTLE_MENU_STOCK_GLYPHS:
        return False
    if glyph_count > BATTLE_MENU_EXPANDED_GLYPHS:
        raise ValueError(
            f"battle menu requires {glyph_count} glyphs, "
            f"{BATTLE_MENU_EXPANDED_GLYPHS} available"
        )
    if source[BATTLE_MENU_CHR_START_LOW_OFFSET] != (
        BATTLE_MENU_CHR_START_LOW_ORIGINAL
    ):
        raise ValueError(
            "battle menu CHR table source mismatch at "
            f"0x{BATTLE_MENU_CHR_START_LOW_OFFSET:06X}"
        )
    actual = candidate[BATTLE_MENU_CHR_START_LOW_OFFSET]
    if actual not in {
        BATTLE_MENU_CHR_START_LOW_ORIGINAL,
        BATTLE_MENU_CHR_START_LOW_EXPANDED,
    }:
        raise ValueError(
            "battle menu CHR table candidate mismatch at "
            f"0x{BATTLE_MENU_CHR_START_LOW_OFFSET:06X}: 0x{actual:02X}"
        )
    candidate[BATTLE_MENU_CHR_START_LOW_OFFSET] = (
        BATTLE_MENU_CHR_START_LOW_EXPANDED
    )
    return True


def patch_fixed_antidote_bag_label(
    source: bytes,
    candidate: bytearray,
) -> None:
    """Keep the non-catalogued Antidote label clear of the quantity field."""
    start = FIXED_ANTIDOTE_LABEL_OFFSET
    end = start + len(FIXED_ANTIDOTE_LABEL_SOURCE)
    if source[start:end] != FIXED_ANTIDOTE_LABEL_SOURCE:
        raise ValueError(
            "fixed Antidote source mismatch at "
            f"0x{FIXED_ANTIDOTE_LABEL_OFFSET:06X}"
        )
    actual = bytes(candidate[start:end])
    if actual not in {
        FIXED_ANTIDOTE_LABEL_SOURCE,
        FIXED_ANTIDOTE_LABEL_PATCH,
    }:
        raise ValueError(
            "fixed Antidote candidate mismatch at "
            f"0x{FIXED_ANTIDOTE_LABEL_OFFSET:06X}: {actual!r}"
        )
    candidate[start:end] = FIXED_ANTIDOTE_LABEL_PATCH


def patch_battle_text_line_break_control(
    source: bytes,
    candidate: bytearray,
) -> None:
    """Install bounded battle-message layout controls."""
    hook_start = BATTLE_TEXT_CONTROL_HOOK_OFFSET
    hook_end = hook_start + len(BATTLE_TEXT_CONTROL_HOOK_SOURCE)
    cave_start = BATTLE_TEXT_CONTROL_CAVE_OFFSET
    cave_end = cave_start + len(BATTLE_TEXT_CONTROL_CAVE_SOURCE)
    if source[hook_start:hook_end] != BATTLE_TEXT_CONTROL_HOOK_SOURCE:
        raise ValueError(
            "battle text control hook source mismatch at "
            f"0x{hook_start:06X}"
        )
    if source[cave_start:cave_end] != BATTLE_TEXT_CONTROL_CAVE_SOURCE:
        raise ValueError(
            "battle text control cave is not empty at "
            f"0x{cave_start:06X}"
        )
    actual_hook = bytes(candidate[hook_start:hook_end])
    if actual_hook not in {
        BATTLE_TEXT_CONTROL_HOOK_SOURCE,
        BATTLE_TEXT_CONTROL_HOOK_PATCH,
    }:
        raise ValueError(
            f"battle text control candidate hook mismatch: {actual_hook!r}"
        )
    actual_cave = bytes(candidate[cave_start:cave_end])
    if actual_cave not in {
        BATTLE_TEXT_CONTROL_CAVE_SOURCE,
        BATTLE_TEXT_CONTROL_CAVE_PATCH,
    }:
        raise ValueError(
            "battle text control candidate cave mismatch at "
            f"0x{cave_start:06X}"
        )
    status_start = BATTLE_STATUS_UNCHANGED_SKIP_OFFSET
    status_end = status_start + len(BATTLE_STATUS_UNCHANGED_SKIP_SOURCE)
    if source[status_start:status_end] != BATTLE_STATUS_UNCHANGED_SKIP_SOURCE:
        raise ValueError(
            "battle unchanged-status source mismatch at "
            f"0x{status_start:06X}"
        )
    actual_status = bytes(candidate[status_start:status_end])
    if actual_status not in {
        BATTLE_STATUS_UNCHANGED_SKIP_SOURCE,
        BATTLE_STATUS_UNCHANGED_SKIP_PATCH,
    }:
        raise ValueError(
            "battle unchanged-status candidate mismatch at "
            f"0x{status_start:06X}: {actual_status!r}"
        )
    clear_start = BATTLE_TEXT_CLEAR_WIDTH_OFFSET
    clear_end = clear_start + len(BATTLE_TEXT_CLEAR_WIDTH_SOURCE)
    if source[clear_start:clear_end] != BATTLE_TEXT_CLEAR_WIDTH_SOURCE:
        raise ValueError(
            "battle text clear-width source mismatch at "
            f"0x{clear_start:06X}"
        )
    actual_clear = bytes(candidate[clear_start:clear_end])
    if actual_clear not in {
        BATTLE_TEXT_CLEAR_WIDTH_SOURCE,
        BATTLE_TEXT_CLEAR_WIDTH_PATCH,
    }:
        raise ValueError(
            "battle text clear-width candidate mismatch at "
            f"0x{clear_start:06X}: {actual_clear!r}"
        )
    candidate[hook_start:hook_end] = BATTLE_TEXT_CONTROL_HOOK_PATCH
    candidate[cave_start:cave_end] = BATTLE_TEXT_CONTROL_CAVE_PATCH
    candidate[status_start:status_end] = BATTLE_STATUS_UNCHANGED_SKIP_PATCH
    candidate[clear_start:clear_end] = BATTLE_TEXT_CLEAR_WIDTH_PATCH


def normalize_for_hint(text: str) -> list[str]:
    return re.findall(r"[A-Za-z@]+", text.lower())


def english_score(text: str) -> int:
    tokens = normalize_for_hint(text)
    return sum(1 for token in tokens if token in ENGLISH_HINTS)


def looks_like_text(text: str) -> bool:
    if len(text.strip()) < 4:
        return False
    letters = sum(ch.isalpha() for ch in text)
    if letters < 3:
        return False
    if letters / max(1, len(text)) < 0.25:
        return False
    return True


def csv_safe(text: str) -> str:
    return text.replace("\r", "\\r").replace("\n", "\\n")


def parse_patch_entries(
    script_path: str | Path = PATCH_SCRIPT,
    *,
    apply_dialogue_inventory: bool = True,
) -> list[PatchEntry]:
    path = ROOT / script_path
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(path))
    entries: list[PatchEntry] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "p":
            continue
        if len(node.args) < 2:
            continue
        try:
            offset = ast.literal_eval(node.args[0])
            text = ast.literal_eval(node.args[1])
        except Exception:
            continue
        layout = ""
        for keyword in node.keywords:
            if keyword.arg != "layout":
                continue
            try:
                layout = ast.literal_eval(keyword.value)
            except Exception as exc:
                raise ValueError(
                    f"{path}:{getattr(node, 'lineno', 0)}: layout must be a string literal"
                ) from exc
        if not isinstance(layout, str) or layout not in SUPPORTED_LAYOUTS:
            raise ValueError(
                f"{path}:{getattr(node, 'lineno', 0)}: "
                f"unknown layout {layout!r}"
            )
        if isinstance(offset, int) and isinstance(text, str):
            entries.append(
                PatchEntry(
                    offset,
                    text,
                    getattr(node, "lineno", 0),
                    layout,
                )
            )

    if (
        apply_dialogue_inventory
        and path.resolve() == (ROOT / PATCH_SCRIPT).resolve()
    ):
        migrated: list[PatchEntry] = []
        for entry in entries:
            if entry.layout:
                migrated.append(entry)
                continue
            semantic = reviewed_dialogue_override(
                entry.offset,
                entry.text,
            )
            if semantic is None:
                migrated.append(entry)
                continue
            migrated.append(
                PatchEntry(
                    entry.offset,
                    semantic,
                    entry.line,
                    DIALOGUE_LAYOUT,
                )
            )
        entries = migrated

    entries.sort(key=lambda item: (item.offset, item.line))
    return entries


def changed_spans(records: Iterable[IpsRecord]) -> list[tuple[int, int]]:
    spans = sorted((record.offset, record.offset + len(record.data)) for record in records)
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def intersects_spans(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    # The IPS has only a few thousand spans, so a linear scan is fine here.
    for span_start, span_end in spans:
        if span_end <= start:
            continue
        if span_start >= end:
            return False
        return True
    return False


def parse_range(value: str) -> tuple[int, int]:
    if ":" in value:
        left, right = value.split(":", 1)
    elif "-" in value:
        left, right = value.split("-", 1)
    else:
        raise ValueError(f'Invalid range: {value}')
    start = int(left, 16) if left.lower().startswith("0x") else int(left)
    end = int(right, 16) if right.lower().startswith("0x") else int(right)
    if start >= end:
        raise ValueError(f'Invalid range: {value}')
    return start, end


def inside_ranges(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < range_end and end > range_start for range_start, range_end in ranges)


def pair_for_offset(offset: int) -> int:
    return (offset - INES_HEADER_SIZE) // PRG_BANK_SIZE


def cpu_addr_for_offset(offset: int) -> int:
    return 0x8000 + ((offset - INES_HEADER_SIZE) % PRG_BANK_SIZE)


def offset_for_cpu_addr(pair: int, address: int, rom_size: int) -> int | None:
    if not 0x8000 <= address <= 0xFFFF:
        return None
    offset = INES_HEADER_SIZE + pair * PRG_BANK_SIZE + (address - 0x8000)
    if offset >= rom_size:
        return None
    return offset


def protected_bank_tail(pair: int) -> tuple[int, int]:
    """Return the file range occupied by the common code/vectors bank tail."""
    end = INES_HEADER_SIZE + (pair + 1) * PRG_BANK_SIZE
    return end - PROTECTED_BANK_TAIL_SIZE, end


def find_structured_glyph_records(
    data: bytes,
) -> list[tuple[int, int, int, int]]:
    """
    Parse the double-byte graphical records in text banks 6/7.

    A glyph begins with B0-BF and consumes the following byte. ASCII/control
    bytes below 0x80 may coexist in the same record. Crucially, 0x0D is a
    delimiter only when it is not the low byte of a glyph code. The English
    patch deliberately uses noncanonical low bytes such as B1 0D, so a raw
    bytes.split(b"\\x0D") would split valid records in the middle.

    The resulting payload ranges are protected from both text allocation and
    pointer rewriting until they are explicitly translated.
    """
    records: list[tuple[int, int, int, int]] = []

    def append_if_structured(
        record_start: int,
        record_end: int,
        pair: int,
    ) -> None:
        if not 1 <= record_end - record_start <= 320:
            return

        cursor = record_start
        glyph_count = 0
        while cursor < record_end:
            value = data[cursor]
            if 0xB0 <= value <= 0xBF:
                if cursor + 1 >= record_end:
                    return
                glyph_count += 1
                cursor += 2
            elif value < 0x80:
                cursor += 1
            else:
                return

        if glyph_count:
            records.append(
                (record_start, record_end, pair, glyph_count)
            )

    for pair in (6, 7):
        start = INES_HEADER_SIZE + pair * PRG_BANK_SIZE
        end = min(len(data), start + PRG_BANK_SIZE)
        record_start = start
        cursor = start

        while cursor < end:
            value = data[cursor]
            if 0xB0 <= value <= 0xBF and cursor + 1 < end:
                cursor += 2
            elif value == 0x0D:
                append_if_structured(
                    record_start,
                    cursor,
                    pair,
                )
                cursor += 1
                record_start = cursor
            else:
                cursor += 1

        append_if_structured(record_start, end, pair)

    return records


def verified_structured_glyph_records(
    data: bytes,
) -> list[tuple[int, int, int, int]]:
    """Return glyph records only when their canonical inventory is exact."""
    records = find_structured_glyph_records(data)
    fingerprint = sha256(
        "\n".join(
            f"{start:06X}-{end:06X}"
            for start, end, _, _ in records
        ).encode("ascii")
    )
    glyph_count = sum(item[3] for item in records)
    payload_size = sum(end - start for start, end, _, _ in records)
    if (
        len(records) != STRUCTURED_GLYPH_RECORD_COUNT
        or glyph_count != STRUCTURED_GLYPH_PAIR_COUNT
        or payload_size != STRUCTURED_GLYPH_PAYLOAD_SIZE
        or fingerprint != STRUCTURED_GLYPH_RECORDS_SHA256
    ):
        raise ValueError(
            f'Noncanonical structural glyph inventory: records={len(records)}, glyphs={glyph_count}, payload={payload_size}, sha256={fingerprint}'
        )
    return records


def verified_field_graphical_text_records(
    data: bytes,
) -> list[tuple[int, int, int, int]]:
    """Validate the four live records embedded after field pointer tables."""
    records: list[tuple[int, int, int, int]] = []
    for start, end, pair, glyph_count, expected_hash in (
        VERIFIED_FIELD_GRAPHICAL_TEXT_RECORDS
    ):
        if not (
            0 <= start < end < len(data)
            and pair_for_offset(start) == pair_for_offset(end - 1) == pair
        ):
            raise ValueError(
                "field graphical record outside ROM/pair: "
                f"0x{start:06X}-0x{end:06X}"
            )
        payload = data[start:end]
        actual_hash = sha256(payload)
        if actual_hash != expected_hash:
            raise ValueError(
                "noncanonical field graphical record "
                f"0x{start:06X}: {actual_hash} instead of {expected_hash}"
            )
        cursor = 0
        actual_glyph_count = 0
        while cursor < len(payload):
            value = payload[cursor]
            if 0xB0 <= value <= 0xBF and cursor + 1 < len(payload):
                actual_glyph_count += 1
                cursor += 2
            elif value < 0x80:
                cursor += 1
            else:
                raise ValueError(
                    f'Invalid byte in field graphical record 0x{start + cursor:06X}: 0x{value:02X}'
                )
        if actual_glyph_count != glyph_count:
            raise ValueError(
                f"field graphical record 0x{start:06X}: "
                f"{actual_glyph_count} glyphs, {glyph_count} expected"
            )
        if end >= len(data) or data[end] != 0x0D:
            raise ValueError(
                f'Missing terminator after field graphical record 0x{start:06X}'
            )
        records.append((start, end, pair, glyph_count))
    return records


def verified_all_graphical_text_records(
    data: bytes,
) -> list[tuple[int, int, int, int]]:
    """Return standalone and embedded graphical text records."""
    standalone = verified_structured_glyph_records(data)
    embedded = verified_field_graphical_text_records(data)
    all_records = standalone + embedded
    ordered = sorted(all_records)
    for left, right in zip(ordered, ordered[1:]):
        if left[1] > right[0]:
            raise ValueError(
                "overlapping verified graphical records: "
                f"0x{left[0]:06X}-0x{left[1]:06X} and "
                f"0x{right[0]:06X}-0x{right[1]:06X}"
            )
    return all_records


def structured_glyph_record_map(
    records: Iterable[tuple[int, int, int, int]],
) -> dict[int, tuple[int, int, int]]:
    """Index verified graphical records by their exact source start."""
    return {
        start: (end, pair, glyph_count)
        for start, end, pair, glyph_count in records
    }


def source_record_len(
    data: bytes,
    offset: int,
    glyph_by_start: dict[int, tuple[int, int, int]] | None = None,
) -> int:
    """Return the canonical payload size for ASCII or graphical text."""
    if glyph_by_start is not None and offset in glyph_by_start:
        end, _, _ = glyph_by_start[offset]
        return end - offset
    return printable_len(data, offset)


def source_record_text(
    data: bytes,
    offset: int,
    length: int,
    glyph_by_start: dict[int, tuple[int, int, int]] | None = None,
) -> str:
    """Render a stable CSV description of an ASCII or graphical source."""
    if glyph_by_start is None or offset not in glyph_by_start:
        return decode_ascii(data[offset:offset + length])

    parts: list[str] = []
    cursor = offset
    end = offset + length
    while cursor < end:
        value = data[cursor]
        if 0xB0 <= value <= 0xBF and cursor + 1 < end:
            parts.append(f"<{value:02X}{data[cursor + 1]:02X}>")
            cursor += 2
        elif 0x20 <= value <= 0x7E:
            parts.append(chr(value))
            cursor += 1
        else:
            parts.append(f"<{value:02X}>")
            cursor += 1
    return "".join(parts)


def find_text_terminator(
    data: bytes,
    offset: int,
    max_scan: int = 260,
) -> int:
    """Find 0x0D while treating the low byte of B0-BF xx as payload."""
    cursor = offset
    limit = min(len(data), offset + max_scan)
    while cursor < limit:
        value = data[cursor]
        if 0xB0 <= value <= 0xBF and cursor + 1 < limit:
            cursor += 2
        elif value == 0x0D:
            return cursor
        else:
            cursor += 1
    return -1


def has_text_terminator(data: bytes, offset: int, max_scan: int = 260) -> bool:
    return find_text_terminator(data, offset, max_scan) >= 0


def has_source_record_terminator(
    data: bytes,
    offset: int,
    source_length: int,
) -> bool:
    """Verify the exact canonical 0x0D immediately after a source payload."""
    terminator = offset + source_length
    return (
        source_length > 0
        and terminator < len(data)
        and data[terminator] == 0x0D
    )


def likely_text_pointer_target(data: bytes, offset: int | None) -> bool:
    if offset is None or offset < 16 or offset >= len(data):
        return False
    if not (0x20 <= data[offset] <= 0x7E):
        return False
    end = find_text_terminator(data, offset, 260)
    if end < 0:
        return False
    block = data[offset:end]
    if len(block) < 3:
        return False
    printable = sum(1 for value in block if 0x20 <= value <= 0x7E)
    letters = sum(1 for value in block if 65 <= value <= 90 or 97 <= value <= 122)
    return printable / len(block) > 0.95 and letters >= 2


def known_source_target_offsets(
    data: bytes,
    source_ranges: Iterable[tuple[int, int]],
) -> set[int]:
    """Return exact starts plus starts after reviewed control/space padding."""
    targets: set[int] = set()
    for offset, length in source_ranges:
        if length < 1:
            continue
        targets.add(offset)
        delta = reviewed_text_prefix_len(data[offset:offset + length])
        if 0 < delta < length:
            targets.add(offset + delta)
    return targets


def reviewed_text_prefix_len(data: bytes) -> int:
    """Count source control bytes and explicit padding before visible text."""
    delta = 0
    while delta < len(data) and data[delta] in (0x00, 0x0A, 0x20, 0x30):
        delta += 1
    return delta


def reviewed_control_prefix_len(data: bytes) -> int:
    """Count non-printing source padding without consuming a join space."""
    delta = 0
    while delta < len(data) and data[delta] in (0x00, 0x0A, 0x30):
        delta += 1
    return delta


def relocated_text_target(
    source: bytes,
    source_offset: int,
    source_length: int,
    translated: bytes,
    target_offset: int,
    new_offset: int,
    collapse_graphical_interior: bool = False,
    collapse_ascii_padding_interior: bool = False,
    preserve_leading_separator: bool = False,
    preserve_leading_control: bool = False,
) -> int:
    """Map a source pointer target into a relocated translated record."""
    target_delta = target_offset - source_offset
    if preserve_leading_separator:
        source_prefix = reviewed_text_prefix_len(
            source[source_offset:source_offset + source_length]
        )
        source_control_prefix = reviewed_control_prefix_len(
            source[source_offset:source_offset + source_length]
        )
        if (
            (
                target_delta == source_control_prefix
                or 0 < target_delta <= source_prefix
            )
            and translated.startswith(b" ")
        ):
            return new_offset
    if preserve_leading_control:
        source_control_prefix = reviewed_control_prefix_len(
            source[source_offset:source_offset + source_length]
        )
        if (
            target_delta == source_control_prefix
            and translated.startswith(b"\x0A")
        ):
            return new_offset
    if collapse_ascii_padding_interior and target_delta > 0:
        source_control_prefix = reviewed_control_prefix_len(
            source[source_offset:source_offset + source_length]
        )
        if target_delta == source_control_prefix:
            return new_offset + reviewed_control_prefix_len(translated)
    if collapse_graphical_interior and target_delta > 0:
        return new_offset + reviewed_text_prefix_len(translated)
    source_prefix_len = reviewed_text_prefix_len(
        source[source_offset:source_offset + source_length]
    )
    if source_prefix_len > 0 and target_delta == source_prefix_len:
        target_delta = reviewed_text_prefix_len(translated)
    return new_offset + target_delta


def graphical_pointer_target_conflicts(
    row_pointer_refs: dict[int, list[tuple[int, list[int]]]],
    graphical_starts: set[int],
) -> list[str]:
    """Reject one translated graphic being used for distinct live targets.

    A graphical source record may contain obsolete prefixes or several
    historical submessages.  Collapsing an interior pointer is safe only
    when the English base still references one distinct target in that
    record; otherwise one French string could silently replace several
    different messages.
    """
    conflicts: list[str] = []
    for source_offset in sorted(graphical_starts):
        live_targets = sorted(
            {
                target
                for target, refs in row_pointer_refs.get(source_offset, [])
                if refs
            }
        )
        if len(live_targets) > 1:
            conflicts.append(
                f"GRAPHICAL RECORD 0x{source_offset:06X}: "
                "multiple active targets "
                + ", ".join(
                    f"0x{target:06X}" for target in live_targets
                )
            )
    return conflicts


def assign_pointer_targets_to_rows(
    row_info: Iterable[tuple[TranslationRow, int, bytes]],
    pointer_entries: dict[int, list[int]],
) -> dict[int, list[tuple[int, list[int]]]]:
    """Assign every live target to its most specific translation row.

    Some canonical ASCII records deliberately expose a second pointer in
    their payload.  Those submessages now have their own translation row.
    An exact row start must therefore win over an older enclosing record;
    otherwise the builder would preserve the obsolete source-byte delta and
    could start the French text in the middle of a word.
    """
    rows = tuple(row_info)
    result: dict[int, list[tuple[int, list[int]]]] = {
        row.offset: []
        for row, _, _ in rows
    }
    for target_offset, refs in pointer_entries.items():
        owners = [
            (row, max_len)
            for row, max_len, _ in rows
            if (
                max_len > 0
                and row.offset <= target_offset < row.offset + max_len
            )
        ]
        if not owners:
            continue
        exact = [
            item
            for item in owners
            if item[0].offset == target_offset
        ]
        owner, _ = min(
            exact or owners,
            key=lambda item: (item[1], -item[0].offset),
        )
        result[owner.offset].append((target_offset, refs))
    return result


def prepare_pointer_variant_payloads(
    data: bytes,
    row_info: Iterable[tuple[TranslationRow, int, bytes]],
    row_pointer_refs: dict[int, list[tuple[int, list[int]]]],
    variants_by_main: Mapping[int, tuple[PointerVariant, ...]],
    restoration_refs: Iterable[int] = (),
    *,
    text_profile: TextProfile | None = None,
) -> dict[int, bytes]:
    """Validate, detach and encode the four secondary EN pointer variants.

    The returned dictionary uses each secondary pointer slot as a synthetic
    allocator key.  A slot and its original MAIN record live in the same PRG
    pair, so the ordinary pair-aware allocator cannot place its payload in an
    unreachable bank.
    """
    profile = resolve_text_profile(text_profile)
    if profile is FRENCH_TEXT_PROFILE:
        raise ValueError(
            'Pointer variants require the en-US profile'
        )

    rows = tuple(row_info)
    info_by_offset = {
        row.offset: (row, max_len, encoded)
        for row, max_len, encoded in rows
    }
    actual_groups = {
        main_offset: tuple(
            variant.pointer_reference
            for variant in variants
        )
        for main_offset, variants in variants_by_main.items()
    }
    if actual_groups != EXPECTED_POINTER_VARIANT_REFERENCES:
        raise ValueError(
            'In-memory variant topology differs from the seven canonical slots'
        )

    all_variant_refs = {
        variant.pointer_reference
        for variants in variants_by_main.values()
        for variant in variants
    }
    restored = set(restoration_refs)
    translated_offsets = set(info_by_offset)
    restoration_collisions = sorted(all_variant_refs & restored)
    offset_collisions = sorted(all_variant_refs & translated_offsets)
    if restoration_collisions or offset_collisions:
        details: list[str] = []
        if restoration_collisions:
            details.append(
                "restorations "
                + ", ".join(
                    f"0x{offset:06X}"
                    for offset in restoration_collisions
                )
            )
        if offset_collisions:
            details.append(
                "MAIN offsets "
                + ", ".join(
                    f"0x{offset:06X}" for offset in offset_collisions
                )
            )
        raise ValueError(
            "synthetic variant key collision with "
            + "; ".join(details)
        )

    encoded_by_ref: dict[int, bytes] = {}
    pointer_owners: dict[int, tuple[int, int, list[int]]] = {}
    for owner_offset, targets in row_pointer_refs.items():
        for target_offset, refs in targets:
            for ref in refs:
                if ref in all_variant_refs:
                    if ref in pointer_owners:
                        raise ValueError(
                            f"variant slot 0x{ref:06X} has two owners"
                        )
                    pointer_owners[ref] = (
                        owner_offset,
                        target_offset,
                        refs,
                    )

    for main_offset, variants in variants_by_main.items():
        info = info_by_offset.get(main_offset)
        if info is None:
            raise ValueError(
                f"missing variant MAIN row 0x{main_offset:06X}"
            )
        row, max_len, main_payload = info
        if max_len < 1:
            raise ValueError(
                f'Variant MAIN row has no source at 0x{main_offset:06X}'
            )
        source_prefix = reviewed_text_prefix_len(
            data[main_offset:main_offset + max_len]
        )
        expected_live_target = main_offset + source_prefix

        group_payloads: list[bytes] = []
        for variant in variants:
            ref = variant.pointer_reference
            if variant.main_offset != main_offset:
                raise ValueError(
                    f"{variant.variant_key}: inconsistent MAIN owner"
                )
            if variant.shared_source_target != main_offset:
                raise ValueError(
                    f"{variant.variant_key}: inconsistent source target"
                )
            if ref < INES_HEADER_SIZE or ref + 2 > len(data):
                raise ValueError(
                    f"{variant.variant_key}: slot outside ROM"
                )
            if pair_for_offset(ref) != pair_for_offset(main_offset):
                raise ValueError(
                    f'{variant.variant_key}: slot and MAIN belong to different PRG pairs'
                )
            actual_address = int.from_bytes(data[ref:ref + 2], "little")
            actual_target = offset_for_cpu_addr(
                pair_for_offset(ref),
                actual_address,
                len(data),
            )
            source_alignment = (
                VERIFIED_SOURCE_ALIGNMENT_POINTER_REDIRECTS.get(ref)
            )
            expected_source_target = (
                source_alignment[0]
                if source_alignment is not None
                else expected_live_target
            )
            if (
                source_alignment is not None
                and source_alignment[1] != expected_live_target
            ):
                raise ValueError(
                    f"{variant.variant_key}: reviewed owner "
                    f"0x{source_alignment[1]:06X} instead of "
                    f"0x{expected_live_target:06X}"
                )
            if actual_target != expected_source_target:
                raise ValueError(
                    f"{variant.variant_key}: English source target "
                    f"0x{(actual_target or 0):06X} instead of "
                    f"0x{expected_source_target:06X}"
                )

            owner = pointer_owners.get(ref)
            if owner is None:
                raise ValueError(
                    f'{variant.variant_key}: slot missing from row_pointer_refs'
                )
            owner_offset, owned_target, _ = owner
            if (
                owner_offset != main_offset
                or owned_target != expected_live_target
            ):
                raise ValueError(
                    f"{variant.variant_key}: detected owner "
                    f"0x{owner_offset:06X}/0x{owned_target:06X} instead of "
                    f"0x{main_offset:06X}/0x{expected_live_target:06X}"
                )

            conflicts = profile_literal_slot_conflicts(
                variant.text,
                text_profile=profile,
            )
            if conflicts:
                raise ValueError(
                    f"{variant.variant_key}: reserved punctuation "
                    + " ".join(
                        repr(item) for item in sorted(conflicts)
                    )
                )
            try:
                payload = format_profile_text(
                    variant.text,
                    row.layout,
                    text_profile=profile,
                )
            except (TypeError, ValueError, UnicodeError) as exc:
                raise ValueError(
                    f'{variant.variant_key}: invalid english_v2: {exc}'
                ) from exc
            if (
                ref in SEMANTIC_LEADING_SEPARATOR_POINTER_REFS
                and not payload.startswith(b" ")
            ):
                raise ValueError(
                    f"{variant.variant_key}: leading join space "
                    "required"
                )
            group_payloads.append(payload)
            encoded_by_ref[ref] = payload

        if group_payloads[0] != main_payload:
            raise ValueError(
                f'{variants[0].variant_key}: first variant must match MAIN payload 0x{main_offset:06X}'
            )

    secondary_refs = {
        variant.pointer_reference
        for variants in variants_by_main.values()
        for variant in variants[1:]
    }
    if len(secondary_refs) != EXPECTED_SECONDARY_POINTER_VARIANT_COUNT:
        raise ValueError(
            f"{len(secondary_refs)} secondary variant slots, "
            f"{EXPECTED_SECONDARY_POINTER_VARIANT_COUNT} expected"
        )

    # Mutate only after every CSV, source-target and ownership check passes.
    for ref in sorted(secondary_refs):
        _, _, owner_refs = pointer_owners[ref]
        owner_refs.remove(ref)

    return {
        ref: encoded_by_ref[ref]
        for ref in sorted(secondary_refs)
    }


def detect_pointer_table_entries(
    data: bytes,
    min_run: int = 10,
    known_offsets: set[int] | None = None,
    min_known_ratio: float = 0.0,
    min_known_count: int = 0,
) -> dict[int, list[int]]:
    """Return {target_file_offset: [pointer_file_offsets]} for table-like pointer runs."""
    entries: dict[int, list[int]] = {}
    pair_count = (len(data) - 16 + 0x7FFF) // 0x8000

    for pair in range(pair_count):
        start = 16 + pair * 0x8000
        end = min(len(data), start + 0x8000)
        cursor = start
        while cursor < end - 1:
            probe = cursor
            targets: list[tuple[int, int]] = []
            while probe < end - 1:
                address = int.from_bytes(data[probe:probe + 2], "little")
                target = offset_for_cpu_addr(pair, address, len(data))
                known_target = (
                    target is not None
                    and known_offsets is not None
                    and target in known_offsets
                )
                if known_target or likely_text_pointer_target(data, target):
                    targets.append((probe, target))
                    probe += 2
                else:
                    break

            if len(targets) >= min_run:
                if known_offsets is not None:
                    known_count = sum(1 for _, target in targets if target in known_offsets)
                    known_ratio = known_count / len(targets)
                    if known_count < min_known_count or known_ratio < min_known_ratio:
                        cursor += 1
                        continue
                for pointer_offset, target in targets:
                    entries.setdefault(target, []).append(pointer_offset)
                cursor = probe
            else:
                cursor += 1

    return entries


def build_pointer_value_index(data: bytes) -> list[dict[int, list[int]]]:
    pair_count = (len(data) - 16 + 0x7FFF) // 0x8000
    by_pair: list[dict[int, list[int]]] = []
    for pair in range(pair_count):
        start = 16 + pair * 0x8000
        end = min(len(data), start + 0x8000)
        values: dict[int, list[int]] = {}
        for offset in range(start, end - 1):
            value = int.from_bytes(data[offset:offset + 2], "little")
            values.setdefault(value, []).append(offset)
        by_pair.append(values)
    return by_pair


def pointer_context_count(data: bytes, pointer_offset: int, pair: int, window: int) -> int:
    pair_start = 16 + pair * 0x8000
    pair_end = min(len(data), pair_start + 0x8000)
    start = max(pair_start, pointer_offset - window)
    end = min(pair_end - 1, pointer_offset + window + 2)

    # Tables may start on either byte parity. Once we have a candidate pointer,
    # nearby table entries should usually keep that same parity.
    if (start - pointer_offset) % 2:
        start += 1

    count = 0
    for offset in range(start, end, 2):
        address = int.from_bytes(data[offset:offset + 2], "little")
        target = offset_for_cpu_addr(pair, address, len(data))
        if likely_text_pointer_target(data, target):
            count += 1
    return count


def detect_contextual_pointer_entries(
    data: bytes,
    target_offsets: set[int],
    window: int = 32,
    min_context_count: int = 5,
) -> dict[int, list[int]]:
    value_index = build_pointer_value_index(data)
    entries: dict[int, list[int]] = {}

    for target in sorted(target_offsets):
        pair = pair_for_offset(target)
        if pair < 0 or pair >= len(value_index):
            continue
        address = cpu_addr_for_offset(target)
        for pointer_offset in value_index[pair].get(address, []):
            if pointer_context_count(data, pointer_offset, pair, window) >= min_context_count:
                entries.setdefault(target, []).append(pointer_offset)

    return entries


def merge_non_overlapping_pointer_entries(
    base_entries: dict[int, list[int]],
    extra_entries: dict[int, list[int]],
) -> tuple[dict[int, list[int]], list[tuple[int, int, int]]]:
    """Merge pointer refs while rejecting refs that overlap an existing 16-bit ref."""
    merged = {target: sorted(set(refs)) for target, refs in base_entries.items()}
    owner_by_ref = {
        ref: target
        for target, refs in merged.items()
        for ref in refs
    }
    occupied_refs = sorted(owner_by_ref)
    skipped: list[tuple[int, int, int]] = []

    for target in sorted(extra_entries):
        for ref in sorted(set(extra_entries[target])):
            existing_target = owner_by_ref.get(ref)
            if existing_target is not None:
                if existing_target != target:
                    skipped.append((target, ref, ref))
                continue

            overlap = next(
                (occupied for occupied in occupied_refs if ref < occupied + 2 and occupied < ref + 2),
                None,
            )
            if overlap is not None:
                skipped.append((target, ref, overlap))
                continue

            merged.setdefault(target, []).append(ref)
            owner_by_ref[ref] = target
            occupied_refs.append(ref)

    for refs in merged.values():
        refs.sort()
    return merged, skipped


def verified_pointer_override_entries(data: bytes) -> dict[int, list[int]]:
    """Return the curated pointer refs after checking every source word."""
    entries: dict[int, list[int]] = {}
    for target, refs in VERIFIED_POINTER_OVERRIDES.items():
        target_pair = pair_for_offset(target)
        target_address = cpu_addr_for_offset(target)
        for ref in refs:
            if pair_for_offset(ref) != target_pair:
                raise ValueError(
                    f'Verified pointer 0x{ref:06X} and target 0x{target:06X} belong to different banks'
                )
            actual_address = int.from_bytes(data[ref:ref + 2], "little")
            if actual_address != target_address:
                raise ValueError(
                    f"verified pointer 0x{ref:06X}: "
                    f"0x{actual_address:04X} instead of 0x{target_address:04X}"
                )
            entries.setdefault(target, []).append(ref)
    return entries


def verified_field_dialogue_pointer_entries(
    data: bytes,
) -> dict[int, list[int]]:
    """Return every exact overworld/NPC table slot and its PRG target."""
    entries: dict[int, list[int]] = {}
    slot_count = 0
    seen_refs: set[int] = set()
    for first, last in VERIFIED_FIELD_DIALOGUE_POINTER_RANGES:
        if first > last or (last - first) % 2:
            raise ValueError(
                f'Invalid field pointer range: 0x{first:06X}-0x{last:06X}'
            )
        pair = pair_for_offset(first)
        if pair_for_offset(last) != pair:
            raise ValueError(
                f'Field pointer range crosses a PRG pair: 0x{first:06X}-0x{last:06X}'
            )
        for ref in range(first, last + 1, 2):
            if ref in seen_refs:
                raise ValueError(
                    f"duplicate field slot: 0x{ref:06X}"
                )
            seen_refs.add(ref)
            address = int.from_bytes(data[ref:ref + 2], "little")
            target = offset_for_cpu_addr(pair, address, len(data))
            if target is None:
                raise ValueError(
                    f'Field slot 0x{ref:06X}: CPU address 0x{address:04X} outside the PRG window'
                )
            entries.setdefault(target, []).append(ref)
            slot_count += 1

    if slot_count != VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT:
        raise ValueError(
            f"{slot_count} field slots, "
            f"{VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT} expected"
        )
    for refs in entries.values():
        refs.sort()
    return entries


def remove_verified_non_dialogue_pointer_refs(
    data: bytes,
    entries: dict[int, list[int]],
) -> dict[int, list[int]]:
    """Remove exact dummy words that must never follow relocated text."""
    filtered = {
        target: sorted(set(refs))
        for target, refs in entries.items()
    }
    for ref, expected_target in sorted(
        VERIFIED_NON_DIALOGUE_POINTER_REFS.items()
    ):
        pair = pair_for_offset(ref)
        address = int.from_bytes(data[ref:ref + 2], "little")
        actual_target = offset_for_cpu_addr(
            pair,
            address,
            len(data),
        )
        if actual_target != expected_target:
            raise ValueError(
                f"verified sentinel 0x{ref:06X}: target "
                f"0x{(actual_target or 0):06X} instead of "
                f"0x{expected_target:06X}"
            )
        owners = [
            target
            for target, refs in filtered.items()
            if ref in refs
        ]
        if len(owners) > 1 or (
            owners and owners != [expected_target]
        ):
            raise ValueError(
                f"verified sentinel 0x{ref:06X}: owner "
                f"unexpected {owners!r}"
            )
        if not owners:
            continue
        filtered[expected_target].remove(ref)
        if not filtered[expected_target]:
            del filtered[expected_target]
    return filtered


def apply_verified_pointer_redirects(
    data: bytes,
    entries: dict[int, list[int]],
) -> dict[int, list[int]]:
    """Redirect reviewed bad English refs before assigning translation rows."""
    redirected = {
        target: sorted(set(refs))
        for target, refs in entries.items()
    }
    for ref, (expected_target, replacement_target) in sorted(
        VERIFIED_POINTER_REDIRECTS.items()
    ):
        pair = pair_for_offset(ref)
        actual_address = int.from_bytes(data[ref:ref + 2], "little")
        actual_target = offset_for_cpu_addr(
            pair,
            actual_address,
            len(data),
        )
        if actual_target != expected_target:
            raise ValueError(
                f"verified redirect 0x{ref:06X}: target "
                f"0x{(actual_target or 0):06X} instead of "
                f"0x{expected_target:06X}"
            )
        owners = [
            target
            for target, refs in redirected.items()
            if ref in refs
        ]
        if owners != [expected_target]:
            raise ValueError(
                f"verified redirect 0x{ref:06X}: owner "
                f"unexpected {owners!r}"
            )
        redirected[expected_target].remove(ref)
        if not redirected[expected_target]:
            del redirected[expected_target]
        redirected.setdefault(replacement_target, []).append(ref)

    for refs in redirected.values():
        refs.sort()
    return redirected


def apply_verified_source_alignment_pointer_redirects(
    data: bytes,
    entries: dict[int, list[int]],
) -> dict[int, list[int]]:
    """Repair reviewed English-table ownership before row assignment."""
    redirected = {
        target: sorted(set(refs))
        for target, refs in entries.items()
    }
    for ref, (observed_target, reviewed_target) in sorted(
        VERIFIED_SOURCE_ALIGNMENT_POINTER_REDIRECTS.items()
    ):
        actual_target = offset_for_cpu_addr(
            pair_for_offset(ref),
            int.from_bytes(data[ref:ref + 2], "little"),
            len(data),
        )
        if actual_target != observed_target:
            raise ValueError(
                f"verified source alignment 0x{ref:06X}: target "
                f"0x{(actual_target or 0):06X} instead of "
                f"0x{observed_target:06X}"
            )
        owners = [
            target
            for target, refs in redirected.items()
            if ref in refs
        ]
        if owners not in ([], [observed_target]):
            raise ValueError(
                f"verified source alignment 0x{ref:06X}: owner "
                f"unexpected {owners!r}"
            )
        if owners:
            redirected[observed_target].remove(ref)
            if not redirected[observed_target]:
                del redirected[observed_target]
        redirected.setdefault(reviewed_target, []).append(ref)

    for refs in redirected.values():
        refs.sort()
    return redirected


def _load_french_restoration_texts() -> Mapping[int, str]:
    """Load French payloads lazily so an EN build never imports them."""
    from tools.chinese_dialogue_restorations import RESTORED_DIALOGUES

    return RESTORED_DIALOGUES


def verified_dialogue_restoration_payloads(
    data: bytes,
    restoration_texts: Mapping[int, str] | None = None,
    *,
    text_profile: TextProfile | None = None,
) -> dict[int, bytes]:
    """Encode and validate the 85 locale-specific restoration payloads.

    Existing callers remain French by default.  An English caller must inject
    its complete catalogue explicitly; silently falling back to French text is
    forbidden.
    """
    profile = resolve_text_profile(text_profile)
    if restoration_texts is None:
        if profile is not FRENCH_TEXT_PROFILE:
            raise ValueError(
                "the en-US profile requires a catalogue of 85 restorations"
            )
        restoration_texts = _load_french_restoration_texts()
    validate_restoration_catalogue(
        restoration_texts,
        label=f"restorations {profile.locale}",
    )

    payloads: dict[int, bytes] = {}
    errors: list[str] = []

    for ref, text in sorted(restoration_texts.items()):
        if ref < INES_HEADER_SIZE or ref + 2 > len(data):
            errors.append(f"RESTORED SLOT OUTSIDE ROM 0x{ref:06X}")
            continue

        pair = pair_for_offset(ref)
        actual_address = int.from_bytes(data[ref:ref + 2], "little")
        actual_target = offset_for_cpu_addr(
            pair,
            actual_address,
            len(data),
        )
        slot = RESTORATION_TOPOLOGY[ref]
        if slot.kind is RestorationKind.COLLAPSED:
            if actual_target != slot.observed_english_target:
                errors.append(
                    f"COLLAPSED SLOT 0x{ref:06X}: target "
                    f"0x{(actual_target or 0):06X} instead of "
                    f"0x{slot.observed_english_target:06X}"
                )
        elif slot.kind is RestorationKind.REMOVED:
            if actual_target is not None:
                errors.append(
                    f"REMOVED SLOT 0x{ref:06X}: English target "
                    f"unexpected 0x{actual_target:06X}"
                )
        elif actual_target != slot.observed_english_target:
            errors.append(
                f"MISWIRED SLOT 0x{ref:06X}: target "
                f"0x{(actual_target or 0):06X} instead of "
                f"0x{slot.observed_english_target:06X}"
            )

        conflicts = profile_literal_slot_conflicts(
            text,
            text_profile=profile,
        )
        if conflicts:
            errors.append(
                f"RESERVED RESTORATION PUNCTUATION 0x{ref:06X}: "
                + " ".join(repr(item) for item in sorted(conflicts))
            )
            continue

        try:
            encoded = format_profile_text(
                text,
                DIALOGUE_LAYOUT,
                text_profile=profile,
            )
        except (TypeError, ValueError, UnicodeError) as exc:
            errors.append(
                f"RESTORATION ENCODING 0x{ref:06X}: {exc}"
            )
            continue
        if any(
            (value < 0x20 or value > 0x7E)
            and value not in profile.renderer_control_bytes
            for value in encoded
        ):
            errors.append(
                f'NONPRINTABLE RESTORED TEXT 0x{ref:06X}'
            )
            continue
        payloads[ref] = encoded

    if errors:
        raise ValueError(
            "invalid Chinese restorations:\n  "
            + "\n  ".join(errors)
        )
    return payloads


def subtract_protected_spans(
    start: int,
    end: int,
    protected: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    spans = [(start, end)]
    for protected_start, protected_end in protected:
        next_spans: list[tuple[int, int]] = []
        for span_start, span_end in spans:
            if protected_end <= span_start or protected_start >= span_end:
                next_spans.append((span_start, span_end))
                continue
            if span_start < protected_start:
                next_spans.append((span_start, protected_start))
            if protected_end < span_end:
                next_spans.append((protected_end, span_end))
        spans = next_spans
    return spans


def find_free_spans(
    data: bytes,
    protected: list[tuple[int, int]],
    min_len: int = 32,
    fill_values: tuple[int, ...] = (0x30, 0xFF, 0x00),
) -> dict[int, list[FreeSpan]]:
    protected = sorted(protected)
    spans_by_pair: dict[int, list[FreeSpan]] = {}
    pair_count = (len(data) - 16 + 0x7FFF) // 0x8000

    for pair in range(pair_count):
        start = 16 + pair * 0x8000
        end = min(len(data), start + 0x8000)
        spans: list[FreeSpan] = []
        cursor = start
        while cursor < end:
            if data[cursor] not in fill_values:
                cursor += 1
                continue
            value = data[cursor]
            run_start = cursor
            while cursor < end and data[cursor] == value:
                cursor += 1
            run_end = cursor
            if run_end - run_start < min_len:
                continue
            for free_start, free_end in subtract_protected_spans(run_start, run_end, protected):
                if free_end - free_start >= min_len:
                    spans.append(FreeSpan(free_start, free_end - free_start))
        spans_by_pair[pair] = sorted(spans, key=lambda span: (span.start, span.length))

    return spans_by_pair


def find_text_free_spans(
    data: bytes,
    protected: list[tuple[int, int]],
    min_len: int = DEFAULT_MIN_FREE_RUN,
    arena_ranges: tuple[tuple[int, int], ...] = VERIFIED_TEXT_PADDING_ARENAS,
    micro_arena_ranges: tuple[
        tuple[int, int], ...
    ] = VERIFIED_TEXT_MICRO_ARENAS,
) -> dict[int, list[FreeSpan]]:
    """
    Find only padding arenas that are safe for translated text.

    The English patch reserves text space with long runs of ASCII ``0``
    (0x30) immediately after a 0x0D terminator. Only the reviewed ranges in
    ``arena_ranges`` are accepted: short runs and newly discovered runs are
    not inferred as free. Protected ranges are subtracted before an arena is
    returned.
    """
    protected = sorted(protected)
    spans_by_pair: dict[int, list[FreeSpan]] = {}
    pair_count = (len(data) - 16 + 0x7FFF) // 0x8000
    min_len = max(min_len, DEFAULT_MIN_FREE_RUN)

    for pair in range(pair_count):
        pair_start = 16 + pair * 0x8000
        pair_end = min(len(data), pair_start + 0x8000)
        spans: list[FreeSpan] = []

        reviewed_arenas = (
            *((start, end, min_len) for start, end in arena_ranges),
            *((start, end, 1) for start, end in micro_arena_ranges),
        )
        for run_start, run_end, required_len in reviewed_arenas:
            if run_start < pair_start or run_end > pair_end:
                continue
            if run_end <= run_start:
                raise ValueError(
                    f'Invalid text arena: 0x{run_start:06X}-0x{run_end:06X}'
                )
            if (
                run_start <= pair_start
                or data[run_start - 1] != SAFE_TEXT_FILL_PREFIX
                or any(
                    value != SAFE_TEXT_FILL_VALUE
                    for value in data[run_start:run_end]
                )
            ):
                raise ValueError(
                    f'Text arena differs from the canonical base: 0x{run_start:06X}-0x{run_end:06X}'
                )

            for free_start, free_end in subtract_protected_spans(
                run_start,
                run_end,
                protected,
            ):
                if free_end - free_start >= required_len:
                    spans.append(FreeSpan(free_start, free_end - free_start))

        spans_by_pair[pair] = sorted(
            spans,
            key=lambda span: (span.start, span.length),
        )

    return spans_by_pair


def allocate_from_pair(spans_by_pair: dict[int, list[FreeSpan]], pair: int, size: int) -> int | None:
    spans = spans_by_pair.get(pair, [])
    for index, span in enumerate(spans):
        if span.length >= size:
            offset = span.start
            span.start += size
            span.length -= size
            if span.length == 0:
                spans.pop(index)
            return offset
    return None


def merge_free_spans(spans: Iterable[FreeSpan]) -> list[FreeSpan]:
    ranges = sorted((span.start, span.start + span.length) for span in spans if span.length > 0)
    merged: list[list[int]] = []
    for start, end in ranges:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [FreeSpan(start, end - start) for start, end in merged]


def allocate_best_fit(spans_by_pair: dict[int, list[FreeSpan]], pair: int, size: int) -> int | None:
    spans = spans_by_pair.get(pair, [])
    best_index: int | None = None
    best_key: tuple[int, int] | None = None
    for index, span in enumerate(spans):
        if span.length < size:
            continue
        candidate_key = (span.length, span.start)
        if best_key is None or candidate_key < best_key:
            best_index = index
            best_key = candidate_key

    if best_index is None:
        return None

    span = spans[best_index]
    offset = span.start
    span.start += size
    span.length -= size
    if span.length == 0:
        spans.pop(best_index)
    return offset


def _maximum_fitting_subset(
    roots: list[bytes],
    capacity: int,
) -> list[bytes]:
    """Return a deterministic subset whose terminated size is maximal.

    The bitset records every reachable byte count, while ``previous_root``
    and ``previous_sum`` retain just enough information to reconstruct one
    subset.  A root is considered at most once.  Iterating roots in their
    canonical order makes ties independent from dictionaries, sets and
    ``PYTHONHASHSEED``.
    """
    if capacity <= 0 or not roots:
        return []
    if sum(len(root) + 1 for root in roots) <= capacity:
        return list(roots)

    reachable = 1
    mask = (1 << (capacity + 1)) - 1
    previous_root = [-1] * (capacity + 1)
    previous_sum = [-1] * (capacity + 1)

    for root_index, root in enumerate(roots):
        size = len(root) + 1
        shifted = (reachable << size) & mask
        newly_reachable = shifted & ~reachable
        while newly_reachable:
            lowest_bit = newly_reachable & -newly_reachable
            total = lowest_bit.bit_length() - 1
            previous_root[total] = root_index
            previous_sum[total] = total - size
            newly_reachable ^= lowest_bit
        reachable |= shifted
        if reachable & (1 << capacity):
            break

    total = reachable.bit_length() - 1
    selected_indices: list[int] = []
    while total:
        root_index = previous_root[total]
        if root_index < 0:
            raise AssertionError(
                "internal subset reconstruction failed"
            )
        selected_indices.append(root_index)
        total = previous_sum[total]
    selected_indices.reverse()
    return [roots[index] for index in selected_indices]


def _allocate_roots_tight_fit(
    spans: list[FreeSpan],
    roots: list[bytes],
) -> tuple[dict[bytes, int], list[bytes], list[FreeSpan]]:
    """Pack roots, with an exact deterministic fallback when needed.

    Calling :func:`allocate_best_fit` once per root is a best-fit-decreasing
    heuristic.  It can strand the final short roots even when the total free
    capacity is sufficient.  The fast first pass gives each constrained span
    a maximum-sum subset.  That pass is still not globally complete: a locally
    full span can consume the only item combination needed by a later span.
    If it strands anything, a memoized exact bin-packing search restarts from
    the original inventory.  Thus a reported failure means no full placement
    exists, rather than merely that the heuristic chose poorly.
    """
    remaining = sorted(roots, key=lambda value: (-len(value), value))
    theoretical_free = sum(span.length for span in spans) - sum(
        len(root) + 1 for root in roots
    )
    unavoidable_single_item_waste = _minimum_single_item_span_waste(
        spans,
        roots,
    )
    root_offsets: dict[bytes, int] = {}
    residual_spans: list[FreeSpan] = []
    sorted_spans = sorted(
        spans,
        key=lambda value: (value.length, value.start),
    )
    roots_by_span: list[list[bytes]] = []

    for span in sorted_spans:
        selected = _maximum_fitting_subset(remaining, span.length)
        roots_by_span.append(list(selected))
        selected_set = set(selected)
        remaining = [
            root
            for root in remaining
            if root not in selected_set
        ]

        cursor = span.start
        for root in sorted(
            selected,
            key=lambda value: (-len(value), value),
        ):
            root_offsets[root] = cursor
            cursor += len(root) + 1
        residual_length = span.start + span.length - cursor
        if residual_length:
            residual_spans.append(FreeSpan(cursor, residual_length))

    residual_spans.sort(key=lambda span: (span.start, span.length))
    if not remaining:
        return root_offsets, remaining, residual_spans
    if theoretical_free < unavoidable_single_item_waste:
        # A cheap proof of impossibility avoids an exponential exact search.
        # The partial heuristic result still identifies the first stranded
        # root and preserves useful capacity diagnostics for the caller.
        return root_offsets, remaining, residual_spans

    repaired_assignment = _repair_local_root_partition(
        sorted_spans,
        roots_by_span,
        remaining,
    )
    if repaired_assignment is not None:
        return _render_root_assignment(sorted_spans, repaired_assignment)

    exact_assignment = _exact_root_bin_assignment(spans, roots)
    if exact_assignment is None:
        return root_offsets, remaining, residual_spans

    return _render_root_assignment(sorted_spans, exact_assignment)


def _render_root_assignment(
    sorted_spans: list[FreeSpan],
    assignment: dict[bytes, int],
) -> tuple[dict[bytes, int], list[bytes], list[FreeSpan]]:
    """Convert a root-to-span assignment into offsets and residual spans."""

    roots_by_span: list[list[bytes]] = [[] for _span in sorted_spans]
    for root, span_index in assignment.items():
        roots_by_span[span_index].append(root)
    exact_offsets: dict[bytes, int] = {}
    exact_residuals: list[FreeSpan] = []
    for span, assigned in zip(sorted_spans, roots_by_span):
        cursor = span.start
        for root in sorted(assigned, key=lambda value: (-len(value), value)):
            exact_offsets[root] = cursor
            cursor += len(root) + 1
        residual_length = span.start + span.length - cursor
        if residual_length:
            exact_residuals.append(FreeSpan(cursor, residual_length))
    exact_residuals.sort(key=lambda span: (span.start, span.length))
    return exact_offsets, [], exact_residuals


def _minimum_single_item_span_waste(
    spans: list[FreeSpan],
    roots: list[bytes],
) -> int:
    """Lower-bound waste in spans too small to hold two minimum roots.

    The bound is exact for this subset of spans: each can contain at most one
    root.  Matching the largest fitting root to each ascending capacity gives
    the maximum possible fill even when every root in the corpus is offered.
    If the corpus-wide free-byte total is below this unavoidable waste, no
    packing exists and branch-and-bound must not be attempted.
    """

    if not spans or not roots:
        return 0
    root_sizes = sorted(len(root) + 1 for root in roots)
    minimum = root_sizes[0]
    single_spans = sorted(
        span.length
        for span in spans
        if span.length < 2 * minimum
    )
    available = list(root_sizes)
    filled = 0
    for capacity in single_spans:
        fitting_index = -1
        for index, size in enumerate(available):
            if size > capacity:
                break
            fitting_index = index
        if fitting_index >= 0:
            filled += available.pop(fitting_index)
    return sum(single_spans) - filled


def _repair_local_root_partition(
    sorted_spans: list[FreeSpan],
    roots_by_span: list[list[bytes]],
    remaining: list[bytes],
    *,
    maximum_spans: int = 3,
) -> dict[bytes, int] | None:
    """Repair a heuristic conflict by exactly repacking a small span set.

    The real corpus can leave one four-byte root even though forty-plus bytes
    remain as one- and two-byte fragments.  Restarting a 1,000-item exact
    search is unnecessary: the conflict is local.  We first enumerate up to
    three spans whose combined residual capacity can absorb every stranded
    root, then solve only those items exactly.  The deterministic global exact
    fallback remains available for genuinely wider conflicts and for the
    small oracle fixtures.
    """

    if not remaining:
        return {
            root: span_index
            for span_index, assigned in enumerate(roots_by_span)
            for root in assigned
        }
    remaining_bytes = sum(len(root) + 1 for root in remaining)
    residuals = [
        span.length
        - sum(len(root) + 1 for root in assigned)
        for span, assigned in zip(sorted_spans, roots_by_span)
    ]
    all_indices = sorted(
        range(len(sorted_spans)),
        key=lambda index: (
            -residuals[index],
            len(roots_by_span[index]),
            sorted_spans[index].length,
            sorted_spans[index].start,
        ),
    )
    positive = [index for index in all_indices if residuals[index] > 0]
    zero_residual = [
        index for index in all_indices if residuals[index] == 0
    ][:32]
    ordered_indices = positive + zero_residual

    for width in range(1, min(maximum_spans, len(ordered_indices)) + 1):
        for chosen in combinations(ordered_indices, width):
            if sum(residuals[index] for index in chosen) < remaining_bytes:
                continue
            local_spans = [sorted_spans[index] for index in chosen]
            local_roots = list(remaining)
            for index in chosen:
                local_roots.extend(roots_by_span[index])
            if len(local_roots) > 64:
                continue
            local_assignment = _exact_root_bin_assignment(
                local_spans,
                local_roots,
            )
            if local_assignment is None:
                continue

            chosen_set = set(chosen)
            repaired = {
                root: span_index
                for span_index, assigned in enumerate(roots_by_span)
                if span_index not in chosen_set
                for root in assigned
            }
            for root, local_index in local_assignment.items():
                repaired[root] = chosen[local_index]
            return repaired
    return None


def _exact_root_bin_assignment(
    spans: list[FreeSpan],
    roots: list[bytes],
) -> dict[bytes, int] | None:
    """Return a complete deterministic root-to-span assignment if one exists.

    This is an exact branch-and-bound fallback for the NP-complete multiple-bin
    packing problem.  It runs only after the fast subset heuristic failed.
    Equal residual capacities are symmetry-equivalent, and failed states are
    memoized by their sorted residual-capacity multiset.
    """
    ordered_spans = sorted(spans, key=lambda value: (value.length, value.start))
    ordered_roots = sorted(roots, key=lambda value: (-len(value), value))
    if not ordered_roots:
        return {}
    capacities = [span.length for span in ordered_spans]
    sizes = [len(root) + 1 for root in ordered_roots]
    if sum(sizes) > sum(capacities) or max(sizes) > max(capacities, default=0):
        return None

    suffix_sizes = [0] * (len(sizes) + 1)
    for index in range(len(sizes) - 1, -1, -1):
        suffix_sizes[index] = suffix_sizes[index + 1] + sizes[index]

    assignment = [-1] * len(ordered_roots)
    failed_states: set[tuple[int, tuple[int, ...]]] = set()

    def search(item_index: int) -> bool:
        if item_index == len(ordered_roots):
            return True
        if suffix_sizes[item_index] > sum(capacities):
            return False
        size = sizes[item_index]
        if size > max(capacities, default=0):
            return False
        state = (item_index, tuple(sorted(capacities, reverse=True)))
        if state in failed_states:
            return False

        candidates = sorted(
            (
                (capacities[span_index] - size, ordered_spans[span_index].start, span_index)
                for span_index in range(len(capacities))
                if capacities[span_index] >= size
            )
        )
        tried_capacities: set[int] = set()
        for _residual, _start, span_index in candidates:
            capacity = capacities[span_index]
            if capacity in tried_capacities:
                continue
            tried_capacities.add(capacity)
            capacities[span_index] -= size
            assignment[item_index] = span_index
            if search(item_index + 1):
                return True
            assignment[item_index] = -1
            capacities[span_index] += size

        failed_states.add(state)
        return False

    old_recursion_limit = sys.getrecursionlimit()
    required_recursion_limit = max(old_recursion_limit, len(ordered_roots) + 200)
    try:
        if required_recursion_limit != old_recursion_limit:
            sys.setrecursionlimit(required_recursion_limit)
        if not search(0):
            return None
    finally:
        if required_recursion_limit != old_recursion_limit:
            sys.setrecursionlimit(old_recursion_limit)

    return {
        root: assignment[index]
        for index, root in enumerate(ordered_roots)
    }


def allocate_suffix_pooled(
    spans_by_pair: dict[int, list[FreeSpan]],
    payload_by_offset: dict[int, bytes],
) -> tuple[dict[int, int], list[tuple[int, int, int]]]:
    """Allocate one terminated copy for identical strings and their suffixes.

    A pointer may safely start inside another terminated string when the bytes
    from that point through the shared 0x0D are identical.  This is standard
    suffix pooling: ``Potion`` can, for example, reuse the tail of
    ``Hyper Potion``.  Pools never cross a 32 KiB PRG pair.
    """
    allocations: dict[int, int] = {}
    failures: list[tuple[int, int, int]] = []
    offsets_by_pair: dict[int, list[int]] = {}
    for source_offset in payload_by_offset:
        offsets_by_pair.setdefault(
            pair_for_offset(source_offset),
            [],
        ).append(source_offset)

    for pair in sorted(offsets_by_pair):
        offsets = sorted(offsets_by_pair[pair])
        offsets_by_payload: dict[bytes, list[int]] = {}
        for source_offset in offsets:
            payload = payload_by_offset[source_offset]
            offsets_by_payload.setdefault(payload, []).append(source_offset)

        roots: list[bytes] = []
        host_by_payload: dict[bytes, bytes] = {}
        for payload in sorted(
            offsets_by_payload,
            key=lambda value: (-len(value), value),
        ):
            hosts = [root for root in roots if root.endswith(payload)]
            if hosts:
                host_by_payload[payload] = min(
                    hosts,
                    key=lambda value: (len(value), value),
                )
            else:
                roots.append(payload)
                host_by_payload[payload] = payload

        root_offsets, unallocated_roots, residual_spans = (
            _allocate_roots_tight_fit(
                spans_by_pair.get(pair, []),
                roots,
            )
        )
        spans_by_pair[pair] = residual_spans
        failed_roots = set(unallocated_roots)

        for payload, source_offsets in offsets_by_payload.items():
            host = host_by_payload[payload]
            if host in failed_roots:
                failures.extend(
                    (source_offset, len(payload) + 1, pair)
                    for source_offset in source_offsets
                )
                continue
            payload_offset = (
                root_offsets[host] + len(host) - len(payload)
            )
            for source_offset in source_offsets:
                allocations[source_offset] = payload_offset

    return allocations, failures


def allocation_report_rows(
    *,
    allocation_payloads: Mapping[int, bytes],
    allocations: Mapping[int, int],
    main_offsets: set[int],
    restoration_offsets: set[int],
    pointer_variant_offsets: set[int],
    pointer_counts: Mapping[int, int],
) -> list[dict[str, str | int]]:
    """Describe logical allocations and their physical suffix pooling.

    ``physical_bytes`` is charged exactly once for each stored terminated
    root.  Identical payloads and suffixes still receive their own logical row
    but name the deterministic root that owns their bytes.
    """

    grouped_by_end: dict[int, list[int]] = {}
    for source_offset, target_offset in allocations.items():
        payload = allocation_payloads[source_offset]
        grouped_by_end.setdefault(
            target_offset + len(payload) + 1,
            [],
        ).append(source_offset)

    host_by_source: dict[int, int] = {}
    for sources in grouped_by_end.values():
        host = min(
            sources,
            key=lambda source: (
                allocations[source],
                -len(allocation_payloads[source]),
                source,
            ),
        )
        for source in sources:
            host_by_source[source] = host

    rows: list[dict[str, str | int]] = []
    for source_offset in sorted(allocations):
        target_offset = allocations[source_offset]
        payload = allocation_payloads[source_offset]
        host = host_by_source[source_offset]
        if source_offset in main_offsets:
            record_type = "MAIN"
            stable_key = f"MAIN:0x{source_offset:06X}"
        elif source_offset in restoration_offsets:
            record_type = "RESTORED"
            stable_key = f"RESTORED:0x{source_offset:06X}"
        elif source_offset in pointer_variant_offsets:
            record_type = "POINTER_VARIANT"
            stable_key = f"POINTER_VARIANT:0x{source_offset:06X}"
        else:
            raise AssertionError(
                f"unclassified allocation at 0x{source_offset:06X}"
            )
        rows.append(
            {
                "record_type": record_type,
                "stable_key": stable_key,
                "source_offset_hex": f"0x{source_offset:06X}",
                "source_pair": pair_for_offset(source_offset),
                "target_offset_hex": f"0x{target_offset:06X}",
                "target_pair": pair_for_offset(target_offset),
                "payload_bytes": len(payload),
                "terminated_bytes": len(payload) + 1,
                "physical_bytes": len(payload) + 1 if host == source_offset else 0,
                "pool_host_offset_hex": f"0x{host:06X}",
                "suffix_delta": target_offset - allocations[host],
                "pointer_reference_count": pointer_counts.get(
                    source_offset,
                    1,
                ),
            }
        )
    return rows


def write_allocation_report(
    path: Path,
    rows: Iterable[Mapping[str, str | int]],
) -> None:
    fields = (
        "record_type",
        "stable_key",
        "source_offset_hex",
        "source_pair",
        "target_offset_hex",
        "target_pair",
        "payload_bytes",
        "terminated_bytes",
        "physical_bytes",
        "pool_host_offset_hex",
        "suffix_delta",
        "pointer_reference_count",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_bank_budget_report(
    path: Path,
    *,
    initial_spans: Mapping[int, tuple[tuple[int, int], ...]],
    remaining_spans: Mapping[int, list[FreeSpan]],
) -> None:
    fields = (
        "prg_pair",
        "initial_free_bytes",
        "allocated_physical_bytes",
        "remaining_free_bytes",
        "initial_span_count",
        "remaining_span_count",
        "largest_remaining_span",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for pair in sorted(initial_spans):
            initial = sum(length for _start, length in initial_spans[pair])
            remaining = sum(
                span.length for span in remaining_spans.get(pair, ())
            )
            writer.writerow(
                {
                    "prg_pair": pair,
                    "initial_free_bytes": initial,
                    "allocated_physical_bytes": initial - remaining,
                    "remaining_free_bytes": remaining,
                    "initial_span_count": len(initial_spans[pair]),
                    "remaining_span_count": len(remaining_spans.get(pair, ())),
                    "largest_remaining_span": max(
                        (
                            span.length
                            for span in remaining_spans.get(pair, ())
                        ),
                        default=0,
                    ),
                }
            )


def command_check(args: argparse.Namespace) -> int:
    chinese = read_bytes(args.chinese_rom)
    canonical = read_bytes(args.english_rom)
    ips_data = read_bytes(args.english_ips)
    records, truncate = parse_ips(args.english_ips)
    rebuilt = apply_ips(chinese, records, truncate)

    print("English IPS provenance check")
    print(f'- Chinese ROM: {args.chinese_rom} ({len(chinese)} bytes, sha256 {sha256(chinese)})')
    print(
        f"- English IPS         : {args.english_ips} ({len(records)} records, "
        f"sha256 {sha256(ips_data)})"
    )
    print(f'- Canonical target: {args.english_rom} ({len(canonical)} bytes, sha256 {sha256(canonical)})')
    print(f'- Reconstruction: {len(rebuilt)} bytes, sha256 {sha256(rebuilt)}')
    print(f"- Exact reconstruction : {'YES' if rebuilt == canonical else 'NO'}")

    if args.write_yellow:
        target = ROOT / args.write_yellow
        target.write_bytes(rebuilt)
        print(f"- Reconstruction written : {target}")

    return 0 if rebuilt == canonical else 1


def command_check_ips(args: argparse.Namespace) -> int:
    base = read_bytes(args.base_rom)
    expected = read_bytes(args.target_rom)
    ips_data = read_bytes(args.ips)
    records, truncate = parse_ips(args.ips)
    rebuilt = apply_ips(base, records, truncate)
    exact = rebuilt == expected

    print("IPS round-trip validation")
    print(f'- Base ROM: {args.base_rom} ({len(base)} bytes, sha256 {sha256(base)})')
    print(
        f'- IPS: {args.ips} ({len(ips_data)} bytes, {len(records)} records, sha256 {sha256(ips_data)})'
    )
    print(f'- Target ROM: {args.target_rom} ({len(expected)} bytes, sha256 {sha256(expected)})')
    print(f'- Rebuilt ROM: {len(rebuilt)} bytes, sha256 {sha256(rebuilt)}')
    print(f"- Base + IPS == target : {'YES' if exact else 'NO'}")

    if not exact:
        common_length = min(len(rebuilt), len(expected))
        first_difference = next(
            (offset for offset in range(common_length) if rebuilt[offset] != expected[offset]),
            common_length if len(rebuilt) != len(expected) else None,
        )
        if first_difference is not None:
            print(f"- First difference       : 0x{first_difference:06X}")
        if len(rebuilt) != len(expected):
            print(f"- Different sizes : {len(rebuilt)} != {len(expected)}")

    return 0 if exact else 1


def command_dump_script(args: argparse.Namespace) -> int:
    english = read_bytes(args.english_rom)
    english_hash = sha256(english)
    if english_hash != TRANSLATION_BASE_SHA256:
        print("Script extraction: FAILED")
        print(
            "- Noncanonical English ROM : "
            f"{english_hash} instead of {TRANSLATION_BASE_SHA256}"
        )
        print('- No CSV written.')
        return 1
    glyph_records = verified_all_graphical_text_records(english)
    glyph_by_start = structured_glyph_record_map(glyph_records)
    entries = parse_patch_entries(args.script)
    output = ROOT / args.output
    fieldnames = [
        "offset_hex", "line", "layout", "max_len", "source_en", "fr_text",
        "fr_len", "overflow",
    ]
    rows: list[dict[str, str | int]] = []

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            max_len = source_record_len(
                english,
                entry.offset,
                glyph_by_start,
            )
            source = source_record_text(
                english,
                entry.offset,
                max_len,
                glyph_by_start,
            )
            encoded = format_game_text(entry.text, entry.layout)
            fr_len = len(encoded)
            row = {
                "offset_hex": f"0x{entry.offset:06X}",
                "line": entry.line,
                "layout": entry.layout,
                "max_len": max_len,
                "source_en": csv_safe(source),
                "fr_text": csv_safe(entry.text),
                "fr_len": fr_len,
                "overflow": "YES" if max_len and fr_len > max_len else "",
            }
            rows.append(row)
            writer.writerow(row)

    overflow_rows = [row for row in rows if row["overflow"] == "YES"]
    if args.overflow_output:
        overflow_output = ROOT / args.overflow_output
        with overflow_output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(overflow_rows)

    print(f"Generated CSV : {output}")
    print(f"Extracted entries : {len(entries)}")
    print(f"Texts too long : {len(overflow_rows)}")
    if args.overflow_output:
        print(f"Overflow CSV : {overflow_output}")
    return 0


def command_audit(args: argparse.Namespace) -> int:
    english = read_bytes(args.english_rom)
    french = read_bytes(args.french_rom)
    records, _ = parse_ips(args.english_ips)
    spans = changed_spans(records)
    entries = parse_patch_entries(args.script)
    scripted_offsets = {entry.offset for entry in entries}
    text_ranges = [] if args.all_ranges else [parse_range(item) for item in args.text_range]

    candidates: list[dict[str, str | int]] = []
    for match in TEXT_RE.finditer(english):
        start, end = match.span()
        if text_ranges and not inside_ranges(start, end, text_ranges):
            continue
        if args.only_english_ips and not intersects_spans(start, end, spans):
            continue

        text = decode_ascii(match.group())
        if not looks_like_text(text):
            continue

        same = french[start:end] == english[start:end]
        score = english_score(text)
        in_script = start in scripted_offsets

        if score >= args.min_english_score and (same or args.include_translated_hits):
            french_text = decode_ascii(french[start:end])
            reason = []
            if same:
                reason.append("identique_EN_FR")
            if score:
                reason.append(f"score_en={score}")
            if in_script:
                reason.append("dans_script")
            candidates.append({
                "offset": start,
                "length": end - start,
                "english": text,
                "french": french_text,
                "in_script": "YES" if in_script else "",
                "reason": ";".join(reason),
            })

    output = ROOT / args.output
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "offset_hex", "length", "reason", "in_script", "english", "french_at_same_offset",
        ])
        writer.writeheader()
        for row in candidates:
            writer.writerow({
                "offset_hex": f"0x{row['offset']:06X}",
                "length": row["length"],
                "reason": row["reason"],
                "in_script": row["in_script"],
                "english": csv_safe(str(row["english"])),
                "french_at_same_offset": csv_safe(str(row["french"])),
            })

    exact_left = sum(1 for row in candidates if "identique_EN_FR" in str(row["reason"]))
    print("Translation audit")
    print(f'- p() entries in {args.script}: {len(entries)}')
    print(f'- Candidates written to: {output}')
    print(f"- Total candidates : {len(candidates)}")
    print(f"- Blocks still identical in English/French : {exact_left}")

    for row in candidates[:args.preview]:
        sample = str(row["english"]).replace("\n", "\\n")
        print(f"  0x{row['offset']:06X} len={row['length']} {row['reason']} :: {sample[:90]}")

    return 0


def _first_csv_value(
    row: Mapping[str, str | None],
    columns: Iterable[str],
) -> str:
    for column in columns:
        value = row.get(column)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_csv_integer(value: str, *, label: str) -> int:
    match = re.search(r"0[xX][0-9A-Fa-f]+|\d+", value)
    if match is None:
        raise ValueError(f'{label}: missing integer in {value!r}')
    token = match.group(0)
    return int(token, 16) if token.lower().startswith("0x") else int(token)


def _catalogue_record_type(row: Mapping[str, str | None]) -> str:
    return _first_csv_value(
        row,
        ("record_type", "entry_type", "entry_kind", "kind", "category"),
    ).casefold()


def _is_restoration_catalogue_row(
    row: Mapping[str, str | None],
) -> bool:
    record_type = _catalogue_record_type(row)
    if "restor" in record_type:
        return True
    explicit = _first_csv_value(
        row,
        (
            "restoration_reference",
            "restoration_slot",
            "slot_hex",
            "slot",
            "pointer_reference",
            "reference_hex",
            "reference",
        ),
    )
    if explicit:
        return True
    identity = _first_csv_value(
        row,
        (
            "source_offset_or_pointer",
            "offset_hex",
            "offset",
            "source_offset_hex",
            "source_offset",
        ),
    )
    if not identity:
        return False
    try:
        return _parse_csv_integer(identity, label="reference") in (
            RESTORATION_REFERENCES
        )
    except ValueError:
        return False


def _catalogue_identity_offset(
    row: Mapping[str, str | None],
    *,
    line_number: int,
) -> int:
    raw_offset = _first_csv_value(
        row,
        (
            "source_offset_or_pointer",
            "offset_hex",
            "offset",
            "source_offset_hex",
            "source_offset",
            "text_offset",
        ),
    )
    if not raw_offset:
        raw_offset = _first_csv_value(row, ("stable_key",))
    if not raw_offset:
        raise ValueError(f"Line {line_number}: missing offset_hex")
    return _parse_csv_integer(
        raw_offset,
        label=f"Line {line_number}: offset",
    )


def _catalogue_text(
    row: Mapping[str, str | None],
    *,
    text_profile: TextProfile,
    line_number: int,
) -> str:
    columns = (
        FRENCH_TRANSLATION_COLUMNS
        if text_profile is FRENCH_TEXT_PROFILE
        else ENGLISH_TRANSLATION_COLUMNS
    )
    text = ""
    for column in columns:
        value = row.get(column)
        if value is not None and str(value) != "":
            # Leading/trailing ASCII spaces are meaningful ROM bytes.  Do not
            # route localized payloads through the metadata helper that strips
            # whitespace.
            text = str(value)
            break
    if text_profile is not FRENCH_TEXT_PROFILE:
        status = _first_csv_value(row, ("review_status", "status"))
        blocked = {
            "",
            "pending",
            "todo",
            "draft",
            "unreviewed",
            "needs_review",
            "missing",
        }
        if status.casefold().replace(" ", "_") in blocked:
            raise ValueError(
                f"Line {line_number}: unapproved English review_status "
                f"({status or 'empty'})"
            )
        if not text:
            raise ValueError(
                f'Line {line_number}: missing en_v2/english_v2 text'
            )
    return text.replace("\\n", "\n").replace("\\r", "\r")


def load_restoration_texts_csv(
    path: str | Path,
    *,
    text_profile: TextProfile | None = None,
) -> dict[int, str]:
    """Load exactly the 85 localized restoration texts from a CSV catalogue."""
    profile = resolve_text_profile(text_profile)
    restorations: dict[int, str] = {}
    csv_path = ROOT / path
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=2):
            if not _is_restoration_catalogue_row(row):
                continue
            raw_reference = _first_csv_value(
                row,
                (
                    "restoration_reference",
                    "restoration_slot",
                    "slot_hex",
                    "slot",
                    "pointer_reference",
                    "reference_hex",
                    "reference",
                    "selected_pointer_references",
                    "source_offset_or_pointer",
                    "offset_hex",
                    "offset",
                    "stable_key",
                ),
            )
            if not raw_reference:
                raise ValueError(
                    f"Line {index}: missing restoration reference"
                )
            reference = _parse_csv_integer(
                raw_reference,
                label=f"Line {index}: restoration reference",
            )
            if reference in restorations:
                raise ValueError(
                    f"Line {index}: duplicate restoration "
                    f"0x{reference:06X}"
                )
            restorations[reference] = _catalogue_text(
                row,
                text_profile=profile,
                line_number=index,
            )
    validate_restoration_catalogue(
        restorations,
        label=f"{csv_path}: restorations {profile.locale}",
    )
    return restorations


def load_pointer_variants_csv(
    path: str | Path,
    *,
    text_profile: TextProfile | None = None,
) -> dict[int, tuple[PointerVariant, ...]]:
    """Load the exact seven reviewed EN pointer variants in source order."""
    profile = resolve_text_profile(text_profile)
    if profile is FRENCH_TEXT_PROFILE:
        raise ValueError(
            'Pointer variants require the en-US profile'
        )

    csv_path = ROOT / path
    variants_by_main: dict[int, list[PointerVariant]] = {}
    seen_variant_keys: set[str] = set()
    seen_pointer_references: set[int] = set()
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for line_number, row in enumerate(reader, start=2):
            status = _first_csv_value(row, ("review_status", "status"))
            blocked_statuses = {
                "",
                "pending",
                "todo",
                "draft",
                "unreviewed",
                "needs_review",
                "missing",
            }
            if status.casefold().replace(" ", "_") in blocked_statuses:
                raise ValueError(
                    f"Line {line_number}: English variant review_status "
                    f"not approved ({status or 'empty'})"
                )

            raw_text = row.get("english_v2")
            if raw_text is None or not str(raw_text).strip():
                raise ValueError(
                    f"Line {line_number}: missing variant english_v2"
                )
            text = str(raw_text).replace("\\n", "\n").replace("\\r", "\r")

            stable_key = _first_csv_value(row, ("stable_key",))
            variant_key = _first_csv_value(row, ("variant_key",))
            raw_reference = _first_csv_value(
                row,
                ("pointer_reference_hex", "pointer_reference"),
            )
            raw_shared_target = _first_csv_value(
                row,
                ("shared_english_2015_target",),
            )
            if not stable_key:
                raise ValueError(f"Line {line_number}: missing stable_key")
            if not variant_key:
                raise ValueError(f"Line {line_number}: missing variant_key")
            if not raw_reference:
                raise ValueError(
                    f"Line {line_number}: missing pointer_reference_hex"
                )
            if not raw_shared_target:
                raise ValueError(
                    f"Line {line_number}: "
                    "missing shared_english_2015_target"
                )

            main_offset = _parse_csv_integer(
                stable_key,
                label=f"Line {line_number}: stable_key",
            )
            pointer_reference = _parse_csv_integer(
                raw_reference,
                label=f"Line {line_number}: pointer_reference_hex",
            )
            shared_source_target = _parse_csv_integer(
                raw_shared_target,
                label=(
                    f"Line {line_number}: "
                    "shared_english_2015_target"
                ),
            )
            expected_stable_key = f"MAIN:0x{main_offset:06X}"
            expected_variant_key = (
                f"{expected_stable_key}@0x{pointer_reference:06X}"
            )
            if stable_key != expected_stable_key:
                raise ValueError(
                    f'Line {line_number}: noncanonical stable_key {stable_key!r}, expected {expected_stable_key!r}'
                )
            if variant_key != expected_variant_key:
                raise ValueError(
                    f'Line {line_number}: noncanonical variant_key {variant_key!r}, expected {expected_variant_key!r}'
                )
            if shared_source_target != main_offset:
                raise ValueError(
                    f"Line {line_number}: shared English target "
                    f"0x{shared_source_target:06X} differs from "
                    f"0x{main_offset:06X}"
                )
            if variant_key in seen_variant_keys:
                raise ValueError(
                    f"Line {line_number}: duplicate variant_key "
                    f"{variant_key!r}"
                )
            if pointer_reference in seen_pointer_references:
                raise ValueError(
                    f"Line {line_number}: duplicate variant reference "
                    f"0x{pointer_reference:06X}"
                )
            seen_variant_keys.add(variant_key)
            seen_pointer_references.add(pointer_reference)
            variants_by_main.setdefault(main_offset, []).append(
                PointerVariant(
                    variant_key=variant_key,
                    stable_key=stable_key,
                    main_offset=main_offset,
                    pointer_reference=pointer_reference,
                    shared_source_target=shared_source_target,
                    text=text,
                )
            )

    variant_count = sum(len(group) for group in variants_by_main.values())
    if variant_count != EXPECTED_POINTER_VARIANT_COUNT:
        raise ValueError(
            f"{csv_path}: {variant_count} pointer variants, "
            f"{EXPECTED_POINTER_VARIANT_COUNT} expected"
        )
    actual_groups = {
        main_offset: tuple(
            variant.pointer_reference
            for variant in variants
        )
        for main_offset, variants in variants_by_main.items()
    }
    if actual_groups != EXPECTED_POINTER_VARIANT_REFERENCES:
        expected = "; ".join(
            f"0x{main_offset:06X}="
            + ",".join(f"0x{ref:06X}" for ref in refs)
            for main_offset, refs in (
                EXPECTED_POINTER_VARIANT_REFERENCES.items()
            )
        )
        actual = "; ".join(
            f"0x{main_offset:06X}="
            + ",".join(f"0x{ref:06X}" for ref in refs)
            for main_offset, refs in sorted(actual_groups.items())
        )
        raise ValueError(
            f"{csv_path}: invalid variant topology ({actual or 'empty'}), expected {expected}"
        )
    return {
        main_offset: tuple(variants)
        for main_offset, variants in variants_by_main.items()
    }


def read_translation_csv(
    path: str | Path,
    *,
    text_profile: TextProfile | None = None,
    skip_restoration_rows: bool = False,
) -> list[TranslationRow]:
    profile = resolve_text_profile(text_profile)
    rows: list[TranslationRow] = []
    with (ROOT / path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=2):
            if skip_restoration_rows and _is_restoration_catalogue_row(row):
                continue
            offset = _catalogue_identity_offset(
                row,
                line_number=index,
            )
            text = _catalogue_text(
                row,
                text_profile=profile,
                line_number=index,
            )

            raw_max = _first_csv_value(
                row,
                (
                    "max_len",
                    "source_capacity_bytes",
                    "source_max_len",
                    "source_length",
                    "length",
                ),
            )
            max_len = int(raw_max) if str(raw_max).strip() else None
            layout = (row.get("layout") or "").strip()
            if layout not in profile.supported_layouts:
                raise ValueError(
                    f"Line {index}: unknown layout {layout!r}"
                )
            rows.append(TranslationRow(offset, text, max_len, layout))
    return rows


def command_build(args: argparse.Namespace) -> int:
    text_profile = text_profile_from_args(args)
    original = read_bytes(args.input_rom)
    rows = read_translation_csv(
        args.csv,
        text_profile=text_profile,
        skip_restoration_rows=(text_profile is not FRENCH_TEXT_PROFILE),
    )
    original_hash = sha256(original)
    glyph_by_start = (
        structured_glyph_record_map(
            verified_all_graphical_text_records(original)
        )
        if original_hash == TRANSLATION_BASE_SHA256
        else {}
    )
    preflight_errors: list[str] = []
    if original_hash != TRANSLATION_BASE_SHA256:
        preflight_errors.append(
            "NONCANONICAL BASE ROM: "
            f"{original_hash} instead of {TRANSLATION_BASE_SHA256}"
        )

    for row in rows:
        offset, text, max_len = row.offset, row.text, row.max_len
        if offset < INES_HEADER_SIZE or offset >= len(original):
            preflight_errors.append(f"OFFSET OUTSIDE ROM 0x{offset:06X}")
            continue
        canonical_max_len = source_record_len(
            original,
            offset,
            glyph_by_start,
        )
        if max_len is None:
            max_len = canonical_max_len
        elif max_len != canonical_max_len:
            preflight_errors.append(
                f"INCONSISTENT SOURCE LENGTH 0x{offset:06X}: "
                f"CSV={max_len}, ROM={canonical_max_len}"
            )
        if max_len < 1:
            preflight_errors.append(
                f'NO SOURCE TEXT 0x{offset:06X}'
            )
            continue

        encoded = format_profile_text(
            text,
            row.layout,
            text_profile=text_profile,
        )
        conflicts = profile_literal_slot_conflicts(
            text,
            text_profile=text_profile,
        )
        if conflicts:
            preflight_errors.append(
                f"RESERVED PUNCTUATION 0x{offset:06X}: "
                + " ".join(repr(item) for item in sorted(conflicts))
            )
        if len(encoded) > max_len:
            preflight_errors.append(
                f"TRUNCATION FORBIDDEN 0x{offset:06X}: "
                f"{len(encoded)} > {max_len}"
            )

    if preflight_errors:
        print("Build from CSV: PREFLIGHT FAILED")
        print(f"- CSV : {args.csv}")
        print(f"- Errors : {len(preflight_errors)}")
        for error in preflight_errors[:40]:
            print(f"  {error}")
        if len(preflight_errors) > 40:
            print(f"  ... and {len(preflight_errors) - 40} more")
        print('- No artifacts written.')
        return 1

    rom = bytearray(original)
    applied = 0
    for row in rows:
        offset, text, max_len = row.offset, row.text, row.max_len
        if max_len is None:
            max_len = source_record_len(
                original,
                offset,
                glyph_by_start,
            )
        encoded = format_profile_text(
            text,
            row.layout,
            text_profile=text_profile,
        )
        encoded = encoded.ljust(max_len)
        rom[offset:offset + max_len] = encoded
        applied += 1

    output_rom = ROOT / args.output_rom
    output_ips = ROOT / args.output_ips
    font_export_directory, font_changed = apply_profile_font_and_export(
        original,
        rom,
        output_rom,
        text_profile=text_profile,
    )
    output_rom.write_bytes(bytes(rom))
    output_ips.write_bytes(make_ips(original, bytes(rom)))

    changed = sum(1 for left, right in zip(original, rom) if left != right)
    print("Build from CSV")
    print(f"- CSV : {args.csv}")
    print(f"- Applied entries : {applied}")
    print(f'- Changed bytes: {changed}')
    print(f"- ROM : {output_rom}")
    print(f"- IPS : {output_ips}")
    if text_profile is FRENCH_TEXT_PROFILE:
        print(f'- French glyphs: {font_changed} bytes changed')
        print(f"- Font CHR export : {font_export_directory}")
    else:
        print("- English font preserved : YES")
        print('- French CHR export: NONE')
    return 0


def command_build_repointed(args: argparse.Namespace) -> int:
    text_profile = text_profile_from_args(args)
    original = read_bytes(args.input_rom)
    rom = bytearray(original)
    rows = read_translation_csv(
        args.csv,
        text_profile=text_profile,
        skip_restoration_rows=(text_profile is not FRENCH_TEXT_PROFILE),
    )
    original_hash = sha256(original)
    if original_hash != TRANSLATION_BASE_SHA256:
        print('Experimental pointer-relocation build: PREFLIGHT FAILED')
        print(
            "- Noncanonical base ROM : "
            f"{original_hash} instead of {TRANSLATION_BASE_SHA256}"
        )
        print('- No artifacts written.')
        return 1

    glyph_records = verified_all_graphical_text_records(original)
    glyph_by_start = structured_glyph_record_map(glyph_records)
    translated_glyph_starts = {
        row.offset
        for row in rows
        if row.offset in glyph_by_start
    }
    untranslated_glyph_spans = [
        (start, end)
        for start, end, _, _ in glyph_records
        if start not in translated_glyph_starts
    ]
    protected: list[tuple[int, int]] = []
    max_len_by_offset: dict[int, int] = {}
    for row in rows:
        canonical_max_len = source_record_len(
            original,
            row.offset,
            glyph_by_start,
        )
        max_len = (
            row.max_len
            if row.max_len is not None
            else canonical_max_len
        )
        max_len_by_offset[row.offset] = max_len
        if max_len > 0:
            protected.append((row.offset, min(len(original), row.offset + max_len + 1)))
    protected.extend(untranslated_glyph_spans)

    known_offsets = known_source_target_offsets(
        original,
        (
            (row.offset, max_len_by_offset[row.offset])
            for row in rows
        ),
    )
    pointer_entries = detect_pointer_table_entries(
        original,
        min_run=args.min_pointer_run,
        known_offsets=known_offsets,
        min_known_ratio=args.min_known_ratio,
        min_known_count=args.min_known_count,
    )
    free_spans = find_text_free_spans(
        original,
        protected,
        min_len=args.min_free_run,
    )

    relocated: list[tuple[int, int, int, int]] = []
    warnings: list[str] = []
    fatal_errors: list[str] = []
    applied = 0

    for row in rows:
        offset, text = row.offset, row.text
        max_len = max_len_by_offset[offset]
        if max_len < 1:
            fatal_errors.append(
                f'NO SOURCE TEXT 0x{offset:06X}'
            )
            continue

        encoded = format_profile_text(
            text,
            row.layout,
            text_profile=text_profile,
        )
        conflicts = profile_literal_slot_conflicts(
            text,
            text_profile=text_profile,
        )
        if conflicts:
            fatal_errors.append(
                f"RESERVED PUNCTUATION 0x{offset:06X}: "
                + " ".join(repr(item) for item in sorted(conflicts))
            )
            continue
        should_repoint = (
            len(encoded) > max_len
            and len(encoded) >= args.min_repoint_text_len
            and offset in pointer_entries
            and has_text_terminator(original, offset)
        )

        if should_repoint:
            pair = pair_for_offset(offset)
            size = len(encoded) + 1
            new_offset = allocate_from_pair(free_spans, pair, size)
            if new_offset is not None:
                new_address = cpu_addr_for_offset(new_offset)
                rom[new_offset:new_offset + len(encoded)] = encoded
                rom[new_offset + len(encoded)] = 0x0D
                for pointer_offset in pointer_entries[offset]:
                    rom[pointer_offset:pointer_offset + 2] = new_address.to_bytes(2, "little")
                relocated.append((offset, new_offset, len(encoded), len(pointer_entries[offset])))
                applied += 1
                continue
            fatal_errors.append(
                f'NO SPACE 0x{offset:06X}: {size} bytes required in pair {pair}'
            )

        if len(encoded) > max_len:
            fatal_errors.append(
                f"TRUNCATION FORBIDDEN 0x{offset:06X}: "
                f"{len(encoded)} > {max_len}"
            )
            continue
        encoded = encoded.ljust(max_len)
        rom[offset:offset + max_len] = encoded
        applied += 1

    if fatal_errors:
        print('Experimental pointer-relocation build: PREFLIGHT FAILED')
        print(f"- CSV : {args.csv}")
        print(f"- Errors : {len(fatal_errors)}")
        for error in fatal_errors[:40]:
            print(f"  {error}")
        if len(fatal_errors) > 40:
            print(f"  ... and {len(fatal_errors) - 40} more")
        print('- No artifacts written.')
        return 1

    output_rom = ROOT / args.output_rom
    output_ips = ROOT / args.output_ips
    font_export_directory, font_changed = apply_profile_font_and_export(
        original,
        rom,
        output_rom,
        text_profile=text_profile,
    )
    output_rom.write_bytes(bytes(rom))
    output_ips.write_bytes(make_ips(original, bytes(rom)))

    changed = sum(1 for left, right in zip(original, rom) if left != right)
    print('Experimental build with pointer relocation')
    print(f"- CSV : {args.csv}")
    print(f"- Applied entries : {applied}")
    print(f"- Relocated texts : {len(relocated)}")
    print(f'- Changed bytes: {changed}')
    print(f"- ROM : {output_rom}")
    print(f"- IPS : {output_ips}")
    if text_profile is FRENCH_TEXT_PROFILE:
        print(f'- French glyphs: {font_changed} bytes changed')
        print(f"- Font CHR export : {font_export_directory}")
    else:
        print("- English font preserved : YES")
        print('- French CHR export: NONE')
    print(f"- Warnings : {len(warnings)}")

    if relocated:
        print("- Pointer-relocation examples :")
        for old_offset, new_offset, length, ref_count in relocated[:15]:
            print(
                f"  0x{old_offset:06X} -> 0x{new_offset:06X} "
                f"({length} characters, {ref_count} pointer(s))"
            )
        if len(relocated) > 15:
            print(f"  ... and {len(relocated) - 15} more")

    if warnings:
        for warning in warnings[:20]:
            print(f"  {warning}")
        if len(warnings) > 20:
            print(f"  ... and {len(warnings) - 20} more")

    return 0


def command_build_repacked(args: argparse.Namespace) -> int:
    text_profile = text_profile_from_args(args)
    original = read_bytes(args.input_rom)
    rom = bytearray(original)
    move_label_catalog = resolve_move_label_catalog(
        getattr(args, "move_labels_csv", ""),
        text_profile=text_profile,
    )
    move_label_specs = load_profile_move_label_specs(
        text_profile=text_profile,
        catalogue=move_label_catalog,
    )
    pointer_variants_csv = getattr(args, "pointer_variants_csv", "")
    pointer_variants: dict[int, tuple[PointerVariant, ...]] = {}
    if (
        pointer_variants_csv
        and text_profile is not FRENCH_TEXT_PROFILE
    ):
        pointer_variants = load_pointer_variants_csv(
            pointer_variants_csv,
            text_profile=text_profile,
        )
    restoration_csv = getattr(args, "restorations_csv", "")
    restoration_texts: Mapping[int, str] | None = None
    if restoration_csv:
        restoration_texts = load_restoration_texts_csv(
            restoration_csv,
            text_profile=text_profile,
        )
    elif text_profile is not FRENCH_TEXT_PROFILE:
        # The canonical EN catalogue contains both MAIN and RESTORED records.
        # Never fall back to the imported French catalogue for an EN build.
        restoration_texts = load_restoration_texts_csv(
            args.csv,
            text_profile=text_profile,
        )
    rows = read_translation_csv(
        args.csv,
        text_profile=text_profile,
        skip_restoration_rows=(text_profile is not FRENCH_TEXT_PROFILE),
    )
    restoration_payloads = verified_dialogue_restoration_payloads(
        original,
        restoration_texts,
        text_profile=text_profile,
    )

    row_info: list[tuple[TranslationRow, int, bytes]] = []
    max_len_by_offset: dict[int, int] = {}
    preflight_errors: list[str] = []
    seen_offsets: set[int] = set()
    original_hash = sha256(original)
    if original_hash != TRANSLATION_BASE_SHA256:
        preflight_errors.append(
            "NONCANONICAL BASE ROM: "
            f"{original_hash} instead of {TRANSLATION_BASE_SHA256}"
        )
        glyph_records: list[tuple[int, int, int, int]] = []
    else:
        glyph_records = verified_all_graphical_text_records(original)
    glyph_by_start = structured_glyph_record_map(glyph_records)
    all_glyph_spans = [
        (start, end)
        for start, end, _, _ in glyph_records
    ]

    for row in rows:
        if row.offset in seen_offsets:
            preflight_errors.append(
                f"DUPLICATE OFFSET 0x{row.offset:06X}"
            )
        seen_offsets.add(row.offset)

        if row.offset < INES_HEADER_SIZE or row.offset >= len(original):
            preflight_errors.append(
                f"OFFSET OUTSIDE ROM 0x{row.offset:06X}"
            )
            max_len = 0
        else:
            containing_glyph = next(
                (
                    (start, end)
                    for start, end in all_glyph_spans
                    if start <= row.offset < end
                ),
                None,
            )
            if (
                containing_glyph is not None
                and row.offset != containing_glyph[0]
            ):
                preflight_errors.append(
                    f"OFFSET INSIDE A GRAPHICAL RECORD "
                    f"0x{row.offset:06X} "
                    f"(debut 0x{containing_glyph[0]:06X})"
                )
            canonical_max_len = source_record_len(
                original,
                row.offset,
                glyph_by_start,
            )
            max_len = (
                row.max_len
                if row.max_len is not None
                else canonical_max_len
            )
            if (
                row.max_len is not None
                and row.max_len != canonical_max_len
            ):
                preflight_errors.append(
                    f"INCONSISTENT SOURCE LENGTH 0x{row.offset:06X}: "
                    f"CSV={row.max_len}, ROM={canonical_max_len}"
                )

        encoded = format_profile_text(
            row.text,
            row.layout,
            text_profile=text_profile,
        )
        conflicts = profile_literal_slot_conflicts(
            row.text,
            text_profile=text_profile,
        )
        if conflicts:
            preflight_errors.append(
                f"RESERVED PUNCTUATION 0x{row.offset:06X}: "
                + " ".join(repr(item) for item in sorted(conflicts))
            )
        if max_len < 1:
            preflight_errors.append(
                f'NO SOURCE TEXT 0x{row.offset:06X}'
            )
        if row.offset + max(0, max_len) > len(original):
            preflight_errors.append(
                f'RANGE OUTSIDE ROM 0x{row.offset:06X}: {max_len} bytes'
            )
        if any(
            (value < 0x20 or value > 0x7E)
            and value not in text_profile.renderer_control_bytes
            for value in encoded
        ):
            preflight_errors.append(
                f'NONPRINTABLE TEXT 0x{row.offset:06X}'
            )
        max_len_by_offset[row.offset] = max_len
        row_info.append((row, max_len, encoded))

    if not rows:
        preflight_errors.append('CSV HAS NO TRANSLATION')

    if preflight_errors:
        print("Full pointer repack: PRELIMINARY CHECK FAILED")
        print(f"- CSV : {args.csv}")
        print(f"- Errors : {len(preflight_errors)}")
        for error in preflight_errors[:40]:
            print(f"  {error}")
        if len(preflight_errors) > 40:
            print(f"  ... and {len(preflight_errors) - 40} more")
        print('- No artifacts written.')
        return 1

    translated_glyph_starts = {
        row.offset
        for row, _, _ in row_info
        if row.offset in glyph_by_start
    }
    glyph_spans = [
        (start, end)
        for start, end, _, _ in glyph_records
        if start not in translated_glyph_starts
    ]
    for row, max_len, _ in row_info:
        if max_len > 0 and intersects_spans(
            row.offset,
            row.offset + max_len,
            glyph_spans,
        ):
            preflight_errors.append(
                f'TRANSLATED RANGE INSIDE UNDECLARED GRAPHICAL RECORD 0x{row.offset:06X}'
            )

    if preflight_errors:
        print("Full pointer repack: GLYPH CHECK FAILED")
        print(f"- CSV : {args.csv}")
        print(f"- Errors : {len(preflight_errors)}")
        for error in preflight_errors[:40]:
            print(f"  {error}")
        print('- No artifacts written.')
        return 1

    known_offsets = known_source_target_offsets(
        original,
        (
            (row.offset, max_len)
            for row, max_len, _ in row_info
        ),
    )
    pointer_entries = detect_pointer_table_entries(
        original,
        min_run=args.min_pointer_run,
        known_offsets=known_offsets,
        min_known_ratio=args.min_known_ratio,
        min_known_count=args.min_known_count,
    )
    verified_entries = verified_pointer_override_entries(original)
    field_pointer_entries = verified_field_dialogue_pointer_entries(
        original
    )
    pointer_entries, skipped_verified_pointers = (
        merge_non_overlapping_pointer_entries(
            pointer_entries,
            verified_entries,
        )
    )
    pointer_entries, skipped_field_pointers = (
        merge_non_overlapping_pointer_entries(
            pointer_entries,
            field_pointer_entries,
        )
    )
    if skipped_verified_pointers:
        raise ValueError(
            "conflict in verified pointers: "
            + repr(skipped_verified_pointers[:5])
        )
    if skipped_field_pointers:
        raise ValueError(
            "conflict in verified field pointers: "
            + repr(skipped_field_pointers[:5])
        )
    pointer_entries = remove_verified_non_dialogue_pointer_refs(
        original,
        pointer_entries,
    )
    pointer_entries = apply_verified_pointer_redirects(
        original,
        pointer_entries,
    )
    if text_profile is ENGLISH_TEXT_PROFILE:
        pointer_entries = apply_verified_source_alignment_pointer_redirects(
            original,
            pointer_entries,
        )
    field_pointer_entries = apply_verified_pointer_redirects(
        original,
        field_pointer_entries,
    )
    if (
        len(field_pointer_entries)
        != VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS
    ):
        raise ValueError(
            f'{len(field_pointer_entries)} field targets after redirection; expected {VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS}'
        )
    contextual_target_offsets: set[int] = set()
    skipped_contextual_pointers: list[tuple[int, int, int]] = []
    if args.min_context_pointers > 0:
        for row, max_len, _ in row_info:
            if max_len < 1:
                continue
            plausible_targets = {row.offset}
            delta = reviewed_text_prefix_len(
                original[row.offset:row.offset + max_len]
            )
            if 0 < delta < max_len:
                plausible_targets.add(row.offset + delta)

            for target_offset in plausible_targets:
                if likely_text_pointer_target(original, target_offset):
                    contextual_target_offsets.add(target_offset)
        contextual_entries = detect_contextual_pointer_entries(
            original,
            contextual_target_offsets,
            window=args.context_pointer_window,
            min_context_count=args.min_context_pointers,
        )
        pointer_entries, skipped_contextual_pointers = merge_non_overlapping_pointer_entries(
            pointer_entries,
            contextual_entries,
        )

    restoration_refs = set(restoration_payloads)
    translated_offsets = {row.offset for row, _, _ in row_info}
    synthetic_collisions = sorted(restoration_refs & translated_offsets)
    if synthetic_collisions:
        raise ValueError(
            "restored slots conflict with source texts: "
            + ", ".join(
                f"0x{offset:06X}" for offset in synthetic_collisions
            )
        )

    pointer_spans = [
        (pointer_offset, pointer_offset + 2)
        for refs in pointer_entries.values()
        for pointer_offset in refs
    ]
    pointer_spans.extend(
        (pointer_offset, pointer_offset + 2)
        for pointer_offset in restoration_refs
    )
    protected_tail_errors: list[str] = []
    protected_glyph_errors: list[str] = []
    for target_offset, refs in pointer_entries.items():
        for pointer_offset in refs:
            pair = pair_for_offset(pointer_offset)
            tail_start, tail_end = protected_bank_tail(pair)
            if (
                pointer_offset < tail_end
                and pointer_offset + 2 > tail_start
            ):
                protected_tail_errors.append(
                    f'POINTER IN TAIL CODE 0x{pointer_offset:06X} to 0x{target_offset:06X}'
                )
            if intersects_spans(
                pointer_offset,
                pointer_offset + 2,
                glyph_spans,
            ):
                protected_glyph_errors.append(
                    f'POINTER IN GLYPH RECORD 0x{pointer_offset:06X} to 0x{target_offset:06X}'
                )

    row_pointer_refs = assign_pointer_targets_to_rows(
        row_info,
        pointer_entries,
    )
    pointer_variant_payloads: dict[int, bytes] = {}
    if pointer_variants:
        pointer_variant_payloads = prepare_pointer_variant_payloads(
            original,
            row_info,
            row_pointer_refs,
            pointer_variants,
            restoration_refs,
            text_profile=text_profile,
        )

    # The graphical payload uses two bytes per 16x16 cell.  Reserve every
    # selected move as a distinct allocator root: ordinary suffix pooling is
    # valid for text but would let the later graphical write cross another
    # live move target.  The binary markers are replaced before output and
    # are constructed so neither printable text nor another marker can be
    # their suffix.
    graphic_requirements = {
        MOVE_NAME_POINTER_TABLE_OFFSET + spec.move_index * 2: (
            spec.move_index,
            spec.required_payload_size - 1,
        )
        for spec in move_label_specs
    }
    graphic_reservation_payloads: dict[int, bytes] = {}
    reserved_move_indexes: set[int] = set()
    if graphic_requirements:
        for row, max_len, encoded in row_info:
            owned = [
                graphic_requirements[pointer_offset]
                for _target, pointer_offsets in row_pointer_refs[row.offset]
                for pointer_offset in pointer_offsets
                if pointer_offset in graphic_requirements
            ]
            if len(owned) > 1:
                raise ValueError(
                    f'Multiple graphical moves share source row 0x{row.offset:06X}: {owned!r}'
                )
            if owned:
                move_index, required_length = owned[0]
                graphic_reservation_payloads[row.offset] = (
                    move_graphic_reservation_payload(
                        move_index,
                        required_length + 1,
                    )
                )
                reserved_move_indexes.add(move_index)
        missing_move_reservations = sorted(
            {spec.move_index for spec in move_label_specs}
            - reserved_move_indexes
        )
        if missing_move_reservations:
            raise ValueError(
                "graphical moves without an allocatable row: "
                + ", ".join(
                    str(move_index)
                    for move_index in missing_move_reservations
                )
            )
    graphic_reservation_offsets = set(graphic_reservation_payloads)

    field_target_owners: dict[int, list[int]] = {}
    for row, _, _ in row_info:
        for target, refs in row_pointer_refs[row.offset]:
            if target not in field_pointer_entries or not refs:
                continue
            field_target_owners.setdefault(target, []).append(row.offset)
            if row.layout != DIALOGUE_LAYOUT:
                preflight_errors.append(
                    f'FIELD TARGET 0x{target:06X} OWNED BY 0x{row.offset:06X} WITHOUT LAYOUT {DIALOGUE_LAYOUT}'
                )
    unowned_field_targets = sorted(
        set(field_pointer_entries) - set(field_target_owners)
    )
    multiply_owned_field_targets = {
        target: owners
        for target, owners in field_target_owners.items()
        if len(owners) != 1
    }
    if unowned_field_targets or multiply_owned_field_targets or preflight_errors:
        print(
            'Full pointer repack: FIELD TARGET OWNERSHIP FAILED'
        )
        for target in unowned_field_targets:
            refs = field_pointer_entries[target]
            print(
                f"  0x{target:06X}: "
                f"{len(refs)} slot(s), premier 0x{refs[0]:06X}"
            )
        for target, owners in sorted(
            multiply_owned_field_targets.items()
        ):
            print(
                f"  0x{target:06X}: owners "
                + ", ".join(
                    f"0x{owner:06X}" for owner in owners
                )
            )
        for error in preflight_errors:
            print(f"  {error}")
        print('- No artifacts written.')
        return 1

    graphical_target_errors = graphical_pointer_target_conflicts(
        row_pointer_refs,
        translated_glyph_starts,
    )
    if graphical_target_errors:
        print("Full pointer repack: GRAPHICAL TARGET CHECK FAILED")
        for error in graphical_target_errors:
            print(f"  {error}")
        print('- No artifacts written.')
        return 1

    candidate_offsets: set[int] = set()
    for row, max_len, encoded in row_info:
        if max_len < 1:
            continue
        if not row_pointer_refs[row.offset]:
            continue
        if not has_source_record_terminator(
            original,
            row.offset,
            max_len,
        ):
            continue
        if (
            args.only_overflow
            and len(encoded) <= max_len
            and row.offset not in graphic_reservation_offsets
        ):
            continue
        candidate_offsets.add(row.offset)

    missing_graphic_candidates = sorted(
        graphic_reservation_offsets - candidate_offsets
    )
    if missing_graphic_candidates:
        raise ValueError(
            "graphical reservations without a repackable source record: "
            + ", ".join(
                f"0x{offset:06X}" for offset in missing_graphic_candidates
            )
        )

    # If a candidate range would overlap non-candidate text or a pointer table,
    # keep it in place. This keeps the old area from being reused unsafely.
    protected_non_candidates: list[tuple[int, int]] = []
    for row, max_len, _ in row_info:
        if max_len > 0 and row.offset not in candidate_offsets:
            protected_non_candidates.append((row.offset, min(len(original), row.offset + max_len + 1)))
    protected_non_candidates.extend(pointer_spans)
    protected_non_candidates.extend(glyph_spans)

    unsafe_candidates: set[int] = set()
    for row, max_len, _ in row_info:
        if row.offset not in candidate_offsets or max_len < 1:
            continue
        if intersects_spans(row.offset, min(len(original), row.offset + max_len + 1), protected_non_candidates):
            unsafe_candidates.add(row.offset)
    unsafe_graphic_candidates = sorted(
        unsafe_candidates & graphic_reservation_offsets
    )
    if unsafe_graphic_candidates:
        raise ValueError(
            "graphical reservations overlap protected "
            "data: "
            + ", ".join(
                f"0x{offset:06X}" for offset in unsafe_graphic_candidates
            )
        )
    candidate_offsets.difference_update(unsafe_candidates)

    normalized_by_offset: dict[int, bytes] = {}
    for row, max_len, encoded in row_info:
        if row.offset in graphic_reservation_payloads:
            normalized_by_offset[row.offset] = (
                graphic_reservation_payloads[row.offset]
            )
            continue
        if row.offset not in candidate_offsets:
            normalized_by_offset[row.offset] = encoded
            continue
        normalized_by_offset[row.offset] = normalize_repacked_payload(
            original,
            row.offset,
            max_len,
            encoded,
            (
                target
                for target, refs in row_pointer_refs[row.offset]
                if refs
            ),
            graphical=(row.offset in translated_glyph_starts),
            preserve_runtime_separator=(
                text_profile is ENGLISH_TEXT_PROFILE
            ),
        )
    row_info = [
        (row, max_len, normalized_by_offset[row.offset])
        for row, max_len, _ in row_info
    ]

    protected: list[tuple[int, int]] = []
    for row, max_len, _ in row_info:
        if max_len > 0 and row.offset not in candidate_offsets:
            protected.append((row.offset, min(len(original), row.offset + max_len + 1)))
    protected.extend(pointer_spans)
    protected.extend(glyph_spans)

    free_spans = find_text_free_spans(
        original,
        protected,
        min_len=args.min_free_run,
    )
    for row, max_len, _ in row_info:
        if row.offset in candidate_offsets and max_len > 0:
            pair = pair_for_offset(row.offset)
            free_spans.setdefault(pair, []).append(FreeSpan(row.offset, max_len + 1))

    for pair in list(free_spans):
        free_spans[pair] = merge_free_spans(free_spans[pair])

    initial_free_spans = {
        pair: tuple((span.start, span.length) for span in spans)
        for pair, spans in free_spans.items()
    }

    allocation_payloads = {
        row.offset: encoded
        for row, _, encoded in row_info
        if row.offset in candidate_offsets
    }
    allocation_payloads.update(restoration_payloads)
    allocation_payloads.update(pointer_variant_payloads)
    allocations, raw_allocation_failures = allocate_suffix_pooled(
        free_spans,
        allocation_payloads,
    )
    allocation_failures = [
        f"NO SPACE 0x{offset:06X}: "
        f"{size} bytes required in pair {pair}"
        for offset, size, pair in raw_allocation_failures
    ]
    candidate_offsets.difference_update(
        offset
        for offset, _, _ in raw_allocation_failures
    )

    # Suffix pooling remains enabled for ordinary text, but a graphical
    # reservation must own every byte through its terminator.  Keep this
    # structural assertion even though the reservation marker construction
    # already makes pooling impossible; it turns a future allocator change
    # into a deterministic preflight failure instead of a corrupted move.
    graphic_allocation_overlaps: list[str] = []
    allocated_ranges = {
        source_offset: (
            target_offset,
            target_offset + len(allocation_payloads[source_offset]) + 1,
        )
        for source_offset, target_offset in allocations.items()
    }
    for source_offset in sorted(graphic_reservation_offsets):
        graphic_range = allocated_ranges.get(source_offset)
        if graphic_range is None:
            continue
        graphic_start, graphic_end = graphic_range
        for other_offset, (other_start, other_end) in allocated_ranges.items():
            if other_offset == source_offset:
                continue
            if graphic_start < other_end and other_start < graphic_end:
                graphic_allocation_overlaps.append(
                    f"GRAPHICAL RESERVATION 0x{source_offset:06X} "
                    f"allocated at 0x{graphic_start:06X}-0x{graphic_end:06X} "
                    f"overlaps 0x{other_offset:06X} allocated at "
                    f"0x{other_start:06X}-0x{other_end:06X}"
                )

    relocated: list[tuple[int, int, int, int]] = []
    warnings: list[str] = []
    fixed_overflows: list[dict[str, str | int]] = [
        {
            "offset_hex": f"0x{row.offset:06X}",
            "max_len": max_len,
            "fr_len": len(encoded),
            "overflow": len(encoded) - max_len,
            "fr_text": row.text,
        }
        for row, max_len, encoded in row_info
        if row.offset not in allocations and len(encoded) > max_len
    ]

    for row, _, encoded in row_info:
        new_offset = allocations.get(row.offset)
        if new_offset is None:
            continue
        allocation_end = new_offset + len(encoded) + 1
        pair = pair_for_offset(new_offset)
        tail_start, tail_end = protected_bank_tail(pair)
        if new_offset < tail_end and allocation_end > tail_start:
            protected_tail_errors.append(
                f'ALLOCATION IN TAIL CODE 0x{row.offset:06X}: 0x{new_offset:06X}-0x{allocation_end:06X}'
            )

    for ref, encoded in restoration_payloads.items():
        new_offset = allocations.get(ref)
        if new_offset is None:
            continue
        allocation_end = new_offset + len(encoded) + 1
        pair = pair_for_offset(new_offset)
        tail_start, tail_end = protected_bank_tail(pair)
        if new_offset < tail_end and allocation_end > tail_start:
            protected_tail_errors.append(
                f'RESTORATION IN TAIL CODE 0x{ref:06X}: 0x{new_offset:06X}-0x{allocation_end:06X}'
            )

    for ref, encoded in pointer_variant_payloads.items():
        new_offset = allocations.get(ref)
        if new_offset is None:
            continue
        allocation_end = new_offset + len(encoded) + 1
        pair = pair_for_offset(new_offset)
        tail_start, tail_end = protected_bank_tail(pair)
        if new_offset < tail_end and allocation_end > tail_start:
            protected_tail_errors.append(
                f'VARIANT IN TAIL CODE 0x{ref:06X}: 0x{new_offset:06X}-0x{allocation_end:06X}'
            )

    fatal_errors = [
        *allocation_failures,
        *graphic_allocation_overlaps,
        *protected_tail_errors,
        *protected_glyph_errors,
    ]
    if fixed_overflows:
        fatal_errors.append(
            f'{len(fixed_overflows)} FIXED TEXT RECORD(S) TOO LONG'
        )
    if skipped_contextual_pointers:
        fatal_errors.append(
            f"{len(skipped_contextual_pointers)} AMBIGUOUS "
            "CONTEXTUAL POINTER(S)"
        )

    if fatal_errors:
        print("Full pointer repack: PREFLIGHT FAILED")
        print(f"- CSV : {args.csv}")
        print(f"- Allocation failures : {len(allocation_failures)}")
        print(
            "- Graphical reservation overlaps : "
            f"{len(graphic_allocation_overlaps)}"
        )
        print(f"- Fixed texts too long : {len(fixed_overflows)}")
        print(f"- Tail-code violations : {len(protected_tail_errors)}")
        print(
            "- Glyph-record violations : "
            f"{len(protected_glyph_errors)}"
        )
        print(
            "- Ambiguous contextual pointers : "
            f"{len(skipped_contextual_pointers)}"
        )
        print(f"- Fatal errors : {len(fatal_errors)}")
        for error in fatal_errors[:40]:
            print(f"  {error}")
        if len(fatal_errors) > 40:
            print(f"  ... and {len(fatal_errors) - 40} more")
        for item in fixed_overflows[:20]:
            print(
                f"  TRUNCATION FORBIDDEN {item['offset_hex']}: "
                f"{item['fr_len']} > {item['max_len']}"
            )
        print('- No artifacts written.')
        return 1

    applied = 0

    for row, max_len, _ in row_info:
        if row.offset in allocations and max_len > 0:
            rom[row.offset:row.offset + max_len + 1] = b"\0" * (max_len + 1)

    for row, max_len, encoded in row_info:
        if max_len < 1:
            warnings.append(f'SKIP 0x{row.offset:06X}: no source text')
            continue

        if row.offset in allocations:
            new_offset = allocations[row.offset]
            rom[new_offset:new_offset + len(encoded)] = encoded
            rom[new_offset + len(encoded)] = 0x0D
            updated_pointer_offsets: set[int] = set()
            for target_offset, pointer_offsets in row_pointer_refs[row.offset]:
                for pointer_offset in pointer_offsets:
                    new_target_offset = relocated_text_target(
                        original,
                        row.offset,
                        max_len,
                        encoded,
                        target_offset,
                        new_offset,
                        collapse_graphical_interior=(
                            row.offset in glyph_by_start
                            or row.offset in graphic_reservation_offsets
                        ),
                        collapse_ascii_padding_interior=(
                            text_profile is ENGLISH_TEXT_PROFILE
                        ),
                        preserve_leading_separator=(
                            text_profile is ENGLISH_TEXT_PROFILE
                            and pointer_offset
                            in SEMANTIC_LEADING_SEPARATOR_POINTER_REFS
                        ),
                        preserve_leading_control=(
                            text_profile is ENGLISH_TEXT_PROFILE
                            and pointer_offset
                            in SEMANTIC_LEADING_CONTROL_POINTER_REFS
                        ),
                    )
                    new_address = cpu_addr_for_offset(new_target_offset)
                    rom[pointer_offset:pointer_offset + 2] = new_address.to_bytes(2, "little")
                    updated_pointer_offsets.add(pointer_offset)
            relocated.append((row.offset, new_offset, len(encoded), len(updated_pointer_offsets)))
            applied += 1
            continue

        # All overflows are rejected by the preflight above. Reaching this
        # branch therefore means the complete encoded text fits in place.
        rom[row.offset:row.offset + max_len] = encoded.ljust(max_len)
        applied += 1

    restored: list[tuple[int, int, int]] = []
    for ref, encoded in sorted(restoration_payloads.items()):
        new_offset = allocations[ref]
        rom[new_offset:new_offset + len(encoded)] = encoded
        rom[new_offset + len(encoded)] = 0x0D
        new_address = cpu_addr_for_offset(new_offset)
        rom[ref:ref + 2] = new_address.to_bytes(2, "little")
        restored.append((ref, new_offset, len(encoded)))

    repointed_variants: list[tuple[int, int, int]] = []
    for ref, encoded in sorted(pointer_variant_payloads.items()):
        new_offset = allocations[ref]
        if pair_for_offset(new_offset) != pair_for_offset(ref):
            raise AssertionError(
                f"variant 0x{ref:06X} allocated outside its PRG pair"
            )
        rom[new_offset:new_offset + len(encoded)] = encoded
        rom[new_offset + len(encoded)] = 0x0D
        new_address = cpu_addr_for_offset(new_offset)
        rom[ref:ref + 2] = new_address.to_bytes(2, "little")
        repointed_variants.append((ref, new_offset, len(encoded)))

    for offset in sorted(unsafe_candidates):
        warnings.append(f'NOT RELOCATED 0x{offset:06X}: overlaps protected data')

    battle_menu_chr_expanded = False
    if text_profile is ENGLISH_TEXT_PROFILE:
        battle_menu_chr_expanded = expand_battle_menu_chr_slots(
            original,
            rom,
            (
                normalized_by_offset[offset]
                for offset in BATTLE_MENU_LABEL_OFFSETS
            ),
        )

    patch_fixed_antidote_bag_label(original, rom)
    patch_battle_text_line_break_control(original, rom)

    output_rom = ROOT / args.output_rom
    output_ips = ROOT / args.output_ips
    font_export_directory, font_changed = apply_profile_font_and_export(
        original,
        rom,
        output_rom,
        text_profile=text_profile,
    )
    move_label_report = apply_profile_move_label_graphics(
        original,
        rom,
        text_profile=text_profile,
        catalogue=move_label_catalog,
        specs=move_label_specs,
    )
    move_label_report_path = getattr(args, "move_label_report", "")
    move_label_report_resolved: Path | None = None
    if move_label_report_path and move_label_report is not None:
        move_label_report_resolved = Path(move_label_report_path)
        if not move_label_report_resolved.is_absolute():
            move_label_report_resolved = ROOT / move_label_report_resolved
        move_label_report_resolved.parent.mkdir(parents=True, exist_ok=True)
        move_label_report_resolved.write_text(
            json.dumps(
                move_label_report.to_dict(),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    output_rom.write_bytes(bytes(rom))
    output_ips.write_bytes(make_ips(original, bytes(rom)))

    allocation_output = getattr(args, "allocation_output", "")
    bank_budget_output = getattr(args, "bank_budget_output", "")
    if allocation_output or bank_budget_output:
        pointer_counts = {
            row.offset: sum(
                len(pointer_offsets)
                for _target, pointer_offsets in row_pointer_refs[row.offset]
            )
            for row, _max_len, _encoded in row_info
        }
        report_rows = allocation_report_rows(
            allocation_payloads=allocation_payloads,
            allocations=allocations,
            main_offsets={row.offset for row, _max_len, _encoded in row_info},
            restoration_offsets=set(restoration_payloads),
            pointer_variant_offsets=set(pointer_variant_payloads),
            pointer_counts=pointer_counts,
        )
        if allocation_output:
            write_allocation_report(ROOT / allocation_output, report_rows)
        if bank_budget_output:
            write_bank_budget_report(
                ROOT / bank_budget_output,
                initial_spans=initial_free_spans,
                remaining_spans=free_spans,
            )

    if args.fixed_overflow_output:
        report_path = ROOT / args.fixed_overflow_output
        with report_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["offset_hex", "max_len", "fr_len", "overflow", "fr_text"],
            )
            writer.writeheader()
            for item in fixed_overflows:
                writer.writerow(item)

    changed = sum(1 for left, right in zip(original, rom) if left != right)
    print("Full pointer repack")
    print(f"- CSV : {args.csv}")
    print(f"- Detected tables/pointers : {sum(len(refs) for refs in pointer_entries.values())} refs to {len(pointer_entries)} targets")
    print(f"- Applied entries : {applied}")
    print(f"- Repacked texts : {len(relocated)}")
    print(f"- Restored Chinese dialogues : {len(restored)}")
    if pointer_variants:
        print(
            "- English pointer variants : "
            f"{len(repointed_variants)}"
        )
    print(f"- Fixed texts still truncated : {len(fixed_overflows)}")
    print(f'- Changed bytes: {changed}')
    print(f"- ROM : {output_rom}")
    print(f"- IPS : {output_ips}")
    if text_profile is FRENCH_TEXT_PROFILE:
        print(f'- French glyphs: {font_changed} bytes changed')
        print(f"- Font CHR export : {font_export_directory}")
    else:
        print("- English font preserved : YES")
        print('- French CHR export: NONE')
    if move_label_report is not None:
        print(
            "- Two-line graphical moves : "
            f"{move_label_report.applied_count} "
            f"({len(move_label_report.used_even_slots)} cells)"
        )
        print(f"- Move plan : {move_label_catalog}")
        if move_label_report_path:
            print(f"- Move report : {move_label_report_resolved}")
    if text_profile is ENGLISH_TEXT_PROFILE:
        print(
            "- Battle-menu CHR region : "
            f"0x{BATTLE_MENU_CHR_START_LOW_OFFSET:06X}=0x"
            f"{rom[BATTLE_MENU_CHR_START_LOW_OFFSET]:02X} "
            + ("(expanded)" if battle_menu_chr_expanded else "(stock)")
        )
    if args.fixed_overflow_output:
        print(f"- Fixed-text overflow report : {ROOT / args.fixed_overflow_output}")
    if allocation_output:
        print(f"- Allocation report : {ROOT / allocation_output}")
    if bank_budget_output:
        print(f"- Bank budget : {ROOT / bank_budget_output}")
    print(f"- Warnings : {len(warnings)}")

    if relocated:
        print("- Repack examples :")
        for old_offset, new_offset, length, ref_count in relocated[:15]:
            print(
                f"  0x{old_offset:06X} -> 0x{new_offset:06X} "
                f"({length} characters, {ref_count} pointer(s))"
            )
        if len(relocated) > 15:
            print(f"  ... and {len(relocated) - 15} more")

    if restored:
        print("- Chinese restoration examples :")
        for ref, new_offset, length in restored[:15]:
            print(
                f"  slot 0x{ref:06X} -> 0x{new_offset:06X} "
                f"({length} characters)"
            )
        if len(restored) > 15:
            print(f"  ... and {len(restored) - 15} more")

    if repointed_variants:
        print("- Relocated English pointer variants :")
        for ref, new_offset, length in repointed_variants:
            print(
                f"  slot 0x{ref:06X} -> 0x{new_offset:06X} "
                f"({length} characters)"
            )

    if warnings:
        for warning in warnings[:25]:
            print(f"  {warning}")
        if len(warnings) > 25:
            print(f"  ... and {len(warnings) - 25} more")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Audit and build tools for Pokemon Yellow NES translations.'
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(
        "check",
        help="Verify that the English IPS rebuilds its canonical yellow.nes target.",
    )
    check.add_argument("--chinese-rom", default=CHINESE_ROM)
    check.add_argument("--english-ips", default=ENGLISH_IPS)
    check.add_argument(
        "--english-rom",
        default=CANONICAL_ENGLISH_ROM,
        help="Expected canonical target of the English IPS (default: yellow.nes).",
    )
    check.add_argument("--write-yellow", default="", help="Optional: write the rebuilt ROM.")
    check.set_defaults(func=command_check)

    check_ips = sub.add_parser(
        "check-ips",
        help="Apply an IPS to its base and compare it byte for byte with the target ROM.",
    )
    check_ips.add_argument("--base-rom", default=CANONICAL_ENGLISH_ROM)
    check_ips.add_argument("--ips", default=FINAL_IPS)
    check_ips.add_argument("--target-rom", default=FINAL_ROM)
    check_ips.set_defaults(func=command_check_ips)

    dump = sub.add_parser("dump-script", help="Extract p(...) entries from script.py into an editable CSV.")
    dump.add_argument("--script", default=PATCH_SCRIPT)
    dump.add_argument("--english-rom", default=TRANSLATION_BASE_ROM)
    dump.add_argument("--output", default="traduction_base.csv")
    dump.add_argument("--overflow-output", default="traductions_trop_longues.csv")
    dump.set_defaults(func=command_dump_script)

    audit = sub.add_parser("audit", help="Find blocks likely to still be in English.")
    audit.add_argument("--script", default=PATCH_SCRIPT)
    audit.add_argument("--english-rom", default=TRANSLATION_BASE_ROM)
    audit.add_argument("--french-rom", default=FRENCH_ROM)
    audit.add_argument("--english-ips", default=ENGLISH_IPS)
    audit.add_argument("--output", default="audit_traduction.csv")
    audit.add_argument("--preview", type=int, default=25)
    audit.add_argument("--min-english-score", type=int, default=1)
    audit.add_argument(
        "--text-range",
        action="append",
        default=["0x30000:0x40000"],
        help="Text range to scan. Repeatable. Default: 0x30000:0x40000.",
    )
    audit.add_argument(
        "--all-ranges",
        action="store_true",
        help="Scan all file ranges; produces noisier results.",
    )
    audit.add_argument(
        "--include-translated-hits",
        action="store_true",
        help="Also include modified blocks that still contain English words.",
    )
    audit.add_argument(
        "--all-ascii",
        dest="only_english_ips",
        action="store_false",
        help="Scan the entire ROM instead of areas changed by the English IPS.",
    )
    audit.set_defaults(func=command_audit, only_english_ips=True)

    build = sub.add_parser("build", help="Rebuild a ROM and an IPS from a CSV.")
    build.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default=DEFAULT_PROFILE,
        help="Text profile (legacy default: fr-FR).",
    )
    build.add_argument("--csv", default="traduction_base.csv")
    build.add_argument("--input-rom", default=TRANSLATION_BASE_ROM)
    build.add_argument("--output-rom", default="Pokemon_Jaune_FR_from_csv.nes")
    build.add_argument("--output-ips", default="Pokemon_Jaune_FR_from_csv.ips")
    build.set_defaults(func=command_build)

    repointed = sub.add_parser(
        "build-repointed",
        help="Build an experimental ROM by relocating oversized texts with pointers.",
    )
    repointed.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default=DEFAULT_PROFILE,
        help="Text profile (legacy default: fr-FR).",
    )
    repointed.add_argument("--csv", default="traduction_base.csv")
    repointed.add_argument("--input-rom", default=TRANSLATION_BASE_ROM)
    repointed.add_argument("--output-rom", default="Pokemon_Jaune_FR_repointed.nes")
    repointed.add_argument("--output-ips", default="Pokemon_Jaune_FR_repointed.ips")
    repointed.add_argument("--min-pointer-run", type=int, default=10)
    repointed.add_argument("--min-known-ratio", type=float, default=0.5)
    repointed.add_argument("--min-known-count", type=int, default=4)
    repointed.add_argument(
        "--min-free-run",
        type=int,
        default=DEFAULT_MIN_FREE_RUN,
    )
    repointed.add_argument("--min-repoint-text-len", type=int, default=20)
    repointed.set_defaults(func=command_build_repointed)

    repacked = sub.add_parser(
        "build-repacked",
        help="Repack texts with pointers by bank and reuse their old slots.",
    )
    repacked.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default=DEFAULT_PROFILE,
        help="Text profile (legacy default: fr-FR).",
    )
    repacked.add_argument("--csv", default="traduction_base.csv")
    repacked.add_argument(
        "--restorations-csv",
        default="",
        help=(
            "Optional catalogue containing exactly the 85 restorations. "
            "For en-US, use the main CSV if omitted."
        ),
    )
    repacked.add_argument(
        "--pointer-variants-csv",
        default="",
        help=(
            "Optional en-US catalogue of the seven pointer variants. "
            "Ignored by the fr-FR profile."
        ),
    )
    repacked.add_argument("--input-rom", default=TRANSLATION_BASE_ROM)
    repacked.add_argument("--output-rom", default="Pokemon_Jaune_FR_repacked.nes")
    repacked.add_argument("--output-ips", default="Pokemon_Jaune_FR_repacked.ips")
    repacked.add_argument("--fixed-overflow-output", default="textes_fixes_trop_longs.csv")
    repacked.add_argument(
        "--move-labels-csv",
        default="",
        help=(
            "UTF-8 plan for two-line graphical moves. Defaults to "
            "locales/<profil>/move_labels_two_line.csv if available."
        ),
    )
    repacked.add_argument(
        "--move-label-report",
        default="",
        help="Optional JSON report of allocated graphical cells.",
    )
    repacked.add_argument(
        "--allocation-output",
        default="",
        help="Optional CSV detailing allocations and suffix pooling.",
    )
    repacked.add_argument(
        "--bank-budget-output",
        default="",
        help="Optional CSV of the remaining free-space budget per PRG pair.",
    )
    repacked.add_argument("--min-pointer-run", type=int, default=5)
    repacked.add_argument("--min-known-ratio", type=float, default=0.4)
    repacked.add_argument("--min-known-count", type=int, default=3)
    repacked.add_argument(
        "--min-free-run",
        type=int,
        default=DEFAULT_MIN_FREE_RUN,
    )
    repacked.add_argument("--context-pointer-window", type=int, default=32)
    repacked.add_argument(
        "--min-context-pointers",
        type=int,
        default=0,
        help=(
            "Exploratory mode: number of neighboring values required to accept a "
            "heuristic pointer. Disabled by default; required short pointers "
            "are verified explicitly."
        ),
    )
    repacked.add_argument(
        "--only-overflow",
        action="store_true",
        help="Only relocate oversized texts with pointers. By default, repack all known targets.",
    )
    repacked.set_defaults(func=command_build_repacked)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
