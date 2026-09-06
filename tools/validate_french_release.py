#!/usr/bin/env python3
"""Validate the historical French 2.0.1 patch-only release.

This gate is intentionally separate from the archived 2.0.0 completion gate:
it reconstructs 2.0.1 through all three published routes, proves that its only
binary delta from 2.0.0 is the shared title-credit patch, and validates the
mapper contract.  An optional Mesen directory binds the title probe to the
exact 2.0.1 target hash.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .bps_patch import apply_patch as apply_bps
    from .title_screen_tools import (
        ENGLISH_CREDIT_NT_COLUMN,
        ENGLISH_CREDIT_NT_ROW,
        TITLE_NT_FILE,
        TITLE_PT1_FILE,
        title_credit_tiles,
    )
    from .validate_mapper163 import build_parser as mapper_parser, validate
except ImportError:  # Direct ``python tools/validate_french_release.py`` use.
    from bps_patch import apply_patch as apply_bps
    from title_screen_tools import (
        ENGLISH_CREDIT_NT_COLUMN,
        ENGLISH_CREDIT_NT_ROW,
        TITLE_NT_FILE,
        TITLE_PT1_FILE,
        title_credit_tiles,
    )
    from validate_mapper163 import build_parser as mapper_parser, validate

from rom_traduction_assistant import apply_ips, parse_ips


RELEASE_DIR = ROOT / "releases/fr/2.0.1"
ARCHIVE_DIR = ROOT / "releases/fr/2.0.0"
TARGET_SHA256 = (
    "78b1deb554a37541399574c2b94fa1a06327e4de51339fa2b8f555350deef85f"
)
ARCHIVE_SHA256 = (
    "1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b"
)
MESEN_SHA256 = (
    "8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7"
)
TITLE_PROBE_SHA256 = (
    "9c71e3177e17ac5bdbbab5a33d274b1ed988b6c0501fbe873a42aa5129d12f4e"
)
EXPECTED_TITLE_MARKER = "TITLE_EN_MENU_FR_PASS"
SOURCE_SHA256 = {
    "chinese": "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed",
    "english_2015": "d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac112509d658a9943b",
    "yellow": "69520103102677b33b47c15fae804dc1a742347a9ee1b02a9195e795eb6e431b",
}

# Frozen layout used by release 2.0.1. The active title renderer later
# stopped borrowing tile $A3 because it is the live title-menu cursor.
LEGACY_V201_CREDIT_TILE_IDS = (
    0x66,
    0x78,
    0x8C,
    *range(0x91, 0x9E),
    *range(0xA0, 0xA4),
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _ips(source: bytes, path: Path) -> bytes:
    records, truncate = parse_ips(path)
    return apply_ips(source, records, truncate)


def patch_legacy_v201_title_credits(rom: bytearray) -> None:
    """Apply the immutable title-credit layout published in FR 2.0.1."""
    for tile_id, tile in zip(
        LEGACY_V201_CREDIT_TILE_IDS,
        title_credit_tiles("LUIGA2009, ZLADE, CHPEXO"),
        strict=True,
    ):
        offset = TITLE_PT1_FILE + tile_id * 16
        rom[offset : offset + 16] = tile
    nt_offset = TITLE_NT_FILE + (
        ENGLISH_CREDIT_NT_ROW * 32 + ENGLISH_CREDIT_NT_COLUMN
    )
    rom[nt_offset : nt_offset + len(LEGACY_V201_CREDIT_TILE_IDS)] = bytes(
        LEGACY_V201_CREDIT_TILE_IDS
    )


def _manifest_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return fields


def validate_mesen_title(evidence_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest = evidence_dir / "mesen_run_manifest.txt"
    stdout_path = evidence_dir / "mesen.stdout.txt"
    stderr_path = evidence_dir / "mesen.stderr.txt"
    chr_path = evidence_dir / "title_en_chr_ram_8k.bin"
    nametable_path = evidence_dir / "title_en_nametable_4k.bin"
    try:
        fields = _manifest_fields(manifest)
        stdout = stdout_path.read_bytes()
        stderr = stderr_path.read_bytes()
        chr_ram = chr_path.read_bytes()
        nametable = nametable_path.read_bytes()
    except OSError as exc:
        return [f"cannot read Mesen title evidence: {exc}"]

    expected = {
        "ROM SHA-256 before": TARGET_SHA256,
        "ROM SHA-256 after": TARGET_SHA256,
        "Mesen executable SHA-256": MESEN_SHA256,
        "Lua scenario SHA-256 before": TITLE_PROBE_SHA256,
        "Lua scenario SHA-256 after": TITLE_PROBE_SHA256,
        "Expected marker": EXPECTED_TITLE_MARKER,
        "Expected marker observed": "True",
        "Mesen process exit code": "0",
        "Timed out": "False",
        "Result": "PASS",
    }
    for key, wanted in expected.items():
        if fields.get(key) != wanted:
            errors.append(f"Mesen {key}: {fields.get(key)!r} != {wanted!r}")
    for key, payload in (
        ("Mesen stdout SHA-256", stdout),
        ("Mesen stderr SHA-256", stderr),
    ):
        if fields.get(key) != sha256(payload):
            errors.append(f"Mesen {key} does not bind the stored stream")
    terminal = fields.get("Mesen terminal output", "").split()
    if EXPECTED_TITLE_MARKER not in terminal:
        errors.append("Mesen title marker is absent from terminal output")
    if "mapper=163" not in terminal or "sameFrameAssets=true" not in terminal:
        errors.append("Mesen title output lacks mapper/same-frame evidence")
    try:
        screenshots = int(fields.get("Screenshots", "0"))
    except ValueError:
        screenshots = 0
    if screenshots < 2:
        errors.append("Mesen title evidence must contain both title/menu captures")
    if len(chr_ram) != 0x2000:
        errors.append("Mesen title CHR-RAM dump must contain exactly 8 KiB")
    else:
        for tile_id, expected_tile in zip(
            LEGACY_V201_CREDIT_TILE_IDS,
            title_credit_tiles("LUIGA2009, ZLADE, CHPEXO"),
            strict=True,
        ):
            offset = 0x1000 + tile_id * 16
            if chr_ram[offset : offset + 16] != expected_tile:
                errors.append(
                    f"Mesen live credit tile 0x{tile_id:02X} differs"
                )
    nt_offset = ENGLISH_CREDIT_NT_ROW * 32 + ENGLISH_CREDIT_NT_COLUMN
    if nametable[
        nt_offset : nt_offset + len(LEGACY_V201_CREDIT_TILE_IDS)
    ] != bytes(
        LEGACY_V201_CREDIT_TILE_IDS
    ):
        errors.append("Mesen live title nametable does not reference credit tiles")
    return errors


def validate_release(
    *,
    chinese: bytes,
    english_2015: bytes,
    yellow: bytes,
    mesen_title_dir: Path | None = None,
) -> tuple[bytes | None, list[str]]:
    errors: list[str] = []
    for label, payload in (
        ("chinese", chinese),
        ("english_2015", english_2015),
        ("yellow", yellow),
    ):
        actual = sha256(payload)
        if actual != SOURCE_SHA256[label]:
            errors.append(
                f"{label} source SHA-256 {actual} != {SOURCE_SHA256[label]}"
            )
    paths = {
        "ips": RELEASE_DIR / "Pokemon_Jaune_FR_v2.0.1.ips",
        "bps_chinese": RELEASE_DIR / "Pokemon_Jaune_FR_v2.0.1_from_chinese.bps",
        "bps_english": RELEASE_DIR / "Pokemon_Jaune_FR_v2.0.1_from_english_2015.bps",
        "archive_ips": ARCHIVE_DIR / "Pokemon_Jaune_FR_repacked_title.ips",
    }
    try:
        targets = {
            "IPS yellow.nes": _ips(yellow, paths["ips"]),
            "BPS Chinese NJ046": apply_bps(chinese, paths["bps_chinese"].read_bytes()),
            "BPS English 2015": apply_bps(english_2015, paths["bps_english"].read_bytes()),
        }
        archive = _ips(yellow, paths["archive_ips"])
    except (OSError, ValueError) as exc:
        return None, [f"cannot reconstruct release: {exc}"]

    hashes = {label: sha256(payload) for label, payload in targets.items()}
    for label, digest in hashes.items():
        if digest != TARGET_SHA256:
            errors.append(f"{label}: target SHA-256 {digest} != {TARGET_SHA256}")
    if len(set(targets.values())) != 1:
        errors.append("the three patch routes do not produce identical targets")
    if sha256(archive) != ARCHIVE_SHA256:
        errors.append("archived 2.0.0 IPS does not reconstruct its certified ROM")

    expected = bytearray(archive)
    patch_legacy_v201_title_credits(expected)
    target = next(iter(targets.values()))
    if bytes(expected) != target:
        errors.append("2.0.1 differs from 2.0.0 outside the exact title credits")

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        target_path = temporary / "Pokemon_Jaune_FR_v2.0.1.nes"
        base_path = temporary / "Pokemon Yellow English 9-23-2015.nes"
        target_path.write_bytes(target)
        base_path.write_bytes(english_2015)
        mapper_args = mapper_parser().parse_args(
            [
                "--rom", str(target_path),
                "--base-rom", str(base_path),
                "--title-logo", "english",
                "--title-credits-mode", "shared",
            ]
        )
        if validate(mapper_args) != 0:
            errors.append("mapper 163 validation failed for active 2.0.1")

    if mesen_title_dir is not None:
        errors.extend(validate_mesen_title(mesen_title_dir))
    return target, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate all French 2.0.1 patch routes and title evidence."
    )
    parser.add_argument(
        "--chinese-rom",
        type=Path,
        default=ROOT / "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes",
    )
    parser.add_argument(
        "--english-2015-rom",
        type=Path,
        default=ROOT / "Pokemon Yellow English 9-23-2015.nes",
    )
    parser.add_argument("--yellow-rom", type=Path, default=ROOT / "yellow.nes")
    parser.add_argument("--mesen-title-dir", type=Path)
    args = parser.parse_args()
    try:
        chinese = args.chinese_rom.read_bytes()
        english = args.english_2015_rom.read_bytes()
        yellow = args.yellow_rom.read_bytes()
    except OSError as exc:
        print(f"Validation FR 2.0.1: FAIL ({exc})")
        return 1
    target, errors = validate_release(
        chinese=chinese,
        english_2015=english,
        yellow=yellow,
        mesen_title_dir=args.mesen_title_dir,
    )
    if errors:
        print("Validation FR 2.0.1: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Validation FR 2.0.1: PASS")
    print(f"- target SHA-256: {sha256(target or b'')}")
    print("- routes: IPS yellow.nes + BPS Chinese + BPS English 2015")
    print("- delta vs FR 2.0.0: exact shared title credits only")
    print("- mapper 163: PASS")
    if args.mesen_title_dir is not None:
        print("- Mesen title/menu evidence: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
