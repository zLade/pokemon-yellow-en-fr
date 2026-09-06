#!/usr/bin/env python3
"""Build safe two-line move labels with the mapper-163 graphic text path.

The battle renderer can display a graphical code as one 16x16 cell.  A cell
is backed by two consecutive 16x8 atlas slots: the even slot is its top half
and the following odd slot is its bottom half.  Each half stores two ordinary
8x8 font tiles, so one code can display two characters on each line.

This module deliberately does not relocate move records.  A graphical payload
is installed only when it fits in the record capacity already addressed by
the candidate ROM's move pointer.  It works entirely on bytes and therefore
can be integrated into either release builder without writing a ROM itself.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable, Iterable, Sequence


MOVE_COUNT = 177
MOVE_NAME_POINTER_TABLE_OFFSET = 0x030F99
MOVE_NAME_BANK_FILE_BASE = 0x030010
MOVE_NAME_BANK_CPU_BASE = 0x8000
MOVE_NAME_BANK_SIZE = 0x8000
TEXT_TERMINATOR = 0x0D

GRAPHIC_HIGH_MIN = 0xB0
GRAPHIC_HIGH_MAX = 0xBF
GRAPHIC_LOW_BASE = 0xA1
GRAPHIC_SLOTS_PER_HIGH = 94
CANONICAL_POOL_FIRST_SLOT = 38
CANONICAL_POOL_LAST_SLOT = 758
DEFAULT_EXCLUDED_EVEN_SLOTS = frozenset({208, 382, 472})

GRAPHIC_ATLAS_OFFSET = 0x040010
GRAPHIC_ATLAS_SLOT_SIZE = 32

ASCII_FONT_OFFSET = 0x078210
ASCII_FONT_FIRST_CODE = 0x20
ASCII_FONT_TILE_COUNT = 96
ASCII_FONT_TILE_SIZE = 16
ASCII_FONT_LAST_CODE = ASCII_FONT_FIRST_CODE + ASCII_FONT_TILE_COUNT - 1

CSV_COLUMNS = ("move_index", "full_name", "line_1", "line_2")

TextEncoder = Callable[[str], bytes]


class MoveLabelError(ValueError):
    """Base error for malformed data or an incompatible ROM layout."""


class MoveLabelCsvError(MoveLabelError):
    """The declarative move-label CSV is invalid."""


class RomLayoutError(MoveLabelError):
    """The ROM does not expose the expected move-table or font layout."""


class IncompleteMoveLabelPatch(MoveLabelError):
    """At least one requested label could not be installed safely."""

    def __init__(self, report: "MoveLabelPatchReport") -> None:
        self.report = report
        super().__init__(
            f"move-label patch incomplete: {report.applied_count}/"
            f"{report.requested_count} labels applied"
        )


@dataclass(frozen=True)
class MoveLabelSpec:
    move_index: int
    full_name: str
    line_1: str
    line_2: str
    encoded_line_1: bytes
    encoded_line_2: bytes

    @property
    def code_count(self) -> int:
        return (max(len(self.encoded_line_1), len(self.encoded_line_2)) + 1) // 2

    @property
    def required_payload_size(self) -> int:
        return self.code_count * 2 + 1


@dataclass(frozen=True)
class MoveRecord:
    move_index: int
    pointer_offset: int
    target: int
    payload: bytes
    graphical_slots: tuple[int, ...]
    writable_capacity: int
    next_live_target: int | None = None
    overlapping_move_indexes: tuple[int, ...] = ()

    @property
    def capacity(self) -> int:
        """Bytes writable without crossing another live move target."""
        return self.writable_capacity

    @property
    def raw_capacity(self) -> int:
        """Bytes through the parsed terminator, including shared suffix data."""
        return len(self.payload)


@dataclass(frozen=True)
class GraphicSlotPool:
    mode: str
    discovered_slots: tuple[int, ...]
    excluded_even_slots: tuple[int, ...]
    available_even_slots: tuple[int, ...]


@dataclass(frozen=True)
class MoveLabelPatchEntry:
    move_index: int
    full_name: str
    line_1: str
    line_2: str
    encoded_line_1_length: int
    encoded_line_2_length: int
    target: int
    capacity: int
    raw_capacity: int
    next_live_target: int | None
    overlapping_move_indexes: tuple[int, ...]
    required_payload_size: int
    code_slots: tuple[int, ...]
    status: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["target_hex"] = f"0x{self.target:06X}"
        result["next_live_target_hex"] = (
            f"0x{self.next_live_target:06X}"
            if self.next_live_target is not None
            else None
        )
        return result


@dataclass(frozen=True)
class MoveLabelPatchReport:
    requested_count: int
    applied_count: int
    skipped_count: int
    candidate_target_count: int
    candidate_unique_target_count: int
    pool_mode: str
    pool_discovered_count: int
    pool_available_count: int
    pool_protected_count: int
    excluded_even_slots: tuple[int, ...]
    used_even_slots: tuple[int, ...]
    changed_offset_count: int
    entries: tuple[MoveLabelPatchEntry, ...]

    @property
    def complete(self) -> bool:
        return self.applied_count == self.requested_count

    def assert_complete(self) -> None:
        if not self.complete:
            raise IncompleteMoveLabelPatch(self)

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["complete"] = self.complete
        result["entries"] = [entry.to_dict() for entry in self.entries]
        return result


@dataclass(frozen=True)
class MoveLabelPatchResult:
    rom: bytes
    report: MoveLabelPatchReport


def ascii_text_encoder(text: str) -> bytes:
    """Encode an English label with the game's one-byte ASCII font."""
    return text.encode("ascii", errors="strict")


def french_text_encoder(text: str) -> bytes:
    """Use the canonical French codec without coupling callers to its path."""
    try:
        from tools.french_font import encode_game_text
    except ModuleNotFoundError:  # Direct execution from the tools directory.
        from french_font import encode_game_text
    return encode_game_text(text)


def resolve_text_encoder(name: str) -> TextEncoder:
    normalized = name.strip().lower()
    if normalized in {"ascii", "en", "english"}:
        return ascii_text_encoder
    if normalized in {"fr", "french", "francais", "français"}:
        return french_text_encoder
    raise MoveLabelError(f"unknown move-label encoder: {name!r}")


def _validate_encoded_line(
    text: str,
    *,
    encoder: TextEncoder,
    row_number: int,
    column: str,
) -> bytes:
    if not text:
        raise MoveLabelCsvError(f"row {row_number}: {column} must not be empty")
    try:
        encoded = encoder(text)
    except (UnicodeError, ValueError) as exc:
        raise MoveLabelCsvError(
            f"row {row_number}: {column} cannot be encoded: {exc}"
        ) from exc
    if not isinstance(encoded, (bytes, bytearray, memoryview)):
        raise MoveLabelCsvError(
            f"row {row_number}: encoder returned {type(encoded).__name__}, expected bytes"
        )
    raw = bytes(encoded)
    if not 1 <= len(raw) <= 8:
        raise MoveLabelCsvError(
            f"row {row_number}: {column} uses {len(raw)} encoded glyphs, expected 1..8"
        )
    invalid = [value for value in raw if not ASCII_FONT_FIRST_CODE <= value <= ASCII_FONT_LAST_CODE]
    if invalid:
        rendered = ", ".join(f"0x{value:02X}" for value in invalid)
        raise MoveLabelCsvError(
            f"row {row_number}: {column} contains bytes outside the patched ASCII font: "
            f"{rendered}"
        )
    return raw


def load_move_label_csv(
    path: str | Path,
    *,
    encoder: TextEncoder = ascii_text_encoder,
) -> tuple[MoveLabelSpec, ...]:
    """Load and validate a partial, uniquely indexed two-line label catalogue."""
    candidate = Path(path)
    try:
        handle = candidate.open("r", encoding="utf-8-sig", errors="strict", newline="")
    except UnicodeDecodeError as exc:
        raise MoveLabelCsvError(f"{candidate}: invalid UTF-8: {exc}") from exc

    try:
        with handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise MoveLabelCsvError(f"{candidate}: missing CSV header")
            missing = [column for column in CSV_COLUMNS if column not in reader.fieldnames]
            if missing:
                raise MoveLabelCsvError(
                    f"{candidate}: missing columns: {', '.join(missing)}"
                )
            specs: list[MoveLabelSpec] = []
            seen: set[int] = set()
            for row_number, row in enumerate(reader, start=2):
                raw_index = (row.get("move_index") or "").strip()
                try:
                    move_index = int(raw_index, 10)
                except ValueError as exc:
                    raise MoveLabelCsvError(
                        f"row {row_number}: invalid move_index {raw_index!r}"
                    ) from exc
                if not 0 <= move_index < MOVE_COUNT:
                    raise MoveLabelCsvError(
                        f"row {row_number}: move_index {move_index} outside 0..176"
                    )
                if move_index in seen:
                    raise MoveLabelCsvError(
                        f"row {row_number}: duplicate move_index {move_index}"
                    )
                seen.add(move_index)

                full_name = (row.get("full_name") or "").strip()
                line_1 = (row.get("line_1") or "").strip()
                line_2 = (row.get("line_2") or "").strip()
                if not full_name:
                    raise MoveLabelCsvError(
                        f"row {row_number}: full_name must not be empty"
                    )
                encoded_line_1 = _validate_encoded_line(
                    line_1,
                    encoder=encoder,
                    row_number=row_number,
                    column="line_1",
                )
                encoded_line_2 = _validate_encoded_line(
                    line_2,
                    encoder=encoder,
                    row_number=row_number,
                    column="line_2",
                )
                specs.append(
                    MoveLabelSpec(
                        move_index=move_index,
                        full_name=full_name,
                        line_1=line_1,
                        line_2=line_2,
                        encoded_line_1=encoded_line_1,
                        encoded_line_2=encoded_line_2,
                    )
                )
    except UnicodeDecodeError as exc:
        raise MoveLabelCsvError(f"{candidate}: invalid UTF-8: {exc}") from exc
    return tuple(specs)


def graphic_slot(high: int, low: int) -> int:
    if not GRAPHIC_HIGH_MIN <= high <= GRAPHIC_HIGH_MAX:
        raise RomLayoutError(f"invalid graphical high byte 0x{high:02X}")
    return (high - GRAPHIC_HIGH_MIN) * GRAPHIC_SLOTS_PER_HIGH + (
        (low - GRAPHIC_LOW_BASE) & 0xFF
    )


def graphic_code(slot: int) -> bytes:
    """Return the canonical two-byte mapper-163 code for an atlas slot."""
    if slot < 0:
        raise MoveLabelError(f"negative graphical slot: {slot}")
    high_index, low_index = divmod(slot, GRAPHIC_SLOTS_PER_HIGH)
    high = GRAPHIC_HIGH_MIN + high_index
    low = GRAPHIC_LOW_BASE + low_index
    if high > GRAPHIC_HIGH_MAX or low > 0xFE:
        raise MoveLabelError(f"graphical slot cannot be encoded: {slot}")
    return bytes((high, low))


def _move_target(rom: bytes, move_index: int) -> tuple[int, int]:
    pointer_offset = MOVE_NAME_POINTER_TABLE_OFFSET + move_index * 2
    if pointer_offset + 2 > len(rom):
        raise RomLayoutError("ROM too short for the 177-entry move pointer table")
    pointer = int.from_bytes(rom[pointer_offset : pointer_offset + 2], "little")
    target = MOVE_NAME_BANK_FILE_BASE + pointer - MOVE_NAME_BANK_CPU_BASE
    bank_end = MOVE_NAME_BANK_FILE_BASE + MOVE_NAME_BANK_SIZE
    if not MOVE_NAME_BANK_FILE_BASE <= target < bank_end:
        raise RomLayoutError(
            f"move {move_index}: pointer 0x{pointer:04X} leaves the move-name bank"
        )
    if target >= len(rom):
        raise RomLayoutError(
            f"move {move_index}: target 0x{target:06X} lies beyond the ROM"
        )
    return pointer_offset, target


def _parse_move_payload(rom: bytes, move_index: int, target: int) -> MoveRecord:
    cursor = target
    graphical_slots: list[int] = []
    scan_end = min(len(rom), MOVE_NAME_BANK_FILE_BASE + MOVE_NAME_BANK_SIZE)
    while cursor < scan_end:
        value = rom[cursor]
        if GRAPHIC_HIGH_MIN <= value <= GRAPHIC_HIGH_MAX:
            if cursor + 1 >= scan_end:
                raise RomLayoutError(
                    f"move {move_index}: truncated graphical code at 0x{cursor:06X}"
                )
            graphical_slots.append(graphic_slot(value, rom[cursor + 1]))
            cursor += 2
            continue
        cursor += 1
        if value == TEXT_TERMINATOR:
            pointer_offset = MOVE_NAME_POINTER_TABLE_OFFSET + move_index * 2
            return MoveRecord(
                move_index=move_index,
                pointer_offset=pointer_offset,
                target=target,
                payload=rom[target:cursor],
                graphical_slots=tuple(graphical_slots),
                writable_capacity=cursor - target,
            )
    raise RomLayoutError(
        f"move {move_index}: unterminated payload at 0x{target:06X}"
    )


def read_move_records(rom: bytes) -> tuple[MoveRecord, ...]:
    """Follow 177 distinct pointers and bound writes at the next live target.

    The text allocator is allowed to suffix-pool ordinary strings, so two
    distinct targets can legally share bytes through one terminator.  A new
    graphical payload is not suffix-compatible with the old text, however.
    Its safe capacity therefore ends immediately before any later live move
    target, even if the parsed source record continues beyond that target.
    """
    records: list[MoveRecord] = []
    for move_index in range(MOVE_COUNT):
        _, target = _move_target(rom, move_index)
        records.append(_parse_move_payload(rom, move_index, target))
    targets = [record.target for record in records]
    if len(set(targets)) != MOVE_COUNT:
        duplicates = sorted(
            target for target in set(targets) if targets.count(target) > 1
        )
        rendered = ", ".join(f"0x{target:06X}" for target in duplicates[:8])
        raise RomLayoutError(
            f"move table has {len(set(targets))}/177 unique targets; duplicates: {rendered}"
        )
    owner_by_target = {record.target: record.move_index for record in records}
    ordered_targets = sorted(owner_by_target)
    bounded: list[MoveRecord] = []
    for record in records:
        payload_end = record.target + record.raw_capacity
        interior_targets = tuple(
            target
            for target in ordered_targets
            if record.target < target < payload_end
        )
        safe_end = interior_targets[0] if interior_targets else payload_end
        bounded.append(
            replace(
                record,
                writable_capacity=safe_end - record.target,
                next_live_target=(interior_targets[0] if interior_targets else None),
                overlapping_move_indexes=tuple(
                    owner_by_target[target] for target in interior_targets
                ),
            )
        )
    return tuple(bounded)


def extract_graphic_slot_pool(
    source_english_rom: bytes | None,
    *,
    mode: str = "source",
    excluded_even_slots: Iterable[int] = DEFAULT_EXCLUDED_EVEN_SLOTS,
) -> GraphicSlotPool:
    """Extract move-owned even cells, or use the reviewed canonical range."""
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"source", "canonical"}:
        raise MoveLabelError(f"unknown graphical slot-pool mode: {mode!r}")

    exclusions = tuple(sorted(set(excluded_even_slots)))
    if any(slot < 0 or slot % 2 for slot in exclusions):
        raise MoveLabelError("excluded graphical slots must be non-negative and even")

    if normalized_mode == "canonical":
        discovered = tuple(
            range(CANONICAL_POOL_FIRST_SLOT, CANONICAL_POOL_LAST_SLOT + 1, 2)
        )
    else:
        if source_english_rom is None:
            raise MoveLabelError("source pool mode requires the English 2015 ROM bytes")
        records = read_move_records(source_english_rom)
        slots = [slot for record in records for slot in record.graphical_slots]
        if any(slot % 2 for slot in slots):
            odd = sorted(set(slot for slot in slots if slot % 2))
            raise RomLayoutError(
                f"English source move records use odd graphical slots: {odd[:8]}"
            )
        if len(slots) != len(set(slots)):
            raise RomLayoutError("English source move records reuse graphical cells")
        discovered = tuple(sorted(slots))

    for slot in discovered:
        start = GRAPHIC_ATLAS_OFFSET + slot * GRAPHIC_ATLAS_SLOT_SIZE
        end = start + 2 * GRAPHIC_ATLAS_SLOT_SIZE
        if source_english_rom is not None and end > len(source_english_rom):
            raise RomLayoutError(f"graphical cell {slot} lies beyond the source ROM")

    available = tuple(slot for slot in discovered if slot not in exclusions)
    return GraphicSlotPool(
        mode=normalized_mode,
        discovered_slots=discovered,
        excluded_even_slots=exclusions,
        available_even_slots=available,
    )


def _font_tile(rom: bytes, code: int) -> bytes:
    if not ASCII_FONT_FIRST_CODE <= code <= ASCII_FONT_LAST_CODE:
        raise MoveLabelError(f"font code outside 0x20..0x7F: 0x{code:02X}")
    start = ASCII_FONT_OFFSET + (code - ASCII_FONT_FIRST_CODE) * ASCII_FONT_TILE_SIZE
    end = start + ASCII_FONT_TILE_SIZE
    if end > len(rom):
        raise RomLayoutError("candidate ROM is too short for the patched ASCII font")
    return rom[start:end]


def _graphic_cell(
    rom: bytes,
    top: bytes,
    bottom: bytes,
    cell_index: int,
) -> bytes:
    left = cell_index * 2

    def character(line: bytes, index: int) -> int:
        return line[index] if index < len(line) else ASCII_FONT_FIRST_CODE

    top_slot = _font_tile(rom, character(top, left)) + _font_tile(
        rom, character(top, left + 1)
    )
    bottom_slot = _font_tile(rom, character(bottom, left)) + _font_tile(
        rom, character(bottom, left + 1)
    )
    cell = top_slot + bottom_slot
    if len(cell) != 2 * GRAPHIC_ATLAS_SLOT_SIZE:
        raise AssertionError("a 16x16 graphical cell must occupy exactly two slots")
    return cell


def _payload_for_slots(slots: Sequence[int]) -> bytes:
    return b"".join(graphic_code(slot) for slot in slots) + bytes((TEXT_TERMINATOR,))


def _offset_in_ranges(offset: int, ranges: Sequence[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in ranges)


def patch_move_labels(
    candidate_rom: bytes,
    source_english_rom: bytes | None,
    specs: Sequence[MoveLabelSpec],
    *,
    pool_mode: str = "source",
    excluded_even_slots: Iterable[int] = DEFAULT_EXCLUDED_EVEN_SLOTS,
    require_all: bool = True,
) -> MoveLabelPatchResult:
    """Patch requested labels in memory and prove every changed byte is allowed."""
    candidate = bytes(candidate_rom)
    records = read_move_records(candidate)
    records_by_index = {record.move_index: record for record in records}
    if len(records_by_index) != MOVE_COUNT:
        raise AssertionError("the candidate must expose exactly 177 indexed records")

    indexes = [spec.move_index for spec in specs]
    if len(indexes) != len(set(indexes)):
        raise MoveLabelError("move-label specs contain duplicate move indexes")
    if any(not 0 <= index < MOVE_COUNT for index in indexes):
        raise MoveLabelError("move-label spec index outside 0..176")

    pool = extract_graphic_slot_pool(
        source_english_rom,
        mode=pool_mode,
        excluded_even_slots=excluded_even_slots,
    )
    requested_indexes = set(indexes)
    protected_atlas_slots = {
        occupied
        for record in records
        if record.move_index not in requested_indexes
        for start_slot in record.graphical_slots
        for occupied in (start_slot, start_slot + 1)
    }
    available_slots = tuple(
        slot
        for slot in pool.available_even_slots
        if slot not in protected_atlas_slots and slot + 1 not in protected_atlas_slots
    )

    entries: list[MoveLabelPatchEntry] = []
    planned: list[tuple[MoveLabelSpec, MoveRecord, tuple[int, ...], bytes]] = []
    pool_cursor = 0
    for spec in sorted(specs, key=lambda item: item.move_index):
        record = records_by_index[spec.move_index]
        required = spec.required_payload_size
        status = "applied"
        reason = ""
        assigned: tuple[int, ...] = ()
        payload = b""
        if required > record.capacity:
            if record.capacity < record.raw_capacity:
                status = "insufficient_disjoint_capacity"
                reason = (
                    f"needs {required} bytes, but only {record.capacity} are "
                    f"writable before live move target "
                    f"0x{record.next_live_target:06X}"
                )
            else:
                status = "insufficient_capacity"
                reason = (
                    f"needs {required} bytes, existing payload capacity is "
                    f"{record.capacity}"
                )
        elif pool_cursor + spec.code_count > len(available_slots):
            status = "insufficient_slot_pool"
            reason = (
                f"needs {spec.code_count} cells, only "
                f"{len(available_slots) - pool_cursor} remain"
            )
        else:
            assigned = available_slots[pool_cursor : pool_cursor + spec.code_count]
            pool_cursor += spec.code_count
            payload = _payload_for_slots(assigned)
            if len(payload) != required:
                raise AssertionError("graphical payload sizing diverged from the plan")
            planned.append((spec, record, assigned, payload))

        entries.append(
            MoveLabelPatchEntry(
                move_index=spec.move_index,
                full_name=spec.full_name,
                line_1=spec.line_1,
                line_2=spec.line_2,
                encoded_line_1_length=len(spec.encoded_line_1),
                encoded_line_2_length=len(spec.encoded_line_2),
                target=record.target,
                capacity=record.capacity,
                raw_capacity=record.raw_capacity,
                next_live_target=record.next_live_target,
                overlapping_move_indexes=record.overlapping_move_indexes,
                required_payload_size=required,
                code_slots=assigned,
                status=status,
                reason=reason,
            )
        )

    provisional_report = MoveLabelPatchReport(
        requested_count=len(entries),
        applied_count=len(planned),
        skipped_count=len(entries) - len(planned),
        candidate_target_count=len(records),
        candidate_unique_target_count=len({record.target for record in records}),
        pool_mode=pool.mode,
        pool_discovered_count=len(pool.discovered_slots),
        pool_available_count=len(available_slots),
        pool_protected_count=len(protected_atlas_slots),
        excluded_even_slots=pool.excluded_even_slots,
        used_even_slots=tuple(slot for _, _, slots, _ in planned for slot in slots),
        changed_offset_count=0,
        entries=tuple(entries),
    )
    if require_all and not provisional_report.complete:
        raise IncompleteMoveLabelPatch(provisional_report)

    patched = bytearray(candidate)
    allowed_ranges: list[tuple[int, int]] = []
    live_targets = {record.target for record in records}
    for spec, record, slots, payload in planned:
        payload_end = record.target + len(payload)
        if payload_end > record.target + record.capacity:
            raise AssertionError("planned write exceeds the existing move payload")
        crossed_targets = sorted(
            target
            for target in live_targets
            if record.target < target < payload_end
        )
        if crossed_targets:
            raise AssertionError(
                "planned move payload crosses live targets: "
                + ", ".join(f"0x{target:06X}" for target in crossed_targets)
            )
        patched[record.target:payload_end] = payload
        allowed_ranges.append((record.target, payload_end))

        for cell_index, slot in enumerate(slots):
            if slot in pool.excluded_even_slots:
                raise AssertionError(f"excluded graphical slot selected: {slot}")
            cell = _graphic_cell(
                candidate,
                spec.encoded_line_1,
                spec.encoded_line_2,
                cell_index,
            )
            atlas_start = GRAPHIC_ATLAS_OFFSET + slot * GRAPHIC_ATLAS_SLOT_SIZE
            atlas_end = atlas_start + len(cell)
            if atlas_end > len(patched):
                raise RomLayoutError(f"graphical cell {slot} lies beyond the candidate ROM")
            patched[atlas_start:atlas_end] = cell
            allowed_ranges.append((atlas_start, atlas_end))

    changed_offsets = tuple(
        offset
        for offset, (before, after) in enumerate(zip(candidate, patched))
        if before != after
    )
    unexpected = [
        offset for offset in changed_offsets if not _offset_in_ranges(offset, allowed_ranges)
    ]
    if unexpected:
        raise AssertionError(
            f"move-label patch changed bytes outside approved ranges: {unexpected[:8]}"
        )

    for excluded in pool.excluded_even_slots:
        start = GRAPHIC_ATLAS_OFFSET + excluded * GRAPHIC_ATLAS_SLOT_SIZE
        end = start + 2 * GRAPHIC_ATLAS_SLOT_SIZE
        if end <= len(candidate) and patched[start:end] != candidate[start:end]:
            raise AssertionError(f"excluded graphical cell {excluded} was modified")

    report = MoveLabelPatchReport(
        requested_count=provisional_report.requested_count,
        applied_count=provisional_report.applied_count,
        skipped_count=provisional_report.skipped_count,
        candidate_target_count=provisional_report.candidate_target_count,
        candidate_unique_target_count=provisional_report.candidate_unique_target_count,
        pool_mode=provisional_report.pool_mode,
        pool_discovered_count=provisional_report.pool_discovered_count,
        pool_available_count=provisional_report.pool_available_count,
        pool_protected_count=provisional_report.pool_protected_count,
        excluded_even_slots=provisional_report.excluded_even_slots,
        used_even_slots=provisional_report.used_even_slots,
        changed_offset_count=len(changed_offsets),
        entries=provisional_report.entries,
    )
    return MoveLabelPatchResult(rom=bytes(patched), report=report)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and apply two-line move graphics in memory"
    )
    parser.add_argument("candidate", type=Path, help="final candidate ROM to inspect")
    parser.add_argument("catalogue", type=Path, help="two-line move-label CSV")
    parser.add_argument(
        "--source",
        type=Path,
        help="English 2015 ROM used to extract move-owned graphical cells",
    )
    parser.add_argument("--encoder", default="ascii", help="ascii/en or french/fr")
    parser.add_argument(
        "--pool-mode",
        choices=("source", "canonical"),
        default="source",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="report labels that do not fit instead of failing",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.pool_mode == "source" and args.source is None:
        raise SystemExit("--source is required with --pool-mode=source")
    specs = load_move_label_csv(
        args.catalogue,
        encoder=resolve_text_encoder(args.encoder),
    )
    candidate = args.candidate.read_bytes()
    source = args.source.read_bytes() if args.source is not None else None
    try:
        result = patch_move_labels(
            candidate,
            source,
            specs,
            pool_mode=args.pool_mode,
            require_all=not args.allow_partial,
        )
    except IncompleteMoveLabelPatch as exc:
        print(json.dumps(exc.report.to_dict(), indent=2, ensure_ascii=False))
        return 2
    print(json.dumps(result.report.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
