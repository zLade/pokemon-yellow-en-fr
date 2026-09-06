#!/usr/bin/env python3
"""Codec-independent English text layout for NJ046.

The English renderer uses the same physical widths as the original game:

* ordinary dialogue: 19 columns on every physical line;
* introduction dialogue: 17 columns on the first line, then 19;
* Pok\u00e9dex descriptions: at most four 13-column lines.
* item descriptions: at most three fixed seven-column lines.

Unlike :mod:`tools.dialogue_layout`, this module has no dependency on the
French codec or on the French page-quality heuristics.  Callers inject the
strict English encoder so widths are measured in the bytes that will really
be written to the ROM.  The formatter never truncates or splits a semantic
unit; an overlong word is a hard error.

The returned payload never includes the game ``0x0D`` terminator.  Keeping
termination in the allocator matches the existing builder contract.
"""

from __future__ import annotations

import re
from collections.abc import Callable


TextEncoder = Callable[[str], bytes]

RAW_LAYOUT = "raw"
DIALOGUE_LAYOUT = "dialogue_19_19"
INTRO_DIALOGUE_LAYOUT = "dialogue_intro_17_19"
POKEDEX_LAYOUT = "pokedex_13x4"
FIXED_GRID_7X3_LAYOUT = "fixed_grid_7x3"

SUPPORTED_LAYOUTS = frozenset(
    {
        "",
        RAW_LAYOUT,
        DIALOGUE_LAYOUT,
        INTRO_DIALOGUE_LAYOUT,
        POKEDEX_LAYOUT,
        FIXED_GRID_7X3_LAYOUT,
    }
)

DIALOGUE_LINE_WIDTH = 19
INTRO_FIRST_LINE_WIDTH = 17
POKEDEX_LINE_WIDTH = 13
FIXED_GRID_7X3_CAPACITY = 21
POKEDEX_MAX_LINES = 4

_REPEATED_ASCII_SPACES = re.compile(r" +")
_SPACE_BEFORE_CLOSING_PUNCTUATION = re.compile(
    r" +([!?,.:;%\)\]\}]+)"
)
_SPACE_AFTER_OPENING_PUNCTUATION = re.compile(r"([\(\[\{]) +")


def normalize_english_spacing(text: str) -> str:
    """Return canonical English horizontal spacing, preserving newlines.

    In particular, French-style spaces before ``!``, ``?``, ``:``, and
    ``;`` are removed.  Commas, periods, percent signs, and closing brackets
    follow the same English rule.  Explicit newlines remain authoritative
    physical-page requests for the wrapping functions.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines: list[str] = []
    for line in text.split("\n"):
        # Only ordinary, printable ASCII spaces are normalized.  Tabs,
        # no-break spaces, and other Unicode whitespace deliberately survive
        # until the strict English codec rejects them; layout must not become
        # a lossy character-normalization back door.
        line = _REPEATED_ASCII_SPACES.sub(" ", line).strip(" ")
        line = _SPACE_BEFORE_CLOSING_PUNCTUATION.sub(r"\1", line)
        line = _SPACE_AFTER_OPENING_PUNCTUATION.sub(r"\1", line)
        normalized_lines.append(line)
    return "\n".join(normalized_lines)


def semantic_units(text: str) -> tuple[str, ...]:
    """Return whitespace-delimited English units with punctuation attached."""
    normalized = normalize_english_spacing(text)
    return tuple(
        unit
        for unit in normalized.replace("\n", " ").split(" ")
        if unit
    )


def dialogue_line_width(
    line_index: int,
    layout: str = DIALOGUE_LAYOUT,
) -> int:
    """Return the physical width of one dialogue line."""
    if line_index < 0:
        raise ValueError("line index must be non-negative")
    if layout == DIALOGUE_LAYOUT:
        return DIALOGUE_LINE_WIDTH
    if layout == INTRO_DIALOGUE_LAYOUT:
        return (
            INTRO_FIRST_LINE_WIDTH
            if line_index == 0
            else DIALOGUE_LINE_WIDTH
        )
    raise ValueError(f"unknown English dialogue layout: {layout!r}")


def _encode(encode_text: TextEncoder, text: str) -> bytes:
    encoded = encode_text(text)
    if not isinstance(encoded, (bytes, bytearray, memoryview)):
        raise TypeError("English text encoder must return bytes")
    return bytes(encoded)


def _padding_byte(encode_text: TextEncoder) -> bytes:
    encoded_space = _encode(encode_text, " ")
    if len(encoded_space) != 1:
        raise ValueError(
            "English text encoder must encode a space as exactly one byte"
        )
    return encoded_space


def _pad(encoded: bytes, width: int, padding_byte: bytes) -> bytes:
    if len(encoded) > width:
        raise AssertionError("attempted to pad an overlong English line")
    return encoded + padding_byte * (width - len(encoded))


def _source_pages(text: str) -> tuple[str, ...]:
    normalized = normalize_english_spacing(text)
    if not normalized:
        return ()
    pages = tuple(normalized.split("\n"))
    if any(not page for page in pages):
        raise ValueError("empty forced English text page")
    return pages


def _wrap_lines(
    text: str,
    *,
    encode_text: TextEncoder,
    width_for_line: Callable[[int], int],
    maximum_lines: int | None = None,
    kind: str,
) -> tuple[bytes, ...]:
    """Greedily wrap complete semantic units within encoded byte widths."""
    pages = _source_pages(text)
    if not pages:
        return ()

    padding_byte = _padding_byte(encode_text)
    encoded_padding = padding_byte
    lines: list[bytes] = []
    line_index = 0

    def append_line(line: bytes, *, pad: bool) -> None:
        nonlocal line_index
        if maximum_lines is not None and len(lines) >= maximum_lines:
            raise ValueError(
                f"{kind} text is too long (more than "
                f"{maximum_lines} lines)"
            )
        width = width_for_line(line_index)
        lines.append(_pad(line, width, encoded_padding) if pad else line)
        line_index += 1

    for page_index, source_page in enumerate(pages):
        units = semantic_units(source_page)
        encoded_units = tuple(
            (unit, _encode(encode_text, unit)) for unit in units
        )
        current = bytearray()

        for unit, encoded_unit in encoded_units:
            width = width_for_line(line_index)
            separator_width = len(encoded_padding) if current else 0
            proposed_length = (
                len(current) + separator_width + len(encoded_unit)
            )
            if proposed_length <= width:
                if current:
                    current.extend(encoded_padding)
                current.extend(encoded_unit)
                continue

            if not current:
                raise ValueError(
                    f"English {kind} unit is too long for line "
                    f"{line_index + 1} ({len(encoded_unit)} > {width}): "
                    f"{unit!r}"
                )

            append_line(bytes(current), pad=True)
            width = width_for_line(line_index)
            if len(encoded_unit) > width:
                raise ValueError(
                    f"English {kind} unit is too long for line "
                    f"{line_index + 1} ({len(encoded_unit)} > {width}): "
                    f"{unit!r}"
                )
            current = bytearray(encoded_unit)

        # Every forced source newline ends a physical line.  Only the final
        # physical line is left unpadded, matching the current ROM builder.
        is_final_source_page = page_index == len(pages) - 1
        append_line(bytes(current), pad=not is_final_source_page)

    return tuple(lines)


def wrap_dialogue_lines(
    text: str,
    layout: str = DIALOGUE_LAYOUT,
    *,
    encode_text: TextEncoder,
) -> tuple[bytes, ...]:
    """Wrap English dialogue without splitting or truncating words."""
    if layout not in {DIALOGUE_LAYOUT, INTRO_DIALOGUE_LAYOUT}:
        raise ValueError(f"unknown English dialogue layout: {layout!r}")
    return _wrap_lines(
        text,
        encode_text=encode_text,
        width_for_line=lambda index: dialogue_line_width(index, layout),
        kind="dialogue",
    )


def wrap_dialogue_19_19(
    text: str,
    *,
    encode_text: TextEncoder,
) -> bytes:
    """Encode ordinary English dialogue on uniform 19-column lines."""
    return b"".join(
        wrap_dialogue_lines(
            text,
            DIALOGUE_LAYOUT,
            encode_text=encode_text,
        )
    )


def wrap_dialogue_17_19(
    text: str,
    *,
    encode_text: TextEncoder,
) -> bytes:
    """Encode English introduction text on a 17/19-column layout."""
    return b"".join(
        wrap_dialogue_lines(
            text,
            INTRO_DIALOGUE_LAYOUT,
            encode_text=encode_text,
        )
    )


def wrap_pokedex_lines(
    text: str,
    *,
    encode_text: TextEncoder,
) -> tuple[bytes, ...]:
    """Wrap English Pok\u00e9dex text on at most four 13-column lines."""
    return _wrap_lines(
        text,
        encode_text=encode_text,
        width_for_line=lambda _index: POKEDEX_LINE_WIDTH,
        maximum_lines=POKEDEX_MAX_LINES,
        kind="Pok\u00e9dex",
    )


def wrap_pokedex_13x4(
    text: str,
    *,
    encode_text: TextEncoder,
) -> bytes:
    """Encode an English Pok\u00e9dex description within its 13x4 box."""
    return b"".join(wrap_pokedex_lines(text, encode_text=encode_text))


def format_game_text(
    text: str,
    layout: str = "",
    *,
    encode_text: TextEncoder,
) -> bytes:
    """Encode English source according to its explicitly declared layout."""
    if layout in {"", RAW_LAYOUT}:
        return _encode(encode_text, text)
    if layout == DIALOGUE_LAYOUT:
        return wrap_dialogue_19_19(text, encode_text=encode_text)
    if layout == INTRO_DIALOGUE_LAYOUT:
        return wrap_dialogue_17_19(text, encode_text=encode_text)
    if layout == POKEDEX_LAYOUT:
        return wrap_pokedex_13x4(text, encode_text=encode_text)
    if layout == FIXED_GRID_7X3_LAYOUT:
        payload = _encode(encode_text, text)
        if len(payload) > FIXED_GRID_7X3_CAPACITY:
            raise ValueError(
                "fixed 7x3 text is too long "
                f"({len(payload)} > {FIXED_GRID_7X3_CAPACITY})"
            )
        return payload
    raise ValueError(f"unknown English text layout: {layout!r}")


def bind_encoder(
    encode_text: TextEncoder,
) -> Callable[[str, str], bytes]:
    """Bind a strict codec and return a profile-friendly formatter callable."""
    # Validate the only byte-level assumption up front, so a malformed codec
    # fails while the profile is constructed rather than halfway through a
    # release build.
    _padding_byte(encode_text)

    def formatter(text: str, layout: str = "") -> bytes:
        return format_game_text(text, layout, encode_text=encode_text)

    return formatter
