#!/usr/bin/env python3
"""Inspect and render the mapper-163 graphical text records.

The English patch keeps the original two-byte text engine.  A pair whose
first byte is in B0-BF selects a 16x16 graphic made from two consecutive
16x8 font slots.  The index calculation below is a direct transcription of
the 6502 routine at file offsets 0x019A53-0x019A8D:

    (high - 0xB0) * 94 + ((low - 0xA1) & 0xFF)

The English patch replaces font slots 0-867 in PRG pair 8.  Slots at and
above 868 retain the Chinese source graphics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    CHINESE_ROM,
    PATCH_SCRIPT,
    TRANSLATION_BASE_ROM,
    TRANSLATION_BASE_SHA256,
    cpu_addr_for_offset,
    detect_pointer_table_entries,
    known_source_target_offsets,
    pair_for_offset,
    parse_patch_entries,
    source_record_len,
    structured_glyph_record_map,
    verified_structured_glyph_records,
)


FONT_BASE_OFFSET = 0x040010
FONT_SLOT_SIZE = 32
ENGLISH_FONT_SLOT_COUNT = 868
INES_HEADER_SIZE = 16
PRG_PAIR_SIZE = 0x8000

FONT_INDEX_ROUTINE_OFFSET = 0x019A4D
FONT_INDEX_ROUTINE = bytes.fromhex(
    "A554F0034C1B9AA9008543A50C38E9A1850CA50D38E9B0850D"
    "F035A8A9008507850DA50D18695E850DA5076900850788D0F0"
    "A50C18650D850CA5076900850D"
)

# Only the characters needed by contact-sheet labels are included.
LABEL_FONT = {
    " ": ("000", "000", "000", "000", "000"),
    "#": ("101", "111", "101", "111", "101"),
    "-": ("000", "000", "111", "000", "000"),
    ":": ("000", "010", "000", "010", "000"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("111", "100", "100", "100", "111"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("111", "100", "101", "101", "111"),
    "I": ("111", "010", "010", "010", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "O": ("111", "101", "101", "101", "111"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("111", "100", "111", "001", "111"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "X": ("101", "101", "010", "101", "101"),
}


@dataclass(frozen=True)
class GlyphCode:
    high: int
    low: int
    slot: int

    @property
    def english_graphic(self) -> bool:
        return self.slot < ENGLISH_FONT_SLOT_COUNT


@dataclass(frozen=True)
class GraphicRecord:
    inventory_index: int
    start: int
    end: int
    pair: int
    codes: tuple[GlyphCode, ...]
    ascii_bytes: bytes


class Raster:
    def __init__(
        self,
        width: int,
        height: int,
        background: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(background * (width * height))

    def set(
        self,
        x: int,
        y: int,
        color: tuple[int, int, int],
    ) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset:offset + 3] = bytes(color)

    def rectangle(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int,
        color: tuple[int, int, int],
    ) -> None:
        for y in range(top, bottom):
            for x in range(left, right):
                self.set(x, y, color)

    def blit(
        self,
        source: "Raster",
        left: int,
        top: int,
        scale: int = 1,
    ) -> None:
        for y in range(source.height):
            for x in range(source.width):
                offset = (y * source.width + x) * 3
                color = tuple(source.pixels[offset:offset + 3])
                self.rectangle(
                    left + x * scale,
                    top + y * scale,
                    left + (x + 1) * scale,
                    top + (y + 1) * scale,
                    color,
                )

    def label(
        self,
        text: str,
        left: int,
        top: int,
        scale: int = 2,
        color: tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        cursor = left
        for character in text.upper():
            pattern = LABEL_FONT.get(character, LABEL_FONT[" "])
            for y, row in enumerate(pattern):
                for x, bit in enumerate(row):
                    if bit == "1":
                        self.rectangle(
                            cursor + x * scale,
                            top + y * scale,
                            cursor + (x + 1) * scale,
                            top + (y + 1) * scale,
                            color,
                        )
            cursor += 4 * scale

    def save_bmp(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        row_size = ((self.width * 3 + 3) // 4) * 4
        image_size = row_size * self.height
        header = (
            b"BM"
            + struct.pack("<IHHI", 54 + image_size, 0, 0, 54)
            + struct.pack(
                "<IIIHHIIIIII",
                40,
                self.width,
                self.height,
                1,
                24,
                0,
                image_size,
                2835,
                2835,
                0,
                0,
            )
        )
        rows = bytearray()
        padding = b"\0" * (row_size - self.width * 3)
        for y in range(self.height - 1, -1, -1):
            row = self.pixels[
                y * self.width * 3:(y + 1) * self.width * 3
            ]
            # Raster stores RGB; BMP stores BGR.
            for x in range(self.width):
                red, green, blue = row[x * 3:x * 3 + 3]
                rows.extend((blue, green, red))
            rows.extend(padding)
        path.write_bytes(header + rows)

    def save_png(self, path: Path) -> None:
        """Write a dependency-free RGB PNG beside the editable BMP."""
        path.parent.mkdir(parents=True, exist_ok=True)

        def chunk(kind: bytes, payload: bytes) -> bytes:
            return (
                struct.pack(">I", len(payload))
                + kind
                + payload
                + struct.pack(
                    ">I",
                    zlib.crc32(kind + payload) & 0xFFFFFFFF,
                )
            )

        scanlines = b"".join(
            b"\0"
            + bytes(
                self.pixels[
                    y * self.width * 3:(y + 1) * self.width * 3
                ]
            )
            for y in range(self.height)
        )
        header = struct.pack(
            ">IIBBBBB",
            self.width,
            self.height,
            8,
            2,
            0,
            0,
            0,
        )
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(scanlines, level=9))
            + chunk(b"IEND", b"")
        )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_rom(path: str | Path) -> bytes:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROM_DIR / candidate
    return candidate.read_bytes()


def validate_sources(english: bytes, chinese: bytes) -> None:
    digest = sha256(english)
    if digest != TRANSLATION_BASE_SHA256:
        raise ValueError(
            "ROM anglaise non canonique: "
            f"{digest} au lieu de {TRANSLATION_BASE_SHA256}"
        )
    if len(english) != len(chinese):
        raise ValueError(
            "ROM chinoise de taille inattendue: "
            f"{len(chinese)} au lieu de {len(english)}"
        )
    actual_routine = english[
        FONT_INDEX_ROUTINE_OFFSET:
        FONT_INDEX_ROUTINE_OFFSET + len(FONT_INDEX_ROUTINE)
    ]
    if actual_routine != FONT_INDEX_ROUTINE:
        raise ValueError(
            "routine d'indexation des glyphes non canonique à "
            f"0x{FONT_INDEX_ROUTINE_OFFSET:06X}"
        )

    changed_slots = [
        slot
        for slot in range(1024)
        if english[
            FONT_BASE_OFFSET + slot * FONT_SLOT_SIZE:
            FONT_BASE_OFFSET + (slot + 1) * FONT_SLOT_SIZE
        ]
        != chinese[
            FONT_BASE_OFFSET + slot * FONT_SLOT_SIZE:
            FONT_BASE_OFFSET + (slot + 1) * FONT_SLOT_SIZE
        ]
    ]
    expected = list(range(ENGLISH_FONT_SLOT_COUNT))
    if changed_slots != expected:
        raise ValueError(
            "empreinte de la police anglaise inattendue: "
            f"{len(changed_slots)} slots modifiés, "
            f"premier={changed_slots[:1]}, dernier={changed_slots[-1:]}"
        )


def glyph_slot(high: int, low: int) -> int:
    if not 0xB0 <= high <= 0xBF:
        raise ValueError(f"octet haut glyphique invalide: 0x{high:02X}")
    return (high - 0xB0) * 94 + ((low - 0xA1) & 0xFF)


def parse_record(
    inventory_index: int,
    start: int,
    end: int,
    pair: int,
    data: bytes,
) -> GraphicRecord:
    codes: list[GlyphCode] = []
    ascii_bytes = bytearray()
    cursor = start
    while cursor < end:
        value = data[cursor]
        if 0xB0 <= value <= 0xBF:
            low = data[cursor + 1]
            codes.append(GlyphCode(value, low, glyph_slot(value, low)))
            cursor += 2
        else:
            ascii_bytes.append(value)
            cursor += 1
    return GraphicRecord(
        inventory_index,
        start,
        end,
        pair,
        tuple(codes),
        bytes(ascii_bytes),
    )


def records(data: bytes) -> list[GraphicRecord]:
    return [
        parse_record(index, start, end, pair, data)
        for index, (start, end, pair, _) in enumerate(
            verified_structured_glyph_records(data),
            start=1,
        )
    ]


def slot_raster(
    data: bytes,
    slot: int,
    ink: tuple[int, int, int],
    bitplane: int | None = None,
) -> Raster:
    result = Raster(16, 8)
    start = FONT_BASE_OFFSET + slot * FONT_SLOT_SIZE
    raw = data[start:start + FONT_SLOT_SIZE]
    if len(raw) != FONT_SLOT_SIZE:
        result.rectangle(0, 0, 16, 8, (255, 0, 255))
        return result
    for tile in range(2):
        tile_start = tile * 16
        for y in range(8):
            plane_zero = raw[tile_start + y]
            plane_one = raw[tile_start + 8 + y]
            for x in range(8):
                mask = 1 << (7 - x)
                visible = (
                    bool(plane_zero & mask)
                    if bitplane == 0
                    else bool(plane_one & mask)
                    if bitplane == 1
                    else bool(plane_zero & mask or plane_one & mask)
                )
                if visible:
                    result.set(tile * 8 + x, y, ink)
    return result


def code_raster(
    data: bytes,
    code: GlyphCode,
    ink_override: tuple[int, int, int] | None = None,
    bitplane: int | None = None,
) -> Raster:
    # Black is an English-patch graphic; red is an untouched source glyph.
    ink = (
        ink_override
        if ink_override is not None
        else (0, 0, 0)
        if code.english_graphic
        else (190, 0, 0)
    )
    result = Raster(16, 16)
    result.blit(
        slot_raster(data, code.slot, ink, bitplane),
        0,
        0,
    )
    result.blit(
        slot_raster(data, code.slot + 1, ink, bitplane),
        0,
        8,
    )
    return result


def wrapped_record_raster(
    data: bytes,
    record: GraphicRecord,
    columns: int,
    ink_override: tuple[int, int, int] | None = None,
    bitplane: int | None = None,
) -> Raster:
    rows = max(1, (len(record.codes) + columns - 1) // columns)
    result = Raster(columns * 16, rows * 16)
    for index, code in enumerate(record.codes):
        left = (index % columns) * 16
        top = (index // columns) * 16
        result.blit(
            code_raster(data, code, ink_override, bitplane),
            left,
            top,
        )
    return result


def raw_pointer_refs(data: bytes, target: int) -> list[int]:
    pair = pair_for_offset(target)
    pair_start = INES_HEADER_SIZE + pair * PRG_PAIR_SIZE
    pair_end = min(len(data), pair_start + PRG_PAIR_SIZE)
    word = cpu_addr_for_offset(target).to_bytes(2, "little")
    refs: list[int] = []
    cursor = pair_start
    while True:
        cursor = data.find(word, cursor, pair_end)
        if cursor < 0:
            return refs
        refs.append(cursor)
        cursor += 1


def ascii_summary(raw: bytes) -> str:
    parts: list[str] = []
    for value in raw:
        if 0x20 <= value <= 0x7E:
            parts.append(chr(value))
        else:
            parts.append(f"<{value:02X}>")
    return "".join(parts)


def record_pointer_table_refs(
    data: bytes,
    parsed: list[GraphicRecord],
    additional_known_targets: set[int] | None = None,
) -> dict[int, list[tuple[int, int]]]:
    """Return verified table references as (pointer offset, target delta)."""
    source_ranges = [
        (record.start, record.end - record.start)
        for record in parsed
    ]
    known_targets = known_source_target_offsets(data, source_ranges)
    if additional_known_targets is not None:
        known_targets.update(additional_known_targets)
    target_records: dict[int, tuple[int, int]] = {}
    for record in parsed:
        for target in known_source_target_offsets(
            data,
            [(record.start, record.end - record.start)],
        ):
            target_records[target] = (record.inventory_index, target - record.start)

    table_entries = detect_pointer_table_entries(
        data,
        min_run=5,
        known_offsets=known_targets,
        min_known_ratio=0.1,
        min_known_count=1,
    )
    graphical_spans = [(record.start, record.end) for record in parsed]
    refs: dict[int, list[tuple[int, int]]] = {
        record.inventory_index: []
        for record in parsed
    }
    for target, pointer_offsets in table_entries.items():
        mapped = target_records.get(target)
        if mapped is None:
            continue
        record_index, delta = mapped
        for pointer_offset in pointer_offsets:
            if any(
                start <= pointer_offset < end
                or start < pointer_offset + 2 <= end
                for start, end in graphical_spans
            ):
                continue
            refs[record_index].append((pointer_offset, delta))

    for record_refs in refs.values():
        record_refs.sort()
    return refs


def command_inventory(args: argparse.Namespace) -> int:
    english = read_rom(args.english_rom)
    chinese = read_rom(args.chinese_rom)
    validate_sources(english, chinese)
    parsed = records(english)
    patch_entries = parse_patch_entries(PATCH_SCRIPT)
    translated_offsets = {entry.offset for entry in patch_entries}
    glyph_by_start = structured_glyph_record_map(
        verified_structured_glyph_records(english)
    )
    patch_source_ranges = [
        (
            entry.offset,
            source_record_len(
                english,
                entry.offset,
                glyph_by_start,
            ),
        )
        for entry in patch_entries
    ]
    table_refs = record_pointer_table_refs(
        english,
        parsed,
        known_source_target_offsets(english, patch_source_ranges),
    )

    output = Path(args.output)
    if not output.is_absolute():
        output = ROM_DIR / output
    output.parent.mkdir(parents=True, exist_ok=True)

    fields = (
        "record_index",
        "start_hex",
        "end_hex_exclusive",
        "pair",
        "payload_bytes",
        "glyph_codes",
        "english_graphic_codes",
        "source_chinese_codes",
        "classification",
        "unchanged_from_chinese_source",
        "declared_french_translation",
        "ascii_bytes",
        "raw_start_pointer_refs",
        "table_pointer_refs",
        "static_table_referenced",
    )
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in parsed:
            english_count = sum(
                code.english_graphic for code in record.codes
            )
            chinese_count = len(record.codes) - english_count
            classification = (
                "english_graphic"
                if chinese_count == 0
                else "mixed_english_chinese"
                if english_count
                else "source_chinese"
            )
            writer.writerow(
                {
                    "record_index": record.inventory_index,
                    "start_hex": f"0x{record.start:06X}",
                    "end_hex_exclusive": f"0x{record.end:06X}",
                    "pair": record.pair,
                    "payload_bytes": record.end - record.start,
                    "glyph_codes": len(record.codes),
                    "english_graphic_codes": english_count,
                    "source_chinese_codes": chinese_count,
                    "classification": classification,
                    "unchanged_from_chinese_source": int(
                        english[record.start:record.end]
                        == chinese[record.start:record.end]
                    ),
                    "declared_french_translation": int(
                        record.start in translated_offsets
                    ),
                    "ascii_bytes": ascii_summary(record.ascii_bytes),
                    "raw_start_pointer_refs": " ".join(
                        f"0x{ref:06X}"
                        for ref in raw_pointer_refs(
                            english,
                            record.start,
                        )
                    ),
                    "table_pointer_refs": " ".join(
                        (
                            f"0x{pointer_offset:06X}->"
                            f"+0x{target_delta:X}"
                        )
                        for pointer_offset, target_delta
                        in table_refs[record.inventory_index]
                    ),
                    "static_table_referenced": int(
                        bool(table_refs[record.inventory_index])
                    ),
                }
            )

    counts: dict[str, int] = {}
    for record in parsed:
        english_count = sum(code.english_graphic for code in record.codes)
        chinese_count = len(record.codes) - english_count
        key = (
            "english_graphic"
            if chinese_count == 0
            else "mixed_english_chinese"
            if english_count
            else "source_chinese"
        )
        counts[key] = counts.get(key, 0) + 1
    print("Inventaire graphique mapper 163")
    print(f"- Records: {len(parsed)}")
    print(
        "- Records entièrement redessinés en anglais: "
        f"{counts.get('english_graphic', 0)}"
    )
    print(
        "- Records mêlant graphismes anglais et glyphes source: "
        f"{counts.get('mixed_english_chinese', 0)}"
    )
    print(
        "- Records uniquement en glyphes source: "
        f"{counts.get('source_chinese', 0)}"
    )
    print(
        "- Records référencés par une table statique vérifiée: "
        f"{sum(bool(table_refs[record.inventory_index]) for record in parsed)}"
    )
    print(f"- CSV: {output}")
    return 0


def command_render(args: argparse.Namespace) -> int:
    english = read_rom(args.english_rom)
    chinese = read_rom(args.chinese_rom)
    validate_sources(english, chinese)
    parsed = records(english)
    if args.unchanged_only:
        parsed = [
            record
            for record in parsed
            if english[record.start:record.end]
            == chinese[record.start:record.end]
        ]
    font_data = chinese if args.font_view == "chinese" else english
    ink_override = (
        (0, 0, 0)
        if args.font_view == "chinese"
        else None
    )
    bitplane = (
        None
        if args.bitplane == "combined"
        else int(args.bitplane)
    )

    output_directory = Path(args.output_directory)
    if not output_directory.is_absolute():
        output_directory = ROM_DIR / output_directory
    records_directory = output_directory / "records"
    pages_directory = output_directory / "pages"
    records_directory.mkdir(parents=True, exist_ok=True)
    pages_directory.mkdir(parents=True, exist_ok=True)

    columns = args.glyph_columns
    scale = args.scale
    page_width = columns * 16 * scale + 32
    panel_height = args.panel_height
    records_per_page = args.records_per_page
    page_count = (
        len(parsed) + records_per_page - 1
    ) // records_per_page

    for record in parsed:
        graphic = wrapped_record_raster(
            font_data,
            record,
            columns,
            ink_override,
            bitplane,
        )
        stem = (
            f"{record.inventory_index:03d}_"
            f"{record.start:06X}"
        )
        graphic.save_bmp(records_directory / f"{stem}.bmp")
        graphic.save_png(records_directory / f"{stem}.png")

    for page_index in range(page_count):
        page_records = parsed[
            page_index * records_per_page:
            (page_index + 1) * records_per_page
        ]
        page = Raster(page_width, panel_height * len(page_records))
        for panel_index, record in enumerate(page_records):
            top = panel_index * panel_height
            if panel_index:
                page.rectangle(
                    0,
                    top,
                    page_width,
                    top + 1,
                    (190, 190, 190),
                )
            english_count = sum(
                code.english_graphic for code in record.codes
            )
            chinese_count = len(record.codes) - english_count
            page.label(
                (
                    f"#{record.inventory_index:03d} "
                    f"{record.start:06X}-{record.end:06X} "
                    f"G:{len(record.codes):03d} "
                    f"C:{chinese_count:03d}"
                ),
                8,
                top + 6,
                scale=2,
            )
            graphic = wrapped_record_raster(
                font_data,
                record,
                columns,
                ink_override,
                bitplane,
            )
            page.blit(graphic, 8, top + 22, scale=scale)
        page_stem = f"glyph_records_{page_index + 1:02d}"
        page.save_bmp(pages_directory / f"{page_stem}.bmp")
        page.save_png(pages_directory / f"{page_stem}.png")

    print("Export graphique mapper 163")
    print(f"- Records: {len(parsed)}")
    print(f"- Fichiers individuels: {records_directory}")
    print(f"- Planches: {pages_directory} ({page_count})")
    print(f"- Police rendue: {args.font_view}")
    print(f"- Plan binaire: {args.bitplane}")
    if args.font_view == "english":
        print(
            "- Convention couleur: noir=police anglaise remplacée, "
            "rouge=glyphe chinois source non remplacé"
        )
    else:
        print(
            "- Vue source: police chinoise canonique en noir; "
            "utiliser --unchanged-only pour une correspondance exacte"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inventorie et rend les records texte graphiques de la ROM."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser(
        "inventory",
        help="Écrit la classification exacte des 317 records.",
    )
    inventory.add_argument("--english-rom", default=TRANSLATION_BASE_ROM)
    inventory.add_argument("--chinese-rom", default=CHINESE_ROM)
    inventory.add_argument(
        "--output",
        default="build/glyph-audit/glyph_record_inventory.csv",
    )
    inventory.set_defaults(function=command_inventory)

    render = subparsers.add_parser(
        "render-records",
        help="Exporte les records et des planches BMP lisibles.",
    )
    render.add_argument("--english-rom", default=TRANSLATION_BASE_ROM)
    render.add_argument("--chinese-rom", default=CHINESE_ROM)
    render.add_argument(
        "--output-directory",
        default="build/glyph-audit",
    )
    render.add_argument(
        "--font-view",
        choices=("english", "chinese"),
        default="english",
        help="Police bitmap utilisée pour rendre les codes inventoriés.",
    )
    render.add_argument(
        "--bitplane",
        choices=("combined", "0", "1"),
        default="combined",
        help=(
            "Rend les deux plans superposés ou un seul plan 1 bit; "
            "les glyphes NJ046 peuvent contenir deux caractères entrelacés."
        ),
    )
    render.add_argument(
        "--unchanged-only",
        action="store_true",
        help=(
            "Ne rend que les plages dont les codes sont identiques entre "
            "la ROM chinoise et le patch anglais."
        ),
    )
    render.add_argument("--glyph-columns", type=int, default=30)
    render.add_argument("--scale", type=int, default=2)
    render.add_argument("--panel-height", type=int, default=96)
    render.add_argument("--records-per-page", type=int, default=10)
    render.set_defaults(function=command_render)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if getattr(args, "glyph_columns", 1) < 1:
        raise SystemExit("--glyph-columns doit être positif")
    if getattr(args, "scale", 1) < 1:
        raise SystemExit("--scale doit être positif")
    if getattr(args, "panel_height", 32) < 32:
        raise SystemExit("--panel-height doit valoir au moins 32")
    if getattr(args, "records_per_page", 1) < 1:
        raise SystemExit("--records-per-page doit être positif")
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
