"""Lecture des 85 textes restaurés depuis le catalogue français unique."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "traduction/catalogue.csv"
COLLAPSED_ENGLISH_POINTER_TARGETS = {0x0348F1: 0x03499D}


def load_restorations(path: str | Path = CATALOGUE) -> dict[int, str]:
    structure = json.loads((ROOT / "data/validation/catalogue_structure.json").read_text(encoding="utf-8"))
    expected = {int(row["offset_hex"], 16) for row in structure if row["record_type"] == "RESTORED"}
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("record_type") == "RESTORED"]
    result = {int(row["offset_hex"], 16): row["fr_text"] for row in rows}
    if len(rows) != 85 or len(result) != 85 or set(result) != expected:
        raise ValueError("Le catalogue doit contenir exactement les 85 restaurations attendues")
    if any(not text.strip() for text in result.values()):
        raise ValueError("Une restauration est vide")
    return result
