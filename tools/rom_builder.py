#!/usr/bin/env python3
"""Encodage et repack de la traduction française NJ046 depuis le catalogue CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from itertools import combinations
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
from tools.restaurations import (
    COLLAPSED_ENGLISH_POINTER_TARGETS,
    load_restorations,
)
from tools.move_label_graphics import (
    MOVE_COUNT,
    MOVE_NAME_POINTER_TABLE_OFFSET,
    MoveLabelPatchReport,
    MoveLabelSpec,
    french_text_encoder,
    load_move_label_csv,
    patch_move_labels,
)


ROOT = Path(__file__).resolve().parent.parent

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
PATCH_SCRIPT = "traduction/catalogue.csv"
DEFAULT_MOVE_LABEL_CATALOG = ROOT / "traduction" / "move_labels_two_line.csv"
DEFAULT_FRENCH_POINTER_VARIANTS = (
    ROOT / "traduction" / "pointer_variants.csv"
)

# The 2015 English reconstruction collapses five distinct Chinese pointer
# slots onto two shared payloads. The first slot in each group remains owned
# by the ordinary translation row; the three remaining slots receive their
# own reviewed French payload and allocator target.
EXPECTED_FRENCH_POINTER_VARIANT_REFERENCES: dict[int, tuple[int, ...]] = {
    0x0302FA: (0x03006B, 0x03006D),
    0x031A15: (0x031971, 0x031973, 0x031975),
}
EXPECTED_FRENCH_POINTER_VARIANT_COUNT = 5
EXPECTED_FRENCH_SECONDARY_POINTER_VARIANT_COUNT = 3

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

# The stock battle-command renderer reserves dynamic CHR tiles $96-$B5 for
# the right-hand menu, then starts the left message pane at $B6. The original
# three-letter Run label fits that 16-glyph window; the official French
# ``Fuite`` makes the four menu labels occupy 18 glyphs. Moving the menu's CHR
# start from $0960 to the unused $0920 keeps all 18 glyphs below $B6.
BATTLE_RUN_LABEL_OFFSET = 0x030599
BATTLE_MENU_CHR_START_LOW_OFFSET = 0x02321B
BATTLE_MENU_CHR_START_LOW_ORIGINAL = 0x60
BATTLE_MENU_CHR_START_LOW_EXPANDED = 0x20

# The stock message transition clears 24 glyph cells although 25 fit inside
# the frame.  Expanding the immediate width to 25 clears columns 4..28 while
# preserving column 29 (the prompt/border cell), eliminating a possible final
# glyph remnant on the following message.
BATTLE_MESSAGE_CLEAR_WIDTH_OFFSET = 0x0231C1
BATTLE_MESSAGE_CLEAR_WIDTH_ORIGINAL = 0x18
BATTLE_MESSAGE_CLEAR_WIDTH_EXPANDED = 0x19
BATTLE_MESSAGE_CLEAR_CONTEXT_OFFSET = 0x0231C0
BATTLE_MESSAGE_CLEAR_CONTEXT_ORIGINAL = bytes.fromhex("A9188D447D")
BATTLE_MESSAGE_CLEAR_CONTEXT_PATCH = bytes.fromhex("A9198D447D")

# The stock pair-4 text loop treats only 0x0D as a control byte.  Reviewed
# battle fragments now use an explicit 0x0A at word boundaries so long
# dynamic compositions can move to the already-existing second 8x16 line
# instead of drawing through the frame.  The hook advances the current
# 32-cell PPU row by two tile rows (one 8x16 text row), consumes the control,
# and resumes the ordinary loop.  From the normal $22E4 start this reaches
# $2324, the second and final text row.  A defensive high-byte check routes a
# newline received on that second row to the normal terminator path; the
# static layout gate still forbids this case because silently ending a payload
# would truncate the message.
BATTLE_TEXT_CONTROL_HOOK_OFFSET = 0x020986
BATTLE_TEXT_CONTROL_HOOK_ORIGINAL = bytes.fromhex("C90DF0")
BATTLE_TEXT_CONTROL_HOOK_PATCH = bytes.fromhex("4C33F4")  # JMP $F433
BATTLE_TEXT_CONTROL_CAVE_OFFSET = 0x027443
BATTLE_TEXT_CONTROL_CAVE_PATCH = bytes.fromhex(
    "C90DF007"  # CMP #$0D / BEQ terminator
    "C90AF006"  # CMP #$0A / BEQ newline
    "4C7A89"    # ordinary glyph path -> $897A
    "4CC989"    # terminator path -> $89C9
    "A50FC923B0F7"  # reject newline when already on row $23xx
    "A50E29E0186944850E"  # low = (low & $E0) + $44
    "A50F6900850F"        # propagate carry to cursor high
    "C8"        # consume the newline control byte
    "4C6989"    # resume the text loop at $8969
)
BATTLE_TEXT_CONTROL_CAVE_ORIGINAL = bytes(
    len(BATTLE_TEXT_CONTROL_CAVE_PATCH)
)
BATTLE_TEXT_NEWLINE_BYTE = 0x0A

# Both "status already present" branches converge after rendering pointer
# 0x030135.  The stock routine then appends the ordinary status event, which
# yields ungrammatical joins such as ``déjà est empoisonné``.  Once 0x030135
# is the autonomous message ``Statut inchangé !``, this three-byte jump skips
# that second payload and rejoins the stock cleanup at $C80C.
STATUS_ALREADY_SKIP_OFFSET = 0x02480D  # CPU $C7FD in pair 4
STATUS_ALREADY_SKIP_ORIGINAL = bytes.fromhex("A90085")
STATUS_ALREADY_SKIP_PATCH = bytes.fromhex("4C0CC8")  # JMP $C80C

# Only these raw battle records may contain the new 0x0A control.  Keeping the
# list explicit prevents an accidental newline in ordinary dialogue or binary
# glyph records from being silently accepted as printable text.
BATTLE_TEXT_NEWLINE_SOURCE_OFFSETS = frozenset(
    {
        0x0307B9,  # immunité poison: acteur ligne 1, explication ligne 2
        0x0307C4,  # immunité brûlure
        0x0307CF,  # immunité gel
        0x030ADB,  # victoire: formule ligne 1, nom du dresseur ligne 2
    }
)

# ``Antidote`` is the only live entry in the 40-slot battle-bag item table
# whose target is not part of the historical translation catalogue.  The
# renderer writes a two-digit quantity immediately after an eight-cell field;
# ending the fixed payload after ``Antid.`` leaves the required blank cell.
ITEM_LIST_ANTIDOTE_OFFSET = 0x03172E
ITEM_LIST_ANTIDOTE_ORIGINAL = b"Antidote\x0D"
ITEM_LIST_ANTIDOTE_PATCH = b"Antid.\x0D00"

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
class FrenchPointerVariant:
    main_offset: int
    pointer_reference: int
    text: str


@dataclass
class FreeSpan:
    start: int
    length: int


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
        output_rom.parent
        / "font"
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
            "Pokemon Yellow NES - export police française",
            f"ROM sortie prévue: {output_rom.resolve()}",
            f"ROM avec police SHA-256: {sha256(after)}",
            f"Tuiles françaises: {len(tiles)}",
            f"Octets de police modifiés: {changed}",
            f"CHR avant: {before_path.resolve()}",
            f"CHR français: {after_path.resolve()}",
            f"Caractères français natifs: {native_characters}",
            "Note: é réutilise le glyphe @ déjà présent dans la base anglaise.",
            "Compromis: œ/Œ restent oe/OE pour préserver toutes les lettres "
            "ASCII dans les noms saisis.",
            "Résultat: PASS",
            "",
        ]
    )
    (export_directory / "font_export_manifest.txt").write_text(
        manifest,
        encoding="utf-8",
    )
    return export_directory, changed


def resolve_move_label_catalog(requested: str | Path) -> Path | None:
    """Resolve the French-owned two-line move plan, if enabled."""
    if requested:
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if not candidate.is_file():
            raise ValueError(f"plan d'attaques deux lignes absent: {candidate}")
        return candidate
    return DEFAULT_MOVE_LABEL_CATALOG if DEFAULT_MOVE_LABEL_CATALOG.is_file() else None


def load_french_move_label_specs(
    catalogue: Path | None,
) -> tuple[MoveLabelSpec, ...]:
    if catalogue is None:
        return ()
    return load_move_label_csv(catalogue, encoder=french_text_encoder)


def apply_french_move_label_graphics(
    original: bytes,
    rom: bytearray,
    *,
    catalogue: Path | None,
    specs: tuple[MoveLabelSpec, ...],
) -> MoveLabelPatchReport | None:
    """Install the graphical labels after the final French font is ready."""
    if catalogue is None:
        return None
    result = patch_move_labels(
        bytes(rom),
        original,
        specs,
        pool_mode="source",
        require_all=True,
    )
    rom[:] = result.rom
    return result.report


def move_graphic_reservation_payload(
    move_index: int,
    required_payload_size: int,
) -> bytes:
    """Return a binary placeholder that cannot participate in suffix pooling."""
    if not 0 <= move_index < MOVE_COUNT:
        raise ValueError(f"index d'attaque hors plage: {move_index}")
    content_length = required_payload_size - 1
    if content_length not in {2, 4, 6, 8}:
        raise ValueError(
            "taille de réservation graphique invalide: "
            f"{required_payload_size}"
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
        raise ValueError(f"{path} n'est pas un IPS valide")

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
                    f"{path} contient {remaining} octet(s) inattendu(s) apres EOF"
                )
            break

        if i + 5 > len(data):
            raise ValueError(f"IPS tronque vers 0x{i:X}")

        offset = int.from_bytes(data[i:i + 3], "big")
        i += 3
        size = int.from_bytes(data[i:i + 2], "big")
        i += 2

        if size == 0:
            if i + 3 > len(data):
                raise ValueError(f"IPS RLE tronque vers 0x{i:X}")
            rle_size = int.from_bytes(data[i:i + 2], "big")
            i += 2
            value = data[i]
            i += 1
            records.append(IpsRecord(offset, bytes([value]) * rle_size, True))
        else:
            if i + size > len(data):
                raise ValueError(f"IPS record tronque vers 0x{i:X}")
            records.append(IpsRecord(offset, data[i:i + size], False))
            i += size

    if not found_eof:
        raise ValueError(f"{path} n'a pas de marqueur EOF IPS")

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
            "la taille finale IPS dépasse la limite 24 bits: "
            f"{len(modified)} > {max_offset}"
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
                    "offset IPS supérieur à 24 bits: "
                    f"0x{offset:X}"
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


# These battle records are sentence fragments immediately followed by a
# runtime value (trainer, Pokemon, move or prize amount).  Their final blank is
# semantic punctuation, not obsolete English layout padding.  Keeping exactly
# one separator prevents the repacker from producing strings such as
# ``BattuRégis`` or ``utilÉclair`` while preserving the general space-saving
# normalization used by every other relocated record.
TRAILING_SEPARATOR_OFFSETS = frozenset(
    {
        0x0301EB,  # En avant ! <Pokemon>
        0x0301F0,  # sauvage <Pokemon>
        0x030221,  # Sacha lance une <ball>
        0x03022A,  # Oui ! <Pokemon> est capturé !
        0x030230,  # Oh non ! <Pokemon> s'est libéré !
        0x030262,  # <trainer> fait appel à... <Pokemon>
        0x0302BF,  # <Pokemon> utilise <move>
        0x030417,  # Bravo ! <ancienne espèce>
        0x03041D,  # Un <wild Pokemon>
        0x030458,  # <Pokemon> essaie d'apprendre <move>
        0x03045F,  # L'attaque <move> / est oubliée !
        0x0304AB,  # <Pokemon> n'a pas appris <move>
        0x030567,  # dévore le rêve de <Pokemon>
        0x03062E,  # Sauv. <Pokemon>
        0x030634,  # <Pokemon> est K.O. ! (indentation d'une case)
        0x03067D,  # monte au niv. <level>
        0x03075C,  # Reçu : <amount/item>
        0x030765,  # Sacha perd <amount>
        0x03076B,  # Dresseur <trainer>
        0x03077A,  # Requis : <Badge>
        0x030ADB,  # Sacha a vaincu <trainer>
        0x035F3D,  # Résultat : <montant>
        0x035F57,  # <Pokémon> a évolué en <espèce>
        0x035FAE,  # Oublier <attaque>
        0x035FB6,  # Adversaire : <Pokémon>
    }
)

# The wild-encounter suffix is pointed at after ten source padding bytes. Its
# French translation deliberately begins with a separating blank after the
# dynamic Pokemon name, so that live pointer must land on the blank itself.
LEADING_SEPARATOR_POINTER_OFFSETS = frozenset(
    {
        0x0301D7,  # <Pokémon> sauvage apparaît !
        0x03024E,  # <Pokémon> est capturé !
        0x030262,  # <Dresseur> fait appel à... <Pokémon>
        0x0302FA,  # <Pokémon> intoxiqué ! / a peur !
        0x0303A9,  # <statistique> au maximum ! (cible au milieu du préfixe source)
        0x0306EC,  # <Pokémon> s'est enfui !
        0x0306F5,  # <Pokémon> ne peut pas fuir !
        0x03651B,  # <Pokémon> s'est endormi !
    }
)

# Like the semantic spaces above, a leading battle newline belongs to the
# translated fragment.  Several source pointers enter after obsolete padding;
# once repacked they must land on 0x0A itself so the hook can move the cursor
# before the first visible glyph.
LEADING_NEWLINE_POINTER_OFFSETS = BATTLE_TEXT_NEWLINE_SOURCE_OFFSETS


def normalize_repacked_payload(
    source: bytes,
    source_offset: int,
    source_length: int,
    translated: bytes,
    live_targets: Iterable[int],
    *,
    graphical: bool = False,
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
        source_offset in TRAILING_SEPARATOR_OFFSETS
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


def expand_battle_menu_chr_slots_for_fuite(
    source: bytes,
    candidate: bytearray,
    translated_run_label: bytes | None,
) -> bool:
    """Reserve two additional dynamic glyphs for the full ``Fuite`` label."""
    if translated_run_label != b"Fuite":
        return False
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


def expand_battle_message_clear_width(
    source: bytes,
    candidate: bytearray,
) -> bool:
    """Clear all 25 visible battle-message glyph cells on transitions."""
    context_end = (
        BATTLE_MESSAGE_CLEAR_CONTEXT_OFFSET
        + len(BATTLE_MESSAGE_CLEAR_CONTEXT_ORIGINAL)
    )
    if source[
        BATTLE_MESSAGE_CLEAR_CONTEXT_OFFSET:context_end
    ] != BATTLE_MESSAGE_CLEAR_CONTEXT_ORIGINAL:
        raise ValueError(
            "battle message clear source context mismatch at "
            f"0x{BATTLE_MESSAGE_CLEAR_CONTEXT_OFFSET:06X}"
        )
    actual_context = bytes(
        candidate[BATTLE_MESSAGE_CLEAR_CONTEXT_OFFSET:context_end]
    )
    if actual_context not in {
        BATTLE_MESSAGE_CLEAR_CONTEXT_ORIGINAL,
        BATTLE_MESSAGE_CLEAR_CONTEXT_PATCH,
    }:
        raise ValueError(
            "battle message clear candidate context mismatch at "
            f"0x{BATTLE_MESSAGE_CLEAR_CONTEXT_OFFSET:06X}: "
            f"{actual_context.hex()}"
        )
    candidate[
        BATTLE_MESSAGE_CLEAR_CONTEXT_OFFSET:context_end
    ] = BATTLE_MESSAGE_CLEAR_CONTEXT_PATCH
    return actual_context != BATTLE_MESSAGE_CLEAR_CONTEXT_PATCH


def patch_battle_text_newline_control(
    source: bytes,
    candidate: bytearray,
) -> bool:
    """Install the reviewed 0x0A battle-text line-control hook.

    Both the call-site bytes and the code cave are guarded against the
    canonical 2015 base.  Candidate bytes may be either pristine or already
    patched, making the operation deterministic without accepting any other
    mutation in pair 4.
    """
    hook_end = (
        BATTLE_TEXT_CONTROL_HOOK_OFFSET
        + len(BATTLE_TEXT_CONTROL_HOOK_ORIGINAL)
    )
    cave_end = (
        BATTLE_TEXT_CONTROL_CAVE_OFFSET
        + len(BATTLE_TEXT_CONTROL_CAVE_PATCH)
    )
    if source[
        BATTLE_TEXT_CONTROL_HOOK_OFFSET:hook_end
    ] != BATTLE_TEXT_CONTROL_HOOK_ORIGINAL:
        raise ValueError(
            "battle text hook source mismatch at "
            f"0x{BATTLE_TEXT_CONTROL_HOOK_OFFSET:06X}"
        )
    if source[
        BATTLE_TEXT_CONTROL_CAVE_OFFSET:cave_end
    ] != BATTLE_TEXT_CONTROL_CAVE_ORIGINAL:
        raise ValueError(
            "battle text cave source mismatch at "
            f"0x{BATTLE_TEXT_CONTROL_CAVE_OFFSET:06X}"
        )

    actual_hook = bytes(
        candidate[BATTLE_TEXT_CONTROL_HOOK_OFFSET:hook_end]
    )
    if actual_hook not in {
        BATTLE_TEXT_CONTROL_HOOK_ORIGINAL,
        BATTLE_TEXT_CONTROL_HOOK_PATCH,
    }:
        raise ValueError(
            "battle text hook candidate mismatch at "
            f"0x{BATTLE_TEXT_CONTROL_HOOK_OFFSET:06X}: "
            f"{actual_hook.hex()}"
        )
    actual_cave = bytes(
        candidate[BATTLE_TEXT_CONTROL_CAVE_OFFSET:cave_end]
    )
    if actual_cave not in {
        BATTLE_TEXT_CONTROL_CAVE_ORIGINAL,
        BATTLE_TEXT_CONTROL_CAVE_PATCH,
    }:
        raise ValueError(
            "battle text cave candidate mismatch at "
            f"0x{BATTLE_TEXT_CONTROL_CAVE_OFFSET:06X}: "
            f"{actual_cave.hex()}"
        )

    candidate[
        BATTLE_TEXT_CONTROL_HOOK_OFFSET:hook_end
    ] = BATTLE_TEXT_CONTROL_HOOK_PATCH
    candidate[
        BATTLE_TEXT_CONTROL_CAVE_OFFSET:cave_end
    ] = BATTLE_TEXT_CONTROL_CAVE_PATCH
    return not (
        actual_hook == BATTLE_TEXT_CONTROL_HOOK_PATCH
        and actual_cave == BATTLE_TEXT_CONTROL_CAVE_PATCH
    )


def is_supported_repacked_text_byte(value: int, source_offset: int) -> bool:
    """Return whether ``value`` is legal in a translated text payload."""
    return (
        0x20 <= value <= 0x7E
        or (
            value == BATTLE_TEXT_NEWLINE_BYTE
            and source_offset in BATTLE_TEXT_NEWLINE_SOURCE_OFFSETS
        )
    )


def patch_fixed_item_list_antidote(
    source: bytes,
    candidate: bytearray,
) -> bool:
    """Shorten the uncatalogued fixed Antidote label deterministically."""
    end = ITEM_LIST_ANTIDOTE_OFFSET + len(ITEM_LIST_ANTIDOTE_ORIGINAL)
    if source[ITEM_LIST_ANTIDOTE_OFFSET:end] != ITEM_LIST_ANTIDOTE_ORIGINAL:
        raise ValueError(
            "fixed Antidote source mismatch at "
            f"0x{ITEM_LIST_ANTIDOTE_OFFSET:06X}"
        )
    actual = bytes(candidate[ITEM_LIST_ANTIDOTE_OFFSET:end])
    if actual not in {
        ITEM_LIST_ANTIDOTE_ORIGINAL,
        ITEM_LIST_ANTIDOTE_PATCH,
    }:
        raise ValueError(
            "fixed Antidote candidate mismatch at "
            f"0x{ITEM_LIST_ANTIDOTE_OFFSET:06X}: {actual!r}"
        )
    candidate[ITEM_LIST_ANTIDOTE_OFFSET:end] = ITEM_LIST_ANTIDOTE_PATCH
    return actual != ITEM_LIST_ANTIDOTE_PATCH


def patch_status_already_message_control(
    source: bytes,
    candidate: bytearray,
) -> bool:
    """Make the already-status branch stop after its autonomous message."""
    end = STATUS_ALREADY_SKIP_OFFSET + len(STATUS_ALREADY_SKIP_ORIGINAL)
    if source[STATUS_ALREADY_SKIP_OFFSET:end] != STATUS_ALREADY_SKIP_ORIGINAL:
        raise ValueError(
            "status-already source mismatch at "
            f"0x{STATUS_ALREADY_SKIP_OFFSET:06X}"
        )
    actual = bytes(candidate[STATUS_ALREADY_SKIP_OFFSET:end])
    if actual not in {
        STATUS_ALREADY_SKIP_ORIGINAL,
        STATUS_ALREADY_SKIP_PATCH,
    }:
        raise ValueError(
            "status-already candidate mismatch at "
            f"0x{STATUS_ALREADY_SKIP_OFFSET:06X}: {actual.hex()}"
        )
    candidate[STATUS_ALREADY_SKIP_OFFSET:end] = STATUS_ALREADY_SKIP_PATCH
    return actual != STATUS_ALREADY_SKIP_PATCH


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


def parse_patch_entries(script_path: str | Path = PATCH_SCRIPT, *, apply_dialogue_inventory: bool = True) -> list[PatchEntry]:
    """Adaptateur interne : les entrées proviennent uniquement du catalogue CSV."""
    return [PatchEntry(row.offset, row.text, index, row.layout)
            for index, row in enumerate(read_translation_csv(script_path), 1)]



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
        raise ValueError(f"Plage invalide: {value}")
    start = int(left, 16) if left.lower().startswith("0x") else int(left)
    end = int(right, 16) if right.lower().startswith("0x") else int(right)
    if start >= end:
        raise ValueError(f"Plage invalide: {value}")
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
            "inventaire des glyphes structurels non canonique: "
            f"records={len(records)}, glyphes={glyph_count}, "
            f"payload={payload_size}, sha256={fingerprint}"
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
                "record graphique terrain hors ROM/paire: "
                f"0x{start:06X}-0x{end:06X}"
            )
        payload = data[start:end]
        actual_hash = sha256(payload)
        if actual_hash != expected_hash:
            raise ValueError(
                "record graphique terrain non canonique "
                f"0x{start:06X}: {actual_hash} au lieu de {expected_hash}"
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
                    "octet invalide dans le record graphique terrain "
                    f"0x{start + cursor:06X}: 0x{value:02X}"
                )
        if actual_glyph_count != glyph_count:
            raise ValueError(
                f"record graphique terrain 0x{start:06X}: "
                f"{actual_glyph_count} glyphes, {glyph_count} attendus"
            )
        if end >= len(data) or data[end] != 0x0D:
            raise ValueError(
                "terminateur absent après le record graphique terrain "
                f"0x{start:06X}"
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
                "records graphiques vérifiés chevauchants: "
                f"0x{left[0]:06X}-0x{left[1]:06X} et "
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
    """Count source padding without consuming a semantic join space.

    Several battle records are addressed after zero/line-control padding and
    begin their translated fragment with a real separator.  Treating ASCII
    spaces like padding made the relocated pointer skip that separator and
    produced joins such as ``Pikachusouffre``.  The live pointer may skip only
    the reviewed control bytes here; a leading space remains printable data.
    """
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
) -> int:
    """Map a source pointer target into a relocated translated record."""
    target_delta = target_offset - source_offset
    if (
        source_offset in LEADING_NEWLINE_POINTER_OFFSETS
        and target_delta > 0
        and translated.startswith(bytes((BATTLE_TEXT_NEWLINE_BYTE,)))
    ):
        return new_offset
    if (
        source_offset in LEADING_SEPARATOR_POINTER_OFFSETS
        and target_delta > 0
        and translated.startswith(b" ")
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
                f"RECORD GRAPHIQUE 0x{source_offset:06X}: "
                "plusieurs cibles actives "
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


def load_french_pointer_variants(
    path: str | Path = DEFAULT_FRENCH_POINTER_VARIANTS,
) -> dict[int, tuple[FrenchPointerVariant, ...]]:
    """Load the exact reviewed FR meanings split from shared 2015 payloads."""

    csv_path = Path(path)
    if not csv_path.is_absolute():
        csv_path = ROOT / csv_path
    groups: dict[int, list[FrenchPointerVariant]] = {}
    seen_refs: set[int] = set()
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {
            "main_offset_hex",
            "pointer_reference_hex",
            "fr_text",
            "review_status",
        }
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(
                f"catalogue variantes FR invalide: {reader.fieldnames!r}"
            )
        for line_number, row in enumerate(reader, start=2):
            status = (row.get("review_status") or "").strip().casefold()
            if status != "reviewed":
                raise ValueError(
                    f"{csv_path}:{line_number}: variante non relue"
                )
            try:
                main_offset = int(row["main_offset_hex"], 0)
                reference = int(row["pointer_reference_hex"], 0)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{csv_path}:{line_number}: offset invalide"
                ) from exc
            text = (row.get("fr_text") or "").replace("\\n", "\n")
            if not text:
                raise ValueError(
                    f"{csv_path}:{line_number}: texte FR manquant"
                )
            if reference in seen_refs:
                raise ValueError(
                    f"{csv_path}:{line_number}: pointeur en double "
                    f"0x{reference:06X}"
                )
            seen_refs.add(reference)
            groups.setdefault(main_offset, []).append(
                FrenchPointerVariant(main_offset, reference, text)
            )

    actual_groups = {
        main_offset: tuple(item.pointer_reference for item in variants)
        for main_offset, variants in groups.items()
    }
    count = sum(len(variants) for variants in groups.values())
    if count != EXPECTED_FRENCH_POINTER_VARIANT_COUNT:
        raise ValueError(
            f"{csv_path}: {count} variantes, "
            f"{EXPECTED_FRENCH_POINTER_VARIANT_COUNT} attendues"
        )
    if actual_groups != EXPECTED_FRENCH_POINTER_VARIANT_REFERENCES:
        raise ValueError(
            f"{csv_path}: topologie variantes FR inattendue: "
            f"{actual_groups!r}"
        )
    return {
        main_offset: tuple(variants)
        for main_offset, variants in groups.items()
    }


def prepare_french_pointer_variant_payloads(
    data: bytes,
    row_info: Iterable[tuple[TranslationRow, int, bytes]],
    row_pointer_refs: dict[int, list[tuple[int, list[int]]]],
    variants_by_main: dict[int, tuple[FrenchPointerVariant, ...]],
    reserved_synthetic_refs: Iterable[int] = (),
) -> dict[int, bytes]:
    """Validate and detach the three secondary FR pointer variants."""

    rows = tuple(row_info)
    info_by_offset = {
        row.offset: (row, max_len, encoded)
        for row, max_len, encoded in rows
    }
    all_variant_refs = {
        variant.pointer_reference
        for variants in variants_by_main.values()
        for variant in variants
    }
    collisions = sorted(all_variant_refs & set(reserved_synthetic_refs))
    if collisions:
        raise ValueError(
            "variantes FR en conflit avec des restaurations: "
            + ", ".join(f"0x{ref:06X}" for ref in collisions)
        )

    pointer_owners: dict[int, tuple[int, int, list[int]]] = {}
    for owner_offset, targets in row_pointer_refs.items():
        for target_offset, refs in targets:
            for ref in refs:
                if ref not in all_variant_refs:
                    continue
                if ref in pointer_owners:
                    raise ValueError(
                        f"variante FR 0x{ref:06X} possédée deux fois"
                    )
                pointer_owners[ref] = (owner_offset, target_offset, refs)

    payload_by_ref: dict[int, bytes] = {}
    secondary_refs: set[int] = set()
    for main_offset, variants in variants_by_main.items():
        info = info_by_offset.get(main_offset)
        if info is None:
            raise ValueError(
                f"ligne principale variante absente 0x{main_offset:06X}"
            )
        row, max_len, main_payload = info
        source_prefix = reviewed_text_prefix_len(
            data[main_offset:main_offset + max_len]
        )
        expected_source_target = main_offset + source_prefix
        group_payloads: list[bytes] = []
        for variant in variants:
            ref = variant.pointer_reference
            if pair_for_offset(ref) != pair_for_offset(main_offset):
                raise ValueError(
                    f"variante FR 0x{ref:06X} hors paire de son texte"
                )
            source_address = int.from_bytes(data[ref:ref + 2], "little")
            source_target = offset_for_cpu_addr(
                pair_for_offset(ref),
                source_address,
                len(data),
            )
            if source_target != expected_source_target:
                raise ValueError(
                    f"variante FR 0x{ref:06X}: cible source "
                    f"0x{(source_target or 0):06X}, attendu "
                    f"0x{expected_source_target:06X}"
                )
            owner = pointer_owners.get(ref)
            if owner is None or owner[:2] != (
                main_offset,
                expected_source_target,
            ):
                raise ValueError(
                    f"variante FR 0x{ref:06X}: propriétaire inattendu "
                    f"{owner!r}"
                )
            conflicts = literal_slot_conflicts(variant.text)
            if conflicts:
                raise ValueError(
                    f"variante FR 0x{ref:06X}: ponctuation réservée"
                )
            payload = format_game_text(variant.text, row.layout)
            payload_by_ref[ref] = payload
            group_payloads.append(payload)
        if group_payloads[0] != main_payload:
            raise ValueError(
                f"variante FR primaire 0x{variants[0].pointer_reference:06X} "
                f"diffère du texte 0x{main_offset:06X}"
            )
        secondary_refs.update(
            variant.pointer_reference for variant in variants[1:]
        )

    if len(secondary_refs) != EXPECTED_FRENCH_SECONDARY_POINTER_VARIANT_COUNT:
        raise ValueError("nombre de variantes FR secondaires inattendu")

    # Detach only after every source target, owner and payload was validated.
    for ref in sorted(secondary_refs):
        pointer_owners[ref][2].remove(ref)
    return {ref: payload_by_ref[ref] for ref in sorted(secondary_refs)}


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
                    f"pointeur verifie 0x{ref:06X} et cible "
                    f"0x{target:06X} dans deux banques differentes"
                )
            actual_address = int.from_bytes(data[ref:ref + 2], "little")
            if actual_address != target_address:
                raise ValueError(
                    f"pointeur verifie 0x{ref:06X}: "
                    f"0x{actual_address:04X} au lieu de 0x{target_address:04X}"
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
                "plage de pointeurs terrain invalide: "
                f"0x{first:06X}-0x{last:06X}"
            )
        pair = pair_for_offset(first)
        if pair_for_offset(last) != pair:
            raise ValueError(
                "plage de pointeurs terrain traversant une paire PRG: "
                f"0x{first:06X}-0x{last:06X}"
            )
        for ref in range(first, last + 1, 2):
            if ref in seen_refs:
                raise ValueError(
                    f"slot terrain en double: 0x{ref:06X}"
                )
            seen_refs.add(ref)
            address = int.from_bytes(data[ref:ref + 2], "little")
            target = offset_for_cpu_addr(pair, address, len(data))
            if target is None:
                raise ValueError(
                    f"slot terrain 0x{ref:06X}: adresse CPU "
                    f"0x{address:04X} hors fenêtre PRG"
                )
            entries.setdefault(target, []).append(ref)
            slot_count += 1

    if slot_count != VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT:
        raise ValueError(
            f"{slot_count} slots terrain, "
            f"{VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT} attendus"
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
                f"sentinelle vérifiée 0x{ref:06X}: cible "
                f"0x{(actual_target or 0):06X} au lieu de "
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
                f"sentinelle vérifiée 0x{ref:06X}: propriétaire "
                f"inattendu {owners!r}"
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
                f"redirection vérifiée 0x{ref:06X}: cible "
                f"0x{(actual_target or 0):06X} au lieu de "
                f"0x{expected_target:06X}"
            )
        owners = [
            target
            for target, refs in redirected.items()
            if ref in refs
        ]
        if owners != [expected_target]:
            raise ValueError(
                f"redirection vérifiée 0x{ref:06X}: propriétaire "
                f"inattendu {owners!r}"
            )
        redirected[expected_target].remove(ref)
        if not redirected[expected_target]:
            del redirected[expected_target]
        redirected.setdefault(replacement_target, []).append(ref)

    for refs in redirected.values():
        refs.sort()
    return redirected


def verified_dialogue_restoration_payloads(
    data: bytes,
    catalogue: str | Path = PATCH_SCRIPT,
) -> dict[int, bytes]:
    """Encode and validate source dialogue slots removed or miswired in English."""
    payloads: dict[int, bytes] = {}
    errors: list[str] = []

    for ref, text in sorted(load_restorations(catalogue).items()):
        if ref < INES_HEADER_SIZE or ref + 2 > len(data):
            errors.append(f"SLOT RESTAURE HORS ROM 0x{ref:06X}")
            continue

        pair = pair_for_offset(ref)
        actual_address = int.from_bytes(data[ref:ref + 2], "little")
        actual_target = offset_for_cpu_addr(
            pair,
            actual_address,
            len(data),
        )
        redirected = VERIFIED_POINTER_REDIRECTS.get(ref)
        collapsed_target = COLLAPSED_ENGLISH_POINTER_TARGETS.get(ref)
        if collapsed_target is not None:
            if actual_target != collapsed_target:
                errors.append(
                    f"SLOT MUTUALISE 0x{ref:06X}: cible "
                    f"0x{(actual_target or 0):06X} au lieu de "
                    f"0x{collapsed_target:06X}"
                )
        elif redirected is None:
            if actual_target is not None:
                errors.append(
                    f"SLOT SUPPRIME 0x{ref:06X}: cible anglaise "
                    f"inattendue 0x{actual_target:06X}"
                )
        elif actual_target != redirected[0]:
            errors.append(
                f"SLOT MAL CABLE 0x{ref:06X}: cible "
                f"0x{(actual_target or 0):06X} au lieu de "
                f"0x{redirected[0]:06X}"
            )

        conflicts = literal_slot_conflicts(text)
        if conflicts:
            errors.append(
                f"PONCTUATION RESERVEE RESTAURATION 0x{ref:06X}: "
                + " ".join(repr(item) for item in sorted(conflicts))
            )
            continue

        encoded = format_game_text(text, DIALOGUE_LAYOUT)
        if any(value < 0x20 or value > 0x7E for value in encoded):
            errors.append(
                f"TEXTE RESTAURE NON IMPRIMABLE 0x{ref:06X}"
            )
            continue
        payloads[ref] = encoded

    if errors:
        raise ValueError(
            "restaurations chinoises invalides:\n  "
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
                    f"arene texte invalide: 0x{run_start:06X}-0x{run_end:06X}"
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
                    "arene texte differente de la base canonique: "
                    f"0x{run_start:06X}-0x{run_end:06X}"
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
                "reconstruction interne du sous-ensemble impossible"
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










def read_translation_csv(path: str | Path) -> list[TranslationRow]:
    rows: list[TranslationRow] = []
    with (ROOT / path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=2):
            if row.get("record_type", "MAIN") == "RESTORED":
                continue
            raw_offset = row.get("offset_hex") or row.get("offset")
            if not raw_offset:
                raise ValueError(f"Ligne {index}: offset_hex manquant")
            offset = int(raw_offset, 16) if raw_offset.lower().startswith("0x") else int(raw_offset)

            text = (
                row.get("fr_text")
                or row.get("french")
                or row.get("french_text")
                or row.get("translation")
                or ""
            )
            text = text.replace("\\n", "\n").replace("\\r", "\r")

            raw_max = row.get("max_len") or row.get("length") or ""
            max_len = int(raw_max) if str(raw_max).strip() else None
            layout = (row.get("layout") or "").strip()
            if layout not in SUPPORTED_LAYOUTS:
                raise ValueError(
                    f"Ligne {index}: layout inconnu {layout!r}"
                )
            rows.append(TranslationRow(offset, text, max_len, layout))
    return rows






def command_build_repacked(args: argparse.Namespace) -> int:
    original = read_bytes(args.input_rom)
    rom = bytearray(original)
    move_label_catalog = resolve_move_label_catalog(
        getattr(args, "move_labels_csv", ""),
    )
    move_label_specs = load_french_move_label_specs(move_label_catalog)
    pointer_variants = load_french_pointer_variants(
        getattr(
            args,
            "pointer_variants_csv",
            DEFAULT_FRENCH_POINTER_VARIANTS,
        )
    )
    rows = read_translation_csv(args.csv)
    restoration_payloads = verified_dialogue_restoration_payloads(original, args.csv)

    row_info: list[tuple[TranslationRow, int, bytes]] = []
    max_len_by_offset: dict[int, int] = {}
    preflight_errors: list[str] = []
    seen_offsets: set[int] = set()
    original_hash = sha256(original)
    if original_hash != TRANSLATION_BASE_SHA256:
        preflight_errors.append(
            "ROM DE BASE NON CANONIQUE: "
            f"{original_hash} au lieu de {TRANSLATION_BASE_SHA256}"
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
                f"OFFSET EN DOUBLE 0x{row.offset:06X}"
            )
        seen_offsets.add(row.offset)

        if row.offset < INES_HEADER_SIZE or row.offset >= len(original):
            preflight_errors.append(
                f"OFFSET HORS ROM 0x{row.offset:06X}"
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
                    f"OFFSET INTERIEUR A UN RECORD GRAPHIQUE "
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
                    f"LONGUEUR SOURCE INCOHERENTE 0x{row.offset:06X}: "
                    f"CSV={row.max_len}, ROM={canonical_max_len}"
                )

        encoded = format_game_text(row.text, row.layout)
        conflicts = literal_slot_conflicts(row.text)
        if conflicts:
            preflight_errors.append(
                f"PONCTUATION RESERVEE 0x{row.offset:06X}: "
                + " ".join(repr(item) for item in sorted(conflicts))
            )
        if max_len < 1:
            preflight_errors.append(
                f"AUCUN TEXTE SOURCE 0x{row.offset:06X}"
            )
        if row.offset + max(0, max_len) > len(original):
            preflight_errors.append(
                f"PLAGE HORS ROM 0x{row.offset:06X}: {max_len} octets"
            )
        if any(
            not is_supported_repacked_text_byte(value, row.offset)
            for value in encoded
        ):
            preflight_errors.append(
                f"TEXTE NON IMPRIMABLE 0x{row.offset:06X}"
            )
        if encoded.count(BATTLE_TEXT_NEWLINE_BYTE) > 1:
            preflight_errors.append(
                f"PLUSIEURS RETOURS LIGNE COMBAT 0x{row.offset:06X}"
            )
        max_len_by_offset[row.offset] = max_len
        row_info.append((row, max_len, encoded))

    if not rows:
        preflight_errors.append("CSV SANS TRADUCTION")

    if preflight_errors:
        print("Build repack complet par pointeurs: ECHEC PRELIMINAIRE")
        print(f"- CSV : {args.csv}")
        print(f"- Erreurs : {len(preflight_errors)}")
        for error in preflight_errors[:40]:
            print(f"  {error}")
        if len(preflight_errors) > 40:
            print(f"  ... et {len(preflight_errors) - 40} de plus")
        print("- Aucun artefact ecrit.")
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
                f"PLAGE TRADUITE DANS RECORD GRAPHIQUE NON DECLARE "
                f"0x{row.offset:06X}"
            )

    if preflight_errors:
        print("Build repack complet par pointeurs: ECHEC GLYPHES")
        print(f"- CSV : {args.csv}")
        print(f"- Erreurs : {len(preflight_errors)}")
        for error in preflight_errors[:40]:
            print(f"  {error}")
        print("- Aucun artefact ecrit.")
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
            "conflit dans les pointeurs verifies: "
            + repr(skipped_verified_pointers[:5])
        )
    if skipped_field_pointers:
        raise ValueError(
            "conflit dans les pointeurs terrain verifies: "
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
    field_pointer_entries = apply_verified_pointer_redirects(
        original,
        field_pointer_entries,
    )
    if (
        len(field_pointer_entries)
        != VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS
    ):
        raise ValueError(
            f"{len(field_pointer_entries)} cibles terrain après "
            "redirection, "
            f"{VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS} "
            "attendues"
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
            "slots restaurés en conflit avec des textes source: "
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
                    f"POINTEUR DANS TAIL CODE 0x{pointer_offset:06X} "
                    f"vers 0x{target_offset:06X}"
                )
            if intersects_spans(
                pointer_offset,
                pointer_offset + 2,
                glyph_spans,
            ):
                protected_glyph_errors.append(
                    f"POINTEUR DANS RECORD GLYPHIQUE "
                    f"0x{pointer_offset:06X} vers 0x{target_offset:06X}"
                )

    row_pointer_refs = assign_pointer_targets_to_rows(
        row_info,
        pointer_entries,
    )
    pointer_variant_payloads = prepare_french_pointer_variant_payloads(
        original,
        row_info,
        row_pointer_refs,
        pointer_variants,
        restoration_refs | translated_offsets,
    )

    # A graphical payload must own a physically independent allocator root.
    # Ordinary suffix pooling remains valid for text but not for the final
    # two-byte graphical codes, so every selected move receives a binary
    # marker that cannot be the suffix of another payload.
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
                    "plusieurs attaques graphiques partagent la même ligne "
                    f"source 0x{row.offset:06X}: {owned!r}"
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
                "attaques graphiques sans ligne allouable: "
                + ", ".join(str(index) for index in missing_move_reservations)
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
                    f"CIBLE TERRAIN 0x{target:06X} POSSÉDÉE PAR "
                    f"0x{row.offset:06X} SANS LAYOUT {DIALOGUE_LAYOUT}"
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
            "Build repack complet par pointeurs: "
            "ECHEC PROPRIÉTÉ DES CIBLES TERRAIN"
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
                f"  0x{target:06X}: propriétaires "
                + ", ".join(
                    f"0x{owner:06X}" for owner in owners
                )
            )
        for error in preflight_errors:
            print(f"  {error}")
        print("- Aucun artefact ecrit.")
        return 1

    graphical_target_errors = graphical_pointer_target_conflicts(
        row_pointer_refs,
        translated_glyph_starts,
    )
    if graphical_target_errors:
        print("Build repack complet par pointeurs: ECHEC CIBLES GRAPHIQUES")
        for error in graphical_target_errors:
            print(f"  {error}")
        print("- Aucun artefact ecrit.")
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
            "réservations graphiques sans record source repackable: "
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
            "réservations graphiques en chevauchement avec des données "
            "protégées: "
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
        f"PAS DE PLACE 0x{offset:06X}: "
        f"{size} octets necessaires dans paire {pair}"
        for offset, size, pair in raw_allocation_failures
    ]
    candidate_offsets.difference_update(
        offset
        for offset, _, _ in raw_allocation_failures
    )

    # Turn any future allocator regression into a deterministic preflight
    # failure instead of allowing one graphical record to overwrite another.
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
                    f"RESERVATION GRAPHIQUE 0x{source_offset:06X} "
                    f"allouee 0x{graphic_start:06X}-0x{graphic_end:06X} "
                    f"chevauche 0x{other_offset:06X} alloue "
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
                f"ALLOCATION DANS TAIL CODE 0x{row.offset:06X}: "
                f"0x{new_offset:06X}-0x{allocation_end:06X}"
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
                f"RESTAURATION DANS TAIL CODE 0x{ref:06X}: "
                f"0x{new_offset:06X}-0x{allocation_end:06X}"
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
                f"VARIANTE FR DANS TAIL CODE 0x{ref:06X}: "
                f"0x{new_offset:06X}-0x{allocation_end:06X}"
            )

    fatal_errors = [
        *allocation_failures,
        *graphic_allocation_overlaps,
        *protected_tail_errors,
        *protected_glyph_errors,
    ]
    if fixed_overflows:
        fatal_errors.append(
            f"{len(fixed_overflows)} TEXTE(S) FIXE(S) TROP LONG(S)"
        )
    if skipped_contextual_pointers:
        fatal_errors.append(
            f"{len(skipped_contextual_pointers)} POINTEUR(S) "
            "CONTEXTUEL(S) AMBIGU(S)"
        )

    if fatal_errors:
        print("Build repack complet par pointeurs: ECHEC PREFLIGHT")
        print(f"- CSV : {args.csv}")
        print(f"- Echecs allocation : {len(allocation_failures)}")
        print(
            "- Chevauchements réservations graphiques : "
            f"{len(graphic_allocation_overlaps)}"
        )
        print(f"- Textes fixes trop longs : {len(fixed_overflows)}")
        print(f"- Violations tails code : {len(protected_tail_errors)}")
        print(
            "- Violations records glyphiques : "
            f"{len(protected_glyph_errors)}"
        )
        print(
            "- Pointeurs contextuels ambigus : "
            f"{len(skipped_contextual_pointers)}"
        )
        print(f"- Erreurs fatales : {len(fatal_errors)}")
        for error in fatal_errors[:40]:
            print(f"  {error}")
        if len(fatal_errors) > 40:
            print(f"  ... et {len(fatal_errors) - 40} de plus")
        for item in fixed_overflows[:20]:
            print(
                f"  TRONCATURE INTERDITE {item['offset_hex']}: "
                f"{item['fr_len']} > {item['max_len']}"
            )
        print("- Aucun artefact ecrit.")
        return 1

    applied = 0

    for row, max_len, _ in row_info:
        if row.offset in allocations and max_len > 0:
            rom[row.offset:row.offset + max_len + 1] = b"\0" * (max_len + 1)

    for row, max_len, encoded in row_info:
        if max_len < 1:
            warnings.append(f"SKIP 0x{row.offset:06X}: aucun texte source")
            continue

        if row.offset in allocations:
            new_offset = allocations[row.offset]
            rom[new_offset:new_offset + len(encoded)] = encoded
            rom[new_offset + len(encoded)] = 0x0D
            updated_pointer_offsets: set[int] = set()
            for target_offset, pointer_offsets in row_pointer_refs[row.offset]:
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
                    collapse_ascii_padding_interior=True,
                )
                new_address = cpu_addr_for_offset(new_target_offset)
                for pointer_offset in pointer_offsets:
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

    pointer_variants_written: list[tuple[int, int, int]] = []
    for ref, encoded in sorted(pointer_variant_payloads.items()):
        new_offset = allocations[ref]
        rom[new_offset:new_offset + len(encoded)] = encoded
        rom[new_offset + len(encoded)] = 0x0D
        rom[ref:ref + 2] = cpu_addr_for_offset(new_offset).to_bytes(
            2,
            "little",
        )
        pointer_variants_written.append((ref, new_offset, len(encoded)))

    for offset in sorted(unsafe_candidates):
        warnings.append(f"NON DEPLACE 0x{offset:06X}: chevauchement avec donnees protegees")

    battle_menu_chr_expanded = expand_battle_menu_chr_slots_for_fuite(
        original,
        rom,
        normalized_by_offset.get(BATTLE_RUN_LABEL_OFFSET),
    )
    battle_message_clear_expanded = expand_battle_message_clear_width(
        original,
        rom,
    )
    battle_text_newline_control_patched = patch_battle_text_newline_control(
        original,
        rom,
    )
    fixed_antidote_patched = patch_fixed_item_list_antidote(
        original,
        rom,
    )
    status_already_control_patched = patch_status_already_message_control(
        original,
        rom,
    )

    output_rom = ROOT / args.output_rom
    output_ips = ROOT / args.output_ips
    font_export_directory, font_changed = apply_french_font_and_export(
        original,
        rom,
        output_rom,
    )
    move_label_report = apply_french_move_label_graphics(
        original,
        rom,
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
    print("Build repack complet par pointeurs")
    print(f"- CSV : {args.csv}")
    print(f"- Tables/pointeurs detectes : {sum(len(refs) for refs in pointer_entries.values())} refs vers {len(pointer_entries)} cibles")
    print(f"- Entrees appliquees : {applied}")
    print(f"- Textes repackes : {len(relocated)}")
    print(f"- Dialogues chinois restaures : {len(restored)}")
    print(
        "- Variantes FR par pointeur : "
        f"{len(pointer_variants_written)} secondaires"
    )
    print(f"- Textes fixes encore tronques : {len(fixed_overflows)}")
    print(f"- Octets modifies : {changed}")
    print(f"- ROM : {output_rom}")
    print(f"- IPS : {output_ips}")
    print(f"- Glyphes français : {font_changed} octets modifiés")
    if move_label_report is not None:
        print(
            "- Attaques graphiques deux lignes : "
            f"{move_label_report.applied_count} "
            f"({len(move_label_report.used_even_slots)} cellules)"
        )
        print(f"- Plan attaques : {move_label_catalog}")
        if move_label_report_path:
            print(f"- Rapport attaques : {move_label_report_resolved}")
    print(
        "- Zone CHR menu combat étendue pour Fuite : "
        + ("OUI" if battle_menu_chr_expanded else "NON")
    )
    print(
        "- Effacement fenêtre combat étendu à 25 cases : "
        + ("OUI" if battle_message_clear_expanded else "DÉJÀ PRÉSENT")
    )
    print(
        "- Contrôle retour ligne du texte combat installé : "
        + ("OUI" if battle_text_newline_control_patched else "DÉJÀ PRÉSENT")
    )
    print(
        "- Antidote abrégé dans la table objets fixe : "
        + ("OUI" if fixed_antidote_patched else "DÉJÀ PRÉSENT")
    )
    print(
        "- Message autonome pour statut inchangé : "
        + ("OUI" if status_already_control_patched else "DÉJÀ PRÉSENT")
    )
    print(f"- Export CHR police : {font_export_directory}")
    if args.fixed_overflow_output:
        print(f"- Rapport textes fixes trop longs : {ROOT / args.fixed_overflow_output}")
    print(f"- Avertissements : {len(warnings)}")

    if relocated:
        print("- Exemples de repack :")
        for old_offset, new_offset, length, ref_count in relocated[:15]:
            print(
                f"  0x{old_offset:06X} -> 0x{new_offset:06X} "
                f"({length} caracteres, {ref_count} pointeur(s))"
            )
        if len(relocated) > 15:
            print(f"  ... et {len(relocated) - 15} de plus")

    if restored:
        print("- Exemples de restaurations chinoises :")
        for ref, new_offset, length in restored[:15]:
            print(
                f"  slot 0x{ref:06X} -> 0x{new_offset:06X} "
                f"({length} caracteres)"
            )
        if len(restored) > 15:
            print(f"  ... et {len(restored) - 15} de plus")

    if pointer_variants_written:
        print("- Variantes FR secondaires :")
        for ref, new_offset, length in pointer_variants_written:
            print(
                f"  slot 0x{ref:06X} -> 0x{new_offset:06X} "
                f"({length} caracteres)"
            )

    if warnings:
        for warning in warnings[:25]:
            print(f"  {warning}")
        if len(warnings) > 25:
            print(f"  ... et {len(warnings) - 25} de plus")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Moteur de construction français (utiliser build.py).")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("build-repacked")
    cmd.add_argument("--csv", default=PATCH_SCRIPT)
    cmd.add_argument("--input-rom", default=TRANSLATION_BASE_ROM)
    cmd.add_argument("--output-rom", default="build/fr/core.nes")
    cmd.add_argument("--output-ips", default="build/fr/core.ips")
    cmd.add_argument("--fixed-overflow-output", default="build/fr/overflow.csv")
    cmd.add_argument("--move-labels-csv", default=str(DEFAULT_MOVE_LABEL_CATALOG))
    cmd.add_argument("--move-label-report", default="")
    cmd.add_argument("--pointer-variants-csv", default=str(DEFAULT_FRENCH_POINTER_VARIANTS))
    for name,value,kind in (("min-pointer-run",5,int),("min-known-ratio",0.4,float),("min-known-count",3,int),("min-free-run",32,int),("context-pointer-window",32,int),("min-context-pointers",0,int)):
        cmd.add_argument("--"+name,default=value,type=kind)
    cmd.add_argument("--only-overflow",action="store_true")
    cmd.set_defaults(func=command_build_repacked)
    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
