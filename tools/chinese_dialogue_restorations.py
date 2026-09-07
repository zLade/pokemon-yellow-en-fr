"""French restorations for NJ046 source dialogues removed by the English ROM.

Keys are live source-side pointer slots.  The English patch replaced 80 of
these slots with invalid words, wired four others to unrelated targets and
collapsed one pair of distinct Chinese item messages onto a single English
payload.  The repacker allocates the French payloads in the same PRG pair and
restores each pointer after the ordinary English-derived translations are
applied.
"""

from __future__ import annotations

import json
from pathlib import Path


BASE_RESTORED_DIALOGUES: dict[int, str] = {
    # First removed Rocket conclusion.
    0x033137: "JESSIE : Team Rocket, galaxie... bientôt dissoute !",
    0x033139: "JAMES : Trou noir et avenir perdu !",
    0x03313B: "MIAOUSS : C'est exact !",
    0x03313D: "JAMES : Pourquoi toujours ainsi...",
    0x03313F: "JESSIE : Affreuse sensation...",
    0x033141: "MIAOUSS : Miaouss...",

    # Post-Mewtwo scene and travel ticket.
    0x033193: "SACHA : Mewtwo ?",
    0x033195: (
        "OLGA : Team Rocket a cloné Mewtwo avec les gènes de Mew. "
        "Tu l'as trouvé à temps. Je retourne à la Ligue. "
        "Reviens nous défier !"
    ),
    0x033197: "SACHA : Compte sur moi !",
    0x033199: (
        "OLGA : Un ami m'a offert ce billet mystérieux, mais la Ligue "
        "me retient. Prends-le en remerciement."
    ),

    # Team Nanjing motto and announcement of the new leader.
    0x0331B3: "JESSIE : Puisque vous le demandez...",
    0x0331B5: "JAMES : Répondons par bonté !",
    0x0331B7: "JESSIE : Pour préserver le monde.",
    0x0331B9: "JAMES : Pour maintenir la paix.",
    0x0331BB: "JESSIE : Amour, vérité et mal.",
    0x0331BD: "JAMES : Des méchants de charme !",
    0x0331BF: "JESSIE : Jessie !",
    0x0331C1: "JAMES : James !",
    0x0331C3: "JESSIE : Team Nanjing, galaxie !",
    0x0331C5: "JAMES : Trou blanc, avenir radieux !",
    0x0331C7: "MIAOUSS : Exact ! Miaouss...",
    0x0331C9: "JAMES : Nouveau chef, autre Team !",
    0x0331D1: (
        "JAMES : Tu es fort.\nPourtant,\nnotre nouveau chef,\n"
        "Kameiyu, te battra\navec ses Pokémon !\nHa ha !"
    ),

    # The English ROM incorrectly shares Parlyz Heal and Awakening text.
    0x0348F1: "Anti-Para reçu !",

    # Team Rocket motto at Mt. Moon.
    0x038313: "JAMES : Répondons par bonté !",
    0x038315: "JESSIE : Pour préserver le monde.",
    0x038317: "JAMES : Pour maintenir la paix.",
    0x038319: "JESSIE : Amour, vérité et mal.",
    0x03831B: "JAMES : Des méchants de charme !",
    0x03831D: "JESSIE : Jessie !",
    0x03831F: "JAMES : James !",
    0x038321: "JESSIE : Team Rocket, galaxie !",
    0x038323: "JAMES : Trou blanc, avenir radieux !",
    0x038325: "MIAOUSS : Exact ! Miaouss...",

    # Four Nugget Bridge responses miswired in the English ROM.
    0x038347: "FILLETTE : Tu as fait tes preuves.",
    0x03834B: "GARÇON : Pas mal !",
    0x03834F: "FILLETTE : Je t'aurai à l'oeil.",
    0x038353: "ÉCLAIREUR : Premier à tous nous battre !",

    # Rocket encounter in the hideout.
    0x03AF94: "SACHA : Qui êtes-vous ?",
    0x03AF96: "JESSIE : Puisque vous le demandez...",
    0x03AF98: "JAMES : Répondons par bonté !",
    0x03AF9A: "JESSIE : Pour préserver le monde.",
    0x03AF9C: "JAMES : Pour maintenir la paix.",
    0x03AF9E: "JESSIE : Amour, vérité et mal.",
    0x03AFA0: "JAMES : Des méchants de charme !",
    0x03AFA2: "JESSIE : Jessie !",
    0x03AFA4: "JAMES : James !",
    0x03AFA6: "JESSIE : Team Rocket, galaxie !",
    0x03AFA8: "JAMES : Trou blanc, avenir radieux !",
    0x03AFAA: "MIAOUSS : Exact ! Miaouss...",
    0x03AFAC: "JAMES : Réglons nos vieux comptes !",
    0x03AFB0: "JESSIE : Affreuse sensation...",
    0x03AFB2: "MIAOUSS : Miaouss...",

    # Rocket encounter in Pokemon Tower.
    0x03AFEA: "SACHA : Qui êtes-vous ?",
    0x03AFEC: "JESSIE : Puisque vous le demandez...",
    0x03AFEE: "JAMES : Répondons par bonté !",
    0x03AFF0: "JESSIE : Pour préserver le monde.",
    0x03AFF2: "JAMES : Pour maintenir la paix.",
    0x03AFF4: "JESSIE : Amour, vérité et mal.",
    0x03AFF6: "JAMES : Des méchants de charme !",
    0x03AFF8: "JESSIE : Jessie !",
    0x03AFFA: "JAMES : James !",
    0x03AFFC: "JESSIE : Team Rocket, galaxie !",
    0x03AFFE: "JAMES : Trou blanc, avenir radieux !",
    0x03B000: "MIAOUSS : Exact ! Miaouss...",
    0x03B004: "JESSIE : Affreuse sensation...",
    0x03B006: "MIAOUSS : Miaouss...",

    # Team Rocket encounter at Silph Co.
    0x03CF3E: "JESSIE : Puisque vous le demandez...",
    0x03CF40: "JAMES : Répondons par bonté !",
    0x03CF42: "JESSIE : Pour préserver le monde.",
    0x03CF44: "JAMES : Pour maintenir la paix.",
    0x03CF46: "JESSIE : Amour, vérité et mal.",
    0x03CF48: "JAMES : Des méchants de charme !",
    0x03CF4A: "JESSIE : Jessie !",
    0x03CF4C: "JAMES : James !",
    0x03CF4E: "JESSIE : Team Rocket, galaxie !",
    0x03CF50: "JAMES : Trou blanc, avenir radieux !",
    0x03CF52: "MIAOUSS : Exact ! Miaouss...",
    0x03CF54: "JAMES : Encore comme toujours...",
    0x03CF56: "JESSIE : Affreuse sensation...",
    0x03CF58: "MIAOUSS : Miaouss...",

    # Final Rocket motto.
    0x03D07A: "JAMES : Pour maintenir la paix.",
    0x03D07C: "JESSIE : Amour, vérité et mal.",
    0x03D07E: "JAMES : Des méchants de charme !",
    0x03D080: "JESSIE : Jessie !",
}


REMOVED_ENGLISH_POINTER_COUNT = 80
BAD_ENGLISH_POINTER_COUNT = 4
COLLAPSED_ENGLISH_POINTER_TARGETS = {0x0348F1: 0x03499D}
COLLAPSED_ENGLISH_POINTER_REFERENCES = frozenset(
    COLLAPSED_ENGLISH_POINTER_TARGETS
)
COLLAPSED_ENGLISH_POINTER_COUNT = len(
    COLLAPSED_ENGLISH_POINTER_REFERENCES
)
EXPECTED_RESTORATION_COUNT = (
    REMOVED_ENGLISH_POINTER_COUNT
    + BAD_ENGLISH_POINTER_COUNT
    + COLLAPSED_ENGLISH_POINTER_COUNT
)

# The Chinese ROM spreads the motto over eleven separate records. The
# French Game Boy Pokemon Yellow does not include this motto, so these
# passages use its French anime adaptation.
ANIME_MOTTO_RESTORATION_REFERENCES = frozenset(
    {
        # Complete Team Nanjing motto.
        0x0331B3, 0x0331B5, 0x0331B7, 0x0331B9, 0x0331BB,
        0x0331BD, 0x0331BF, 0x0331C1, 0x0331C3, 0x0331C5,
        0x0331C7,
        # Mt. Moon: the first line remains in the main script.
        0x038313, 0x038315, 0x038317, 0x038319, 0x03831B,
        0x03831D, 0x03831F, 0x038321, 0x038323, 0x038325,
        # Rocket hideout.
        0x03AF96, 0x03AF98, 0x03AF9A, 0x03AF9C, 0x03AF9E,
        0x03AFA0, 0x03AFA2, 0x03AFA4, 0x03AFA6, 0x03AFA8,
        0x03AFAA,
        # Pokemon Tower.
        0x03AFEC, 0x03AFEE, 0x03AFF0, 0x03AFF2, 0x03AFF4,
        0x03AFF6, 0x03AFF8, 0x03AFFA, 0x03AFFC, 0x03AFFE,
        0x03B000,
        # Silph Co.
        0x03CF3E, 0x03CF40, 0x03CF42, 0x03CF44, 0x03CF46,
        0x03CF48, 0x03CF4A, 0x03CF4C, 0x03CF4E, 0x03CF50,
        0x03CF52,
        # Final motto, of which only four segments had been removed.
        0x03D07A, 0x03D07C, 0x03D07E, 0x03D080,
    }
)

# These conclusions correspond directly to the four encounters with the trio
# in Pokemon Yellow, so the official French Game Boy wording takes
# priority for these reference payloads.
OFFICIAL_YELLOW_RESTORATION_REFERENCES = frozenset(
    {0x03AFB0, 0x03B004, 0x03CF54, 0x03CF56, 0x03CF58}
)

EXPECTED_RESTORATION_NATURALIZATION_COUNT = 85

if len(BASE_RESTORED_DIALOGUES) != EXPECTED_RESTORATION_COUNT:
    raise ValueError(
        f"{len(BASE_RESTORED_DIALOGUES)} restorations instead of "
        f"{EXPECTED_RESTORATION_COUNT}"
    )


RESTORATION_NATURALIZATION_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "french_restoration_naturalization_overrides.json"
)


def _load_restoration_naturalization_overrides() -> dict[int, str]:
    document = json.loads(
        RESTORATION_NATURALIZATION_PATH.read_text(encoding="utf-8")
    )
    if not isinstance(document, dict):
        raise ValueError(
            f"{RESTORATION_NATURALIZATION_PATH}: "
            "the root must be a JSON object"
        )
    overrides = {
        int(reference, 0): str(text)
        for reference, text in document.items()
    }
    unknown = set(overrides) - set(BASE_RESTORED_DIALOGUES)
    if unknown:
        rendered = ", ".join(
            f"0x{reference:06X}" for reference in sorted(unknown)
        )
        raise ValueError(
            "Unknown restoration naturalizations: " + rendered
        )
    return overrides


RESTORATION_NATURALIZATION_OVERRIDES = (
    _load_restoration_naturalization_overrides()
)
if (
    len(RESTORATION_NATURALIZATION_OVERRIDES)
    != EXPECTED_RESTORATION_NATURALIZATION_COUNT
):
    raise ValueError(
        f"{len(RESTORATION_NATURALIZATION_OVERRIDES)} restoration naturalizations "
        f"instead of "
        f"{EXPECTED_RESTORATION_NATURALIZATION_COUNT}"
    )
for provenance_name, references in (
    ("anime motto", ANIME_MOTTO_RESTORATION_REFERENCES),
    ("Pokémon Yellow", OFFICIAL_YELLOW_RESTORATION_REFERENCES),
):
    missing = references - set(RESTORATION_NATURALIZATION_OVERRIDES)
    if missing:
        rendered = ", ".join(
            f"0x{reference:06X}" for reference in sorted(missing)
        )
        raise ValueError(
            f"{provenance_name} references missing from naturalization: "
            + rendered
        )
RESTORED_DIALOGUES = {
    **BASE_RESTORED_DIALOGUES,
    **RESTORATION_NATURALIZATION_OVERRIDES,
}
