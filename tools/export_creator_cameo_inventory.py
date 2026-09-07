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
        "MAIN:0x0345E4", "creator_mention", "Kameiyu", "Warning",
    ),
    CameoMetadata(
        "MAIN:0x0346A1", "creator_story_dialogue", "Kameiyu", "Secret boss",
    ),
    CameoMetadata(
        "MAIN:0x034739", "creator_story_dialogue", "Kameiyu", "Secret boss",
    ),
    CameoMetadata(
        "MAIN:0x0347A2", "creator_story_dialogue", "Kameiyu", "Mew gift",
    ),
    CameoMetadata(
        "MAIN:0x034873", "creator_story_dialogue", "Kameiyu", "After battle",
    ),
    CameoMetadata(
        "MAIN:0x034887", "creator_story_dialogue", "Beibei", "Compliment",
    ),
    CameoMetadata(
        "MAIN:0x0348B5", "creator_story_dialogue", "Xiao Li", "Warning",
    ),
    CameoMetadata(
        "MAIN:0x0353F0", "creator_mention", "Kameiyu", "Rumor",
    ),
    CameoMetadata(
        "MAIN:0x037A51", "creator_mention", "Kameiyu", "Announcement",
    ),
    CameoMetadata(
        "MAIN:0x037ADC", "creator_story_dialogue", "Kameiyu", "Secret challenge",
    ),
    CameoMetadata(
        "MAIN:0x03BAB6", "creator_story_dialogue", "Beibei", "Eevee gift",
    ),
    CameoMetadata(
        "MAIN:0x03BCF6", "developer_office", "Xiaohong", "Graphic artist",
    ),
    CameoMetadata(
        "MAIN:0x03BD1A", "developer_office", "Kameiyu", "Writer",
    ),
    CameoMetadata(
        "MAIN:0x03BD3F", "developer_office", "Wei Cunfu", "Programmer",
    ),
    CameoMetadata(
        "MAIN:0x03BD65", "developer_office", "BOSS", "Manager",
    ),
    CameoMetadata(
        "MAIN:0x03BE0E", "creator_story_dialogue", "Xiao Li", "Secret gift",
    ),
    CameoMetadata(
        "RESTORED:0x0331D1", "creator_mention", "Kameiyu", "Warning",
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
        raise ValueError("Missing cameo keys : " + ", ".join(missing))
    result: list[dict[str, str]] = []
    for metadata in CAMEO_METADATA:
        dialogue = by_key[metadata.stable_key]
        result.append(
            {
                "id": dialogue.public_id,
                "stable_key": dialogue.stable_key,
                "scope": metadata.scope,
                "creator_or_cameo": metadata.creator,
                "source_role": metadata.source_role,
                "chinese_text": dialogue.chinese_text,
                "french_reference_text": dialogue.french_text,
                "status": "restored in the French version",
            }
        )
    return result


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "id",
        "stable_key",
        "scope",
        "creator_or_cameo",
        "source_role",
        "chinese_text",
        "french_reference_text",
        "status",
    )
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Regenerate the current creator-cameo inventory.'
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = build_cameo_rows()
    write_csv(args.output, rows)
    print(f"Exported cameos : {len(rows)}")
    print(f"CSV : {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
