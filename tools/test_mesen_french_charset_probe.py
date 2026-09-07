#!/usr/bin/env python3
"""Static contracts for the exhaustive Mesen French-charset probe."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    TRANSLATION_BASE_ROM,
    parse_patch_entries,
)
from tools.dialogue_layout import format_game_text  # noqa: E402
from tools.french_font import (  # noqa: E402
    ASCII_FONT_FIRST_CODE,
    ASCII_FONT_OFFSET,
    ASCII_FONT_TILE_SIZE,
    FRENCH_GLYPH_LABELS,
    FRENCH_NATIVE_GLYPH_CODES,
    encode_game_text,
    extract_ascii_font,
    patch_french_font,
)


PROBE_PATH = ROM_DIR / "tools" / "mesen_intro_french_accents_probe.lua"
MANIFEST_PATH = (
    ROM_DIR
    / "tools"
    / "data"
    / "mesen_french_charset_probe_expected.json"
)


def lua_hex_constant(source: str, name: str) -> str:
    match = re.search(
        rf"local {re.escape(name)}\s*=\s*(.*?)(?=\nlocal )",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Missing Lua constant : {name}")
    chunks = re.findall(r'"([0-9a-fA-F]+)"', match.group(1))
    if not chunks:
        raise AssertionError(f"Empty hexadecimal Lua constant: {name}")
    return "".join(chunks).lower()


def lua_glyph_rows(source: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"""\{\s*
        label\s*=\s*"(?P<label>[^"]+)",\s*
        character\s*=\s*"(?P<character>[^"]+)",\s*
        code\s*=\s*0x(?P<code>[0-9A-Fa-f]{2}),\s*
        romOffset\s*=\s*0x(?P<offset>[0-9A-Fa-f]{6}),\s*
        expectedHex\s*=\s*"(?P<tile>[0-9A-Fa-f]{32})",\s*
        \}""",
        flags=re.VERBOSE,
    )
    return [
        {
            "character": match.group("character"),
            "label": match.group("label"),
            "code": f"0x{match.group('code').upper()}",
            "rom_offset": f"0x{match.group('offset').upper()}",
            "tile_hex": match.group("tile").lower(),
        }
        for match in pattern.finditer(source)
    ]


class MesenFrenchCharsetProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.probe = PROBE_PATH.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.base = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
        cls.patched = bytearray(cls.base)
        patch_french_font(cls.patched)
        cls.font = extract_ascii_font(bytes(cls.patched))

    def test_manifest_glyphs_are_generated_from_the_canonical_font(self) -> None:
        expected = []
        for code in sorted(FRENCH_NATIVE_GLYPH_CODES):
            label, character = FRENCH_GLYPH_LABELS[code]
            tile_index = code - ASCII_FONT_FIRST_CODE
            tile_start = tile_index * ASCII_FONT_TILE_SIZE
            expected.append(
                {
                    "character": character,
                    "label": label,
                    "code": f"0x{code:02X}",
                    "rom_offset": (
                        f"0x{ASCII_FONT_OFFSET + tile_start:06X}"
                    ),
                    "tile_hex": self.font[
                        tile_start : tile_start + ASCII_FONT_TILE_SIZE
                    ].hex(),
                }
            )
        self.assertEqual(self.manifest["native_glyph_count"], 16)
        self.assertEqual(self.manifest["glyphs"], expected)
        self.assertEqual(lua_glyph_rows(self.probe), expected)

    def test_diagnostic_record_contains_each_native_glyph_once(self) -> None:
        semantic = self.manifest["semantic_sequence"]
        encoded = encode_game_text(semantic)
        self.assertEqual(len(semantic), 16)
        self.assertEqual(len(encoded), 16)
        self.assertEqual(set(encoded), FRENCH_NATIVE_GLYPH_CODES)
        self.assertEqual(encoded.hex(), self.manifest["encoded_sequence_hex"])

        diagnostic_hex = self.manifest["diagnostic_record_hex"]
        self.assertEqual(
            lua_hex_constant(self.probe, "DIAGNOSTIC_RECORD_HEX"),
            diagnostic_hex,
        )
        diagnostic = bytes.fromhex(diagnostic_hex)
        self.assertEqual(len(diagnostic), 104)
        self.assertEqual(diagnostic[17:33], encoded)
        self.assertEqual(diagnostic[-1:], b"\x0D")
        for code in encoded:
            self.assertEqual(diagnostic.count(code), 1)

    def test_original_intro_record_and_transient_write_count_are_exact(
        self,
    ) -> None:
        entry = next(
            entry
            for entry in parse_patch_entries()
            if entry.offset == 0x035E82
        )
        original = format_game_text(entry.text, entry.layout) + b"\x0D"
        self.assertEqual(len(original), 104)
        self.assertEqual(
            lua_hex_constant(self.probe, "ORIGINAL_RECORD_HEX"),
            original.hex(),
        )
        diagnostic = bytes.fromhex(self.manifest["diagnostic_record_hex"])
        changed = sum(
            before != after
            for before, after in zip(original, diagnostic, strict=True)
        )
        self.assertEqual(
            changed,
            self.manifest["transient_prg_patch_writes"],
        )
        self.assertEqual(
            changed,
            self.manifest["transient_prg_restore_writes"],
        )
        self.assertEqual(changed, 91)

    def test_page_and_artifact_contract_is_complete(self) -> None:
        self.assertEqual(
            self.manifest["page_boundaries"],
            [[0, 35], [36, 73], [74, 102]],
        )
        self.assertEqual(self.manifest["required_page"], 1)
        self.assertEqual(
            self.manifest["pass_marker"],
            "POKEMON_FRENCH_CHARSET_EXHAUSTIVE_PASS",
        )
        self.assertIn(self.manifest["pass_marker"], self.probe)
        for suffix in (
            ".png",
            "_chr_ram_8k.bin",
            "_ppu_pattern_8k.bin",
            "_nametable_4k.bin",
            "_palette_32.bin",
            "_oam_256.bin",
        ):
            self.assertIn(f'prefix .. "{suffix}"', self.probe)
        self.assertIn(
            '"french_charset_exhaustive_validation.txt"',
            self.probe,
        )

    def test_probe_asserts_the_full_runtime_evidence_chain(self) -> None:
        required_snippets = (
            "emu.memType.nesPrgRom",
            "installTransientRecord()",
            "restoreTransientRecord()",
            "targetUniqueBytesRead=%d/%d",
            "glyphData.sourcePlane0 ~= 8",
            "glyphData.sourceEvents < 16",
            "glyphData.ppuWritesNearSourceReads < 32",
            "matchingReferences ~= referenceCount",
            "missing completed target page",
            "transientPrgRecordRestored=",
            "diskRomWritesByProbe=0",
            "cpuRamWritesByProbe=0",
            "ppuWritesByProbe=0",
            "mapperWritesByProbe=0",
            "savestateRewindCheat=false",
        )
        for snippet in required_snippets:
            self.assertIn(snippet, self.probe)
        writes = list(re.finditer(r"\bemu\.write\s*\(", self.probe))
        self.assertEqual(len(writes), 2)
        self.assertNotIn("emu.memType.nesMemory)", self.probe)
        self.assertNotIn("emu.memType.nesDebug)", self.probe)


if __name__ == "__main__":
    unittest.main()
