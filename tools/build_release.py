#!/usr/bin/env python3
"""Build and validate a reproducible Pokemon Yellow NES French release.

The release directory is published with one directory rename only after every
build, comparison and validator has succeeded.  All intermediate ROMs live in
the temporary staging directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent

DEFAULT_CHINESE_ROM = ROOT / (
    "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"
)
DEFAULT_ENGLISH_IPS = ROOT / "Pokemon Yellow English 9-23-2015.ips"
DEFAULT_CANONICAL_ENGLISH_ROM = ROOT / "yellow.nes"
DEFAULT_TRANSLATION_BASE_ROM = (
    ROOT / "Pokemon Yellow English 9-23-2015.nes"
)
DEFAULT_SCRIPT = ROOT / "script.py"
DEFAULT_CANONICAL_CSV = ROOT / "traduction_base.csv"
DEFAULT_CANONICAL_OVERFLOW_CSV = ROOT / "traductions_trop_longues.csv"

EXPECTED_INPUT_SHA256 = {
    "chinese_rom": (
        "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e6"
        "5271e2f7b40c65ed"
    ),
    "english_ips": (
        "15371a2f8b36b1e412e4e08b49097f1061959f9922eba45b"
        "193c812abf42e887"
    ),
    "canonical_english_rom": (
        "69520103102677b33b47c15fae804dc1a742347a9ee1b02a"
        "9195e795eb6e431b"
    ),
    "translation_base_rom": (
        "d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac"
        "112509d658a9943b"
    ),
    "script": (
        "e870f48105bd570d8323bf0c9358b95dbe5e59e655721419"
        "6a547cfedcb56180"
    ),
    "canonical_csv": (
        "a4932263753587b744cf3cc614f884c8754e95fec5b486f88"
        "c951adf242be803"
    ),
    "canonical_overflow_csv": (
        "561ff1e58bc91b7671fc0c9d5d54140a175918d2a6d1a288"
        "d31d5b116c37c748"
    ),
    "core_dialogue_boundary_inventory": (
        "c90e128d67fea797c575a04ef305c0e42bd29a8a5f044cd0"
        "a4b4ec8e6762caf6"
    ),
    "restoration_naturalization_overrides": (
        "5cbb41c914bf015d857eaf87835398ac42e32d5705ebf72c6"
        "553b1d8900f26b3"
    ),
    "main_naturalization_overrides": (
        "923a9d3b39f834b83a1d59e5f0c9c7cd9e0a3d7d5389b448"
        "b6e52407147fce56"
    ),
    "chinese_fidelity_overrides": (
        "0761b3f173d96ff6ddbdf54a2829d9cddbabc7720af41d014"
        "5d300154b3ec9ed"
    ),
    "external_patcher_proof": (
        "3f53aace4f07fbed273baa6ecf20ee5e4ee731dffbf187d5d"
        "2e9e5b6dedcb338"
    ),
}

TEXT_BANK_BUDGET_POLICY = {
    "floors": {
        "6": {"free_bytes": 40, "largest_block": 4},
        "7": {"free_bytes": 128, "largest_block": 128},
    },
    "pair6_capacity_proof": {
        "arena_capacity_bytes": 29171,
        "suffix_pool_root_bytes": 29120,
        "theoretical_free_bytes": 51,
        "seven_byte_spans": 85,
        "seven_byte_roots": 45,
        "minimum_root_bytes": 4,
        "minimum_stranded_bytes": 40,
        "maximum_possible_largest_block": 11,
        "rationale": (
            "At least 40 of the 85 seven-byte spans retain one byte "
            "that is unusable after placing the 45 seven-byte roots. The 51 "
            "theoretically free bytes therefore allow a block of at most 11 "
            "bytes; the current layout reaches exactly that bound."
        ),
    },
}

BUILD_FILENAMES = (
    "Pokemon_Jaune_FR_repacked.nes",
    "Pokemon_Jaune_FR_repacked.ips",
    "Pokemon_Jaune_FR_repacked_title.nes",
    "Pokemon_Jaune_FR_repacked_title.ips",
    "Pokemon_Jaune_FR_repacked_title_from_chinese.bps",
    "Pokemon_Jaune_FR_repacked_title_from_english.bps",
    "textes_fixes_trop_longs.csv",
)

CURRENT_ARTIFACTS = {
    "Pokemon_Jaune_FR_repacked.nes": "Pokemon_Jaune_FR_repacked.nes",
    "Pokemon_Jaune_FR_repacked.ips": "Pokemon_Jaune_FR_repacked.ips",
    "Pokemon_Jaune_FR_repacked_title.nes": (
        "Pokemon_Jaune_FR_repacked_title.nes"
    ),
    "Pokemon_Jaune_FR_repacked_title.ips": (
        "Pokemon_Jaune_FR_repacked_title.ips"
    ),
    "textes_fixes_trop_longs.csv": "textes_fixes_trop_longs.csv",
}

TRACEABLE_TOOL_SUFFIXES = frozenset(
    {".csv", ".json", ".lua", ".md", ".mjs", ".ps1", ".py"}
)


class ReleaseError(RuntimeError):
    """A release gate failed before publication."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, display_path: str | None = None) -> FileRecord:
    return FileRecord(
        path=display_path or str(path),
        size=path.stat().st_size,
        sha256=sha256_file(path),
    )


def as_manifest_record(record: FileRecord) -> dict[str, object]:
    return {
        "path": record.path,
        "size": record.size,
        "sha256": record.sha256,
    }


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ReleaseError(f"{label} missing: {resolved}")
    return resolved


def assert_same_file(left: Path, right: Path, label: str) -> str:
    left_hash = sha256_file(left)
    right_hash = sha256_file(right)
    if left_hash != right_hash or left.read_bytes() != right.read_bytes():
        raise ReleaseError(
            f"{label} is not reproducible: {left} ({left_hash}) != "
            f"{right} ({right_hash})"
        )
    return left_hash


class ReleaseBuilder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.python = str(Path(args.python).expanduser())
        self.output_dir = Path(args.output_dir).expanduser().resolve()
        self.output_parent = self.output_dir.parent
        self.output_parent.mkdir(parents=True, exist_ok=True)
        if self.output_dir.exists():
            raise ReleaseError(
                "the release directory already exists; choose a new "
                f"destination: {self.output_dir}"
            )

        self.staging = Path(
            tempfile.mkdtemp(
                prefix=f".{self.output_dir.name}.staging-",
                dir=self.output_parent,
            )
        )
        self.work = self.staging / ".work"
        self.logs = self.staging / "logs"
        self.audits = self.staging / "audits"
        self.generated = self.work / "generated"
        self.helper_root = self.work / "helper"
        self.run_dirs = [self.work / "run-1", self.work / "run-2"]
        for directory in (
            self.work,
            self.logs,
            self.audits,
            self.generated,
            self.helper_root,
            *self.run_dirs,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.steps: list[dict[str, object]] = []
        self.input_paths: dict[str, Path] = {}
        self.initial_hashes: dict[str, str] = {}
        self.helper = self.helper_root / "rom_traduction_assistant.py"

    def normalize_argument(self, value: str) -> str:
        replacements = (
            (str(self.staging), "$STAGING"),
            (str(ROOT), "$ROOT"),
        )
        normalized = value
        for prefix, replacement in replacements:
            if normalized == prefix:
                return replacement
            if normalized.startswith(prefix + os.sep):
                return replacement + normalized[len(prefix):]
        return normalized

    def run_step(
        self,
        name: str,
        arguments: Sequence[str | Path],
        *,
        environment: dict[str, str] | None = None,
    ) -> None:
        number = len(self.steps) + 1
        log_path = self.logs / f"{number:02d}-{name}.log"
        command = [self.python, *(str(item) for item in arguments)]
        display_command = [self.normalize_argument(item) for item in command]
        started = time.monotonic()
        process_environment = os.environ.copy()
        existing_python_path = process_environment.get("PYTHONPATH")
        process_environment["PYTHONPATH"] = os.pathsep.join(
            part
            for part in (str(ROOT), existing_python_path)
            if part
        )
        if environment:
            process_environment.update(environment)
        process = subprocess.run(
            command,
            cwd=ROOT,
            env=process_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        duration = round(time.monotonic() - started, 3)
        log_path.write_text(process.stdout, encoding="utf-8")
        self.steps.append(
            {
                "name": name,
                "command": display_command,
                "returncode": process.returncode,
                "seconds": duration,
                "log": str(log_path.relative_to(self.staging)),
            }
        )
        if process.returncode != 0:
            tail = "\n".join(process.stdout.splitlines()[-12:])
            raise ReleaseError(
                f"step {name} failed (code {process.returncode}); "
                f"log: {log_path}\n{tail}"
            )

    def prepare_inputs(self) -> None:
        requested = {
            "chinese_rom": self.args.chinese_rom,
            "english_ips": self.args.english_ips,
            "canonical_english_rom": self.args.canonical_english_rom,
            "translation_base_rom": self.args.translation_base_rom,
            "script": self.args.script,
            "canonical_csv": self.args.canonical_csv,
            "canonical_overflow_csv": self.args.canonical_overflow_csv,
            "rom_traduction_assistant": ROOT / "rom_traduction_assistant.py",
            "title_screen_tools": TOOLS_DIR / "title_screen_tools.py",
            "bps_patch": TOOLS_DIR / "bps_patch.py",
            "pointer_manifest": TOOLS_DIR / "pointer_manifest.py",
            "audit_text_bank_budget": (
                TOOLS_DIR / "audit_text_bank_budget.py"
            ),
            "validate_repacked": TOOLS_DIR / "validate_repacked.py",
            "validate_mapper163": TOOLS_DIR / "validate_mapper163.py",
            "validate_dialogue_layout": (
                TOOLS_DIR / "validate_dialogue_layout.py"
            ),
            "dialogue_page_quality": (
                TOOLS_DIR / "dialogue_page_quality.py"
            ),
            "validate_pokedex_layout": (
                TOOLS_DIR / "validate_pokedex_layout.py"
            ),
            "validate_final_pokedex_runtime": (
                TOOLS_DIR / "validate_final_pokedex_runtime.py"
            ),
            "audit_french_accents": TOOLS_DIR / "audit_french_accents.py",
            "audit_quality_ambitious": (
                TOOLS_DIR / "audit_quality_ambitious.py"
            ),
            "audit_translation_coverage": (
                TOOLS_DIR / "audit_translation_coverage.py"
            ),
            "core_french_font": TOOLS_DIR / "french_font.py",
            "core_dialogue_layout": TOOLS_DIR / "dialogue_layout.py",
            "core_dialogue_inventory": TOOLS_DIR / "dialogue_inventory.py",
            "core_dialogue_boundary_inventory": (
                TOOLS_DIR / "data" / "dialogue_boundary_inventory.json"
            ),
            "core_chinese_dialogue_restorations": (
                TOOLS_DIR / "chinese_dialogue_restorations.py"
            ),
            "restoration_naturalization_overrides": (
                TOOLS_DIR
                / "data"
                / "french_restoration_naturalization_overrides.json"
            ),
            "main_naturalization_overrides": (
                TOOLS_DIR / "data" / "french_naturalization_overrides.json"
            ),
            "chinese_fidelity_overrides": (
                TOOLS_DIR / "data" / "chinese_fidelity_dialogue_overrides.json"
            ),
            "external_patcher_proof": (
                ROOT / "build" / "external-patcher-proof.json"
            ),
        }
        # The release executes the whole Python suite, whose tests also read
        # Lua, PowerShell, JSON, CSV and JavaScript fixtures.  Recording every
        # such tool source makes the archived test corpus reproducible instead
        # of reporting only a module count with no binding to its contents.
        for source_path in sorted(TOOLS_DIR.rglob("*")):
            if (
                not source_path.is_file()
                or source_path.suffix.lower() not in TRACEABLE_TOOL_SUFFIXES
            ):
                continue
            relative = source_path.relative_to(ROOT).as_posix()
            label = f"tool_source:{relative}"
            requested.setdefault(label, source_path)
        # The completion tests also exercise the project-level Markdown
        # reports.  Bind those exact inputs as well, otherwise a release could
        # report a green documentation test without identifying the documents
        # that were actually checked.
        for documentation_path in sorted(ROOT.glob("*.md")):
            label = f"project_documentation:{documentation_path.name}"
            requested.setdefault(label, documentation_path)
        for label, requested_path in requested.items():
            self.input_paths[label] = require_file(
                Path(requested_path), label
            )

        for label, expected in EXPECTED_INPUT_SHA256.items():
            actual = sha256_file(self.input_paths[label])
            if actual != expected:
                raise ReleaseError(
                    f"Unexpected {label} SHA-256: {actual}; expected {expected}"
                )

        self.initial_hashes = {
            label: sha256_file(path)
            for label, path in self.input_paths.items()
        }
        shutil.copy2(
            self.input_paths["rom_traduction_assistant"], self.helper
        )

    def generate_and_compare_csv(self) -> tuple[Path, Path]:
        generated_csv = self.generated / "traduction_base.csv"
        generated_overflow = self.generated / "traductions_trop_longues.csv"
        self.run_step(
            "dump-script",
            (
                self.helper,
                "dump-script",
                "--script",
                self.input_paths["script"],
                "--english-rom",
                self.input_paths["translation_base_rom"],
                "--output",
                generated_csv,
                "--overflow-output",
                generated_overflow,
            ),
        )
        assert_same_file(
            generated_csv,
            self.input_paths["canonical_csv"],
            "Canonical CSV generated from script.py",
        )
        assert_same_file(
            generated_overflow,
            self.input_paths["canonical_overflow_csv"],
            "Canonical overflow CSV",
        )
        return generated_csv, generated_overflow

    def run_provenance(self) -> None:
        self.run_step(
            "provenance-english-ips",
            (
                self.helper,
                "check",
                "--chinese-rom",
                self.input_paths["chinese_rom"],
                "--english-ips",
                self.input_paths["english_ips"],
                "--english-rom",
                self.input_paths["canonical_english_rom"],
            ),
        )

    def run_budget_preflight(self) -> None:
        self.run_step(
            "audit-text-bank-budget",
            (
                self.input_paths["audit_text_bank_budget"],
                "--csv",
                self.input_paths["canonical_csv"],
                "--input-rom",
                self.input_paths["translation_base_rom"],
                "--floor",
                "6:40:4",
                "--floor",
                "7:128:128",
                "--output",
                self.audits / "text_bank_budget.json",
            ),
        )
        report_path = self.audits / "text_bank_budget.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "PASS":
            raise ReleaseError("Inconsistent budget audit: status is not PASS")
        report["release_policy"] = TEXT_BANK_BUDGET_POLICY
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def build_once(self, run_directory: Path, csv_path: Path) -> None:
        text_rom = run_directory / "Pokemon_Jaune_FR_repacked.nes"
        text_ips = run_directory / "Pokemon_Jaune_FR_repacked.ips"
        final_rom = run_directory / "Pokemon_Jaune_FR_repacked_title.nes"
        final_ips = run_directory / "Pokemon_Jaune_FR_repacked_title.ips"
        chinese_bps = (
            run_directory
            / "Pokemon_Jaune_FR_repacked_title_from_chinese.bps"
        )
        english_bps = (
            run_directory
            / "Pokemon_Jaune_FR_repacked_title_from_english.bps"
        )
        fixed_overflow = run_directory / "textes_fixes_trop_longs.csv"
        graphics = run_directory / "graphics"
        run_label = run_directory.name

        self.run_step(
            f"build-repacked-{run_label}",
            (
                self.helper,
                "build-repacked",
                "--csv",
                csv_path,
                "--input-rom",
                self.input_paths["translation_base_rom"],
                "--output-rom",
                text_rom,
                "--output-ips",
                text_ips,
                "--fixed-overflow-output",
                fixed_overflow,
            ),
        )
        self.run_step(
            f"patch-french-graphics-{run_label}",
            (
                self.input_paths["title_screen_tools"],
                "patch-french-graphics",
                "--rom",
                text_rom,
                "--base-rom",
                self.input_paths["canonical_english_rom"],
                "--title-logo",
                "english",
                "--english-title-rom",
                self.input_paths["translation_base_rom"],
                "--out-rom",
                final_rom,
                "--out-ips",
                final_ips,
                "--out",
                graphics,
            ),
        )
        self.run_step(
            f"create-chinese-bps-{run_label}",
            (
                self.input_paths["bps_patch"],
                "create",
                "--source",
                self.input_paths["chinese_rom"],
                "--target",
                final_rom,
                "--patch",
                chinese_bps,
                "--metadata",
                "Pokemon Yellow NES FR; source=NJ046 Chinese",
            ),
        )
        self.run_step(
            f"create-english-bps-{run_label}",
            (
                self.input_paths["bps_patch"],
                "create",
                "--source",
                self.input_paths["translation_base_rom"],
                "--target",
                final_rom,
                "--patch",
                english_bps,
                "--metadata",
                "Pokemon Yellow NES FR; source=English 2015",
            ),
        )
        for filename in BUILD_FILENAMES:
            require_file(run_directory / filename, filename)

    def compare_builds(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for filename in BUILD_FILENAMES:
            hashes[filename] = assert_same_file(
                self.run_dirs[0] / filename,
                self.run_dirs[1] / filename,
                f"double build {filename}",
            )
        return hashes

    def compare_current_artifacts(self) -> dict[str, str]:
        comparisons: dict[str, str] = {}
        if not self.args.expect_current_artifacts:
            return comparisons
        artifact_root = Path(
            self.args.current_artifacts_dir
        ).expanduser().resolve()
        for produced_name, current_name in CURRENT_ARTIFACTS.items():
            current = require_file(
                artifact_root / current_name,
                f"current artifact {current_name}",
            )
            comparisons[produced_name] = assert_same_file(
                self.run_dirs[0] / produced_name,
                current,
                f"reproduction of {current_name}",
            )
        return comparisons

    def run_validators(self, csv_path: Path) -> None:
        final_rom = self.run_dirs[0] / "Pokemon_Jaune_FR_repacked_title.nes"
        final_ips = self.run_dirs[0] / "Pokemon_Jaune_FR_repacked_title.ips"
        fixed = self.run_dirs[0] / "textes_fixes_trop_longs.csv"
        chinese_bps = (
            self.run_dirs[0]
            / "Pokemon_Jaune_FR_repacked_title_from_chinese.bps"
        )
        english_bps = (
            self.run_dirs[0]
            / "Pokemon_Jaune_FR_repacked_title_from_english.bps"
        )
        pointer_manifest = self.audits / "pointer_manifest.json"
        script = self.input_paths["script"]
        translation_base = self.input_paths["translation_base_rom"]

        validator_steps: tuple[tuple[str, tuple[str | Path, ...]], ...] = (
            (
                "final-ips-roundtrip",
                (
                    self.helper,
                    "check-ips",
                    "--base-rom",
                    self.input_paths["canonical_english_rom"],
                    "--ips",
                    final_ips,
                    "--target-rom",
                    final_rom,
                ),
            ),
            (
                "verify-chinese-bps",
                (
                    self.input_paths["bps_patch"],
                    "verify",
                    "--source",
                    self.input_paths["chinese_rom"],
                    "--patch",
                    chinese_bps,
                    "--target",
                    final_rom,
                ),
            ),
            (
                "verify-english-bps",
                (
                    self.input_paths["bps_patch"],
                    "verify",
                    "--source",
                    translation_base,
                    "--patch",
                    english_bps,
                    "--target",
                    final_rom,
                ),
            ),
            (
                "validate-repacked",
                (
                    self.input_paths["validate_repacked"],
                    "--rom",
                    final_rom,
                    "--csv",
                    csv_path,
                    "--input-rom",
                    translation_base,
                    "--fixed-overflow",
                    fixed,
                ),
            ),
            (
                "validate-mapper163",
                (
                    self.input_paths["validate_mapper163"],
                    "--rom",
                    final_rom,
                    "--base-rom",
                    translation_base,
                "--title-logo",
                "english",
                "--title-credits-mode",
                "shared",
            ),
            ),
            (
                "validate-dialogue-layout",
                (
                    self.input_paths["validate_dialogue_layout"],
                    "--script",
                    script,
                    "--output",
                    self.audits / "dialogue_layout_validation.json",
                ),
            ),
            (
                "dialogue-page-quality",
                (
                    self.input_paths["dialogue_page_quality"],
                    "--script",
                    script,
                    "--output",
                    self.audits / "dialogue_page_quality.json",
                ),
            ),
            (
                "validate-pokedex-layout",
                (
                    self.input_paths["validate_pokedex_layout"],
                    "--script",
                    script,
                    "--rom",
                    translation_base,
                    "--output",
                    self.audits / "pokedex_layout_validation.json",
                ),
            ),
            (
                "validate-final-pokedex-runtime",
                (
                    self.input_paths["validate_final_pokedex_runtime"],
                    "--rom",
                    final_rom,
                    "--script",
                    script,
                    "--pointer-rom",
                    translation_base,
                    "--output",
                    self.audits / "final_pokedex_runtime_validation.json",
                ),
            ),
            (
                "audit-french-accents",
                (
                    self.input_paths["audit_french_accents"],
                    "--script",
                    script,
                    "--output",
                    self.audits / "french_accents.json",
                ),
            ),
            (
                "audit-quality",
                (
                    self.input_paths["audit_quality_ambitious"],
                    "--csv",
                    csv_path,
                    "--output",
                    self.audits / "audit_qualite_ambitieux.csv",
                    "--fail-on-high",
                ),
            ),
            (
                "audit-translation-coverage",
                (
                    self.input_paths["audit_translation_coverage"],
                    "--rom",
                    final_rom,
                    "--csv",
                    csv_path,
                    "--english-rom",
                    translation_base,
                    "--chinese-rom",
                    self.input_paths["chinese_rom"],
                    "--ascii-report",
                    self.audits / "translation_ascii_coverage.csv",
                    "--glyph-report",
                    self.audits / "translation_glyph_records.csv",
                ),
            ),
            (
                "generate-pointer-manifest",
                (
                    self.input_paths["pointer_manifest"],
                    "generate",
                    "--rom",
                    final_rom,
                    "--csv",
                    csv_path,
                    "--input-rom",
                    translation_base,
                    "--output",
                    pointer_manifest,
                ),
            ),
            (
                "validate-pointer-manifest",
                (
                    self.input_paths["pointer_manifest"],
                    "validate",
                    "--rom",
                    final_rom,
                    "--manifest",
                    pointer_manifest,
                    "--csv",
                    csv_path,
                    "--input-rom",
                    translation_base,
                ),
            ),
        )
        for name, command in validator_steps:
            self.run_step(name, command)

    def run_tests(self) -> None:
        if self.args.skip_tests:
            return
        self.run_step(
            "python-test-suite",
            (
                "-m",
                "unittest",
                "discover",
                "-s",
                "tools",
                "-p",
                "test_*.py",
                "-v",
            ),
            environment={"POKEMON_RELEASE_ACTIVE": "1"},
        )

    def assert_inputs_unchanged(self) -> None:
        for label, path in self.input_paths.items():
            actual = sha256_file(path)
            expected = self.initial_hashes[label]
            if actual != expected:
                raise ReleaseError(
                    f"input changed during the build ({label}) : "
                    f"{actual} instead of {expected}"
                )

    def promote(
        self,
        generated_csv: Path,
        generated_overflow: Path,
        deterministic_hashes: dict[str, str],
        current_hashes: dict[str, str],
    ) -> None:
        for filename in BUILD_FILENAMES:
            shutil.copy2(self.run_dirs[0] / filename, self.staging / filename)
        shutil.copy2(generated_csv, self.staging / "traduction_base.csv")
        shutil.copy2(
            generated_overflow,
            self.staging / "traductions_trop_longues.csv",
        )
        shutil.copy2(
            self.input_paths["external_patcher_proof"],
            self.staging / "external-patcher-proof.json",
        )

        shutil.rmtree(self.work)
        self.assert_inputs_unchanged()

        output_files = sorted(
            path
            for path in self.staging.rglob("*")
            if path.is_file()
            and path.name not in {"release_manifest.json", "SHA256SUMS"}
        )
        input_manifest = {}
        for label, path in sorted(self.input_paths.items()):
            try:
                display_path = str(path.relative_to(ROOT))
            except ValueError:
                display_path = str(path)
            input_manifest[label] = as_manifest_record(
                file_record(path, display_path)
            )
        output_manifest = {
            str(path.relative_to(self.staging)): as_manifest_record(
                file_record(path, str(path.relative_to(self.staging)))
            )
            for path in output_files
        }
        manifest = {
            "schema": "pokemon-yellow-nes-release/v1",
            "result": "PASS",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_root": str(ROOT),
            "python": sys.version.split()[0],
            "test_module_count": len(list(TOOLS_DIR.glob("test_*.py"))),
            "tool_source_count": sum(
                label.startswith("tool_source:")
                for label in self.input_paths
            ),
            "canonical_csv_regenerated": True,
            "double_build_deterministic": True,
            "deterministic_artifacts": deterministic_hashes,
            "current_artifacts_reproduced": bool(current_hashes),
            "current_artifact_hashes": current_hashes,
            "text_bank_budget_policy": TEXT_BANK_BUDGET_POLICY,
            "inputs": input_manifest,
            "steps": self.steps,
            "outputs": output_manifest,
        }
        manifest_path = self.staging / "release_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

        checksum_files = sorted(
            path
            for path in self.staging.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS"
        )
        checksum_lines = [
            f"{sha256_file(path)}  {path.relative_to(self.staging).as_posix()}"
            for path in checksum_files
        ]
        (self.staging / "SHA256SUMS").write_text(
            "\n".join(checksum_lines) + "\n",
            encoding="utf-8",
        )

        if self.output_dir.exists():
            raise ReleaseError(
                f"destination appeared during the build: {self.output_dir}"
            )
        os.replace(self.staging, self.output_dir)

    def build(self) -> None:
        try:
            self.prepare_inputs()
            generated_csv, generated_overflow = (
                self.generate_and_compare_csv()
            )
            self.run_provenance()
            self.run_budget_preflight()
            for run_directory in self.run_dirs:
                self.build_once(run_directory, generated_csv)
            deterministic_hashes = self.compare_builds()
            current_hashes = self.compare_current_artifacts()
            self.run_validators(generated_csv)
            self.run_tests()
            self.promote(
                generated_csv,
                generated_overflow,
                deterministic_hashes,
                current_hashes,
            )
        except Exception:
            if self.staging.exists():
                shutil.rmtree(self.staging)
            raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build twice, validate, then publish a release atomically."
        )
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--chinese-rom", default=DEFAULT_CHINESE_ROM)
    parser.add_argument("--english-ips", default=DEFAULT_ENGLISH_IPS)
    parser.add_argument(
        "--canonical-english-rom", default=DEFAULT_CANONICAL_ENGLISH_ROM
    )
    parser.add_argument(
        "--translation-base-rom", default=DEFAULT_TRANSLATION_BASE_ROM
    )
    parser.add_argument("--script", default=DEFAULT_SCRIPT)
    parser.add_argument("--canonical-csv", default=DEFAULT_CANONICAL_CSV)
    parser.add_argument(
        "--canonical-overflow-csv",
        default=DEFAULT_CANONICAL_OVERFLOW_CSV,
    )
    parser.add_argument(
        "--expect-current-artifacts",
        action="store_true",
        help=(
            "Require the five rebuilt artifacts to be identical "
            "to the files in the current directory."
        ),
    )
    parser.add_argument(
        "--current-artifacts-dir",
        default=ROOT,
        help="Directory containing the artifacts to reproduce with the preceding option.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help=(
            "Reserved for the wrapper integration test; validators "
            "remain mandatory."
        ),
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        builder = ReleaseBuilder(args)
        builder.build()
    except (OSError, ReleaseError, subprocess.SubprocessError) as exc:
        print(f"Release build: FAILED\n- {exc}", file=sys.stderr)
        return 1
    final_rom = builder.output_dir / "Pokemon_Jaune_FR_repacked_title.nes"
    print("Release build: PASS")
    print(f"- Directory: {builder.output_dir}")
    print(f"- Final ROM SHA-256: {sha256_file(final_rom)}")
    print(f"- Manifest : {builder.output_dir / 'release_manifest.json'}")
    print(f"- Checksums: {builder.output_dir / 'SHA256SUMS'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
