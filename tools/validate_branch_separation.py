#!/usr/bin/env python3
"""Validate the language-specific repository layout for the current branch."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

PROFILES = {
    "fr": {
        "required": (
            ".github/workflows/validate.yml",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            "NOTICE.md",
            "locales/fr-FR/manifest.json",
            "profiles/fr-release.json",
            "releases/fr/README.md",
            "releases/fr/2.0.1/README.md",
            "releases/fr/2.0.1/SHA256SUMS",
        ),
        "forbidden_prefixes": ("locales/en-US/", "releases/en/"),
        "forbidden_files": (
            "profiles/en-development.json",
            "tools/build_english_release.py",
        ),
    },
    "en": {
        "required": (
            ".github/workflows/validate.yml",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            "NOTICE.md",
            "README.md",
            "docs/en/README.md",
            "docs/en/BUILD_AND_RELEASE.md",
            "docs/en/INHERITED_FRENCH_INPUTS.md",
            "docs/en/MAPPER163_AND_MESEN.md",
            "docs/en/REPRODUCIBILITY.md",
            "docs/en/SOURCE_FIDELITY_AUDIT.md",
            "docs/en/TRANSLATION_POLICY.md",
            "docs/en/VALIDATION_STATUS.md",
            "locales/en-US/catalog.csv",
            "locales/en-US/ENGLISH_REVIEW_SHEET.csv",
            "locales/en-US/README.md",
            "releases/en/README.md",
            "releases/en/2.0.0/README.md",
            "releases/en/2.0.0/SHA256SUMS",
            "tools/build_english_release.py",
        ),
        "forbidden_prefixes": (
            "locales/fr-FR/",
            "releases/fr/",
            "dist/fr/",
        ),
        "forbidden_files": ("profiles/fr-release.json",),
        "forbidden_markdown": (
            "AUDIT_CHINESE_ENGLISH_FIDELITY.md",
            "AUDIT_COHERENCE_GEN1_GEN2_FR.md",
            "CHECKLIST_TEST_MATERIEL_MAPPER163.md",
            "CORRECTIONS_FIDELITE_CHINOISE.md",
            "DIALOGUES_CHINOIS_ABSENTS_ET_DIVERGENTS.md",
            "LISTE_EXHAUSTIVE_DIALOGUES.md",
            "MODE_EMPLOI_TRADUCTION.md",
            "RAPPORT_RELEASE_2026-08-09.md",
            "tools/MESEN_FRENCH_CHARSET_PROBE.md",
            "tools/campaign/EVIDENCE_OAK_LAB_FR.md",
            "tools/campaign/STATUS_FR.md",
        ),
    },
}

ROM_SUFFIXES = (".nes", ".gb", ".gbc", ".rom")


def tracked_files() -> set[str]:
    output = subprocess.check_output(("git", "ls-files", "-z"), cwd=ROOT)
    return {item.decode("utf-8") for item in output.split(b"\0") if item}


def validate(language: str, files: set[str]) -> list[str]:
    profile = PROFILES[language]
    failures: list[str] = []
    for path in profile["required"]:
        if path not in files:
            failures.append(f"required file missing: {path}")
    for prefix in profile["forbidden_prefixes"]:
        matches = sorted(path for path in files if path.startswith(prefix))
        failures.extend(f"foreign-language path tracked: {path}" for path in matches)
    for path in profile["forbidden_files"]:
        if path in files:
            failures.append(f"foreign-language file tracked: {path}")
    for path in profile.get("forbidden_markdown", ()):
        if path in files:
            failures.append(f"French-only documentation tracked: {path}")
    for path in sorted(files):
        if path.lower().endswith(ROM_SUFFIXES):
            failures.append(f"complete ROM tracked: {path}")
            continue
        candidate = ROOT / path
        if candidate.is_file():
            try:
                with candidate.open("rb") as handle:
                    if handle.read(4) == b"NES\x1a":
                        failures.append(
                            f"iNES ROM payload tracked under another suffix: {path}"
                        )
            except OSError as exc:
                failures.append(f"cannot inspect tracked file {path}: {exc}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=tuple(PROFILES), required=True)
    args = parser.parse_args()
    files = tracked_files()
    failures = validate(args.language, files)
    if failures:
        print(f"Branch separation {args.language}: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        f"Branch separation {args.language}: PASS "
        f"({len(files)} tracked files, no complete ROM)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
