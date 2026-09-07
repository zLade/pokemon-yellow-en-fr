#!/usr/bin/env python3
"""Validate the language-specific repository layout for the current branch."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

PROFILES = {'en': {'required': ['.github/workflows/validate.yml',
                     'README.md',
                     'CHANGELOG.md',
                     'NOTICE.md',
                     'build.py',
                     'translation/catalog.csv',
                     'translation/pointer_variants.csv',
                     'translation/move_labels_two_line.csv',
                     'data/source/chinese_records.csv',
                     'data/source/chinese_glyph_map.csv',
                     'data/validation/structural_pointer_inventory.json',
                     'tools/rom_builder.py',
                     'tools/build_english_release.py',
                     'releases/en/2.0.3/README.md',
                     'releases/en/2.0.3/SHA256SUMS',
                     'releases/en/2.0.3/VERSION'],
        'forbidden_prefixes': ['locales/',
                               'releases/fr/',
                               'dist/fr/',
                               'releases/en/2.0.0/',
                               'releases/en/2.0.1/',
                               'docs/en/'],
        'forbidden_files': ['script.py',
                            'traduction_base.csv',
                            'LISTE_EXHAUSTIVE_DIALOGUES.csv',
                            'rom_traduction_assistant.py',
                            'profiles/fr-release.json'],
        'forbidden_markdown': ['MODE_EMPLOI_TRADUCTION.md']}}

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
