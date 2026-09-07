#!/usr/bin/env python3
"""
Tools for analyzing the Pokemon Yellow NES NJ046 title screen.

The ROM uses CHR-RAM. Title graphics visible in FCEUX are stored uncompressed
in PRG bank 28. Offsets below include the iNES file header.

Commands:
  python tools/title_screen_tools.py extract-state
  python tools/title_screen_tools.py scan-rom
  python tools/title_screen_tools.py render-rom



"""

from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROM_DIR.parent

ENGLISH_ROM = ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
ENGLISH_ROM_SHA256 = (
    "d5c308b5862ccbe4647d4255a11bb0f1"
    "cb6817c4b107feac112509d658a9943b"
)
FRENCH_ROM = ROM_DIR / "Pokemon_Jaune_FR.nes"
ENGLISH_BASE_ROM = ENGLISH_ROM
ENGLISH_BASE_ROM_SHA256 = ENGLISH_ROM_SHA256
ENGLISH_TITLE_CREDITS = "LUIGA2009, ZLADE, CHPEXO"
PATCHED_TITLE_ROM = ROM_DIR / "Pokemon_Jaune_FR_title.nes"
PATCHED_TITLE_IPS = ROM_DIR / "Pokemon_Jaune_FR_title.ips"
DEFAULT_STATE = (
    PROJECT_DIR
    / "fceux-2.6.6-win64"
    / "fcs"
    / "Pokemon Yellow English 9-23-2015.bak.fc0"
)
DEFAULT_OUT = ROM_DIR / "tools" / "analysis" / "title"

# Source addresses observed in bank 28. CPU bank is mapped at $8000.
TITLE_BANK_FILE_BASE = 0x070010
TITLE_PT1_FILE = 0x0705AB  # PPU pattern table $1000, 4096 bytes
TITLE_PT0_FILE = 0x070FFB  # PPU pattern table $0000, 4096 bytes
TITLE_NT_FILE = 0x071A0B   # nametable, 1024 bytes

# The player menu uses two separate 4 KiB CHR blocks. The first contains
# POKEDEX/POKEMON/ITEMS/Ash/HMs/SAVE labels; its visible nametable is
# stored uncompressed slightly later in the same bank.
PLAYER_MENU_PT0_FILE = 0x0288D5
PLAYER_MENU_PT1_FILE = 0x13B17B
PLAYER_MENU_NT_FILE = 0x0295D5
PLAYER_MENU_NT_VISIBLE_SIZE = 32 * 30

# The mapper 163 title screen swaps the two physical 4 KiB CHR-RAM halves at
# scanline 127.  NEW/LOAD are therefore stored in the second source half even
# though the background selects PPU pattern table $0000.
MENU_NEW_TILEMAP_FILE = 0x06E401
MENU_LOAD_TILEMAP_FILE = 0x06E417
MENU_TILE_IDS = (0x30, 0x31, 0x32, 0x40, 0x41, 0x42, 0x43)
TITLE_LOGO_TILE_IDS = tuple(range(0x51, 0x56))
ENGLISH_CREDIT_TILE_IDS = (
    0x66,
    0x78,
    0x8C,
    *range(0x91, 0x9E),
    *range(0xA0, 0xA3),
    0x5F,
)
TITLE_MENU_CURSOR_TILE_ID = 0xA3
ENGLISH_CREDIT_NT_ROW = 23
ENGLISH_CREDIT_NT_COLUMN = 6

# Compact 3x5 title-credit alphabet.  One blank column follows every glyph,
# The credit uses twenty tile IDs that do not carry live title graphics.  Tile
# $A3 is deliberately excluded: it is the Poké Ball cursor sprite and does not
# appear in the background nametables.  The final blank cell uses the canonical
# blank tile $5F instead.
TITLE_CREDIT_FONT_3X5 = {
    " ": ("0000",) * 6,
    ",": ("0000", "0000", "0000", "0000", "0110", "0100"),
    "0": ("0110", "1001", "1011", "1101", "1001", "0110"),
    "2": ("1110", "0001", "0010", "0100", "1000", "1111"),
    "9": ("0110", "1001", "0111", "0001", "0010", "1100"),
    "A": ("0110", "1001", "1001", "1111", "1001", "1001"),
    "C": ("0111", "1000", "1000", "1000", "1000", "0111"),
    "D": ("1110", "1001", "1001", "1001", "1001", "1110"),
    "E": ("1111", "1000", "1000", "1110", "1000", "1111"),
    "G": ("0111", "1000", "1000", "1011", "1001", "0111"),
    "H": ("1001", "1001", "1001", "1111", "1001", "1001"),
    "I": ("1111", "0110", "0110", "0110", "0110", "1111"),
    "L": ("1000", "1000", "1000", "1000", "1000", "1111"),
    "O": ("0110", "1001", "1001", "1001", "1001", "0110"),
    "P": ("1110", "1001", "1001", "1110", "1000", "1000"),
    "U": ("1001", "1001", "1001", "1001", "1001", "0110"),
    "X": ("1001", "1001", "0110", "0110", "1001", "1001"),
    "Z": ("1111", "0001", "0010", "0100", "1000", "1111"),
}

# Exact 5-row glyph shapes observed in 2015 English reference' original
# ``LUGIA2009,CHPEXO`` credit.  These are deliberately kept separate from the
# fallback alphabet above: the English release composes its credits from this
# original title font, preserving the same chunky proportions and color.
ORIGINAL_TITLE_CREDIT_GLYPHS = {
    " ": ("000",) * 5,
    ",": ("0", "0", "0", "1", "1"),
    "0": ("111", "101", "101", "101", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "A": ("111", "101", "111", "101", "101"),
    "C": ("111", "100", "100", "100", "111"),
    "E": ("111", "100", "110", "100", "111"),
    "G": ("111", "100", "101", "101", "111"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "L": ("100", "100", "100", "100", "111"),
    "O": ("111", "101", "101", "101", "111"),
    "P": ("110", "101", "110", "100", "100"),
    "U": ("101", "101", "101", "101", "111"),
    "X": ("101", "101", "010", "101", "101"),
    # Z is derived from the original 2's diagonal; D closes the original P.
    "Z": ("111", "001", "010", "100", "111"),
    "D": ("110", "101", "101", "101", "110"),
}


def english_title_changed_offsets(
    source: bytes,
    title_reference: bytes,
    credits: str = ENGLISH_TITLE_CREDITS,
) -> set[int]:
    """Return the exact bank-14 bytes owned by the English title profile."""
    patched = bytearray(source)
    patch_english_yellow_title(patched, title_reference, credits)
    return {
        offset
        for offset, (before, after) in enumerate(zip(source, patched))
        if before != after
    }

JAUNE_TILES = [
    bytes.fromhex("1c08080848483000e3f7f7f7b7b7cfff"),
    bytes.fromhex("3844447c44444400c7bbbb83bbbbbbff"),
    bytes.fromhex("4444444444443800bbbbbbbbbbbbc7ff"),
    bytes.fromhex("4464544c44444400bb9babb3bbbbbbff"),
    bytes.fromhex("7c40407840407c0083bfbf87bfbf83ff"),
]

CONDENSED_FONT_5X6 = {
    "N": ("10001", "11001", "10101", "10011", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "01110"),
    "U": ("10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "01010", "00100"),
}


def condensed_word_tiles(word: str, tile_count: int) -> list[bytes]:
    width = tile_count * 8
    rows = ["0" * width]
    for y in range(6):
        row = "0".join(CONDENSED_FONT_5X6[letter][y] for letter in word)
        if len(row) > width:
            raise ValueError(f'{word} does not fit in {tile_count} tiles')
        rows.append(row.ljust(width, "0"))
    rows.append("0" * width)

    tiles: list[bytes] = []
    for tile_index in range(tile_count):
        plane = bytes(
            int(row[tile_index * 8 : tile_index * 8 + 8], 2)
            for row in rows
        )
        tiles.append(plane + plane)
    return tiles


MENU_FR_TILES = condensed_word_tiles("NOUV", 3) + [
    # CONT, one letter per original LOAD tile.
    bytes.fromhex("003c666060663c00003c666060663c00"),  # C
    bytes.fromhex("003c666666663c00003c666666663c00"),  # O
    bytes.fromhex("006676767e6e6600006676767e6e6600"),  # N
    bytes.fromhex("007e181818181800007e181818181800"),  # T
]

# Condensed font for graphical player-menu labels. Each glyph is 4x7 pixels;
# a light lower-right shadow reproduces the original English relief
# without exceeding the tiles already reserved by the game.
PLAYER_MENU_FONT_4X7 = {
    "A": ("0110", "1001", "1001", "1111", "1001", "1001", "1001"),
    "B": ("1110", "1001", "1001", "1110", "1001", "1001", "1110"),
    "C": ("0111", "1000", "1000", "1000", "1000", "1000", "0111"),
    "E": ("1111", "1000", "1000", "1110", "1000", "1000", "1111"),
    "H": ("1001", "1001", "1001", "1111", "1001", "1001", "1001"),
    "J": ("0011", "0001", "0001", "0001", "1001", "1001", "0110"),
    "O": ("0110", "1001", "1001", "1001", "1001", "1001", "0110"),
    "R": ("1110", "1001", "1001", "1110", "1010", "1001", "1001"),
    "S": ("0111", "1000", "1000", "0110", "0001", "0001", "1110"),
    "T": ("1111", "0110", "0110", "0110", "0110", "0110", "0110"),
    "U": ("1001", "1001", "1001", "1001", "1001", "1001", "0110"),
    "V": ("1001", "1001", "1001", "1001", "1001", "0110", "0110"),
}

PLAYER_MENU_LABELS = {
    "ITEMS": {
        "french": "OBJETS",
        "top": (0x25, 0x29, 0x2B, 0x2F),
        "bottom": (0x26, 0x2A, 0x2C, 0x30),
        "row": 10,
        "column": 14,
        "original_sha256": (
            "30c07607eb3ba22b7de500b693a75143"
            "dc83a10e4e367b195e70c2192600384a"
        ),
    },
    "ASH": {
        "french": "SACHA",
        "top": (0x31, 0x33, 0x35),
        "bottom": (0x32, 0x34, 0x36),
        "row": 14,
        "column": 15,
        "original_sha256": (
            "66c8555bee6700d01a64abe07736cc80"
            "a3c982ad9832aa00edd35888ad6d36eb"
        ),
    },
    "HMS": {
        "french": "CS",
        "top": (0x4C, 0x4E, 0x5B),
        "bottom": (0x4D, 0x4F, 0x5C),
        "row": 18,
        "column": 15,
        "original_sha256": (
            "e7fb1abb463ff6aa57c696d7b1899c4"
            "22a128a6474ab64ae7d10f1bca828270d"
        ),
    },
    "SAVE": {
        "french": "SAUVER",
        "top": (0x5D, 0x7B, 0x7D, 0x84),
        "bottom": (0x5E, 0x7C, 0x7E, 0x85),
        "row": 22,
        "column": 14,
        "original_sha256": (
            "7f5682dd0cf1f8e58954dc18b9ce78e"
            "45bafb6eea8fe39765b11b7ee7eb5a8b0"
        ),
    },
}


def encode_chr_tile(pixels: list[list[int]]) -> bytes:
    if len(pixels) != 8 or any(len(row) != 8 for row in pixels):
        raise ValueError('A CHR tile must measure exactly 8x8 pixels')

    low_plane = bytearray()
    high_plane = bytearray()
    for row in pixels:
        low = 0
        high = 0
        for color in row:
            if not 0 <= color <= 3:
                raise ValueError(f'Invalid CHR palette index: {color}')
            low = (low << 1) | (color & 1)
            high = (high << 1) | ((color >> 1) & 1)
        low_plane.append(low)
        high_plane.append(high)
    return bytes(low_plane + high_plane)


def player_menu_word_tiles(word: str, tile_count: int) -> list[bytes]:
    """Center a word in the two previously reserved CHR rows."""
    word = word.upper()
    missing = sorted(set(word) - set(PLAYER_MENU_FONT_4X7))
    if missing:
        raise ValueError(f"Missing player-menu glyph(s): {', '.join(missing)}")

    width = tile_count * 8
    glyph_width = 4
    spacing = 1
    main_width = len(word) * glyph_width + (len(word) - 1) * spacing
    # The shadow adds one pixel on the right. SACHA occupies three tiles;
    # therefore use zero letter spacing to retain a safety margin.
    if main_width + 1 > width:
        spacing = 0
        main_width = len(word) * glyph_width
    if main_width + 1 > width:
        raise ValueError(f'{word} does not fit in {tile_count} tiles')

    pixels = [[2 for _ in range(width)] for _ in range(16)]
    start_x = (width - (main_width + 1)) // 2
    start_y = 4

    glyph_pixels: list[tuple[int, int]] = []
    cursor_x = start_x
    for letter in word:
        for glyph_y, row in enumerate(PLAYER_MENU_FONT_4X7[letter]):
            for glyph_x, bit in enumerate(row):
                if bit == "1":
                    glyph_pixels.append((cursor_x + glyph_x, start_y + glyph_y))
        cursor_x += glyph_width + spacing

    # Light shadow, then dark stroke. This order prevents a letter shadow
    # from covering the next letter's main stroke.
    for x, y in glyph_pixels:
        for shadow_x, shadow_y in ((x, y + 1), (x + 1, y + 1)):
            if 0 <= shadow_x < width and 0 <= shadow_y < 16:
                pixels[shadow_y][shadow_x] = 0
    for x, y in glyph_pixels:
        pixels[y][x] = 1

    tiles: list[bytes] = []
    for tile_row in range(2):
        for tile_column in range(tile_count):
            tile_pixels = [
                row[tile_column * 8 : tile_column * 8 + 8]
                for row in pixels[tile_row * 8 : tile_row * 8 + 8]
            ]
            tiles.append(encode_chr_tile(tile_pixels))
    return tiles


def read_file(path: Path) -> bytes:
    return path.read_bytes()


def write_bmp(path: Path, width: int, height: int, rgb: bytes | bytearray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row_pad = (4 - (width * 3) % 4) % 4
    pixel_size = (width * 3 + row_pad) * height
    with path.open("wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<IHHI", 54 + pixel_size, 0, 0, 54))
        f.write(
            struct.pack(
                "<IiiHHIIiiII",
                40,
                width,
                height,
                1,
                24,
                0,
                pixel_size,
                2835,
                2835,
                0,
                0,
            )
        )
        for y in range(height - 1, -1, -1):
            row = bytearray()
            for x in range(width):
                r, g, b = rgb[(y * width + x) * 3 : (y * width + x) * 3 + 3]
                row += bytes([b, g, r])
            row += b"\0" * row_pad
            f.write(row)


def put_pixel(rgb: bytearray, width: int, height: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < width and 0 <= y < height:
        i = (y * width + x) * 3
        rgb[i : i + 3] = bytes(color)


def render_chr(chr_data: bytes, path: Path, tiles_per_row: int = 16, scale: int = 3) -> None:
    tile_count = len(chr_data) // 16
    rows = (tile_count + tiles_per_row - 1) // tiles_per_row
    gap = 1
    width = tiles_per_row * 8 * scale + (tiles_per_row - 1) * gap
    height = rows * 8 * scale + (rows - 1) * gap
    palette = [(16, 16, 16), (96, 96, 96), (176, 176, 176), (248, 248, 248)]
    rgb = bytearray([40, 40, 40]) * width * height

    for tile_index in range(tile_count):
        tx = tile_index % tiles_per_row
        ty = tile_index // tiles_per_row
        tile = chr_data[tile_index * 16 : tile_index * 16 + 16]
        base_x = tx * (8 * scale + gap)
        base_y = ty * (8 * scale + gap)
        draw_tile(rgb, width, height, tile, base_x, base_y, scale, palette)

    write_bmp(path, width, height, rgb)


def draw_tile(
    rgb: bytearray,
    width: int,
    height: int,
    tile: bytes,
    base_x: int,
    base_y: int,
    scale: int,
    palette: list[tuple[int, int, int]],
) -> None:
    for y in range(8):
        low = tile[y]
        high = tile[y + 8]
        for x in range(8):
            bit = 7 - x
            color_index = ((low >> bit) & 1) | (((high >> bit) & 1) << 1)
            color = palette[color_index]
            for sy in range(scale):
                for sx in range(scale):
                    put_pixel(rgb, width, height, base_x + x * scale + sx, base_y + y * scale + sy, color)


def render_nametable(chr_data: bytes, nametable: bytes, path: Path, scale: int = 2) -> None:
    width = 32 * 8 * scale
    height = 30 * 8 * scale
    palette = [(22, 42, 30), (88, 122, 78), (178, 208, 154), (246, 246, 224)]
    rgb = bytearray([0, 0, 0]) * width * height

    for ty in range(30):
        for tx in range(32):
            tile_id = nametable[ty * 32 + tx]
            tile = chr_data[tile_id * 16 : tile_id * 16 + 16]
            draw_tile(
                rgb,
                width,
                height,
                tile,
                tx * 8 * scale,
                ty * 8 * scale,
                scale,
                palette,
            )

    write_bmp(path, width, height, rgb)


def render_mapper163_title_nametable(
    chr_data: bytes,
    nametable: bytes,
    path: Path,
    scale: int = 2,
) -> None:
    """Render the title as mapper 163 displays it across its CHR split."""
    width = 32 * 8 * scale
    height = 30 * 8 * scale
    palette = [(22, 42, 30), (88, 122, 78), (178, 208, 154), (246, 246, 224)]
    rgb = bytearray([0, 0, 0]) * width * height

    for ty in range(30):
        physical_half = 0x1000 if ty >= 16 else 0
        for tx in range(32):
            tile_id = nametable[ty * 32 + tx]
            tile_offset = physical_half + tile_id * 16
            tile = chr_data[tile_offset : tile_offset + 16]
            draw_tile(
                rgb,
                width,
                height,
                tile,
                tx * 8 * scale,
                ty * 8 * scale,
                scale,
                palette,
            )

    write_bmp(path, width, height, rgb)


def parse_fceux_state(path: Path) -> dict[str, bytes]:
    raw = path.read_bytes()
    if raw[:4] != b"FCSX":
        raise ValueError(f'{path} is not an FCEUX FCSX savestate')

    data = zlib.decompress(raw[16:])
    offset = 0
    values: dict[str, bytes] = {}
    while offset + 5 <= len(data):
        section_type = data[offset]
        section_len = struct.unpack_from("<I", data, offset + 1)[0]
        inner = offset + 5
        end = inner + section_len

        # Section 8 is raw mapper state, not a tagged variable block.
        if section_type != 8:
            while inner + 8 <= end:
                name = data[inner : inner + 4].rstrip(b"\0").decode("latin1")
                size = struct.unpack_from("<I", data, inner + 4)[0]
                if inner + 8 + size > end:
                    break
                values[name] = data[inner + 8 : inner + 8 + size]
                inner += 8 + size

        offset = end

    return values


def title_chr_from_rom(rom: bytes) -> bytes:
    pt0 = rom[TITLE_PT0_FILE : TITLE_PT0_FILE + 0x1000]
    pt1 = rom[TITLE_PT1_FILE : TITLE_PT1_FILE + 0x1000]
    return pt0 + pt1


def title_nametable_from_rom(rom: bytes) -> bytes:
    return rom[TITLE_NT_FILE : TITLE_NT_FILE + 0x400]


def player_menu_chr_from_rom(rom: bytes) -> bytes:
    pt0 = rom[PLAYER_MENU_PT0_FILE : PLAYER_MENU_PT0_FILE + 0x1000]
    pt1 = rom[PLAYER_MENU_PT1_FILE : PLAYER_MENU_PT1_FILE + 0x1000]
    if len(pt0) != 0x1000 or len(pt1) != 0x1000:
        raise ValueError('ROM too short to extract player-menu CHR')
    return pt0 + pt1


def player_menu_nametable_from_rom(rom: bytes) -> bytes:
    nametable = rom[
        PLAYER_MENU_NT_FILE
        : PLAYER_MENU_NT_FILE + PLAYER_MENU_NT_VISIBLE_SIZE
    ]
    if len(nametable) != PLAYER_MENU_NT_VISIBLE_SIZE:
        raise ValueError('ROM too short to extract the player-menu nametable')
    return nametable


def build_ips(base: bytes, patched: bytes) -> bytes:
    if len(base) != len(patched):
        raise ValueError('ROMs must have the same size to create a simple IPS')

    ips = bytearray(b"PATCH")
    i = 0
    while i < len(base):
        while i < len(base) and base[i] == patched[i]:
            i += 1
        if i >= len(base):
            break
        start = i
        while i < len(base) and base[i] != patched[i]:
            i += 1
        block = bytes(patched[start:i])
        offset = start
        while block:
            chunk = block[:0xFFFF]
            block = block[0xFFFF:]
            ips.extend(offset.to_bytes(3, "big"))
            ips.extend(len(chunk).to_bytes(2, "big"))
            ips.extend(chunk)
            offset += len(chunk)
    ips.extend(b"EOF")
    return bytes(ips)


def patch_jaune_tiles(rom: bytearray) -> None:
    # Tiles 0x51..0x55 spell the small YELLOW label under the main logo.
    # They live in pattern table $0000, whose source block starts at TITLE_PT0_FILE.
    for tile_id, tile in zip(TITLE_LOGO_TILE_IDS, JAUNE_TILES, strict=True):
        offset = TITLE_PT0_FILE + tile_id * 16
        rom[offset : offset + 16] = tile


def restore_english_title_tiles(
    rom: bytearray,
    english_reference: bytes,
) -> None:
    if len(english_reference) != len(rom):
        raise ValueError(
            f'Incompatible English reference ROM: {len(english_reference)} bytes instead of {len(rom)}'
        )
    for tile_id in TITLE_LOGO_TILE_IDS:
        offset = TITLE_PT0_FILE + tile_id * 16
        rom[offset : offset + 16] = english_reference[offset : offset + 16]


def title_credit_tiles(text: str) -> list[bytes]:
    """Render one compact credit line into the reserved 20-tile title row."""
    text = text.upper()
    missing = sorted(set(text) - set(ORIGINAL_TITLE_CREDIT_GLYPHS))
    if missing:
        raise ValueError(
            "Missing title-credit glyph(s): " + ", ".join(missing)
        )
    width = len(ENGLISH_CREDIT_TILE_IDS) * 8
    spacing = 1
    text_width = sum(
        len(ORIGINAL_TITLE_CREDIT_GLYPHS[character][0])
        for character in text
    ) + spacing * (len(text) - 1)
    if text_width > width:
        raise ValueError(
            f'Title credit too long: {text_width} pixels for {width}'
        )
    pixels = [[0 for _ in range(width)] for _ in range(8)]
    cursor = (width - text_width) // 2
    for character in text:
        glyph = ORIGINAL_TITLE_CREDIT_GLYPHS[character]
        for y, row in enumerate(glyph, start=1):
            for x, bit in enumerate(row):
                if bit == "1":
                    pixels[y][cursor + x] = 3
        cursor += len(glyph[0]) + spacing
    return [
        encode_chr_tile([row[index * 8 : (index + 1) * 8] for row in pixels])
        for index in range(len(ENGLISH_CREDIT_TILE_IDS))
    ]


def patch_english_yellow_title(
    rom: bytearray,
    title_reference: bytes,
    credits: str = ENGLISH_TITLE_CREDITS,
) -> None:
    """Reconstruct the reviewed title from the canonical 2015 technical base."""
    if len(title_reference) != len(rom) or hashlib.sha256(title_reference).hexdigest() != ENGLISH_ROM_SHA256:
        raise ValueError("Noncanonical 2015 English title reference")
    # Exactly 187 reviewed title bytes; offsets include the iNES header.
    # Keeping the small guarded delta avoids a separate intermediate ROM.
    corrections = (
        (0x070A5C, "c0c0c0c0c0", "dec6ded8de"),
        (0x070A64, "80c0c0c0c0", "9cc6ced8de"),
        (0x070B0C, "0000000000", "f7b5b5b5f3"),
        (0x070B14, "0000000000", "63b5b5b563"),
        (0x070B1C, "0000000000", "beb6be86bc"),
        (0x070B24, "0000000000", "1cb6be863c"),
        (0x070B30, "0f00", "cf40"),
        (0x070B38, "0f00", "cf40"),
        (0x070D9C, "ffffffffffff", "c3993c3c99c3"),
        (0x070DA4, "ff", "c3"),
        (0x070DA9, "ff", "c3"),
        (0x070DBC, "ffffffffffff", "1899c3e7e7c3"),
        (0x070DC4, "ff", "18"),
        (0x070DC9, "ff", "c3"),
        (0x070DCC, "ffffffffffff", "019f879f9d01"),
        (0x070DD4, "ff", "01"),
        (0x070DD9, "ff", "01"),
        (0x070DDC, "ffffffffffff", "0f9f9f9f9d01"),
        (0x070DE4, "ff", "0f"),
        (0x070DE9, "ff", "01"),
        (0x070DEC, "ffffffffffff", "183c24248199"),
        (0x070DF4, "ff", "18"),
        (0x070DF9, "ff", "99"),
        (0x07150C, "535252572223", "020202010101"),
        (0x071513, "ffacadada8dd5477", "0705050502020203"),
        (0x07151C, "635456635156", "9a92923a121b"),
        (0x071523, "f79caba99caea9ff", "ff656d6dc5eda4bf"),
        (0x07152C, "495555555549", "444a4a4a4a64"),
        (0x071533, "ffb6aaaaaaaab6ff", "efbbb5b5b5b59bfe"),
        (0x07153C, "20a0a0606020", "a8a8a8f85050"),
        (0x071543, "f8d858589898d8", "fc54545404aca8"),
        (0x0715A5, "0101010101", "0000000000"),
        (0x0715AC, "171515171575", "535252572223"),
        (0x0715B3, "7fe8eaeae8ea8aff", "ffacadada8dd5477"),
        (0x0715BC, "5456", "6354"),
        (0x0715BF, "555574", "635156"),
        (0x0715C3, "ffaba9", "f79cab"),
        (0x0715C7, "aaaa8b", "9caea9"),
        (0x0715CC, "989090b89098", "495555555549"),
        (0x0715D3, "fc666e6e466e66fc", "ffb6aaaaaaaab6ff"),
        (0x0715DC, "000000000000", "20a0a0606020"),
        (0x0715E3, "0000000000000000", "f0d050509090d0f0"),
    )
    rebuilt = bytearray(title_reference)
    for offset, before_hex, after_hex in corrections:
        before, after = bytes.fromhex(before_hex), bytes.fromhex(after_hex)
        if rebuilt[offset:offset + len(before)] != before:
            raise ValueError(f"Unexpected title bytes at {offset:06X}")
        rebuilt[offset:offset + len(after)] = after
    title_start = min(TITLE_PT1_FILE, TITLE_PT0_FILE)
    title_end = max(TITLE_PT1_FILE + 0x1000, TITLE_PT0_FILE + 0x1000)
    rom[title_start:title_end] = rebuilt[title_start:title_end]
    patch_title_credits(rom, credits)


def patch_title_credits(
    rom: bytearray,
    credits: str = ENGLISH_TITLE_CREDITS,
) -> None:
    """Install the shared three-name credit line without changing the logo."""
    for tile_id, tile in zip(
        ENGLISH_CREDIT_TILE_IDS,
        title_credit_tiles(credits),
        strict=True,
    ):
        offset = TITLE_PT1_FILE + tile_id * 16
        rom[offset : offset + 16] = tile

    nt_offset = TITLE_NT_FILE + (
        ENGLISH_CREDIT_NT_ROW * 32 + ENGLISH_CREDIT_NT_COLUMN
    )
    rom[nt_offset : nt_offset + len(ENGLISH_CREDIT_TILE_IDS)] = bytes(
        ENGLISH_CREDIT_TILE_IDS
    )


def patch_french_menu_tiles(rom: bytearray) -> None:
    expected_new = bytes([0x30, 0x31, 0x32, 0x5F])
    expected_load = bytes([0x40, 0x41, 0x42, 0x43])
    actual_new = bytes(rom[MENU_NEW_TILEMAP_FILE : MENU_NEW_TILEMAP_FILE + 4])
    actual_load = bytes(
        rom[MENU_LOAD_TILEMAP_FILE : MENU_LOAD_TILEMAP_FILE + 4]
    )
    if actual_new != expected_new or actual_load != expected_load:
        raise ValueError(
            "Unexpected NEW/LOAD table: "
            f"NEW={actual_new.hex()} LOAD={actual_load.hex()}"
        )

    for tile_id, tile in zip(MENU_TILE_IDS, MENU_FR_TILES, strict=True):
        offset = TITLE_PT1_FILE + tile_id * 16
        rom[offset : offset + 16] = tile


def patch_french_player_menu_labels(rom: bytearray) -> None:
    nametable = player_menu_nametable_from_rom(rom)
    for source_name, layout in PLAYER_MENU_LABELS.items():
        top = tuple(layout["top"])
        bottom = tuple(layout["bottom"])
        tile_ids = top + bottom
        row = int(layout["row"])
        column = int(layout["column"])

        actual_top = tuple(
            nametable[row * 32 + column : row * 32 + column + len(top)]
        )
        actual_bottom = tuple(
            nametable[
                (row + 1) * 32 + column
                : (row + 1) * 32 + column + len(bottom)
            ]
        )
        if actual_top != top or actual_bottom != bottom:
            raise ValueError(
                f"Unexpected {source_name} tilemap: "
                f"top={actual_top}, bottom={actual_bottom}"
            )

        generated = player_menu_word_tiles(str(layout["french"]), len(top))
        current = b"".join(
            rom[
                PLAYER_MENU_PT0_FILE + tile_id * 16
                : PLAYER_MENU_PT0_FILE + (tile_id + 1) * 16
            ]
            for tile_id in tile_ids
        )
        expected_original_hash = str(layout["original_sha256"])
        current_hash = hashlib.sha256(current).hexdigest()
        generated_block = b"".join(generated)
        if current_hash != expected_original_hash and current != generated_block:
            raise ValueError(
                f"Unexpected {source_name} tiles: SHA-256={current_hash}"
            )

        for tile_id, tile in zip(tile_ids, generated, strict=True):
            offset = PLAYER_MENU_PT0_FILE + tile_id * 16
            rom[offset : offset + 16] = tile


def export_player_menu_chr_assets(rom: bytes, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    chr_data = player_menu_chr_from_rom(rom)
    nametable = player_menu_nametable_from_rom(rom)

    (out_dir / "player_menu_chr_8k.bin").write_bytes(chr_data)
    (out_dir / "player_menu_chr_pt0_4k.bin").write_bytes(chr_data[:0x1000])
    (out_dir / "player_menu_chr_pt1_4k.bin").write_bytes(chr_data[0x1000:])
    (out_dir / "player_menu_nametable_visible_960.bin").write_bytes(nametable)

    render_chr(chr_data, out_dir / "player_menu_chr_8k_sheet.bmp")
    render_chr(chr_data[:0x1000], out_dir / "player_menu_chr_pt0_sheet.bmp")
    render_chr(chr_data[0x1000:], out_dir / "player_menu_chr_pt1_sheet.bmp")
    render_nametable(chr_data, nametable, out_dir / "player_menu_render.bmp")

    for source_name, layout in PLAYER_MENU_LABELS.items():
        top = tuple(layout["top"])
        bottom = tuple(layout["bottom"])
        label_tiles = b"".join(
            chr_data[tile_id * 16 : (tile_id + 1) * 16]
            for tile_id in top + bottom
        )
        prefix = (
            f"player_menu_label_{source_name}_to_"
            f"{str(layout['french']).upper()}"
        )
        (out_dir / f"{prefix}_tiles.bin").write_bytes(label_tiles)
        render_chr(
            label_tiles,
            out_dir / f"{prefix}_tiles.bmp",
            tiles_per_row=len(top),
            scale=5,
        )


def export_rom_chr_assets(rom: bytes, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    chr_data = title_chr_from_rom(rom)
    nametable = title_nametable_from_rom(rom)
    menu_tiles = b"".join(
        chr_data[0x1000 + tile_id * 16 : 0x1000 + tile_id * 16 + 16]
        for tile_id in MENU_TILE_IDS
    )

    (out_dir / "title_chr_8k.bin").write_bytes(chr_data)
    (out_dir / "title_chr_pt0_4k.bin").write_bytes(chr_data[:0x1000])
    (out_dir / "title_chr_pt1_4k.bin").write_bytes(chr_data[0x1000:])
    (out_dir / "title_nametable_1k.bin").write_bytes(nametable)
    (out_dir / "menu_fr_tiles_8x8_2bpp.bin").write_bytes(menu_tiles)
    (out_dir / "menu_tilemap_new_4.bin").write_bytes(
        rom[MENU_NEW_TILEMAP_FILE : MENU_NEW_TILEMAP_FILE + 4]
    )
    (out_dir / "menu_tilemap_load_4.bin").write_bytes(
        rom[MENU_LOAD_TILEMAP_FILE : MENU_LOAD_TILEMAP_FILE + 4]
    )

    render_chr(chr_data, out_dir / "title_chr_8k_sheet.bmp")
    render_chr(chr_data[:0x1000], out_dir / "title_chr_pt0_sheet.bmp")
    render_chr(chr_data[0x1000:], out_dir / "title_chr_pt1_sheet.bmp")
    render_chr(menu_tiles, out_dir / "menu_fr_tiles_sheet.bmp", tiles_per_row=4)
    render_mapper163_title_nametable(
        chr_data,
        nametable,
        out_dir / "title_mapper163_split_render.bmp",
    )
    export_player_menu_chr_assets(rom, out_dir)


def command_extract_state(args: argparse.Namespace) -> None:
    state_path = Path(args.state)
    out_dir = Path(args.out)
    values = parse_fceux_state(state_path)

    required = ["CHRR", "NTAR", "PRAM"]
    missing = [key for key in required if key not in values]
    if missing:
        raise SystemExit(f"Incomplete savestate, missing section(s): {', '.join(missing)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "state_CHRR.bin").write_bytes(values["CHRR"])
    (out_dir / "state_NTAR.bin").write_bytes(values["NTAR"])
    (out_dir / "state_PRAM.bin").write_bytes(values["PRAM"])

    render_chr(values["CHRR"][:0x1000], out_dir / "state_CHR_pt0.bmp")
    render_chr(values["CHRR"][0x1000:0x2000], out_dir / "state_CHR_pt1.bmp")
    render_nametable(values["CHRR"], values["NTAR"][:0x400], out_dir / "state_nametable0.bmp")

    print(f"Extracted: {state_path}")
    print(f"Output:  {out_dir}")


def command_scan_rom(args: argparse.Namespace) -> None:
    rom_path = Path(args.rom)
    rom = read_file(rom_path)
    values = parse_fceux_state(Path(args.state))
    chr_ram = values["CHRR"]
    nt = values["NTAR"]

    probes = [
        ("CHR $0000", chr_ram[:0x1000]),
        ("CHR $1000", chr_ram[0x1000:0x2000]),
        ("NT $2000", nt[:0x400]),
    ]

    print(f"ROM: {rom_path}")
    for label, chunk in probes:
        hits = []
        pos = rom.find(chunk)
        while pos != -1:
            hits.append(pos)
            pos = rom.find(chunk, pos + 1)
        pretty = ", ".join(f"0x{hit:06X}" for hit in hits) if hits else "no complete match"
        print(f"{label}: {pretty}")

    print("")
    print('Known offsets for this English/French ROM:')
    print(f'  CHR $1000: 0x{TITLE_PT1_FILE:06X} (4096 bytes)')
    print(f'  CHR $0000: 0x{TITLE_PT0_FILE:06X} (4096 bytes)')
    print(f'  NT  $2000: 0x{TITLE_NT_FILE:06X} (1024 bytes)')
    print('Note: overlapping source ranges are expected in this bank.')


def command_render_rom(args: argparse.Namespace) -> None:
    rom_path = Path(args.rom)
    out_dir = Path(args.out)
    rom = read_file(rom_path)
    chr_data = title_chr_from_rom(rom)
    nametable = title_nametable_from_rom(rom)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "rom_title_CHR.bin").write_bytes(chr_data)
    (out_dir / "rom_title_NT.bin").write_bytes(nametable)
    render_chr(chr_data[:0x1000], out_dir / "rom_title_CHR_pt0.bmp")
    render_chr(chr_data[0x1000:0x2000], out_dir / "rom_title_CHR_pt1.bmp")
    render_nametable(chr_data, nametable, out_dir / "rom_title_nametable0.bmp")

    print(f"ROM:    {rom_path}")
    print(f"Output: {out_dir}")


def command_render_dump(args: argparse.Namespace) -> None:
    chr_path = Path(args.chr)
    nametable_path = Path(args.nametable) if args.nametable else None
    out_dir = Path(args.out)
    prefix = args.prefix
    chr_data = read_file(chr_path)
    if len(chr_data) != 0x2000:
        raise SystemExit(
            f'Invalid CHR dump: {len(chr_data)} bytes instead of 8192'
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{prefix}_chr_8k.bin").write_bytes(chr_data)
    (out_dir / f"{prefix}_chr_pt0.bin").write_bytes(chr_data[:0x1000])
    (out_dir / f"{prefix}_chr_pt1.bin").write_bytes(chr_data[0x1000:])
    render_chr(chr_data, out_dir / f"{prefix}_chr_8k_sheet.bmp")
    render_chr(chr_data[:0x1000], out_dir / f"{prefix}_chr_pt0_sheet.bmp")
    render_chr(chr_data[0x1000:], out_dir / f"{prefix}_chr_pt1_sheet.bmp")

    if nametable_path is not None:
        nametable = read_file(nametable_path)
        if len(nametable) < 0x400:
            raise SystemExit(
                f'Invalid nametable dump: {len(nametable)} bytes, minimum 1024'
            )
        first_nametable = nametable[:0x400]
        (out_dir / f"{prefix}_nametable0.bin").write_bytes(first_nametable)
        render_nametable(
            chr_data,
            first_nametable,
            out_dir / f"{prefix}_nametable0_render.bmp",
        )
        render_mapper163_title_nametable(
            chr_data,
            first_nametable,
            out_dir / f"{prefix}_nametable0_mapper163_split_render.bmp",
        )

    print(f"Source CHR: {chr_path}")
    if nametable_path is not None:
        print(f"Source nametable: {nametable_path}")
    print(f"Manual export: {out_dir}")


def command_patch_jaune(args: argparse.Namespace) -> None:
    rom_path = Path(args.rom)
    base_path = Path(args.base_rom)
    out_rom_path = Path(args.out_rom)
    out_ips_path = Path(args.out_ips)
    out_dir = Path(args.out)

    rom = bytearray(read_file(rom_path))
    base = read_file(base_path)
    patch_jaune_tiles(rom)

    out_rom_path.write_bytes(rom)
    out_ips_path.write_bytes(build_ips(base, bytes(rom)))

    out_dir.mkdir(parents=True, exist_ok=True)
    chr_data = title_chr_from_rom(rom)
    nametable = title_nametable_from_rom(rom)
    render_chr(chr_data[:0x1000], out_dir / "patched_jaune_CHR_pt0.bmp")
    render_nametable(chr_data, nametable, out_dir / "patched_jaune_nametable0.bmp")

    print(f"Source ROM: {rom_path}")
    print(f"Output ROM: {out_rom_path}")
    print(f"Output IPS: {out_ips_path}")
    print("Patch: small YELLOW logo label replaced with JAUNE")


def command_patch_english_title(args: argparse.Namespace) -> None:
    rom_path = Path(args.rom)
    reference_path = Path(args.title_reference_rom)
    base_path = Path(args.base_rom)
    out_rom_path = Path(args.out_rom)
    out_ips_path = Path(args.out_ips)
    out_dir = Path(args.out)

    source = read_file(rom_path)
    base = read_file(base_path)
    rom = bytearray(source)
    patch_english_yellow_title(rom, read_file(reference_path), args.credits)
    patched = bytes(rom)

    out_rom_path.parent.mkdir(parents=True, exist_ok=True)
    out_ips_path.parent.mkdir(parents=True, exist_ok=True)
    out_rom_path.write_bytes(patched)
    out_ips_path.write_bytes(build_ips(base, patched))
    export_rom_chr_assets(patched, out_dir)
    (out_dir / "english_title_manifest.txt").write_text(
        "\n".join(
            (
                "Pokemon Yellow NES - true English title",
                f"Source ROM SHA-256: {hashlib.sha256(source).hexdigest()}",
                f"2015 English reference SHA-256: {hashlib.sha256(read_file(reference_path)).hexdigest()}",
                f"Credits: {args.credits.upper()}",
                f"Output ROM SHA-256: {hashlib.sha256(patched).hexdigest()}",
                "Title legend: YELLOW VERSION",
                "Result: PASS",
                "",
            )
        ),
        encoding="utf-8",
    )
    print(f"Source ROM: {rom_path}")
    print(f"Output ROM: {out_rom_path}")
    print(f"Output IPS: {out_ips_path}")
    print(f"English title: YELLOW VERSION; credits: {args.credits.upper()}")


def command_patch_french_graphics(args: argparse.Namespace) -> None:
    rom_path = Path(args.rom)
    base_path = Path(args.base_rom)
    english_title_path = Path(args.english_title_rom)
    out_rom_path = Path(args.out_rom)
    out_ips_path = Path(args.out_ips)
    out_dir = Path(args.out)

    source = read_file(rom_path)
    base = read_file(base_path)
    base_hash = hashlib.sha256(base).hexdigest()
    if base_hash != ENGLISH_BASE_ROM_SHA256:
        raise SystemExit(
            "Noncanonical IPS base: "
            f"{base_hash} instead of {ENGLISH_BASE_ROM_SHA256}"
        )
    if len(source) != len(base):
        raise SystemExit(
            f"Incompatible sizes: source={len(source)} base={len(base)}"
        )

    rom = bytearray(source)
    export_rom_chr_assets(source, out_dir / "before")
    title_reference_manifest_lines: list[str] = []
    if args.title_logo == "english":
        english_title_reference = read_file(english_title_path)
        english_title_hash = hashlib.sha256(
            english_title_reference
        ).hexdigest()
        if english_title_hash != ENGLISH_ROM_SHA256:
            raise SystemExit(
                "Noncanonical English title ROM: "
                f"{english_title_hash} instead of {ENGLISH_ROM_SHA256}"
            )
        restore_english_title_tiles(rom, english_title_reference)
        title_reference_manifest_lines = [
            (
                "English title ROM: "
                f"{english_title_path.resolve()}"
            ),
            f"English title ROM SHA-256: {english_title_hash}",
        ]
        title_patch_description = (
            "Title logo: English YELLOW restored from the English ROM, "
            "PT0 tiles $51-$55"
        )
    else:
        patch_jaune_tiles(rom)
        title_patch_description = (
            "Logo patch: YELLOW -> JAUNE, PT0 tiles $51-$55"
        )
    patch_french_menu_tiles(rom)
    patch_french_player_menu_labels(rom)
    patch_title_credits(rom)
    patched = bytes(rom)
    export_rom_chr_assets(patched, out_dir / "after")

    out_rom_path.parent.mkdir(parents=True, exist_ok=True)
    out_ips_path.parent.mkdir(parents=True, exist_ok=True)
    out_rom_path.write_bytes(patched)
    out_ips_path.write_bytes(build_ips(base, patched))

    source_hash = hashlib.sha256(source).hexdigest()
    patched_hash = hashlib.sha256(patched).hexdigest()
    manifest = "\n".join(
        [
            "Pokemon Yellow NES - CHR export and French graphics patch",
            f"Source ROM: {rom_path.resolve()}",
            f"Source ROM SHA-256: {source_hash}",
            f"IPS base ROM: {base_path.resolve()}",
            f"IPS base ROM SHA-256: {base_hash}",
            f"Output ROM: {out_rom_path.resolve()}",
            f"Output ROM SHA-256: {patched_hash}",
            f"Output IPS: {out_ips_path.resolve()}",
            f"Source CHR PT0: 0x{TITLE_PT0_FILE:06X}, 4096 bytes",
            f"Source CHR PT1: 0x{TITLE_PT1_FILE:06X}, 4096 bytes",
            f"Title logo mode: {args.title_logo}",
            *title_reference_manifest_lines,
            title_patch_description,
            "Menu patch: NEW -> condensed NOUV, PT1 tiles $30-$32",
            "Menu patch: LOAD -> CONT, PT1 tiles $40-$43",
            (
                "Player-menu patch: ITEMS -> OBJETS, Ash -> SACHA, "
                "HMs -> CS, SAVE -> SAUVER"
            ),
            f"Title credits: {ENGLISH_TITLE_CREDITS}",
            (
                f"Player-menu CHR PT0: 0x{PLAYER_MENU_PT0_FILE:06X}, "
                "4096 bytes"
            ),
            (
                f"Player-menu CHR PT1: 0x{PLAYER_MENU_PT1_FILE:06X}, "
                "4096 bytes"
            ),
            (
                f"Preserved player-menu nametable: "
                f"0x{PLAYER_MENU_NT_FILE:06X}"
            ),
            f"Preserved NEW table: 0x{MENU_NEW_TILEMAP_FILE:06X}",
            f"Preserved LOAD table: 0x{MENU_LOAD_TILEMAP_FILE:06X}",
            f"Before CHR export: {(out_dir / 'before').resolve()}",
            f"After CHR export: {(out_dir / 'after').resolve()}",
            "Result: PASS",
            "",
        ]
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graphics_patch_manifest.txt").write_text(
        manifest,
        encoding="utf-8",
    )

    print(f"Source ROM:      {rom_path}")
    print(f"Output ROM:      {out_rom_path}")
    print(f"Output IPS:      {out_ips_path}")
    print(f"Before/after CHR export: {out_dir}")
    print(
        f"Graphics: logo={args.title_logo}, NEW -> NOUV, LOAD -> CONT, "
        "ITEMS -> OBJETS, Ash -> SACHA, HMs -> CS, SAVE -> SAUVER; "
        f"credits={ENGLISH_TITLE_CREDITS}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze the NJ046 title screen.")
    sub = parser.add_subparsers(dest="command", required=True)

    extract_state = sub.add_parser("extract-state", help="extract CHR/nametable from an FCEUX savestate")
    extract_state.add_argument("--state", default=str(DEFAULT_STATE))
    extract_state.add_argument("--out", default=str(DEFAULT_OUT))
    extract_state.set_defaults(func=command_extract_state)

    scan_rom = sub.add_parser("scan-rom", help="search the ROM for data visible in FCEUX")
    scan_rom.add_argument("--rom", default=str(ENGLISH_ROM))
    scan_rom.add_argument("--state", default=str(DEFAULT_STATE))
    scan_rom.set_defaults(func=command_scan_rom)

    render_rom = sub.add_parser("render-rom", help="render known title data from a ROM")
    render_rom.add_argument("--rom", default=str(FRENCH_ROM))
    render_rom.add_argument("--out", default=str(DEFAULT_OUT))
    render_rom.set_defaults(func=command_render_rom)

    render_dump = sub.add_parser(
        "render-dump",
        help="render a Mesen CHR-RAM dump as BMP sheets for editing",
    )
    render_dump.add_argument("--chr", required=True)
    render_dump.add_argument("--nametable", default="")
    render_dump.add_argument("--out", required=True)
    render_dump.add_argument("--prefix", default="mesen")
    render_dump.set_defaults(func=command_render_dump)

    patch_jaune = sub.add_parser("patch-jaune", help="create a test ROM with YELLOW -> JAUNE on the logo")
    patch_jaune.add_argument("--rom", default=str(FRENCH_ROM))
    patch_jaune.add_argument("--base-rom", default=str(ENGLISH_BASE_ROM))
    patch_jaune.add_argument("--out-rom", default=str(PATCHED_TITLE_ROM))
    patch_jaune.add_argument("--out-ips", default=str(PATCHED_TITLE_IPS))
    patch_jaune.add_argument("--out", default=str(DEFAULT_OUT))
    patch_jaune.set_defaults(func=command_patch_jaune)

    patch_english_title = sub.add_parser(
        "patch-english-title",
        help="restore the original 2015 English reference title and add credits",
    )
    patch_english_title.add_argument("--rom", required=True)
    patch_english_title.add_argument("--title-reference-rom", default=str(ENGLISH_BASE_ROM))
    patch_english_title.add_argument("--base-rom", default=str(ENGLISH_ROM))
    patch_english_title.add_argument("--credits", default=ENGLISH_TITLE_CREDITS)
    patch_english_title.add_argument("--out-rom", required=True)
    patch_english_title.add_argument("--out-ips", required=True)
    patch_english_title.add_argument("--out", required=True)
    patch_english_title.set_defaults(func=command_patch_english_title)

    patch_french_graphics = sub.add_parser(
        "patch-french-graphics",
        help="translate title/menu graphics and export before/after CHR",
    )
    patch_french_graphics.add_argument(
        "--rom",
        default=str(ROM_DIR / "Pokemon_Jaune_FR_repacked.nes"),
    )
    patch_french_graphics.add_argument(
        "--base-rom",
        default=str(ENGLISH_BASE_ROM),
    )
    patch_french_graphics.add_argument(
        "--title-logo",
        choices=("english", "french"),
        default="english",
        help=(
            "title logo: English YELLOW (default) or French JAUNE"
        ),
    )
    patch_french_graphics.add_argument(
        "--english-title-rom",
        default=str(ENGLISH_ROM),
        help="canonical English ROM providing the YELLOW tiles",
    )
    patch_french_graphics.add_argument(
        "--out-rom",
        default=str(ROM_DIR / "Pokemon_Jaune_FR_repacked_title.nes"),
    )
    patch_french_graphics.add_argument(
        "--out-ips",
        default=str(ROM_DIR / "Pokemon_Jaune_FR_repacked_title.ips"),
    )
    patch_french_graphics.add_argument(
        "--out",
        default=str(ROM_DIR / "build" / "chr-exports" / "french-graphics"),
    )
    patch_french_graphics.set_defaults(func=command_patch_french_graphics)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
