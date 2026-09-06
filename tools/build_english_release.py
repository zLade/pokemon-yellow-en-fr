#!/usr/bin/env python3
"""Build and publish the local, patch-only English 2.0 release.

This wrapper deliberately keeps complete ROMs under ``build/private`` and
publishes only reversible patches and documentation under ``dist``.  It
performs two independent builds, pins the three ROM inputs by SHA-256, rejects
an unreviewed catalogue, verifies every internally generated patch, and only
then promotes both release directories.

The wrapper does not translate text and does not modify its inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERSION = "2.0.0"
ROM_FILENAME = "Pokemon_Yellow_NJ046_EN_v2.0.0.nes"
IPS_FILENAME = "Pokemon_Yellow_NJ046_EN_v2.0.0.ips"
CHINESE_BPS_FILENAME = (
    "Pokemon_Yellow_NJ046_EN_v2.0.0_from_chinese.bps"
)
ENGLISH_BPS_FILENAME = (
    "Pokemon_Yellow_NJ046_EN_v2.0.0_from_english_2015.bps"
)
ALLOCATION_FILENAME = "english_text_allocation.csv"
BANK_BUDGET_FILENAME = "english_bank_budget.csv"
FIXED_OVERFLOW_FILENAME = "english_fixed_overflow.csv"
REVIEW_FILENAME = "English_fidelity_review.csv"

DEFAULT_CHINESE_ROM = (
    ROOT / "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"
)
DEFAULT_ENGLISH_2015_ROM = ROOT / "Pokemon Yellow English 9-23-2015.nes"
DEFAULT_YELLOW_ROM = ROOT / "yellow.nes"
DEFAULT_CATALOG = ROOT / "locales" / "en-US" / "catalog.csv"
DEFAULT_SOURCE_ADJUDICATIONS = (
    ROOT / "locales" / "en-US" / "source_adjudications.csv"
)
DEFAULT_POINTER_VARIANTS = (
    ROOT / "locales" / "en-US" / "pointer_variants.csv"
)
DEFAULT_STORAGE_OVERLAPS = (
    ROOT / "locales" / "en-US" / "storage_overlaps.csv"
)
DEFAULT_NEUTRAL_GLYPHS = (
    ROOT / "locales" / "en-US" / "neutral_glyph_records.csv"
)
DEFAULT_BANK_BUDGET_POLICY = (
    ROOT / "locales" / "en-US" / "bank_budget_policy.json"
)
DEFAULT_PRIVATE_DIR = ROOT / "build" / "private" / "en" / VERSION
DEFAULT_DIST_DIR = ROOT / "dist" / "en" / VERSION
DEFAULT_EVIDENCE_ROOT = ROOT / "build" / "evidence" / "en" / VERSION
DEFAULT_POINTER_INVENTORY = (
    ROOT / "data" / "source" / "structural_pointer_inventory.json"
)
DEFAULT_AUDITS_DIR = DEFAULT_EVIDENCE_ROOT / "audits"
DEFAULT_MESEN_LOGS_DIR = DEFAULT_EVIDENCE_ROOT / "mesen"

EXPECTED_ROM_SHA256: Mapping[str, str] = {
    "chinese_nj046": (
        "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e6"
        "5271e2f7b40c65ed"
    ),
    "english_2015": (
        "d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac"
        "112509d658a9943b"
    ),
    "yellow_canonical": (
        "69520103102677b33b47c15fae804dc1a742347a9ee1b02a"
        "9195e795eb6e431b"
    ),
}
EXPECTED_FRENCH_NON_REGRESSION_SHA256: Mapping[str, str] = {
    "text_rom": (
        "fe01711d751243f0afd9937691a1f080587eb97d83bf90587b83c49dabca032f"
    ),
    "text_ips": (
        "4d7c2c60ccfdbe1b308f7d8b4f5b54f76b0664ddab86cbe8fd61b76b3ac742a7"
    ),
    "fixed_overflow": (
        "8f7fb001b31bdb8544db4e9dcc6eeb7a6721e5a54e7f721a6738613b2fec89f2"
    ),
    "final_rom": (
        "1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b"
    ),
    "final_ips": (
        "912d9feaf7278f1cf0d139e4805360ad6d2232b68f98f9f9ac8e7e9bca9e5c29"
    ),
}

EXPECTED_MESEN_SHA256 = (
    "8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7"
)
EXPECTED_RUNTIME_REGIONS = ("Dendy", "Ntsc", "Pal")
EXPECTED_RUNTIME_STEPS_PER_REGION = (
    "01-boot",
    "02-mapper-runtime",
    "03-intro-broad",
    "04-intro-prompts",
    "05-english-charset",
    "06-title-and-new-load",
    "07-player-menu-exact",
    "08-campaign-start",
    "09-critical-restorations-pair6-assisted",
    "10-critical-restorations-pair7-assisted",
    "11-route1-viridian",
    "battery",
)
EXPECTED_MESEN_SCENARIOS: Mapping[str, tuple[str, str, str]] = {
    "01-boot": (
        "mesen_mapper163_boot_probe.lua",
        "POKEMON_MESEN_PASS",
        "none",
    ),
    "02-mapper-runtime": (
        "mesen_mapper163_runtime_probe.lua",
        "MAPPER163_PASS",
        "none",
    ),
    "03-intro-broad": (
        "mesen_pokemon_intro_probe.lua",
        "POKEMON_INTRO_PASS",
        "none",
    ),
    "04-intro-prompts": (
        "mesen_pokemon_intro_prompt_en_probe.lua",
        "POKEMON_ENGLISH_INTRO_PROMPTS_PASS",
        "none",
    ),
    "05-english-charset": (
        "mesen_english_charset_probe.lua",
        "POKEMON_ENGLISH_CHARSET_PASS",
        "none",
    ),
    "06-title-and-new-load": (
        "mesen_title_yellow_version_probe.lua",
        "TITLE_YELLOW_VERSION_PASS",
        "none",
    ),
    "07-player-menu-exact": (
        "mesen_player_menu_en_probe.lua",
        "POKEMON_PLAYER_MENU_EN_PASS",
        "none",
    ),
    "08-campaign-start": (
        "mesen_campaign_english_trace.lua",
        "POKEMON_CAMPAIGN_ENGLISH_TRACE_PASS",
        "none",
    ),
    "09-critical-restorations-pair6-assisted": (
        "mesen_critical_restorations_pair6_probe.lua",
        "POKEMON_CRITICAL_RESTORATIONS_PAIR6_PASS",
        "critical",
    ),
    "10-critical-restorations-pair7-assisted": (
        "mesen_critical_restorations_pair7_probe.lua",
        "POKEMON_CRITICAL_RESTORATIONS_PAIR7_PASS",
        "critical",
    ),
    "11-route1-viridian": (
        "mesen_fm3_route1_viridian_en_after_prototype.lua",
        "POKEMON_FM3_ROUTE1_VIRIDIAN_EN_TRACE_PASS",
        "route1",
    ),
    "01-fresh-control": (
        "mesen_battery_control_probe.lua",
        "POKEMON_BATTERY_CONTROL_PASS",
        "none",
    ),
    "02-create-save": (
        "mesen_battery_create_probe.lua",
        "POKEMON_BATTERY_CREATE_PASS",
        "none",
    ),
    "03-reload-save": (
        "mesen_battery_load_probe.lua",
        "POKEMON_BATTERY_LOAD_PASS",
        "none",
    ),
    "04-primary-corrupt": (
        "mesen_battery_corruption_probe.lua",
        "POKEMON_BATTERY_CORRUPTION_OBSERVED",
        "none",
    ),
    "05-backup-corrupt": (
        "mesen_battery_corruption_probe.lua",
        "POKEMON_BATTERY_CORRUPTION_OBSERVED",
        "none",
    ),
}
EXPECTED_ROUTE1_INPUT_SHA256 = (
    "ee79b39f3556a2acc316545614d77c910dc17b34e67ca7bbc17f803c13c46d9b"
)

EXPECTED_CATALOG_COUNTS: Mapping[str, int] = {
    "rows": 1929,
    "main": 1844,
    "restored": 85,
    "dialogues": 1055,
    "pokedex": 159,
}

VALIDATION_LIMITS: Mapping[str, str] = {
    "hardware_validation": "NON TESTÉ",
    "ram_quirk": "inherited_source_engine_quirk_unresolved",
    "harmlessness": "harmlessness_not_proven",
    "new_hzk16_extraction": "absent",
    "editorial_status": (
        "AI-assisted full source review; human playthrough pending"
    ),
}

DISALLOWED_COMPLETE_IMAGE_SUFFIXES = frozenset(
    {
        ".nes",
        ".rom",
        ".bin",
        ".sav",
        ".srm",
        ".state",
        ".cdl",
    }
)
ROM_SIGNATURES = (b"NES\x1a", b"FDS\x1a")
MAX_RUNTIME_EVIDENCE_BINARY_SIZE = 8 * 1024
PENDING_REVIEW_TOKENS = frozenset(
    {
        "",
        "draft",
        "needs_review",
        "pending",
        "todo",
        "unreviewed",
    }
)
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:\\+(?:Users|Documents|Temp)\\+", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9:])/(?:home|mnt|tmp|Users)/"),
    re.compile(r"file://", re.IGNORECASE),
)


class EnglishReleaseError(RuntimeError):
    """A release gate failed before either destination was promoted."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class CatalogueSummary:
    rows: int
    main: int
    restored: int
    dialogues: int
    pokedex: int

    def as_dict(self) -> dict[str, int]:
        return {
            "rows": self.rows,
            "main": self.main,
            "restored": self.restored,
            "dialogues": self.dialogues,
            "pokedex": self.pokedex,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, display_path: str) -> FileRecord:
    return FileRecord(
        path=display_path,
        size=path.stat().st_size,
        sha256=sha256_file(path),
    )


def manifest_record(record: FileRecord) -> dict[str, object]:
    return {
        "path": record.path,
        "size": record.size,
        "sha256": record.sha256,
    }


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise EnglishReleaseError(f"{label} absent ou non régulier: {resolved}")
    return resolved


def require_nonempty_directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir() or resolved.is_symlink():
        raise EnglishReleaseError(f"{label} absent ou non régulier: {resolved}")
    if not any(candidate.is_file() for candidate in resolved.rglob("*")):
        raise EnglishReleaseError(f"{label} vide: {resolved}")
    return resolved


def verify_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise EnglishReleaseError(
            f"SHA-256 {label} inattendu: {actual}; attendu {expected}"
        )


def _read_dict_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise EnglishReleaseError(f"CSV sans en-tête: {path}")
        return list(reader.fieldnames), list(reader)


def _normalized_status(value: str) -> str:
    return value.strip().casefold().replace(" ", "_").replace("-", "_")


def _assert_reviewed_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    label: str,
    status_field: str = "review_status",
) -> None:
    bad: list[str] = []
    for index, row in enumerate(rows, start=2):
        status = _normalized_status(row.get(status_field, ""))
        origin = _normalized_status(row.get("editorial_origin", "reviewed"))
        source_resolution = _normalized_status(
            row.get("source_resolution", "resolved")
        )
        resolution_status = _normalized_status(
            row.get("resolution_status", "resolved")
        )
        if (
            status in PENDING_REVIEW_TOKENS
            or "pending" in origin
            or "pending" in source_resolution
            or "pending" in resolution_status
        ):
            key = row.get("stable_key") or row.get("variant_key") or str(index)
            bad.append(key)
    if bad:
        preview = ", ".join(bad[:8])
        raise EnglishReleaseError(
            f"{label}: {len(bad)} ligne(s) non relue(s): {preview}"
        )


def validate_catalogue(path: Path) -> CatalogueSummary:
    fields, rows = _read_dict_rows(path)
    required = {
        "stable_key",
        "record_type",
        "category",
        "chinese_text",
        "english_v2",
        "editorial_origin",
        "source_resolution",
        "review_status",
        "compression",
        "compression_justification",
    }
    missing = sorted(required.difference(fields))
    if missing:
        raise EnglishReleaseError(
            "catalogue EN incomplet; colonnes absentes: " + ", ".join(missing)
        )
    _assert_reviewed_rows(rows, label="catalogue EN")

    keys = [row["stable_key"].strip() for row in rows]
    if any(not key for key in keys) or len(set(keys)) != len(keys):
        raise EnglishReleaseError("catalogue EN: stable_key vide ou dupliquée")

    incomplete = [
        row["stable_key"]
        for row in rows
        if not row["chinese_text"].strip()
        or not row["english_v2"].strip()
        or not row["editorial_origin"].strip()
        or not row["source_resolution"].strip()
    ]
    if incomplete:
        raise EnglishReleaseError(
            "catalogue EN: source/traduction/provenance absente pour "
            + ", ".join(incomplete[:8])
        )

    unjustified_compressions = [
        row["stable_key"]
        for row in rows
        if _normalized_status(row["compression"])
        not in {"", "none", "no", "not_required"}
        and not row["compression_justification"].strip()
    ]
    if unjustified_compressions:
        raise EnglishReleaseError(
            "catalogue EN: compression sans justification pour "
            + ", ".join(unjustified_compressions[:8])
        )

    types = Counter(row["record_type"].strip().upper() for row in rows)
    categories = Counter(row["category"].strip() for row in rows)
    summary = CatalogueSummary(
        rows=len(rows),
        main=types["MAIN"],
        restored=types["RESTORED"],
        dialogues=(
            categories["Dialogue en jeu"]
            + categories["Introduction"]
            + categories["Dialogue restauré"]
        ),
        pokedex=categories["Pokédex"],
    )
    if summary.as_dict() != dict(EXPECTED_CATALOG_COUNTS):
        raise EnglishReleaseError(
            "comptages du catalogue EN inattendus: "
            f"{summary.as_dict()}; attendu {dict(EXPECTED_CATALOG_COUNTS)}"
        )
    return summary


def validate_review_companion(
    path: Path,
    *,
    expected_rows: int,
    label: str,
    status_field: str | None = "review_status",
    required_nonempty: Sequence[str] = (),
) -> int:
    fields, rows = _read_dict_rows(path)
    if len(rows) != expected_rows:
        raise EnglishReleaseError(
            f"{label}: {len(rows)} lignes; attendu {expected_rows}"
        )
    if status_field is not None:
        if status_field not in fields:
            raise EnglishReleaseError(
                f"{label}: colonne {status_field} absente"
            )
        _assert_reviewed_rows(
            rows,
            label=label,
            status_field=status_field,
        )
    missing_fields = sorted(set(required_nonempty).difference(fields))
    if missing_fields:
        raise EnglishReleaseError(
            f"{label}: colonnes absentes: {', '.join(missing_fields)}"
        )
    incomplete = [
        str(index)
        for index, row in enumerate(rows, start=2)
        if any(not row[field].strip() for field in required_nonempty)
    ]
    if incomplete:
        raise EnglishReleaseError(
            f"{label}: champs requis vides aux lignes "
            + ", ".join(incomplete[:8])
        )
    return len(rows)


def _manifest_value(lines: Sequence[str], label: str, path: Path) -> str:
    prefix = label + ":"
    values = [
        line[len(prefix) :].strip()
        for line in lines
        if line.startswith(prefix)
    ]
    if len(values) != 1:
        raise EnglishReleaseError(
            f"preuve Mesen {path}: champ {label!r} présent {len(values)} fois"
        )
    return values[0]


def _manifest_basename(value: str) -> str:
    """Return a portable basename for Windows or POSIX evidence paths."""

    return value.replace("\\", "/").rsplit("/", 1)[-1]


def validate_mesen_evidence(
    directory: Path,
    expected_rom_sha256: str,
) -> dict[str, object]:
    """Bind the complete strict Mesen matrix to the built target hash."""

    expected_hash = expected_rom_sha256.casefold()
    runtime_manifests = sorted(directory.rglob("english_runtime_manifest.txt"))
    if len(runtime_manifests) != 1:
        raise EnglishReleaseError(
            "preuves Mesen: un seul english_runtime_manifest.txt est requis; "
            f"trouvé {len(runtime_manifests)}"
        )
    runtime_path = runtime_manifests[0]
    runtime_lines = runtime_path.read_text(
        encoding="utf-8-sig", errors="strict"
    ).splitlines()
    if _manifest_value(runtime_lines, "Candidate SHA-256", runtime_path).casefold() != expected_hash:
        raise EnglishReleaseError("preuves Mesen liées à un autre SHA de ROM")
    if _manifest_value(runtime_lines, "Result", runtime_path) != "PASS":
        raise EnglishReleaseError("suite Mesen anglaise non PASS")
    if _manifest_value(runtime_lines, "Regions", runtime_path) != ",".join(
        EXPECTED_RUNTIME_REGIONS
    ):
        raise EnglishReleaseError("matrice régionale Mesen incomplète")

    expected_steps = [
        f"{region}/{name}"
        for region in EXPECTED_RUNTIME_REGIONS
        for name in EXPECTED_RUNTIME_STEPS_PER_REGION
    ]
    declared_steps = int(
        _manifest_value(runtime_lines, "Executed steps", runtime_path)
    )
    step_pattern = re.compile(
        r"^Step (?P<number>\d{2}): PASS \| (?P<name>[^|]+?) \| "
    )
    observed_steps: list[str] = []
    for line in runtime_lines:
        match = step_pattern.match(line)
        if match is not None:
            expected_number = len(observed_steps) + 1
            if int(match.group("number")) != expected_number:
                raise EnglishReleaseError("ordre des étapes Mesen incohérent")
            observed_steps.append(match.group("name").strip())
    if declared_steps != len(expected_steps) or observed_steps != expected_steps:
        raise EnglishReleaseError(
            "matrice Mesen incomplète ou étape non PASS: "
            f"déclaré={declared_steps} observé={len(observed_steps)}"
        )

    scenario_manifests = sorted(directory.rglob("mesen_run_manifest.txt"))
    expected_scenarios = (
        len(EXPECTED_RUNTIME_REGIONS) * len(EXPECTED_MESEN_SCENARIOS)
    )
    if len(scenario_manifests) != expected_scenarios:
        raise EnglishReleaseError(
            "preuves Mesen: "
            f"{len(scenario_manifests)} scénarios; attendu {expected_scenarios}"
        )
    scenarios_by_region: Counter[str] = Counter()
    scenario_identities: set[tuple[str, str]] = set()
    critical_input_hashes: set[str] = set()
    for path in scenario_manifests:
        lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
        for label in ("ROM SHA-256 before", "ROM SHA-256 after"):
            if _manifest_value(lines, label, path).casefold() != expected_hash:
                raise EnglishReleaseError(
                    f"preuve Mesen {path} liée à un autre SHA de ROM"
                )
        required = {
            "Mesen executable SHA-256": EXPECTED_MESEN_SHA256,
            "iNES mapper": "163",
            "Strict hardware profile": "True",
            "Full NES debug-stop profile": "True",
            "Expected marker observed": "True",
            "Timed out": "False",
            "Result": "PASS",
        }
        for label, expected in required.items():
            if _manifest_value(lines, label, path) != expected:
                raise EnglishReleaseError(
                    f"preuve Mesen {path}: {label} n'est pas {expected}"
                )
        region = _manifest_value(lines, "Region", path)
        if region not in EXPECTED_RUNTIME_REGIONS:
            raise EnglishReleaseError(f"preuve Mesen région inattendue: {region}")
        if _manifest_value(lines, "Expected effective region", path) != region:
            raise EnglishReleaseError(
                f"preuve Mesen {path}: région effective non vérifiée"
            )

        scenario_name = path.parent.name
        expected_scenario = EXPECTED_MESEN_SCENARIOS.get(scenario_name)
        if expected_scenario is None:
            raise EnglishReleaseError(
                f"preuve Mesen {path}: scénario inattendu {scenario_name}"
            )
        identity = (region, scenario_name)
        if identity in scenario_identities:
            raise EnglishReleaseError(
                f"preuve Mesen dupliquée: {region}/{scenario_name}"
            )
        scenario_identities.add(identity)
        script_name, expected_marker, input_policy = expected_scenario
        actual_script = _manifest_basename(
            _manifest_value(lines, "Lua scenario", path)
        )
        if actual_script != script_name:
            raise EnglishReleaseError(
                f"preuve Mesen {path}: script {actual_script}, attendu {script_name}"
            )
        expected_script_hash = sha256_file(TOOLS_DIR / script_name)
        for label in (
            "Lua scenario SHA-256 before",
            "Lua scenario SHA-256 after",
        ):
            if _manifest_value(lines, label, path).casefold() != expected_script_hash:
                raise EnglishReleaseError(
                    f"preuve Mesen {path}: {label} ne correspond pas au script figé"
                )
        if _manifest_value(lines, "Expected marker", path) != expected_marker:
            raise EnglishReleaseError(
                f"preuve Mesen {path}: marqueur inattendu"
            )
        input_before = _manifest_value(
            lines, "Scenario input SHA-256 before", path
        ).casefold()
        input_after = _manifest_value(
            lines, "Scenario input SHA-256 after", path
        ).casefold()
        if input_before != input_after:
            raise EnglishReleaseError(
                f"preuve Mesen {path}: entrée changée pendant le scénario"
            )
        if input_policy == "none":
            if input_before:
                raise EnglishReleaseError(
                    f"preuve Mesen {path}: entrée inattendue"
                )
        elif input_policy == "route1":
            if input_before != EXPECTED_ROUTE1_INPUT_SHA256:
                raise EnglishReleaseError(
                    f"preuve Mesen {path}: flux Route 1 non canonique"
                )
        elif input_policy == "critical":
            if not re.fullmatch(r"[0-9a-f]{64}", input_before):
                raise EnglishReleaseError(
                    f"preuve Mesen {path}: spécification critique absente"
                )
            critical_input_hashes.add(input_before)
        else:
            raise AssertionError(f"politique d'entrée inconnue: {input_policy}")
        scenarios_by_region[region] += 1
    if scenarios_by_region != Counter(
        {
            region: len(EXPECTED_MESEN_SCENARIOS)
            for region in EXPECTED_RUNTIME_REGIONS
        }
    ):
        raise EnglishReleaseError(
            f"répartition régionale des scénarios invalide: {scenarios_by_region}"
        )
    expected_identities = {
        (region, scenario)
        for region in EXPECTED_RUNTIME_REGIONS
        for scenario in EXPECTED_MESEN_SCENARIOS
    }
    if scenario_identities != expected_identities:
        raise EnglishReleaseError("identités des scénarios Mesen incomplètes")
    if len(critical_input_hashes) != 1:
        raise EnglishReleaseError(
            "les six scénarios critiques doivent partager une spécification"
        )

    battery_manifests = sorted(directory.rglob("battery_persistence_manifest.txt"))
    if len(battery_manifests) != len(EXPECTED_RUNTIME_REGIONS):
        raise EnglishReleaseError(
            "preuves batterie Mesen incomplètes: "
            f"{len(battery_manifests)} au lieu de 3"
        )
    battery_regions: set[str] = set()
    for path in battery_manifests:
        lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
        required = {
            "ROM SHA-256": expected_hash,
            "iNES mapper": "163",
            "Strict hardware profile": "True",
            "Full NES debug-stop profile": "True",
            "Primary corruption restored from valid backup": "true",
            "Primary-corrupt CONT equals valid resumed room": "true",
            "Backup-corrupt CONT equals fresh fallback": "true",
            "Corruption scenarios use memory injection": "false",
            "Result": "PASS",
        }
        for label, expected in required.items():
            actual = _manifest_value(lines, label, path)
            if label == "ROM SHA-256":
                actual = actual.casefold()
            if actual != expected:
                raise EnglishReleaseError(
                    f"preuve batterie {path}: {label} n'est pas {expected}"
                )
        region = _manifest_value(lines, "Region", path)
        if region not in EXPECTED_RUNTIME_REGIONS or region in battery_regions:
            raise EnglishReleaseError(
                f"preuve batterie région absente ou dupliquée: {region}"
            )
        battery_regions.add(region)

    return {
        "result": "PASS",
        "candidate_sha256": expected_hash,
        "regions": list(EXPECTED_RUNTIME_REGIONS),
        "suite_steps": len(expected_steps),
        "scenario_manifests": len(scenario_manifests),
        "battery_manifests": len(battery_manifests),
        "strict_hardware": True,
        "full_debug": True,
        "mesen_sha256": EXPECTED_MESEN_SHA256,
    }


def _git_output(root: Path, arguments: Sequence[str]) -> str:
    process = subprocess.run(
        ["git", *arguments],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if process.returncode != 0:
        raise EnglishReleaseError(
            f"git {' '.join(arguments)} a échoué: {process.stdout.strip()}"
        )
    return process.stdout.strip()


def require_clean_git_revision(root: Path) -> str:
    revision = _git_output(root, ("rev-parse", "HEAD"))
    status = _git_output(
        root,
        ("status", "--porcelain", "--untracked-files=all", "--", "."),
    )
    if status:
        preview = "\n".join(status.splitlines()[:12])
        raise EnglishReleaseError(
            "les sources de release doivent être figées dans Git:\n" + preview
        )
    return revision


def _unsafe_image_file(path: Path) -> bool:
    suffixes = {suffix.casefold() for suffix in path.suffixes}
    if suffixes.intersection(DISALLOWED_COMPLETE_IMAGE_SUFFIXES):
        return True
    with path.open("rb") as handle:
        prefix = handle.read(4)
    return any(prefix.startswith(signature) for signature in ROM_SIGNATURES)


def _unsafe_evidence_file(path: Path) -> bool:
    """Reject ROM-like evidence while allowing bounded RAM/PPU snapshots."""

    with path.open("rb") as handle:
        prefix = handle.read(4)
    if any(prefix.startswith(signature) for signature in ROM_SIGNATURES):
        return True
    suffix = path.suffix.casefold()
    if suffix in {".nes", ".rom", ".state", ".cdl"}:
        return True
    if suffix in {".bin", ".sav", ".srm"}:
        return path.stat().st_size > MAX_RUNTIME_EVIDENCE_BINARY_SIZE
    return False


def assert_no_complete_images(directory: Path) -> None:
    violations: list[str] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            violations.append(f"symlink:{path.relative_to(directory).as_posix()}")
        elif path.is_file() and _unsafe_image_file(path):
            violations.append(path.relative_to(directory).as_posix())
    if violations:
        raise EnglishReleaseError(
            "image complète/interdite dans le bundle patch-only: "
            + ", ".join(violations)
        )


def assert_portable_text_tree(directory: Path) -> None:
    violations: list[str] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.casefold() in {".bps", ".ips"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(text) for pattern in ABSOLUTE_PATH_PATTERNS):
            violations.append(path.relative_to(directory).as_posix())
    if violations:
        raise EnglishReleaseError(
            "chemin absolu ou donnée locale dans le bundle: "
            + ", ".join(violations)
        )


def normalize_log_paths(text: str, replacements: Mapping[str, str]) -> str:
    normalized = text
    for source, replacement in sorted(
        replacements.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if source:
            normalized = normalized.replace(source, replacement)
            normalized = normalized.replace(source.replace("/", "\\"), replacement)
    normalized = re.sub(
        r"[A-Za-z]:\\Users\\[^\\\r\n]+",
        "$LOCAL_USER",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"/(?:home|mnt/[a-z]/Users)/[^/\r\n]+",
        "$LOCAL_USER",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def create_verified_ips(base: Path, target: Path, output: Path) -> str:
    """Create and round-trip an IPS using the project's internal generator."""

    from rom_traduction_assistant import apply_ips, make_ips, parse_ips

    base_bytes = base.read_bytes()
    target_bytes = target.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(make_ips(base_bytes, target_bytes))
    records, truncate = parse_ips(output)
    rebuilt = apply_ips(base_bytes, records, truncate)
    if rebuilt != target_bytes:
        raise EnglishReleaseError("échec de l'aller-retour IPS interne")
    return sha256_file(output)


def assistant_build_arguments(
    *,
    assistant: Path,
    catalog: Path,
    pointer_variants: Path,
    english_rom: Path,
    output_rom: Path,
    output_ips: Path,
    allocation_csv: Path,
    bank_budget_csv: Path | None = None,
    fixed_overflow_csv: Path | None = None,
) -> tuple[str | Path, ...]:
    """Return the canonical English profile invocation used by both builds."""

    bank_budget_csv = bank_budget_csv or allocation_csv.with_name(
        BANK_BUDGET_FILENAME
    )
    fixed_overflow_csv = fixed_overflow_csv or allocation_csv.with_name(
        FIXED_OVERFLOW_FILENAME
    )

    return (
        assistant,
        "build-repacked",
        "--profile",
        "en-US",
        "--csv",
        catalog,
        "--restorations-csv",
        catalog,
        "--pointer-variants-csv",
        pointer_variants,
        "--input-rom",
        english_rom,
        "--output-rom",
        output_rom,
        "--output-ips",
        output_ips,
        "--fixed-overflow-output",
        fixed_overflow_csv,
        "--allocation-output",
        allocation_csv,
        "--bank-budget-output",
        bank_budget_csv,
    )


def assert_same_file(left: Path, right: Path, label: str) -> str:
    left_hash = sha256_file(left)
    right_hash = sha256_file(right)
    if left_hash != right_hash or left.read_bytes() != right.read_bytes():
        raise EnglishReleaseError(
            f"double build non déterministe ({label}): "
            f"{left_hash} != {right_hash}"
        )
    return left_hash


def write_sha256sums(directory: Path) -> None:
    paths = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    lines = [
        f"{sha256_file(path)}  {path.relative_to(directory).as_posix()}"
        for path in paths
    ]
    (directory / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def tree_manifest(
    directory: Path,
    *,
    excluded_names: frozenset[str] = frozenset(),
) -> dict[str, dict[str, object]]:
    return {
        path.relative_to(directory).as_posix(): manifest_record(
            file_record(path, path.relative_to(directory).as_posix())
        )
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name not in excluded_names
    }


def publish_transactionally(
    private_stage: Path,
    private_destination: Path,
    dist_stage: Path,
    dist_destination: Path,
) -> None:
    """Promote two directories and roll the first back if the second fails."""

    if private_destination.exists() or dist_destination.exists():
        raise EnglishReleaseError(
            "une destination de release existe déjà; aucune écrasement autorisé"
        )
    private_destination.parent.mkdir(parents=True, exist_ok=True)
    dist_destination.parent.mkdir(parents=True, exist_ok=True)
    promoted_private = False
    try:
        os.replace(private_stage, private_destination)
        promoted_private = True
        os.replace(dist_stage, dist_destination)
    except Exception:
        if promoted_private and private_destination.exists():
            os.replace(private_destination, private_stage)
        raise


def _copy_evidence_tree(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise EnglishReleaseError(f"lien symbolique interdit: {path}")
        if not path.is_file():
            continue
        if _unsafe_evidence_file(path):
            raise EnglishReleaseError(f"image complète dans les preuves: {path}")
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _documentation(
    target_hash: str,
    *,
    external_patcher_status: str,
) -> Mapping[str, str]:
    bases = EXPECTED_ROM_SHA256
    readme = f"""# Pokémon Yellow NES — English fidelity 2.0

Unofficial, local patch-only release. No complete ROM is included.

## Apply one patch

- `{CHINESE_BPS_FILENAME}` requires the NJ046 Chinese ROM with SHA-256
  `{bases['chinese_nj046']}`.
- `{ENGLISH_BPS_FILENAME}` requires the 2015 English ROM with SHA-256
  `{bases['english_2015']}`.
- `{IPS_FILENAME}` is a compatibility patch and requires **only** `yellow.nes`
  with SHA-256 `{bases['yellow_canonical']}`.

All three routes must produce `{ROM_FILENAME}` with SHA-256
`{target_hash}`. Verify the base hash before applying a patch, then verify the
target hash. This project is not affiliated with Nintendo, Game Freak, or The
Pokémon Company.
"""
    policy = """# Translation policy

- The Chinese NJ046 text is the semantic source of record.
- The 2015 English text is reusable only when it faithfully represents that
  source; official English terminology may be preferred where appropriate.
- Natural English adaptation is allowed without changing the source meaning.
- Space-driven compression must be explicit and justified in the review CSV.
- The French 2.0 text is a secondary gloss, never the primary semantic source.
- No licence is asserted or added for third-party data.
"""
    changelog = """# Changelog

## 2.0.0

- Restores Chinese-source dialogue omitted from the 2015 English release.
- Reworks English text against the Chinese semantic source.
- Separates English codec/layout/release policy from the French release.
- Adds deterministic dual builds and three verified patch routes.
- Ships review matrices and explicit validation limits.
"""
    fidelity = f"""# Fidelity report

The canonical catalogue contains 1,844 main entries and 85 restored entries
(1,929 total), including 1,055 dialogue/intro records and 159 Pokédex entries.
Its review tables record Chinese provenance, retained official terminology,
natural adaptations, and ROM-size compression decisions.

Editorial status: {VALIDATION_LIMITS['editorial_status']}.

The internal IPS and BPS round-trips passed byte-for-byte. External patcher
matrix status: `{external_patcher_status}`. Static coverage and scenes actually
visited in Mesen remain separate evidence; this report does not turn a Route 1
diagnostic into a complete playthrough.
"""
    limits = f"""# Exact validation limits

- Mapper 163 hardware validation: **{VALIDATION_LIMITS['hardware_validation']}**.
- Inherited RAM issue: `{VALIDATION_LIMITS['ram_quirk']}`.
- Harmlessness conclusion: `{VALIDATION_LIMITS['harmlessness']}`.
- New HZK16 extraction: `{VALIDATION_LIMITS['new_hzk16_extraction']}`; none is
  claimed by this release.
- Editorial status: {VALIDATION_LIMITS['editorial_status']}.
- This is an unofficial project and any potential public release is
  patch-only.
"""
    return {
        "README.md": readme,
        "TRANSLATION_POLICY.md": policy,
        "CHANGELOG.md": changelog,
        "FIDELITY_REPORT.md": fidelity,
        "VALIDATION_LIMITS.md": limits,
    }


class EnglishReleaseBuilder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.python = str(Path(args.python).expanduser().resolve())
        self.private_destination = Path(args.private_dir).expanduser().resolve()
        self.dist_destination = Path(args.dist_dir).expanduser().resolve()
        if self.private_destination.exists() or self.dist_destination.exists():
            raise EnglishReleaseError(
                "une destination de release existe déjà; aucune écrasement autorisé"
            )

        # Check the revision before creating the dist-side staging directory,
        # which is intentionally not ignored by Git.
        self.revision = require_clean_git_revision(ROOT)

        self.inputs: dict[str, Path] = {}
        self.initial_hashes: dict[str, str] = {}
        self.evidence_hashes: dict[str, dict[str, str]] = {}
        self.steps: list[dict[str, object]] = []
        self.catalogue_summary: CatalogueSummary | None = None
        self.mesen_summary: dict[str, object] | None = None
        self.external_status = "not_run_no_complete_pinned_external_tool_matrix"

        self.private_destination.parent.mkdir(parents=True, exist_ok=True)
        self.dist_destination.parent.mkdir(parents=True, exist_ok=True)
        self.private_stage = Path(
            tempfile.mkdtemp(
                prefix=f".{self.private_destination.name}.staging-",
                dir=self.private_destination.parent,
            )
        )
        self.dist_stage = Path(
            tempfile.mkdtemp(
                prefix=f".{self.dist_destination.name}.staging-",
                dir=self.dist_destination.parent,
            )
        )
        work_parent = ROOT / "build"
        work_parent.mkdir(parents=True, exist_ok=True)
        self.work = Path(
            tempfile.mkdtemp(
                prefix=".english-release-work-", dir=work_parent
            )
        )
        self.logs = self.work / "logs"
        self.logs.mkdir()
        self.run_dirs = [self.work / "run-1", self.work / "run-2"]
        for directory in self.run_dirs:
            directory.mkdir()

    def _display_argument(self, value: str) -> str:
        replacements = (
            (str(self.work), "$WORK"),
            (str(ROOT), "$ROOT"),
            (self.python, "$PYTHON"),
        )
        for prefix, replacement in replacements:
            if value == prefix:
                return replacement
            if value.startswith(prefix + os.sep):
                return replacement + value[len(prefix) :]
        if Path(value).is_absolute():
            return f"$EXTERNAL/{Path(value).name}"
        return value

    def run_step(self, name: str, arguments: Sequence[str | Path]) -> None:
        command = [self.python, *(str(item) for item in arguments)]
        process = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        log = normalize_log_paths(
            process.stdout,
            {
                str(self.work): "$WORK",
                str(ROOT): "$ROOT",
                str(Path.home()): "$LOCAL_HOME",
            },
        )
        log_path = self.logs / f"{len(self.steps) + 1:02d}-{name}.log"
        log_path.write_text(log, encoding="utf-8", newline="\n")
        self.steps.append(
            {
                "name": name,
                "command": [self._display_argument(item) for item in command],
                "returncode": process.returncode,
                "log": f"logs/python/{log_path.name}",
            }
        )
        if process.returncode != 0:
            tail = "\n".join(log.splitlines()[-12:])
            raise EnglishReleaseError(
                f"étape {name} en échec (code {process.returncode})\n{tail}"
            )

    def prepare_inputs(self) -> None:
        requested = {
            "chinese_nj046": self.args.chinese_rom,
            "english_2015": self.args.english_2015_rom,
            "yellow_canonical": self.args.yellow_rom,
            "catalog": self.args.catalog,
            "source_adjudications": self.args.source_adjudications,
            "pointer_variants": self.args.pointer_variants,
            "storage_overlaps": self.args.storage_overlaps,
            "neutral_glyphs": self.args.neutral_glyphs,
            "bank_budget_policy": self.args.bank_budget_policy,
            "pointer_inventory": self.args.pointer_inventory,
            "french_catalog": ROOT / "traduction_base.csv",
            "assistant": ROOT / "rom_traduction_assistant.py",
            "title_screen_tools": TOOLS_DIR / "title_screen_tools.py",
            "restore_chinese_dojo_deputy": (
                TOOLS_DIR / "restore_chinese_dojo_deputy.py"
            ),
            "bps_patch": TOOLS_DIR / "bps_patch.py",
            "pointer_manifest_tool": TOOLS_DIR / "english_pointer_manifest.py",
            "catalog_validator": TOOLS_DIR / "validate_english_catalog.py",
            "exact_repacked_validator": (
                TOOLS_DIR / "validate_english_repacked.py"
            ),
            "mapper_validator": TOOLS_DIR / "validate_mapper163.py",
            "bank_budget_validator": (
                TOOLS_DIR / "validate_english_bank_budget.py"
            ),
            "glyph_residue_validator": (
                TOOLS_DIR / "validate_english_glyph_residue.py"
            ),
            "runtime_text_validator": (
                TOOLS_DIR / "validate_english_runtime_text_reads.py"
            ),
            "critical_restoration_runtime_preparer": (
                TOOLS_DIR / "prepare_critical_restoration_runtime.py"
            ),
            "wrapper": Path(__file__),
        }
        self.inputs = {
            label: require_file(Path(path), label)
            for label, path in requested.items()
        }
        self.inputs["audits_dir"] = require_nonempty_directory(
            Path(self.args.audits_dir), "audits anglais"
        )
        self.inputs["mesen_logs_dir"] = require_nonempty_directory(
            Path(self.args.mesen_logs_dir), "journaux Mesen"
        )
        for label in ("audits_dir", "mesen_logs_dir"):
            directory = self.inputs[label]
            self.evidence_hashes[label] = {
                path.relative_to(directory).as_posix(): sha256_file(path)
                for path in sorted(directory.rglob("*"))
                if path.is_file() and not path.is_symlink()
            }

        for label, expected in EXPECTED_ROM_SHA256.items():
            verify_hash(self.inputs[label], expected, label)

        self.catalogue_summary = validate_catalogue(self.inputs["catalog"])
        validate_review_companion(
            self.inputs["source_adjudications"],
            expected_rows=63,
            label="adjudications de source",
            required_nonempty=(
                "selected_source_method",
                "selected_chinese_text",
                "resolution_status",
            ),
        )
        validate_review_companion(
            self.inputs["pointer_variants"],
            expected_rows=5,
            label="variantes de pointeur",
            required_nonempty=(
                "chinese_text",
                "english_v2",
                "editorial_origin",
            ),
        )
        validate_review_companion(
            self.inputs["storage_overlaps"],
            expected_rows=3,
            label="chevauchements de stockage",
            status_field=None,
            required_nonempty=(
                "owner_key",
                "alias_key",
                "relationship",
                "structural_status",
            ),
        )
        validate_review_companion(
            self.inputs["neutral_glyphs"],
            expected_rows=18,
            label="pictogrammes graphiques neutres",
            status_field="review_status",
            required_nonempty=(
                "record_index",
                "start_hex",
                "end_hex_exclusive",
                "classification",
                "reason",
            ),
        )

        external = (
            self.args.lunar_ips_exe,
            self.args.floating_ips_exe,
            self.args.floating_ips_archive,
        )
        if not all(external):
            raise EnglishReleaseError(
                "la release finale exige Lunar IPS, Floating IPS et son "
                "archive officielle pour la matrice externe"
            )
        if not self.args.external_verified_utc:
            raise EnglishReleaseError(
                "--external-verified-utc est requis pour une preuve reproductible"
            )
        self.inputs["lunar_ips_exe"] = require_file(
            Path(self.args.lunar_ips_exe), "Lunar IPS"
        )
        self.inputs["floating_ips_exe"] = require_file(
            Path(self.args.floating_ips_exe), "Floating IPS"
        )
        self.inputs["floating_ips_archive"] = require_file(
            Path(self.args.floating_ips_archive), "archive Floating IPS"
        )

        self.initial_hashes = {
            label: sha256_file(path)
            for label, path in self.inputs.items()
            if path.is_file()
        }

    def verify_french_non_regression(self) -> None:
        """Rebuild the canonical FR release and require all golden hashes."""

        directory = self.work / "french-non-regression"
        directory.mkdir()
        artifacts = {
            "text_rom": directory / "Pokemon_Jaune_FR_repacked.nes",
            "text_ips": directory / "Pokemon_Jaune_FR_repacked.ips",
            "fixed_overflow": directory / "textes_fixes_trop_longs.csv",
            "final_rom": directory / "Pokemon_Jaune_FR_repacked_title.nes",
            "final_ips": directory / "Pokemon_Jaune_FR_repacked_title.ips",
        }
        self.run_step(
            "french-non-regression-text",
            (
                self.inputs["assistant"],
                "build-repacked",
                "--profile",
                "fr-FR",
                "--csv",
                self.inputs["french_catalog"],
                "--input-rom",
                self.inputs["english_2015"],
                "--output-rom",
                artifacts["text_rom"],
                "--output-ips",
                artifacts["text_ips"],
                "--fixed-overflow-output",
                artifacts["fixed_overflow"],
            ),
        )
        self.run_step(
            "french-non-regression-graphics",
            (
                self.inputs["title_screen_tools"],
                "patch-french-graphics",
                "--rom",
                artifacts["text_rom"],
                "--base-rom",
                self.inputs["yellow_canonical"],
                "--title-logo",
                "english",
                "--english-title-rom",
                self.inputs["english_2015"],
                "--out-rom",
                artifacts["final_rom"],
                "--out-ips",
                artifacts["final_ips"],
                "--out",
                directory / "graphics",
            ),
        )
        actual = {
            label: sha256_file(path) for label, path in artifacts.items()
        }
        if actual != dict(EXPECTED_FRENCH_NON_REGRESSION_SHA256):
            differences = [
                f"{label}: {actual.get(label)} != {expected}"
                for label, expected in EXPECTED_FRENCH_NON_REGRESSION_SHA256.items()
                if actual.get(label) != expected
            ]
            raise EnglishReleaseError(
                "French golden non-regression broken: "
                + "; ".join(differences)
            )
        self.french_non_regression = {
            "result": "PASS",
            "sha256": actual,
        }
        _write_json(
            directory / "french_non_regression.json",
            self.french_non_regression,
        )

    def build_once(self, run_directory: Path) -> None:
        target = run_directory / ROM_FILENAME
        title_target = run_directory / "english_title_before_dojo_restore.nes"
        assistant_ips = run_directory / "assistant_from_english_2015.ips"
        allocation = run_directory / ALLOCATION_FILENAME
        bank_budget = run_directory / BANK_BUDGET_FILENAME
        fixed_overflow = run_directory / FIXED_OVERFLOW_FILENAME
        run_label = run_directory.name
        self.run_step(
            f"build-repacked-{run_label}",
            assistant_build_arguments(
                assistant=self.inputs["assistant"],
                catalog=self.inputs["catalog"],
                pointer_variants=self.inputs["pointer_variants"],
                english_rom=self.inputs["english_2015"],
                output_rom=target,
                output_ips=assistant_ips,
                allocation_csv=allocation,
                bank_budget_csv=bank_budget,
                fixed_overflow_csv=fixed_overflow,
            ),
        )
        raw_target = run_directory / "assistant_text_only.nes"
        target.replace(raw_target)
        self.run_step(
            f"english-yellow-title-{run_label}",
            (
                self.inputs["title_screen_tools"],
                "patch-english-title",
                "--rom",
                raw_target,
                "--yellow-rom",
                self.inputs["yellow_canonical"],
                "--base-rom",
                self.inputs["english_2015"],
                "--credits",
                "LUIGA2009, ZLADE, CHPEXO",
                "--out-rom",
                title_target,
                "--out-ips",
                run_directory / "english_title_before_dojo_restore.ips",
                "--out",
                run_directory / "english-title-assets",
            ),
        )
        self.run_step(
            f"restore-chinese-dojo-deputy-{run_label}",
            (
                self.inputs["restore_chinese_dojo_deputy"],
                "--rom",
                title_target,
                "--chinese-rom",
                self.inputs["chinese_nj046"],
                "--out-rom",
                target,
                "--base-rom",
                self.inputs["english_2015"],
                "--out-ips",
                run_directory / "english_title_from_english_2015.ips",
            ),
        )
        for output, label in (
            (target, "ROM anglaise"),
            (assistant_ips, "IPS de build anglais"),
            (allocation, "rapport d'allocation"),
            (bank_budget, "budget des banques"),
            (fixed_overflow, "rapport des textes fixes"),
        ):
            require_file(output, f"{label} {run_label}")

        self.run_step(
            f"catalogue-gate-{run_label}",
            (
                self.inputs["catalog_validator"],
                "--catalogue",
                self.inputs["catalog"],
                "--adjudications",
                self.inputs["source_adjudications"],
                "--variants",
                self.inputs["pointer_variants"],
                "--overlaps",
                self.inputs["storage_overlaps"],
                "--output",
                run_directory / "catalogue_validation.json",
            ),
        )

        self.run_step(
            f"mapper163-{run_label}",
            (
                self.inputs["mapper_validator"],
                "--rom",
                target,
                "--base-rom",
                self.inputs["english_2015"],
                "--profile",
                "en-US",
                "--title-logo",
                "yellow-version",
                "--title-reference-rom",
                self.inputs["yellow_canonical"],
                "--title-credits",
                "LUIGA2009, ZLADE, CHPEXO",
            ),
        )

        self.run_step(
            f"exact-repacked-{run_label}",
            (
                self.inputs["exact_repacked_validator"],
                "--rom",
                raw_target,
                "--base-rom",
                self.inputs["english_2015"],
                "--catalogue",
                self.inputs["catalog"],
                "--variants",
                self.inputs["pointer_variants"],
                "--output",
                run_directory / "exact_repacked_validation.json",
            ),
        )

        self.run_step(
            f"bank-budget-{run_label}",
            (
                self.inputs["bank_budget_validator"],
                "--allocation",
                allocation,
                "--budget",
                bank_budget,
                "--policy",
                self.inputs["bank_budget_policy"],
                "--output",
                run_directory / "bank_budget_validation.json",
            ),
        )

        self.run_step(
            f"glyph-residue-{run_label}",
            (
                self.inputs["glyph_residue_validator"],
                "--rom",
                target,
                "--base-rom",
                self.inputs["english_2015"],
                "--catalogue",
                self.inputs["catalog"],
                "--neutral",
                self.inputs["neutral_glyphs"],
                "--output",
                run_directory / "glyph_residue_validation.json",
            ),
        )

        self.run_step(
            f"pointer-manifest-{run_label}",
            (
                self.inputs["pointer_manifest_tool"],
                "build",
                "--rom",
                target,
                "--catalogue",
                self.inputs["catalog"],
                "--variants",
                self.inputs["pointer_variants"],
                "--inventory",
                self.inputs["pointer_inventory"],
                "--output",
                run_directory / "pointer_manifest.json",
            ),
        )

        self.run_step(
            f"runtime-text-reads-{run_label}",
            (
                "-m",
                "tools.validate_english_runtime_text_reads",
                "--pointer-manifest",
                run_directory / "pointer_manifest.json",
                "--mesen-root",
                self.inputs["mesen_logs_dir"],
                "--output",
                run_directory / "runtime_text_read_validation.json",
            ),
        )

        create_verified_ips(
            self.inputs["yellow_canonical"],
            target,
            run_directory / IPS_FILENAME,
        )
        for source_label, patch_name, metadata in (
            (
                "chinese_nj046",
                CHINESE_BPS_FILENAME,
                "Pokemon Yellow NES EN 2.0.0; source=NJ046 Chinese",
            ),
            (
                "english_2015",
                ENGLISH_BPS_FILENAME,
                "Pokemon Yellow NES EN 2.0.0; source=English 2015",
            ),
        ):
            patch = run_directory / patch_name
            self.run_step(
                f"create-{source_label}-bps-{run_label}",
                (
                    self.inputs["bps_patch"],
                    "create",
                    "--source",
                    self.inputs[source_label],
                    "--target",
                    target,
                    "--patch",
                    patch,
                    "--metadata",
                    metadata,
                ),
            )
            self.run_step(
                f"verify-{source_label}-bps-{run_label}",
                (
                    self.inputs["bps_patch"],
                    "verify",
                    "--source",
                    self.inputs[source_label],
                    "--patch",
                    patch,
                    "--target",
                    target,
                ),
            )

    def compare_builds(self) -> dict[str, str]:
        deterministic = (
            ROM_FILENAME,
            "assistant_from_english_2015.ips",
            ALLOCATION_FILENAME,
            BANK_BUDGET_FILENAME,
            FIXED_OVERFLOW_FILENAME,
            IPS_FILENAME,
            CHINESE_BPS_FILENAME,
            ENGLISH_BPS_FILENAME,
            "pointer_manifest.json",
            "catalogue_validation.json",
            "exact_repacked_validation.json",
            "bank_budget_validation.json",
            "glyph_residue_validation.json",
            "runtime_text_read_validation.json",
        )
        return {
            filename: assert_same_file(
                self.run_dirs[0] / filename,
                self.run_dirs[1] / filename,
                filename,
            )
            for filename in deterministic
        }

    def run_external_patchers(self) -> Path | None:
        if "lunar_ips_exe" not in self.inputs:
            return None
        proof = self.work / "external_patcher_proof.json"
        first = self.run_dirs[0]
        self.run_step(
            "external-patcher-matrix",
            (
                TOOLS_DIR / "generate_external_patcher_proof.py",
                "--root",
                ROOT,
                "--target-rom",
                first / ROM_FILENAME,
                "--ips-base",
                self.inputs["yellow_canonical"],
                "--ips-patch",
                first / IPS_FILENAME,
                "--chinese-base",
                self.inputs["chinese_nj046"],
                "--chinese-bps",
                first / CHINESE_BPS_FILENAME,
                "--english-base",
                self.inputs["english_2015"],
                "--english-bps",
                first / ENGLISH_BPS_FILENAME,
                "--lunar-ips-exe",
                self.inputs["lunar_ips_exe"],
                "--floating-ips-exe",
                self.inputs["floating_ips_exe"],
                "--floating-ips-archive",
                self.inputs["floating_ips_archive"],
                "--output",
                proof,
                "--temp-parent",
                self.work / "external-temp",
                "--verified-utc",
                self.args.external_verified_utc,
            ),
        )
        payload = json.loads(proof.read_text(encoding="utf-8"))
        target_hash = sha256_file(first / ROM_FILENAME)
        if (
            payload.get("result") != "PASS"
            or payload.get("target", {}).get("sha256") != target_hash
        ):
            raise EnglishReleaseError("preuve des patchers externes incohérente")
        self.external_status = "PASS"
        return proof

    def assert_inputs_unchanged(self) -> None:
        for label, expected in self.initial_hashes.items():
            actual = sha256_file(self.inputs[label])
            if actual != expected:
                raise EnglishReleaseError(
                    f"entrée modifiée pendant le build ({label}): {actual}"
                )
        for label, expected_records in self.evidence_hashes.items():
            directory = self.inputs[label]
            actual_records = {
                path.relative_to(directory).as_posix(): sha256_file(path)
                for path in sorted(directory.rglob("*"))
                if path.is_file() and not path.is_symlink()
            }
            if actual_records != expected_records:
                raise EnglishReleaseError(
                    f"preuves modifiées pendant le build ({label})"
                )

    def _input_manifest(self) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for label, path in sorted(self.inputs.items()):
            if not path.is_file():
                continue
            display = path.name
            try:
                display = path.relative_to(ROOT).as_posix()
            except ValueError:
                display = f"external/{path.name}"
            result[label] = manifest_record(file_record(path, display))
        for label, records in sorted(self.evidence_hashes.items()):
            directory = self.inputs[label]
            for relative, digest in sorted(records.items()):
                path = directory / relative
                key = f"{label}:{relative}"
                result[key] = {
                    "path": f"evidence/{label}/{relative}",
                    "size": path.stat().st_size,
                    "sha256": digest,
                }
        return result

    def stage_release(
        self,
        deterministic_hashes: Mapping[str, str],
        external_proof: Path | None,
    ) -> None:
        first = self.run_dirs[0]
        target = first / ROM_FILENAME
        target_hash = sha256_file(target)

        shutil.copyfile(target, self.private_stage / ROM_FILENAME)
        shutil.copyfile(
            first / ALLOCATION_FILENAME,
            self.private_stage / ALLOCATION_FILENAME,
        )
        shutil.copyfile(
            first / BANK_BUDGET_FILENAME,
            self.private_stage / BANK_BUDGET_FILENAME,
        )
        shutil.copyfile(
            first / FIXED_OVERFLOW_FILENAME,
            self.private_stage / FIXED_OVERFLOW_FILENAME,
        )
        shutil.copyfile(
            first / "pointer_manifest.json",
            self.private_stage / "pointer_manifest.json",
        )
        generated_audits = self.private_stage / "audits" / "generated"
        generated_audits.mkdir(parents=True)
        for filename in (
            "catalogue_validation.json",
            "exact_repacked_validation.json",
            "bank_budget_validation.json",
            "glyph_residue_validation.json",
            "runtime_text_read_validation.json",
        ):
            shutil.copyfile(first / filename, generated_audits / filename)
        shutil.copyfile(
            self.work
            / "french-non-regression"
            / "french_non_regression.json",
            generated_audits / "french_non_regression.json",
        )
        _copy_evidence_tree(
            self.inputs["audits_dir"], self.private_stage / "audits"
        )
        _copy_evidence_tree(
            self.inputs["mesen_logs_dir"], self.private_stage / "logs" / "mesen"
        )
        _copy_evidence_tree(self.logs, self.private_stage / "logs" / "python")
        if external_proof is not None:
            shutil.copyfile(
                external_proof,
                self.private_stage / "audits" / "external_patcher_proof.json",
            )

        for filename in (
            IPS_FILENAME,
            CHINESE_BPS_FILENAME,
            ENGLISH_BPS_FILENAME,
        ):
            shutil.copyfile(first / filename, self.dist_stage / filename)

        review_dir = self.dist_stage / "review"
        review_dir.mkdir()
        review_sources = {
            REVIEW_FILENAME: self.inputs["catalog"],
            "source_adjudications.csv": self.inputs["source_adjudications"],
            "pointer_variants.csv": self.inputs["pointer_variants"],
            "storage_overlaps.csv": self.inputs["storage_overlaps"],
            "neutral_glyph_records.csv": self.inputs["neutral_glyphs"],
        }
        for filename, source in review_sources.items():
            shutil.copyfile(source, review_dir / filename)

        for filename, contents in _documentation(
            target_hash,
            external_patcher_status=self.external_status,
        ).items():
            (self.dist_stage / filename).write_text(
                contents,
                encoding="utf-8",
                newline="\n",
            )

        patch_records = {
            filename: manifest_record(
                file_record(first / filename, filename)
            )
            for filename in (
                IPS_FILENAME,
                CHINESE_BPS_FILENAME,
                ENGLISH_BPS_FILENAME,
            )
        }
        manifest: dict[str, object] = {
            "schema": "pokemon-yellow-nes-english-release/v1",
            "result": "PASS",
            "version": VERSION,
            "source_revision": self.revision,
            "local_only": True,
            "patch_only_distribution": True,
            "double_build_deterministic": True,
            "deterministic_artifacts": dict(deterministic_hashes),
            "catalogue": {
                **self.catalogue_summary.as_dict(),
                "sha256": sha256_file(self.inputs["catalog"]),
            },
            "inputs": self._input_manifest(),
            "target": {
                "filename": ROM_FILENAME,
                "size": target.stat().st_size,
                "sha256": target_hash,
                "included_in_dist": False,
            },
            "patches": patch_records,
            "patch_roundtrips": {
                "internal_ips": "PASS",
                "internal_bps_chinese": "PASS",
                "internal_bps_english_2015": "PASS",
                "external_patcher_matrix": self.external_status,
            },
            "validation_limits": dict(VALIDATION_LIMITS),
            "mesen_runtime": self.mesen_summary,
            "french_non_regression": self.french_non_regression,
            "steps": self.steps,
            "private_outputs": tree_manifest(
                self.private_stage,
                excluded_names=frozenset({"release_manifest.json", "SHA256SUMS"}),
            ),
            "dist_outputs": tree_manifest(
                self.dist_stage,
                excluded_names=frozenset({"release_manifest.json", "SHA256SUMS"}),
            ),
        }
        _write_json(self.private_stage / "release_manifest.json", manifest)
        _write_json(self.dist_stage / "release_manifest.json", manifest)
        write_sha256sums(self.private_stage)
        write_sha256sums(self.dist_stage)
        assert_no_complete_images(self.dist_stage)
        assert_portable_text_tree(self.dist_stage)

    def build(self) -> None:
        published = False
        try:
            self.prepare_inputs()
            self.verify_french_non_regression()
            for run_directory in self.run_dirs:
                self.build_once(run_directory)
            self.mesen_summary = validate_mesen_evidence(
                self.inputs["mesen_logs_dir"],
                sha256_file(self.run_dirs[0] / ROM_FILENAME),
            )
            deterministic_hashes = self.compare_builds()
            external_proof = self.run_external_patchers()
            self.assert_inputs_unchanged()
            self.stage_release(deterministic_hashes, external_proof)
            self.assert_inputs_unchanged()
            publish_transactionally(
                self.private_stage,
                self.private_destination,
                self.dist_stage,
                self.dist_destination,
            )
            published = True
        finally:
            shutil.rmtree(self.work, ignore_errors=True)
            if not published:
                shutil.rmtree(self.private_stage, ignore_errors=True)
                shutil.rmtree(self.dist_stage, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--chinese-rom", type=Path, default=DEFAULT_CHINESE_ROM)
    parser.add_argument(
        "--english-2015-rom", type=Path, default=DEFAULT_ENGLISH_2015_ROM
    )
    parser.add_argument("--yellow-rom", type=Path, default=DEFAULT_YELLOW_ROM)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--source-adjudications",
        type=Path,
        default=DEFAULT_SOURCE_ADJUDICATIONS,
    )
    parser.add_argument(
        "--pointer-variants", type=Path, default=DEFAULT_POINTER_VARIANTS
    )
    parser.add_argument(
        "--storage-overlaps", type=Path, default=DEFAULT_STORAGE_OVERLAPS
    )
    parser.add_argument(
        "--neutral-glyphs", type=Path, default=DEFAULT_NEUTRAL_GLYPHS
    )
    parser.add_argument(
        "--bank-budget-policy",
        type=Path,
        default=DEFAULT_BANK_BUDGET_POLICY,
    )
    parser.add_argument(
        "--pointer-inventory", type=Path, default=DEFAULT_POINTER_INVENTORY
    )
    parser.add_argument("--audits-dir", type=Path, default=DEFAULT_AUDITS_DIR)
    parser.add_argument(
        "--mesen-logs-dir", type=Path, default=DEFAULT_MESEN_LOGS_DIR
    )
    parser.add_argument("--private-dir", type=Path, default=DEFAULT_PRIVATE_DIR)
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST_DIR)
    parser.add_argument("--lunar-ips-exe", type=Path)
    parser.add_argument("--floating-ips-exe", type=Path)
    parser.add_argument("--floating-ips-archive", type=Path)
    parser.add_argument(
        "--external-verified-utc",
        help="horodatage reproductible YYYY-MM-DDTHH:MM:SSZ",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        builder = EnglishReleaseBuilder(args)
        builder.build()
    except (EnglishReleaseError, OSError, subprocess.SubprocessError) as exc:
        print(f"English release build: FAILED\n- {exc}", file=sys.stderr)
        return 1
    target = builder.private_destination / ROM_FILENAME
    print("Build release EN: PASS")
    print(f"- ROM privée: {builder.private_destination}")
    print(f"- Bundle patch-only: {builder.dist_destination}")
    print(f"- SHA-256 cible: {sha256_file(target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
