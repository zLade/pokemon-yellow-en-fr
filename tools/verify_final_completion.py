#!/usr/bin/env python3
"""Cross-check every final translation, release and runtime deliverable.

This is deliberately a post-release gate.  It ties together evidence that is
otherwise validated by separate tools: the deterministic release, exhaustive
dialogue table, creator cameos, review workbook,
Mesen runs and CHR catalogue.  Physical mapper-163 hardware remains an
explicit external validation and is never inferred from emulator results.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROM_ROOT = Path(__file__).resolve().parents[1]
if str(ROM_ROOT) not in sys.path:
    sys.path.insert(0, str(ROM_ROOT))

from tools.verify_mesen_route1_matrix import build_matrix_report
from tools.verify_mesen_route1_uninitialized import (
    build_report as build_uninitialized_report,
)
from tools.verify_mesen_battery_corruption import verify_run as verify_battery_run


SCHEMA = "pokemon-yellow-nes-final-completion/v1"
FINAL_ROM_SHA256 = (
    "1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b"
)
FINAL_RELEASE_DIR = Path("build/release-2026-08-09-final-v2")
EXPECTED_DIALOGUE_HEADER = [
    "id",
    "cle_stable",
    "categorie",
    "offset_ou_pointeur",
    "ligne_script",
    "layout",
    "intervenant",
    "texte_francais",
    "texte_chinois_source",
    "traduction_anglaise_rom_anglaise",
    "confiance_alignement",
    "historique_traduction",
    "naturalise",
    "corrige_d_apres_le_chinois",
    "votre_verdict",
    "votre_commentaire",
]
EXPECTED_CAMEOS = Counter(
    {
        "Kameiyu": 10,
        "Beibei": 2,
        "Xiao Li": 2,
        "Xiaohong": 1,
        "Wei Cunfu": 1,
        "BOSS": 1,
    }
)
CORE_MANIFEST = Path(
    "build/runtime-proof-final-1fefecbf-core-normal/"
    "run-20260809T163735Z-ba4e9771/regression_suite_manifest.txt"
)
ROUTE1_DIR = Path("build/runtime-proof-final-1fefecbf-route1")
EXPECTED_RUNTIME_PYTHON_TESTS = 399
EXPECTED_RUNTIME_PYTHON_MODULES = 50
CHR_DIR = Path("build/chr-catalog/current-1fefecbf")
EXTERNAL_PATCHER_PROOF = Path("build/external-patcher-proof.json")
UNINITIALIZED_DIAGNOSTIC = Path(
    "build/runtime-proof-final-1fefecbf-uninitialized-dendy/"
    "uninitialized_diagnostic.json"
)
BATTERY_CORRUPTION_DIRS = {
    "Dendy": Path("build/runtime-proof-final-1fefecbf-battery-dendy"),
    "Ntsc": Path("build/runtime-proof-final-1fefecbf-battery-ntsc"),
    "Pal": Path("build/runtime-proof-final-1fefecbf-battery-pal"),
}

EXPECTED_EXTERNAL_PATCH_TOOLS = {
    "lunar_ips": {
        "version": "1.03 x64",
        "sha256": "9e67a1f3105092bda45cf02ac638e2d014e9a1aa28cc9a78c801881eb72f82be",
    },
    "floating_ips": {
        "version": "v198 Windows",
        "source": "https://github.com/Alcaro/Flips/releases/tag/v198",
        "archive_sha256": "802bfb315dca08a2f765dd6864472ecbb2b482681045c573d5e4b657b8e5295d",
        "executable_sha256": "ca6b364ccb23ab83ff0f4458f589eac001e7baf74315decde73c878a8eb519fd",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root JSON value must be an object")
    return value


def record(name: str, errors: Iterable[str], **evidence: Any) -> dict[str, Any]:
    error_list = list(errors)
    return {
        "name": name,
        "result": "PASS" if not error_list else "FAIL",
        "evidence": evidence,
        "errors": error_list,
    }


def _read_dialogues(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    return header, rows


def validate_release(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    release_dir = root / FINAL_RELEASE_DIR
    manifest_path = release_dir / "release_manifest.json"
    try:
        manifest = load_json(manifest_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return record("deterministic_release", [f"cannot read manifest: {exc}"])

    for key in (
        "canonical_csv_regenerated",
        "current_artifacts_reproduced",
        "double_build_deterministic",
    ):
        if manifest.get(key) is not True:
            errors.append(f"release manifest {key} is not true")
    if manifest.get("result") != "PASS":
        errors.append("release manifest result is not PASS")

    expected = manifest.get("deterministic_artifacts")
    if not isinstance(expected, dict) or not expected:
        errors.append("deterministic_artifacts is missing")
        expected = {}
    checked_artifacts = 0
    for filename, wanted_hash in sorted(expected.items()):
        if not isinstance(filename, str) or not isinstance(wanted_hash, str):
            errors.append("invalid deterministic_artifacts entry")
            continue
        for label, path in (
            ("root", root / filename),
            ("release", release_dir / filename),
        ):
            try:
                actual = sha256_file(path)
            except OSError as exc:
                errors.append(f"{label} {filename}: cannot hash: {exc}")
            else:
                if actual != wanted_hash:
                    errors.append(
                        f"{label} {filename}: {actual} != {wanted_hash}"
                    )
        checked_artifacts += 1

    inputs = manifest.get("inputs")
    input_records_checked = 0
    if not isinstance(inputs, dict) or not inputs:
        errors.append("release manifest inputs are missing")
        inputs = {}
    for label, input_record in sorted(inputs.items()):
        if not isinstance(label, str) or not isinstance(input_record, dict):
            errors.append("invalid release input record")
            continue
        recorded_path = input_record.get("path")
        recorded_hash = input_record.get("sha256")
        recorded_size = input_record.get("size")
        if (
            not isinstance(recorded_path, str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(recorded_hash))
            or not isinstance(recorded_size, int)
        ):
            errors.append(f"release input {label}: incomplete record")
            continue
        candidate = Path(recorded_path)
        if candidate.is_absolute():
            current_input = candidate
        else:
            current_input = (root / candidate).resolve()
            try:
                current_input.relative_to(root.resolve())
            except ValueError:
                errors.append(f"release input {label}: path escapes project root")
                continue
        try:
            current_hash = sha256_file(current_input)
            current_size = current_input.stat().st_size
        except OSError as exc:
            errors.append(f"release input {label}: cannot verify: {exc}")
            continue
        if current_hash != recorded_hash or current_size != recorded_size:
            errors.append(f"release input {label}: current source differs from manifest")
        input_records_checked += 1

    canonical = inputs.get("canonical_csv") if isinstance(inputs, dict) else None
    canonical_hash = canonical.get("sha256") if isinstance(canonical, dict) else None
    if not isinstance(canonical_hash, str):
        errors.append("canonical CSV hash missing from release manifest")
    else:
        for path in (root / "traduction_base.csv", release_dir / "traduction_base.csv"):
            try:
                actual = sha256_file(path)
            except OSError as exc:
                errors.append(f"cannot hash {path}: {exc}")
            else:
                if actual != canonical_hash:
                    errors.append(f"{path}: stale canonical CSV")

    sums_path = release_dir / "SHA256SUMS"
    sums_checked = 0
    try:
        lines = sums_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read SHA256SUMS: {exc}")
        lines = []
    for line in lines:
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            errors.append(f"malformed SHA256SUMS line: {line!r}")
            continue
        wanted, relative = match.groups()
        try:
            actual = sha256_file(release_dir / relative)
        except OSError as exc:
            errors.append(f"SHA256SUMS {relative}: {exc}")
        else:
            if actual != wanted:
                errors.append(f"SHA256SUMS mismatch: {relative}")
        sums_checked += 1

    try:
        final_rom_hash = sha256_file(root / "Pokemon_Jaune_FR_repacked_title.nes")
    except OSError as exc:
        final_rom_hash = None
        errors.append(f"cannot hash final ROM: {exc}")
    if final_rom_hash != FINAL_ROM_SHA256:
        errors.append("final ROM is not the certified 1fefecbf release")

    return record(
        "deterministic_release",
        errors,
        final_rom_sha256=final_rom_hash,
        artifacts_checked=checked_artifacts,
        inputs_checked=input_records_checked,
        sha256sums_checked=sums_checked,
        manifest=str(manifest_path.relative_to(root)),
    )


def validate_external_patchers(root: Path) -> dict[str, Any]:
    """Verify the independently produced IPS/BPS round-trip evidence."""

    errors: list[str] = []
    path = root / EXTERNAL_PATCHER_PROOF
    try:
        proof = load_json(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return record("external_patchers", [f"cannot read proof: {exc}"])

    if proof.get("schema") != "pokemon-yellow-nes-external-patcher-proof/v1":
        errors.append("unexpected external patcher proof schema")
    if proof.get("result") != "PASS":
        errors.append("external patcher proof is not PASS")

    target = proof.get("target")
    if not isinstance(target, dict):
        errors.append("external patcher target is missing")
        target = {}
    if target.get("path") != "Pokemon_Jaune_FR_repacked_title.nes":
        errors.append("external patcher target path is wrong")
    if target.get("sha256") != FINAL_ROM_SHA256:
        errors.append("external patcher target hash is wrong")
    try:
        actual_target = sha256_file(root / "Pokemon_Jaune_FR_repacked_title.nes")
    except OSError as exc:
        actual_target = None
        errors.append(f"cannot hash external patcher target: {exc}")
    if actual_target != FINAL_ROM_SHA256:
        errors.append("current target ROM differs from external patcher proof")

    tools = proof.get("tools")
    if not isinstance(tools, dict):
        errors.append("external patcher tool metadata is missing")
        tools = {}
    for tool_name, expected in EXPECTED_EXTERNAL_PATCH_TOOLS.items():
        actual = tools.get(tool_name)
        if not isinstance(actual, dict):
            errors.append(f"external patcher metadata missing: {tool_name}")
            continue
        for key, value in expected.items():
            if actual.get(key) != value:
                errors.append(f"external patcher {tool_name} {key} is not pinned")

    expected_rows = {
        (
            "IPS",
            "lunar_ips",
            "yellow.nes",
            "Pokemon_Jaune_FR_repacked_title.ips",
        ),
        (
            "BPS",
            "floating_ips",
            "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes",
            "Pokemon_Jaune_FR_repacked_title_from_chinese.bps",
        ),
        (
            "BPS",
            "floating_ips",
            "Pokemon Yellow English 9-23-2015.nes",
            "Pokemon_Jaune_FR_repacked_title_from_english.bps",
        ),
    }
    roundtrips = proof.get("roundtrips")
    if not isinstance(roundtrips, list):
        errors.append("external patcher roundtrips are missing")
        roundtrips = []
    observed_rows: set[tuple[str, str, str, str]] = set()
    for row in roundtrips:
        if not isinstance(row, dict):
            errors.append("malformed external patcher roundtrip")
            continue
        key = (
            str(row.get("format", "")),
            str(row.get("tool", "")),
            str(row.get("base", "")),
            str(row.get("patch", "")),
        )
        if key in observed_rows:
            errors.append(f"duplicate external patcher roundtrip: {key}")
        observed_rows.add(key)
        if row.get("result") != "PASS":
            errors.append(f"external patcher roundtrip is not PASS: {key}")
        if row.get("output_sha256") != FINAL_ROM_SHA256:
            errors.append(f"external patcher output hash is wrong: {key}")
        for kind, filename, hash_key in (
            ("base", key[2], "base_sha256"),
            ("patch", key[3], "patch_sha256"),
        ):
            try:
                actual = sha256_file(root / filename)
            except OSError as exc:
                errors.append(f"cannot hash {kind} {filename}: {exc}")
            else:
                if row.get(hash_key) != actual:
                    errors.append(f"external proof {kind} hash differs: {filename}")
    if observed_rows != expected_rows:
        errors.append("external patcher proof is not the exact IPS + two BPS matrix")

    return record(
        "external_patchers",
        errors,
        path=str(EXTERNAL_PATCHER_PROOF),
        proof_sha256=sha256_file(path),
        roundtrips=len(roundtrips),
        formats=["IPS", "BPS"],
    )


def validate_dialogues(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    path = root / "LISTE_EXHAUSTIVE_DIALOGUES.csv"
    errors: list[str] = []
    try:
        header, rows = _read_dialogues(path)
    except (OSError, UnicodeError, csv.Error) as exc:
        return record("exhaustive_dialogues", [f"cannot read CSV: {exc}"]), []

    if header != EXPECTED_DIALOGUE_HEADER:
        errors.append("unexpected dialogue CSV header")
    ids = [row.get("id", "") for row in rows]
    expected_ids = [f"D{index:04d}" for index in range(1, 1056)]
    if ids != expected_ids:
        errors.append("dialogue IDs are not the exact D0001..D1055 sequence")
    keys = [row.get("cle_stable", "") for row in rows]
    if len(set(keys)) != len(keys) or any(not key for key in keys):
        errors.append("stable dialogue keys are missing or duplicated")
    for field in (
        "texte_francais",
        "texte_chinois_source",
        "traduction_anglaise_rom_anglaise",
    ):
        missing = [row.get("id", "?") for row in rows if not row.get(field, "").strip()]
        if missing:
            errors.append(f"{field}: {len(missing)} empty value(s)")
    confidence = Counter(row.get("confiance_alignement", "") for row in rows)
    if confidence != Counter({"high": 970, "source directe": 85}):
        errors.append(f"unexpected confidence distribution: {dict(confidence)}")
    for field in ("naturalise", "corrige_d_apres_le_chinois"):
        if any(row.get(field) != "oui" for row in rows):
            errors.append(f"not every dialogue has {field}=oui")
    categories = Counter(row.get("categorie", "") for row in rows)
    if categories != Counter(
        {"Dialogue en jeu": 967, "Dialogue restauré": 85, "Introduction": 3}
    ):
        errors.append(f"unexpected category distribution: {dict(categories)}")

    return (
        record(
            "exhaustive_dialogues",
            errors,
            path=str(path.relative_to(root)),
            sha256=sha256_file(path),
            dialogues=len(rows),
            confidence=dict(sorted(confidence.items())),
            categories=dict(sorted(categories.items())),
        ),
        rows,
    )


def validate_cameos(root: Path, dialogues: list[dict[str, str]]) -> dict[str, Any]:
    errors: list[str] = []
    path = root / "build/chinese-english-fidelity/extraction/creator_cameo_dialogues.csv"
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            cameos = list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error) as exc:
        return record("creator_cameos", [f"cannot read cameo CSV: {exc}"])

    counts = Counter(row.get("createur_ou_cameo", "") for row in cameos)
    if counts != EXPECTED_CAMEOS:
        errors.append(f"unexpected cameo distribution: {dict(counts)}")
    index = {(row.get("id"), row.get("cle_stable")): row for row in dialogues}
    for cameo in cameos:
        key = (cameo.get("id"), cameo.get("cle_stable"))
        dialogue = index.get(key)
        if dialogue is None:
            errors.append(f"cameo not found in exhaustive CSV: {key}")
            continue
        if cameo.get("texte_chinois_source") != dialogue.get("texte_chinois_source"):
            errors.append(f"cameo Chinese source differs from exhaustive CSV: {key}")
        if cameo.get("texte_francais_actuel") != dialogue.get("texte_francais"):
            errors.append(f"cameo French text differs from exhaustive CSV: {key}")
    beibei = sorted(row.get("id") for row in cameos if row.get("createur_ou_cameo") == "Beibei")
    if beibei != ["D0064", "D0632"]:
        errors.append(f"Beibei IDs are not D0064 and D0632: {beibei}")

    return record(
        "creator_cameos",
        errors,
        path=str(path.relative_to(root)),
        cameos=len(cameos),
        counts=dict(sorted(counts.items())),
        beibei_ids=beibei,
    )


def validate_fidelity_derivatives(root: Path) -> dict[str, Any]:
    """Reconstruct every French-dependent Chinese fidelity derivative."""

    command = [
        sys.executable,
        str(root / "tools/refresh_chinese_fidelity_derivatives.py"),
        "--check",
    ]
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(
            "fidelity derivative refresh --check failed: "
            + (completed.stderr or completed.stdout).strip()
        )
    summary_path = (
        root / "build/chinese-english-fidelity/extraction/summary.json"
    )
    try:
        summary = load_json(summary_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return record(
            "chinese_fidelity_derivatives",
            [*errors, f"cannot read fidelity summary: {exc}"],
        )

    expected = {
        "source_dialogues_removed_from_english_inventory": 80,
        "source_dialogue_pointers_invalidated_in_english": 80,
        "source_dialogue_pointers_restored_in_french": 80,
        "source_dialogues_absent_from_english_and_french": 0,
        "restored_chinese_dialogues_inventory": 85,
        "restored_payloads_verified_in_french_rom": 85,
        "creator_cameo_dialogues": 17,
        "review_dialogue_rows": 1055,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"fidelity summary {key} is not {value}")
    if summary.get("french_rom_sha256") != FINAL_ROM_SHA256:
        errors.append("fidelity derivatives target the wrong French ROM")
    if summary.get("provenance_mode") != "derived_refresh_without_hzk_reextraction":
        errors.append("fidelity derivative provenance mode is not explicit")
    provenance = summary.get("provenance")
    if not isinstance(provenance, dict) or (
        provenance.get("immutable_source_reextracted") is not False
        or provenance.get("hzk16_input_used_for_refresh") is not False
    ):
        errors.append("fidelity derivative HZK16 qualification is incomplete")
    derived = summary.get("derived_artifacts_sha256")
    if not isinstance(derived, dict) or len(derived) != 12:
        errors.append("fidelity derivative hash inventory is not exactly 12 files")

    return record(
        "chinese_fidelity_derivatives",
        errors,
        path=str(summary_path.relative_to(root)),
        sha256=sha256_file(summary_path),
        derived_files=len(derived) if isinstance(derived, dict) else None,
        removed_from_english=summary.get(
            "source_dialogues_removed_from_english_inventory"
        ),
        restored_pointer_slots=summary.get(
            "source_dialogue_pointers_restored_in_french"
        ),
        restored_payloads=summary.get(
            "restored_payloads_verified_in_french_rom"
        ),
        provenance_mode=summary.get("provenance_mode"),
    )


def validate_pointer_manifest(root: Path) -> dict[str, Any]:
    """Validate pointer payloads and regenerate their complete owner set."""

    manifest_path = root / FINAL_RELEASE_DIR / "audits/pointer_manifest.json"
    command = [
        sys.executable,
        str(root / "tools/pointer_manifest.py"),
        "validate",
        "--rom",
        str(root / "Pokemon_Jaune_FR_repacked_title.nes"),
        "--manifest",
        str(manifest_path),
        "--csv",
        str(root / "traduction_base.csv"),
        "--input-rom",
        str(root / "Pokemon Yellow English 9-23-2015.nes"),
    ]
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(
            "pointer manifest validation failed: "
            + (completed.stderr or completed.stdout).strip()
        )
    try:
        manifest = load_json(manifest_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return record("pointer_manifest", [*errors, f"cannot read manifest: {exc}"])

    summary = manifest.get("summary")
    commitment = manifest.get("canonical_inventory")
    if manifest.get("schema") != "pokemon-yellow-nes-pointer-manifest/v2":
        errors.append("pointer manifest is not schema v2")
    expected_summary = {
        "allocated_payloads": 1904,
        "pointer_records": 1912,
        "unique_references": 1912,
        "restorations": 85,
    }
    if not isinstance(summary, dict):
        errors.append("pointer manifest summary is missing")
        summary = {}
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            errors.append(f"pointer manifest {key} is not {value}")
    if not isinstance(commitment, dict) or (
        commitment.get("derivation") != "translation_csv_and_canonical_base_rom"
        or commitment.get("entries") != 1912
        or not re.fullmatch(r"[0-9a-f]{64}", str(commitment.get("sha256", "")))
    ):
        errors.append("canonical pointer inventory commitment is incomplete")

    return record(
        "pointer_manifest",
        errors,
        path=str(manifest_path.relative_to(root)),
        sha256=sha256_file(manifest_path) if manifest_path.exists() else None,
        pointer_records=summary.get("pointer_records"),
        commitment_sha256=(commitment or {}).get("sha256")
        if isinstance(commitment, dict)
        else None,
    )


def validate_xlsx(root: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(root / "tools/verify_dialogue_review_xlsx.py"),
        "--xlsx",
        str(root / "build/LISTE_EXHAUSTIVE_DIALOGUES.xlsx"),
        "--csv",
        str(root / "LISTE_EXHAUSTIVE_DIALOGUES.csv"),
        "--strict",
        "--json",
    ]
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
    errors: list[str] = []
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        report = {}
        errors.append(f"XLSX verifier did not return JSON: {exc}")
    if completed.returncode != 0:
        errors.append(f"XLSX verifier exited {completed.returncode}")
    if not isinstance(report, dict) or report.get("ok") is not True or report.get("strict") is not True:
        errors.append("strict XLSX verification did not pass")
    if isinstance(report, dict):
        errors.extend(str(error) for error in report.get("errors", []))
    path = root / "build/LISTE_EXHAUSTIVE_DIALOGUES.xlsx"
    return record(
        "review_xlsx",
        errors,
        path=str(path.relative_to(root)),
        sha256=sha256_file(path) if path.exists() else None,
        checks=len(report.get("checks", [])) if isinstance(report, dict) else 0,
    )


def _manifest_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.lstrip("\ufeff").strip()] = value.strip()
    return fields


def validate_runtime(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    core_path = root / CORE_MANIFEST
    try:
        core_text = core_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return record("mesen_runtime", [f"cannot read core manifest: {exc}"])
    fields = _manifest_fields(core_text)
    if fields.get("ROM SHA-256") != FINAL_ROM_SHA256:
        errors.append("core Mesen manifest targets the wrong ROM")
    if fields.get("Strict hardware profile") != "True":
        errors.append("core Mesen manifest is not strict hardware")
    if fields.get("Full NES debug-stop profile") != "True":
        errors.append("core Mesen manifest is not FullDebug")
    if fields.get("Bootstrap completion gate") != "False":
        errors.append("core Mesen manifest is still a bootstrap run")
    if fields.get("Result") != "PASS":
        errors.append("core Mesen suite is not PASS")
    try:
        python_modules = int(fields.get("Python test modules discovered", ""))
    except ValueError:
        python_modules = -1
    if python_modules != EXPECTED_RUNTIME_PYTHON_MODULES:
        errors.append(
            "core Mesen Python module count is not "
            f"{EXPECTED_RUNTIME_PYTHON_MODULES}: {python_modules}"
        )
    try:
        executed = int(fields.get("Executed steps", ""))
    except ValueError:
        executed = -1
    steps = re.findall(r"^Step \d+: (PASS|FAIL) \|", core_text, re.MULTILINE)
    if executed != 45 or len(steps) != 45 or any(step != "PASS" for step in steps):
        errors.append(f"core Mesen steps are not exactly 45/45 PASS: {executed}/{len(steps)}")

    python_log_path = (
        core_path.parent
        / "static"
        / "04a-full-python-test-suite.log.stderr.txt"
    )
    try:
        python_log = python_log_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        python_log = ""
        errors.append(f"cannot read core Python-suite log: {exc}")
    match = re.search(r"^Ran (\d+) tests in [0-9.]+s$", python_log, re.MULTILINE)
    python_tests = int(match.group(1)) if match else -1
    terminal_lines = [line.strip() for line in python_log.splitlines() if line.strip()]
    python_terminal = terminal_lines[-1] if terminal_lines else ""
    if python_tests != EXPECTED_RUNTIME_PYTHON_TESTS:
        errors.append(
            "core Mesen Python suite did not run exactly "
            f"{EXPECTED_RUNTIME_PYTHON_TESTS} tests: {python_tests}"
        )
    if python_terminal != "OK":
        errors.append(
            "core Mesen Python suite is not an unskipped terminal OK: "
            f"{python_terminal!r}"
        )

    campaign_frames: dict[str, int] = {}
    for slug, region in (("dendy", "Dendy"), ("ntsc", "Ntsc"), ("pal", "Pal")):
        path = core_path.parent / "mesen" / slug / "07-campaign-prototype/mesen_run_manifest.txt"
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read {region} campaign manifest: {exc}")
            continue
        manifest = _manifest_fields(text)
        terminal = manifest.get("Mesen terminal output", "")
        required_tokens = (
            "POKEMON_CAMPAIGN_PROTOTYPE_PASS",
            f"region={region}",
            "endpoint=outside_lab_stable",
            "mode=controller",
            "writes_to_game=0",
        )
        if (
            manifest.get("Result") != "PASS"
            or manifest.get("ROM SHA-256 before") != FINAL_ROM_SHA256
            or manifest.get("ROM SHA-256 after") != FINAL_ROM_SHA256
            or manifest.get("Strict hardware profile") != "True"
            or manifest.get("Full NES debug-stop profile") != "True"
            or any(token not in terminal.split() for token in required_tokens)
        ):
            errors.append(f"{region} controller-only campaign evidence failed")
        match = re.search(r"\bframes=(\d+)\b", terminal)
        if match:
            campaign_frames[region] = int(match.group(1))

    route_report = build_matrix_report(root / ROUTE1_DIR)
    try:
        stored_route = load_json(root / ROUTE1_DIR / "route1_matrix.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        stored_route = None
        errors.append(f"cannot read stored Route 1 matrix: {exc}")
    if route_report.get("result") != "PASS" or route_report.get("summary", {}).get(
        "regions_passed"
    ) != 3:
        errors.append("Route 1 matrix does not pass 3/3 regions")
    if stored_route != route_report:
        errors.append("stored Route 1 matrix is stale")

    return record(
        "mesen_runtime",
        errors,
        core_manifest=str(CORE_MANIFEST),
        core_steps=executed,
        bootstrap_completion_gate=fields.get("Bootstrap completion gate"),
        python_tests=python_tests,
        python_modules=python_modules,
        python_terminal=python_terminal,
        campaign_frames=campaign_frames,
        route1_regions=route_report.get("summary", {}).get("regions_passed"),
        route1_screenshots=route_report.get("summary", {}).get("screenshots"),
    )


def validate_uninitialized_read(root: Path) -> dict[str, Any]:
    """Bind the qualified uninitialized-read diagnostic to its live evidence.

    Passing this check deliberately does *not* mean that the engine quirk is
    harmless.  It means that the actual CPU reads were reproduced, the
    offending routine is byte-identical in the source and translated ROMs,
    and the remaining uncertainty is stated without overclaiming.
    """

    errors: list[str] = []
    path = root / UNINITIALIZED_DIAGNOSTIC
    try:
        stored = load_json(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return record(
            "uninitialized_read_diagnostic",
            [f"cannot read stored diagnostic: {exc}"],
        )

    rebuilt = build_uninitialized_report(root)
    if stored != rebuilt:
        errors.append("stored uninitialized-read diagnostic is stale")
    if rebuilt.get("result") != "PASS":
        errors.append("uninitialized-read diagnostic does not pass")
    if rebuilt.get("classification") != "inherited_source_engine_quirk_unresolved":
        errors.append("uninitialized-read classification is not the unresolved source quirk")
    if rebuilt.get("safety_conclusion") != "harmlessness_not_proven":
        errors.append("uninitialized-read diagnostic overclaims harmlessness")

    claims = rebuilt.get("claims")
    if not isinstance(claims, dict):
        errors.append("uninitialized-read claims are missing")
        claims = {}
    expected_claims = {
        "routine_identical_in_chinese_english_french": True,
        "runtime_cpu_read_confirmed": True,
        "offending_routine_introduced_by_french_translation": False,
        "same_trigger_observed_in_chinese_runtime": False,
        "translation_trigger_regression_excluded": False,
        "harmlessness_proven": False,
    }
    for key, expected in expected_claims.items():
        if claims.get(key) is not expected:
            errors.append(f"uninitialized-read claim {key} is not {expected}")

    qualification = rebuilt.get("qualification")
    if not isinstance(qualification, dict) or (
        qualification.get("actual_cpu_reads") is not True
        or qualification.get("probe_generated_reads") is not False
        or qualification.get("unresolved") is not True
        or qualification.get("inherited_scope")
        != "offending_engine_routine_bytes"
    ):
        errors.append("uninitialized-read qualification is incomplete")

    runtime = rebuilt.get("runtime")
    regional = rebuilt.get("regional_full_debug")
    return record(
        "uninitialized_read_diagnostic",
        errors,
        path=str(UNINITIALIZED_DIAGNOSTIC),
        sha256=sha256_file(path),
        classification=rebuilt.get("classification"),
        safety_conclusion=rebuilt.get("safety_conclusion"),
        actual_cpu_reads=(qualification or {}).get("actual_cpu_reads")
        if isinstance(qualification, dict)
        else None,
        diagnostic_frame=(runtime or {}).get("absolute_frame")
        if isinstance(runtime, dict)
        else None,
        regional_full_debug=sorted(regional)
        if isinstance(regional, dict)
        else [],
    )


def validate_battery_corruption(root: Path) -> dict[str, Any]:
    """Rebuild the three regional one-byte save-corruption reports."""

    errors: list[str] = []
    regions: dict[str, Any] = {}
    rom_path = root / "Pokemon_Jaune_FR_repacked_title.nes"
    for region, relative in BATTERY_CORRUPTION_DIRS.items():
        path = root / relative / "verification.json"
        try:
            stored = load_json(path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{region}: cannot read battery report: {exc}")
            continue
        run_directory = stored.get("run_directory")
        if not isinstance(run_directory, str):
            errors.append(f"{region}: battery run directory is missing")
            continue
        rebuilt, rebuilt_errors = verify_battery_run(
            root / run_directory,
            rom_path,
        )
        if rebuilt_errors or rebuilt.get("result") != "PASS":
            errors.extend(f"{region}: {error}" for error in rebuilt_errors)
        if stored != rebuilt:
            errors.append(f"{region}: stored battery report is stale")
        if stored.get("region") != region:
            errors.append(f"{region}: battery region label differs")
        if stored.get("rom_sha256") != FINAL_ROM_SHA256:
            errors.append(f"{region}: battery proof targets the wrong ROM")
        if stored.get("strict_hardware") is not True or stored.get(
            "full_debug_stop"
        ) is not True:
            errors.append(f"{region}: battery proof is not strict FullDebug")
        observations = stored.get("observations")
        if not isinstance(observations, dict) or (
            observations.get("primary_corruption")
            != "restored_from_backup_and_resumed"
            or observations.get("backup_corruption")
            != "rejected_to_new_game_fallback"
            or observations.get("memory_injection") is not False
        ):
            errors.append(f"{region}: battery outcomes are incomplete")
        limits = stored.get("scope_limits")
        if not isinstance(limits, list) or not any(
            "physical mapper-163 hardware not tested" in str(limit)
            for limit in limits
        ):
            errors.append(f"{region}: battery scope limits are incomplete")
        regions[region] = {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
            "run_directory": run_directory,
            "artifacts": len(stored.get("artifact_hashes", {}))
            if isinstance(stored.get("artifact_hashes"), dict)
            else None,
        }

    if set(regions) != set(BATTERY_CORRUPTION_DIRS):
        errors.append("battery corruption matrix is not exactly Dendy/Ntsc/Pal")
    return record(
        "battery_corruption_runtime",
        errors,
        regions=regions,
        corruption_cases_per_region=2,
        changed_bytes_per_case=1,
        memory_injection=False,
        physical_mapper163="NON_TESTE",
    )


def validate_chr(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    reports: dict[str, dict[str, Any]] = {}
    for filename in ("verify.json", "roundtrip.json"):
        path = root / CHR_DIR / filename
        try:
            report_json = load_json(path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read {filename}: {exc}")
            continue
        reports[filename] = report_json
        if report_json.get("result") != "PASS":
            errors.append(f"{filename}: result is not PASS")
        if report_json.get("output_sha256") != FINAL_ROM_SHA256:
            errors.append(f"{filename}: output is not the final ROM")
        if report_json.get("logical_changed_bytes") != 0:
            errors.append(f"{filename}: logical changes are not zero")
        if report_json.get("physical_changed_bytes") != 0:
            errors.append(f"{filename}: physical changes are not zero")
        if report_json.get("changed_ranges") != []:
            errors.append(f"{filename}: changed_ranges is not empty")
    if len(reports) == 2 and reports["verify.json"].get("manifest_sha256") != reports[
        "roundtrip.json"
    ].get("manifest_sha256"):
        errors.append("CHR verify and roundtrip use different manifests")
    assets = reports.get("verify.json", {}).get("assets", [])
    overlaps = reports.get("verify.json", {}).get("overlaps", [])
    return record(
        "chr_catalog",
        errors,
        directory=str(CHR_DIR),
        assets=len(assets) if isinstance(assets, list) else None,
        overlaps=len(overlaps) if isinstance(overlaps, list) else None,
        whitelist_bytes=reports.get("verify.json", {}).get("whitelist_bytes"),
        manifest_sha256=reports.get("verify.json", {}).get("manifest_sha256"),
    )


def validate_documentation(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "RAPPORT_RELEASE_2026-08-09.md",
        "MODE_EMPLOI_TRADUCTION.md",
        "CORRECTIONS_FIDELITE_CHINOISE.md",
        "DIALOGUES_CHINOIS_ABSENTS_ET_DIVERGENTS.md",
        "AUDIT_COHERENCE_GEN1_GEN2_FR.md",
        "CHECKLIST_TEST_MATERIEL_MAPPER163.md",
        "tools/campaign/STATUS_FR.md",
    )
    texts: dict[str, str] = {}
    for filename in required:
        path = root / filename
        try:
            texts[filename] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read {filename}: {exc}")
    for filename in required[:5]:
        if FINAL_ROM_SHA256 not in texts.get(filename, ""):
            errors.append(f"{filename} is not bound to the final ROM SHA-256")
    report_text = texts.get("RAPPORT_RELEASE_2026-08-09.md", "")
    for fragment in (
        "1 055 dialogues",
        "17 dialogues de caméo",
        "Beibei",
        "CT35 reçue !",
        "parcel_route_done=false",
        "NON TESTÉ",
    ):
        if fragment not in report_text:
            errors.append(f"release report misses required statement: {fragment}")
    checklist = texts.get("CHECKLIST_TEST_MATERIEL_MAPPER163.md", "")
    if checklist.count("NON TESTÉ") < 9 or "[x]" in checklist.lower():
        errors.append("physical-hardware checklist is not explicitly untested")
    campaign_status = texts.get("tools/campaign/STATUS_FR.md", "")
    if "État courant — 9 août 2026" not in campaign_status or FINAL_ROM_SHA256 not in campaign_status:
        errors.append("campaign status still lacks a current final-release section")

    return record(
        "documentation",
        errors,
        files=len(required),
        physical_mapper163_status="NON_TESTE",
        physical_mapper163_reason="aucune cartouche/console fournie",
    )


def build_report(root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(validate_release(root))
    checks.append(validate_external_patchers(root))
    dialogue_check, dialogues = validate_dialogues(root)
    checks.append(dialogue_check)
    checks.append(validate_cameos(root, dialogues))
    checks.append(validate_fidelity_derivatives(root))
    checks.append(validate_pointer_manifest(root))
    checks.append(validate_xlsx(root))
    checks.append(validate_runtime(root))
    checks.append(validate_uninitialized_read(root))
    checks.append(validate_battery_corruption(root))
    checks.append(validate_chr(root))
    checks.append(validate_documentation(root))
    failed = [check["name"] for check in checks if check["result"] != "PASS"]
    return {
        "schema": SCHEMA,
        "result": "PASS" if not failed else "FAIL",
        "final_rom_sha256": FINAL_ROM_SHA256,
        "checks": checks,
        "summary": {
            "checks_total": len(checks),
            "checks_passed": len(checks) - len(failed),
            "failed": failed,
            "local_completion": "PASS" if not failed else "FAIL",
            "physical_mapper163": "NON_TESTE",
        },
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    report = build_report(root)
    if args.output is not None:
        output = args.output if args.output.is_absolute() else root / args.output
        write_report(report, output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
