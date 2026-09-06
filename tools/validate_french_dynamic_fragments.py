#!/usr/bin/env python3
"""Validate live French pointer fragments independently of the repacker.

The mapper-163 battle engine concatenates many pointer payloads with a
runtime Pokémon, trainer, move, item or amount.  A lost leading/trailing blank
is therefore a visible grammar bug even when the relocated payload itself is
otherwise valid.  This catalogue pins the exact bytes reached by every
reviewed dynamic pointer and the distinct item-help/acquisition variants.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    offset_for_cpu_addr,
    pair_for_offset,
)
from tools.dialogue_layout import format_game_text  # noqa: E402


# Pointer reference -> exact payload beginning at the live target.  Spaces and
# 0x0A controls at either edge are intentional data and must not be stripped
# by the allocator.
DYNAMIC_FRAGMENT_EXPECTATIONS: dict[int, str] = {
    0x03002D: "Un ",
    0x03002F: " sauvage apparaît !",
    0x030031: "En avant ! ",
    0x030033: "sauvage ",
    0x030035: " est K.O. !",
    0x030037: " EXP gagnés !",
    0x03003B: "Sacha lance une ",
    0x03003D: "Oui ! ",
    0x03003F: " est capturé !",
    0x030041: "Oh non ! ",
    0x030043: " s'est libéré !",
    0x030045: " veut se battre !",
    0x030047: "envoie ",
    0x030049: "Fuite impossible !",
    0x03004B: "Sacha a vaincu\n",
    0x03004D: "Résultat : ",
    0x030051: "Voler, c'est mal !",
    0x030055: " utilise ",
    0x03005B: "Peu efficace...",
    0x03005F: " est empoisonné !",
    0x030061: " s'est endormi !",
    0x030063: "est paralysé !",
    0x030065: " est brûlé !",
    0x030067: " est confus !",
    0x030069: " est gelé !",
    0x03006B: " est intoxiqué !",
    0x03006D: " a peur !",
    0x03006F: " souffre du poison !",
    0x030071: " dort !",
    0x030073: "est paralysé !",
    0x030075: " brûle !",
    0x030077: " se blesse !",
    0x030079: " est gelé !",
    0x03007B: " souffre du poison !",
    0x03007D: " a trop peur !",
    0x03007F: " monte !",
    0x030081: " monte fort !",
    0x030083: " au maximum !",
    0x030085: " baisse !",
    0x030087: " baisse fort !",
    0x030089: " au minimum !",
    0x030097: " évolue !",
    0x030099: "Bravo ! ",
    0x03009B: "a évolué en ",
    0x0300A1: " veut apprendre",
    0x0300A3: "...!",
    0x0300A5: "Mais il connaît",
    0x0300A7: "déjà 4 attaques !",
    0x0300A9: " veut apprendre ",
    0x0300AB: "Oublier une attaque ?",
    0x0300AD: "Oui / Non",
    0x0300AF: "Quelle attaque ?",
    0x0300B1: "L'attaque ",
    0x0300B3: "est oubliée !",
    0x0300B5: "Attaque apprise :",
    0x0300B7: "Oublier ",
    0x0300B9: " ?",
    0x0300BB: " n'apprend pas",
    0x0300BD: " rayonne !",
    0x0300BF: " se décharge !",
    0x0300C1: " creuse un trou !",
    0x0300C3: " frappe vite !",
    0x0300C5: " se concentre !",
    0x0300C7: " frappe à fond !",
    0x0300C9: " se concentre !",
    0x0300CB: " frappe à fond !",
    0x0300CD: "cesse de se concentrer !",
    0x0300CF: " s'envole !",
    0x0300D1: " se sacrifie !",
    0x0300D3: " se concentre !",
    0x0300D5: " libère sa force !",
    0x0300D7: " prévoit un coup !",
    0x0300D9: " subit Prescience !",
    0x0300DB: " dévore le rêve de ",
    0x0300DD: " !",
    0x0300DF: " enrage !",
    0x0300E1: " maudit !",
    0x030123: "Sauv. ",
    0x030125: " ",
    0x03012D: "Adversaire : ",
    0x030131: "Monte au niv. ",
    0x030135: "Statut inchangé !",
    0x030145: " immobile !",
    0x030149: " s'est enfui !",
    0x03014B: " ne peut pas fuir !",
    0x03014D: " est guéri !",
    0x03014F: " se réveille !",
    0x030151: " n'est plus paralysé !",
    0x030153: " n'est plus brûlé !",
    0x030157: " n'est plus gelé !",
    0x030159: " est guéri !",
    0x03015B: " n'a plus peur !",
    0x03015D: "Reçu : ",
    0x03015F: "Sacha perd ",
    0x030161: "Dresseur ",
    0x030165: "Requis : ",
    0x030173: "\nRésiste au poison !",
    0x030175: "\nRésiste aux brûlures !",
    0x030177: "\nRésiste au gel !",
    0x0301A9: " Déchaîne !",
    0x0301AB: " maudit !",
}


# Distinct pointer slots that the 2015 English base incorrectly collapsed or
# mislabeled.  These assertions bind runtime topology to the reviewed French
# wording rather than merely checking a source dictionary.
SEMANTIC_POINTER_EXPECTATIONS: dict[int, str] = {
    0x031971: "CapturePokémon",
    0x031973: "Mieux  qu'une PokéB.",
    0x031975: "Mieux  qu'une SuperB.",
    0x0348FD: "Huile reçue !",
    0x0348FF: "Huile Max reçue !",
}


# The battle bag renderer reserves eight cells for an item label and writes
# its two-digit quantity immediately afterwards.  Seven printable cells leave
# the eighth cell blank, preventing joins such as ``Sup.Pot.01``.  The whole
# 40-entry pointer table is pinned: testing a sample would miss fixed targets
# such as the stock eight-cell ``Antidote`` record.
ITEM_LIST_NAME_EXPECTATIONS: dict[int, str] = {
    0x03164B: "PokéB.",
    0x03164D: "SuperB.",
    0x03164F: "HyperB.",
    0x031651: "MasterB",
    0x031653: "Potion",
    0x031655: "Sup.Pot",
    0x031657: "Hyp.Pot",
    0x031659: "Max.Pot",
    0x03165B: "Antid.",
    0x03165D: "AntiPa",
    0x03165F: "Réveil",
    0x031661: "Antigel",
    0x031663: "AntBrûl",
    0x031665: "TotSoin",
    0x031667: "Rappel",
    0x031669: "Huile",
    0x03166B: "HuilMax",
    0x03166D: "SupBonb",
    0x03166F: "P.Feu",
    0x031671: "P.Eau",
    0x031673: "P.Fdr",
    0x031675: "P.Plte",
    0x031677: "P.Lune",
    0x031679: "Colis",
    0x03167B: "Pokédex",
    0x03167D: "Carte",
    0x03167F: "Nautile",
    0x031681: "F.Dôme",
    0x031683: "PassBat",
    0x031685: "EauFr.",
    0x031687: "Sc.Sylp",
    0x031689: "PokFlût",
    0x03168B: "DentOr",
    0x03168D: "CléSec.",
    0x03168F: "Cpe CS",
    0x031691: "Vol CS",
    0x031693: "Surf CS",
    0x031695: "ForceCS",
    0x031697: "FlashCS",
    0x031699: "CT 01",
}
ITEM_LIST_NAME_MAX_CELLS = 7


# Runtime evidence fixes two limits for the stock combat message window:
# 25 glyphs remain inside the visible border, while the original routine
# clears only 24 before the following message.  The reviewed builder expands
# that clear to all 25 cells (columns 4..28, never the border/prompt column29).
# The categories below cover every live/reviewed dynamic pointer; dead table
# entries remain byte-checked but are not promoted to executable callsites.
BATTLE_VISIBLE_BORDER_CELLS = 25
BATTLE_STOCK_ARTIFACT_FREE_CELLS = 24
BATTLE_ARTIFACT_FREE_CELLS = 25
POKEMON_NAME_MAX_CELLS = 10
MOVE_NAME_MAX_CELLS = 10
TRAINER_NAME_MAX_CELLS = 10
BADGE_NAME_MAX_CELLS = 13

NAME_SUFFIX_REFS = frozenset(
    {0x030035, 0x030055, 0x030097, 0x0300A1, 0x0300BB}
)
STATUS_LINE2_REFS = frozenset(
    {0x03005F, 0x030061, 0x030063, 0x030065, 0x030067,
     0x030069, 0x03006B, 0x03006D}
)
ROW2_PAYLOAD_REFS = frozenset(
    {
        0x03006F, 0x030071, 0x030073, 0x030075, 0x030077, 0x030079,
        0x03007B, 0x03007D,
        0x0300BD, 0x0300BF, 0x0300C1, 0x0300C3, 0x0300C5,
        0x0300C7, 0x0300C9, 0x0300CB, 0x0300CD, 0x0300CF,
        0x0300D1, 0x0300D3, 0x0300D5, 0x0300D7, 0x0300D9,
        0x0300DF, 0x0300E1,
        0x030135,
        0x030145, 0x030149, 0x03014B, 0x03014D, 0x03014F,
        0x030151, 0x030153, 0x030157, 0x030159, 0x03015B,
        0x0301A9, 0x0301AB,
    }
)
STAT_SUFFIX_REFS = frozenset(
    {0x03007F, 0x030081, 0x030083,
     0x030085, 0x030087, 0x030089}
)
# $C2E2 renders ref A5 on row 1; $C2F5 then explicitly resets the
# cursor to $2324 before rendering ref A7 on row 2.
LEARN_LIMIT_TWO_ROW_REFS = frozenset({0x0300A5, 0x0300A7})
PREFIX_FIELD_MAX: dict[int, int] = {
    0x030031: POKEMON_NAME_MAX_CELLS,
    0x030033: POKEMON_NAME_MAX_CELLS,
    0x03003B: ITEM_LIST_NAME_MAX_CELLS,
    0x03004B: TRAINER_NAME_MAX_CELLS,
    0x030099: POKEMON_NAME_MAX_CELLS,
    0x030123: POKEMON_NAME_MAX_CELLS,
    0x030131: 3,
    0x03015D: 10,
    0x03015F: 5,
    0x030161: TRAINER_NAME_MAX_CELLS,
    0x030165: BADGE_NAME_MAX_CELLS,
}
MULTI_ROW_REFS = frozenset(
    {
        0x03002D, 0x03002F,
        0x03003D, 0x03003F,
        0x030041, 0x030043,
        0x030047, 0x03009B, 0x0300B5,
    }
)
# $C229 renders ref B1 plus the old move on row 1; $C243 resets to row 2
# before rendering the autonomous confirmation at ref B3.
FORGET_MOVE_TWO_ROW_REFS = frozenset({0x0300B1, 0x0300B3})
SEPARATE_ROW_REFS = frozenset(
    {
        0x030037, 0x030045, 0x03004D, 0x03012D,
        0x030173, 0x030175, 0x030177,
    }
)
DEAD_UNREFERENCED_REFS = frozenset(
    {0x0300A9, 0x0300AD, 0x0300DB, 0x0300DD}
)
CONTROL_COMPONENT_REFS = frozenset({0x0300A3, 0x0300B7, 0x0300B9, 0x030125})
STANDALONE_MESSAGE_REFS = frozenset(
    {0x030049, 0x030051, 0x03005B, 0x0300AB, 0x0300AF}
)
NEWLINE_CONTROL_REFS = frozenset(
    {0x03004B, 0x030173, 0x030175, 0x030177}
)

DYNAMIC_LAYOUT_CLASSIFIED_REFS = frozenset().union(
    NAME_SUFFIX_REFS,
    STATUS_LINE2_REFS,
    ROW2_PAYLOAD_REFS,
    STAT_SUFFIX_REFS,
    LEARN_LIMIT_TWO_ROW_REFS,
    PREFIX_FIELD_MAX,
    MULTI_ROW_REFS,
    FORGET_MOVE_TWO_ROW_REFS,
    SEPARATE_ROW_REFS,
    DEAD_UNREFERENCED_REFS,
    CONTROL_COMPONENT_REFS,
    STANDALONE_MESSAGE_REFS,
)
LIVE_DYNAMIC_LAYOUT_REFS = (
    DYNAMIC_LAYOUT_CLASSIFIED_REFS - DEAD_UNREFERENCED_REFS
)


def _payload_length(reference: int) -> int:
    return len(format_game_text(DYNAMIC_FRAGMENT_EXPECTATIONS[reference]))


def dynamic_layout_composed_max(reference: int) -> int | None:
    """Return the worst physical-row width for one reviewed callsite."""
    length = _payload_length(reference)
    if reference in DEAD_UNREFERENCED_REFS:
        return None
    if reference in STANDALONE_MESSAGE_REFS:
        return length
    if reference in NAME_SUFFIX_REFS:
        indent = 1 if reference == 0x030035 else 0
        return indent + POKEMON_NAME_MAX_CELLS + length
    if reference in STATUS_LINE2_REFS:
        # Normal status application: actor is row 1, event payload is row 2.
        # The already-present branches are diverted to autonomous ref 0x135.
        return length
    if reference in ROW2_PAYLOAD_REFS:
        return length
    if reference in STAT_SUFFIX_REFS:
        return 9 + length  # longest live French stat label
    if reference in LEARN_LIMIT_TWO_ROW_REFS:
        return max(_payload_length(item) for item in LEARN_LIMIT_TWO_ROW_REFS)
    if reference in PREFIX_FIELD_MAX:
        if reference == 0x03003B:
            # Ball name is explicitly reset to row 2 after this row-1 prefix.
            return max(length, PREFIX_FIELD_MAX[reference])
        if reference == 0x03004B:
            # The explicit final 0x0A moves the following trainer to row 2.
            return max(length - 1, PREFIX_FIELD_MAX[reference])
        return length + PREFIX_FIELD_MAX[reference]
    if reference in {0x03002D, 0x03002F}:
        return max(
            _payload_length(0x03002D) + POKEMON_NAME_MAX_CELLS,
            _payload_length(0x03002F),
        )
    if reference in {0x03003D, 0x03003F}:
        return max(
            _payload_length(0x03003D) + POKEMON_NAME_MAX_CELLS,
            _payload_length(0x03003F),
        )
    if reference in {0x030041, 0x030043}:
        return max(
            _payload_length(0x030041) + POKEMON_NAME_MAX_CELLS,
            _payload_length(0x030043),
        )
    if reference == 0x030047:
        return length + POKEMON_NAME_MAX_CELLS
    if reference == 0x03009B:
        return length + POKEMON_NAME_MAX_CELLS
    if reference in FORGET_MOVE_TWO_ROW_REFS:
        return max(
            _payload_length(0x0300B1) + MOVE_NAME_MAX_CELLS,
            _payload_length(0x0300B3),
        )
    if reference == 0x0300B5:
        return max(length, MOVE_NAME_MAX_CELLS)
    if reference == 0x030037:
        return 5 + length  # maximum experience amount on row 2
    if reference in {0x030045, 0x03004D}:
        return length
    if reference == 0x03012D:
        return max(length, POKEMON_NAME_MAX_CELLS)
    if reference in {0x030173, 0x030175, 0x030177}:
        return max(
            POKEMON_NAME_MAX_CELLS,
            length - 1,  # leading 0x0A is a control, not a glyph
        )
    if reference == 0x0300B7:
        return (
            length
            + MOVE_NAME_MAX_CELLS
            + _payload_length(0x0300B9)
        )
    if reference == 0x0300B9:
        return (
            _payload_length(0x0300B7)
            + MOVE_NAME_MAX_CELLS
            + length
        )
    if reference == 0x0300A3:
        return MOVE_NAME_MAX_CELLS + length
    if reference == 0x030125:
        return length + POKEMON_NAME_MAX_CELLS
    raise KeyError(f"référence dynamique non classée 0x{reference:06X}")


def validate_dynamic_layout_catalogue() -> list[str]:
    """Gate every reviewed dynamic composition at 25 artifact-free cells."""
    errors: list[str] = []
    expected_refs = set(DYNAMIC_FRAGMENT_EXPECTATIONS)
    if DYNAMIC_LAYOUT_CLASSIFIED_REFS != expected_refs:
        missing = sorted(expected_refs - DYNAMIC_LAYOUT_CLASSIFIED_REFS)
        extra = sorted(DYNAMIC_LAYOUT_CLASSIFIED_REFS - expected_refs)
        if missing:
            errors.append(
                "références dynamiques non classées: "
                + ", ".join(f"0x{ref:06X}" for ref in missing)
            )
        if extra:
            errors.append(
                "références dynamiques classées en trop: "
                + ", ".join(f"0x{ref:06X}" for ref in extra)
            )

    for reference, text in sorted(DYNAMIC_FRAGMENT_EXPECTATIONS.items()):
        payload = format_game_text(text)
        newline_count = payload.count(0x0A)
        if newline_count > 1:
            errors.append(
                f"0x{reference:06X}: {newline_count} retours ligne; "
                "la fenêtre n'a que deux rangs"
            )
        if newline_count and reference not in NEWLINE_CONTROL_REFS:
            errors.append(
                f"0x{reference:06X}: retour ligne interdit à ce callsite"
            )
        if reference in NEWLINE_CONTROL_REFS and newline_count != 1:
            errors.append(
                f"0x{reference:06X}: retour ligne contrôlé absent"
            )
        if reference in ROW2_PAYLOAD_REFS and newline_count:
            errors.append(
                f"0x{reference:06X}: troisième rang interdit depuis ligne 2"
            )
        for line_number, line in enumerate(payload.split(b"\x0A"), start=1):
            if len(line) > BATTLE_ARTIFACT_FREE_CELLS:
                errors.append(
                    f"0x{reference:06X}: ligne {line_number} de "
                    f"{len(line)} cases, maximum "
                    f"{BATTLE_ARTIFACT_FREE_CELLS}"
                )
        try:
            composed = dynamic_layout_composed_max(reference)
        except KeyError as exc:
            errors.append(str(exc))
            continue
        if (
            composed is not None
            and composed > BATTLE_ARTIFACT_FREE_CELLS
        ):
            errors.append(
                f"0x{reference:06X}: composition maximale de {composed} "
                f"cases, maximum {BATTLE_ARTIFACT_FREE_CELLS} sans artefact"
            )
    return errors


def maximum_live_composition_cells() -> int:
    """Return the largest reviewed live composition after all splits."""
    widths = (
        dynamic_layout_composed_max(reference)
        for reference in LIVE_DYNAMIC_LAYOUT_REFS
    )
    return max(width for width in widths if width is not None)


def payload_at_pointer(rom: bytes, reference: int) -> tuple[int, bytes]:
    if reference < 16 or reference + 2 > len(rom):
        raise ValueError(f"référence hors ROM 0x{reference:06X}")
    word = int.from_bytes(rom[reference:reference + 2], "little")
    target = offset_for_cpu_addr(
        pair_for_offset(reference),
        word,
        len(rom),
    )
    if target is None:
        raise ValueError(
            f"0x{reference:06X}: pointeur CPU 0x{word:04X} invalide"
        )
    end = rom.find(b"\x0D", target, min(len(rom), target + 512))
    if end < 0:
        raise ValueError(
            f"0x{reference:06X}: terminateur absent après 0x{target:06X}"
        )
    return target, rom[target:end]


def validate_dynamic_fragments(rom: bytes) -> list[str]:
    errors = validate_dynamic_layout_catalogue()
    catalogues = (
        ("fragment dynamique", DYNAMIC_FRAGMENT_EXPECTATIONS),
        ("variante sémantique", SEMANTIC_POINTER_EXPECTATIONS),
        ("nom d'objet de liste", ITEM_LIST_NAME_EXPECTATIONS),
    )
    for label, expectations in catalogues:
        for reference, text in sorted(expectations.items()):
            expected = format_game_text(text)
            try:
                target, actual = payload_at_pointer(rom, reference)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if actual != expected:
                errors.append(
                    f"0x{reference:06X} -> 0x{target:06X}: {label} "
                    f"{actual!r}, attendu {expected!r}"
                )
            if (
                reference in ITEM_LIST_NAME_EXPECTATIONS
                and len(expected) > ITEM_LIST_NAME_MAX_CELLS
            ):
                errors.append(
                    f"0x{reference:06X}: nom d'objet de {len(expected)} "
                    f"cases, maximum {ITEM_LIST_NAME_MAX_CELLS} avant quantité"
                )
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rom_path = args.rom if args.rom.is_absolute() else ROM_DIR / args.rom
    rom = rom_path.read_bytes()
    errors = validate_dynamic_fragments(rom)
    print("Validation fragments dynamiques FR")
    print(f"- ROM : {rom_path}")
    print(
        "- Fragments dynamiques : "
        f"{len(DYNAMIC_FRAGMENT_EXPECTATIONS)}"
    )
    print(
        "- Variantes sémantiques : "
        f"{len(SEMANTIC_POINTER_EXPECTATIONS)}"
    )
    print(
        "- Noms d'objets bornés avant quantité : "
        f"{len(ITEM_LIST_NAME_EXPECTATIONS)}"
    )
    print(
        "- Pointeurs dynamiques classés / callsites vivants bornés : "
        f"{len(DYNAMIC_LAYOUT_CLASSIFIED_REFS)} / "
        f"{len(LIVE_DYNAMIC_LAYOUT_REFS)} "
        f"(max réel {maximum_live_composition_cells()}, "
        f"limite {BATTLE_ARTIFACT_FREE_CELLS})"
    )
    print(f"- Erreurs : {len(errors)}")
    for error in errors[:50]:
        print(f"  {error}")
    if len(errors) > 50:
        print(f"  ... et {len(errors) - 50} de plus")
    print(f"- Résultat : {'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
