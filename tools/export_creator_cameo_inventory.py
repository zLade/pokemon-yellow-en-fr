#!/usr/bin/env python3
"""Regenerate the creator-cameo inventory from stable dialogue keys."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR.parent))

from tools.export_dialogue_review_table import (
    DEFAULT_ALIGNMENT,
    DEFAULT_ANIME_MOTTO_MAIN_MAP,
    DEFAULT_FIDELITY_MAP,
    DEFAULT_NATURALIZATION_MAP,
    DEFAULT_OFFICIAL_GEN1_SHARED_MAP,
    DEFAULT_OFFICIAL_YELLOW_MAP,
    DEFAULT_REMOVED_SOURCE,
    DEFAULT_SOURCE_INVENTORY,
    ROM_DIR,
    ReviewRow,
    build_rows,
)


DEFAULT_OUTPUT = (
    ROM_DIR
    / "build"
    / "chinese-english-fidelity"
    / "extraction"
    / "creator_cameo_dialogues.csv"
)


@dataclass(frozen=True)
class CameoMetadata:
    stable_key: str
    scope: str
    creator: str
    source_role: str


# This reviewed manifest names the narrative function only. Text and public
# IDs always come from the current exhaustive inventory, so an editorial
# rewrite cannot silently leave this CSV with the old English replacement.
CAMEO_METADATA = (
    CameoMetadata(
        "MAIN:0x0345E4", "creator_mention", "Kameiyu", "Avertissement",
    ),
    CameoMetadata(
        "MAIN:0x0346A1", "creator_story_dialogue", "Kameiyu", "Boss secret",
    ),
    CameoMetadata(
        "MAIN:0x034739", "creator_story_dialogue", "Kameiyu", "Boss secret",
    ),
    CameoMetadata(
        "MAIN:0x0347A2", "creator_story_dialogue", "Kameiyu", "Don de Mew",
    ),
    CameoMetadata(
        "MAIN:0x034873", "creator_story_dialogue", "Kameiyu", "Après-combat",
    ),
    CameoMetadata(
        "MAIN:0x034887", "creator_story_dialogue", "Beibei", "Compliment",
    ),
    CameoMetadata(
        "MAIN:0x0348B5", "creator_story_dialogue", "Xiao Li", "Avertissement",
    ),
    CameoMetadata(
        "MAIN:0x0353F0", "creator_mention", "Kameiyu", "Rumeur",
    ),
    CameoMetadata(
        "MAIN:0x037A51", "creator_mention", "Kameiyu", "Annonce",
    ),
    CameoMetadata(
        "MAIN:0x037ADC", "creator_story_dialogue", "Kameiyu", "Défi secret",
    ),
    CameoMetadata(
        "MAIN:0x03BAB6", "creator_story_dialogue", "Beibei", "Don d'Évoli",
    ),
    CameoMetadata(
        "MAIN:0x03BCF6", "developer_office", "Xiaohong", "Graphiste",
    ),
    CameoMetadata(
        "MAIN:0x03BD1A", "developer_office", "Kameiyu", "Scénariste",
    ),
    CameoMetadata(
        "MAIN:0x03BD3F", "developer_office", "Wei Cunfu", "Programmeur",
    ),
    CameoMetadata(
        "MAIN:0x03BD65", "developer_office", "BOSS", "Responsable",
    ),
    CameoMetadata(
        "MAIN:0x03BE0E", "creator_story_dialogue", "Xiao Li", "Don secret",
    ),
    CameoMetadata(
        "RESTORED:0x0331D1", "creator_mention", "Kameiyu", "Avertissement",
    ),
)


def exhaustive_rows() -> list[ReviewRow]:
    return build_rows(
        script_path=ROM_DIR / "script.py",
        alignment_path=DEFAULT_ALIGNMENT,
        source_inventory_path=DEFAULT_SOURCE_INVENTORY,
        removed_source_path=DEFAULT_REMOVED_SOURCE,
        fidelity_map_path=DEFAULT_FIDELITY_MAP,
        naturalization_map_path=DEFAULT_NATURALIZATION_MAP,
        official_yellow_map_path=DEFAULT_OFFICIAL_YELLOW_MAP,
        official_gen1_shared_map_path=DEFAULT_OFFICIAL_GEN1_SHARED_MAP,
        anime_motto_main_map_path=DEFAULT_ANIME_MOTTO_MAIN_MAP,
    )


def build_cameo_rows(
    rows: list[ReviewRow] | None = None,
) -> list[dict[str, str]]:
    by_key = {row.stable_key: row for row in rows or exhaustive_rows()}
    missing = [
        metadata.stable_key
        for metadata in CAMEO_METADATA
        if metadata.stable_key not in by_key
    ]
    if missing:
        raise ValueError("clés de caméos absentes : " + ", ".join(missing))
    result: list[dict[str, str]] = []
    for metadata in CAMEO_METADATA:
        dialogue = by_key[metadata.stable_key]
        result.append(
            {
                "id": dialogue.public_id,
                "cle_stable": dialogue.stable_key,
                "scope": metadata.scope,
                "createur_ou_cameo": metadata.creator,
                "role_source": metadata.source_role,
                "texte_chinois_source": dialogue.chinese_text,
                "texte_francais_actuel": dialogue.french_text,
                "statut": "restauré dans la version française",
            }
        )
    return result


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "id",
        "cle_stable",
        "scope",
        "createur_ou_cameo",
        "role_source",
        "texte_chinois_source",
        "texte_francais_actuel",
        "statut",
    )
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Régénère l'inventaire courant des caméos des créateurs."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = build_cameo_rows()
    write_csv(args.output, rows)
    print(f"Caméos exportés : {len(rows)}")
    print(f"CSV : {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
