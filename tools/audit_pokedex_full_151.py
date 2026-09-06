#!/usr/bin/env python3
"""Audit the 151 descriptions reachable from the Kanto Pokédex UI.

The English ROM stores the description pointer table at file offset 0x3201E.
Pointers are little-endian CPU addresses in the PRG window whose matching file
offset is ``pointer + 0x28010``.  The Kanto UI stops after entry 151; eight
additional pointers follow it but are outside that UI range.

This tool is deliberately read-only with respect to ``script.py`` and the ROM.
It writes a reproducible JSON report containing the current source, the
species actually selected by the UI, and a concise canonical French proposal
validated through the real ``pokedex_13x4`` wrapper.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.dialogue_layout import semantic_units, wrap_pokedex_lines  # noqa: E402
from tools.french_font import encode_game_text  # noqa: E402


DEFAULT_ROM = ROOT / "Pokemon Yellow English 9-23-2015.nes"
DEFAULT_SCRIPT = ROOT / "script.py"
DEFAULT_CSV = ROOT / "traduction_base.csv"
DEFAULT_OUTPUT = ROOT / "build" / "audits" / "pokedex_full_151_audit.json"

POINTER_TABLE_OFFSET = 0x3201E
POINTER_FILE_BIAS = 0x28010
NAME_POINTER_TABLE_OFFSET = 0x30977
KANTO_COUNT = 151
EXTENDED_POINTER_COUNT = 8


SPECIES = (
    "Bulbizarre", "Herbizarre", "Florizarre", "Salamèche", "Reptincel",
    "Dracaufeu", "Carapuce", "Carabaffe", "Tortank", "Chenipan",
    "Chrysacier", "Papilusion", "Aspicot", "Coconfort", "Dardargnan",
    "Roucool", "Roucoups", "Roucarnage", "Rattata", "Rattatac",
    "Piafabec", "Rapasdepic", "Abo", "Arbok", "Pikachu", "Raichu",
    "Sabelette", "Sablaireau", "Nidoran♀", "Nidorina", "Nidoqueen",
    "Nidoran♂", "Nidorino", "Nidoking", "Mélofée", "Mélodelfe",
    "Goupix", "Feunard", "Rondoudou", "Grodoudou", "Nosferapti",
    "Nosferalto", "Mystherbe", "Ortide", "Rafflesia", "Paras",
    "Parasect", "Mimitoss", "Aéromite", "Taupiqueur", "Triopikeur",
    "Miaouss", "Persian", "Psykokwak", "Akwakwak", "Férosinge",
    "Colossinge", "Caninos", "Arcanin", "Ptitard", "Têtarte", "Tartard",
    "Abra", "Kadabra", "Alakazam", "Machoc", "Machopeur", "Mackogneur",
    "Chétiflor", "Boustiflor", "Empiflor", "Tentacool", "Tentacruel",
    "Racaillou", "Gravalanch", "Grolem", "Ponyta", "Galopa", "Ramoloss",
    "Flagadoss", "Magnéti", "Magnéton", "Canarticho", "Doduo", "Dodrio",
    "Otaria", "Lamantine", "Tadmorv", "Grotadmorv", "Kokiyas",
    "Crustabri", "Fantominus", "Spectrum", "Ectoplasma", "Onix",
    "Soporifik", "Hypnomade", "Krabby", "Krabboss", "Voltorbe",
    "Électrode", "Noeunoeuf", "Noadkoko", "Osselait", "Ossatueur",
    "Kicklee", "Tygnon", "Excelangue", "Smogo", "Smogogo", "Rhinocorne",
    "Rhinoféros", "Leveinard", "Saquedeneu", "Kangourex", "Hypotrempe",
    "Hypocéan", "Poissirène", "Poissoroy", "Stari", "Staross", "M. Mime",
    "Insécateur", "Lippoutou", "Élektek", "Magmar", "Scarabrute",
    "Tauros", "Magicarpe", "Léviator", "Lokhlass", "Métamorph", "Évoli",
    "Aquali", "Voltali", "Pyroli", "Porygon", "Amonita", "Amonistar",
    "Kabuto", "Kabutops", "Ptéra", "Ronflex", "Artikodin", "Électhor",
    "Sulfura", "Minidraco", "Draco", "Dracolosse", "Mewtwo", "Mew",
)


PROPOSALS = (
    "Il stocke de l'énergie dans le bulbe de son dos.",
    "Le bulbe sur son dos a un doux parfum.",
    "Il cherche la lumière pour obtenir de l'énergie.",
    "Sous la pluie, sa queue produit de la vapeur.",
    "Il crache du feu bleu et blanc en colère.",
    "Son feu peut faire fondre les rochers.",
    "Il rentre dans sa carapace face au danger.",
    "Ses oreilles gardent son équilibre en nageant.",
    "Ce Pokémon brutal a de puissants jets dorsaux.",
    "Ses ventouses lui servent à grimper aux arbres.",
    "Sa carapace protège son corps fragile.",
    "Ses ailes étanches lui font braver la pluie.",
    "Il se cache dans l'herbe pour manger des feuilles.",
    "Il sort son dard pour empoisonner ses ennemis.",
    "Ses trois dards injectent un poison.",
    "Il projette du sable pour se protéger.",
    "Il vole sans cesse en quête de proies.",
    "Il rase l'eau pour chasser un Magicarpe.",
    "Très commun, il vit en groupes de quarante.",
    "Il nage et chasse avec ses pattes palmées.",
    "Il mange des insectes dans l'herbe et vole vite.",
    "Ses ailes immenses le portent sans repos.",
    "Il mange les oeufs des Pokémon oiseaux.",
    "Ses motifs ventraux avertissent ses ennemis.",
    "Réunis, ils peuvent causer un orage.",
    "Sa queue évacue les décharges dans le sol.",
    "Il vit dans les lieux arides loin de l'eau.",
    "Ses griffes cassées repoussent en un jour.",
    "Ses piquants venimeux le rendent dangereux.",
    "Il préfère les attaques au contact et les morsures.",
    "Son gabarit permet des attaques puissantes.",
    "Face au danger, il attaque avec ses cornes.",
    "Agressif, il attaque sans hésiter.",
    "Sa queue brise les os de ses proies.",
    "Rare, il a beaucoup d'admirateurs",
    "Timide, il fuit dès qu'il sent des humains.",
    "En grandissant, ses queues se multiplient.",
    "Neuf saints se seraient réincarnés en Feunard.",
    "Sa mélodie endort ses ennemis.",
    "En colère, il gonfle et devient énorme.",
    "Il vit dans le noir et voit avec des ultrasons.",
    "Il draine sans fin toute victime mordue.",
    "Il s'enterre le jour et sème la nuit.",
    "Il suinte du nectar pour attirer ses proies.",
    "Ses pétales répandent un pollen toxique.",
    "Il absorbe l'énergie des racines des arbres.",
    "Le champignon dorsal absorbe son énergie.",
    "À l'ombre des arbres, il mange des insectes.",
    "Ses ailes ont des écailles très toxiques.",
    "Il vit sous terre et mange des racines.",
    "Un groupe de Taupiqueur peut causer des séismes.",
    "Il erre pour trouver des pièces brillantes.",
    "Admiré, il reste difficile à élever.",
    "Sa migraine renforce ses pouvoirs psy.",
    "Ses nageoires le font nager avec grâce.",
    "Il s'énerve vite et attaque sans hésiter.",
    "Furieux, il poursuit sa proie sans relâche.",
    "Territorial, il chasse les intrus en aboyant.",
    "Admiré pour sa beauté, il court comme s'il volait.",
    "Il préfère nager plutôt que marcher.",
    "La spirale de son ventre endort ses ennemis.",
    "Ce puissant nageur bat même les champions.",
    "Il lit les pensées et se téléporte en danger.",
    "Ses ondes donnent de forts maux de tête.",
    "Il mémorise tout et n'oublie jamais rien.",
    "Les arts martiaux le rendent plus fort.",
    "Sa ceinture limite son immense force.",
    "Ses poings projettent ses ennemis au loin.",
    "Il piège puis mange les insectes avec ses lianes.",
    "Affamé, il avale tout ce qui bouge.",
    "Son arôme attire les proies qu'il avale.",
    "Il dérive en mer et lance de l'acide.",
    "Ses nombreux tentacules piègent ses proies.",
    "Pris pour des rochers, on lui marche dessus.",
    "Il roule sur les obstacles sans les éviter.",
    "Il résiste aux explosions de dynamite.",
    "Ses sabots sont dix fois plus durs que le diamant.",
    "Il poursuit tout ce qui se déplace vite.",
    "Il sent la douleur cinq secondes plus tard.",
    "Le Kokiyas de sa queue mange ses restes.",
    "Ses ondes magnétiques le font léviter.",
    "Les taches solaires le font apparaître.",
    "Il manie son poireau comme une épée.",
    "Il préfère courir sur ses fortes pattes.",
    "Deux têtes dorment, la troisième veille.",
    "Il adore nager dans une eau à 14 degrés.",
    "Insensible au froid, il nage vite en eau glacée.",
    "Il prospère en aspirant les boues polluées.",
    "Son odeur affreuse peut faire perdre connaissance.",
    "Sa coquille résiste à toutes les attaques.",
    "Il tire des pics de sa coquille pour se défendre.",
    "Sans forme réelle, il semble fait de gaz.",
    "Sa langue aspire la force vitale.",
    "Il adore rire des gens qu'il effraie.",
    "Les grottes qu'il creuse abritent des Taupiqueur.",
    "Il endort ses ennemis puis dévore leurs rêves.",
    "Il hypnotise l'ennemi qui croise son regard.",
    "Ses pinces l'aident à garder l'équilibre.",
    "Sa pince broie avec une force de 4,5 tonnes.",
    "Il peut exploser au moindre stimulus.",
    "Il stocke de l'électricité dans son corps.",
    "Pris pour des oeufs, ils attaquent en essaim.",
    "On dit que ses têtes donnent des Noeunoeuf.",
    "Il porte le crâne de sa mère et pleure.",
    "Il manie habilement son os comme un boomerang.",
    "Ses coups de pied terrassent ses rivaux.",
    "Il frappe si vite qu'on ne voit pas ses coups.",
    "Sa langue de deux mètres peut paralyser.",
    "Son gaz interne peut le faire exploser.",
    "Gaz, poussière et bactéries le font grandir.",
    "Ses os sont mille fois plus durs que les nôtres.",
    "Sa peau blindée repousse même la lave.",
    "Rare, il apporterait le bonheur à tous.",
    "Des lianes d'algues cachent son identité.",
    "Il combat sans fuir pour protéger son petit.",
    "En danger, il projette de l'encre par la bouche.",
    "Ses nageoires et sa queue le font reculer.",
    "Il nage en groupe à la saison de la ponte.",
    "À la ponte, il remonte les rivières.",
    "Tout membre perdu peut repousser.",
    "Sa gemme brille quand il communique.",
    "Il mime des objets pour tromper ses ennemis.",
    "Son agilité crée des illusions de lui-même.",
    "Il balance ses hanches comme s'il dansait.",
    "Près des centrales, il cause des pannes.",
    "Né au volcan, son corps est couvert de flammes.",
    "Ses grandes pinces écrasent ses ennemis.",
    "Ce Pokémon turbulent charge ses ennemis.",
    "Très faible et peu fiable, il vit partout.",
    "Énorme et féroce, il peut détruire une ville.",
    "Ce doux Pokémon peut lire l'esprit humain.",
    "Il change son ADN pour copier son ennemi.",
    "Il peut muter au contact de pierres élémentaires.",
    "Sa queue est souvent prise pour celle d'une sirène.",
    "Il capte des ions négatifs et lance des éclairs.",
    "Il stocke de l'énergie et atteint 900 degrés.",
    "Programmé, il voyage dans le cyberespace.",
    "Ce Pokémon ancien nage avec ses tentacules.",
    "Sa lourde coquille gêne la capture de ses proies.",
    "Ressuscité d'un fossile, il vivait dans la mer.",
    "Il tranche ses proies et aspire leurs fluides.",
    "Ses crocs visent la gorge de son ennemi.",
    "Très paresseux, il dévore tout.",
    "Il guide les égarés dans les blizzards.",
    "Oiseau mystique qui apparaît dans les tempêtes.",
    "Ses ailes font jaillir des gerbes de flammes.",
    "Pris pour un mythe, il fut découvert récemment.",
    "Ce Pokémon mystique dégage une aura douce.",
    "Pokémon marin rare, son Q.I. égale le nôtre.",
    "Un savant l'a créé par génie génétique.",
    "Si rare que très peu de gens l'ont vu.",
)


# Entries whose current French text is visibly truncated, glued, grammatically
# incomplete, or omits a material clause from the exact linked English source.
# Every other current text is retained verbatim (apart from whitespace reflow).
CURRENT_INCOMPLETE_IDS = frozenset({
    1, 3, 5, 6, 7, 8, 11, 12, 13, 19, 20, 23, 24, 26, 31, 35, 36,
    38, 42, 43, 45, 48, 51, 53, 57, 61, 70, 79, 83, 89, 95, 99, 106,
    109, 110, 111, 113, 114, 116, 122, 126, 127, 129, 133, 134, 141,
    142, 145, 150, 151,
})

CONTENT_ISSUES = {
    1: "« pour l'énergie » ne rend pas l'action de stocker l'énergie.",
    3: "La finalité « for energy » disparaît du texte français.",
    5: "La proposition « quand enragé » est grammaticalement incomplète.",
    6: "La fin « fondre roche » perd articles et nombre.",
    7: "Deux mots sont collés dans « danssa ».",
    8: "Le dernier mot est coupé à « equilib ».",
    11: "Le dernier mot est coupé à « fra ».",
    12: "La fin « voler sous pluie » est grammaticalement incomplète.",
    13: "La proposition anglaise « to eat leaves » a été omise.",
    19: "« 40 autres attendent » ne rend pas « 40 more near ».",
    20: "La fonction de chasse des pattes palmées a été omise.",
    23: "Le complément « bird Pokémon » a été omis.",
    24: "Le dernier mot est coupé à « avertisse ».",
    26: "La phrase s'arrête après « protéger » et omet les décharges.",
    31: "Le dernier mot est coupé à « puiss ».",
    35: "Deux propositions sont collées sans liaison grammaticale.",
    36: "La fin « sent gens » est grammaticalement incomplète.",
    38: "« saints » a été remplacé à tort par « sages ».",
    42: "La traduction omet que le drainage ne s'arrête plus après la morsure.",
    43: "« s'enterrele » est collé et « grain » est tronqué.",
    45: "Le dernier mot est coupé à « toxi ».",
    48: "La fin « mange insect » est tronquée.",
    51: "L'article manque dans « peut causer séismes ».",
    53: "« Bien que ... il est » exige une autre construction.",
    57: "La poursuite « till it's caught » est omise.",
    61: "La phrase s'arrête sur l'infinitif « endormir ».",
    70: "Le dernier mot est coupé à « boug ».",
    79: "« sente mal » ne signifie pas « feel pain ».",
    83: "« sprig of onions » doit employer le terme canonique « poireau ».",
    89: "Le dernier mot est coupé à « s'evano ».",
    95: "Le texte omet que les grottes servent aux Taupiqueur.",
    99: "L'unité anglaise « lbs » n'a pas été convertie pour le texte français.",
    106: "« à coups pied » est grammaticalement incomplet.",
    109: "Deux mots sont collés dans « explosionsdue ».",
    110: "Plusieurs mots sont collés et « bactéries » est corrompu.",
    111: "Le dernier mot est coupé à « l'humai ».",
    113: "Le complément « to all » a été omis.",
    114: "Le dernier mot est coupé à « algu ».",
    116: "L'article manque dans « par bouche ».",
    122: "La formulation ne rend pas clairement l'illusion créée par le mime.",
    126: "« volcan,son » et « estcouvert » sont collés.",
    127: "Le dernier verbe est coupé à « ecrase ».",
    129: "Le sens « unreliable » a été omis.",
    133: "Le dernier mot est coupé à « eleme ».",
    134: "La fin « d'1 sire » est une abréviation tronquée de « sirène ».",
    141: "Plusieurs mots sont collés ou coupés : « saproie », « grifes », « fluid ».",
    142: "La fin contient « avecses croc », collé et tronqué.",
    145: "Deux mots sont collés dans « dansles ».",
    150: "« Créé par un scientifique par... » répète fautivement la préposition.",
    151: "La phrase complète doit retrouver sa ponctuation finale.",
}

# Complete current texts whose wording is faithful but cannot be reflowed
# verbatim within four 13-column lines.  Their proposal is only condensed.
NEEDS_CONDENSATION_IDS = frozenset({
    18, 29, 54, 68, 76, 84, 124, 136, 137, 147,
})

# Exact editorial adjustments requested after source-by-source review.  Some
# overlap content corrections or mandatory condensations; the remainder are
# faithful grammar/terminology improvements.
REVIEWED_REFINEMENT_IDS = frozenset({
    9, 18, 26, 33, 35, 38, 42, 83, 87, 95, 99, 107, 111, 113, 114,
    120, 128, 129, 137, 143, 147, 148, 149, 150, 151,
})

# Hard anchors for the table start and indexing.  These values are also
# exercised by ``test_pokedex_full_151_audit.py``.
POINTER_ANCHORS = {
    1: 0x030898,
    2: 0x036950,
    3: 0x036978,
    4: 0x03217A,
    5: 0x0369AA,
    25: 0x036B71,
    49: 0x0325D4,
    100: 0x032A17,
    149: 0x037869,
    150: 0x032EF7,
    151: 0x03789A,
}

NAME_ANCHORS = {
    1: ("Bulbasaur", 0x035FCD),
    2: ("Ivysaur", 0x035FD7),
    3: ("Venusaur", 0x035FDF),
    4: ("Charmander", 0x035FE8),
    5: ("Charmeleon", 0x035FF3),
    25: ("Pikachu", 0x03609D),
    49: ("Venomoth", 0x03616D),
    100: ("Voltorb", 0x03630C),
    149: ("Dragonite", 0x03649E),
    150: ("Mewtwo", 0x0364A8),
    151: ("Mew", 0x0364AF),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _script_records(path: Path) -> dict[int, dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    records: dict[int, dict[str, Any]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "p"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, int)
        ):
            continue
        strings = [
            arg.value
            for arg in node.args[1:]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        ]
        layout = ""
        for keyword in node.keywords:
            if (
                keyword.arg == "layout"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                layout = keyword.value.value
        records[node.args[0].value] = {
            "text": "".join(strings),
            "layout": layout,
            "line": node.lineno,
        }
    return records


def _english_sources(path: Path) -> dict[int, str]:
    sources: dict[int, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            sources[int(row["offset_hex"], 16)] = row["source_en"]
    return sources


def _description_offsets(rom: bytes, count: int) -> list[int]:
    result = []
    for index in range(count):
        start = POINTER_TABLE_OFFSET + index * 2
        pointer = int.from_bytes(rom[start:start + 2], "little")
        result.append(pointer + POINTER_FILE_BIAS)
    return result


def _name_records(rom: bytes, count: int) -> list[tuple[int, str]]:
    result = []
    for index in range(count):
        start = NAME_POINTER_TABLE_OFFSET + index * 2
        pointer = int.from_bytes(rom[start:start + 2], "little")
        offset = pointer + POINTER_FILE_BIAS
        end = rom.index(0x0D, offset)
        result.append((offset, rom[offset:end].decode("ascii")))
    return result


def _human_wrapped_lines(text: str) -> list[str]:
    lines: list[list[str]] = [[]]
    encoded_width = 0
    for unit in semantic_units(text):
        unit_width = len(encode_game_text(unit))
        separator = 1 if lines[-1] else 0
        if encoded_width + separator + unit_width <= 13:
            lines[-1].append(unit)
            encoded_width += separator + unit_width
        else:
            lines.append([unit])
            encoded_width = unit_width
    return [" ".join(line) for line in lines]


def build_report(rom_path: Path, script_path: Path, csv_path: Path) -> dict[str, Any]:
    if len(SPECIES) != KANTO_COUNT or len(PROPOSALS) != KANTO_COUNT:
        raise AssertionError("the species/proposal tables must contain 151 rows")
    if frozenset(CONTENT_ISSUES) != CURRENT_INCOMPLETE_IDS:
        raise AssertionError("every incomplete entry must have one exact issue")

    rom = rom_path.read_bytes()
    script = _script_records(script_path)
    sources = _english_sources(csv_path)
    offsets = _description_offsets(rom, KANTO_COUNT)
    names = _name_records(rom, KANTO_COUNT)
    extended = _description_offsets(rom, KANTO_COUNT + EXTENDED_POINTER_COUNT)[KANTO_COUNT:]
    for species_id, expected_offset in POINTER_ANCHORS.items():
        actual_offset = offsets[species_id - 1]
        if actual_offset != expected_offset:
            raise RuntimeError(
                f"Pokédex pointer #{species_id}: 0x{actual_offset:06X}, "
                f"expected 0x{expected_offset:06X}"
            )
    for species_id, (expected_name, expected_offset) in NAME_ANCHORS.items():
        actual_offset, actual_name = names[species_id - 1]
        if (actual_name, actual_offset) != (expected_name, expected_offset):
            raise RuntimeError(
                f"Pokédex name #{species_id}: {actual_name!r} at "
                f"0x{actual_offset:06X}, expected {expected_name!r} at "
                f"0x{expected_offset:06X}"
            )

    records = []
    for species_id, (species, offset, correction) in enumerate(
        zip(SPECIES, offsets, PROPOSALS, strict=True),
        1,
    ):
        current = script.get(offset)
        if current is None:
            raise RuntimeError(
                f"no script.py description for species {species_id} at 0x{offset:06X}"
            )
        baseline_content_incomplete = species_id in CURRENT_INCOMPLETE_IDS
        needs_condensation = species_id in NEEDS_CONDENSATION_IDS
        reviewed_refinement = species_id in REVIEWED_REFINEMENT_IDS
        proposal = (
            correction
            if baseline_content_incomplete or needs_condensation or reviewed_refinement
            else " ".join(current["text"].split())
        )
        current_normalized = " ".join(current["text"].split())
        current_matches_proposal = current_normalized == proposal
        name_offset, rom_name_en = names[species_id - 1]
        lines = wrap_pokedex_lines(proposal)
        baseline_status = (
            "incomplete" if baseline_content_incomplete else "complete"
        )
        if current_matches_proposal:
            status = "complete"
            proof = (
                "Le texte actuel correspond exactement à la proposition "
                "revue et validée en 13x4."
            )
        else:
            status = "incomplete"
            proof = CONTENT_ISSUES.get(
                species_id,
                "Le texte actuel diverge de la proposition fidèle validée en 13x4.",
            )
        records.append({
            "species_id": species_id,
            "species_fr": species,
            "rom_name_en": rom_name_en,
            "name_pointer_table_file_offset": (
                f"0x{NAME_POINTER_TABLE_OFFSET + 2 * (species_id - 1):06X}"
            ),
            "name_offset": f"0x{name_offset:06X}",
            "pointer_table_file_offset": f"0x{POINTER_TABLE_OFFSET + 2 * (species_id - 1):06X}",
            "description_offset": f"0x{offset:06X}",
            "script_line": current["line"],
            "source_en": sources.get(offset, ""),
            "current_fr": current["text"],
            "current_layout": current["layout"],
            "current_status": status,
            "proof": proof,
            "current_matches_reviewed_proposal": current_matches_proposal,
            "baseline_review_status": baseline_status,
            "baseline_issue": CONTENT_ISSUES.get(species_id),
            "requires_content_correction": not current_matches_proposal,
            "baseline_required_content_correction": baseline_content_incomplete,
            "baseline_required_13x4_condensation": needs_condensation,
            "reviewed_editorial_refinement": reviewed_refinement,
            "requires_layout_migration": current["layout"] != "pokedex_13x4",
            "proposal_kind": (
                "minimal_source_faithful_correction"
                if baseline_content_incomplete
                else (
                    "source_faithful_condensation_for_13x4"
                    if needs_condensation
                    else (
                        "reviewed_source_faithful_refinement"
                        if reviewed_refinement
                        else "preserve_current_text_reflow_only"
                    )
                )
            ),
            "proposed_fr": proposal,
            "proposed_lines": _human_wrapped_lines(proposal),
            "proposed_encoded_lines_ascii": [
                line.decode("ascii") for line in lines
            ],
            "proposed_line_lengths": [len(line.rstrip(b" ")) for line in lines],
            "proposal_valid_13x4": True,
        })

    accessible_layout = sum(
        record["current_layout"] == "pokedex_13x4" for record in records
    )
    extended_layout = sum(
        script.get(offset, {}).get("layout") == "pokedex_13x4"
        for offset in extended
    )
    status_counts = {
        name: sum(record["current_status"] == name for record in records)
        for name in ("complete", "incomplete", "incorrect")
    }
    remaining_content_corrections = sum(
        record["requires_content_correction"] for record in records
    )
    runtime_dir = (
        ROOT
        / "build"
        / "pokedex-map"
        / "samples-final-42a0d940-verified"
    )
    runtime_files = {
        label: runtime_dir / filename
        for label, filename in {
            "entry_001_screen": "pokedex_mapping_001.png",
            "entry_002_screen": "pokedex_mapping_002.png",
            "entry_004_screen": "pokedex_mapping_004.png",
            "filtered_reads": "pokedex_mapping_samples_reads.csv",
            "mesen_manifest": "mesen_run_manifest.txt",
        }.items()
    }
    source_complete = (
        accessible_layout == KANTO_COUNT
        and remaining_content_corrections == 0
        and status_counts["complete"] == KANTO_COUNT
    )
    return {
        "schema": "pokedex_full_151_audit/v1",
        "result": "PASS" if source_complete else "FAIL",
        "inputs": {
            "rom": str(rom_path),
            "rom_sha256": _sha256(rom_path),
            "script": str(script_path),
            "script_sha256": _sha256(script_path),
            "translation_csv": str(csv_path),
            "translation_csv_sha256": _sha256(csv_path),
        },
        "pointer_model": {
            "table_file_offset": f"0x{POINTER_TABLE_OFFSET:06X}",
            "entry_encoding": "little-endian 16-bit CPU pointer",
            "file_offset_formula": "pointer + 0x28010",
            "kanto_ui_entries": KANTO_COUNT,
            "following_extended_pointers": EXTENDED_POINTER_COUNT,
            "extended_description_offsets": [
                f"0x{offset:06X}" for offset in extended
            ],
            "name_table_file_offset": f"0x{NAME_POINTER_TABLE_OFFSET:06X}",
            "mapping_proof": (
                "Le même identifiant 1..151 indexe la table nationale des "
                "noms à 0x030977 et la table des descriptions à 0x03201E."
            ),
        },
        "runtime_evidence": {
            "available": all(path.is_file() for path in runtime_files.values()),
            "mode": (
                "Dendy, strict hardware, full debug; navigation contrôleur; "
                "drapeaux Pokédex assistés; aucun pointeur ou texte modifié"
            ),
            "sampled_species_ids": [1, 2, 4],
            "files": {
                label: {
                    "path": str(path),
                    "sha256": _sha256(path) if path.is_file() else None,
                }
                for label, path in runtime_files.items()
            },
        },
        "summary": {
            "accessible_descriptions": KANTO_COUNT,
            "accessible_already_pokedex_13x4": accessible_layout,
            "extended_already_pokedex_13x4": extended_layout,
            "all_script_pokedex_13x4": accessible_layout + extended_layout,
            "accessible_without_pokedex_13x4": KANTO_COUNT - accessible_layout,
            "baseline_accessible_pokedex_13x4": 45,
            "baseline_extended_pokedex_13x4": 4,
            "baseline_content_corrections_reviewed": len(CURRENT_INCOMPLETE_IDS),
            "baseline_content_condensations_reviewed": len(NEEDS_CONDENSATION_IDS),
            "baseline_editorial_refinements_reviewed": len(REVIEWED_REFINEMENT_IDS),
            "baseline_verbatim_reflow_only": (
                KANTO_COUNT
                - len(
                    CURRENT_INCOMPLETE_IDS
                    | NEEDS_CONDENSATION_IDS
                    | REVIEWED_REFINEMENT_IDS
                )
            ),
            "remaining_content_corrections": remaining_content_corrections,
            "remaining_layout_migrations": KANTO_COUNT - accessible_layout,
            "status_counts": status_counts,
            "all_proposals_valid_13x4": True,
            "important_count_correction": (
                "Au point de départ, 45 des 151 descriptions atteignables "
                "étaient en 13x4; 4 autres des 49 refaites appartenaient aux "
                "8 pointeurs étendus. Les compteurs courants sont calculés "
                "dynamiquement après migration."
            ),
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(args.rom, args.script, args.csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    result = str(report["result"])
    print(
        f"POKEDEX_FULL_151_AUDIT_{result} "
        f"accessible={summary['accessible_descriptions']} "
        f"layout={summary['accessible_already_pokedex_13x4']} "
        f"needs_layout={summary['accessible_without_pokedex_13x4']} "
        f"output={args.output}"
    )
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
