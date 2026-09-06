#!/usr/bin/env python3
"""Export an exhaustive, stable review table for every French dialogue.

The ordinary translation script contains 970 dialogue payloads (including
the three introduction payloads).  Another 85 source dialogues are restored
directly by the repacker because the English ROM deleted or miswired their
pointers.  This exporter deliberately includes both groups.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import parse_patch_entries  # noqa: E402
from tools.chinese_dialogue_restorations import (  # noqa: E402
    ANIME_MOTTO_RESTORATION_REFERENCES,
    COLLAPSED_ENGLISH_POINTER_REFERENCES,
    OFFICIAL_YELLOW_RESTORATION_REFERENCES,
    RESTORED_DIALOGUES,
    RESTORATION_NATURALIZATION_OVERRIDES,
)


PINNED_FIDELITY_SOURCE = (
    ROM_DIR
    / "data"
    / "source"
    / "chinese-english-fidelity"
)
DEFAULT_ALIGNMENT = PINNED_FIDELITY_SOURCE / "chinese_dialogues.csv"
DEFAULT_SOURCE_INVENTORY = (
    PINNED_FIDELITY_SOURCE / "chinese_french_dialogue_inventory.csv"
)
DEFAULT_REMOVED_SOURCE = (
    PINNED_FIDELITY_SOURCE / "dialogues_removed_from_english.csv"
)
DEFAULT_FIDELITY_MAP = (
    ROM_DIR / "tools" / "data" / "chinese_fidelity_dialogue_overrides.json"
)
DEFAULT_NATURALIZATION_MAP = (
    ROM_DIR / "tools" / "data" / "french_naturalization_overrides.json"
)
DEFAULT_OFFICIAL_YELLOW_MAP = (
    ROM_DIR
    / "tools"
    / "data"
    / "french_official_yellow_dialogue_overrides.json"
)
DEFAULT_OFFICIAL_GEN1_SHARED_MAP = (
    ROM_DIR
    / "tools"
    / "data"
    / "french_official_gen1_shared_dialogue_overrides.json"
)
DEFAULT_ANIME_MOTTO_MAIN_MAP = (
    ROM_DIR
    / "tools"
    / "data"
    / "french_anime_motto_main_overrides.json"
)
DEFAULT_CSV = ROM_DIR / "LISTE_EXHAUSTIVE_DIALOGUES.csv"
DEFAULT_MARKDOWN = ROM_DIR / "LISTE_EXHAUSTIVE_DIALOGUES.md"


# The English record at 0x03F033 spans several unrelated source records.
# 0x03D074 merely contains a verified dummy word that resembles a pointer;
# the live dialogue slot is 0x03D086.  The general pointer alignment therefore
# supplies the wrong Chinese provenance for this one main-script row unless we
# select the reviewed live source explicitly.
REVIEWED_SOURCE_POINTER_BY_MAIN_OFFSET: dict[int, int] = {
    # Deux messages d'objet chinois partageaient le même texte anglais.
    # L'Anti-Para est désormais restauré séparément ; le texte principal
    # restant correspond donc au Réveil.
    0x03499D: 0x0348F3,
    # Les premières sources de ces trois paires ont été restaurées à leur
    # propre emplacement. Le dialogue principal doit montrer la seconde.
    0x039D74: 0x038367,
    0x039DA8: 0x038377,
    0x039DE5: 0x03837D,
    # Le pointeur vivant de la scène de Régis sur l'Océane vise une source
    # distincte de l'enregistrement anglais agrégé retenu automatiquement.
    0x03A9D1: 0x038405,
    0x03F033: 0x03D086,
}

# Cinq lignes ne passent pas par un enregistrement chinois ordinaire dans
# l'inventaire d'alignement : deux sont encore encodées avec les glyphes
# graphiques source dans la ROM anglaise et trois vivent dans des blocs
# spéciaux (menu/introduction). Leur décodage a été relu directement dans la
# ROM chinoise avec build/.../chinese_glyph_map.csv. Garder cette liste
# explicite évite de transformer une absence d'alignement en texte inventé.
REVIEWED_INLINE_CHINESE_BY_MAIN_OFFSET: dict[int, str] = {
    0x034927: "得到无",
    0x034C03: "欢迎!",
    0x03804B: "精灵取出精灵存放",
    0x038445: (
        "你好!欢迎你光临宠物精灵的世界!大家都叫我大木博士,"
        "在这世界住着被称为宠物精灵的生物!这生物被视为宠物,"
        "或使用于对战等等.而我是研究这宠物精灵的!小智,一个将"
        "属于你的故事,梦想即将开始!"
    ),
    0x03D088: "捉鸟人:那里有很多珍贵的精灵...",
}

# Cette restauration a été découverte après la publication des 1 054 IDs
# initiaux. Elle reste en fin de tableau pour ne pas renuméroter les lignes
# déjà communiquées au relecteur.
APPENDED_RESTORATION_REFERENCES = (0x0348F1,)


@dataclass(frozen=True)
class ReviewRow:
    public_id: str
    stable_key: str
    category: str
    offset_or_pointer: str
    script_line: str
    layout: str
    speaker: str
    french_text: str
    chinese_text: str
    english_intermediate: str
    alignment_confidence: str
    translation_history: str
    naturalized: str
    chinese_fidelity_corrected: str


def read_csv_by_hex(path: Path, field: str) -> dict[int, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return {
        int(row[field], 16): row
        for row in rows
        if row.get(field)
    }


def read_csv_grouped_by_hex(
    path: Path,
    field: str,
) -> dict[int, list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        if not row.get(field):
            continue
        grouped.setdefault(int(row[field], 16), []).append(row)
    return grouped


def read_offset_map(path: Path) -> dict[int, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path}: la racine doit être un objet JSON")
    return {int(key, 16): str(value) for key, value in document.items()}


def clean_source_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def english_rom_text(source: dict[str, str]) -> str:
    if source.get("english_storage") == "graphical_codes":
        return (
            "NON TRADUIT — texte chinois conservé dans la ROM anglaise"
        )
    return clean_source_text(source.get("english_text", ""))


def speaker_from_text(text: str) -> str:
    match = re.match(r"^\s*([^:：\n]{1,32})\s*[:：]", text)
    if not match:
        return ""
    candidate = match.group(1).strip()
    letters = [character for character in candidate if character.isalpha()]
    return candidate if letters and candidate == candidate.upper() else ""


def history_for_main(
    *,
    offset: int,
    layout: str,
    fidelity_offsets: set[int],
    naturalized_offsets: set[int],
    official_yellow_offsets: set[int],
    official_gen1_shared_offsets: set[int],
    anime_motto_offsets: set[int],
) -> str:
    labels: list[str] = []
    if layout == "dialogue_intro_17_19":
        labels.append("introduction")
    if offset in official_yellow_offsets:
        labels.append("adapté d'après Pokémon Jaune (FR)")
    elif offset in official_gen1_shared_offsets:
        labels.append("adapté d'après les dialogues officiels R/B/J (FR)")
    elif offset in anime_motto_offsets:
        labels.append("adapté d'après la devise française de l'anime")
    elif offset in fidelity_offsets:
        labels.append("corrigé d'après le chinois")
    if (
        offset in naturalized_offsets
        and offset not in official_yellow_offsets
        and offset not in official_gen1_shared_offsets
        and offset not in anime_motto_offsets
    ):
        labels.append("naturalisé en français")
    return " + ".join(labels) if labels else "traduction principale"


def build_rows(
    *,
    script_path: Path,
    alignment_path: Path,
    source_inventory_path: Path,
    removed_source_path: Path,
    fidelity_map_path: Path,
    naturalization_map_path: Path,
    official_yellow_map_path: Path,
    official_gen1_shared_map_path: Path,
    anime_motto_main_map_path: Path,
) -> list[ReviewRow]:
    alignments = read_csv_by_hex(alignment_path, "english_offset_hex")
    source_inventory = read_csv_by_hex(
        source_inventory_path,
        "pointer_reference_hex",
    )
    direct_sources_by_main_offset = read_csv_grouped_by_hex(
        source_inventory_path,
        "english_offset_hex",
    )
    removed_sources = read_csv_by_hex(
        removed_source_path,
        "pointer_reference_hex",
    )
    fidelity_offsets = set(read_offset_map(fidelity_map_path))
    naturalized_offsets = set(read_offset_map(naturalization_map_path))
    official_yellow_offsets = set(
        read_offset_map(official_yellow_map_path)
    )
    official_gen1_shared_offsets = set(
        read_offset_map(official_gen1_shared_map_path)
    )
    anime_motto_offsets = set(
        read_offset_map(anime_motto_main_map_path)
    )
    naturalized_restoration_offsets = set(
        RESTORATION_NATURALIZATION_OVERRIDES
    )

    entries = [
        entry
        for entry in parse_patch_entries(
            script_path,
            apply_dialogue_inventory=False,
        )
        if entry.layout.startswith("dialogue_")
    ]
    if len(entries) != 970:
        raise ValueError(
            f"{len(entries)} dialogues principaux au lieu des 970 attendus"
        )
    if len({entry.offset for entry in entries}) != len(entries):
        raise ValueError("offsets de dialogues principaux non uniques")

    rows: list[ReviewRow] = []
    for index, entry in enumerate(entries, start=1):
        source = alignments.get(entry.offset)
        if source is None:
            raise ValueError(
                f"0x{entry.offset:06X}: alignement chinois absent"
            )
        reviewed_source_pointer = REVIEWED_SOURCE_POINTER_BY_MAIN_OFFSET.get(
            entry.offset
        )
        chinese_text = source["chinese_text"]
        alignment_confidence = source["alignment_confidence"]
        direct_sources = direct_sources_by_main_offset.get(
            entry.offset,
            [],
        )
        # A unique source reached through the corresponding live pointer slot
        # is stronger evidence than a record merely containing the same file
        # offset. This also restores source text for a few main entries that
        # the generic record matcher left unaligned. Multi-source English
        # records keep their aggregate pointer-table alignment instead.
        if len(direct_sources) == 1:
            chinese_text = direct_sources[0]["chinese_text"]
            alignment_confidence = "high"
        if reviewed_source_pointer is not None:
            reviewed_source = source_inventory.get(reviewed_source_pointer)
            if reviewed_source is None:
                raise ValueError(
                    f"0x{entry.offset:06X}: source chinoise relue "
                    f"0x{reviewed_source_pointer:06X} absente"
                )
            chinese_text = reviewed_source["chinese_text"]
            alignment_confidence = "high"
        reviewed_inline_source = (
            REVIEWED_INLINE_CHINESE_BY_MAIN_OFFSET.get(entry.offset)
        )
        if reviewed_inline_source is not None:
            chinese_text = reviewed_inline_source
            alignment_confidence = "high"
        history = history_for_main(
            offset=entry.offset,
            layout=entry.layout,
            fidelity_offsets=fidelity_offsets,
            naturalized_offsets=naturalized_offsets,
            official_yellow_offsets=official_yellow_offsets,
            official_gen1_shared_offsets=official_gen1_shared_offsets,
            anime_motto_offsets=anime_motto_offsets,
        )
        rows.append(
            ReviewRow(
                public_id=f"D{index:04d}",
                stable_key=f"MAIN:0x{entry.offset:06X}",
                category=(
                    "Introduction"
                    if entry.layout == "dialogue_intro_17_19"
                    else "Dialogue en jeu"
                ),
                offset_or_pointer=f"0x{entry.offset:06X}",
                script_line=str(entry.line),
                layout=entry.layout,
                speaker=speaker_from_text(entry.text),
                french_text=clean_source_text(entry.text),
                chinese_text=clean_source_text(chinese_text),
                english_intermediate=english_rom_text(source),
                alignment_confidence=alignment_confidence,
                translation_history=history,
                naturalized=(
                    "oui" if entry.offset in naturalized_offsets else "non"
                ),
                chinese_fidelity_corrected=(
                    "oui" if entry.offset in fidelity_offsets else "non"
                ),
            )
        )

    next_index = len(rows) + 1
    appended_references = set(APPENDED_RESTORATION_REFERENCES)
    restoration_items = [
        *sorted(
            (reference, text)
            for reference, text in RESTORED_DIALOGUES.items()
            if reference not in appended_references
        ),
        *(
            (reference, RESTORED_DIALOGUES[reference])
            for reference in APPENDED_RESTORATION_REFERENCES
        ),
    ]
    for relative_index, (reference, french_text) in enumerate(
        restoration_items
    ):
        removed_source = removed_sources.get(reference)
        source = removed_source or source_inventory.get(reference)
        if source is None:
            raise ValueError(
                f"0x{reference:06X}: source chinoise restaurée absente"
            )
        if removed_source is not None:
            english_text = (
                "ABSENT — dialogue supprimé de la ROM anglaise"
            )
        elif reference in COLLAPSED_ENGLISH_POINTER_REFERENCES:
            shared_text = english_rom_text(source)
            english_text = (
                "TEXTE MUTUALISÉ"
                + (
                    f" — texte affiché : {shared_text}"
                    if shared_text
                    else ""
                )
            )
        else:
            miswired_text = english_rom_text(source)
            english_text = (
                "POINTEUR ERRONÉ"
                + (f" — texte affiché : {miswired_text}" if miswired_text else "")
            )
        rows.append(
            ReviewRow(
                public_id=f"D{next_index + relative_index:04d}",
                stable_key=f"RESTORED:0x{reference:06X}",
                category="Dialogue restauré",
                offset_or_pointer=f"0x{reference:06X}",
                script_line="",
                layout="dialogue_19_19",
                speaker=speaker_from_text(french_text),
                french_text=clean_source_text(french_text),
                chinese_text=clean_source_text(source["chinese_text"]),
                english_intermediate=clean_source_text(english_text),
                alignment_confidence="source directe",
                translation_history=(
                    "restauré d'après le chinois + adapté d'après "
                    "Pokémon Jaune (FR)"
                    if reference in OFFICIAL_YELLOW_RESTORATION_REFERENCES
                    else (
                        "restauré d'après le chinois + adapté d'après "
                        "la devise française de l'anime"
                        if reference in ANIME_MOTTO_RESTORATION_REFERENCES
                        else (
                            "restauré d'après le chinois + "
                            "naturalisé en français"
                            if reference in naturalized_restoration_offsets
                            else "restauré d'après le chinois"
                        )
                    )
                ),
                naturalized=(
                    "oui"
                    if reference in naturalized_restoration_offsets
                    else "non"
                ),
                chinese_fidelity_corrected="oui",
            )
        )

    if len(rows) != 1055:
        raise ValueError(
            f"{len(rows)} dialogues exportés au lieu des 1055 attendus"
        )
    if len({row.public_id for row in rows}) != len(rows):
        raise ValueError("IDs publics non uniques")
    if len({row.stable_key for row in rows}) != len(rows):
        raise ValueError("clés techniques non uniques")
    return rows


def write_csv(path: Path, rows: list[ReviewRow]) -> None:
    fields = (
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
    )
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row.public_id,
                    "cle_stable": row.stable_key,
                    "categorie": row.category,
                    "offset_ou_pointeur": row.offset_or_pointer,
                    "ligne_script": row.script_line,
                    "layout": row.layout,
                    "intervenant": row.speaker,
                    "texte_francais": row.french_text,
                    "texte_chinois_source": row.chinese_text,
                    "traduction_anglaise_rom_anglaise": (
                        row.english_intermediate
                    ),
                    "confiance_alignement": row.alignment_confidence,
                    "historique_traduction": row.translation_history,
                    "naturalise": row.naturalized,
                    "corrige_d_apres_le_chinois": (
                        row.chinese_fidelity_corrected
                    ),
                    "votre_verdict": "",
                    "votre_commentaire": "",
                }
            )


def markdown_text(text: str, *, missing: str = "—") -> str:
    if not text:
        return missing
    escaped = html.escape(text, quote=False)
    return escaped.replace("|", "&#124;").replace("\n", "<br>")


def write_markdown(path: Path, rows: list[ReviewRow]) -> None:
    aligned = sum(bool(row.chinese_text) for row in rows)
    naturalized = sum(row.naturalized == "oui" for row in rows)
    restored = sum(row.category == "Dialogue restauré" for row in rows)
    lines = [
        "# Liste exhaustive des dialogues français",
        "",
        (
            f"Inventaire de **{len(rows)} dialogues** : "
            f"{len(rows) - restored} dialogues principaux, "
            f"dont 3 introductions, et {restored} dialogues restaurés "
            "depuis la ROM chinoise."
        ),
        "",
        (
            f"La source chinoise est directement alignée pour "
            f"**{aligned}/{len(rows)} dialogues**. Les "
            f"**{naturalized} dialogues** de la passe de naturalisation "
            "sont signalés dans la colonne « Historique »."
        ),
        "",
        (
            "Pour demander une correction, indique simplement l'ID et ta "
            "remarque, par exemple : `D0042 : formulation trop littérale`."
        ),
        "",
        (
            "Les retours à la ligne visibles dans une cellule correspondent "
            "aux changements de page explicitement imposés dans le texte."
        ),
        "",
        (
            "| ID | Type | Intervenant | Texte français | "
            "ROM anglaise | Source chinoise | Historique |"
        ),
        "|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    row.public_id,
                    markdown_text(row.category),
                    markdown_text(row.speaker),
                    markdown_text(row.french_text),
                    markdown_text(row.english_intermediate),
                    markdown_text(
                        row.chinese_text,
                        missing="Source non alignée automatiquement",
                    ),
                    markdown_text(row.translation_history),
                )
            )
            + " |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporte la table exhaustive de relecture des dialogues."
    )
    parser.add_argument("--script", type=Path, default=ROM_DIR / "script.py")
    parser.add_argument("--alignment", type=Path, default=DEFAULT_ALIGNMENT)
    parser.add_argument(
        "--source-inventory",
        type=Path,
        default=DEFAULT_SOURCE_INVENTORY,
    )
    parser.add_argument(
        "--removed-source",
        type=Path,
        default=DEFAULT_REMOVED_SOURCE,
    )
    parser.add_argument(
        "--fidelity-map",
        type=Path,
        default=DEFAULT_FIDELITY_MAP,
    )
    parser.add_argument(
        "--naturalization-map",
        type=Path,
        default=DEFAULT_NATURALIZATION_MAP,
    )
    parser.add_argument(
        "--official-yellow-map",
        type=Path,
        default=DEFAULT_OFFICIAL_YELLOW_MAP,
    )
    parser.add_argument(
        "--official-gen1-shared-map",
        type=Path,
        default=DEFAULT_OFFICIAL_GEN1_SHARED_MAP,
    )
    parser.add_argument(
        "--anime-motto-main-map",
        type=Path,
        default=DEFAULT_ANIME_MOTTO_MAIN_MAP,
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = build_rows(
        script_path=args.script,
        alignment_path=args.alignment,
        source_inventory_path=args.source_inventory,
        removed_source_path=args.removed_source,
        fidelity_map_path=args.fidelity_map,
        naturalization_map_path=args.naturalization_map,
        official_yellow_map_path=args.official_yellow_map,
        official_gen1_shared_map_path=args.official_gen1_shared_map,
        anime_motto_main_map_path=args.anime_motto_main_map,
    )
    write_csv(args.csv, rows)
    write_markdown(args.markdown, rows)
    print(f"Dialogues exportés : {len(rows)}")
    print(f"CSV : {args.csv}")
    print(f"Markdown : {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
