#!/usr/bin/env python3
"""Inventory missing French accents in the effective translation texts.

The audit consumes ``parse_patch_entries()`` so reviewed dialogue inventory
overrides are represented exactly as the builder sees them.  It never edits
``script.py`` or the inventory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    PATCH_SCRIPT,
    parse_patch_entries,
    sha256,
)
from tools.dialogue_layout import format_game_text  # noqa: E402
from tools.french_font import FRENCH_GLYPH_LABELS  # noqa: E402


WORD_CHARS = "A-Za-zÀ-ÖØ-öø-ÿŒœ"
STATUS_RANK = {"certain": 0, "contextuel": 1, "ambigu": 2}


def _pairs(raw: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        source, replacement = line.split("|", 1)
        pairs[source] = replacement
    return pairs


# These forms have one reviewed correction everywhere they occur in the
# effective corpus.  Context-sensitive homographs are marked separately below
# even when all current occurrences happen to share the same correction.
WORD_REPLACEMENTS = _pairs(
    """
abime|abîme
ame|âme
ames|âmes
amene|amène
amenent|amènent
annees|années
apparait|apparaît
apres|après
arene|arène
arenes|arènes
arome|arôme
arrete|arrête
arrivee|arrivée
beaute|beauté
betes|bêtes
betises|bêtises
bientot|bientôt
brulure|brûlure
casses|cassés
celebre|célèbre
cimetiere|cimetière
cle|clé
colere|colère
competition|compétition
connait|connaît
controle|contrôle
controlent|contrôlent
cote|côté
crame|cramé
crane|crâne
cree|créé
creer|créer
creve|crevé
cupidite|cupidité
debute|débute
dechaine|déchaîne
dechets|déchets
decu|déçu
defi|défi
defier|défier
degage|dégage
degats|dégâts
deja|déjà
déja|déjà
dela|delà
deluges|déluges
desaltere|désaltère
desole|désolé
detruire|détruire
devore|dévore
dome|dôme
ecarte|écarte
echappe|échappe
echauffer|échauffer
echoue|échoué
echouer|échouer
eclate|éclate
egal|égal
electricite|électricité
electrique|électrique
eleves|élèves
elus|élus
enchantee|enchantée
enerve|énerve
enorme|énorme
entraine|entraîne
entrainer|entraîner
enveloppee|enveloppée
epuise|épuisé
epuisees|épuisées
equilibre|équilibre
equipe|équipe
espere|espère
etais|étais
eteint|éteint
etoffe|étoffe
etre|être
eveillee|éveillée
eviter|éviter
executer|exécuter
experience|expérience
experiences|expériences
expose|exposé
fantome|fantôme
fantomes|fantômes
fatigues|fatigués
felicitations|félicitations
ferme|fermé
fermee|fermée
feroce|féroce
fete|fête
fierte|fierté
flute|flûte
fonde|fondé
gagne|gagné
galeres|galères
genetiques|génétiques
genial|génial
gere|gère
gerer|gérer
gout|goût
gueris|guéris
guerit|guérit
he|hé
hesitation|hésitation
identite|identité
iles|îles
impermeables|imperméables
interesse|intéresse
karate|karaté
leve|levé
lumiere|lumière
maitre|maître
maitres|maîtres
maitrise|maîtrise
mechant|méchant
melodie|mélodie
meme|même
mene|mène
mere|mère
merite|mérite
miserables|misérables
montee|montée
musee|musée
nait|naît
nomme|nommé
numeros|numéros
operation|opération
palmees|palmées
paralyse|paralysé
peche|pêche
pecher|pêcher
pedale|pédalé
penible|pénible
pensees|pensées
pere|père
petales|pétales
piege|piège
piegent|piègent
pitie|pitié
plait|plaît
polluees|polluées
possede|possédé
poussiere|poussière
prepare|prépare
preparez|préparez
pret|prêt
prets|prêts
previens|préviens
prevu|prévu
prospere|prospère
proteger|protéger
préféres|préfères
rate|raté
reincarnes|réincarnés
relacher|relâcher
repere|repéré
reperes|repères
resiste|résiste
ressuscite|ressuscité
reussie|réussie
revais|rêvais
reves|rêves
secrete|secrète
seme|sème
specialite|spécialité
stoppe|stoppé
strategie|stratégie
submergee|submergée
supreme|suprême
surement|sûrement
telephone|téléphone
tete|tête
tetes|têtes
touchee|touchée
trainait|traînait
traitre|traître
tres|très
tues|tués
velo|vélo
voles|volés
"""
)


# A replacement is still safe, but its exact accent or ending was selected
# from syntax, speaker meaning, or a fixed label rather than from the isolated
# token alone.
CONTEXTUAL_WORDS = frozenset(
    {
        "abime",
        "amene",
        "arrete",
        "casses",
        "cote",
        "crame",
        "cree",
        "creve",
        "debute",
        "dechaine",
        "desole",
        "echoue",
        "enerve",
        "entraine",
        "epuise",
        "espere",
        "expose",
        "fatigues",
        "ferme",
        "fonde",
        "gagne",
        "leve",
        "mene",
        "nomme",
        "paralyse",
        "pedale",
        "possede",
        "prepare",
        "preparez",
        "prospere",
        "rate",
        "reincarnes",
        "repere",
        "ressuscite",
        "stoppe",
        "tues",
    }
)


# Homographes revus qui doivent rester non accentués à un emplacement précis.
# Les règles lexicales générales restent actives partout ailleurs.
WORD_REPLACEMENT_EXCLUSIONS: dict[int, frozenset[str]] = {
    0x0397E8: frozenset({"paralyse"}),
}


# Offsets where every standalone ASCII ``a`` is the preposition and may be
# replaced by the native one-byte ``à``.  Mixed auxiliary/preposition records
# are handled by exact phrase rules below.
A_GRAVE_ALL_OFFSETS = frozenset(
    {
        0x0302A9,
        0x0323C8,
        0x032451,
        0x032512,
        0x032C32,
        0x032D32,
        0x033583,
        0x033814,
        0x033861,
        0x034F66,
        0x034F7F,
        0x035035,
        0x0350BD,
        0x035433,
        0x03556A,
        0x036795,
        0x036AA9,
        0x036E68,
        0x03744B,
        0x037869,
        0x038092,
        0x0387A0,
        0x038E2C,
        0x039660,
        0x039698,
        0x03971B,
        0x03A195,
        0x03A1E6,
        0x03A324,
        0x03A3C8,
        0x03A5DC,
        0x03ABAC,
        0x03B739,
        0x03B892,
        0x03D13F,
        0x03D35D,
        0x03D39A,
        0x03E2AD,
        0x03E640,
        0x03E732,
        0x03E954,
    }
)


# Exact phrase corrections avoid changing valid homographs in the same text.
CONTEXT_PHRASE_RULES: dict[int, tuple[tuple[str, str, str], ...]] = {
    0x033715: (("a toi", "à toi", "préposition"),),
    0x03427E: (("a cause", "à cause", "locution prépositive"),),
    0x03A4B8: (("A plus", "À plus", "locution"),),
    0x03C765: (("vu a Safrania", "vu à Safrania", "lieu"),),
    0x03DA8E: (("a cote", "à côté", "locution de lieu"),),
    0x03E308: (("Auguste a descendre", "Auguste à descendre", "infinitif"),),
    # Où / ou.
    0x0354E1: (("Ou est", "Où est", "adverbe interrogatif"),),
    0x036DCC: (("arbres ou il", "arbres où il", "adverbe relatif"),),
    0x03B132: (("Ou est", "Où est", "adverbe interrogatif"),),
    0x03E19A: (("ou est", "où est", "adverbe interrogatif"),),
    0x03E308: (
        ("Auguste a descendre", "Auguste à descendre", "infinitif"),
        ("montagne ou il", "montagne où il", "adverbe relatif"),
    ),
    0x03E4A6: (("Ou as-tu", "Où as-tu", "adverbe interrogatif"),),
    # Là / la.
    0x035615: (("la-bas", "là-bas", "adverbe de lieu"),),
    0x0356F2: (("la-dedans", "là-dedans", "adverbe de lieu"),),
    0x0365D0: (("la-bas", "là-bas", "adverbe de lieu"),),
    0x0384F8: (("pas la!", "pas là!", "adverbe de lieu"),),
    0x03868A: (("celui-la", "celui-là", "démonstratif"),),
    0x03AACC: (("la-bas", "là-bas", "adverbe de lieu"),),
    0x03C861: (("par la.", "par là.", "adverbe de lieu"),),
    0x03D3B7: (("Halte-la!", "Halte-là!", "locution"),),
    # Other homographs.
    0x038AA1: (("Bien sur", "Bien sûr", "locution"),),
    0x039334: (("suis sur", "suis sûr", "adjectif"),),
    0x03AD29: (("leve tot", "levé tôt", "adverbe temporel"),),
}


# A context-specific inflection is required; leaving the same source token
# untouched elsewhere is intentional.
CONTEXT_WORD_RULES: dict[int, tuple[tuple[str, str, str], ...]] = {
    0x030304: (("brule", "brûlé", "participe passé"),),
    0x03031A: (("gele", "gelé", "participe passé"),),
    0x030373: (("gele", "gelé", "participe passé"),),
    0x0326A0: (("Admire", "Admiré", "participe passé"),),
    0x03326D: (("joue", "joué", "participe passé"),),
    0x0339A9: (
        ("cherche", "cherché", "participe passé"),
        ("forme", "formé", "participe passé"),
    ),
    0x033A48: (("oublie", "oublié", "participe passé"),),
    0x034F38: (("visite", "visité", "participe passé"),),
    0x035154: (("vole", "volé", "participe passé"),),
    0x0354E1: (("passe", "passé", "participe passé"),),
    0x035F57: (("évolue", "évolué", "participe passé"),),
    0x035F65: (("évolue", "évolué", "participe passé"),),
    0x036E68: (("admire", "admiré", "participe passé"),),
    0x038230: (("coupe", "coupé", "participe passé"),),
    0x038C6C: (("cherche", "cherché", "participe passé"),),
    0x03909E: (("regarde", "regardé", "participe passé"),),
    0x039215: (("touchee", "touchée", "participe passé féminin"),),
    0x039251: (("lance", "lancé", "participe passé"),),
    0x0398BD: (("submergee", "submergée", "participe passé féminin"),),
    0x039B45: (("Fatigue", "Fatigué", "adjectif"),),
    0x039CE0: (("entraine", "entraîné", "participe passé"),),
    0x03A0F7: (("marche", "marché", "participe passé"),),
    0x03A2EB: (("coule", "coulé", "participe passé"),),
    0x03AABA: (("consume", "consumé", "participe passé"),),
    0x03AD43: (("entraine", "entraîne", "verbe conjugué"),),
    0x03BB1B: (("force", "forcé", "participe passé"),),
    0x03BB57: (("arrive", "arrivé", "participe passé"),),
    0x03C765: (("progresse", "progressé", "participe passé"),),
    0x03CA26: (("ruine", "ruiné", "participe passé"),),
    0x03CAB3: (("sauves", "sauvés", "participe passé pluriel"),),
    0x03D50C: (("trouve", "trouvé", "participe passé"),),
    0x03D6A4: (("brule", "brûle", "verbe conjugué"),),
    0x03E0F5: (("utilise", "utilisé", "participe passé"),),
    0x03E308: (("aide", "aidé", "participe passé"),),
    0x03E3D0: (("consume", "consumé", "participe passé"),),
    0x03E433: (("creve", "crevé", "adjectif"),),
    0x03E483: (("capture", "capturé", "participe passé"),),
    0x03E4A6: (("capture", "capturé", "participe passé"),),
}


LOWERCASE_CA_OFFSETS = frozenset(
    {
        0x033A48,
        0x03513A,
        0x038F49,
        0x03956C,
        0x039F3F,
        0x03B687,
        0x03BB39,
        0x03D7CB,
        0x03E51F,
    }
)

UPPERCASE_CA_OFFSETS = frozenset(
    {
        0x03427E,
        0x03692B,
        0x038F91,
        0x0392A6,
        0x03A0F7,
        0x03B310,
        0x03BBBF,
        0x03BCA7,
        0x03CAFB,
        0x03D4FB,
        0x03D746,
    }
)


CA_OFFSETS = LOWERCASE_CA_OFFSETS | UPPERCASE_CA_OFFSETS


AMBIGUOUS_RULES: dict[int, tuple[dict[str, object], ...]] = {
    0x0321DD: (
        {
            "source": "equilib",
            "replacement": "équilibre",
            "reason": "mot source déjà tronqué; correction non isométrique",
        },
    ),
    0x032924: (
        {
            "source": "s'evano",
            "replacement": "s'évanouir",
            "reason": "mot source déjà tronqué; correction non isométrique",
        },
    ),
    0x0369AA: (
        {
            "source": "quand enrage",
            "replacement": "quand il est enragé",
            "reason": "construction tronquée; reformulation nécessaire",
        },
    ),
    0x037646: (
        {
            "source": "ecrase",
            "replacement": "écraser",
            "reason": "infinitif tronqué; correction non isométrique",
        },
    ),
    0x03BFF8: (
        {
            "source": "sauve",
            "replacement": "sauvé",
            "alternatives": ["sauve"],
            "reason": "genre du locuteur requis pour choisir sauvé/sauve",
        },
    ),
}


def _preserve_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _word_regex(source: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![{WORD_CHARS}]){re.escape(source)}(?![{WORD_CHARS}])",
        re.IGNORECASE,
    )


def _replace_word(
    text: str,
    source: str,
    replacement: str,
) -> tuple[str, int, list[tuple[str, str]]]:
    pattern = _word_regex(source)
    pairs: list[tuple[str, str]] = []

    def repl(match: re.Match[str]) -> str:
        found = match.group(0)
        corrected = _preserve_case(found, replacement)
        pairs.append((found, corrected))
        return corrected

    corrected, count = pattern.subn(repl, text)
    return corrected, count, pairs


def _replacement(
    source: str,
    replacement: str,
    count: int,
    status: str,
    reason: str,
    *,
    applied: bool = True,
    alternatives: object | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "source": source,
        "replacement": replacement,
        "count": count,
        "status": status,
        "reason": reason,
        "applied_to_proposal": applied,
    }
    if alternatives:
        item["alternatives"] = alternatives
    return item


def audit(
    script_path: str | Path = PATCH_SCRIPT,
) -> dict[str, object]:
    entries = parse_patch_entries(script_path)
    records: list[dict[str, object]] = []

    replacement_occurrences = Counter()
    replacement_offsets: dict[str, set[int]] = defaultdict(set)

    for entry in entries:
        before = entry.text
        corrected = before
        replacements: list[dict[str, object]] = []

        # Apply exact context rules before broad lexical rules.  This matters
        # for pairs such as ``entraine -> entraîné`` versus the general
        # present-tense ``entraine -> entraîne``.
        for source, target, reason in CONTEXT_PHRASE_RULES.get(
            entry.offset,
            (),
        ):
            count = corrected.count(source)
            if not count:
                continue
            corrected = corrected.replace(source, target)
            replacements.append(
                _replacement(
                    source,
                    target,
                    count,
                    "contextuel",
                    reason,
                )
            )

        for source, target, reason in CONTEXT_WORD_RULES.get(
            entry.offset,
            (),
        ):
            corrected_next, count, pairs = _replace_word(
                corrected,
                source,
                target,
            )
            if not count:
                continue
            corrected = corrected_next
            replacements.append(
                _replacement(
                    " / ".join(sorted({pair[0] for pair in pairs})),
                    " / ".join(sorted({pair[1] for pair in pairs})),
                    count,
                    "contextuel",
                    reason,
                )
            )

        for source, target in WORD_REPLACEMENTS.items():
            if source in WORD_REPLACEMENT_EXCLUSIONS.get(entry.offset, ()):
                continue
            corrected_next, count, pairs = _replace_word(
                corrected,
                source,
                target,
            )
            if not count:
                continue
            corrected = corrected_next
            status = (
                "contextuel"
                if source in CONTEXTUAL_WORDS
                else "certain"
            )
            replacements.append(
                _replacement(
                    " / ".join(sorted({pair[0] for pair in pairs})),
                    " / ".join(sorted({pair[1] for pair in pairs})),
                    count,
                    status,
                    (
                        "forme relue dans son contexte"
                        if status == "contextuel"
                        else "graphie française non ambiguë"
                    ),
                )
            )

        if entry.offset in A_GRAVE_ALL_OFFSETS:
            corrected, count, pairs = _replace_word(corrected, "a", "à")
            if count:
                replacements.append(
                    _replacement(
                        " / ".join(sorted({pair[0] for pair in pairs})),
                        " / ".join(sorted({pair[1] for pair in pairs})),
                        count,
                        "contextuel",
                        "préposition confirmée par la syntaxe",
                    )
                )

        if entry.offset in CA_OFFSETS:
            corrected, count, pairs = _replace_word(corrected, "ca", "ça")
            if count:
                replacements.append(
                    _replacement(
                        " / ".join(sorted({pair[0] for pair in pairs})),
                        " / ".join(sorted({pair[1] for pair in pairs})),
                        count,
                        "contextuel",
                        (
                            "pronom démonstratif confirmé; "
                            "Ç/ç natifs disponibles"
                        ),
                    )
                )

        for rule in AMBIGUOUS_RULES.get(entry.offset, ()):
            source = str(rule["source"])
            count = corrected.count(source)
            if not count:
                continue
            replacements.append(
                _replacement(
                    source,
                    str(rule["replacement"]),
                    count,
                    "ambigu",
                    str(rule["reason"]),
                    applied=False,
                    alternatives=rule.get("alternatives"),
                )
            )

        if not replacements:
            continue

        before_encoded = format_game_text(before, entry.layout)
        corrected_encoded = format_game_text(corrected, entry.layout)
        if len(before_encoded) != len(corrected_encoded):
            raise ValueError(
                f"0x{entry.offset:06X}: correction proposée non isométrique "
                f"({len(before_encoded)} -> {len(corrected_encoded)})"
            )

        record_status = max(
            (str(item["status"]) for item in replacements),
            key=STATUS_RANK.__getitem__,
        )
        for item in replacements:
            status = str(item["status"])
            count = int(item["count"])
            replacement_occurrences[status] += count
            replacement_offsets[status].add(entry.offset)

        records.append(
            {
                "offset": entry.offset,
                "offset_hex": f"0x{entry.offset:06X}",
                "script_line": entry.line,
                "layout": entry.layout,
                "effective_text_before": before,
                "corrected_text": corrected,
                "encoded_bytes_before": len(before_encoded),
                "encoded_bytes_after": len(corrected_encoded),
                "status": record_status,
                "replacements": replacements,
            }
        )

    record_status_counts = Counter(
        str(record["status"])
        for record in records
    )
    all_offsets = {int(record["offset"]) for record in records}
    changed_offsets = {
        int(record["offset"])
        for record in records
        if record["effective_text_before"] != record["corrected_text"]
    }
    report: dict[str, object] = {
        "schema_version": 1,
        "result": "PASS",
        "method": (
            "effective parse_patch_entries texts; reviewed lexical mapping; "
            "context-specific homograph rules; no source mutation"
        ),
        "script": str((ROM_DIR / script_path).resolve()),
        "script_sha256": sha256((ROM_DIR / script_path).read_bytes()),
        "effective_entries_scanned": len(entries),
        "native_single_byte_glyphs": [
            character
            for _, character in (
                FRENCH_GLYPH_LABELS[code]
                for code in sorted(FRENCH_GLYPH_LABELS)
            )
        ],
        "summary": {
            "flagged_offsets": len(all_offsets),
            "proposal_changed_offsets": len(changed_offsets),
            "record_status_counts": dict(sorted(record_status_counts.items())),
            "replacement_occurrences_by_status": {
                status: replacement_occurrences[status]
                for status in STATUS_RANK
            },
            "replacement_offsets_by_status": {
                status: len(replacement_offsets[status])
                for status in STATUS_RANK
            },
            "ambiguous_offsets": sorted(
                f"0x{offset:06X}"
                for offset in replacement_offsets["ambigu"]
            ),
        },
        "policy_exclusions": [
            {
                "forms": ["Soeur", "soeur", "oeufs"],
                "reason": (
                    "œ/Œ reste volontairement encodé oe/OE sur deux colonnes"
                ),
            },
            {
                "forms": ["Tot.Soin"],
                "reason": "abréviation de Total Soin, pas l'adverbe tôt",
            },
            {
                "forms": ["taches solaires"],
                "reason": "taches est ici le nom correct, sans circonflexe",
            },
            {
                "forms": ["évolue!"],
                "offset_hex": "0x030409",
                "reason": "présent verbal correct pour « is evolving »",
            },
            {
                "forms": ["Électrik paralyse !"],
                "offset_hex": "0x0397E8",
                "reason": "paralyse est ici le verbe au présent",
            },
        ],
        "records": records,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventorie les accents français absents des textes effectifs."
    )
    parser.add_argument("--script", default=PATCH_SCRIPT)
    parser.add_argument(
        "--output",
        default="build/audits/french_accent_audit.json",
    )
    args = parser.parse_args()

    report = audit(args.script)
    output = (
        Path(args.output)
        if Path(args.output).is_absolute()
        else ROM_DIR / args.output
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    print("Audit accents français")
    print(f"- Textes effectifs scannés : {report['effective_entries_scanned']}")
    print(f"- Offsets signalés : {summary['flagged_offsets']}")
    print(
        "- Offsets avec proposition isométrique : "
        f"{summary['proposal_changed_offsets']}"
    )
    print(
        "- Occurrences certaines/contextuelles/ambiguës : "
        f"{summary['replacement_occurrences_by_status']}"
    )
    print(f"- Rapport : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
