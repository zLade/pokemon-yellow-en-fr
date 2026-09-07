#!/usr/bin/env python3
"""
Additional quality audit for the French reference translation.

Finds issues that storage and pointer checks do not detect: unsupported
characters, likely English leftovers, truncated translation fragments,
joined words, implausible repeated letters and inconsistent Pokemon terms.




"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from tools.dialogue_layout import format_game_text  # noqa: E402


WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ@]+(?:'[A-Za-zÀ-ÖØ-öø-ÿ@]+)?")


@dataclass(frozen=True)
class TextRule:
    rule_id: str
    severity: int
    category: str
    regex: re.Pattern[str]
    detail: str
    offsets: frozenset[int] | None = None

    def applies_to(self, offset: int, text: str) -> bool:
        return (
            (self.offsets is None or offset in self.offsets)
            and self.regex.search(text) is not None
        )


def text_rule(
    rule_id: str,
    severity: int,
    category: str,
    pattern: str,
    detail: str,
    *offsets: int,
) -> TextRule:
    return TextRule(
        rule_id=rule_id,
        severity=severity,
        category=category,
        regex=re.compile(pattern, re.I),
        detail=detail,
        offsets=frozenset(offsets) if offsets else None,
    )


# Testable rules for high-signal artifacts already found in this
# translation. Rules do not depend on script.py line numbers:
# ROM offsets provide stable text identity.
TEXT_RULES = (
    # Short English leftovers missed by the previous word-based detector.
    text_rule(
        "english_balls",
        3,
        "english_leak",
        r"^\s*Balls\s*$",
        "English label 'Balls' (expected: Poké Balls or a French label)",
    ),
    text_rule(
        "mixed_yes_no",
        3,
        "english_leak",
        r"\bOui\s+No\b",
        "bilingual label 'Oui No' (expected: Oui Non)",
    ),
    text_rule(
        "article_ball",
        3,
        "english_leak",
        r"\b(?:la|cette|une|un)\s+ball(?:!|\b)",
        "anglicism 'ball' after a French article",
    ),
    text_rule(
        "pokeball_gender",
        2,
        "grammar",
        r"\bUn\s+Pok[ée]\s*ball\b",
        "incorrect gender: 'Une Poké Ball'",
    ),
    # Official names and localized mistranslations.
    text_rule(
        "misty_wrong_hm",
        3,
        "official_term",
        r"\bCS\s+Surf\b",
        "Ondine must give Coupe and CT11/Bulles d'O, not Surf",
        0x039937,
    ),
    text_rule(
        "psybeam_psyko",
        3,
        "official_term",
        r"\bPsyko\b",
        "Psybeam must be translated as Rafale Psy",
        0x03DC8E,
    ),
    text_rule(
        "rainbow_badge",
        2,
        "official_term",
        r"Badge\s+Arc-en-Ciel",
        "official French name: Badge Prisme",
        0x03B9F1,
    ),
    text_rule(
        "marsh_badge",
        2,
        "official_term",
        r"badge\s+Ar[eè]ne\s+de\s+Morgane",
        "official French name: Badge Marais",
        0x03DB8E,
    ),
    text_rule(
        "fake_out",
        2,
        "official_term",
        r"\bBlopAtq\b",
        "official French name for Fake Out: Bluff",
        0x031538,
    ),
    text_rule(
        "swift",
        2,
        "official_term",
        r"\bVit\.E\b",
        "official French name for Swift: Météores",
        0x031545,
    ),
    text_rule(
        "max_ether",
        2,
        "official_term",
        r"\bMaxElixr\b",
        "MaxEther must not become Max Élixir (expected: Huile Max)",
        0x03176F,
    ),
    # Known mistranslations that a simple lexicon cannot detect.
    text_rule(
        "eusine_rewrite",
        3,
        "semantic_mismatch",
        r"Suicune|Je\s+serai\s+ici\s+[aà]\s+l'attendre",
        "Eusine dialogue rewritten: the source describes legendary Pokémon testing Sacha",
        0x037ADC,
    ),
    text_rule(
        "bill_ticket_invention",
        3,
        "semantic_mismatch",
        r"billet\s+pour\s+le\s+S\.?S\.?\s*Anne",
        "the source asks the player to thank Léo; it does not give this ticket",
        0x039A24,
    ),
    text_rule(
        "gary_badge_invention",
        3,
        "semantic_mismatch",
        r"J'en\s+ai\s+d[eé]j[aà]\s+2|J'accumule",
        "the rival must mention the guard and ask whether the Pokémon are stronger",
        0x038B03,
    ),
    text_rule(
        "gary_sneaky_invention",
        3,
        "semantic_mismatch",
        r"d[eé]teste\s+devoir\s+[eê]tre\s+sournois",
        "mistranslation absent from the source",
        0x038BBC,
    ),
    text_rule(
        "mewtwo_duplicate",
        2,
        "truncated_or_extra",
        r"Mewtwo\s*$",
        "extraneous Mewtwo repeated at the end of the sentence",
        0x03E13F,
    ),
    text_rule(
        "rival_champion_ending",
        3,
        "semantic_mismatch",
        r"Zut\.\s*$",
        "the ending where the rival acknowledges Sacha as Champion is missing",
        0x037994,
    ),
    text_rule(
        "giovanni_challenge_ending",
        3,
        "semantic_mismatch",
        r"force\s+est\s+remarquable[!.]?\s*$",
        "the ending of Giovanni's challenge is missing",
        0x03E8A0,
    ),
    text_rule(
        "caught_unaccented",
        2,
        "grammar",
        r"est\s+capture!\s*$",
        "expected agreement: est capturé !",
        0x03024E,
    ),
    text_rule(
        "woke_up",
        2,
        "grammar",
        r"^\s*R[eé]veille\s*$",
        "expected wording: Se réveille !",
        0x03070B,
    ),
)


# Distinctive final fragments that can be flagged anywhere without
# mistaking valid French terms such as Vol, Surf, Route or Continue for
# troncatures.
TRUNCATED_ENDINGS = {
    "abando": "abandonne",
    "dang": "danger",
    "empoiso": "empoisonné",
    "espri": "esprit",
    "faci": "facile",
    "for": "fort",
    "gami": "gamin",
    "irrespct": "irrespectueux",
    "pokém": "Pokémon",
    "tempe": "tempête/température (text to review)",
}


KNOWN_CLIPPED_TEXTS = {
    0x030479: (
        re.compile(r"Quelle\s+att\?\s*$", re.I),
        "truncated label: 'Quelle attaque ?'",
    ),
    0x036D6B: (
        re.compile(r"\bpour\s+att\s*$", re.I),
        "description truncated before 'attirer ses proies'",
    ),
    0x037618: (
        re.compile(r"\bcorps\s+est\s+couve\s*$", re.I),
        "truncated description: 'son corps est couvert'",
    ),
    0x033D67: (
        re.compile(r"\bet\s*$", re.I),
        "conclusion truncated after 'Plateau Indigo et'",
    ),
    0x035500: (
        re.compile(r"\bcie\s*$", re.I),
        "truncated ending: 'me tiennent compagnie'",
    ),
    0x035556: (
        re.compile(r"\bgami\s*$", re.I),
        "truncated ending: 'gamin'",
    ),
    0x0355B7: (
        re.compile(r"\bti\s*$", re.I),
        "truncated ending: 'le tien'",
    ),
    0x035685: (
        re.compile(r"\bga\s*$", re.I),
        "truncated ending: 'gardien'",
    ),
    0x039463: (
        re.compile(r"Tu\s+m'as\s+fait\s*$", re.I),
        "truncated ending: 'Tu m'as fait peur !'",
    ),
    0x039477: (
        re.compile(r"devraient\s+pas\s+[eê]tre\s*$", re.I),
        "sentence truncated before 'ici'",
    ),
    0x039B2C: (
        re.compile(r"\bfaci\s*$", re.I),
        "truncated ending: 'facile'",
    ),
    0x039B59: (
        re.compile(r"Tiens-toi\s*$", re.I),
        "truncated ending: 'Tiens-toi prêt !'",
    ),
    0x03A0D2: (
        re.compile(r"C'est\s+pas\s+moi\s+qui\s*$", re.I),
        "truncated sentence",
    ),
    0x03A525: (
        re.compile(r"Le\s+S\.?S\.?\s*ANNE\s+est\s*$", re.I),
        "sentence truncated before 'parti'",
    ),
    0x03AC24: (
        re.compile(r"Pok[eé]\s+Insect\s*$", re.I),
        "truncated name and sentence: Pokémon Insecte",
    ),
    0x03ACB9: (
        re.compile(r"\bfor\s*$", re.I),
        "truncated ending: 'fort'",
    ),
    0x03AD8B: (
        re.compile(r"Cette\s+grotte\s+est\s*$", re.I),
        "truncated sentence",
    ),
    0x03ADC8: (
        re.compile(r"\babando\s*$", re.I),
        "truncated ending: 'J'abandonne !'",
    ),
    0x03CAE7: (
        re.compile(r"Le\s+Pok[eé]mon\s+s'est\s*$", re.I),
        "sentence truncated before 'réveillé'",
    ),
    0x03CBF5: (
        re.compile(r"\bespri\s*$", re.I),
        "truncated ending: 'esprit'",
    ),
    0x03CDFD: (
        re.compile(r"Mes\s+oiseaux\s+sont\s+les\s+!\s*$", re.I),
        "missing word before the exclamation mark",
    ),
    0x03D6B5: (
        re.compile(r"je\s+suis\s+c\s*$", re.I),
        "truncated ending: 'je suis crevé'",
    ),
    0x03D732: (
        re.compile(r"\bta\s+mont\s*$", re.I),
        "truncated sentence ending",
    ),
    0x03D88B: (
        re.compile(r"Notre\s+ma[iî]tre\s+est\s*$", re.I),
        "truncated sentence",
    ),
    0x03D8AF: (
        re.compile(r"Rien\s+ne\s+me\s+fait\s*$", re.I),
        "truncated sentence",
    ),
    0x03DB61: (
        re.compile(r"J'avais\s+pr[eé]vu\s+cette\s*$", re.I),
        "truncated sentence",
    ),
    0x03DE0C: (
        re.compile(r"mon\s+Pok[eé]m\s*$", re.I),
        "truncated ending: Pokémon",
    ),
    0x03E186: (
        re.compile(r"Cet\s+endroit\s+est\s*$", re.I),
        "truncated sentence",
    ),
    0x03E2DA: (
        re.compile(r"Le\s+Feu\s+fond\s+la\s*$", re.I),
        "truncated sentence: 'Le Feu fait fondre la Glace !'",
    ),
}

STRONG_ENGLISH_WORDS = {
    "about", "after", "all", "already", "and", "are", "attack", "battle",
    "because", "before", "blocked", "buy", "can", "caught", "city", "come",
    "did", "does", "enemy", "escaped", "fight", "from", "game", "get",
    "give", "got", "gym", "have", "hello", "here", "item", "leader",
    "learn", "leave", "lost", "made", "mistakes", "name", "not", "now",
    "people", "please", "run", "save", "sell", "that", "the", "them",
    "there", "this", "town", "trainer", "want", "welcome", "what", "where",
    "will", "with", "won", "world", "would", "you", "your",
}

ENGLISH_WHITELIST = {
    "ash", "blue", "bill", "bob", "ct", "cs", "go", "ko", "leo", "link",
    "master", "mew", "mewtwo", "mimi", "mont", "oak", "prof", "rocket",
    "sacha", "safari", "scope", "silph", "surf",
}

NAME_WHITELIST = {
    "abra", "akali", "aeromite", "akwakwak", "arbok", "arcanin", "aspicot",
    "boustiflor", "bulbizarre", "canarticho", "carabaffe", "carapuce",
    "chenipan", "chétiflor", "crustabri", "dracaufeu", "dragonite",
    "ectoplasma", "electhor", "evoli", "fantominus", "florizarre",
    "galopa", "grolem", "herbizarre", "hypnomade", "kangourex",
    "leviator", "lokhlass", "machoc", "miaouss", "mimitoss", "nosferalto",
    "nosferapti", "osselait", "pikachu", "poissirene", "pokémon", "ponyta",
    "psykokwak", "racaillou", "rattata", "roucool", "salameche", "scopesilph",
    "soporifik", "stari", "tentacool", "voltali",
}

FR_SEED_WORDS = {
    "acheter", "adversaire", "affronter", "aide", "aller", "ami", "amis",
    "ancien", "apres", "arene", "argent", "attaque", "attaques", "attrape",
    "attraper", "autre", "autres", "avant", "avoir", "badge", "balle",
    "balles", "battu", "beaucoup", "besoin", "bien", "bienvenue", "boire",
    "boisson", "bonjour", "bourg", "boutique", "ca", "cache", "capturer",
    "carte", "casino", "cave", "cela", "celui", "centre", "champion",
    "champions", "chance", "changer", "chemin", "cherche", "choisir",
    "choisis", "combat", "combats", "combattre", "combattons", "comme", "comment",
    "comprends", "contre", "coupe", "courir", "crois", "dans", "dangereux", "deja", "des", "dresse",
    "dressee", "dressees", "dresser", "dresseur", "dresseurs", "echange",
    "ecole", "effet", "efficace", "elle", "elles", "encore", "enfant", "enfin",
    "equipe", "escalier", "est", "etre", "faire", "fait", "fille", "fils",
    "facilement", "fort", "forte", "fossile", "gagne", "gagner", "garde", "garcon",
    "gars", "grotte", "guerit", "haut", "herbe", "homme", "ici", "jamais",
    "jaune", "joue", "jouer", "jour", "juste", "la", "lac", "le", "les",
    "leur", "ligne", "loin", "long", "longtemps", "machine", "maison", "mais", "mauvais",
    "meilleur", "meme", "merci", "mer", "mes", "mettre", "mon", "monde", "mystique",
    "mont", "montre", "niveau", "nom", "nous", "nouveau", "objet", "objets",
    "obtenu", "obtenue", "pardonne", "parle", "parler", "partir", "pas", "peux", "peut",
    "peuvent", "pierre", "place", "plus", "pokeball", "pokedex", "poké",
    "pokéball", "pokéballs", "pokédex", "pokémon", "pour", "pourquoi",
    "prendre", "pret", "profond", "profonde", "prix", "prof", "quand", "que", "quel", "quelle",
    "qui", "quoi", "recu", "regarde", "rencontre", "route", "rue", "sacha",
    "sac", "sais", "sans", "sante", "sauver", "secret", "semble", "sera",
    "repoussent", "repousser", "seulement", "ses", "soigne", "soigner", "soin",
    "sont", "sort", "sortie", "sous", "suis", "super", "sur", "surnommé",
    "surprends",
    "surnomme", "team", "tel", "temps", "tes", "toi", "ton", "tous",
    "tout", "toute", "tres", "trouve", "trouver", "type", "une",
    "utilise", "utiliser", "vais", "vas", "venir", "ville", "voir", "vois",
    "vont", "vous", "vrai", "autrefois", "dracosouffle",
}

RARE_DOUBLE_ALLOWLIST = {
    "affaire", "affaires", "affiche", "affilee", "affronter", "affrontes", "d'affilee",
    "blizzard", "bluff", "difficile", "efficace", "effraye", "effrayant", "fuff",
    "griffe", "heff", "krabboss", "l'affaire", "l'etoffe", "l'offensive",
    "m'echauffer", "m'offre", "offre", "ohh", "rafflesia", "raflessia",
    "sniff", "souffle",
    "souffre", "suffit", "affrontons", "blizzards", "différents",
    "affamé", "affreuse", "difficiles", "dracosouffle", "griffes",
    "inefficaces", "inoffensif", "l'étoffe", "m'échauffer",
    "siffl'herbe",
}

SOUND_ALLOWLIST = {"aaaah", "kwaaah", "rrrroar"}

BAD_FRAGMENT_PATTERNS = [
    (re.compile(r"\binter\b", re.I), "fragment_switch", "inter -> interrupteur ?"),
    (re.compile(r"\bobte\b|\bobt\b", re.I), "fragment_obtained", "truncated obte/obt"),
    (re.compile(r"\bmig\b", re.I), "fragment_cute", "truncated mig"),
    (re.compile(r"dressessont", re.I), "glue_known", "dresses sont"),
    (re.compile(r"dresseurspour", re.I), "glue_known", "dresseurs pour"),
    (re.compile(r"poursoigner", re.I), "glue_known", "pour soigner"),
    (re.compile(r"pourcapturer", re.I), "glue_known", "pour capturer"),
    (re.compile(r"pokemonfeu|pokémonfeu", re.I), "glue_known", "Pokemon Feu"),
    (re.compile(r"tu capturer", re.I), "bad_phrase", "tu peux capturer ?"),
    (re.compile(r"\bmembr\b", re.I), "fragment_member", "truncated membre"),
    (re.compile(r"de-\s* vore|de-\s*vore", re.I), "fragment_devour", "devore tout ?"),
    (re.compile(r"voletres", re.I), "glue_known", "vole tres ?"),
    (re.compile(r"\bpeude\b", re.I), "glue_known", "peu de"),
    (re.compile(r"autres att(?!endent)", re.I), "fragment_attacks", "autres attaques ?"),
    (re.compile(r"estdifficile", re.I), "glue_known", "est difficile"),
    (re.compile(r"capture deproies", re.I), "glue_known", "capture de proies"),
    (re.compile(r"\btepermets\b", re.I), "glue_known", "te permet"),
    (re.compile(r"\bpersoncomprenait\b", re.I), "glue_known", "personne ne comprenait"),
    (re.compile(r"\brevepour\b", re.I), "glue_known", "rêve pour"),
    (re.compile(r"\bmaisonun\b", re.I), "glue_known", "maison un"),
    (re.compile(r"\bcentrede\b", re.I), "glue_known", "Centre de"),
    (re.compile(r"\bilsseront\b", re.I), "glue_known", "ils seront"),
    (re.compile(r"\bBquand\b"), "glue_known", "B quand"),
    (re.compile(r"\bPok[eé]moqui\b", re.I), "glue_known", "Pokémon qui"),
]

CRITICAL_TERM_RULES = [
    ("Pok@mon", re.compile(r"pok[eé@]|pkmn", re.I), "term_pokemon"),
    ("Pok@dex", re.compile(r"pok[eé@]dex", re.I), "term_pokedex"),
    ("switch", re.compile(r"changer|interrupteur|bouton|switch", re.I), "term_switch"),
    ("Badge", re.compile(r"badge", re.I), "term_badge"),
    ("Gym", re.compile(r"ar[eè]ne|gym|badge", re.I), "term_gym"),
]

# These translations legitimately replace the generic Pokemon name in the
# source with an already explicit subject (a pronoun, body part or species
# description). Each exception remains offset-specific and never disables
# terminology checks elsewhere.
CRITICAL_TERM_OFFSET_ALLOWLIST = {
    "term_pokemon": frozenset(
        {
            0x032420,
            0x032451,
            0x0324AF,
            0x032B12,
            0x032E2F,
            0x032F2A,
            0x036BD3,
            0x03744B,
            0x03773F,
            0x0398D1,
        }
    ),
}


@dataclass
class Row:
    offset: int
    line: int
    max_len: int
    source_en: str
    fr_text: str
    layout: str = ""


def normalize_token(token: str) -> str:
    return token.lower().replace("@", "é").strip("'")


def words(text: str) -> list[str]:
    return [normalize_token(match.group(0)) for match in WORD_RE.finditer(text)]


def read_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for item in csv.DictReader(handle):
            rows.append(
                Row(
                    offset=int(item["offset_hex"], 16),
                    line=int(item["line"]),
                    max_len=int(item["max_len"] or 0),
                    source_en=item["source_en"].replace("\\n", "\n").replace(
                        "\\r", "\r"
                    ),
                    fr_text=item["fr_text"].replace("\\n", "\n").replace(
                        "\\r", "\r"
                    ),
                    layout=item.get("layout") or "",
                )
            )
    return rows


def build_lexicon(rows: list[Row]) -> set[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(token for token in words(row.fr_text) if len(token) >= 3)
    lexicon = set(FR_SEED_WORDS) | NAME_WHITELIST
    lexicon.update(token for token, count in counter.items() if count >= 2 and 3 <= len(token) <= 16)
    return lexicon


def best_split(token: str, lexicon: set[str]) -> str | None:
    if len(token) < 8 or token in lexicon or token in NAME_WHITELIST:
        return None
    if token.startswith(("poké", "poke", "pkmn")):
        return None
    candidates: list[tuple[int, str, str]] = []
    for index in range(3, len(token) - 2):
        left = token[:index]
        right = token[index:]
        if left in lexicon and right in lexicon:
            score = min(len(left), len(right))
            candidates.append((score, left, right))
    if not candidates:
        return None
    _, left, right = sorted(candidates, reverse=True)[0]
    return f"{left} {right}"


def split_is_dialogue_line_boundary(
    match: re.Match[str],
    split: str,
) -> bool:
    """Ignore joins caused only by the game's 17/19-column page layout."""
    left, _ = split.split(" ", 1)
    boundary = match.start() + len(left)
    return boundary >= 17 and (boundary - 17) % 19 == 0


def add_issue(
    issues: list[dict[str, str | int]],
    row: Row,
    severity: int,
    category: str,
    detail: str,
    rule_id: str = "",
) -> None:
    issues.append(
        {
            "severity": severity,
            "category": category,
            "rule_id": rule_id,
            "offset_hex": f"0x{row.offset:06X}",
            "line": row.line,
            "max_len": row.max_len,
            "fr_len": len(format_game_text(row.fr_text, row.layout)),
            "detail": detail,
            "source_en": row.source_en,
            "fr_text": row.fr_text,
        }
    )


def audit_rows(rows: list[Row]) -> list[dict[str, str | int]]:
    lexicon = build_lexicon(rows)
    issues: list[dict[str, str | int]] = []

    for row in rows:
        encoded = format_game_text(row.fr_text, row.layout)
        if b"?" in encoded and "?" not in row.fr_text:
            add_issue(
                issues,
                row,
                3,
                "encoding_loss",
                "a character will become '?' in the ROM",
                "encoding_loss",
            )

        stripped = row.fr_text.strip()
        for rule in TEXT_RULES:
            if rule.applies_to(row.offset, stripped):
                add_issue(
                    issues,
                    row,
                    rule.severity,
                    rule.category,
                    rule.detail,
                    rule.rule_id,
                )

        clipped_rule = KNOWN_CLIPPED_TEXTS.get(row.offset)
        matched_known_clip = bool(clipped_rule and clipped_rule[0].search(stripped))
        if clipped_rule and matched_known_clip:
            add_issue(
                issues,
                row,
                3,
                "truncated_text",
                clipped_rule[1],
                f"clip_{row.offset:06x}",
            )

        if not matched_known_clip:
            final_word = re.search(
                r"([A-Za-zÀ-ÖØ-öø-ÿ@]+)[.!?…]*\s*$",
                stripped,
            )
            if final_word:
                final_token = normalize_token(final_word.group(1))
                expected = TRUNCATED_ENDINGS.get(final_token)
                if expected:
                    add_issue(
                        issues,
                        row,
                        2,
                        "truncated_ending",
                        f"suspicious ending '{final_word.group(1)}' (expected: {expected})",
                        f"ending_{final_token}",
                    )

        for pattern_index, (regex, category, detail) in enumerate(
            BAD_FRAGMENT_PATTERNS,
            1,
        ):
            if regex.search(stripped):
                add_issue(
                    issues,
                    row,
                    3,
                    category,
                    detail,
                    f"fragment_{pattern_index:02d}",
                )

        for token_match in WORD_RE.finditer(stripped):
            token = normalize_token(token_match.group(0))
            if token in ENGLISH_WHITELIST or token in NAME_WHITELIST:
                continue
            if token in STRONG_ENGLISH_WORDS:
                add_issue(
                    issues,
                    row,
                    2,
                    "english_leak",
                    f"suspicious English word: {token}",
                    f"english_word_{token}",
                )

            split = best_split(token, lexicon)
            if split and not (
                row.layout == ""
                and split_is_dialogue_line_boundary(token_match, split)
            ):
                add_issue(
                    issues,
                    row,
                    2,
                    "possible_glue",
                    f"{token} -> {split}",
                    "possible_glue",
                )

            if token not in SOUND_ALLOWLIST and re.search(r"([a-zé])\1\1", token, re.I):
                add_issue(
                    issues,
                    row,
                    2,
                    "triple_letter",
                    f"suspicious repetition: {token}",
                    "triple_letter",
                )
            if (
                token not in lexicon
                and token not in RARE_DOUBLE_ALLOWLIST
                and re.search(r"([bdfghjkqvwxz])\1", token, re.I)
            ):
                add_issue(
                    issues,
                    row,
                    1,
                    "rare_double",
                    f"rare double letter: {token}",
                    "rare_double",
                )
            if len(token) > 17 and token not in NAME_WHITELIST:
                add_issue(
                    issues,
                    row,
                    1,
                    "long_word",
                    f"very long word: {token}",
                    "long_word",
                )

        source_lower = row.source_en.lower()
        for source_marker, expected_regex, category in CRITICAL_TERM_RULES:
            if row.offset in CRITICAL_TERM_OFFSET_ALLOWLIST.get(
                category,
                frozenset(),
            ):
                continue
            if source_marker.lower() in source_lower and not expected_regex.search(row.fr_text):
                add_issue(
                    issues,
                    row,
                    2,
                    category,
                    f"source term '{source_marker}' missing or inconsistent",
                    category,
                )

    unique_issues: dict[tuple[str, str, str], dict[str, str | int]] = {}
    for issue in issues:
        unique_key = (
            str(issue["offset_hex"]),
            str(issue["rule_id"] or issue["category"]),
            str(issue["detail"]),
        )
        unique_issues.setdefault(unique_key, issue)
    issues = list(unique_issues.values())
    issues.sort(key=lambda item: (-int(item["severity"]), str(item["category"]), int(item["line"])))
    return issues


def command_audit(args: argparse.Namespace) -> int:
    rows = read_rows(ROM_DIR / args.csv)
    issues = audit_rows(rows)
    output = ROM_DIR / args.output

    with output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "severity",
            "category",
            "rule_id",
            "offset_hex",
            "line",
            "max_len",
            "fr_len",
            "detail",
            "source_en",
            "fr_text",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for issue in issues:
            writer.writerow(issue)

    counts = Counter(str(issue["category"]) for issue in issues)
    high = sum(1 for issue in issues if int(issue["severity"]) >= 3)
    medium = sum(1 for issue in issues if int(issue["severity"]) == 2)
    low = sum(1 for issue in issues if int(issue["severity"]) <= 1)

    print("Ambitious quality audit")
    print(f"- Rows analyzed : {len(rows)}")
    print(f"- Suspects: {len(issues)} ({high} high, {medium} medium, {low} low)")
    print(f"- CSV : {output}")
    for category, count in counts.most_common():
        print(f"  {category}: {count}")
    for issue in issues[: args.preview]:
        print(
            f"  [{issue['severity']}] {issue['category']}/{issue['rule_id']} "
            f"{issue['offset_hex']} l.{issue['line']}: {issue['detail']} :: "
            f"{str(issue['fr_text'])[:80]}"
        )
    return 1 if args.fail_on_high and high else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggressive quality audit of French texts.")
    parser.add_argument("--csv", default="traduction_base.csv")
    parser.add_argument("--output", default="audit_qualite_ambitieux.csv")
    parser.add_argument("--preview", type=int, default=40)
    parser.add_argument("--fail-on-high", action="store_true")
    return parser


def main() -> int:
    return command_audit(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
