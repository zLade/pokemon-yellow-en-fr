#!/usr/bin/env python3
"""Deterministic layouts for the NJ046 two-line dialogue boxes.

The regular overworld/NPC/laboratory renderer consumes 19 printable columns
on every line.  The introduction uses a separate renderer whose first line is
indented by two columns: 17 columns, then 19 on every following line.  Neither
renderer wraps on spaces, so semantic source strings need explicit padding at
the correct boundaries or a word can be split between lines or bubbles.
"""

from __future__ import annotations

import re

from tools.french_font import decode_game_text, encode_game_text


DIALOGUE_LAYOUT = "dialogue_19_19"
INTRO_DIALOGUE_LAYOUT = "dialogue_intro_17_19"
RAW_LAYOUT = "raw"
POKEDEX_LAYOUT = "pokedex_13x4"
SUPPORTED_LAYOUTS = frozenset(
    {
        "",
        RAW_LAYOUT,
        DIALOGUE_LAYOUT,
        INTRO_DIALOGUE_LAYOUT,
        POKEDEX_LAYOUT,
    }
)
DIALOGUE_LINE_WIDTH = 19
INTRO_FIRST_LINE_WIDTH = 17
POKEDEX_LINE_WIDTH = 13
POKEDEX_MAX_LINES = 4

_SPACE_BEFORE_PUNCTUATION = frozenset({"!", "?", ":", ";"})
_PUNCTUATION_ONLY = re.compile(r"^[!?:;]+$")
_LEXICAL_CONNECTORS = frozenset({"'", "’", "-"})


def semantic_units(text: str) -> list[str]:
    """Collapse source whitespace and keep French punctuation with its word."""
    units: list[str] = []
    for token in text.split():
        if _PUNCTUATION_ONLY.fullmatch(token) and units:
            separator = (
                " "
                if token[0] in _SPACE_BEFORE_PUNCTUATION
                else ""
            )
            units[-1] += separator + token
        else:
            units.append(token)
    return units


def dialogue_line_width(
    line_index: int,
    layout: str = DIALOGUE_LAYOUT,
) -> int:
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
    raise ValueError(f"unknown dialogue layout: {layout!r}")


def dialogue_boundaries(
    encoded_length: int,
    layout: str = DIALOGUE_LAYOUT,
) -> tuple[int, ...]:
    """Return every physical-line boundary inside an encoded payload."""
    if encoded_length < 0:
        raise ValueError("encoded length must be non-negative")
    boundaries: list[int] = []
    line_index = 0
    boundary = dialogue_line_width(line_index, layout)
    while boundary < encoded_length:
        boundaries.append(boundary)
        line_index += 1
        boundary += dialogue_line_width(line_index, layout)
    return tuple(boundaries)


def wrap_dialogue_lines_greedy(
    text: str,
    layout: str = DIALOGUE_LAYOUT,
) -> tuple[bytes, ...]:
    """Return the legacy greedy physical-line plan.

    A newline in the semantic source forces the next renderer page.  This is
    useful for the ordinary one-line dialogue box when a greedy word wrap is
    technically correct but produces an awkward, hard-to-read sequence of
    fragments.  Empty forced pages are rejected.
    """
    if layout not in {DIALOGUE_LAYOUT, INTRO_DIALOGUE_LAYOUT}:
        raise ValueError(f"unknown dialogue layout: {layout!r}")
    source_pages = text.splitlines()
    if not source_pages:
        return ()
    if any(not page.strip() for page in source_pages):
        raise ValueError("empty forced dialogue page")

    lines: list[bytes] = []
    line_index = 0

    for page_index, source_page in enumerate(source_pages):
        units = semantic_units(source_page)
        encoded_units: list[bytes] = []
        for unit in units:
            encoded = encode_game_text(unit)
            if len(encoded) > DIALOGUE_LINE_WIDTH:
                raise ValueError(
                    "lexical unit too long for a dialogue line "
                    f"({len(encoded)} > {DIALOGUE_LINE_WIDTH}): {unit!r}"
                )
            encoded_units.append(encoded)

        current = bytearray()
        for source_unit, unit in zip(units, encoded_units):
            width = dialogue_line_width(line_index, layout)
            separator = 1 if current else 0
            if len(current) + separator + len(unit) <= width:
                if current:
                    current.append(0x20)
                current.extend(unit)
                continue

            if not current:
                raise ValueError(
                    "first unit too long for the current line "
                    f"({len(unit)} > {width}): {source_unit!r}"
                )

            lines.append(bytes(current).ljust(width, b" "))
            line_index += 1
            width = dialogue_line_width(line_index, layout)
            if len(unit) > width:
                raise ValueError(
                    "lexical unit too long for the current line "
                    f"({len(unit)} > {width}): {source_unit!r}"
                )
            current = bytearray(unit)

        is_last_source_page = page_index == len(source_pages) - 1
        width = dialogue_line_width(line_index, layout)
        lines.append(
            bytes(current)
            if is_last_source_page
            else bytes(current).ljust(width, b" ")
        )
        line_index += 1

    return tuple(lines)


def wrap_dialogue_lines(
    text: str,
    layout: str = DIALOGUE_LAYOUT,
) -> tuple[bytes, ...]:
    """Return the release page plan for one dialogue.

    Ordinary field dialogue uses the French page-aware dynamic-programming
    planner.  It keeps the greedy minimum page count and the exact encoded
    byte budget, so the linguistic improvement cannot consume additional ROM
    space.  Explicit newlines remain authoritative.  The distinct
    introduction renderer keeps its observed legacy 17/19-column behaviour.
    """
    if layout == DIALOGUE_LAYOUT:
        # Local import avoids a module cycle: the quality planner reuses the
        # constants and the explicit legacy wrapper defined above.
        from tools.dialogue_page_quality import wrap_dialogue_lines_dp

        return wrap_dialogue_lines_dp(
            text,
            layout,
            preserve_forced_pages=True,
            preserve_minimum_page_count=True,
            preserve_encoded_length=True,
        )
    return wrap_dialogue_lines_greedy(text, layout)


def wrap_dialogue_19_19(text: str) -> bytes:
    """Encode a regular dialogue with two uniform 19-column lines."""
    return b"".join(wrap_dialogue_lines(text, DIALOGUE_LAYOUT))


def wrap_dialogue_17_19(text: str) -> bytes:
    """Encode an introduction dialogue with a 17-column first line."""
    return b"".join(wrap_dialogue_lines(text, INTRO_DIALOGUE_LAYOUT))


def wrap_pokedex_lines(text: str) -> tuple[bytes, ...]:
    """Wrap a Pokédex description on at most four 13-column lines."""
    units = semantic_units(text)
    if not units:
        return ()

    encoded_units: list[bytes] = []
    for unit in units:
        encoded = encode_game_text(unit)
        if len(encoded) > POKEDEX_LINE_WIDTH:
            raise ValueError(
                "lexical unit too long for a Pokédex line "
                f"({len(encoded)} > {POKEDEX_LINE_WIDTH}): {unit!r}"
            )
        encoded_units.append(encoded)

    lines: list[bytes] = []
    current = bytearray()
    for source_unit, unit in zip(units, encoded_units):
        separator = 1 if current else 0
        if len(current) + separator + len(unit) <= POKEDEX_LINE_WIDTH:
            if current:
                current.append(0x20)
            current.extend(unit)
            continue

        if not current:
            raise ValueError(
                "first unit too long for a Pokédex line: "
                f"{source_unit!r}"
            )
        lines.append(bytes(current).ljust(POKEDEX_LINE_WIDTH, b" "))
        if len(lines) >= POKEDEX_MAX_LINES:
            raise ValueError(
                "Pokédex description too long "
                f"(more than {POKEDEX_MAX_LINES} lines)"
            )
        current = bytearray(unit)

    lines.append(bytes(current))
    if len(lines) > POKEDEX_MAX_LINES:
        raise ValueError(
            "Pokédex description too long "
            f"({len(lines)} > {POKEDEX_MAX_LINES} lines)"
        )
    return tuple(lines)


def wrap_pokedex_13x4(text: str) -> bytes:
    """Encode a complete four-line Pokédex description."""
    return b"".join(wrap_pokedex_lines(text))


def format_game_text(text: str, layout: str = "") -> bytes:
    """Encode a source string according to its explicitly declared layout."""
    if layout in {"", RAW_LAYOUT}:
        return encode_game_text(text)
    if layout == DIALOGUE_LAYOUT:
        return wrap_dialogue_19_19(text)
    if layout == INTRO_DIALOGUE_LAYOUT:
        return wrap_dialogue_17_19(text)
    if layout == POKEDEX_LAYOUT:
        return wrap_pokedex_13x4(text)
    raise ValueError(f"unknown text layout: {layout!r}")


def _is_lexical_character(character: str) -> bool:
    return (
        character.isalpha()
        or character.isdigit()
        or character in _LEXICAL_CONNECTORS
    )


def text_midword_boundary_positions(
    text: str,
    layout: str = DIALOGUE_LAYOUT,
) -> tuple[int, ...]:
    """Return raw renderer boundaries that split one lexical sequence.

    The source-character ownership table is essential for French: accented
    letters occupy repurposed punctuation byte slots, and ``œ`` expands to
    two bytes.  Looking only at ``bytes.isalpha()`` would therefore miss real
    cuts such as ``rés|urrection``.
    """
    encoded = bytearray()
    owners: list[str] = []
    for character in text:
        part = encode_game_text(character)
        encoded.extend(part)
        owners.extend([character] * len(part))

    positions: list[int] = []
    for boundary in dialogue_boundaries(len(encoded), layout):
        if (
            _is_lexical_character(owners[boundary - 1])
            and _is_lexical_character(owners[boundary])
        ):
            positions.append(boundary)
    return tuple(positions)


def midword_boundary_positions(
    encoded: bytes,
    layout: str = DIALOGUE_LAYOUT,
) -> tuple[int, ...]:
    """Return boundaries between encoded lexical characters.

    Prefer :func:`text_midword_boundary_positions` when source text is
    available; it also preserves ownership of multi-byte fallbacks.
    """
    decoded = decode_game_text(encoded)
    positions: list[int] = []
    for boundary in dialogue_boundaries(len(encoded), layout):
        if (
            _is_lexical_character(decoded[boundary - 1])
            and _is_lexical_character(decoded[boundary])
        ):
            positions.append(boundary)
    return tuple(positions)
