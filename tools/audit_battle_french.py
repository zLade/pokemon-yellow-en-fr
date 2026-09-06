#!/usr/bin/env python3
"""Audit the complete French battle vocabulary and the 177 move labels.

The Generation I spellings come from the exact French Pokémon Red/Blue
disassembly (``data/moves/names.asm``).  Its Game Boy battle renderer accepts
12 characters; the NES move picker only exposes 10.  ``GEN1_MOVE_LABELS``
therefore records both the official spelling and the deliberately shortened
NES spelling whenever the official one cannot fit.
"""

from __future__ import annotations

import argparse
import csv
import unicodedata
from dataclasses import dataclass
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOLS_DIR.parent

import sys

sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    TRAILING_SEPARATOR_OFFSETS,
    parse_patch_entries,
)


ENGLISH_ROM = ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
PATCH_SCRIPT = ROM_DIR / "script.py"
MOVE_POINTER_TABLE = 0x030F99
MOVE_POINTER_COUNT = 177
MOVE_BANK_FILE_BASE = 0x030010
MOVE_CPU_BASE = 0x8000
NES_MOVE_COLUMNS = 8
MOVE_LABEL_PLAN = ROM_DIR / "locales" / "fr-FR" / "move_labels_two_line.csv"


# index: (official French Red/Blue label, reviewed NES label)
GEN1_MOVE_LABELS: dict[int, tuple[str, str]] = {
    0: ("FLAMMECHE", "Flammèch"),
    2: ("POING DE FEU", "Poing Feu"),
    3: ("LANCE-FLAMME", "LanceFlam."),
    5: ("DEFLAGRATION", "Déflagr."),
    8: ("ECUME", "Écume"),
    9: ("PISTOLET A O", "Pistolet O"),
    11: ("BULLES D'O", "Bulles d'O"),
    13: ("PINCE-MASSE", "PinceMasse"),
    14: ("SURF", "Surf"),
    15: ("HYDROCANON", "Hydrocan"),
    17: ("CLAQUOIR", "Claquoir"),
    18: ("REPLI", "Repli"),
    19: ("ECLAIR", "Éclair"),
    22: ("POING-ECLAIR", "Poing-Écl."),
    23: ("TONNERRE", "Tonnerre"),
    26: ("FATAL-FOUDRE", "FatalFoud."),
    27: ("CAGE-ECLAIR", "CageÉclair"),
    28: ("VOL-VIE", "Vol-Vie"),
    29: ("MEGA-SANGSUE", "Méga-Sang."),
    31: ("FOUET LIANES", "FouetLiane"),
    32: ("TRANCH'HERBE", "TranchHerb"),
    35: ("LANCE-SOLEIL", "Lance-Sol."),
    38: ("POUDRE DODO", "PoudreDodo"),
    39: ("SPORE", "Spore"),
    40: ("PARA-SPORE", "Para-Spore"),
    44: ("POINGLACE", "Poinglace"),
    45: ("LASER GLACE", "LaserGlace"),
    46: ("BLIZZARD", "Blizzard"),
    50: ("TUNNEL", "Tunnel"),
    51: ("MASSD'OS", "Massd'Os"),
    52: ("SEISME", "Séisme"),
    53: ("OSMERANG", "Osmerang"),
    54: ("ABIME", "Abîme"),
    55: ("JET DE SABLE", "JetSable"),
    56: ("JET-PIERRES", "JetPierres"),
    59: ("EBOULEMENT", "Éboulem."),
    60: ("VAMPIRISME", "Vampir."),
    61: ("DOUBLE-DARD", "DoubleDard"),
    66: ("SECRETION", "Sécrét."),
    67: ("DARD-VENIN", "Dard-Venin"),
    68: ("PUREDPOIS", "Purédp."),
    69: ("ACIDE", "Acide"),
    72: ("DETRITUS", "Détritus"),
    74: ("GAZ TOXIK", "Gaz Toxik"),
    75: ("POUDRE TOXIK", "Poud.Toxik"),
    76: ("TOXIK", "Toxik"),
    77: ("BALAYAGE", "Balayage"),
    79: ("POING-KARATE", "PoingKarat"),
    80: ("DOUBLE PIED", "DoublePied"),
    82: ("MAWASHI GERI", "MawashiG."),
    84: ("FRAPPE ATLAS", "FrappAtlas"),
    91: ("PICPIC", "Picpic"),
    92: ("TORNADE", "Tornade"),
    94: ("CRU-AILE", "Cru-Aile"),
    96: ("VOL", "Vol"),
    97: ("BEC VRILLE", "Bec Vrille"),
    100: ("PIQUE", "Piqué"),
    101: ("CHOC MENTAL", "ChocMental"),
    102: ("RAFALE PSY", "Rafale Psy"),
    107: ("DEVOREVE", "Dévorêve"),
    109: ("HYPNOSE", "Hypnose"),
    110: ("REPOS", "Repos"),
    111: ("TELEPORT", "Téléport"),
    113: ("HATE", "Hâte"),
    114: ("LECHOUILLE", "Léchouil"),
    119: ("ONDE FOLIE", "Onde Folie"),
    121: ("DRACO-RAGE", "Draco-Rage"),
    128: ("MORSURE", "Morsure"),
    135: ("TREMPETTE", "Trempett"),
    137: ("CHARGE", "Charge"),
    138: ("GRIFFE", "Griffe"),
    139: ("ECRAS'FACE", "Écras'Face"),
    140: ("VIVE-ATTAQUE", "Vive-Att."),
    141: ("JACKPOT", "Jackpot"),
    143: ("COUPE", "Coupe"),
    144: ("METEORES", "Météores"),
    145: ("ECRASEMENT", "Écrasem"),
    148: ("CROC DE MORT", "CrocMort"),
    149: ("COUPE-VENT", "Coupe-Vent"),
    150: ("DAMOCLES", "Damoclès"),
    151: ("ULTRALASER", "Ultralas"),
    152: ("DESTRUCTION", "Destruct"),
    153: ("EXPLOSION", "Explos."),
    154: ("GUILLOTINE", "Guillot."),
    155: ("EMPAL'KORNE", "EmpalKorne"),
    156: ("BERCEUSE", "Berceuse"),
    157: ("GROBISOU", "Grobisou"),
    158: ("ULTRASON", "Ultrason"),
    159: ("DANSE-LAMES", "DanseLames"),
    160: ("RUGISSEMENT", "Rugisse-\nment"),
    162: ("BOUL'ARMURE", "BoulArmure"),
    163: ("ARMURE", "Armure"),
    164: ("MIMI-QUEUE", "Mimi-Queue"),
    166: ("BROUILLARD", "Brouill."),
    167: ("FLASH", "Flash"),
    168: ("REFLET", "Reflet"),
    169: ("SOIN", "Soin"),
    171: ("HURLEMENT", "Hurlemen"),
    172: ("CYCLONE", "Cyclone"),
    173: ("MORPHING", "Morphing"),
    175: ("FORCE", "Force"),
}


BATTLE_TEXT_EXPECTATIONS: dict[int, str] = {
    0x0301D7: "0000000000 sauvage apparaît !",
    0x0301EB: "En avant ! ",
    0x0301F0: "sauvage ",
    0x0301F9: " est K.O. !",
    0x030203: " EXP gagn. !",
    0x030210: "Vous prenez la fuite !",
    0x030221: "Sacha lance une ",
    0x03022A: "Oui ! ",
    0x030230: "000000000Oh non ! ",
    0x030242: " s'est libéré !",
    0x03024E: "00000000 est capturé !",
    0x030262: "0envoie ",
    0x03026D: "Fuite impossible !",
    0x030290: "Voler, c'est mal !",
    0x0302A9: "0000000000À toi !",
    0x0302BF: " utilise ",
    0x0302C5: "Coup normal !",
    0x0302CF: "0Peu efficace...",
    0x0302E4: "00Raté !",
    0x0302EE: " est empoisonné !",
    0x0302FA: " est intoxiqué !",
    0x030304: " est brûlé !",
    0x03030E: " est confus !",
    0x03031A: " est gelé !",
    0x030324: "000000 souffre du poison !",
    0x030341: " dort !",
    0x03034B: "0 brûle !",
    0x030364: "000 se blesse !",
    0x030373: "0000 est gelé !",
    0x030381: " souffre du poison !",
    0x030392: " a trop peur !",
    0x0303A1: " monte !",
    0x0303A9: " au maximum !",
    0x0303BC: "000000 baisse !",
    0x0303C8: " baisse fort !",
    0x0303D6: " au minimum !",
    0x030403: "Hein ?",
    0x030409: " évolue !",
    0x030417: "Bravo ! ",
    0x03041D: "Un ",
    0x030428: " apprend",
    0x03043F: "000000déjà 4 attaques !",
    0x030458: " veut apprendre ",
    0x03045F: "L'attaque ",
    0x030467: "Oui / Non",
    0x030479: "Quelle attaque ?",
    0x030485: "est oubliée !",
    0x03048C: " monte fort !",
    0x03049A: "000Attaque apprise :",
    0x0304AB: "00000000 n'apprend pas",
    0x0304C2: " rayonne !",
    0x0304CF: " se décharge !",
    0x0304DB: " creuse un trou !",
    0x0304E7: " frappe vite !",
    0x0304F1: " se concentre !",
    0x0304FB: " frappe à fond !",
    0x030505: " se concentre !",
    0x03050F: " frappe à fond !",
    0x030519: "cesse de se concentrer !",
    0x030523: " s'envole !",
    0x03052D: " se sacrifie !",
    0x030537: " se concentre !",
    0x030541: " libère sa force !",
    0x03054B: " prévoit un coup !",
    0x030555: " subit Prescience !",
    0x030567: " dévore le rêve de ",
    0x03056F: " !",
    0x030575: " enrage !",
    0x03057D: " maudit !",
    0x030588: "ATQ.",
    0x03058E: "Objet",
    0x030594: "PKMN",
    0x030599: "Fuite",
    0x0305E8: "Combat",
    0x0305F5: "   00Objet",
    0x030602: "Balle",
    0x030608: "00CT/CS ",
    0x030611: "ObjClé",
    0x030618: "00PUI :",
    0x030621: "Préc.",
    0x03062E: "Sauv. ",
    0x030634: " ",
    0x03063B: "Critique !",
    0x030646: "Changer de Pokémon ?",
    0x030659: "Oui Non",
    0x030660: "0000000000000Changer de Pokémon ?",
    0x03067D: "000Monte au niv. ",
    0x03068E: "0000000Statut inchangé !",
    0x03069F: ": Attaque",
    0x0306A6: ": Défense",
    0x0306AF: ": Atq.Spé",
    0x0306B5: ": Déf.Spé",
    0x0306BA: ": Vitesse",
    0x0306C0: ": Préc.",
    0x0306C9: "PV restaurés !",
    0x0306D7: " immobile !",
    0x0306E1: "K.O. en un coup !",
    0x0306EC: " s'est enfui !",
    0x0306F5: " ne peut pas fuir !",
    0x0306FE: " est guéri !",
    0x03070B: " se réveille !",
    0x030714: " n'est plus paralysé !",
    0x030720: " n'est plus brûlé !",
    0x03072D: "Confusion dissipée !",
    0x030738: " n'est plus gelé !",
    0x030744: " est guéri !",
    0x030750: " n'a plus peur !",
    0x03075C: "Reçu : ",
    0x030765: "Sacha perd ",
    0x03076B: "00Dresseur ",
    0x030775: "gagne !",
    0x0307B9: "\nRésiste au poison !",
    0x0307C4: "\nRésiste aux brûlures !",
    0x0307CF: "\nRésiste au gel !",
    0x0308C7: " Déchaîne !",
    0x030939: "Dégâts de recul !",
    0x03094A: " maudit !",
    0x030955: "00000000000000000PV restaurés !",
    0x030AB5: " EXP gagnés !",
    0x030ADB: "Sacha a vaincu\n",
    0x030AE5: "Lance Lutte !",
    0x035F05: " veut se battre !",
    0x03077A: "Requis : ",
    0x035F15: "est paralysé !",
    0x035F23: "Super efficace !",
    0x035F3D: "Résultat : ",
    0x035F57: "a évolué en ",
    0x035F65: "Évolution annulée !",
    0x035F75: " veut apprendre",
    0x035F98: "Oublier une attaque ?",
    0x035FAE: "Oublier ",
    0x035FB6: "Adversaire : ",
    0x03651B: " s'est endormi !",
    0x03650D: "est paralysé !",
}


# CT/CS and "déjà" keep fixed-field padding, not a separator before a
# runtime-inserted word.
REQUIRED_TRAILING_SEPARATORS = frozenset(
    offset
    for offset, text in BATTLE_TEXT_EXPECTATIONS.items()
    if text.endswith(" ") and offset not in {0x030608, 0x03068E}
)


@dataclass(frozen=True)
class BattleAudit:
    move_labels: tuple[str, ...]
    official_gen1_count: int
    abbreviated_gen1_count: int
    two_line_count: int
    battle_text_count: int


def _load_move_label_plan(
    path: Path = MOVE_LABEL_PLAN,
) -> dict[int, tuple[str, str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        expected = {"move_index", "full_name", "line_1", "line_2"}
        if reader.fieldnames is None or set(reader.fieldnames) != expected:
            raise ValueError(
                f"plan deux lignes invalide: {reader.fieldnames!r}"
            )
        result: dict[int, tuple[str, str, str]] = {}
        for line_number, row in enumerate(reader, start=2):
            index = int(row["move_index"], 10)
            if index in result or not 0 <= index < MOVE_POINTER_COUNT:
                raise ValueError(
                    f"plan deux lignes, ligne {line_number}: index {index}"
                )
            full_name = row["full_name"]
            line_1 = row["line_1"]
            line_2 = row["line_2"]
            if (
                not full_name
                or not line_1
                or not line_2
                or len(line_1) > NES_MOVE_COLUMNS
                or len(line_2) > NES_MOVE_COLUMNS
            ):
                raise ValueError(
                    f"plan deux lignes, ligne {line_number}: largeur invalide"
                )
            result[index] = (full_name, line_1, line_2)
    return result


def _record_start(rom: bytes, target: int) -> int:
    previous = rom.rfind(b"\r", 0, target)
    return target if previous < MOVE_POINTER_TABLE else previous + 1


def _move_label(
    rom: bytes,
    target: int,
    translations: dict[int, str],
) -> str:
    if target in translations:
        return translations[target].rstrip(" ")

    start = _record_start(rom, target)
    translated = translations.get(start)
    if translated is not None:
        delta = target - start
        if delta and translated.startswith("0" * delta):
            translated = translated[delta:]
        return translated.rstrip(" ")

    end = rom.index(b"\r", target)
    payload = rom[target:end]
    if any(value < 0x20 or value > 0x7E for value in payload):
        raise ValueError(
            f"capacité graphique non traduite à 0x{target:06X}"
        )
    return payload.decode("ascii").rstrip(" ")


def _ascii_fold(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
    )


def audit(
    *,
    english_rom: Path = ENGLISH_ROM,
    patch_script: Path = PATCH_SCRIPT,
    move_label_plan: Path = MOVE_LABEL_PLAN,
) -> BattleAudit:
    rom = english_rom.read_bytes()
    two_line = _load_move_label_plan(move_label_plan)
    translations = {
        entry.offset: entry.text
        for entry in parse_patch_entries(
            patch_script,
            apply_dialogue_inventory=False,
        )
    }

    labels: list[str] = []
    for index in range(MOVE_POINTER_COUNT):
        pointer_offset = MOVE_POINTER_TABLE + index * 2
        pointer = int.from_bytes(
            rom[pointer_offset:pointer_offset + 2], "little"
        )
        target = MOVE_BANK_FILE_BASE + pointer - MOVE_CPU_BASE
        label = _move_label(rom, target, translations)
        if not label:
            raise ValueError(f"capacité {index:03d}: libellé vide")
        if index not in two_line and len(label) > NES_MOVE_COLUMNS:
            raise ValueError(
                f"capacité {index:03d}: {label!r} occupe {len(label)} "
                f"cases, maximum {NES_MOVE_COLUMNS}"
            )
        if index in two_line:
            _full_name, line_1, line_2 = two_line[index]
            labels.append(f"{line_1}\n{line_2}")
        else:
            labels.append(label)

    if len(labels) != MOVE_POINTER_COUNT:
        raise ValueError(
            f"{len(labels)} capacités résolues, {MOVE_POINTER_COUNT} attendues"
        )

    for index, (official, expected) in GEN1_MOVE_LABELS.items():
        actual = labels[index]
        semantic = two_line.get(index, (actual, "", ""))[0]
        if index not in two_line and actual != expected:
            raise ValueError(
                f"capacité Gen 1 {index:03d}: {actual!r}, attendu "
                f"{expected!r} d'après {official!r}"
            )
        if index in two_line:
            if _ascii_fold(semantic) != _ascii_fold(official):
                raise ValueError(
                    f"capacité Gen 1 {index:03d}: nom deux lignes "
                    f"{semantic!r}, attendu {official!r}"
                )
        elif len(official) <= NES_MOVE_COLUMNS:
            folded_official = _ascii_fold(official)
            folded_actual = _ascii_fold(actual)
            if folded_actual != folded_official:
                raise ValueError(
                    f"capacité Gen 1 {index:03d}: le nom officiel "
                    f"{official!r} tient en entier mais devient {actual!r}"
                )

    for offset, expected in BATTLE_TEXT_EXPECTATIONS.items():
        actual = translations.get(offset)
        if actual != expected:
            raise ValueError(
                f"texte de combat 0x{offset:06X}: {actual!r}, "
                f"attendu {expected!r}"
            )

    missing_separators = sorted(
        REQUIRED_TRAILING_SEPARATORS - TRAILING_SEPARATOR_OFFSETS
    )
    if missing_separators:
        raise ValueError(
            "séparateurs dynamiques non protégés : "
            + ", ".join(f"0x{x:06X}" for x in missing_separators)
        )

    abbreviated = sum(
        index not in two_line and len(official) > NES_MOVE_COLUMNS
        for index, (official, _expected) in GEN1_MOVE_LABELS.items()
    )
    return BattleAudit(
        move_labels=tuple(labels),
        official_gen1_count=len(GEN1_MOVE_LABELS),
        abbreviated_gen1_count=abbreviated,
        two_line_count=len(two_line),
        battle_text_count=len(BATTLE_TEXT_EXPECTATIONS),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--english-rom", type=Path, default=ENGLISH_ROM)
    parser.add_argument("--script", type=Path, default=PATCH_SCRIPT)
    parser.add_argument(
        "--move-label-plan",
        type=Path,
        default=MOVE_LABEL_PLAN,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = audit(
        english_rom=args.english_rom,
        patch_script=args.script,
        move_label_plan=args.move_label_plan,
    )
    print(
        "BATTLE_FRENCH_AUDIT_OK "
        f"moves={len(result.move_labels)} "
        f"gen1_official={result.official_gen1_count} "
        f"gen1_shortened={result.abbreviated_gen1_count} "
        f"two_line={result.two_line_count} "
        f"battle_texts={result.battle_text_count} "
        f"max_columns={NES_MOVE_COLUMNS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
