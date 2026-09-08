"""Compilation française reproductible ; les contrôles statiques ne remplacent pas Mesen."""
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
sys.path.insert(0, str(ROOT))
from tools import rom_builder as core
from tools import title_screen_tools as title
from tools import pointer_manifest as pointers
from tools import validate_french_dynamic_fragments as dynamic
from tools import validate_repacked as repacked
from tools import audit_text_bank_budget as budget
from tools import validate_mapper163 as mapper
from tools.restore_chinese_dojo_deputy import restore
from tools.french_font import encode_game_text, literal_slot_conflicts
from tools.dialogue_layout import format_game_text
from tools.move_label_graphics import load_move_label_csv, french_text_encoder

CATALOGUE = ROOT / "traduction/catalogue.csv"
VERSION = "2.0.13"
DEFAULT_ROMS = {
    "english": ROOT / core.TRANSLATION_BASE_ROM,
    "chinese": ROOT / core.CHINESE_ROM,
}
SOURCE_HASHES = {
    "english": "d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac112509d658a9943b",
    "chinese": "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed",
}
ROM_HASH = "2846fac5738ad24bc65dd1c24622fe4a1e9fffe94062052e84bfbae1cd34fae3"
IPS_HASH = "c05525ad4bbc628f5f97c9005ff85751236be282913ce835d25d350f6dccec0c"
PITCH_START = 0x01B0A9
PITCH_BEFORE = bytes.fromhex(
    "9a2dc66408b26013ca854407cd96633204d9b08965422203e6cbb199826c584432211101"
    "f3e5d8ccc1b6aca29990888079726c66605b56514c4945403d3936330707070606060505"
    "0504040404040404"
)
PITCH_AFTER = bytes.fromhex(
    "f17f13ad4df39d4c00b87434f8bf895626f9cea6805c3a1afbdfc4ab937c67523f2d1c0c"
    "fdefe1d5c9bdb3a99f968e867e77706a645e59544f4b46423f3b38340707070706060505"
    "0505040404030303"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check() -> dict:
    for name, expected_hash in {
        "chinese_glyph_map.csv": "5fa49b098eee1fab8ff854a899c3e3f3cb8111d5686dd2a131f52941acbcc1bd",
        "chinese_records.csv": "89e7f91d2102533a47ac6c58ab5aab1471b13bebb66e20737796863e247f1cca",
    }.items():
        require(sha((ROOT / "data/source" / name).read_bytes()) == expected_hash,
                f"Référence chinoise modifiée : {name}")
    with CATALOGUE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = json.loads((ROOT / "data/validation/catalogue_structure.json").read_text(encoding="utf-8"))
    fields = ("stable_key", "record_type", "offset_hex", "layout", "max_len")
    actual = [{key: row[key] for key in fields} for row in rows]
    require(actual == expected and len(rows) == 1931, "Structure du catalogue modifiée")
    blanks = json.loads((ROOT / "data/validation/blank_records.json").read_text())
    for row in rows:
        text = row["fr_text"]
        require(bool(text.strip()) or row["stable_key"] in blanks, f"Texte vide : {row['stable_key']}")
        require(not literal_slot_conflicts(text), f"Caractère réservé : {row['stable_key']}")
        format_game_text(text, row["layout"])
    core.load_restorations(CATALOGUE)
    variants = core.load_french_pointer_variants(core.DEFAULT_FRENCH_POINTER_VARIANTS)
    labels = load_move_label_csv(core.DEFAULT_MOVE_LABEL_CATALOG, encoder=french_text_encoder)
    ownership = json.loads((ROOT / "data/validation/move_indices.json").read_text())
    require(sorted(spec.move_index for spec in labels) == ownership, "Indices des attaques modifiés")
    errors = dynamic.validate_dynamic_layout_catalogue()
    require(not errors, "\n".join(errors))
    return {"catalogue": len(rows), "restaurations": 85, "attaques_graphiques": len(labels),
            "variantes": sum(len(group) for group in variants.values()), "statut": "PASS"}


def safe_destination(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for parent in (path, *path.parents):
        require(not parent.is_symlink() and not getattr(parent, "is_junction", lambda: False)(),
                "La destination ne doit pas traverser de lien ou jonction")
    path = path.resolve()
    require(path != ROOT and path.is_relative_to(ROOT), "Destination hors du dépôt")
    relative = path.relative_to(ROOT)
    require(relative.parts[0] == "build", "Utiliser un sous-dossier de build/")
    tracked = subprocess.run(["git", "ls-files", "-z", "--", relative.as_posix()],
                             cwd=ROOT, capture_output=True)
    require(tracked.returncode == 0 and not tracked.stdout, "Destination contenant des fichiers suivis")
    require(not path.exists() or (path.is_dir() and not any(path.iterdir())),
            "La destination doit être absente ou vide")
    return path


def apply_pitch(data: bytes) -> bytes:
    end = PITCH_START + len(PITCH_BEFORE)
    require(data[PITCH_START:end] == PITCH_BEFORE, "Table musicale source inattendue")
    return data[:PITCH_START] + PITCH_AFTER + data[end:]


def build_core(english: Path, work: Path) -> bytes:
    work.mkdir()
    args = core.build_parser().parse_args([
        "build-repacked", "--csv", str(CATALOGUE), "--input-rom", str(english),
        "--output-rom", str(work / "core.nes"), "--output-ips", str(work / "core.ips"),
        "--fixed-overflow-output", str(work / "overflow.csv"),
        "--move-label-report", str(work / "move_labels.json"),
    ])
    require(core.command_build_repacked(args) == 0, "Échec du repack")
    validation = repacked.build_parser().parse_args([
        "--csv", str(CATALOGUE), "--input-rom", str(english),
        "--rom", str(work / "core.nes"), "--fixed-overflow", str(work / "overflow.csv"),
    ])
    require(repacked.command_validate(validation) == 0, "Échec de la reconstruction indépendante")
    return (work / "core.nes").read_bytes()


def build(args: argparse.Namespace) -> dict:
    report = {"sources": check(), "version_reference": VERSION, "emulation": "NON_EXECUTEE"}
    inputs = {key: Path(getattr(args, key)).resolve() for key in DEFAULT_ROMS}
    data = {key: path.read_bytes() for key, path in inputs.items()}
    for key, value in data.items():
        require(len(value) == 2097168 and sha(value) == SOURCE_HASHES[key], f"ROM source incorrecte : {key}")
    destination = safe_destination(args.output_dir)
    require(not any(path.is_relative_to(destination) for path in inputs.values()), "Destination contenant une source")
    source_files = [ROOT / "build.py", CATALOGUE, *sorted((ROOT / "tools").glob("*.py")),
                    *sorted((ROOT / "traduction").glob("*.csv")), *sorted((ROOT / "data/validation").glob("*.json")),
                    *sorted((ROOT / "data/source").glob("*.csv"))]
    before = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in source_files}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".fr-build-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        first = build_core(inputs["english"], stage / "first")
        second = build_core(inputs["english"], stage / "second")
        require(first == second, "Compilation non déterministe")
        rom = bytearray(first)
        for patch in (title.patch_jaune_tiles, title.patch_french_menu_tiles,
                      title.patch_french_player_menu_labels, title.patch_french_status_screen_labels,
                      title.patch_french_saving_screen_label, title.patch_title_credits,
                      title.patch_french_bottom_title_label):
            patch(rom)
        rom = restore(bytes(rom), data["chinese"])
        pre_pitch = stage / "mapper.nes"
        pre_pitch.write_bytes(rom)
        mapper_args = mapper.build_parser().parse_args([
            "--rom", str(pre_pitch), "--base-rom", str(inputs["english"]), "--title-logo", "french"])
        require(mapper.validate(mapper_args) == 0, "Contrat mapper 163 invalide")
        final = apply_pitch(rom)
        ips = core.make_ips(data["chinese"], final)
        output = stage / "output"
        output.mkdir()
        rom_path = output / "Pokemon_Jaune_NJ046_FR.nes"
        ips_path = output / "Pokemon_Jaune_NJ046_FR.ips"
        rom_path.write_bytes(final)
        ips_path.write_bytes(ips)
        records, truncate = core.parse_ips(ips_path)
        require(core.apply_ips(data["chinese"], records, truncate) == final, "Aller-retour IPS incorrect")
        manifest = pointers.build_manifest(rom_path=rom_path, csv_path=CATALOGUE, input_rom_path=inputs["english"])
        commitment = pointers.canonical_inventory_commitment(manifest["records"])
        expected = json.loads((ROOT / "data/validation/pointer_commitment.json").read_text())
        require(commitment == expected, "Inventaire des 1 916 pointeurs modifié")
        errors = pointers.validate_manifest(rom_path=rom_path, manifest=manifest)
        errors += dynamic.validate_dynamic_fragments(final)
        bank_args = budget.build_parser().parse_args([
            "--csv", str(CATALOGUE), "--input-rom", str(inputs["english"]),
            "--floor", "6:40:4", "--floor", "7:128:128"])
        bank_report, bank_errors = budget.build_report(bank_args)
        errors += bank_errors
        require(not errors, "\n".join(errors))
        if args.verify_release:
            require(sha(final) == ROM_HASH and sha(ips) == IPS_HASH, "Différence avec la release 2.0.13")
            published = ROOT / "releases/fr/2.0.13/Pokemon_Jaune_NJ046_FR_v2.0.13.ips"
            require(ips == published.read_bytes(), "IPS publié différent")
        require(before == {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in source_files},
                "Une source a changé pendant la compilation")
        require(all(path.read_bytes() == data[key] for key, path in inputs.items()), "Une ROM source a changé")
        report.update({"rom_sha256": sha(final), "ips_sha256": sha(ips), "pointeurs": commitment,
                       "banques": bank_report, "sources_sha256": before,
                       "roms_sources_sha256": SOURCE_HASHES, "base_ips": "chinese",
                       "base_ips_sha256": SOURCE_HASHES["chinese"], "determinisme": "PASS",
                       "mapper163_avant_correction_musicale": "PASS", "correction_musicale": "PASS",
                       "ips": "PASS", "limites_dynamiques": "PASS", "release_exacte": args.verify_release})
        (output / "pointer_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Ne jamais remplacer une destination devenue non vide pendant les contrôles.
        safe_destination(destination)
        if destination.exists():
            destination.rmdir()
        output.rename(destination)
    print(f"Compilation validée : {destination}")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Contrôles du catalogue sans ROM")
    command = commands.add_parser("build", help="Compiler et contrôler les ROM et IPS")
    command.add_argument("--output-dir", type=Path, default=ROOT / "build/fr")
    command.add_argument("--verify-release", action="store_true", help="Exiger les octets exacts de la 2.0.13")
    for name, path in DEFAULT_ROMS.items():
        command.add_argument(f"--{name}", type=Path, default=path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            print(json.dumps(check(), ensure_ascii=False, indent=2))
        else:
            build(args)
        return 0
    except (ValueError, OSError) as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
