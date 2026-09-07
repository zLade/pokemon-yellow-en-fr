#!/usr/bin/env python3
"""Local English builder. Static/byte checks are not emulator validation.

Run ``python build.py check`` without ROMs, or ``python build.py build``.
Only --verify-release pins the output to the published 2.0.3 bytes.
Outputs must be in an ignored directory inside this checkout; existing
nonempty directories are never replaced. No release files are modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_english_catalog as catalog
from tools.move_label_graphics import load_move_label_csv

VERSION = "2.0.3"
ROM_FILENAME = "Pokemon_Yellow_NJ046_EN.nes"
IPS_FILENAME = "Pokemon_Yellow_NJ046_EN.ips"
REPORT_FILENAME = "build_report.json"
CORE_SCRIPT = ROOT / "tools" / "rom_builder.py"
LOCALE = ROOT / "translation"
VALIDATION = ROOT / "data" / "validation"
DATA_INPUTS = {
    "catalogue": LOCALE / "catalog.csv",
    "adjudications": VALIDATION / "source_adjudications.csv",
    "variants": LOCALE / "pointer_variants.csv",
    "overlaps": VALIDATION / "storage_overlaps.csv",
    "cameos": VALIDATION / "creator_cameo_dialogues.csv",
    "move_labels": LOCALE / "move_labels_two_line.csv",
    "neutral": VALIDATION / "neutral_glyph_records.csv",
    "budget_policy": VALIDATION / "bank_budget_policy.json",
    "inventory": VALIDATION / "structural_pointer_inventory.json",
}
DEFAULT_ROMS = {
    "english_2015": ROOT / "Pokemon Yellow English 9-23-2015.nes",
    "chinese": ROOT / "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes",
}
EXPECTED_ROM_SHA256 = {
    "english_2015": "d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac112509d658a9943b",
    "chinese": "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed",
}
RELEASE_ROM_SHA256 = "703662c3739884513bf6493b748743eff0933b2479dc21644433699891f9d0f3"
RELEASE_IPS_SHA256 = "6f42637770fd4fc4971ef90d156d6f5959bb88e546122e2747b6b34c8cd168da"
ROM_SIZE = 2097168

# Retained local build/validator closure, independent of the caller's imports.
# Keep this explicit list synchronized when moving or adding engine modules.
# French-named codec/layout modules remain implementation dependencies, not
# French translation inputs or French release-validation requirements.
SOURCE_FILES = (
    "build.py",
    "tools/build_english_release.py",
    "tools/dialogue_layout.py",
    "tools/english_pointer_manifest.py",
    "tools/french_font.py",
    "tools/locales/__init__.py",
    "tools/locales/english_codec.py",
    "tools/locales/english_layout.py",
    "tools/locales/profiles.py",
    "tools/move_label_graphics.py",
    "tools/restoration_topology.py",
    "tools/restore_chinese_dojo_deputy.py",
    "tools/rom_builder.py",
    "tools/title_screen_tools.py",
    "tools/validate_english_bank_budget.py",
    "tools/validate_english_catalog.py",
    "tools/validate_english_glyph_residue.py",
    "tools/validate_english_repacked.py",
    "tools/validate_mapper163.py",
)
# Pin graphical ownership, not the editable names or display-line wording.
EXPECTED_MOVE_INDICES = frozenset({
    1, 2, 3, 4, 5, 7, 9, 10, 11, 12, 13, 15, 16, 19, 20, 22, 23, 24, 25,
    27, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 40, 41, 43, 44, 47, 51,
    52, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65, 66, 67, 70, 71, 73, 74,
    75, 77, 78, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 93, 94, 95,
    97, 99, 100, 103, 104, 105, 107, 108, 112, 116, 117, 118, 119, 121,
    122, 123, 125, 126, 130, 131, 132, 133, 134, 136, 138, 140, 145,
    146, 147, 148, 149, 150, 151, 152, 154, 157, 158, 159, 162, 164,
    166, 168, 172, 173,
})

# Source representation of the published 2.0.1 -> 2.0.3 pitch correction.
# Offsets include the 16-byte iNES header. 80 bytes, 69 actual changes.
# Recovered and byte-verified against both tracked release IPS targets.
PITCH_START = 0x01B0A9
PITCH_BEFORE = bytes.fromhex(
    "9a2dc66408b26013ca854407cd96633204d9"
    "b08965422203e6cbb199826c584432211101"
    "f3e5d8ccc1b6aca29990888079726c66605b"
    "56514c4945403d3936330707070606060505"
    "0504040404040404"
)
PITCH_AFTER = bytes.fromhex(
    "f17f13ad4df39d4c00b87434f8bf895626f9"
    "cea6805c3a1afbdfc4ab937c67523f2d1c0c"
    "fdefe1d5c9bdb3a99f968e867e77706a645e"
    "59544f4b46423f3b38340707070706060505"
    "0505040404030303"
)


class BuildError(RuntimeError):
    """An input, byte check, or destination is unsafe."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def apply_pitch(candidate: bytes) -> bytes:
    end = PITCH_START + len(PITCH_BEFORE)
    if candidate[PITCH_START:end] != PITCH_BEFORE:
        raise BuildError("Pitch source bytes mismatch (already patched or unexpected ROM)")
    result = bytearray(candidate)
    result[PITCH_START:end] = PITCH_AFTER
    return bytes(result)


def read_source_rom(path: Path, label: str) -> bytes:
    data = path.read_bytes()
    if len(data) != ROM_SIZE or sha256(data) != EXPECTED_ROM_SHA256[label]:
        raise BuildError(f"{label}: unexpected source ROM size/SHA-256: {path}")
    return data


def verify_release(rom: bytes, ips: bytes) -> None:
    if sha256(rom) != RELEASE_ROM_SHA256 or sha256(ips) != RELEASE_IPS_SHA256:
        raise BuildError("Output differs from published 2.0.3; omit --verify-release for edited sources")


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=False)


def safe_destination(path: Path, inputs: list[Path]) -> Path:
    # Check lexical ancestry before resolving, so junctions cannot hide escapes.
    path = Path(os.path.abspath(path))
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or getattr(ancestor, "is_junction", lambda: False)():
            raise BuildError(f"Output path contains a link/junction: {ancestor}")
    destination = path.resolve()
    if destination == ROOT or not destination.is_relative_to(ROOT):
        raise BuildError("Output directory must be inside this checkout")
    relative = destination.relative_to(ROOT)
    if any(part in {".git", ".agents", ".codex"} for part in relative.parts):
        raise BuildError("Output directory is repository metadata")
    if any(p.resolve() == destination or p.resolve().is_relative_to(destination) for p in inputs):
        raise BuildError("Output directory contains a source input")
    tracked = run_git("ls-files", "-z", "--", relative.as_posix())
    if tracked.returncode or tracked.stdout:
        raise BuildError("Output directory contains tracked files or Git could not verify safety")
    # Require the directory itself to be ignored, not just its .nes children.
    ignored = run_git("check-ignore", "-q", "--", relative.as_posix() + "/")
    if ignored.returncode:
        raise BuildError("Output directory must be ignored by Git (for example build/en)")
    stage_probe = relative.parent / ".en-build-safety-probe"
    if run_git("check-ignore", "-q", "--", stage_probe.as_posix() + "/").returncode:
        raise BuildError("Output parent must also ignore temporary build directories (use build/en)")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise BuildError(f"Refusing nonempty/existing-file destination: {destination}")
    return destination


def input_records(paths: list[Path]) -> dict[str, dict[str, object]]:
    records = {}
    for path in sorted({p.resolve() for p in paths}):
        name = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
        data = path.read_bytes()
        records[name] = {"size": len(data), "sha256": sha256(data)}
    return records


def source_paths() -> list[Path]:
    return [ROOT / name for name in SOURCE_FILES]


def check_move_labels(path: Path) -> dict[str, object]:
    specs = load_move_label_csv(path)
    indices = {spec.move_index for spec in specs}
    if len(specs) != 114 or indices != EXPECTED_MOVE_INDICES:
        raise BuildError(
            "Graphical move ownership must contain the 114 known indices; "
            f"missing={sorted(EXPECTED_MOVE_INDICES - indices)}, "
            f"unexpected={sorted(indices - EXPECTED_MOVE_INDICES)}"
        )
    return {"result": "PASS", "records": len(specs)}


def check() -> dict[str, object]:
    """Validate all three editable tables without reading a ROM."""
    report = catalog.validate_all(
        DATA_INPUTS["catalogue"], DATA_INPUTS["adjudications"],
        DATA_INPUTS["variants"], DATA_INPUTS["overlaps"], DATA_INPUTS["cameos"],
    )
    report["move_labels"] = check_move_labels(DATA_INPUTS["move_labels"])
    return report


def core_command(english_rom: Path, work: Path) -> list[str]:
    return [
        sys.executable, "-B", str(CORE_SCRIPT), "build-repacked", "--profile", "en-US",
        "--input-rom", str(english_rom),
        "--csv", str(DATA_INPUTS["catalogue"]),
        "--restorations-csv", str(DATA_INPUTS["catalogue"]),
        "--pointer-variants-csv", str(DATA_INPUTS["variants"]),
        "--move-labels-csv", str(DATA_INPUTS["move_labels"]),
        "--output-rom", str(work / "text.nes"),
        "--output-ips", str(work / "text.ips"),
        "--fixed-overflow-output", str(work / "overflow.csv"),
        "--move-label-report", str(work / "move_labels.json"),
        "--allocation-output", str(work / "allocation.csv"),
        "--bank-budget-output", str(work / "bank_budget.csv"),
    ]


def build_core(english_rom: Path, work: Path) -> bytes:
    from tools import validate_english_repacked as repacked

    work.mkdir()
    process = subprocess.run(core_command(english_rom, work), cwd=ROOT,
                             capture_output=True, text=True, check=False)
    if process.returncode:
        raise BuildError("Core build failed:\n" + process.stdout + process.stderr)
    repacked.validate_overflow_report(work / "overflow.csv")
    return (work / "text.nes").read_bytes()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, report: object) -> None:
    path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def build(args: argparse.Namespace) -> dict[str, object]:
    # The ROM-free check command does not import the ROM engine or build validators.
    from tools import rom_builder as core
    from tools import english_pointer_manifest as pointers
    from tools import validate_english_bank_budget as budget
    from tools import validate_english_glyph_residue as glyphs
    from tools import validate_english_repacked as repacked
    from tools.restore_chinese_dojo_deputy import restore
    from tools.title_screen_tools import patch_english_yellow_title

    rom_paths = {"english_2015": args.english_2015_rom.resolve(),
                 "chinese": args.chinese_rom.resolve()}
    inputs = [*rom_paths.values(), *DATA_INPUTS.values(), *source_paths()]
    destination = safe_destination(args.output_dir, inputs)
    before = input_records(inputs)
    roms = {label: read_source_rom(path, label) for label, path in rom_paths.items()}
    static = check()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A sibling staging directory keeps publication on the same filesystem.
    with tempfile.TemporaryDirectory(prefix=".en-build-", dir=destination.parent) as temporary:
        work = Path(temporary)
        first = work / "first"
        raw = build_core(rom_paths["english_2015"], first)
        repeated = build_core(rom_paths["english_2015"], work / "second")
        if raw != repeated:
            raise BuildError("Independent core builds differ")
        if len(raw) != ROM_SIZE or raw[:16] != roms["english_2015"][:16]:
            raise BuildError("Core ROM size/header contract changed")
        header = repacked.parse_header(raw)
        if header["mapper"] != 163 or header["chr_size"] != 0 or not header["battery"]:
            raise BuildError("Mapper-163/CHR-RAM/battery contract mismatch")
        repacked.validate_battle_text_control(roms["english_2015"], raw)
        repacked.validate_restored_pointers(raw)
        font = slice(repacked.ASCII_FONT_OFFSET, repacked.ASCII_FONT_OFFSET + repacked.ASCII_FONT_SIZE)
        if raw[font] != roms["english_2015"][font]:
            raise BuildError("English font changed")
        move_check = repacked.certify_move_label_graphics(
            base=roms["english_2015"], candidate=raw, profile="en-US",
            catalogue=DATA_INPUTS["move_labels"],
        )
        repacked.validate_move_label_report(first / "move_labels.json", move_check)
        budget_check = budget.validate_budget(first / "allocation.csv", first / "bank_budget.csv",
                                              DATA_INPUTS["budget_policy"])
        title = bytearray(raw)
        patch_english_yellow_title(title, roms["english_2015"], "LUIGA2009, ZLADE, CHPEXO")
        dojo = restore(bytes(title), roms["chinese"])
        final = apply_pitch(dojo)
        ips = core.make_ips(roms["chinese"], final)
        if args.verify_release:
            verify_release(final, ips)
        staged = work / "publish"
        staged.mkdir()
        target = staged / ROM_FILENAME
        target.write_bytes(final)
        patch_path = staged / IPS_FILENAME
        patch_path.write_bytes(ips)
        records, truncate = core.parse_ips(patch_path)
        if core.apply_ips(roms["chinese"], records, truncate) != final:
            raise BuildError("IPS round-trip mismatch")
        glyph_check = glyphs.validate_glyph_residue(
            candidate=final, base=roms["english_2015"],
            catalogue_rows=read_rows(DATA_INPUTS["catalogue"]),
            neutral_rows=read_rows(DATA_INPUTS["neutral"]),
        )
        manifest = pointers.build_manifest(
            rom_path=target, catalogue_path=DATA_INPUTS["catalogue"],
            variants_path=DATA_INPUTS["variants"], inventory_path=DATA_INPUTS["inventory"],
            move_labels_path=DATA_INPUTS["move_labels"],
        )
        after = input_records(inputs)
        if after != before:
            changed = ", ".join(name for name in before if before[name] != after.get(name))
            raise BuildError(f"Source inputs changed during build; nothing published: {changed}")
        report = {
            "schema": "nj046-en-local-build/v1", "result": "PASS",
            "runtime_validation": "NOT RUN", "hardware_validation": "NOT RUN",
            "release_verification": "PASS" if args.verify_release else "NOT REQUESTED",
            "release_reference": VERSION, "ips_base": "chinese",
            "ips_base_sha256": EXPECTED_ROM_SHA256["chinese"], "inputs": before, "source_inputs_unchanged": True,
            "stages": {"core_sha256": sha256(raw), "title_sha256": sha256(bytes(title)),
                       "dojo_sha256": sha256(dojo), "pitch_changed_bytes": 69},
            "checks": {"source_rom_hashes": "PASS", "catalogue": static, "core_exact_rebuild": "PASS",
                       "mapper_header_preserved": "PASS", "english_font_preserved": "PASS",
                       "battle_control": "PASS", "restored_pointers": "PASS",
                       "move_labels": move_check.requested_count,
                       "bank_budget": budget_check, "glyphs": glyph_check,
                       "pointers": manifest["summary"], "ips_roundtrip": "PASS"},
            "outputs": {ROM_FILENAME: {"size": len(final), "sha256": sha256(final)},
                        IPS_FILENAME: {"size": len(ips), "sha256": sha256(ips)}},
        }
        write_json(staged / REPORT_FILENAME, report)
        write_json(staged / "pointer_manifest.json", manifest)
        # Recheck after building, never replace a destination populated meanwhile.
        safe_destination(destination, inputs)
        if destination.exists():
            destination.rmdir()  # Only an empty, rechecked directory.
        staged.rename(destination)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="ROM-free catalogue, variant and graphical-label validation")
    command = commands.add_parser("build", help="Build into a new/empty ignored directory")
    command.add_argument("--verify-release", action="store_true",
                         help="Require exact published 2.0.3 ROM and IPS hashes")
    command.add_argument("--output-dir", type=Path, default=ROOT / "build" / "en")
    command.add_argument("--english-2015-rom", type=Path, default=DEFAULT_ROMS["english_2015"])
    command.add_argument("--chinese-rom", type=Path, default=DEFAULT_ROMS["chinese"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            print(json.dumps(check(), indent=2, ensure_ascii=False))
        else:
            report = build(args)
            print(f"English build: PASS -> {args.output_dir.resolve()}")
            print(f"ROM SHA-256: {report['outputs'][ROM_FILENAME]['sha256']}")
            print(f"Release verification: {report['release_verification']}")
            print("Runtime/hardware validation: NOT RUN")
    except (OSError, ValueError, RuntimeError, csv.Error) as exc:
        print(f"English {args.command}: FAIL\n{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
