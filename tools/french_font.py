#!/usr/bin/env python3
"""French one-byte codec and editable ASCII-font patch for NJ046.

The English patch loads a 96-tile 8x8 ASCII font from file offset 0x078210.
Every text byte from 0x20 through 0x7E selects one font tile. ``@`` was already
redrawn as ``é`` by the English patch.

The French build gives every accented letter that occurs in the canonical
translation its own one-byte glyph.  The ``œ`` ligature deliberately remains
the two-column fallback ``oe`` so that all ASCII letters stay available for
player-entered names. Slots are otherwise drawn only from characters absent
from the final French corpus and its invariant runtime strings. The one
exception is ``"``: it occurs in two English source records, but both records
are translated without quotes before the French font is installed. Literal
uses of every repurposed slot are rejected by the build preflight.
"""

from __future__ import annotations

import csv
import hashlib
import io
import unicodedata
from pathlib import Path
from typing import MutableSequence


ASCII_FONT_OFFSET = 0x078210
ASCII_FONT_FIRST_CODE = 0x20
ASCII_FONT_TILE_COUNT = 96
ASCII_FONT_TILE_SIZE = 16
ASCII_FONT_SIZE = ASCII_FONT_TILE_COUNT * ASCII_FONT_TILE_SIZE

# One-byte assignments for every French-specific character used by the
# canonical corpus.  Uppercase È/Ê do not currently occur and intentionally
# share the lowercase glyph. Both œ variants stay two-column fallbacks.
# Every other mapped value is a distinct native glyph.
FRENCH_CHAR_MAP: dict[str, str] = {
    "é": "@",
    "É": "*",
    "à": "{",
    "À": '"',
    "è": "|",
    "È": "|",
    "ê": "}",
    "Ê": "}",
    "Â": "#",
    "Ç": ";",
    "Î": "<",
    "â": "~",
    "ç": "[",
    "î": "\\",
    "ï": "]",
    "ô": "^",
    "ù": "_",
    "û": "`",
    "œ": "oe",
    "Œ": "OE",
}

REPURPOSED_ASCII_CODES = frozenset(
    ord(value)
    for value in FRENCH_CHAR_MAP.values()
    if len(value) == 1
)
FRENCH_PATCHED_ASCII_CODES = frozenset(
    {
        ord('"'),
        ord("#"),
        ord("*"),
        ord(";"),
        ord("<"),
        ord("["),
        ord("\\"),
        ord("]"),
        ord("^"),
        ord("_"),
        ord("`"),
        ord("{"),
        ord("|"),
        ord("}"),
        ord("~"),
    }
)
FRENCH_NATIVE_GLYPH_CODES = FRENCH_PATCHED_ASCII_CODES | {ord("@")}
FRENCH_GLYPH_LABELS = {
    ord('"'): ("A_grave_upper", "À"),
    ord("#"): ("A_circumflex_upper", "Â"),
    ord("*"): ("E_acute_upper", "É"),
    ord(";"): ("C_cedilla_upper", "Ç"),
    ord("<"): ("I_circumflex_upper", "Î"),
    ord("@"): ("e_acute", "é"),
    ord("["): ("c_cedilla", "ç"),
    ord("\\"): ("i_circumflex", "î"),
    ord("]"): ("i_diaeresis", "ï"),
    ord("^"): ("o_circumflex", "ô"),
    ord("_"): ("u_grave", "ù"),
    ord("`"): ("u_circumflex", "û"),
    ord("{"): ("a_grave", "à"),
    ord("|"): ("e_grave", "è"),
    ord("}"): ("e_circumflex", "ê"),
    ord("~"): ("a_circumflex", "â"),
}

if set(FRENCH_GLYPH_LABELS) != FRENCH_NATIVE_GLYPH_CODES:
    raise AssertionError("les libellés et les slots de glyphes divergent")
if any(chr(code).isalpha() for code in FRENCH_PATCHED_ASCII_CODES):
    raise AssertionError("une lettre ASCII ne doit jamais être réaffectée")


def literal_slot_conflicts(text: str) -> set[str]:
    """Return literal ASCII characters whose font slots are repurposed."""
    return {
        character
        for character in text
        if ord(character) in REPURPOSED_ASCII_CODES
    }


def encode_game_text(text: str) -> bytes:
    """Encode French source text into the ROM's printable one-byte charset."""
    mapped = "".join(FRENCH_CHAR_MAP.get(character, character) for character in text)
    # Canonical decomposition preserves the deliberate fallback used by
    # ordinary accented Latin letters (for example ``ë`` -> ``e``), while
    # refusing compatibility substitutions such as NBSP -> ASCII space.
    # Unsupported punctuation and symbols must stop the build instead of
    # becoming an indistinguishable question-mark glyph in the ROM.
    normalized = unicodedata.normalize("NFD", mapped)
    ascii_text = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return ascii_text.encode("ascii", errors="strict")


def decode_game_text(data: bytes) -> str:
    """Decode printable game bytes to their semantic French characters."""
    replacements = {
        code: character
        for code, (_, character) in FRENCH_GLYPH_LABELS.items()
    }
    return "".join(
        replacements.get(
            value,
            chr(value) if 0x20 <= value <= 0x7E else "�",
        )
        for value in data
    )


def _tile_offset(character: str) -> int:
    if len(character) != 1:
        raise ValueError("un seul caractère ASCII est attendu")
    code = ord(character)
    if not ASCII_FONT_FIRST_CODE <= code < (
        ASCII_FONT_FIRST_CODE + ASCII_FONT_TILE_COUNT
    ):
        raise ValueError(f"caractère hors police ASCII: {character!r}")
    return (code - ASCII_FONT_FIRST_CODE) * ASCII_FONT_TILE_SIZE


def _base_tile(font: bytes, character: str) -> bytearray:
    start = _tile_offset(character)
    tile = bytearray(font[start : start + ASCII_FONT_TILE_SIZE])
    if len(tile) != ASCII_FONT_TILE_SIZE:
        raise ValueError("police ASCII tronquée")
    return tile


def _monochrome_tile(rows: bytes | bytearray) -> bytes:
    """Build the 2bpp tile shape consumed by the game's text renderer.

    Runtime tracing proves that the renderer reads the first eight bitmap
    bytes and emits the two enlarged CHR tiles itself.  Keeping plane 1 clear
    matches the complete source ASCII font and makes that contract explicit.
    """
    if len(rows) != 8:
        raise ValueError("un glyphe monochrome doit contenir huit lignes")
    return bytes(rows) + b"\0" * 8


def _accent_rows(accent: str) -> tuple[int, int]:
    if accent == "acute":
        return 0x30, 0xC0
    if accent == "grave":
        return 0x0C, 0x03
    if accent == "circumflex":
        return 0x18, 0x24
    if accent == "diaeresis":
        return 0x24, 0x00
    raise ValueError(f"accent inconnu: {accent}")


def _lower_accent(font: bytes, base: str, accent: str) -> bytes:
    rows = _base_tile(font, base)[:8]
    # The lowercase body begins on row 3 in this font, leaving a clean
    # two-row accent area.  ``i`` is special: rows 0-2 replace its old dot.
    rows[0:3] = b"\0\0\0"
    first, second = _accent_rows(accent)
    if accent in {"acute", "grave"}:
        rows[1], rows[2] = first, second
    else:
        rows[0], rows[1] = first, second
    return _monochrome_tile(rows)


def _upper_accent(font: bytes, base: str, accent: str) -> bytes:
    """Fit a true uppercase body and a two-row accent in one 8x8 tile."""
    source = list(_base_tile(font, base)[:8])
    body = source[1:]
    # The stock uppercase A/E/I use seven rows and contain at least one
    # adjacent duplicate. Removing one duplicate preserves their silhouette
    # while freeing two complete rows for the accent.
    for index in range(1, len(body)):
        if body[index] == body[index - 1]:
            del body[index]
            break
    if len(body) != 6:
        raise ValueError(
            f"le glyphe majuscule {base!r} ne peut pas être comprimé"
        )
    first, second = _accent_rows(accent)
    return _monochrome_tile(bytes([first, second, *body]))


def _c_cedilla(font: bytes) -> bytes:
    """Move the five-row lowercase c up and add a two-row cedilla."""
    source = _base_tile(font, "c")[:8]
    body = source[3:8]
    return _monochrome_tile(bytes([0x00, *body, 0x10, 0x20]))


def _upper_c_cedilla(font: bytes) -> bytes:
    """Compress uppercase C by one repeated row and append a cedilla."""
    body = list(_base_tile(font, "C")[1:8])
    for index in range(1, len(body)):
        if body[index] == body[index - 1]:
            del body[index]
            break
    if len(body) != 6:
        raise ValueError("le glyphe majuscule 'C' ne peut pas être comprimé")
    return _monochrome_tile(bytes([*body, 0x10, 0x20]))


def french_font_tiles(font: bytes) -> dict[int, bytes]:
    """Return ``{ASCII byte: 16-byte NES tile}`` for every French glyph."""
    if len(font) != ASCII_FONT_SIZE:
        raise ValueError(
            f"police ASCII de {len(font)} octets, attendu {ASCII_FONT_SIZE}"
        )
    tiles = {
        ord('"'): _upper_accent(font, "A", "grave"),
        ord("#"): _upper_accent(font, "A", "circumflex"),
        ord("*"): _upper_accent(font, "E", "acute"),
        ord(";"): _upper_c_cedilla(font),
        ord("<"): _upper_accent(font, "I", "circumflex"),
        ord("["): _c_cedilla(font),
        ord("\\"): _lower_accent(font, "i", "circumflex"),
        ord("]"): _lower_accent(font, "i", "diaeresis"),
        ord("^"): _lower_accent(font, "o", "circumflex"),
        ord("_"): _lower_accent(font, "u", "grave"),
        ord("`"): _lower_accent(font, "u", "circumflex"),
        ord("{"): _lower_accent(font, "a", "grave"),
        ord("|"): _lower_accent(font, "e", "grave"),
        ord("}"): _lower_accent(font, "e", "circumflex"),
        ord("~"): _lower_accent(font, "a", "circumflex"),
    }
    if set(tiles) != FRENCH_PATCHED_ASCII_CODES:
        raise AssertionError("la table de tuiles et le codec divergent")
    if any(len(tile) != ASCII_FONT_TILE_SIZE for tile in tiles.values()):
        raise AssertionError("une tuile française n'a pas 16 octets")
    return tiles


def patch_french_font(rom: MutableSequence[int]) -> dict[int, bytes]:
    """Patch the French glyph tiles in a mutable full ROM image."""
    font_end = ASCII_FONT_OFFSET + ASCII_FONT_SIZE
    if len(rom) < font_end:
        raise ValueError("ROM trop courte pour contenir la police ASCII")
    original_font = bytes(rom[ASCII_FONT_OFFSET:font_end])
    tiles = french_font_tiles(original_font)
    for code, tile in tiles.items():
        start = ASCII_FONT_OFFSET + _tile_offset(chr(code))
        rom[start : start + ASCII_FONT_TILE_SIZE] = tile
    return tiles


def extract_ascii_font(rom: bytes) -> bytes:
    end = ASCII_FONT_OFFSET + ASCII_FONT_SIZE
    if len(rom) < end:
        raise ValueError("ROM trop courte pour contenir la police ASCII")
    return rom[ASCII_FONT_OFFSET:end]


def export_font_pair(
    before_rom: bytes,
    after_rom: bytes,
    output_directory: str | Path,
) -> tuple[Path, Path]:
    """Export before/after ``.chr`` files for manual pixel retouching."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    before_path = output / "ui_ascii_font_before.chr"
    after_path = output / "ui_ascii_font_french.chr"
    before_font = extract_ascii_font(before_rom)
    after_font = extract_ascii_font(after_rom)
    before_path.write_bytes(before_font)
    after_path.write_bytes(after_font)

    glyph_directory = output / "glyphs"
    glyph_directory.mkdir(parents=True, exist_ok=True)
    glyph_rows = [
        [
            "ascii_code",
            "source_slot",
            "french_character",
            "file_offset",
            "tile_index",
            "patched_by_french_build",
            "filename",
            "sha256",
        ]
    ]
    all_glyphs = bytearray()
    patched_glyphs = bytearray()
    legacy_three = bytearray()
    for code in sorted(FRENCH_NATIVE_GLYPH_CODES):
        tile_offset = _tile_offset(chr(code))
        tile = after_font[
            tile_offset : tile_offset + ASCII_FONT_TILE_SIZE
        ]
        label, character = FRENCH_GLYPH_LABELS[code]
        filename = f"glyph_{code:02X}_{label}.chr"
        (glyph_directory / filename).write_bytes(tile)
        all_glyphs.extend(tile)
        if code in FRENCH_PATCHED_ASCII_CODES:
            patched_glyphs.extend(tile)
        if code in {ord("{"), ord("|"), ord("}")}:
            legacy_three.extend(tile)
        glyph_rows.append(
            [
                f"0x{code:02X}",
                chr(code),
                character,
                f"0x{ASCII_FONT_OFFSET + tile_offset:06X}",
                str(code - ASCII_FONT_FIRST_CODE),
                str(code in FRENCH_PATCHED_ASCII_CODES).lower(),
                filename,
                hashlib.sha256(tile).hexdigest(),
            ]
        )
    (
        glyph_directory / "french_glyphs_all_16tiles.chr"
    ).write_bytes(all_glyphs)
    (
        glyph_directory / "french_glyphs_patched_15tiles.chr"
    ).write_bytes(patched_glyphs)
    # Backward-compatible hand-retouch pack used by earlier builds.
    (glyph_directory / "french_glyphs_3tiles.chr").write_bytes(legacy_three)
    manifest_buffer = io.StringIO(newline="")
    writer = csv.writer(manifest_buffer, lineterminator="\n")
    writer.writerows(glyph_rows)
    (glyph_directory / "glyph_tiles_manifest.csv").write_text(
        manifest_buffer.getvalue(),
        encoding="utf-8",
    )

    # Reuse the project's dependency-free BMP renderer. The .chr files remain
    # the canonical editable assets; these sheets are quick visual previews.
    from tools.title_screen_tools import render_chr

    render_chr(
        before_font,
        output / "ui_ascii_font_before_sheet.bmp",
        tiles_per_row=16,
        scale=4,
    )
    render_chr(
        after_font,
        output / "ui_ascii_font_french_sheet.bmp",
        tiles_per_row=16,
        scale=4,
    )
    render_chr(
        bytes(all_glyphs),
        glyph_directory / "french_glyphs_all_16tiles_sheet.bmp",
        tiles_per_row=8,
        scale=8,
    )
    render_chr(
        bytes(patched_glyphs),
        glyph_directory / "french_glyphs_patched_15tiles_sheet.bmp",
        tiles_per_row=8,
        scale=8,
    )
    render_chr(
        bytes(legacy_three),
        glyph_directory / "french_glyphs_3tiles_sheet.bmp",
        tiles_per_row=3,
        scale=8,
    )
    return before_path, after_path
