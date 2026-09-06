#!/usr/bin/env python3
"""Strict one-byte English codec for the 2015 NJ046 ASCII font.

The English patch already draws ``é`` in the ASCII ``@`` tile.  Unicode
``é`` therefore encodes to byte ``0x40`` and a literal ``@`` is rejected:
allowing both would make round trips ambiguous and could display the wrong
character in-game.  No normalization, transliteration or lossy fallback is
performed.
"""

from __future__ import annotations


PRINTABLE_ASCII_MIN = 0x20
PRINTABLE_ASCII_MAX = 0x7E
TEXT_TERMINATOR = 0x0D
LINE_BREAK_BYTE = 0x0A
LINE_BREAK_CHARACTER = "\n"
E_ACUTE_BYTE = 0x40
RESERVED_ASCII_CHARACTER = "@"


class EnglishCodecError(ValueError):
    """A character or byte cannot be represented by the English font."""


def encode_english_text(text: str) -> bytes:
    """Encode printable English text without any silent substitution.

    Printable ASCII is byte-preserving except for literal ``@``, whose font
    slot is reserved.  Unicode lowercase ``é`` is the sole non-ASCII input
    accepted by this codec and maps to that reserved byte.
    """

    encoded = bytearray()
    for index, character in enumerate(text):
        if character == LINE_BREAK_CHARACTER:
            encoded.append(LINE_BREAK_BYTE)
            continue
        if character == "é":
            encoded.append(E_ACUTE_BYTE)
            continue
        if character == RESERVED_ASCII_CHARACTER:
            raise EnglishCodecError(
                f"character {character!r} at index {index} uses the reserved "
                "é glyph slot"
            )
        value = ord(character)
        if not PRINTABLE_ASCII_MIN <= value <= PRINTABLE_ASCII_MAX:
            raise EnglishCodecError(
                f"character U+{value:04X} at index {index} is not supported "
                "by the strict English codec"
            )
        encoded.append(value)
    return bytes(encoded)


def decode_english_text(data: bytes) -> str:
    """Decode printable game bytes, interpreting ``0x40`` as Unicode ``é``."""

    decoded: list[str] = []
    for index, value in enumerate(data):
        if value == LINE_BREAK_BYTE:
            decoded.append(LINE_BREAK_CHARACTER)
            continue
        if value == E_ACUTE_BYTE:
            decoded.append("é")
            continue
        if not PRINTABLE_ASCII_MIN <= value <= PRINTABLE_ASCII_MAX:
            raise EnglishCodecError(
                f"byte 0x{value:02X} at index {index} is not printable text"
            )
        decoded.append(chr(value))
    return "".join(decoded)


def encode_terminated_english_text(text: str) -> bytes:
    """Encode one payload and append the ROM's ``0x0D`` terminator."""

    return encode_english_text(text) + bytes((TEXT_TERMINATOR,))


def decode_terminated_english_text(data: bytes) -> str:
    """Decode a payload containing exactly one final ``0x0D`` terminator."""

    if not data or data[-1] != TEXT_TERMINATOR:
        raise EnglishCodecError("English payload is missing its final 0x0D")
    if TEXT_TERMINATOR in data[:-1]:
        raise EnglishCodecError("English payload contains an early 0x0D")
    return decode_english_text(data[:-1])
