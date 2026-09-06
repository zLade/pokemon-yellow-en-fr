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
    # Première conclusion Rocket supprimée.
    0x033137: "JESSIE : Team Rocket, galaxie... bientôt dissoute !",
    0x033139: "JAMES : Trou noir et avenir perdu !",
    0x03313B: "MIAOUSS : C'est exact !",
    0x03313D: "JAMES : Pourquoi toujours ainsi...",
    0x03313F: "JESSIE : Affreuse sensation...",
    0x033141: "MIAOUSS : Miaouss...",

    # Scène post-Mewtwo et billet de voyage.
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

    # Devise de la Team Nanjing et annonce du nouveau chef.
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

    # La ROM anglaise mutualise par erreur Anti-Para et Réveil.
    0x0348F1: "Anti-Para reçu !",

    # Devise Rocket du Mont Sélénite.
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

    # Quatre réponses du Pont Pépite mal câblées dans la ROM anglaise.
    0x038347: "FILLETTE : Tu as fait tes preuves.",
    0x03834B: "GARÇON : Pas mal !",
    0x03834F: "FILLETTE : Je t'aurai à l'oeil.",
    0x038353: "ÉCLAIREUR : Premier à tous nous battre !",

    # Rencontre Rocket dans le repaire.
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

    # Rencontre Rocket à la Tour Pokémon.
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

    # Rencontre Rocket chez Sylphe SARL.
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

    # Dernière devise Rocket.
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

# La ROM chinoise récite la devise sur onze enregistrements séparés. La
# version Game Boy française de Pokémon Jaune ne contient pas cette devise :
# ces passages emploient donc son adaptation française issue de l'anime.
ANIME_MOTTO_RESTORATION_REFERENCES = frozenset(
    {
        # Devise complète de la Team Nanjing.
        0x0331B3, 0x0331B5, 0x0331B7, 0x0331B9, 0x0331BB,
        0x0331BD, 0x0331BF, 0x0331C1, 0x0331C3, 0x0331C5,
        0x0331C7,
        # Mont Sélénite : la première réplique reste dans le script principal.
        0x038313, 0x038315, 0x038317, 0x038319, 0x03831B,
        0x03831D, 0x03831F, 0x038321, 0x038323, 0x038325,
        # Repaire Rocket.
        0x03AF96, 0x03AF98, 0x03AF9A, 0x03AF9C, 0x03AF9E,
        0x03AFA0, 0x03AFA2, 0x03AFA4, 0x03AFA6, 0x03AFA8,
        0x03AFAA,
        # Tour Pokémon.
        0x03AFEC, 0x03AFEE, 0x03AFF0, 0x03AFF2, 0x03AFF4,
        0x03AFF6, 0x03AFF8, 0x03AFFA, 0x03AFFC, 0x03AFFE,
        0x03B000,
        # Sylphe SARL.
        0x03CF3E, 0x03CF40, 0x03CF42, 0x03CF44, 0x03CF46,
        0x03CF48, 0x03CF4A, 0x03CF4C, 0x03CF4E, 0x03CF50,
        0x03CF52,
        # Dernière devise, dont seuls quatre segments avaient été supprimés.
        0x03D07A, 0x03D07C, 0x03D07E, 0x03D080,
    }
)

# Ces conclusions correspondent directement aux quatre rencontres du trio
# dans Pokémon Jaune ; elles reprennent donc prioritairement le texte officiel
# de la version française du jeu Game Boy.
OFFICIAL_YELLOW_RESTORATION_REFERENCES = frozenset(
    {0x03AFB0, 0x03B004, 0x03CF54, 0x03CF56, 0x03CF58}
)

EXPECTED_RESTORATION_NATURALIZATION_COUNT = 85

if len(BASE_RESTORED_DIALOGUES) != EXPECTED_RESTORATION_COUNT:
    raise ValueError(
        f"{len(BASE_RESTORED_DIALOGUES)} restaurations au lieu de "
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
            "la racine doit être un objet JSON"
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
            "naturalisations de restaurations inconnues : " + rendered
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
        f"{len(RESTORATION_NATURALIZATION_OVERRIDES)} naturalisations "
        f"restaurées au lieu de "
        f"{EXPECTED_RESTORATION_NATURALIZATION_COUNT}"
    )
for provenance_name, references in (
    ("devise de l'anime", ANIME_MOTTO_RESTORATION_REFERENCES),
    ("Pokémon Jaune", OFFICIAL_YELLOW_RESTORATION_REFERENCES),
):
    missing = references - set(RESTORATION_NATURALIZATION_OVERRIDES)
    if missing:
        rendered = ", ".join(
            f"0x{reference:06X}" for reference in sorted(missing)
        )
        raise ValueError(
            f"références {provenance_name} absentes de la naturalisation : "
            + rendered
        )
RESTORED_DIALOGUES = {
    **BASE_RESTORED_DIALOGUES,
    **RESTORATION_NATURALIZATION_OVERRIDES,
}
