#!/usr/bin/env python3
"""Unit tests for declarative, FR-compatible locale profiles."""

from __future__ import annotations

import dataclasses
import unittest

from tools.dialogue_layout import format_game_text as format_french_text
from tools.french_font import encode_game_text as encode_french_text
from tools.locales.profiles import (
    ENGLISH_RELEASE_PROFILE,
    ENGLISH_TEXT_PROFILE,
    FRENCH_RELEASE_PROFILE,
    FRENCH_TEXT_PROFILE,
    FontPolicy,
    GraphicsPolicy,
    RELEASE_PROFILES,
    get_release_profile,
)


class LocaleProfileTests(unittest.TestCase):
    def test_french_profile_delegates_to_unchanged_existing_path(self) -> None:
        source = "Pokémon très fort !"
        self.assertIs(FRENCH_TEXT_PROFILE.encoder, encode_french_text)
        self.assertIs(FRENCH_TEXT_PROFILE.formatter, format_french_text)
        self.assertEqual(
            FRENCH_TEXT_PROFILE.encode_text(source),
            encode_french_text(source),
        )
        self.assertEqual(
            FRENCH_TEXT_PROFILE.format_text(source, "dialogue_19_19"),
            format_french_text(source, "dialogue_19_19"),
        )

    def test_english_profile_binds_strict_codec_to_english_layout(self) -> None:
        self.assertEqual(ENGLISH_TEXT_PROFILE.locale, "en-US")
        self.assertEqual(
            ENGLISH_TEXT_PROFILE.format_text(
                "Pokémon is ready !",
                "dialogue_19_19",
            ),
            b"Pok@mon is ready!",
        )
        with self.assertRaisesRegex(ValueError, "reserved é glyph slot"):
            ENGLISH_TEXT_PROFILE.format_text("literal @ is forbidden", "raw")

    def test_profile_appends_allocator_terminator_only_on_request(self) -> None:
        plain = ENGLISH_TEXT_PROFILE.encode_payload("Pokémon", "raw")
        terminated = ENGLISH_TEXT_PROFILE.encode_payload(
            "Pokémon",
            "raw",
            terminated=True,
        )
        self.assertEqual(plain, b"Pok@mon")
        self.assertEqual(terminated, b"Pok@mon\x0d")
        self.assertEqual(terminated.count(b"\x0d"), 1)

    def test_unknown_layout_is_rejected_before_formatter_dispatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "not supported by en-US"):
            ENGLISH_TEXT_PROFILE.format_text("Hello", "magic_layout")

    def test_french_release_declaration_matches_existing_artifacts(self) -> None:
        profile = FRENCH_RELEASE_PROFILE
        self.assertEqual(profile.catalogue_path, "script.py")
        self.assertEqual(
            profile.artifacts.rom,
            "Pokemon_Jaune_FR_repacked_title.nes",
        )
        self.assertEqual(
            profile.artifacts.ips,
            "Pokemon_Jaune_FR_repacked_title.ips",
        )
        self.assertIs(profile.font_policy, FontPolicy.PATCH_FRENCH)
        self.assertIs(profile.graphics_policy, GraphicsPolicy.PATCH_FRENCH)
        self.assertTrue(profile.patch_french_font)
        self.assertTrue(profile.patch_french_graphics)

    def test_english_release_preserves_english_font_and_graphics(self) -> None:
        profile = ENGLISH_RELEASE_PROFILE
        self.assertEqual(profile.catalogue_path, "locales/en-US/catalog.csv")
        self.assertEqual(profile.dist_directory, "dist/en/2.0.0")
        self.assertEqual(
            profile.artifacts.rom,
            "Pokemon_Yellow_NJ046_EN_v2.0.0.nes",
        )
        self.assertEqual(
            profile.artifacts.ips,
            "Pokemon_Yellow_NJ046_EN_v2.0.0.ips",
        )
        self.assertIs(profile.font_policy, FontPolicy.PRESERVE_ENGLISH)
        self.assertIs(profile.graphics_policy, GraphicsPolicy.PRESERVE_ENGLISH)
        self.assertFalse(profile.patch_french_font)
        self.assertFalse(profile.patch_french_graphics)

    def test_profiles_share_the_verified_english_build_base(self) -> None:
        expected = (
            "d5c308b5862ccbe4647d4255a11bb0f1"
            "cb6817c4b107feac112509d658a9943b"
        )
        self.assertEqual(FRENCH_RELEASE_PROFILE.base_rom_sha256, expected)
        self.assertEqual(ENGLISH_RELEASE_PROFILE.base_rom_sha256, expected)

    def test_profile_registry_has_language_and_locale_aliases(self) -> None:
        self.assertIs(get_release_profile("fr"), FRENCH_RELEASE_PROFILE)
        self.assertIs(get_release_profile("fr-FR"), FRENCH_RELEASE_PROFILE)
        self.assertIs(get_release_profile("en"), ENGLISH_RELEASE_PROFILE)
        self.assertIs(get_release_profile("en-US"), ENGLISH_RELEASE_PROFILE)
        with self.assertRaisesRegex(ValueError, "unknown release profile"):
            get_release_profile("de")

    def test_profiles_and_registry_are_immutable(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ENGLISH_RELEASE_PROFILE.version = "3.0.0"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            RELEASE_PROFILES["de"] = FRENCH_RELEASE_PROFILE  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
