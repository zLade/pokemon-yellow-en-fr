#!/usr/bin/env python3
"""Reviewed semantic overrides for legacy preformatted dialogues."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


INVENTORY_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "dialogue_boundary_inventory.json"
)
INVENTORY_SHA256 = (
    "c90e128d67fea797c575a04ef305c0e4"
    "2bd29a8a5f044cd0a4b4ec8e6762caf6"
)
INVENTORY_DIALOGUE_RECORD_COUNT = 506
INVENTORY_FAULTY_BOUNDARY_COUNT = 814
INVENTORY_LEGITIMATE_BOUNDARY_COUNT = 29
INVENTORY_POKEDEX_RECORD_COUNT = 49
INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT = 54


@lru_cache(maxsize=1)
def _load_inventory_document() -> dict[str, Any]:
    raw = INVENTORY_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != INVENTORY_SHA256:
        raise ValueError(
            "inventaire des frontières de dialogue non canonique: "
            f"{digest} au lieu de {INVENTORY_SHA256}"
        )
    document = json.loads(raw.decode("utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError("version d'inventaire de dialogue inconnue")
    return document


@lru_cache(maxsize=1)
def load_dialogue_inventory() -> dict[int, dict[str, Any]]:
    document = _load_inventory_document()
    summary = document.get("summary") or {}
    expected_summary = {
        "dialogue_records": INVENTORY_DIALOGUE_RECORD_COUNT,
        "faulty_boundaries": INVENTORY_FAULTY_BOUNDARY_COUNT,
        "legitimate_boundaries": INVENTORY_LEGITIMATE_BOUNDARY_COUNT,
    }
    for field, expected in expected_summary.items():
        if summary.get(field) != expected:
            raise ValueError(
                f"inventaire dialogue: {field}={summary.get(field)!r}, "
                f"attendu {expected}"
            )

    records: dict[int, dict[str, Any]] = {}
    for item in document.get("dialogue_records") or []:
        offset = int(item["offset_hex"], 16)
        if offset in records:
            raise ValueError(
                f"offset en double dans l'inventaire: 0x{offset:06X}"
            )
        source = item.get("source_fr_text")
        semantic = item.get("semantic_text_proposed")
        if not isinstance(source, str) or not isinstance(semantic, str):
            raise ValueError(
                f"texte d'inventaire invalide à 0x{offset:06X}"
            )
        records[offset] = item
    if len(records) != INVENTORY_DIALOGUE_RECORD_COUNT:
        raise ValueError(
            f"{len(records)} dialogues inventoriés, "
            f"attendu {INVENTORY_DIALOGUE_RECORD_COUNT}"
        )
    return records


@lru_cache(maxsize=1)
def load_pokedex_inventory() -> dict[int, dict[str, Any]]:
    """Load the reviewed 13-column Pokédex descriptions."""
    document = _load_inventory_document()
    summary = document.get("summary") or {}
    expected_summary = {
        "pokedex_records": INVENTORY_POKEDEX_RECORD_COUNT,
        "pokedex_artificial_hyphenations": (
            INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT
        ),
    }
    for field, expected in expected_summary.items():
        if summary.get(field) != expected:
            raise ValueError(
                f"inventaire Pokédex: {field}={summary.get(field)!r}, "
                f"attendu {expected}"
            )

    records: dict[int, dict[str, Any]] = {}
    artificial_hyphenations = 0
    for item in document.get("pokedex_13_column_records") or []:
        offset = int(item["offset_hex"], 16)
        if offset in records:
            raise ValueError(
                "offset Pokédex en double dans l'inventaire: "
                f"0x{offset:06X}"
            )
        source = item.get("source_fr_text")
        semantic = item.get("semantic_text_proposed")
        repairs = item.get("artificial_hyphenations")
        if (
            not isinstance(source, str)
            or not isinstance(semantic, str)
            or not isinstance(repairs, list)
        ):
            raise ValueError(
                f"texte d'inventaire Pokédex invalide à 0x{offset:06X}"
            )
        artificial_hyphenations += len(repairs)
        records[offset] = item

    if len(records) != INVENTORY_POKEDEX_RECORD_COUNT:
        raise ValueError(
            f"{len(records)} descriptions Pokédex inventoriées, "
            f"attendu {INVENTORY_POKEDEX_RECORD_COUNT}"
        )
    if (
        artificial_hyphenations
        != INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT
    ):
        raise ValueError(
            f"{artificial_hyphenations} césures Pokédex inventoriées, "
            "attendu "
            f"{INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT}"
        )
    return records


def reviewed_dialogue_override(
    offset: int,
    source_text: str,
) -> str | None:
    """Return reviewed semantic text, failing on stale source divergence."""
    record = load_dialogue_inventory().get(offset)
    if record is None:
        return None
    expected_source = record["source_fr_text"]
    if source_text != expected_source:
        raise ValueError(
            f"0x{offset:06X}: le texte source a divergé de l'inventaire "
            "17/19; déclarer explicitement layout='dialogue_17_19' "
            "après révision"
        )
    # The historical source used literal ASCII ``0`` bytes as pointer-side
    # padding. Repointed text starts at the reviewed visible target, so these
    # bytes are not dialogue columns and must be removed before reflow.
    return str(record["semantic_text_proposed"]).lstrip("0")


def reviewed_pokedex_override(
    offset: int,
    source_text: str,
) -> str | None:
    """Return reviewed 13×4 text, failing on stale source divergence."""
    record = load_pokedex_inventory().get(offset)
    if record is None:
        return None
    expected_source = record["source_fr_text"]
    if source_text != expected_source:
        raise ValueError(
            f"0x{offset:06X}: le texte source a divergé de l'inventaire "
            "Pokédex 13×4"
        )
    return str(record["semantic_text_proposed"])
