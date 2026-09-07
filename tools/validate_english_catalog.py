#!/usr/bin/env python3
"""Static release gate for the complete NJ046 English 2.0 corpus."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.locales.profiles import ENGLISH_TEXT_PROFILE  # noqa: E402


DEFAULT_CATALOGUE = ROOT / "translation"
DEFAULT_ADJUDICATIONS = (
    ROOT / "data" / "validation" / "source_adjudications.csv"
)
DEFAULT_VARIANTS = ROOT / "translation" / "pointer_variants.csv"
DEFAULT_OVERLAPS = ROOT / "data" / "validation" / "storage_overlaps.csv"
DEFAULT_CAMEOS = (
    ROOT
    / "data" / "validation" / "creator_cameo_dialogues.csv"
)

EXPECTED_COUNTS = {
    "catalogue": 1929,
    "main": 1844,
    "restored": 85,
    "dialogues": 1055,
    "pokedex": 159,
    "item_descriptions": 31,
    "adjudications": 63,
    "variants": 7,
    "overlaps": 3,
    "cameos": 17,
}

PENDING_MARKERS = frozenset(
    {"", "pending", "draft", "todo", "unreviewed", "needs_review"}
)
FRENCH_LEAK_PATTERNS = (
    re.compile(r"\bSACHA\b", re.IGNORECASE),
    re.compile(r"\bR[ÉE]GIS\b", re.IGNORECASE),
    re.compile(r"\bPROF\.?\s+CHEN\b", re.IGNORECASE),
    re.compile(r"\bMIAOUSS\b", re.IGNORECASE),
    re.compile(r"\bDRESSEUR(?:E|S)?\b", re.IGNORECASE),
    re.compile(r"\b(?:NOUV|OBJETS|SAUVER)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:bonjour|merci|avec|pour|vous|votre|vos|une|des|les|le|la|"
        r"est|sont|dans|sur|mais|pas|que|qui|quoi|maintenant|oui|non|"
        r"attaque|attaques|gagne|obtenu|obtenue|reçoit|"
        r"utilise|capacité|capacités|objet|objets|sauvage|sauvages)\b",
        re.IGNORECASE,
    ),
)
FRENCH_PUNCTUATION_SPACE = re.compile(r"[ \t]+[!?:;]")
NON_POKE_E_ACUTE = re.compile(r"(?<!Pok)é", re.IGNORECASE)
REQUIRED_SOURCE_TERMS = (
    ("南晶队", "Team Nanjing"),
    ("南晶", "Nanjing"),
    ("宝石大陆", "Hoenn"),
    ("金银地区", "Johto"),
    ("石英地区", "Kanto"),
    ("真新镇", "Pallet"),
    ("华蓝市", "Cerulean"),
    ("彩虹市", "Celadon"),
    ("枯叶市", "Vermilion"),
    ("紫苑镇", "Lavender"),
    ("卡美优", "Kameiyu"),
    ("蓓蓓", "Beibei"),
    ("小李", "Xiao Li"),
    ("小红", "Xiaohong"),
    ("魏村夫", "Wei Cunfu"),
    ("小智", "Ash"),
    ("小茂", "Gary"),
    ("大木博士", "Oak"),
    ("小刚", "Brock"),
    ("小霞", "Misty"),
    ("加纳", "Lorelei"),
    ("西巴", "Bruno"),
    ("菊子:", "Agatha"),
    ("瓦它诺", "Lance"),
    ("武藏", "Jessie"),
    ("小次郎", "James"),
    ("喵喵", "Meowth"),
)

# This shared battle-result payload is executed on both the victory and defeat
# paths.  The player name present in its standalone Chinese source cannot be
# retained without making one of those runtime compositions misleading.
SOURCE_TERM_CONTEXT_EXCEPTIONS = frozenset(
    {
        ("MAIN:0x035F3D", "小智"),
    }
)

# These fragments are concatenated with runtime names, amounts, or adjacent
# lines.  Tiny spacing or wording regressions therefore become broken battle
# sentences even though each standalone payload still passes the codec gate.
EXPECTED_BATTLE_BOUNDARY_PAYLOADS = {
    "MAIN:0x0301D7": " appeared!",
    "MAIN:0x0301EB": "Go! ",
    "MAIN:0x0301F0": "Wild ",
    "MAIN:0x0301F9": " fainted!",
    "MAIN:0x030210": "Got away safely!",
    "MAIN:0x03022A": "Gotcha! ",
    "MAIN:0x030230": "Oh no! ",
    "MAIN:0x03024E": " was caught!",
    "MAIN:0x030262": " sent out ",
    "MAIN:0x030634": "Enemy ",
    "MAIN:0x030646": "Use next Pokémon?",
    "MAIN:0x030660": "Will Ash change Pokémon?",
    "MAIN:0x03075C": "Got ",
    "MAIN:0x030765": "Paid ",
    "MAIN:0x03076B": "Trainer ",
    "MAIN:0x030775": "won!",
    "MAIN:0x030AB5": " EXP gained!",
    "MAIN:0x030ADB": "Ash defeated ",
    "MAIN:0x035F05": "wants to fight!",
    "MAIN:0x035F3D": "Battle result: ",
    "MAIN:0x035FB6": "Enemy is about to use\n",
}

BATTLE_LINE_BREAK_KEYS = frozenset(
    {
        "MAIN:0x03026D",
        "MAIN:0x030290",
        "MAIN:0x030479",
        "MAIN:0x0307B9",
        "MAIN:0x0307C4",
        "MAIN:0x0307CF",
        "MAIN:0x035FAE",
        "MAIN:0x035FB6",
    }
)
BATTLE_ARTIFACT_FREE_LINE_CELLS = 25
EXPECTED_BATTLE_COMPACT_PAYLOADS = {
    "MAIN:0x030242": " broke free!",
    "MAIN:0x0302CF": "It's not very effective!",
    "MAIN:0x0302FA": " was badly poisoned!",
    "MAIN:0x03030E": " became confused!",
    "MAIN:0x030364": " hurt itself!",
    "MAIN:0x030373": " is frozen solid!",
    "MAIN:0x030381": " was hurt by poison!",
    "MAIN:0x030392": " flinched!",
    "MAIN:0x0303A9": " won't rise!",
    "MAIN:0x0303D6": " won't fall!",
    "MAIN:0x030417": "Congrats! ",
    "MAIN:0x03043F": "It knows four moves!",
    "MAIN:0x03045F": "The move ",
    "MAIN:0x030485": "was forgotten!",
    "MAIN:0x03049A": "Learned move:",
    "MAIN:0x0304AB": " didn't learn",
    "MAIN:0x03052D": " risked everything!",
    "MAIN:0x030537": " gathered mystical power!",
    "MAIN:0x030541": " released mystic power!",
    "MAIN:0x030555": " hit by Future Sight!",
    "MAIN:0x0306C0": "'s Accuracy",
    "MAIN:0x03068E": "Status unchanged!",
    "MAIN:0x030744": "No longer badly poisoned!",
    "MAIN:0x035F15": " is paralyzed!",
    "MAIN:0x035F75": " wants to learn",
    "MAIN:0x03650D": " is fully paralyzed!",
}

# Executable tables/dialogue context resolve source labels that are ambiguous
# or demonstrably wrong in the Chinese text itself.
EXPECTED_EXECUTABLE_CONTEXT_PAYLOADS = {
    "MAIN:0x0349E5": "Got Ether!",
    "MAIN:0x0349F2": "Got Max Ether!",
    "MAIN:0x038F91": "Got TM35!",
}

# The Bag list writes a two-digit quantity immediately after an eight-cell
# item-name field.  The last cell is deliberately kept blank so names and
# quantities never collide or appear glued together.
EXPECTED_FIXED_ITEM_NAME_PAYLOADS = {
    "MAIN:0x035F34": "PokéB.",
    "MAIN:0x0316EE": "Great B",
    "MAIN:0x0316F7": "Ultra B",
    "MAIN:0x031700": "MasterB",
    "MAIN:0x031709": "Potion",
    "MAIN:0x031710": "Sup.Pot",
    "MAIN:0x031719": "Hyp.Pot",
    "MAIN:0x031722": "Max.Pot",
    "MAIN:0x031737": "PARHeal",
    "MAIN:0x03173E": "Awaken.",
    "MAIN:0x031746": "IceHeal",
    "MAIN:0x03174F": "BurnHl.",
    "MAIN:0x031758": "FullHl.",
    "MAIN:0x031761": "Revive",
    "MAIN:0x031769": "Ether",
    "MAIN:0x03176F": "MaxEth.",
    "MAIN:0x031779": "RareCdy",
    "MAIN:0x031782": "FireSt.",
    "MAIN:0x03178B": "WatrSt.",
    "MAIN:0x031794": "ThunSt.",
    "MAIN:0x030F8E": "LeafSt.",
    "MAIN:0x03179D": "MoonSt.",
    "MAIN:0x0317A6": "Parcel",
    "MAIN:0x0317B5": "TownMap",
    "MAIN:0x0317B9": "HelixFs",
    "MAIN:0x0317C4": "DomeFos",
    "MAIN:0x0317CF": "S.S.Tkt",
    "MAIN:0x0317DA": "FreshWt",
    "MAIN:0x0317E3": "SilphSc",
    "MAIN:0x0317EE": "PokéFlt",
    "MAIN:0x0317F8": "GoldTth",
    "MAIN:0x030F83": "MystTkt",
    "MAIN:0x031803": "Cut HM",
    "MAIN:0x03180D": "Fly HM",
    "MAIN:0x031815": "Surf HM",
    "MAIN:0x03181D": "STR HM",
    "MAIN:0x031824": "FlashHM",
    "MAIN:0x03182D": "TM 01",
}

EXPECTED_FIXED_GRID_7X3_KEYS = frozenset(
    {
        "MAIN:0x031A15", "MAIN:0x031A24", "MAIN:0x031A37",
        "MAIN:0x031A4A", "MAIN:0x031A5D", "MAIN:0x031A78",
        "MAIN:0x031A86", "MAIN:0x031A95", "MAIN:0x031AA4",
        "MAIN:0x031AB2", "MAIN:0x031AC1", "MAIN:0x031ACE",
        "MAIN:0x031ADC", "MAIN:0x031AE8", "MAIN:0x031AFF",
        "MAIN:0x031B0E", "MAIN:0x031B29", "MAIN:0x031B42",
        "MAIN:0x031B54", "MAIN:0x031B67", "MAIN:0x031B7A",
        "MAIN:0x031B8D", "MAIN:0x031BA0", "MAIN:0x031BAB",
        "MAIN:0x031BBC", "MAIN:0x031BCA", "MAIN:0x031BE0",
        "MAIN:0x031BE8", "MAIN:0x031BFD", "MAIN:0x031C13",
        "MAIN:0x031C27",
    }
)


class EnglishCatalogueError(ValueError):
    """One or more release-blocking corpus defects were found."""


from tools.catalogue_io import open_csv


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open_csv(path) as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def normalized_status(value: str) -> str:
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def is_pending(value: str) -> bool:
    normalized = normalized_status(value)
    return normalized in PENDING_MARKERS or "pending" in normalized


def _require_unique(
    rows: Sequence[Mapping[str, str]], field: str, label: str
) -> dict[str, Mapping[str, str]]:
    result: dict[str, Mapping[str, str]] = {}
    for index, row in enumerate(rows, start=2):
        key = row.get(field, "").strip()
        if not key:
            raise EnglishCatalogueError(f"{label}:{index}: empty {field}")
        if key in result:
            raise EnglishCatalogueError(f"{label}: duplicate {field} {key}")
        result[key] = row
    return result


def validate_catalogue_rows(
    rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Mapping[str, str]], dict[str, int]]:
    if len(rows) != EXPECTED_COUNTS["catalogue"]:
        raise EnglishCatalogueError(
            f"catalogue has {len(rows)} rows, expected 1929"
        )
    by_key = _require_unique(rows, "stable_key", "catalogue")
    types = Counter(row.get("record_type", "").upper() for row in rows)
    layouts = Counter(row.get("layout", "") for row in rows)
    counts = {
        "main": types["MAIN"],
        "restored": types["RESTORED"],
        "dialogues": (
            layouts["dialogue_19_19"]
            + layouts["dialogue_intro_17_19"]
        ),
        "pokedex": layouts["pokedex_13x4"],
        "item_descriptions": layouts["fixed_grid_7x3"],
    }
    for label in (
        "main", "restored", "dialogues", "pokedex", "item_descriptions"
    ):
        if counts[label] != EXPECTED_COUNTS[label]:
            raise EnglishCatalogueError(
                f"{label}: {counts[label]}, expected {EXPECTED_COUNTS[label]}"
            )

    errors: list[str] = []
    actual_fixed_grid_keys = {
        row["stable_key"]
        for row in rows
        if row.get("layout") == "fixed_grid_7x3"
    }
    if actual_fixed_grid_keys != EXPECTED_FIXED_GRID_7X3_KEYS:
        missing = sorted(EXPECTED_FIXED_GRID_7X3_KEYS - actual_fixed_grid_keys)
        extra = sorted(actual_fixed_grid_keys - EXPECTED_FIXED_GRID_7X3_KEYS)
        errors.append(
            "fixed 7x3 item-description topology mismatch; "
            f"missing={missing}, extra={extra}"
        )
    for key, expected in EXPECTED_BATTLE_BOUNDARY_PAYLOADS.items():
        row = by_key.get(key)
        if row is not None and row.get("english_v2") != expected:
            errors.append(
                f"{key}: battle boundary payload must be {expected!r}"
            )
    for key, expected in EXPECTED_EXECUTABLE_CONTEXT_PAYLOADS.items():
        row = by_key.get(key)
        if row is not None and row.get("english_v2") != expected:
            errors.append(
                f"{key}: executable-context payload must be {expected!r}"
            )
    for key, expected in EXPECTED_FIXED_ITEM_NAME_PAYLOADS.items():
        row = by_key.get(key)
        if row is None:
            errors.append(f"{key}: fixed item name is missing")
            continue
        actual = row.get("english_v2", "")
        if actual != expected:
            errors.append(
                f"{key}: fixed item name must be {expected!r}, got {actual!r}"
            )
        try:
            encoded = ENGLISH_TEXT_PROFILE.format_text(actual, "")
        except (TypeError, ValueError, UnicodeError):
            encoded = b""
        if len(encoded) > 7:
            errors.append(
                f"{key}: fixed item name uses {len(encoded)} cells, maximum is 7"
            )
    actual_break_keys = {
        row["stable_key"]
        for row in rows
        if "\n" in row.get("english_v2", "")
        and row.get("layout", "") in {"", "raw"}
    }
    if actual_break_keys != BATTLE_LINE_BREAK_KEYS:
        errors.append(
            "battle line-break topology mismatch; "
            f"missing={sorted(BATTLE_LINE_BREAK_KEYS - actual_break_keys)}, "
            f"extra={sorted(actual_break_keys - BATTLE_LINE_BREAK_KEYS)}"
        )
    for key in BATTLE_LINE_BREAK_KEYS:
        row = by_key.get(key)
        if row is None:
            continue
        text = row.get("english_v2", "")
        if text.count("\n") != 1:
            errors.append(f"{key}: battle text must contain exactly one line break")
            continue
        for line in text.split("\n"):
            try:
                cells = len(ENGLISH_TEXT_PROFILE.encode_text(line))
            except (TypeError, ValueError, UnicodeError):
                continue
            if cells > BATTLE_ARTIFACT_FREE_LINE_CELLS:
                errors.append(
                    f"{key}: battle line uses {cells} cells, artifact-free maximum "
                    f"is {BATTLE_ARTIFACT_FREE_LINE_CELLS}"
                )
    for key, expected in EXPECTED_BATTLE_COMPACT_PAYLOADS.items():
        row = by_key.get(key)
        if row is not None and row.get("english_v2") != expected:
            errors.append(
                f"{key}: compact battle payload must be {expected!r}"
            )
    for row in rows:
        key = row["stable_key"]
        for field in (
            "chinese_text",
            "english_v2",
            "editorial_origin",
            "source_resolution",
            "review_status",
        ):
            if not row.get(field, "").strip():
                errors.append(f"{key}: empty {field}")
        for field in (
            "editorial_origin",
            "source_resolution",
            "review_status",
        ):
            if is_pending(row.get(field, "")):
                errors.append(f"{key}: pending {field}")

        text = row.get("english_v2", "")
        chinese = row.get("chinese_text", "")
        folded_text = text.casefold()
        for source_term, required_english in REQUIRED_SOURCE_TERMS:
            if (
                source_term in chinese
                and required_english.casefold() not in folded_text
                and (key, source_term) not in SOURCE_TERM_CONTEXT_EXCEPTIONS
            ):
                errors.append(
                    f"{key}: source term {source_term!r} requires "
                    f"{required_english!r}"
                )
        if FRENCH_PUNCTUATION_SPACE.search(text):
            errors.append(f"{key}: French punctuation spacing")
        for pattern in FRENCH_LEAK_PATTERNS:
            if pattern.search(text):
                errors.append(f"{key}: possible French leakage {pattern.pattern}")
        if NON_POKE_E_ACUTE.search(text):
            errors.append(
                f"{key}: é is only permitted in English Poké terminology"
            )
        try:
            payload = ENGLISH_TEXT_PROFILE.format_text(
                text,
                row.get("layout", ""),
            )
        except (TypeError, ValueError, UnicodeError) as exc:
            errors.append(f"{key}: codec/layout: {exc}")
            continue
        declared = row.get("encoded_length", "").strip()
        if declared and declared.isdigit() and int(declared) != len(payload):
            errors.append(
                f"{key}: encoded_length {declared} != {len(payload)}"
            )
        compression = normalized_status(row.get("compression", ""))
        if compression in {"yes", "true", "compressed"} and not row.get(
            "compression_justification", ""
        ).strip():
            errors.append(f"{key}: compression lacks justification")

    if errors:
        raise EnglishCatalogueError(
            f"catalogue has {len(errors)} error(s):\n  "
            + "\n  ".join(errors[:50])
        )
    return by_key, counts


def validate_adjudications(rows: Sequence[Mapping[str, str]]) -> None:
    if len(rows) != EXPECTED_COUNTS["adjudications"]:
        raise EnglishCatalogueError("source adjudication count is not 63")
    _require_unique(rows, "stable_key", "source adjudications")
    errors = [
        row["stable_key"]
        for row in rows
        if is_pending(row.get("review_status", ""))
        or is_pending(row.get("resolution_status", ""))
        or not row.get("selected_chinese_text", "").strip()
        or not row.get("selected_source_method", "").strip()
    ]
    if errors:
        raise EnglishCatalogueError(
            f"unresolved source adjudications: {', '.join(errors[:20])}"
        )


def validate_variants(
    rows: Sequence[Mapping[str, str]],
    catalogue: Mapping[str, Mapping[str, str]],
) -> None:
    if len(rows) != EXPECTED_COUNTS["variants"]:
        raise EnglishCatalogueError("pointer variant count is not 7")
    _require_unique(rows, "variant_key", "pointer variants")
    groups = Counter(row.get("stable_key", "") for row in rows)
    expected = {
        "MAIN:0x0302FA": 2,
        "MAIN:0x03162C": 2,
        "MAIN:0x031A15": 3,
    }
    if dict(groups) != expected:
        raise EnglishCatalogueError(f"unexpected pointer variant groups: {groups}")
    errors: list[str] = []
    first_by_group: dict[str, Mapping[str, str]] = {}
    for row in rows:
        key = row["variant_key"]
        owner = row["stable_key"]
        first_by_group.setdefault(owner, row)
        if is_pending(row.get("review_status", "")):
            errors.append(f"{key}: pending review")
        if not row.get("editorial_origin", "").strip():
            errors.append(f"{key}: missing editorial origin")
        try:
            layout = (
                "fixed_grid_7x3"
                if owner == "MAIN:0x031A15"
                else ""
            )
            ENGLISH_TEXT_PROFILE.format_text(
                row.get("english_v2", ""), layout
            )
        except (TypeError, ValueError, UnicodeError) as exc:
            errors.append(f"{key}: codec/layout: {exc}")
    for owner, first in first_by_group.items():
        if catalogue[owner].get("english_v2") != first.get("english_v2"):
            errors.append(f"{owner}: main payload differs from primary variant")
    if errors:
        raise EnglishCatalogueError(
            "invalid pointer variants:\n  " + "\n  ".join(errors)
        )


def validate_overlaps(rows: Sequence[Mapping[str, str]]) -> None:
    if len(rows) != EXPECTED_COUNTS["overlaps"]:
        raise EnglishCatalogueError("storage overlap count is not 3")
    _require_unique(rows, "overlap_group", "storage overlaps")
    for row in rows:
        if row.get("relationship") != "alias_is_exact_suffix_of_owner":
            raise EnglishCatalogueError(
                f"{row['overlap_group']}: unexpected relationship"
            )
        if row.get("structural_status") != "declared_source_storage_fact":
            raise EnglishCatalogueError(
                f"{row['overlap_group']}: unreviewed structural status"
            )


def validate_cameos(
    rows: Sequence[Mapping[str, str]],
    catalogue: Mapping[str, Mapping[str, str]],
) -> None:
    if len(rows) != EXPECTED_COUNTS["cameos"]:
        raise EnglishCatalogueError("creator/cameo count is not 17")
    errors: list[str] = []
    for row in rows:
        key = row.get("stable_key", "")
        name = row.get("creator_or_cameo", "")
        catalogue_row = catalogue.get(key)
        if catalogue_row is None:
            errors.append(f"{key}: missing catalogue row")
            continue
        if name.casefold() not in catalogue_row.get("english_v2", "").casefold():
            errors.append(f"{key}: creator/cameo {name!r} not preserved")
    if errors:
        raise EnglishCatalogueError(
            "creator/cameo failures:\n  " + "\n  ".join(errors)
        )


def validate_all(
    catalogue_path: Path,
    adjudications_path: Path,
    variants_path: Path,
    overlaps_path: Path,
    cameos_path: Path,
) -> dict[str, object]:
    _fields, catalogue_rows = read_csv(catalogue_path)
    _fields, adjudication_rows = read_csv(adjudications_path)
    _fields, variant_rows = read_csv(variants_path)
    _fields, overlap_rows = read_csv(overlaps_path)
    _fields, cameo_rows = read_csv(cameos_path)
    catalogue, counts = validate_catalogue_rows(catalogue_rows)
    validate_adjudications(adjudication_rows)
    validate_variants(variant_rows, catalogue)
    validate_overlaps(overlap_rows)
    validate_cameos(cameo_rows, catalogue)
    return {
        "schema": "nj046-en2-static-catalogue-gate/v1",
        "result": "PASS",
        "counts": {
            "catalogue": len(catalogue_rows),
            **counts,
            "adjudications": len(adjudication_rows),
            "variants": len(variant_rows),
            "overlaps": len(overlap_rows),
            "cameos": len(cameo_rows),
        },
        "codec": "strict_printable_ascii_with_unicode_e_acute_to_0x40",
        "human_playthrough": "pending",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument(
        "--adjudications", type=Path, default=DEFAULT_ADJUDICATIONS
    )
    parser.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
    parser.add_argument("--overlaps", type=Path, default=DEFAULT_OVERLAPS)
    parser.add_argument("--cameos", type=Path, default=DEFAULT_CAMEOS)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = validate_all(
            args.catalogue.resolve(),
            args.adjudications.resolve(),
            args.variants.resolve(),
            args.overlaps.resolve(),
            args.cameos.resolve(),
        )
    except (EnglishCatalogueError, OSError, csv.Error) as exc:
        print(f"English catalogue gate: FAIL\n{exc}")
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
