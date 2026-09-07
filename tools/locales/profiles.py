#!/usr/bin/env python3
"""Declarative French and English text/release profiles.

The existing French builder remains authoritative and unchanged.  These
profiles expose its current choices next to the English 2.0 choices so the
future shared builder can select behaviour from data instead of language-
specific conditionals.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from tools.dialogue_layout import (
    SUPPORTED_LAYOUTS as FRENCH_SUPPORTED_LAYOUTS,
)
from tools.dialogue_layout import format_game_text as format_french_text
from tools.french_font import (
    REPURPOSED_ASCII_CODES,
    decode_game_text as decode_french_text,
    encode_game_text as encode_french_text,
)
from tools.locales.english_codec import (
    PRINTABLE_ASCII_MAX,
    PRINTABLE_ASCII_MIN,
    RESERVED_ASCII_CHARACTER,
    TEXT_TERMINATOR,
    LINE_BREAK_BYTE,
    decode_english_text,
    encode_english_text,
)
from tools.locales.english_layout import (
    SUPPORTED_LAYOUTS as ENGLISH_SUPPORTED_LAYOUTS,
)
from tools.locales.english_layout import bind_encoder


TextEncoder = Callable[[str], bytes]
TextDecoder = Callable[[bytes], str]
TextFormatter = Callable[[str, str], bytes]


@dataclass(frozen=True, slots=True)
class TextProfile:
    """All byte-level text behaviour selected by one locale."""

    locale: str
    encoder: TextEncoder
    decoder: TextDecoder
    formatter: TextFormatter
    supported_layouts: frozenset[str]
    reserved_ascii_literals: frozenset[str] = frozenset()
    terminator: int = TEXT_TERMINATOR
    printable_min: int = PRINTABLE_ASCII_MIN
    printable_max: int = PRINTABLE_ASCII_MAX
    renderer_control_bytes: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        if not self.locale or "-" not in self.locale:
            raise ValueError("locale must be an explicit language-region tag")
        if not self.supported_layouts:
            raise ValueError("a text profile must declare supported layouts")
        if not 0 <= self.terminator <= 0xFF:
            raise ValueError("text terminator must fit in one byte")
        if self.printable_min > self.printable_max:
            raise ValueError("invalid printable byte range")
        if self.printable_min <= self.terminator <= self.printable_max:
            raise ValueError("text terminator cannot be a printable byte")
        if any(not 0 <= value <= 0xFF for value in self.renderer_control_bytes):
            raise ValueError("renderer control bytes must fit in one byte")
        if self.terminator in self.renderer_control_bytes:
            raise ValueError("text terminator cannot be a renderer control")
        if any(
            self.printable_min <= value <= self.printable_max
            for value in self.renderer_control_bytes
        ):
            raise ValueError("renderer controls cannot overlap printable bytes")
        if any(len(character) != 1 for character in self.reserved_ascii_literals):
            raise ValueError("reserved literals must be single characters")

    def encode_text(self, text: str) -> bytes:
        """Delegate plain text to this locale's canonical strict encoder."""

        encoded = self.encoder(text)
        if not isinstance(encoded, bytes):
            raise TypeError("a text profile encoder must return bytes")
        return encoded

    def format_text(self, text: str, layout: str = "") -> bytes:
        """Format text for a declared renderer layout, without termination."""

        if layout not in self.supported_layouts:
            raise ValueError(
                f"layout {layout!r} is not supported by {self.locale}"
            )
        encoded = self.formatter(text, layout)
        if not isinstance(encoded, bytes):
            raise TypeError("a text profile formatter must return bytes")
        if any(
            not self.printable_min <= value <= self.printable_max
            and value not in self.renderer_control_bytes
            for value in encoded
        ):
            raise ValueError(
                f"{self.locale} formatter returned a non-printable byte"
            )
        return encoded

    def terminate(self, payload: bytes) -> bytes:
        """Append exactly one allocator-level text terminator."""

        if not isinstance(payload, bytes):
            raise TypeError("text payload must be bytes")
        if self.terminator in payload:
            raise ValueError("an unterminated text payload contains 0x0D")
        return payload + bytes((self.terminator,))

    def encode_payload(
        self,
        text: str,
        layout: str = "",
        *,
        terminated: bool = False,
    ) -> bytes:
        """Format one payload and optionally append its ROM terminator."""

        payload = self.format_text(text, layout)
        return self.terminate(payload) if terminated else payload


class FontPolicy(str, Enum):
    """How a release treats the base ROM's printable ASCII font."""

    PATCH_FRENCH = "patch_french"
    PRESERVE_ENGLISH = "preserve_english"


class GraphicsPolicy(str, Enum):
    """How a release treats the base ROM's title/menu graphics."""

    PATCH_FRENCH = "patch_french"
    PRESERVE_ENGLISH = "preserve_english"


@dataclass(frozen=True, slots=True)
class ReleaseArtifacts:
    """Names of the distributable and locally verified release artifacts."""

    rom: str
    ips: str
    bps_from_chinese: str
    bps_from_english: str

    def __post_init__(self) -> None:
        expected_suffixes = {
            "rom": ".nes",
            "ips": ".ips",
            "bps_from_chinese": ".bps",
            "bps_from_english": ".bps",
        }
        for field_name, suffix in expected_suffixes.items():
            value = getattr(self, field_name)
            if not value or "/" in value or "\\" in value:
                raise ValueError(f"{field_name} must be a plain filename")
            if not value.endswith(suffix):
                raise ValueError(f"{field_name} must end in {suffix}")
        if len(set(self.as_tuple())) != 4:
            raise ValueError("release artifact names must be distinct")

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (
            self.rom,
            self.ips,
            self.bps_from_chinese,
            self.bps_from_english,
        )


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ReleaseProfile:
    """Declarative release choices consumed by a multilingual builder."""

    key: str
    version: str
    text: TextProfile
    catalogue_path: str
    restoration_catalogue: str
    base_rom_filename: str
    base_rom_sha256: str
    canonical_ips_base_filename: str
    canonical_ips_base_sha256: str
    artifacts: ReleaseArtifacts
    dist_directory: str
    font_policy: FontPolicy
    graphics_policy: GraphicsPolicy

    def __post_init__(self) -> None:
        if not self.key or not self.key.isascii():
            raise ValueError("release key must be non-empty ASCII")
        if not self.version:
            raise ValueError("release version is required")
        for label, digest in (
            ("base ROM", self.base_rom_sha256),
            ("canonical IPS base", self.canonical_ips_base_sha256),
        ):
            if not _SHA256_RE.fullmatch(digest):
                raise ValueError(f"{label} SHA-256 must be lowercase hex")
        if self.dist_directory.startswith(("/", "\\")):
            raise ValueError("distribution directory must be repository-relative")
        if not self.catalogue_path.endswith((".py", ".csv")) and self.catalogue_path != "translation":
            raise ValueError(
                "canonical catalogue must be a Python source, CSV file or the translation directory"
            )

    @property
    def patch_french_font(self) -> bool:
        return self.font_policy is FontPolicy.PATCH_FRENCH

    @property
    def patch_french_graphics(self) -> bool:
        return self.graphics_policy is GraphicsPolicy.PATCH_FRENCH


FRENCH_TEXT_PROFILE = TextProfile(
    locale="fr-FR",
    encoder=encode_french_text,
    decoder=decode_french_text,
    formatter=format_french_text,
    supported_layouts=FRENCH_SUPPORTED_LAYOUTS,
    reserved_ascii_literals=frozenset(
        chr(code) for code in REPURPOSED_ASCII_CODES
    ),
    renderer_control_bytes=frozenset({LINE_BREAK_BYTE}),
)

ENGLISH_TEXT_PROFILE = TextProfile(
    locale="en-US",
    encoder=encode_english_text,
    decoder=decode_english_text,
    formatter=bind_encoder(encode_english_text),
    supported_layouts=ENGLISH_SUPPORTED_LAYOUTS,
    reserved_ascii_literals=frozenset({RESERVED_ASCII_CHARACTER}),
    renderer_control_bytes=frozenset({LINE_BREAK_BYTE}),
)

FRENCH_RELEASE_PROFILE = ReleaseProfile(
    key="fr",
    version="2.0.0",
    text=FRENCH_TEXT_PROFILE,
    catalogue_path="script.py",
    restoration_catalogue=(
        "tools.chinese_dialogue_restorations:RESTORED_DIALOGUES"
    ),
    base_rom_filename="Pokemon Yellow English 9-23-2015.nes",
    base_rom_sha256=(
        "d5c308b5862ccbe4647d4255a11bb0f1"
        "cb6817c4b107feac112509d658a9943b"
    ),
    canonical_ips_base_filename="Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes",
    canonical_ips_base_sha256=(
        "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed"
    ),
    artifacts=ReleaseArtifacts(
        rom="Pokemon_Jaune_FR_repacked_title.nes",
        ips="Pokemon_Jaune_FR_repacked_title.ips",
        bps_from_chinese=(
            "Pokemon_Jaune_FR_repacked_title_from_chinese.bps"
        ),
        bps_from_english=(
            "Pokemon_Jaune_FR_repacked_title_from_english.bps"
        ),
    ),
    dist_directory="dist/fr/2.0.0",
    font_policy=FontPolicy.PATCH_FRENCH,
    graphics_policy=GraphicsPolicy.PATCH_FRENCH,
)

ENGLISH_RELEASE_PROFILE = ReleaseProfile(
    key="en",
    version="2.0.0",
    text=ENGLISH_TEXT_PROFILE,
    catalogue_path="translation",
    restoration_catalogue="translation",
    base_rom_filename="Pokemon Yellow English 9-23-2015.nes",
    base_rom_sha256=(
        "d5c308b5862ccbe4647d4255a11bb0f1"
        "cb6817c4b107feac112509d658a9943b"
    ),
    canonical_ips_base_filename="Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes",
    canonical_ips_base_sha256=(
        "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed"
    ),
    artifacts=ReleaseArtifacts(
        rom="Pokemon_Yellow_NJ046_EN_v2.0.0.nes",
        ips="Pokemon_Yellow_NJ046_EN_v2.0.0.ips",
        bps_from_chinese=(
            "Pokemon_Yellow_NJ046_EN_v2.0.0_from_chinese.bps"
        ),
        bps_from_english=(
            "Pokemon_Yellow_NJ046_EN_v2.0.0_from_english_2015.bps"
        ),
    ),
    dist_directory="dist/en/2.0.0",
    font_policy=FontPolicy.PRESERVE_ENGLISH,
    graphics_policy=GraphicsPolicy.PRESERVE_ENGLISH,
)

# Short aliases are convenient for command-line selectors while the verbose
# names remain unambiguous in imports and test failures.
FR_TEXT_PROFILE = FRENCH_TEXT_PROFILE
EN_TEXT_PROFILE = ENGLISH_TEXT_PROFILE
FR_RELEASE_PROFILE = FRENCH_RELEASE_PROFILE
EN_RELEASE_PROFILE = ENGLISH_RELEASE_PROFILE

RELEASE_PROFILES: Mapping[str, ReleaseProfile] = MappingProxyType(
    {
        "fr": FRENCH_RELEASE_PROFILE,
        "fr-FR": FRENCH_RELEASE_PROFILE,
        "en": ENGLISH_RELEASE_PROFILE,
        "en-US": ENGLISH_RELEASE_PROFILE,
    }
)


def get_release_profile(key: str) -> ReleaseProfile:
    """Return a declared profile or fail with a deterministic useful error."""

    try:
        return RELEASE_PROFILES[key]
    except KeyError as exc:
        available = ", ".join(sorted(RELEASE_PROFILES))
        raise ValueError(
            f"unknown release profile {key!r}; available: {available}"
        ) from exc
