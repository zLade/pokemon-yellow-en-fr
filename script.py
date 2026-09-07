#!/usr/bin/env python3
"""
POKEMON YELLOW NES (NJ046) — French reference corpus.

This corpus is retained for structural comparison and French non-regression
tests. The English build uses locales/en-US/catalog.csv, not these payloads.

Reference workflow:
  python3 rom_traduction_assistant.py dump-script
  python3 rom_traduction_assistant.py build-repacked
  python3 tools/title_screen_tools.py patch-french-graphics

Direct execution is disabled: the historical fixed-width writer could silently
truncate text. Build deliverables through the repacked pipeline instead.

Each p(0xOFFSET, "French text") call records a translation at a source offset.
The dialogue_19_19 layout wraps whole words without splitting between pages.
The introduction uses 17 columns on its first line, then 19 columns.
The pokedex_13x4 layout uses four lines of thirteen columns.
Repacking relocates dialogue and updates its pointers. Fixed labels must fit
their source storage. Byte 0x0D separates in-game ASCII blocks.
French accents have dedicated glyphs; ligatures use the two-column oe/OE
fallback to preserve ASCII letters. Leading zeroes represent original 0x30
padding. Do not change offsets without checking the pointer topology.

Preserve visible line widths and validate changes with the text audits,
validate_repacked.py, validate_mapper163.py and the Dendy/NTSC/PAL Mesen suite.










"""

import os, sys

from tools.french_font import encode_game_text

if __name__ == "__main__":
    print(
        "ERREUR: script.py est une source de donnees, pas un builder. "
        "Utilisez `python3 rom_traduction_assistant.py dump-script`, puis "
        "`python3 rom_traduction_assistant.py build-repacked`."
    )
    raise SystemExit(2)

# ============================================================
# CONFIGURATION
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROM_INPUT  = os.path.join(SCRIPT_DIR, "yellow.nes")
ROM_OUTPUT = os.path.join(SCRIPT_DIR, "Pokemon_Jaune_FR.nes")
IPS_OUTPUT = os.path.join(SCRIPT_DIR, "Pokemon_Jaune_FR.ips")

# ============================================================
# PATCH ENGINE (do not edit)
# ============================================================
if not os.path.exists(ROM_INPUT):
    print(f"ERREUR: ROM introuvable: {ROM_INPUT}")
    print("Placez la ROM originale dans le meme dossier que ce script.")
    sys.exit(1)

with open(ROM_INPUT, 'rb') as f:
    orig = f.read()
rom = bytearray(orig)

patch_count = 0
warnings = []

def p(offset, fr_text, layout=""):
    """
Historical fixed-width writer for the text at the given offset.
Reads the original contiguous ASCII length and pads or truncates French text.
The translation assistant reads the layout argument. Direct execution remains
disabled and must never be used to produce a release ROM.

"""
    global patch_count
    # Measure the original ASCII text length at this offset
    length = 0
    while offset + length < len(rom) and 0x20 <= rom[offset + length] <= 0x7E:
        length += 1
    if length < 1:
        warnings.append(f"SKIP 0x{offset:06X}: pas de texte ASCII a cet offset")
        return
    fr = encode_game_text(fr_text)
    if len(fr) > length:
        warnings.append(f"TRONQUE 0x{offset:06X}: '{fr_text[:30]}...' ({len(fr)} > {length})")
        fr = fr[:length]
    fr = fr.ljust(length)  # Pad with spaces
    rom[offset:offset+length] = fr
    patch_count += 1


# ############################################################
# ############################################################
# ##                                                        ##
# ##          TRANSLATION CORPUS                           ##
# ##    (French reference text for non-regression tests)   ##
# ##                                                        ##
# ############################################################
# ############################################################


# ============================================================
# 1. BATTLE / SYSTEM TEXT
# ============================================================

p(0x0301D7, "0000000000Apparaît!")
p(0x0301F9, " K.O.!  ")
p(0x030203, " Exp gagnée!")
p(0x030210, "Fuite réussie!  ")
p(0x030221, "Lance  ")
p(0x03022A, "Oui! ")
p(0x030230, "000000000Oh non! ")
p(0x030242, "S'échappe! ")
p(0x03024E, "00000000est capturé!")
p(0x030262, "0envoie   ")
p(0x03026D, "Fuite impossible!    ")
p(0x030290, "Le Dresseur bloque la Poké Ball!")
p(0x0302A9, "0000000000À ton tour")
p(0x0302BF, " util")
p(0x0302C5, "Bon coup!")
p(0x0302CF, "0Peu efficace!     ")
p(0x0302EE, "est empoisonné")
p(0x0302FA, " Recule ")
p(0x030304, "est brûlé")
p(0x03030E, "est confus ")
p(0x03031A, "est gelé ")
p(0x030324, "000000souffre du poison!    ")
p(0x030341, "dort     ")
p(0x03034B, "0souffre de brûlure!    ")
p(0x030364, "000est confus")
p(0x030373, "0000est gelé")
p(0x0303A9, "  ne monte plus! ")
p(0x0303D6, " ne baisse plus")
p(0x030409, " évolue!    ")
p(0x030428, " apprend")
p(0x03043F, "000000Déjà 4 attaques!")
p(0x03045F, "Oublie ")
p(0x030479, "Quelle attaque?")
p(0x03048C, " Monte bcp! ")
p(0x03049A, "000Apprend ")
p(0x0304AB, "00000000 N'apprend pas")
p(0x030660, "0000000000000Changer Pokémon")
p(0x03067D, "000Monte au niv. ")
p(0x030898, "Il stocke de l'énergie dans le bulbe de son dos.", layout="pokedex_13x4")
p(0x0308C7, " Déchaîne! ")
p(0x030902, "0000000000Sac plein!  ")
p(0x030919, "00000000Pas en stock!")
p(0x030955, "00000000000000000PV restaurés !")
p(0x030AB5, " Exp. gagnée!     ")
p(0x030AC9, "Pas assez d'$!   ")
p(0x030ADB, "Battu    ")
p(0x030AE5, "Util. Lutte!  ")

# ============================================================
# 2. BATTLE MENU
# ============================================================

p(0x030588, "Att. ")      # Fight
p(0x03058E, "Objet")      # Item
p(0x030594, "PKMN")       # PKMN
p(0x030599, " Fu")        # Run

# ============================================================
# 3. BATTLE INTERFACE
# ============================================================

p(0x0305E8, "Envoi ")
p(0x030602, "Balle")
p(0x030608, "00CT/CS ")     # TM/HMs
p(0x030634, "Ennemi")       # Enemy
p(0x030646, "Envoyer un Pokémon?")
p(0x030659, "Oui Non")      # Yes No
p(0x0306C9, "PV restaurés !")   # Recovered HP
p(0x03070B, "se réveille!")  # Woke up
p(0x03075C, "Obtenu! ")      # You got
p(0x030765, "Perdu")         # Lost
p(0x03076B, "00Dresseur")    # Trainer

# ============================================================
# 4. PC BOXES
# ============================================================

p(0x0307E1, "Bte 1")
p(0x0307E9, "Bte 2")   # Note: offset within the "00Box 2" block
p(0x0307F1, "Bte 3")
p(0x0307F9, "Bte 4")
p(0x030801, "Bte 5")
p(0x030809, "Bte 6")
p(0x030811, "Bte 7")
p(0x030819, "Bte 8")

# ============================================================
# 5. SHOP / TRADING
# ============================================================

p(0x0308D3, "0Boutique   ")      # Item Shop
p(0x0308E9, "Combien?    ")      # How Many?
p(0x0308F6, "Merci!     ")       # Thank you!
p(0x03092D, "Pas de Pokémon")       # No Pokemon!
p(0x030939, "Dégâts de recul!")   # Hit with recoil
p(0x035D9B, "Visiter  Partir", layout="dialogue_19_19")   # Buy Leave
p(0x038130, "Soigner  Partir", layout="dialogue_19_19")  # Heal Leave
p(0x038194, "Acheter  Annuler", layout="dialogue_19_19")   # Buy Pass
p(0x0381C1, "Karaté  Taekwondo", layout="dialogue_19_19")   # Left Right
p(0x0381AF, "Oui     Non", layout="dialogue_19_19")  # Yes No

# ============================================================
# 6. PROFESSOR OAK INTRODUCTION
# ============================================================

# The introduction uses a separate renderer: 17 columns on the very
# first line, then 19. In-game dialogue uses 19 columns throughout.
p(
    0x03082C,
    "PROF. CHEN :\nBien le bonjour !\nBienvenue !\nVoici le monde\ndes Pokémon !\nMoi, c'est Chen,\nle Prof Pokémon !\nIci vivent\ndes créatures\nappelées Pokémon !",
    layout="dialogue_intro_17_19",
)

p(
    0x035DCC,
    "Ce monde abrite\ndes créatures\nappelées Pokémon !\nCertains en font\ndes compagnons.\nD'autres les font\ncombattre.\nMoi, je les étudie.",
    layout="dialogue_intro_17_19",
)

p(
    0x035E82,
    "SACHA !\nTa quête Pokémon\nva commencer !\nUn monde de rêves\net d'aventures\nt'attend !",
    layout="dialogue_intro_17_19",
)

# ============================================================
# 7. HOME / MOM
# ============================================================

p(
    0x03F27B,
    "MAMAN : C'est vrai.\nTous les garçons\npartent un jour.\nLa télé l'a dit !\nLe Prof te cherche.\nIl est à côté.",
    layout="dialogue_19_19",
)

# ============================================================
# 8. PROFESSOR OAK LAB / DEPARTURE
# ============================================================

p(
    0x03F2EE,
    "PROF. CHEN : Régis ? Déjà là ? Je t'avais dit d'attendre. Sacha, cette Poké Ball contient ton Pokémon. Prends-la !",
    layout="dialogue_19_19",
)

p(
    0x03F426,
    (
        (
            (
                (
                    (
                        (
                            (
                                (
                                    "PROF. CHEN :\n"
                                    "Sacha, Régis !\n"
                                    "J'ai une mission :\n"
                                    "le Pokédex recense\n"
                                    "chaque Pokémon vu.\n"
                                    "Ils sont à vous !"
                                )
                            )
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03F3D2,
    "Bienvenue !\nAu Centre Pokémon,\nnous soignons\ntes Pokémon !",
    layout="dialogue_19_19",
)

p(0x03F5A3,
  (
      (
          (
              "Il dort ?\n"
              "Attendons un peu."
          )
      )
  ),
  layout="dialogue_19_19")

p(
    0x03F5F5,
    "Je vais te montrer\nmes talents !",
    layout="dialogue_19_19",
)

# ============================================================
# 9. PALLET TOWN / RIVAL
# ============================================================

p(
    0x038445,
    "PROF. CHEN :\nBien le bonjour !\nBienvenue !\nVoici le monde\nmagique\ndes Pokémon !\nMon nom est Chen,\nle Prof Pokémon !\nDes Pokémon\nvivent partout.\nCertains sont\nnos compagnons.\nD'autres les font\ncombattre.\nMoi, je les étudie.\nSacha !\nTa quête commence !\nRêves et aventures\nt'attendent !",
    layout="dialogue_19_19",
)

p(
    0x0384F8,
    (
        "RÉGIS : Hé, Sacha !\n"
        "Pépé n'est pas là !\n"
        "Pour un Pokémon,\n"
        "j'ai rappliqué !"
    ),
    layout="dialogue_19_19",
)

p(
    0x038519,
    "PROF. CHEN :\nNe sors pas !\nDes Pokémon rôdent\ndans les herbes.\nIl t'en faut un.\nSuis-moi !",
    layout="dialogue_19_19",
)

p(0x0385A7, (
                (
                    (
                        'RÉGIS : Pépé !\nTe voilà !'
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x0385D6,
    "RÉGIS : Pépé ! C'est pas juste ! Et moi ?",
    layout="dialogue_19_19",
)

p(
    0x0385F3,
    "PROF. CHEN :\nPatience, Régis.\nTu l'auras bientôt.",
    layout="dialogue_19_19",
)

p(
    0x038620,
    "RÉGIS : Pff ! J'aurai un meilleur Pokémon que toi !",
    layout="dialogue_19_19",
)
p(
    0x03864F,
    "RÉGIS : Non !\nIl est à moi !",
    layout="dialogue_19_19",
)
p(
    0x038670,
    "PROF. CHEN :\nRégis !\nQue fais-tu ?",
    layout="dialogue_19_19",
)
p(
    0x03868A,
    "RÉGIS :\nPépé, je le veux !",
    layout="dialogue_19_19",
)

p(
    0x0386A2,
    "PROF. CHEN :\nBon, d'accord.\nIl est à toi.\nJe comptais déjà\nt'en donner un.\nSacha, viens ici !",
    layout="dialogue_19_19",
)

p(
    0x038715,
    (
        (
            (
                (
                    (
                        (
                            "PROF. CHEN :\n"
                            "Je l'ai capturé.\n"
                            "Il craint encore\n"
                            "les humains."
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)
p(0x038744, "Pikachu reçu !", layout="dialogue_19_19")

p(
    0x038755,
    "RÉGIS : Sacha !\nTestons-les.\nJe te défie !",
    layout="dialogue_19_19",
)

p(
    0x0387A0,
    (
        "RÉGIS : Ton Pokémon est fort ! Je vais entraîner le mien ailleurs. À plus, Sacha ! Salut, Papy !"
    ),
    layout="dialogue_19_19",
)

p(
    0x0387F3,
    "Bourg Palette ? Porte la commande du Prof. Chen !",
    layout="dialogue_19_19",
)

p(0x038945, "CHEN : Ma Poké Ball spéciale ! Merci. J'ai une mission.", layout="dialogue_19_19")

p(0x038950, (
                (
                    (
                        (
                            (
                                "RÉGIS : Papy !\n"
                                "Mon Pokémon a\n"
                                "grandi ! Regarde !"
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03897B, "Pokédex obtenu !", layout="dialogue_19_19")
p(0x03898D, (
                (
                    (
                        (
                            (
                                "PROF. CHEN :\n"
                                "Mon rêve : finir\n"
                                "le Pokédex complet.\n"
                                "Je suis trop vieux.\n"
                                "Prenez le relais !"
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")

p(0x0389B4,
  (
      (
          (
              (
                  (
                      "RÉGIS : Papy,\n"
                      "confie-moi tout !\n"
                      "Dommage pour Sacha.\n"
                      "Je prends la Carte\n"
                      "chez ma sœur. Toi,\n"
                      "tu ne l'auras pas !\n"
                      "Ha ha !"
                  )
              )
          )
      )
  ),
  layout="dialogue_19_19")

p(
    0x038A46,
    "SŒUR DE RÉGIS :\nPépé t'envoie\nen course ?\nTiens, ça t'aidera.",
    layout="dialogue_19_19",
)

p(0x038A8E, "Carte obtenue !", layout="dialogue_19_19")

p(
    0x038AA1,
    (
        (
            (
                (
                    "Quel mal de tête...\n"
                    "Je te bloquais ?\n"
                    "Pour le Pokédex,\n"
                    "achète\n"
                    "des Poké Balls !"
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x038AEE,
    "L'Arène est fermée à clé.",
    layout="dialogue_19_19",
)

# ============================================================
# 10. RIVAL GARY ENCOUNTERS
# ============================================================

p(
    0x038B03,
    "RÉGIS : Sacha !\nTu vas à la Ligue ?\nPas de Badge ?\nPassage interdit !\nTes Pokémon\nont progressé ?",
    layout="dialogue_19_19",
)

p(
    0x038BBC,
    "RÉGIS : La Ligue regorge de grands Dresseurs. Je passerai. Toi aussi, avance !",
    layout="dialogue_19_19",
)

p(0x038C50, (
                (
                    "Tu vises le titre ?\n"
                    "Alors, bats-moi !"
                )
            ), layout="dialogue_19_19")
p(
    0x038C6C,
    (
        "T'es fort, toi !"
    ),
    layout="dialogue_19_19",
)
p(0x038C8D, "Impossible...", layout="dialogue_19_19")

# ============================================================
# 11. VIRIDIAN FOREST / ROUTES 1–3
# ============================================================

p(0x038CA8, (
                "Toi aussi, t'es\n"
                "Dresseur ? Alors,\n"
                "battons-nous !"
            ), layout="dialogue_19_19")
p(
    0x038CC6,
    "Tu es vraiment fort...",
    layout="dialogue_19_19",
)
p(0x038CD8, "Ne te défile pas ! Viens te battre !", layout="dialogue_19_19")
p(0x038CF6, (
                (
                    "J'ai perdu."
                )
            ), layout="dialogue_19_19")
p(0x038D11, (
                (
                    "Tu refuses donc\n"
                    "de nous suivre..."
                )
            ), layout="dialogue_19_19")
p(
    0x039193,
    "Hé ! Pas de short ?",
    layout="dialogue_19_19",
)
p(0x0391B2, (
                (
                    "Encore perdu..."
                )
            ), layout="dialogue_19_19")
p(
    0x0391D2,
    (
        (
            "Ma nouvelle prise\n"
            "va t'affronter !"
        )
    ),
    layout="dialogue_19_19",
)
p(0x0391EE, "T'es très fort !", layout="dialogue_19_19")
p(
    0x039215,
    "Aah ! Tu m'as touchée ?!",
    layout="dialogue_19_19",
)

# ============================================================
# 12. PEWTER GYM (Brock)
# ============================================================

p(
    0x038D7A,
    "Tu es Dresseur ?\nPierre cherche\nun adversaire.\nSuis-moi !",
    layout="dialogue_19_19",
)
p(
    0x038D9F,
    "Si tu es prêt,\nva défier Pierre !",
    layout="dialogue_19_19",
)

p(
    0x038DBF,
    "Hé, Champion !\nLes Pokémon Sol\nde Pierre ignorent\nl'Électrik.\nDur pour Pikachu !",
    layout="dialogue_19_19",
)

p(0x038E2C, (
                (
                    (
                        (
                            "Défier Pierre ?\n"
                            "Tu es à dix mille\n"
                            "années-lumière !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x038E60, (
                (
                    (
                        (
                            "Tu es fort. Pierre l'est encore plus !"
                        )
                    )
                )
            ), layout="dialogue_19_19")

p(
    0x038E86,
    (
        (
            (
                (
                    "PIERRE : Je suis\n"
                    "Champion d'Argenta.\n"
                    "Mes Pokémon Roche\n"
                    "sont très solides !\n"
                    "Même si je perds,\n"
                    "je me battrai.\n"
                    "En garde !"
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x038EFE,
    "PIERRE : Bravo ! Voici le Badge Roche !",
    layout="dialogue_19_19",
)

p(0x038F49, "Badge Roche reçu !", layout="dialogue_19_19")
p(0x038F82, (
                (
                    (
                        "PIERRE : Ce Badge renforce tes Pokémon. Flash marche hors combat. Tiens !"
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x038F91,
    (
        "CT35 reçue !"
    ),
    layout="dialogue_19_19",
)
p(
    0x038FCA,
    (
        (
            (
                (
                    (
                        (
                            "PIERRE : Chaque CT\n"
                            "sert une fois.\n"
                            "Choisis bien !\n"
                            "CT35 : Armure\n"
                            "monte la Défense."
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x03900E,
  (
      (
          (
              "PIERRE : Élevage ou combat, chacun sa voie. Pour progresser, va défier l'Arène d'Azuria !"
          )
      )
  ),
  layout="dialogue_19_19")

p(
    0x03906E,
    "Je le savais ! Tu as l'étoffe d'un Champion !",
    layout="dialogue_19_19",
)

# ============================================================
# 13. ROUTE 4 / MT. MOON
# ============================================================

p(0x0330C1, "Mont Sélénite")
p(0x03909E, 'Hé ! Tu me fixais ?', layout="dialogue_19_19")
p(0x0390BD, (
                (
                    (
                        (
                            "Arrête de fixer,\n"
                            "ou je te frappe !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x0390CA,
    "Hé ! On s'est vus\ndans la Forêt\nde Jade !",
    layout="dialogue_19_19",
)
p(0x0390EE, (
                (
                    "Ici, les Pokémon\n"
                    "diffèrent de ceux\n"
                    "de la forêt."
                )
            ), layout="dialogue_19_19")
p(0x039101, (
                (
                    "Les shorts, c'est\n"
                    "pratique ! Essaie !"
                )
            ), layout="dialogue_19_19")
p(
    0x039121,
    (
        (
            "Après six Pokémon, les suivants sont envoyés au PC."
        )
    ),
    layout="dialogue_19_19",
)
p(0x039147, (
                (
                    "Tu es Dresseur ?\n"
                    "Alors, en garde !"
                )
            ), layout="dialogue_19_19")
p(0x039167, (
                (
                    "Quelle blague..."
                )
            ), layout="dialogue_19_19")
p(0x03922D, (
                (
                    (
                        "Ah, je m'étais trompée..."
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x039251,
    "Ton regard...\nÇa me gêne !",
    layout="dialogue_19_19",
)
p(
    0x039278,
    "Pas de combat ?\nÉvite les regards !",
    layout="dialogue_19_19",
)

p(
    0x0392A6,
    "Bonjour l'ami !\nJ'ai une super\naffaire !\nUn Magicarpe :\njuste 500 $ !\nQu'en dis-tu ?",
    layout="dialogue_19_19",
)
p(0x0392F0, "Magicarpe reçu !", layout="dialogue_19_19")
p(
    0x039303,
    "Un homme suspect\nrôde dans le coin.\nEt toi, t'es qui ?",
    layout="dialogue_19_19",
)
p(
    0x039334,
    "On m'a bien eu !\nC'était un membre\nde la Team Rocket !",
    layout="dialogue_19_19",
)
p(
    0x039359,
    "Quoi ? J'attends mes amis perdus dans la grotte !",
    layout="dialogue_19_19",
)
p(
    0x039385,
    "Je suis venue\npour les fossiles\nrares cachés ici.",
    layout="dialogue_19_19",
)
p(
    0x0393B1,
    "TEAM ROCKET :\nMafia Pokémon,\nforte et redoutée !",
    layout="dialogue_19_19",
)
p(0x0393D6, (
                (
                    "Tu me fais encore plus peur..."
                )
            ), layout="dialogue_19_19")
p(
    0x0393ED,
    "Cette grotte est immense !",
    layout="dialogue_19_19",
)
p(
    0x039404,
    "C'est immense... Où est la sortie ?",
    layout="dialogue_19_19",
)
p(
    0x039420,
    "Tu explores aussi ?",
    layout="dialogue_19_19",
)
p(
    0x039440,
    "Mais où sont donc\nles Pokémon rares ?",
    layout="dialogue_19_19",
)
p(
    0x039463,
    "Oh ! Un gamin !\nTu m'as fait peur !",
    layout="dialogue_19_19",
)
p(
    0x039477,
    "Il fait trop sombre\npour un enfant !",
    layout="dialogue_19_19",
)
p(
    0x03949D,
    "On a du travail !\nRentre chez toi,\ngamin !",
    layout="dialogue_19_19",
)
p(0x0394C3, (
                (
                    "Pas mal ! Rejoins\n"
                    "la Team Rocket !"
                )
            ), layout="dialogue_19_19")
p(
    0x0394F0,
    "Fourrer ton nez\ndans les affaires\ndes adultes,\nc'est dangereux !",
    layout="dialogue_19_19",
)
p(0x039514, "Ça m'énerve !", layout="dialogue_19_19")
p(
    0x039540,
    "Stop ! J'ai trouvé ces deux fossiles. Ils sont à moi !",
    layout="dialogue_19_19",
)
p(
    0x03956C,
    "Ne me surprends pas\ncomme ça !",
    layout="dialogue_19_19",
)
p(0x039589, (
                "..."
            ), layout="dialogue_19_19")
p(
    0x0395AE,
    "Bon, partageons :\nun fossile chacun.\nPas question\nde tout garder !",
    layout="dialogue_19_19",
)

p(0x0395E5,
  (
      (
          (
              (
                  (
                      (
                          "À Cramois'Île,\n"
                          "un labo redonne\n"
                          "vie aux Pokémon\n"
                          "tirés de fossiles."
                      )
                  )
              )
          )
      )
  ),
  layout="dialogue_19_19")

# ============================================================
# 14. JESSIE & JAMES (Mt. Moon)
# ============================================================

p(0x039660, (
                (
                    (
                        "TEAM ROCKET : Hop là ! Ce fossile est à la Team Rocket ! Rends-toi ou mange ta baffe !"
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x039698,
    (
        (
            (
                (
                    (
                        "SACHA :\n"
                        "Qui êtes-vous ?"
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)
p(0x0396C5, (
                (
                    "JESSIE :\n"
                    "Nous revoilà !"
                )
            ), layout="dialogue_19_19")
p(0x0396E6, "TEAM ROCKET : ??? Ce mioche a gagné ?",
  layout="dialogue_19_19")
p(0x0396FD, (
                (
                    "TEAM ROCKET :\n"
                    "La Team Rocket..."
                )
            ), layout="dialogue_19_19")
p(
    0x03971B,
    (
        (
            (
                (
                    "À la vitesse\n"
                    "de la lumière..."
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

# ============================================================
# 15. CERULEAN CITY / MISTY GYM
# ============================================================

p(
    0x039770,
    "POLICIER : Ces gens\nont été volés.\nLe coupable ?\nLa Team Rocket !\nMême la police\npeine face à eux !",
    layout="dialogue_19_19",
)

p(
    0x0397E8,
    "Hé, Champion !\nOndine utilise\ndes Pokémon Eau.\nPlante absorbe\nl'eau.\nÉlectrik paralyse !",
    layout="dialogue_19_19",
)

p(0x039861, (
                "Ton adversaire ?\n"
                "C'est moi !"
            ), layout="dialogue_19_19")
p(
    0x039875,
    "Ondine est forte. Elle ne perdra pas contre toi !",
    layout="dialogue_19_19",
)
p(
    0x03989A,
    "Je peux te battre seule. Pas besoin d'Ondine !",
    layout="dialogue_19_19",
)
p(
    0x0398BD,
    "J'ai perdu...",
    layout="dialogue_19_19",
)

p(
    0x039937,
    (
        (
            (
                (
                    (
                        (
                            (
                                (
                                    "ONDINE : Battue...\n"
                                    "Prends le Badge\n"
                                    "Cascade ! Coupe\n"
                                    "marche hors combat.\n"
                                    "Apprends la CT11\n"
                                    "Bulles d'O\n"
                                    "à un Pokémon Eau !"
                                )
                            )
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x0399DC,
    "RÉGIS : Sacha ! Moi, j'ai de super Pokémon. Montre-moi les tiens !",
    layout="dialogue_19_19",
)

p(
    0x039A24,
    (
        (
            (
                (
                    (
                        (
                            "RÉGIS : Léo m'a\n"
                            "montré ses Pokémon\n"
                            "rares. Ce célèbre\n"
                            "collectionneur a\n"
                            "enrichi mon Pokédex\n"
                            "et créé le stockage\n"
                            "PC. Tu l'utilises ?\n"
                            "Remercie-le !"
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

# ============================================================
# 16. NUGGET BRIDGE / ROUTES 24–25
# ============================================================

p(
    0x039AC6,
    "Bats 5 Dresseurs !\nUn prix t'attend.\nTu peux gagner ?",
    layout="dialogue_19_19",
)
p(
    0x039AF5,
    (
        (
            "Pas mal ! Tu peux tous nous battre ?"
        )
    ),
    layout="dialogue_19_19",
)
p(
    0x039B19,
    "Je suis deuxième !\nLe vrai combat\ncommence !",
    layout="dialogue_19_19",
)
p(0x039B2C, (
                "Quatrième ! Tu veux te faire remarquer ?"
            ), layout="dialogue_19_19")
p(0x039B45, (
                (
                    (
                        (
                            (
                                "Troisième ! Tu vas\n"
                                "en baver !"
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x039B59,
    "Je suis cinquième\net dernier !\nEn garde !",
    layout="dialogue_19_19",
)
p(
    0x039B6A,
    "Bravo ! Le cadeau\npromis est à toi !",
    layout="dialogue_19_19",
)
p(
    0x039B86,
    "Pierre Lune reçue !",
    layout="dialogue_19_19",
)

p(
    0x039B95,
    (
        "La Team Rocket utilise les Pokémon pour étendre son territoire. Rejoins-nous !"
    ),
    layout="dialogue_19_19",
)
p(0x039BD4, (
                (
                    "Quel gâchis !\n"
                    "Tu aurais brillé\n"
                    "chez la Team Rocket"
                )
            ), layout="dialogue_19_19")
p(
    0x039BE8,
    "Je t'ai vu combattre depuis les hautes herbes.",
    layout="dialogue_19_19",
)
p(
    0x039C07,
    "T'es coriace...",
    layout="dialogue_19_19",
)

# ============================================================
# 17. CHARMANDER / ROUTE 24
# ============================================================

p(
    0x039C17,
    "Je l'élève mal.\nJe vais relâcher\nce Salamèche...\nSi tu t'en occupes,\nil est à toi.",
    layout="dialogue_19_19",
)
p(
    0x039C62,
    "Alors, je vais\nle relâcher...",
    layout="dialogue_19_19",
)
p(0x039C7D, "C'est vrai ? Merci beaucoup !", layout="dialogue_19_19")
p(0x039D74, "Salamèche reçu !", layout="dialogue_19_19")

# ============================================================
# 18. MISCELLANEOUS ROUTES
# ============================================================

p(0x039C8F, (
                (
                    "Encore en forme après avoir franchi le Mont Sélénite ?"
                )
            ), layout="dialogue_19_19")
p(0x039CB1, "Quelle force !", layout="dialogue_19_19")
p(
    0x039CC0,
    "Ici, les Dresseurs\ns'entraînent !",
    layout="dialogue_19_19",
)
p(
    0x039CE0,
    "Pas mal !",
    layout="dialogue_19_19",
)
p(
    0x039CF2,
    "Tu vas chez Léo ? Affronte-moi d'abord !",
    layout="dialogue_19_19",
)
p(0x039D18, (
                (
                    "La Minijupe, c'est moi !"
                )
            ), layout="dialogue_19_19")
p(
    0x039D31,
    "J'ai perdu...",
    layout="dialogue_19_19",
)
p(
    0x039D4E,
    "T'es coriace !",
    layout="dialogue_19_19",
)
p(0x039D84, (
                (
                    "Au bal de l'Océane\n"
                    "avec mon père !\n"
                    "Jaloux ?"
                )
            ), layout="dialogue_19_19")
p(0x039DA8, (
                (
                    (
                        (
                            "L'Océane est pleine de Dresseurs redoutables !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x039DC5, (
                (
                    (
                        'Vive la minijupe !'
                    )
                )
            ), layout="dialogue_19_19")
p(0x039DE5, 'Tu veux passer ? Alors bats-moi !', layout="dialogue_19_19")
p(0x039DF9, "Je suis un Scout !", layout="dialogue_19_19")
p(0x039E0D, "Ha ha ha...", layout="dialogue_19_19")
p(
    0x039E21,
    "Je pressentais\nqu'on se battrait.",
    layout="dialogue_19_19",
)
p(
    0x039E3F,
    "Je pressentais\nque je perdrais...",
    layout="dialogue_19_19",
)
p(0x039E53, (
                (
                    "Mes amies ont\n"
                    "de jolis Pokémon...\n"
                    "C'est pas juste !"
                )
            ), layout="dialogue_19_19")
p(
    0x039E79,
    "Du Mont Sélénite ?\nMoi, je veux\nun Mélofée...",
    layout="dialogue_19_19",
)

# ============================================================
# 19. BILL
# ============================================================

p(
    0x039E91,
    "LÉO : Salut !\nMoi, Léo,\nle Pokémaniac !\nTu doutes ?\nUne expérience\nratée m'a fusionné\navec un Pokémon.\nAide-moi.\nJe prends place\nau Téléporteur.\nSur ce PC, lance\nla séparation !",
    layout="dialogue_19_19",
)

p(
    0x039F3F,
    "LÉO : Merci !\nTu viens voir\nma collection ?\nTiens, prends ça !",
    layout="dialogue_19_19",
)

p(0x039F7C, "Passe Bateau obtenu !", layout="dialogue_19_19")

p(
    0x039F8C,
    "LÉO : L'Océane est\nà Carmin, pleine\nde Dresseurs.\nJ'ai une invitation\nmais je hais\nles fêtes.\nVas-y à ma place !",
    layout="dialogue_19_19",
)

p(0x039FF5, (
                (
                    "LÉO : Ma collection ! 150 espèces sont connues, peut-être plus. J'attends ici un Pokémon légendaire..."
                )
            ), layout="dialogue_19_19")

p(0x039FFF, (
                (
                    "Hé ! Défense d'entrer ! Moi, louche ? Je ne fais que passer."
                )
            ), layout="dialogue_19_19")

# ============================================================
# 20. S.S. ANNE / VERMILION CITY
# ============================================================

p(0x03A03C, "Pitié ! Je ne recommencerai plus ! Je file...", layout="dialogue_19_19")
p(0x03A058, (
                (
                    "Je monte la garde.\n"
                    "Mais j'ai soif !\n"
                    "Passage interdit !"
                )
            ), layout="dialogue_19_19")
p(0x03A088, "Ta tête m'agace !", layout="dialogue_19_19")
p(0x03A0AD, (
                "Tu me plais déjà davantage..."
            ), layout="dialogue_19_19")
p(
    0x03A0BE,
    "Tu veux me tester ?",
    layout="dialogue_19_19",
)
p(0x03A0D2, (
                (
                    "Cette fois, tu m'as\n"
                    "donné une leçon !"
                )
            ), layout="dialogue_19_19")
p(0x03A0E5, "Je suis mignonne, non ?", layout="dialogue_19_19")
p(0x03A0F7, "Je t'aime bien !", layout="dialogue_19_19")
p(0x03A109, (
                (
                    "J'ai capturé\n"
                    "un super Pokémon.\n"
                    "Viens te battre !"
                )
            ), layout="dialogue_19_19")
p(0x03A127, (
                (
                    (
                        "Je dois encore\n"
                        "m'entraîner..."
                    )
                )
            ),
  layout="dialogue_19_19")
p(0x03A14B, (
                (
                    "Tu regardes où ?"
                )
            ), layout="dialogue_19_19")
p(0x03A169, (
                (
                    (
                        "C'était un simple\nmalentendu."
                    )
                )
            ), layout="dialogue_19_19")
p(0x03A17D, (
                "Je suis de mauvais\n"
                "poil !"
            ), layout="dialogue_19_19")
p(0x03A195, (
                (
                    (
                        (
                            "Ça m'énerve\n"
                            "encore plus..."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03A1A7, (
                (
                    (
                        (
                            "L'Océane accoste\n"
                            "à Carmin sur Mer\n"
                            "une fois par an."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03A1C4,
    "MATELOT : Bienvenue sur l'Océane ! Votre passe ?",
    layout="dialogue_19_19",
)
p(
    0x03A1E6,
    "Merci !\nBienvenue à bord !",
    layout="dialogue_19_19",
)
p(0x03A1FA, (
                "Je viens de Hoenn."
            ), layout="dialogue_19_19")
p(0x03A216, (
                "Va donc à Hoenn\n"
                "un de ces jours !"
            ), layout="dialogue_19_19")
p(0x03A235, (
                (
                    "Les garçons d'ici sont tous timides."
                )
            ), layout="dialogue_19_19")
p(0x03A252, (
                "Les gamins comme\n"
                "toi m'énervent !"
            ), layout="dialogue_19_19")
p(0x03A26B, (
                (
                    "Ne sous-estime pas mes Pokémon !"
                )
            ), layout="dialogue_19_19")
p(0x03A283, (
                "Je dois encore\n"
                "m'entraîner..."
            ), layout="dialogue_19_19")
p(0x03A296, "On se sent vraiment bien à Hoenn.", layout="dialogue_19_19")
p(0x03A2B7, (
                (
                    (
                        (
                            'Légendes de Johto :\ntu connais ?'
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03A2D1, (
                (
                    "Quel beau temps !"
                )
            ), layout="dialogue_19_19")
p(0x03A2EB, "Je me suis bien amusé.", layout="dialogue_19_19")
p(0x03A2F8, (
                (
                    "Admire ma prise !"
                )
            ), layout="dialogue_19_19")
p(
    0x03A315,
    "Zut...",
    layout="dialogue_19_19",
)
p(
    0x03A324,
    "J'adore l'air marin.",
    layout="dialogue_19_19",
)
p(0x03A342, (
                (
                    (
                        "Je t'aime presque\nautant..."
                    )
                )
            ), layout="dialogue_19_19")
p(0x03A365, (
                (
                    'Salut !'
                )
            ), layout="dialogue_19_19")
p(0x03A388, "Sacré Dresseur !", layout="dialogue_19_19")
p(0x03A394, 'Je bosse dur tous les jours.', layout="dialogue_19_19")
p(0x03A3B4, "C'est une blague ?!", layout="dialogue_19_19")
p(0x03A3C8, (
                (
                    "T'es qui, toi ?"
                )
            ), layout="dialogue_19_19")
p(0x03A3EE, (
                (
                    (
                        (
                            (
                                'Moi, qui suis-je ?'
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03A406, "Bonne traversée !", layout="dialogue_19_19")
p(0x03A41F, (
                (
                    (
                        'À quand le dîner ?'
                    )
                )
            ), layout="dialogue_19_19")
p(0x03A433, "Je suis au régime !", layout="dialogue_19_19")
p(0x03A44D, (
                "Et me voilà encore\n"
                "gros !"
            ), layout="dialogue_19_19")

p(
    0x03A460,
    (
        (
            (
                (
                    "RÉGIS : Sacha !\n"
                    "Toi aussi, invité ?\n"
                    "Mon Pokédex compte\n"
                    "plus de 40 espèces.\n"
                    "Voyons tes progrès."
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03A4B8,
    (
        (
            (
                (
                    "RÉGIS : À bord,\n"
                    "le maître de Coupe\n"
                    "a le mal de mer !\n"
                    "Va le voir.\n"
                    "À plus !"
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03A504,
    "Beurk...\nJ'ai le mal\nde mer !",
    layout="dialogue_19_19",
)
p(
    0x03A525,
    "L'Océane est partie.",
    layout="dialogue_19_19",
)
p(
    0x03A538,
    "Même tes Pokémon\nne suffisent pas :\nt'es trop jeune !",
    layout="dialogue_19_19",
)
p(0x03A555, (
                (
                    "AGENT JENNY :\nCe Carapuce faisait\nn'importe quoi.\nJe l'ai capturé !"
                )
            ), layout="dialogue_19_19")

p(
    0x03A57C,
    "Hé, Champion ! Major Bob, le Ricain Survolté, a la meilleure équipe Électrik d'Amérique ! Évite Eau et Vol !",
    layout="dialogue_19_19",
)

p(
    0x03A5DC,
    (
        "Les passagers\n"
        "de l'Océane\n"
        "sont tous riches !\n"
        "Ne traîne pas ici,\n"
        "gamin !"
    ),
    layout="dialogue_19_19",
)
p(0x03A60F, "Évoli reçu !", layout="dialogue_19_19")
p(
    0x03A61A,
    "Pas mal !",
    layout="dialogue_19_19",
)

# ============================================================
# 21. VERMILION GYM (Lt. Surge)
# ============================================================

p(
    0x03A62F,
    "CS01 obtenue !",
    layout="dialogue_19_19",
)

p(
    0x03A6AC,
    (
        (
            "Le Major Bob est\n"
            "militaire. Tu veux\n"
            "t'engager ?"
        )
    ),
    layout="dialogue_19_19",
)
p(0x03A6CC, (
                (
                    (
                        (
                            "Tu crois pouvoir\n"
                            "passer ?"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x038891, "Tu peux entrer.", layout="dialogue_19_19")
p(0x0388BD, "PROF. CHEN : Pikachu t'apprécie. Tu feras un bon Dresseur !", layout="dialogue_19_19")
p(0x0388DE, (
                (
                    (
                        "PROF. CHEN : Quoi ?\n"
                        "C'est pour moi ?"
                    )
                )
            ), layout="dialogue_19_19")
p(0x038916, (
                (
                    (
                        (
                            (
                                (
                                    "Sacha remet\n"
                                    "le Colis Chen\n"
                                    "au Prof. Chen !"
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")

p(
    0x03A6E9,
    (
        (
            (
                (
                    (
                        (
                            (
                                "MAJOR BOB :\n"
                                "Tu oses me défier\n"
                                "si faible ?\n"
                                "Quel cran ! Prends\n"
                                "donc ta leçon !"
                            )
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03A745,
    (
        "CT24 reçue !"
    ),
    layout="dialogue_19_19",
)

# ============================================================
# 22. SQUIRTLE GIFT
# ============================================================

p(
    0x03A821,
    (
        (
            "AGENT JENNY : Le Badge Foudre ? Tu es fort ! Veux-tu ce Carapuce farceur ?"
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03A88A,
    "Qui veut Carapuce ?",
    layout="dialogue_19_19",
)
p(
    0x03A8A5,
    "Prends soin de lui,\ns'il te plaît !",
    layout="dialogue_19_19",
)
p(0x038122, (
                "Carapuce reçu !"
            ), layout="dialogue_19_19")

# ============================================================
# 23. CELADON GAME CORNER / GAMBLERS
# ============================================================

p(0x03A91B, (
                (
                    "Mes Pokémon sont invincibles !"
                )
            ), layout="dialogue_19_19")
p(0x03A92F, "Enfin... seulement chez moi.", layout="dialogue_19_19")
p(0x03A94A, "J'ai sommeil...", layout="dialogue_19_19")
p(0x03A957, "Pourquoi m'empêcher de dormir ?", layout="dialogue_19_19")
p(
    0x03A971,
    (
        (
            "On a quelque chose sur le visage ?"
        )
    ),
    layout="dialogue_19_19",
)
p(0x03A98F, (
                "Oui, toi ! Arrête de nous dévisager !"
            ), layout="dialogue_19_19")
p(0x03A9A3, (
                (
                    "Traite tes Pokémon avec amour."
                )
            ), layout="dialogue_19_19")
p(0x03A9BE, "Pas mal, petit !", layout="dialogue_19_19")
p(
    0x03A9D1,
    "RÉGIS : À bord,\nle maître de Coupe\nest un vieux.\nIl a le mal\nde mer !\nVa voir. À plus !",
    layout="dialogue_19_19",
)
p(0x03A9EA, "Tu m'as battu.", layout="dialogue_19_19")
p(0x03A9F7, (
                (
                    (
                        "SACHA :\n"
                        "Je vais vous masser\n"
                        "le dos !"
                    )
                )
            ),
  layout="dialogue_19_19")
p(0x03A9FC, (
                "Hé ! C'est quoi,\n"
                "ces manières ?"
            ), layout="dialogue_19_19")
p(0x03AA16, "Bon, je laisse tomber.", layout="dialogue_19_19")
p(0x03AA38, "Comment peux-tu faire ça ?", layout="dialogue_19_19")
p(0x03AA55, "Je n'ai rien dit.", layout="dialogue_19_19")
p(0x03AA6E, "Tu ne passeras pas.", layout="dialogue_19_19")
p(0x03AA91, "Je n'ai rien vu. Allez, file !", layout="dialogue_19_19")
p(0x03AAA1, "Réglons ça aujourd'hui !", layout="dialogue_19_19")
p(0x03AABA, "Tu as eu\nde la chance...", layout="dialogue_19_19")

# ============================================================
# 24. ROUTES / SNORLAX / OAK AIDE
# ============================================================

p(0x03AACC, "Tu es fichu !", layout="dialogue_19_19")
p(0x03AB01, (
                (
                    (
                        (
                            "J'ai mal au ventre.\n"
                            "Pas de dispute\n"
                            "aujourd'hui."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03AB27,
    (
        "D'après la rumeur,\n"
        "les Taupiqueur ont\n"
        "creusé ce tunnel\n"
        "jusqu'à Jadielle !"
    ),
    layout="dialogue_19_19",
)

p(
    0x03AB5C,
    (
        "Certains Pokémon apprennent Flash avec la CS05. Utile dans les grottes !"
    ),
    layout="dialogue_19_19",
)
p(0x03ABA2, "CS05 obtenue !", layout="dialogue_19_19")

# ============================================================
# 25. ROCK TUNNEL / MISCELLANEOUS TRAINERS
# ============================================================

p(0x03ABAC, "Dis donc, tu es plutôt mignon !", layout="dialogue_19_19")
# Post-battle line called through a second pointer to the same record.
p(0x03ABCB, "Tu es fort, j'aime ça !", layout="dialogue_19_19")
p(0x03ABDC, (
                (
                    (
                        (
                            (
                                "On négocie ?\n"
                                "Ton Pikachu,\n"
                                "donne-le-moi !"
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03AC11, "J'avais tort.", layout="dialogue_19_19")
p(0x03AC24, (
                "Te revoir ici ? Quelle surprise !"
            ), layout="dialogue_19_19")
p(0x03AC37, "Encore plus fort !", layout="dialogue_19_19")
p(0x03AC43, (
                (
                    (
                        (
                            (
                                (
                                    "Attention, ou ça va\n"
                                    "mal finir !"
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03AC57, "Alors, comment vas-tu ? Ha ha...", layout="dialogue_19_19")
p(0x03AC70, (
                (
                    "Intéressant..."
                )
            ), layout="dialogue_19_19")
p(0x03AC84, (
                (
                    "Cette fois, je suis\n"
                    "fichu..."
                )
            ), layout="dialogue_19_19")
p(
    0x03AC97,
    (
        "Un conseil : fuis !"
    ),
    layout="dialogue_19_19",
)
p(0x03ACB9, "Pas mal...", layout="dialogue_19_19")
p(0x03ACCD, (
                (
                    (
                        "Tous tes efforts\n"
                        "sont vains.\n"
                        "Je suis trop fort !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x03ACF4, (
                "Mais... C'est pas\n"
                "possible !"
            ), layout="dialogue_19_19")
p(0x03AD02, "Encore toi !", layout="dialogue_19_19")
p(0x03AD29, "Laisse-moi te voir.", layout="dialogue_19_19")
p(0x03AD43, "Tu aurais pu y aller mollo !", layout="dialogue_19_19")
p(0x03AD5C, (
                (
                    (
                        (
                            (
                                (
                                    "Tu as osé venir\n"
                                    "dans ce noir !"
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03AD7A, (
                (
                    "Quel courage !"
                )
            ), layout="dialogue_19_19")
p(0x03AD8B, "J'ai perdu quelque chose.", layout="dialogue_19_19")
p(0x03AD9E, "Je dois le trouver.", layout="dialogue_19_19")
p(0x03ADC8, "Tu n'es pas n'importe qui.", layout="dialogue_19_19")
p(0x03ADD0, "J'ai vraiment très peur...", layout="dialogue_19_19")
p(0x03ADF0, (
                (
                    "Tu me protèges, d'accord ?"
                )
            ), layout="dialogue_19_19")
p(0x03ADFF, "Que fais-tu ici ?", layout="dialogue_19_19")
p(0x03AE24, "Je passe mes journées à travailler ici. Quel ennui !", layout="dialogue_19_19")
p(0x03AE43, "LÉO : Merci...", layout="dialogue_19_19")
p(0x03ADB0, (
                (
                    "Moi, je n'ai pas peur du noir."
                )
            ), layout="dialogue_19_19")

# ============================================================
# 26. LAVENDER TOWN / POKEMON TOWER
# ============================================================

p(0x03B058, (
                "Demain, ça ira\n"
                "mieux... pas vrai ?"
            ), layout="dialogue_19_19")
p(0x03B068, "Pas touche !", layout="dialogue_19_19")
p(0x03B08A, (
                "Je t'avais prévenu. Pas touche !"
            ), layout="dialogue_19_19")
p(0x03B09D, "La montagne, ça endurcit !", layout="dialogue_19_19")
p(0x03B0B0, (
                (
                    "Je m'en doutais !"
                )
            ), layout="dialogue_19_19")
p(0x03B0BB, "Je cherche un petit ami.", layout="dialogue_19_19")
p(0x03B0CB, "Pas mon genre !", layout="dialogue_19_19")
p(0x03B0DF, (
                (
                    "Tu veux savoir ?"
                )
            ), layout="dialogue_19_19")
p(0x03B0FB, (
                (
                    "Les Pokémon peuvent évoluer en gagnant des niveaux !"
                )
            ), layout="dialogue_19_19")
p(0x03B117, "Les Pokémon Roche\nsont imbattables !", layout="dialogue_19_19")
p(0x03B132, "Je me trompais ?", layout="dialogue_19_19")
p(0x03B144, "Je viens de rompre avec ma copine.", layout="dialogue_19_19")
p(0x03B160, "Je suis de mauvaise humeur.", layout="dialogue_19_19")
p(0x03B174, "Tu m'as bousculé !", layout="dialogue_19_19")

# Bulbasaur gift
p(
    0x03B188,
    "Bulbizarre va bien.\nIl lui faut un bon\nDresseur.\nTu le veux ?",
    layout="dialogue_19_19",
)
p(0x03B1E7, (
                (
                    (
                        "Ah bon ? Dommage..."
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03B1FF,
    "Alors, prends soin\nde Bulbizarre !",
    layout="dialogue_19_19",
)
p(0x03B20E, "Bulbizarre reçu !", layout="dialogue_19_19")

p(0x03B21F, "Désolé, je me suis trompé !", layout="dialogue_19_19")
p(0x03B233, "Ne te balade pas partout.", layout="dialogue_19_19")
p(0x03B244, (
                (
                    (
                        "Si ça s'écroule,\n"
                        "on est fichus !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x03B257, "Bonjour !", layout="dialogue_19_19")
p(0x03B267, (
                (
                    (
                        "Ravi d'avoir fait ta connaissance."
                    )
                )
            ), layout="dialogue_19_19")
p(0x03B283, (
                (
                    "Rien à négocier !"
                )
            ), layout="dialogue_19_19")
p(0x03B29B, (
                (
                    "Bon, vas-y, parle."
                )
            ), layout="dialogue_19_19")
p(0x03B2AE, (
                (
                    "J'adore distribuer des coups !"
                )
            ), layout="dialogue_19_19")
p(0x03B2C2, (
                (
                    "Je ne recommencerai plus..."
                )
            ), layout="dialogue_19_19")
p(0x03B2E4, (
                (
                    "Impressionnant..."
                )
            ), layout="dialogue_19_19")
p(0x03B2F8, (
                (
                    (
                        (
                            "Ma Défense est imbattable !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03B310, (
                (
                    (
                        (
                            "Tu as percé\n"
                            "ma Défense ?!"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03B329,
    "C'est bizarre...\nOù est donc passé\nM. Fuji ?",
    layout="dialogue_19_19",
)

p(0x03B34F,
  (
      (
          (
              "M. Fuji recueille\n"
              "ici les Pokémon\n"
              "abandonnés."
          )
      )
  ),
  layout="dialogue_19_19")

p(
    0x03B390,
    (
        (
            (
                (
                    (
                        (
                            "Pour de l'argent,\n"
                            "la Team Rocket\n"
                            "est prête à tout."
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)
p(0x03B3C2, (
                (
                    "Cette Tour apaise l'âme des Pokémon disparus."
                )
            ), layout="dialogue_19_19")
p(0x03B418, "ÉLECTHOR : ...", layout="dialogue_19_19")
p(0x03B427, (
                "EXORCISTE :\n"
                "Une âme erre\n"
                "plus haut..."
            ), layout="dialogue_19_19")
p(0x03B44A,
  (
      "Mon Mélofée est\n"
      "mort... Je pleure\n"
      "encore..."
  ),
  layout="dialogue_19_19")

p(
    0x03B47A,
    (
        (
            (
                (
                    (
                        (
                            "Tu viens prier ?\n"
                            "Tu aimes beaucoup\n"
                            "les Pokémon."
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03B4B9,
    "RÉGIS : Sacha ?\nIls sont en vie !\nJe peux les mettre\nK.O. quand même !",
    layout="dialogue_19_19",
)

p(0x03B516,
  (
      (
          (
              (
                  "RÉGIS : Doucement !\n"
                  "Je t'avais ménagé.\n"
                  "Ton Pokédex ? J'ai\n"
                  "trouvé Osselait,\n"
                  "mais pas Ossatueur.\n"
                  "Je suis pressé.\n"
                  "Salut !"
              )
          )
      )
  ),
  layout="dialogue_19_19")

p(0x03B592, (
                "Un Scope Sylphe\n"
                "pourrait démasquer\n"
                "les Spectres..."
            ), layout="dialogue_19_19")
p(0x03B5C8, (
                "Là-haut,\n"
                "les Pokémon\n"
                "sont terrifiés..."
            ), layout="dialogue_19_19")
p(0x03B5E8, (
                "Tu sais combien le poison est terrifiant ?"
            ), layout="dialogue_19_19")
p(0x03B604,
  (
      "Le poison réduit\n"
      "peu à peu tes PV."
  ),
  layout="dialogue_19_19")
p(0x03B621, "Encore toi ?", layout="dialogue_19_19")
p(0x03B631, "Tu me colles !", layout="dialogue_19_19")
p(0x03B64D, (
                "J'adore Miaouss...\n"
                "Miaou !"
            ), layout="dialogue_19_19")
p(0x03B666, "Miaouss porte chance !", layout="dialogue_19_19")
p(0x03B687, "Même un Pokémon ordinaire peut être unique.", layout="dialogue_19_19")
p(
    0x03B6B3,
    "Comme tu es banal,\ntes Pokémon le sont\nforcément aussi !",
    layout="dialogue_19_19",
)
p(0x03B6D9, "Pas de chance aujourd'hui.", layout="dialogue_19_19")
p(0x03B6F4, "Quelle malchance...", layout="dialogue_19_19")
p(0x03B716, "Je suis encore jeune !", layout="dialogue_19_19")
p(0x03B739, (
                (
                    (
                        (
                            "Tu vois ? En pleine forme !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03B754, (
                (
                    (
                        (
                            "Je ne supporte plus tous ces Tadmorv !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03B770,
  (
      "Merci d'avoir maté\n"
      "ces Tadmorv !"
  ),
  layout="dialogue_19_19")
p(0x03B77E,
  (
      "Rien de plus beau\n"
      "que les flammes !"
  ),
  layout="dialogue_19_19")
p(0x03B792, "Je me suis un peu trop échauffé...", layout="dialogue_19_19")
p(0x03B7A1, "Regarde\nmon Mélofée !", layout="dialogue_19_19")
p(0x03B7B5, "Tu n'as pas été hypnotisé ?", layout="dialogue_19_19")

# ============================================================
# 27. CELADON GYM (Erika)
# ============================================================

p(0x03B7C8, (
                "Héhé ! Cette Arène\n"
                "est terrible !\n"
                "Y'a plein d'meufs !"
            ), layout="dialogue_19_19")
p(0x03B7E8, (
                "Pfff ! Erika va\n"
                "gagner, c'est sûr !"
            ), layout="dialogue_19_19")
p(0x03B835, "Réservé aux filles.", layout="dialogue_19_19")
p(
    0x03B851,
    "Que des femmes !\nQuel ennui mortel !",
    layout="dialogue_19_19",
)
p(0x03B865, "Quel ennui...", layout="dialogue_19_19")
p(
    0x03B870,
    "Les Pokémon Plante\ns'élèvent bien !",
    layout="dialogue_19_19",
)
p(0x03B892, "Tu es vraiment fort !", layout="dialogue_19_19")
p(0x03B8B9, "Tu m'observes ?", layout="dialogue_19_19")
p(
    0x03B8D8,
    (
        "Tu ne matais pas ? Les voyeurs sont partout !"
    ),
    layout="dialogue_19_19",
)
p(0x03B8F9, "Pas de Pokémon Insecte ou Feu ici !", layout="dialogue_19_19")
p(0x03B919, "C'est ça !", layout="dialogue_19_19")
p(0x03B938, (
                (
                    (
                        (
                            (
                                (
                                    "Bienvenue à l'Arène\n"
                                    "de Céladopole !\n"
                                    "Ne sous-estime pas\n"
                                    "les filles !"
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03B95F, "Pas mal !", layout="dialogue_19_19")
p(0x03B968, (
                (
                    "Qu'aimes-tu faire ?"
                )
            ), layout="dialogue_19_19")
p(
    0x03B97A,
    "J'ai un rendez-vous arrangé la semaine prochaine...",
    layout="dialogue_19_19",
)

p(
    0x03B993,
    (
        (
            (
                (
                    (
                        (
                            "ERIKA : Quel beau\n"
                            "temps ! Bienvenue\n"
                            "dans mon Arène.\n"
                            "J'aime les fleurs.\n"
                            "Tu veux combattre ?\n"
                            "Je ne perdrai pas !"
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03B9F1,
    "ERIKA : Bravo ! Voici le Badge Prisme. Il permet d'utiliser Force !",
    layout="dialogue_19_19",
)

# ============================================================
# 28. CYCLING ROAD / EEVEE
# ============================================================

p(
    0x03BA58,
    (
        "Je viens de Carmin sur Mer."
    ),
    layout="dialogue_19_19",
)
p(0x03BA87, (
                "La Poké Flûte\n"
                "émet un son spécial\n"
                "inaudible à l'homme\n"
                "qui réveille\n"
                "un Pokémon endormi."
            ), layout="dialogue_19_19")
p(0x03BAB6, (
                (
                    "BEIBEI : Je sais tout, jeux vidéo compris ! Cet Évoli est pour toi !"
                )
            ), layout="dialogue_19_19")

# ============================================================
# 29. TEAM ROCKET HIDEOUT / SILPH CO.
# ============================================================

p(
    0x03BAF9,
    "Oh ? Un bouton secret derrière l'affiche ! Essayons !",
    layout="dialogue_19_19",
)
p(0x03BB1B, (
                "T'es qui ? Comment\n"
                "t'es entré ici ?"
            ), layout="dialogue_19_19")
p(0x03BB39, (
                (
                    (
                        (
                            "Tu sous-estimes\n"
                            "la Team Rocket ?!"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03BB57,
    "TEAM ROCKET : Qui ose s'infiltrer ici ?",
    layout="dialogue_19_19",
)
p(0x03BB86,
  (
      "Le chef dit qu'un\n"
      "Scope Sylphe révèle\n"
      "les fantômes."
  ),
  layout="dialogue_19_19")
p(0x03BBB2, "Tu te crois tout permis ?!", layout="dialogue_19_19")
p(0x03BBBF, (
                (
                    "Tu viens faire quoi ici ?"
                )
            ), layout="dialogue_19_19")
p(0x03BBCE, (
                (
                    "D'accord. Tu peux y aller."
                )
            ), layout="dialogue_19_19")
p(
    0x03BBFA,
    "TEAM ROCKET : Intrus repéré !",
    layout="dialogue_19_19",
)
p(
    0x03BC0A,
    "TEAM ROCKET :\nLe Scope Sylphe ?\nJe ne sais rien !",
    layout="dialogue_19_19",
)
p(0x03BC31, (
                (
                    (
                        (
                            "Défier la Team Rocket est inutile !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03BC4C, (
                (
                    "Le Boss a dérobé ce Scope à Nanjing Tech !"
                )
            ), layout="dialogue_19_19")
p(0x03BC5A, "Tu tombes à pic !", layout="dialogue_19_19")
p(0x03BC7A, (
                (
                    (
                        (
                            "Tu as du cran ?\n"
                            "Va donc trouver\n"
                            "notre Boss !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03BC9C, (
                (
                    "Je ne sais rien, moi !"
                )
            ), layout="dialogue_19_19")

p(0x03BCA7, "100e client ! Eau Fraîche offerte !", layout="dialogue_19_19")
p(0x03BCE8, "Eau Fraîche reçue !", layout="dialogue_19_19")
p(
    0x03BCF6,
    "XIAOHONG : C'est moi, la graphiste qui t'a dessiné !",
    layout="dialogue_19_19",
)
p(0x03BD1A, (
                "KAMEIYU : Le scénario, c'est moi ! Pikachu est mignon, non ?"
            ), layout="dialogue_19_19")
p(0x03BD3F, "WEI CUNFU : Je suis le programmeur. Enchanté !", layout="dialogue_19_19")
p(0x03BD65, (
                (
                    "BOSS : La tâche est\n"
                    "rude : les attraper\n"
                    "tous ! Courage !\n"
                    "Une fois ta quête\n"
                    "achevée, préviens\n"
                    "Kameiyu."
                )
            ), layout="dialogue_19_19")
p(0x03BDB1, (
                (
                    (
                        (
                            "Qu'ai-je fait ?\n"
                            "Pardon... J'étais\n"
                            "possédée !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03BDC5, "Je ne sais rien !", layout="dialogue_19_19")

p(0x03BDE2, (
                (
                    (
                        (
                            (
                                (
                                    "GIOVANNI : Ha ha !\n"
                                    "Bien joué.\n"
                                    "Je dirige ce QG\n"
                                    "de trafic Pokémon.\n"
                                    "Tu vas le payer !"
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03BE0E,
    "XIAO LI : Tu m'as trouvé... Garde ça secret. Tiens, prends ça !",
    layout="dialogue_19_19",
)
p(0x03BE50, "CS02 : Vol reçue !", layout="dialogue_19_19")

# ============================================================
# 30. JESSIE & JAMES (Silph Co.)
# ============================================================

p(
    0x03BE5E,
    (
        (
            (
                (
                    "JAMES : Cette fois, tu vas prendre cher !"
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03BEE1,
    "JAMES :\nT'as pas honte ?",
    layout="dialogue_19_19",
)

# ============================================================
# 31. GIOVANNI (Silph Co.)
# ============================================================

p(
    0x03BF2D,
    (
        (
            (
                (
                    "GIOVANNI :\n"
                    "Im... impossible !\n"
                    "Tu tiens vraiment\n"
                    "à tes Pokémon ?\n"
                    "Ça me dépasse...\n"
                    "J'ai fort à faire.\n"
                    "Je pars !"
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x03BFD6, "Scope Sylphe reçu !", layout="dialogue_19_19")

# ============================================================
# 32. POKEMON TOWER (Ghosts/Fuji)
# ============================================================

p(
    0x03BFF8,
    "Hein ? Que m'est-il arrivé ?",
    layout="dialogue_19_19",
)
p(0x03C008, (
                (
                    "Ton âme... Donne-la-moi !"
                )
            ), layout="dialogue_19_19")
p(0x03C01C, "Je suis épuisée...", layout="dialogue_19_19")
p(0x03C035, "Hein ? Qu'est-ce que c'est...", layout="dialogue_19_19")
p(0x03C059, "Hein ? Que m'est-il arrivé ?", layout="dialogue_19_19")
p(
    0x03C096,
    (
        "Tout tourne...\n"
        "Suis-je anémique ?"
    ),
    layout="dialogue_19_19",
)
p(0x03C0C5, "Un zombie...", layout="dialogue_19_19")
p(0x03C15A, "Ça y est, j'ai repris mes esprits.", layout="dialogue_19_19")
p(0x03C16A, "Kang'er... Kang'er...", layout="dialogue_19_19")
p(0x03C17D, "Je tremble...", layout="dialogue_19_19")
p(0x03C197, "Quelque chose est sorti de moi...", layout="dialogue_19_19")
p(
    0x03C1B2,
    "Hi hi...\nQue m'arrive-t-il ?",
    layout="dialogue_19_19",
)
p(
    0x03C1EA,
    "Le Scope Sylphe\na révélé la vraie\nnature du Spectre !",
    layout="dialogue_19_19",
)

p(0x03C21F,
  (
      (
          "SACHA : Le fantôme était en fait la douce mère d'Osselait..."
      )
  ),
  layout="dialogue_19_19")

p(
    0x03C28D,
    (
        (
            (
                (
                    (
                        "JESSIE : Pas bouger ! Le vieux s'est plaint, alors on l'a enfermé !"
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03C33F,
    "JAMES :\nTu vas voir !",
    layout="dialogue_19_19",
)

p(
    0x03C370,
    "M. FUJI :\nTu viens m'aider ?\nMerci.\nJe suis venu\napaiser l'âme\nde la mère\nd'Osselait.\nElle est en paix.\nRentrons.",
    layout="dialogue_19_19",
)

p(0x03C424, (
                (
                    (
                        (
                            "M. FUJI :\n"
                            "Aime tes Pokémon,\n"
                            "sinon ton Pokédex\n"
                            "restera incomplet.\n"
                            "Tiens, prends ceci."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03C464,
    "M. FUJI :\nLa Poké Flûte\nréveille un Pokémon\nqui dort.\nEssaie-la !",
    layout="dialogue_19_19",
)

# ============================================================
# 33. SAFFRON GUARD / SILPH CO. (continued)
# ============================================================

p(
    0x03C493,
    "GARDE : J'ai soif.\nCette Eau Fraîche\nest pour moi ?\nMerci ! Safrania\nt'est ouverte !",
    layout="dialogue_19_19",
)

p(0x03C4FE, (
                (
                    (
                        (
                            "Hé, gamin !\n"
                            "Ne traîne pas ici !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03C51C,
    "TEAM ROCKET :\nLe Boss convoite\nla Sylphe SARL !",
    layout="dialogue_19_19",
)
p(0x03C541, "Je suis l'un des quatre frères Rocket !", layout="dialogue_19_19")
p(0x03C54E, (
                (
                    "Contrôler Sylphe SARL, c'est vendre les Pokémon au prix fort !"
                )
            ), layout="dialogue_19_19")
p(0x03C55B, "Quel casse-pieds !", layout="dialogue_19_19")
p(0x03C577, "J'ai eu tort...", layout="dialogue_19_19")
p(0x03C58E, "Un individu suspect !", layout="dialogue_19_19")
p(
    0x03C5A6,
    "TEAM ROCKET : T'es qui, toi ?",
    layout="dialogue_19_19",
)
p(
    0x03C5CA,
    "T'as réussi à venir jusqu'ici...",
    layout="dialogue_19_19",
)
p(0x03C5E5, (
                (
                    "Bravo ! Le bureau\n"
                    "du Président reste\n"
                    "inaccessible."
                )
            ), layout="dialogue_19_19")
p(0x03C5F0, "Toi, je t'ai jamais vu ici !", layout="dialogue_19_19")

p(
    0x03C60E,
    (
        (
            (
                "Tu me crois fini ?\n"
                "Je t'empêcherai\n"
                "de gagner !"
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x03C650, (
                (
                    "La Team Rocket contrôle la Sylphe SARL !"
                )
            ), layout="dialogue_19_19")
p(0x03C662, "Vive\nla Team Rocket !", layout="dialogue_19_19")
p(0x03C66F, (
                (
                    "Encore toi ?\n"
                    "Tu viens semer\n"
                    "le trouble ?"
                )
            ), layout="dialogue_19_19")
p(0x03C68D, (
                (
                    (
                        (
                            "Tu peux regarder..."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03C6AC, "Tu veux quoi ?", layout="dialogue_19_19")
p(0x03C6CF, "Sale morveux !", layout="dialogue_19_19")
p(0x03C6EB, (
                (
                    "Le Boss est là. Rien à craindre !"
                )
            ), layout="dialogue_19_19")
p(0x03C70E, "Employée de Sylphe SARL. Je suis aussi de la Team Rocket !", layout="dialogue_19_19")
p(
    0x03C722,
    "La Team Rocket contrôle la Sylphe SARL !",
    layout="dialogue_19_19",
)
p(
    0x03C748,
    "Me frappe pas ! Moi aussi, on m'a forcé...",
    layout="dialogue_19_19",
)

# ============================================================
# 34. RIVAL AT SILPH CO.
# ============================================================

p(
    0x03C765,
    "RÉGIS : Sacha ! Je savais que tu viendrais. La Team Rocket t'a ralenti ? Peu importe ! Montre tes progrès !",
    layout="dialogue_19_19",
)

p(
    0x03C7DF,
    "RÉGIS : Je file\nau Conseil des 4 !\nFais de ton mieux.\nÀ plus, Sacha !",
    layout="dialogue_19_19",
)

# ============================================================
# 35. ROCKET GRUNTS (Silph Co., continued)
# ============================================================

p(0x03C861, (
                (
                    "Moi, je compte\n"
                    "parmi les quatre\n"
                    "frères Rocket !"
                )
            ), layout="dialogue_19_19")
p(0x03C886, (
                (
                    (
                        "Tant pis !\n"
                        "Mon cadet vengera\n"
                        "cet affront !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x03C890, "Tu m'crois faible ?", layout="dialogue_19_19")
p(0x03C8A4, "Sous-estime-moi !", layout="dialogue_19_19")
p(0x03C8B1, (
                "On dit qu'un gamin rôde dans le coin !"
            ), layout="dialogue_19_19")
p(0x03C8C9, (
                (
                    (
                        "Ne résiste pas\n"
                        "à la Team Rocket..."
                    )
                )
            ), layout="dialogue_19_19")

p(
    0x03C8E5,
    (
        (
            (
                (
                    (
                        "JAMES : Avorton !\n"
                        "Notre Boss est\n"
                        "en réunion !\n"
                        "Ne le dérange pas !"
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03C958,
    (
        (
            (
                "SACHA :\n"
                "Qui êtes-vous ?"
            )
        )
    ),
    layout="dialogue_19_19",
)

# ============================================================
# 36. GIOVANNI (Silph Co. boss fight)
# ============================================================

p(
    0x03C992,
    "GIOVANNI : Sacha !\nEncore toi...\nLe PDG et moi\nparlons affaires.\nNe t'en mêle pas,\ngamin. Gare à toi !",
    layout="dialogue_19_19",
)

p(
    0x03CA26,
    "GIOVANNI : Zut !\nLa Sylphe m'échappe\nmais la Team Rocket\nest éternelle !\nTous les Pokémon\nsont à nous !\nRetiens ça, Sacha.\nJe reviendrai !",
    layout="dialogue_19_19",
)

p(
    0x03CAB3,
    "SECRÉTAIRE : Merci ! Le PDG et moi te sommes reconnaissants.",
    layout="dialogue_19_19",
)

# ============================================================
# 37. FISHING / WATER ROUTES
# ============================================================

p(0x03CAE7, "Ronflex s'éveille !", layout="dialogue_19_19")
p(0x03CAFB, "Ce coin est réputé pour la pêche.", layout="dialogue_19_19")
p(0x03CB0E, "Tu n'aimes pas pêcher ?", layout="dialogue_19_19")
p(0x03CB20, (
                (
                    (
                        (
                            "Plein de Pokémon vivent dans l'eau !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03CB39, "Les Pokémon Eau sont les plus mignons !", layout="dialogue_19_19")
p(0x03CB4C, "Les Pokémon Eau sont magnifiques !", layout="dialogue_19_19")
p(0x03CB64, "Tu vois pas\nque je pêche ?", layout="dialogue_19_19")
p(0x03CB80, "Laisse tomber...\nTous les poissons\nont fui !", layout="dialogue_19_19")
p(
    0x03CB91,
    "J'ai une belle prise. Tu veux voir ?",
    layout="dialogue_19_19",
)
p(0x03CBBB, (
                (
                    (
                        (
                            "Ici, mes Pokémon\n"
                            "n'ont presque aucun\n"
                            "rival !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03CBD9, "Je me suis fait avoir...", layout="dialogue_19_19")
p(0x03CBF5, (
                (
                    "Je ne demande rien."
                )
            ), layout="dialogue_19_19")
p(0x03CC09, "Je ne suis pas louche !", layout="dialogue_19_19")
p(0x03CC2E, "Dégage !\nJe te connais pas !", layout="dialogue_19_19")
p(0x03CC54, "Pardon, je t'avais mal jugé.", layout="dialogue_19_19")
p(0x03CC68, "La vitesse avant tout !", layout="dialogue_19_19")
p(0x03CC88, (
                (
                    (
                        (
                            "Même battu,\n"
                            "je ne change pas !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03CCA0, "Rien qu'à te voir,\nj'en salive !", layout="dialogue_19_19")
p(0x03CCB8, "J'avais tort...", layout="dialogue_19_19")
p(
    0x03CCCA,
    "Quoi ?\nJe te plais pas ?",
    layout="dialogue_19_19",
)
p(0x03CCE8, "Tu as raison.", layout="dialogue_19_19")
p(0x03CCF5, "Toi, encore !", layout="dialogue_19_19")
p(
    0x03CD0E,
    "C'est le destin !\nOn se revoit !",
    layout="dialogue_19_19",
)
p(0x03CD22, (
                (
                    "Arrête de tourner devant moi !"
                )
            ), layout="dialogue_19_19")
p(0x03CD39, "J'ai exagéré...", layout="dialogue_19_19")
p(0x03CD4C, (
                (
                    "Je suis spécialiste\n"
                    "des Pokémon Vol."
                )
            ), layout="dialogue_19_19")
p(0x03CD6D, "Tes Pokémon\nbattent les miens.", layout="dialogue_19_19")
p(
    0x03CD81,
    "T'as battu l'aîné ?\nJe m'incline pas !",
    layout="dialogue_19_19",
)
p(0x03CD9C, "Plus rien à dire.", layout="dialogue_19_19")
p(0x03CDA6, "Tu aimes la vitesse ? Suis-moi !", layout="dialogue_19_19")
p(
    0x03CDBD,
    "J'aurais pas dû insister.",
    layout="dialogue_19_19",
)
p(
    0x03CDC7,
    "Envole-toi,\nmon Pokémon !",
    layout="dialogue_19_19",
)
p(0x03CDE9, "Tout est fini...", layout="dialogue_19_19")
p(0x03CDFD, "Tu es allé au Parc Safari ?", layout="dialogue_19_19")
p(0x03CE1E, (
                (
                    (
                        "Le type Vol domine\n"
                        "le type Insecte !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x03CE3B, (
                (
                    "Ah, tu avais donc\n"
                    "compris !"
                )
            ), layout="dialogue_19_19")
p(0x03CE4F, "Tu m'as cherché !", layout="dialogue_19_19")
p(0x03CE69, "Ce n'est rien...", layout="dialogue_19_19")
p(0x03CE78, "T'es trop mignon !", layout="dialogue_19_19")

# ============================================================
# 38. MISCELLANEOUS ROUTES (continued)
# ============================================================

p(
    0x03D088,
    "ORNITHOLOGUE :\nDes Pokémon rares\nvivent ici...",
    layout="dialogue_19_19",
)
p(0x03D0A7, "Ne pars pas ! Reste discuter avec moi !", layout="dialogue_19_19")
p(0x03D0C2, "Je vais t'apprendre les bonnes manières !", layout="dialogue_19_19")
p(0x03D0D3, "J'adore les gens forts !", layout="dialogue_19_19")
p(0x03D0E3, "J'ai un Pokémon rare.", layout="dialogue_19_19")
p(0x03D0FB, "Alors ? Pas mal, hein ?", layout="dialogue_19_19")
p(0x03D10F, (
                (
                    (
                        "Enchantée !\n"
                        "À nous deux !"
                    )
                )
            ),
  layout="dialogue_19_19")
p(0x03D12B, "Aïe ! Tu m'as touchée !",
  layout="dialogue_19_19")
p(0x03D13F, "Et si je tombais enceinte ?", layout="dialogue_19_19")
p(0x03D157, (
                (
                    "Ta tête m'agace !"
                )
            ), layout="dialogue_19_19")
p(0x03D1A4, "Je m'y suis fait. Ça va.", layout="dialogue_19_19")
p(0x03D1AF, "T'as vraiment pas l'air honnête !", layout="dialogue_19_19")
p(0x03D1C3, "Tu es loyal, non ?", layout="dialogue_19_19")
p(0x03D1CF, "Tu es mon 52e petit ami.", layout="dialogue_19_19")
p(0x03D1F5, "Bon, je te laisse partir...", layout="dialogue_19_19")
p(0x03D20F, "T'as vu ma force ?\nAlors, dégage !", layout="dialogue_19_19")
p(0x03D22A, "Bonne route ! Ha ha !", layout="dialogue_19_19")
p(0x03D23B, (
                (
                    "Pourquoi ce drôle de regard ?"
                )
            ), layout="dialogue_19_19")
p(0x03D24B, "Dommage, j'ai déjà un petit ami...", layout="dialogue_19_19")
p(
    0x03D25A,
    (
        (
            (
                (
                    (
                        (
                            "Je suis un pro\n"
                            "des Pokémon Vol."
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)
p(
    0x03D276,
    (
        (
            "Je vais à la Ligue cette année !"
        )
    ),
    layout="dialogue_19_19",
)

# ============================================================
# 39. FUCHSIA GYM (Koga)
# ============================================================

p(
    0x03D292,
    "Hé, Champion !\nIci, les murs\nsont invisibles !\nRepère les trous !",
    layout="dialogue_19_19",
)
p(0x03D2DD, "Tu n'as rien\nà faire ici !", layout="dialogue_19_19")
p(0x03D2EE, "Belle technique\nde ninja !", layout="dialogue_19_19")
p(
    0x03D2FD,
    "La force brute ?\nÇa ne suffit pas !\nLa technique,\nvoilà le secret !",
    layout="dialogue_19_19",
)
p(0x03D31C, (
                (
                    "Apparemment,\n"
                    "t'as compris."
                )
            ),
  layout="dialogue_19_19")
p(0x03D341, "Le Champion de cette Arène est fort. Sois prudent.", layout="dialogue_19_19")
p(0x03D35D, (
                (
                    "Je me suis inquiété pour rien..."
                )
            ), layout="dialogue_19_19")
p(0x03D37C, "Tu as l'air\nsûr de toi !", layout="dialogue_19_19")
p(0x03D39A, (
                (
                    "Enfin un combat\n"
                    "sérieux !\n"
                    "Depuis le temps !"
                )
            ), layout="dialogue_19_19")
p(
    0x03D3B7,
    "Voyons si tu peux\npasser !",
    layout="dialogue_19_19",
)
p(
    0x03D3C9,
    "Tu as réussi...",
    layout="dialogue_19_19",
)
p(0x03D3D8, (
                "Je rêvais de devenir ninja, alors j'ai rejoint cette Arène."
            ), layout="dialogue_19_19")
p(0x03D406, "T'es très fort !", layout="dialogue_19_19")

p(0x03D41F, (
                (
                    "KOGA : Un gamin\n"
                    "ose me défier ?\n"
                    "Le poison tue.\n"
                    "Découvre son art !"
                )
            ), layout="dialogue_19_19")
p(
    0x03D453,
    "KOGA : Bien joué ! Prends le Badge Âme. Tu peux utiliser Surf hors combat !",
    layout="dialogue_19_19",
)

# ============================================================
# 40. SAFARI ZONE
# ============================================================

p(
    0x03D49D,
    (
        "Bienvenue au Parc\n"
        "Safari ! Ici vivent\n"
        "des Pokémon rares.\n"
        "Entrée : 500 $.\n"
        "Ça te dit ?"
    ),
    layout="dialogue_19_19",
)
p(
    0x03D4EF,
    "À la prochaine !",
    layout="dialogue_19_19",
)
p(0x03D4FB, (
                "Ça fera 500 $.\n"
                "Bonne chance !"
            ), layout="dialogue_19_19")

p(0x03D50C, (
                (
                    (
                        "Tu as trouvé\n"
                        "la Cabane Secrète !\n"
                        "Voici ton prix !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x03D539, "CS03 obtenue !", layout="dialogue_19_19")
p(
    0x03D543,
    (
        (
            "CS03 : Surf !\n"
            "Un Pokémon te porte\n"
            "sur l'eau.\n"
            "Elle ne s'use pas !"
        )
    ),
    layout="dialogue_19_19",
)
p(0x03D582, "Dent d'Or obtenue !", layout="dialogue_19_19")
p(
    0x03D58E,
    (
        "Ma Dent d'Or ?\n"
        "Où est-elle donc ?\n"
        "Je l'ai peut-être\n"
        "perdue...\n"
        "au Parc Safari ?"
    ),
    layout="dialogue_19_19",
)

p(
    0x03D5B0,
    (
        (
            (
                (
                    (
                        (
                            "Mes Dents d'Or !\n"
                            "Merci ! Secret :\n"
                            "sans mon dentier,\n"
                            "j'avais honte\n"
                            "au bureau. Voici\n"
                            "ta récompense !"
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x03D61A, "CS04 obtenue !", layout="dialogue_19_19")
p(0x03D624, (
                (
                    (
                        "CS04 : Force !\n"
                        "Bouge les rochers !"
                    )
                )
            ), layout="dialogue_19_19")

# ============================================================
# 41. WATER ROUTES / ISLANDS
# ============================================================

p(0x03D64A, (
                (
                    "Allons, ne fais pas cette tête."
                )
            ), layout="dialogue_19_19")
p(0x03D65B, "Sors avec moi !", layout="dialogue_19_19")
p(0x03D667, "Je ne t'ai jamais vu par ici.", layout="dialogue_19_19")
p(0x03D683, (
                (
                    "Tu es le meilleur Dresseur que j'aie vu !"
                )
            ), layout="dialogue_19_19")
p(0x03D692, (
                (
                    (
                        "Encore un regard ?\n"
                        "Je te frappe !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x03D6A4, "Je ne recommencerai plus !", layout="dialogue_19_19")
p(0x03D6B5, "Ha ha ha...", layout="dialogue_19_19")
p(0x03D6CF, "Ce n'est rien.", layout="dialogue_19_19")
p(0x03D6E0, "Tu ne passeras pas.", layout="dialogue_19_19")
p(0x03D700, "Je plaisantais !", layout="dialogue_19_19")
p(0x03D70F, (
                (
                    "Tu m'as vraiment énervé !"
                )
            ), layout="dialogue_19_19")
p(0x03D732, "...", layout="dialogue_19_19")
p(
    0x03D746,
    "...",
    layout="dialogue_19_19",
)
p(0x03D767, "Ne te moque pas\nde moi !", layout="dialogue_19_19")
p(0x03D78B, "Désolé...", layout="dialogue_19_19")
p(0x03D79A, "Certains Pokémon Eau ont une Défense élevée.", layout="dialogue_19_19")
p(0x03D7BA, "Tu vas comprendre !", layout="dialogue_19_19")
p(
    0x03D7CB,
    (
        (
            (
                (
                    "PRÉSIDENT :\n"
                    "Merci, mon garçon !\n"
                    "Tu m'as sauvé !\n"
                    "Juste à temps !\n"
                    "Je ne l'oublierai !\n"
                    "Prends ce cadeau !"
                )
            )
        )
    ),
    layout="dialogue_19_19",
)
p(0x03D801, "Toujours pas d'excuses ?", layout="dialogue_19_19")
p(0x03D81D, (
                "Les meilleurs combattants du pays sont ici !"
            ), layout="dialogue_19_19")

# ============================================================
# 42. FIGHTING DOJO
# ============================================================

p(
    0x03D83E,
    "Master Ball reçue !",
    layout="dialogue_19_19",
)
p(0x03D88B, (
                (
                    "Tu viens défier notre dojo ?"
                )
            ), layout="dialogue_19_19")
p(0x03D89F, (
                "Seul le type Psy\n"
                "nous fait peur !"
            ), layout="dialogue_19_19")
p(0x03D8AF, (
                (
                    "Tu serais fort ? Alors, aucune pitié !"
                )
            ), layout="dialogue_19_19")
p(
    0x03D8C2,
    (
        "Notre Maître ?\n"
        "Le dieu du combat !\n"
        "Tu veux le défier ?\n"
        "Prépare-toi !"
    ),
    layout="dialogue_19_19",
)
p(0x03D8E8, (
                "Seul le type Psy\n"
                "nous fait peur !"
            ), layout="dialogue_19_19")
p(0x03D8FC, (
                (
                    "Numéro 2 du dojo,\n"
                    "c'est moi !\n"
                    "Tu nous défies ?\n"
                    "Impardonnable !\n"
                    "En garde !"
                )
            ), layout="dialogue_19_19")
p(0x03D910, (
                "Attends le Maître !\n"
                "Tu vas dérouiller !"
            ), layout="dialogue_19_19")

p(
    0x03D933,
    (
        "LE GRAND MAÎTRE :\n"
        "Tu le regretteras !"
    ),
    layout="dialogue_19_19",
)

p(
    0x03D960,
    (
        (
            (
                (
                    (
                        "J'ai perdu...\n"
                        "Épargne l'enseigne.\n"
                        "Choisis ton prix :\n"
                        "Kicklee ou Tygnon ?"
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x03D9CD, "Tygnon reçu !", layout="dialogue_19_19")
p(0x03D9DD, "Kicklee reçu !", layout="dialogue_19_19")

# ============================================================
# 43. SAFFRON GYM (Sabrina)
# ============================================================

p(
    0x03D9EC,
    "Hé, Champion !\nLes Pokémon Psy\nde Morgane ignorent\nle type Combat !",
    layout="dialogue_19_19",
)

p(
    0x03DA39,
    "Morgane est jeune,\nmais dirige l'Arène\nde Safrania !",
    layout="dialogue_19_19",
)
p(0x03DA59, (
                (
                    (
                        (
                            (
                                (
                                    "Safrania avait deux\n"
                                    "Arènes. L'Arène\n"
                                    "voisine a perdu..."
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03DA73,
    "La force seule\nne suffit pas !",
    layout="dialogue_19_19",
)
p(
    0x03DA8E,
    "Comment ai-je pu perdre ?",
    layout="dialogue_19_19",
)
p(0x03DABF, (
                (
                    "Le pouvoir Psy, c'est une force invisible !"
                )
            ), layout="dialogue_19_19")
p(
    0x03DAE3,
    "Comment est-ce possible ?",
    layout="dialogue_19_19",
)
p(
    0x03DAFC,
    "Morgane est encore\nplus jeune que moi.",
    layout="dialogue_19_19",
)
p(0x03DB22, (
                (
                    "Face à Morgane,\n"
                    "il faut de grands\n"
                    "pouvoirs Psy !"
                )
            ), layout="dialogue_19_19")
p(0x03DB40, (
                (
                    "Le Pokémon reflète\n"
                    "le caractère\n"
                    "de son Dresseur."
                )
            ), layout="dialogue_19_19")
p(0x03DB61, (
                (
                    "Hmm...\n"
                    "Tu as donc compris."
                )
            ), layout="dialogue_19_19")
p(0x03DB75, "Tu veux voir Morgane ?", layout="dialogue_19_19")
p(0x03DB8E, "Je te laisse passer.", layout="dialogue_19_19")
p(
    0x03DBB5,
    "Oh ? Apprendre\nles pouvoirs Psy\nne te tente pas ?",
    layout="dialogue_19_19",
)
p(0x03DBCF, "Si tu ne veux pas apprendre, tant pis...", layout="dialogue_19_19")

p(
    0x03DBE1,
    "MORGANE :\nJ'avais prédit\nta venue.\nJe suis médium\net hais le combat.\nVois mes pouvoirs !",
    layout="dialogue_19_19",
)

p(
    0x03DC38,
    "MORGANE : Le Badge Marais et la CT40 sont à toi ! Vague Psy inflige de gros dégâts psychiques.",
    layout="dialogue_19_19",
)

p(0x03DC83, "Badge Marais reçu !", layout="dialogue_19_19")
p(0x03DC8E, "CT40 reçue !", layout="dialogue_19_19")
p(0x03DCAA, "MORGANE :\nEncore toi ? Pff !", layout="dialogue_19_19")

# ============================================================
# 44. SEAFOAM ISLANDS / CINNABAR ISLAND
# ============================================================

p(0x03DCEB, (
                (
                    "Hein ? J'entends mal !"
                )
            ), layout="dialogue_19_19")
p(0x03DD07, (
                (
                    (
                        (
                            "Cette fois,\n"
                            "j'ai bien entendu."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03DD27, (
                (
                    "Déjà allé aux Îles Écume ?"
                )
            ), layout="dialogue_19_19")
p(0x03DD43, "On raconte qu'un Pokémon légendaire vivrait là...", layout="dialogue_19_19")
p(0x03DD4C, "Encore toi ?", layout="dialogue_19_19")
p(0x03DD5E, (
                (
                    (
                        (
                            "Tu ne veux pas sortir avec moi ?"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03DD77, "ARTIKODIN : ...", layout="dialogue_19_19")
p(0x03DD88, "T'es trop mignon !", layout="dialogue_19_19")
p(0x03DDA3, "Je suis plus beau que toi !", layout="dialogue_19_19")
p(0x03DDBB, "En fait,\nt'es le plus beau !", layout="dialogue_19_19")
p(0x03DDCC, "La mer est la source de toute vie.", layout="dialogue_19_19")
p(0x03DDE9, "J'ai compris !\nTu avais raison.", layout="dialogue_19_19")
p(0x03DE0C, (
                (
                    "Où vas-tu ?"
                )
            ), layout="dialogue_19_19")
p(0x03DE2C, "Cesse de me fixer !", layout="dialogue_19_19")
p(0x03DE4A, (
                (
                    (
                        (
                            "Vas-y, regarde tant que tu veux."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03DE67, "Que veux-tu ?", layout="dialogue_19_19")
p(0x03DE8B, (
                (
                    "Finalement, fais comme tu veux."
                )
            ), layout="dialogue_19_19")
p(0x03DE9F, (
                (
                    (
                        (
                            "On joue ensemble ?"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03DEBF, "Désolé... Je sais que tu es occupé.", layout="dialogue_19_19")

# ============================================================
# 45. CINNABAR LAB / FOSSILS
# ============================================================

p(
    0x03DEDF,
    "Salut ! J'étudie les fossiles rares. T'aurais un fossile pour moi ?",
    layout="dialogue_19_19",
)
p(
    0x03DF87,
    (
        (
            "Fossile Nautile !\n"
            "Celui d'Amonita !\n"
            "Je le ressusciterai\n"
            "avec ma machine.\n"
            "Confie-le-moi !"
        )
    ),
    layout="dialogue_19_19",
)
p(
    0x03DFC0,
    (
        (
            "Amonita revit !"
        )
    ),
    layout="dialogue_19_19",
)
p(0x03DFF8, "Amonita reçu !", layout="dialogue_19_19")
p(0x03E005, (
                (
                    (
                        (
                            "Fossile Dôme !\n"
                            "Il contient Kabuto.\n"
                            "Je le ressusciterai\n"
                            "avec ma machine.\n"
                            "Confie-le-moi !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x03E03E,
    "Ma machine va\nréanimer Kabuto !",
    layout="dialogue_19_19",
)
p(0x03E076, "Kabuto reçu !", layout="dialogue_19_19")

# ============================================================
# 46. POKEMON MANSION (Cinnabar Island)
# ============================================================

p(0x03E082, "Je me croyais seul.", layout="dialogue_19_19")
p(0x03E08F, "J'avais tort...", layout="dialogue_19_19")
p(0x03E0A9, (
                (
                    "Le volcan a détruit ce laboratoire."
                )
            ), layout="dialogue_19_19")
p(0x03E0C7, (
                (
                    "Il doit encore y avoir des Pokémon rares ici..."
                )
            ), layout="dialogue_19_19")
p(0x03E0F5, "Tu fais quoi ici ?", layout="dialogue_19_19")
p(0x03E11B, (
                (
                    "Visite librement."
                )
            ), layout="dialogue_19_19")

p(
    0x03E13F,
    (
        (
            "Quelle imprudence !"
        )
    ),
    layout="dialogue_19_19",
)

p(0x03E186, "Zut !\nTu m'as trouvé !", layout="dialogue_19_19")
p(0x03E19A, "Épargne-moi !", layout="dialogue_19_19")

# ============================================================
# 47. CINNABAR GYM (Blaine)
# ============================================================

p(0x03E1BB,
  (
      (
          (
              (
                  "Salut !\n"
                  "Champion en herbe !\n"
                  "Auguste maîtrise\n"
                  "les Pokémon Feu !"
              )
          )
      )
  ),
  layout="dialogue_19_19")
p(0x03E200, (
                (
                    "Les Pokémon Feu,\n"
                    "j'adore ça !"
                )
            ), layout="dialogue_19_19")
p(0x03E233, (
                (
                    "Je brûle..."
                )
            ), layout="dialogue_19_19")
p(0x03E259, "Le type Feu est\nle plus fort !", layout="dialogue_19_19")
p(0x03E27A, (
                (
                    "J'ai encore tant\n"
                    "à étudier..."
                )
            ), layout="dialogue_19_19")
p(0x03E28C, (
                (
                    "Tu crois pouvoir passer ?"
                )
            ), layout="dialogue_19_19")
p(0x03E2AD, "Ha ha ! Tu peux passer.", layout="dialogue_19_19")
p(0x03E2C0, (
                (
                    "Chacun a ses goûts.\n"
                    "Tu les connais ?"
                )
            ), layout="dialogue_19_19")
p(0x03E2DA, "Comment est-ce possible...", layout="dialogue_19_19")
p(0x03E2EA, (
                (
                    (
                        (
                            "J'ai vu beaucoup\n"
                            "d'Arènes. Celle-ci\n"
                            "est parfaite\n"
                            "pour un vol !"
                        )
                    )
                )
            ), layout="dialogue_19_19")

p(
    0x03E308,
    (
        (
            "Quelle chaleur !"
        )
    ),
    layout="dialogue_19_19",
)

p(0x03E347, "J'étais voleur. J'ai changé de vie.", layout="dialogue_19_19")
p(0x03E366, "Ha ha ! Tu peux passer.", layout="dialogue_19_19")

p(
    0x03E376,
    "AUGUSTE : Je suis le fougueux Champion de Cramois'Île ! Admire mes Pokémon Feu !",
    layout="dialogue_19_19",
)

p(
    0x03E3D0,
    (
        (
            (
                (
                    "AUGUSTE : Bravo !\n"
                    "Le Badge Volcan\n"
                    "augmente l'Attaque\n"
                    "de tes Pokémon."
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

# ============================================================
# 48. SEA ROUTES (swimmers/surfers)
# ============================================================

p(0x03E41A, (
                (
                    "Mon équipe de Magicarpe est imbattable !"
                )
            ), layout="dialogue_19_19")
p(0x03E433, (
                (
                    "Quelle défaite\n"
                    "cuisante..."
                )
            ), layout="dialogue_19_19")
p(0x03E441, (
                (
                    (
                        (
                            (
                                (
                                    "Encore un peu :\n"
                                    "Bourg Palette est\n"
                                    "tout près..."
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03E467, (
                (
                    (
                        (
                            (
                                "Bourg Palette ?\n"
                                "C'est chez toi !"
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03E483, "Rien qu'à te voir,\ntu m'énerves !", layout="dialogue_19_19")
p(0x03E4A6, (
                (
                    "Même battu, je ne changerai pas d'avis !"
                )
            ), layout="dialogue_19_19")
p(0x03E4C7, (
                (
                    (
                        "Tu te crois fort ?\n"
                        "Je vais te casser\n"
                        "les dents !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x03E4E8, "J'avais tort...", layout="dialogue_19_19")
p(0x03E502, (
                (
                    "Salut ! Ça te dit, un combat ?"
                )
            ), layout="dialogue_19_19")
p(0x03E51F, (
                "C'est rageant..."
            ), layout="dialogue_19_19")
p(0x03E53E, (
                "Halte !\n"
                "Tu restes ici !"
            ), layout="dialogue_19_19")
p(0x03E565, (
                (
                    "Tu vises la Ligue ?\n"
                    "Quel courage !\n"
                    "N'aie pas peur."
                )
            ), layout="dialogue_19_19")
p(0x03E580, (
                (
                    "DOMPTEUR : Sans PV, le Boss te bat ! KARATÉKA : Ma rage est au comble !"
                )
            ), layout="dialogue_19_19")
p(0x03E5B4, (
                (
                    (
                        (
                            "KARATÉKA : Je dois\n"
                            "progresser...\n"
                            "DOMPTEUR :\n"
                            "Je les comprends !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03E5E2, "DOMPTEUR : Je t'en prie... KARATÉKA : Viens !", layout="dialogue_19_19")

# ============================================================
# 49. VIRIDIAN GYM (Giovanni)
# ============================================================

p(
    0x03E612,
    "KARATÉKA : Si j'étais fort comme le Boss ! DOMPTEUR : On s'en va !",
    layout="dialogue_19_19",
)
p(0x03E640, "DOMPTEUR : Bats notre Boss et file à la Ligue ! GIOVANNI : Ha ha ! Encore toi...", layout="dialogue_19_19")
p(0x03E674, "SACHA :\nTu diriges\nla Team Rocket\net l'Arène ?", layout="dialogue_19_19")
p(0x03E6A6, "ROCKET : Tu nous as mis au chômage ! Impardonnable !", layout="dialogue_19_19")
p(0x03E6CC, "SACHA :\nQui êtes-vous ?", layout="dialogue_19_19")
p(
    0x03E6E9,
    (
        (
            (
                (
                    (
                        (
                            (
                                "Tu sais au moins\n"
                                "qui je suis ?\n"
                                "KARATÉKA : Un vrai\n"
                                "Dresseur remporte\n"
                                "ses victoires\n"
                                "avec élégance !"
                            )
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)
p(
    0x03E732,
    (
        (
            (
                "Le Boss va être furieux... TOPDRESSEUR : Moi, je suis un génie !"
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03E8A0,
    (
        (
            "GIOVANNI : Ha ha ! Tu as trouvé ma cachette. Aucune pitié ! Je suis Giovanni, le plus puissant Dresseur !"
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03E954,
    (
        (
            (
                (
                    (
                        (
                            (
                                "GIOVANNI :\n"
                                "J'ai perdu. Prends\n"
                                "le Badge Terre.\n"
                                "Tu seras un grand\n"
                                "Dresseur !\n"
                                "Je reprends\n"
                                "mon entraînement.\n"
                                "Je dissous\n"
                                "la Team Rocket\n"
                                "pour le moment.\n"
                                "À bientôt !"
                            )
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

# ============================================================
# 50. JESSIE & JAMES (post-game)
# ============================================================

p(0x03EAB4,
  (
      "JAMES : Un mauvais tour vous attend !"
  ),
  layout="dialogue_19_19")

p(0x03EC46,
  (
      (
          (
              "JESSIE :\n"
              "Préservons le monde\n"
              "de la dévastation !"
          )
      )
  ),
  layout="dialogue_19_19")

# ============================================================
# 51. ELITE FOUR / POKEMON LEAGUE
# ============================================================

p(
    0x0334D1,
    (
        (
            "Futur Champion ! Bats les quatre de suite. Toute défaite te renvoie au début. Courage !"
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03353B,
    "Tu vas affronter\n"
    "les quatre membres\n"
    "du Conseil des 4.\n"
    "Vise la victoire !",
    layout="dialogue_19_19",
)

p(
    0x033583,
    "Bienvenue !\n"
    "Je zuis OLGA,\n"
    "du Conzeil des 4 !\n"
    "Ma glaze va figer\n"
    "toute ton équipe !\n"
    "Ach ! Z'est parti !",
    layout="dialogue_19_19",
)

p(
    0x033604,
    "Tu es fort.\n"
    "Z'est bien.\n"
    "J'ai perdu.\n"
    "Passe dans la salle\n"
    "suivante !",
    layout="dialogue_19_19",
)

p(0x03365E,
  "Mon nom est ALDO,\n"
  "du Conseil des 4 !\n"
  "Mes Pokémon et moi,\n"
  "on adore la muscu !\n"
  "Sacha, en garde !\n"
  "À table !",
  layout="dialogue_19_19")

p(
    0x0336E4,
    "J'ai perdu...\n"
    "Bien joué !\n"
    "La suite t'attend.",
    layout="dialogue_19_19",
)

p(
    0x033715,
    "Je suis AGATHA,\n"
    "du Conseil des 4 !\n"
    "CHEN mise sur toi.\n"
    "Ce vieux machin\n"
    "était fort et beau.\n"
    "Mais le Pokédex\n"
    "ne suffit pas :\n"
    "les Pokémon\n"
    "servent au combat !\n"
    "Je vais te montrer\n"
    "un vrai combat !",
    layout="dialogue_19_19",
)

p(
    0x033814,
    "Je vois pourquoi\n"
    "CHEN t'apprécie !\n"
    "J'ai perdu.\n"
    "Tu peux passer.",
    layout="dialogue_19_19",
)

p(
    0x033861,
    "Moi, c'est PETER !\n"
    "Je dirige\n"
    "le Conseil des 4 !\n"
    "Les dragons sont\n"
    "des êtres sacrés.\n"
    "Durs à capturer,\n"
    "ils sont presque\n"
    "invincibles !\n"
    "Le glas sonne...\n"
    "Tu vas perdre !",
    layout="dialogue_19_19",
)

p(0x0338F4,
  "Incroyable !\n"
  "Tu mérites le titre\n"
  "de Maître Pokémon !\n"
  "Enfin...\n"
  "Pas encore !\n"
  "RÉGIS a déjà battu\n"
  "le Conseil des 4.\n"
  "Bats-le et deviens\n"
  "le vrai Champion !",
  layout="dialogue_19_19")

p(
    0x0339A9,
    "RÉGIS : Bonjour,\n"
    "minable. Toi, ici ?\n"
    "En complétant\n"
    "mon Pokédex,\n"
    "j'ai trouvé\n"
    "l'équipe parfaite !\n"
    "Je suis le meilleur\n"
    "Dresseur du monde !",
    layout="dialogue_19_19",
)

p(
    0x033A48,
    (
        (
            (
                (
                    (
                        "PROF. CHEN : Bravo,\n"
                        "Sacha !\n"
                        "Pikachu et toi\n"
                        "avez bien grandi.\n"
                        "Régis... Dommage !\n"
                        "Je venais saluer\n"
                        "le Champion.\n"
                        "Mais tu as perdu.\n"
                        "Pourquoi ?\n"
                        "Tu leur as refusé\n"
                        "amour et confiance.\n"
                        "Sans ce lien\n"
                        "tu ne seras jamais\n"
                        "Champion !"
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x033B7F,
    "PROF. CHEN :\n"
    "Sacha ! Ta victoire\n"
    "vient du lien\n"
    "qui t'unit\n"
    "à tes Pokémon.\n"
    "C'est merveilleux !\n"
    "Suis-moi !",
    layout="dialogue_19_19",
)

p(0x033BFE,
  (
      (
          "PROF. CHEN : Sacha est Champion ! Inscrivons ton nom et tes Pokémon. Rentrons : ta mère t'attend."
      )
  ),
  layout="dialogue_19_19")

# ============================================================
# 52. POST-GAME / LEGENDARY POKEMON
# ============================================================

p(
    0x033CB1,
    (
        "MAMAN : Étrange phénomène près d'Azuria. Olga enquête..."
    ),
    layout="dialogue_19_19",
)

p(
    0x033D67,
    (
        (
            "OLGA : Mewtwo\n"
            "causait tout ça."
        )
    ),
    layout="dialogue_19_19",
)

p(0x033E5F, (
                (
                    "Un Ticket Mystik ? Monte à bord ! Bienvenue à nouveau sur l'Océane !"
                )
            ), layout="dialogue_19_19")
p(0x033EAA, "HO-OH : ...", layout="dialogue_19_19")
p(0x033EEA, "LUGIA : ...", layout="dialogue_19_19")
p(
    0x033EF8,
    (
        (
            (
                "Quel voyage !\n"
                "Olga est revenue :\n"
                "la Ligue rouvre !"
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x03427E,
    "SACHA : C'est vous, les nouveaux Champions ? Hein ? Vous êtes...",
    layout="dialogue_19_19",
)

p(
    0x0343EF,
    (
        (
            "JAMES : Encore battus ! Va défier le nouveau chef !"
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x0346A1,
    (
        (
            (
                (
                    "KAMEIYU : Bravo ! Tu es sans rival à Kanto. "
                    "Pourtant, il y a plus fort ailleurs. Hoenn a "
                    "d'autres Pokémon. Reviens, Pokédex complet."
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x034739,
    (
        (
            "KAMEIYU : Hoenn a d'autres Pokémon. Finis ton Pokédex, puis reviens."
        )
    ),
    layout="dialogue_19_19",
)

p(0x0347A2, (
                (
                    "KAMEIYU : Bravo ! Le Pokédex de Kanto est complet. Ce Mew est à toi !"
                )
            ), layout="dialogue_19_19")
p(0x0347BD, "Mew reçu !", layout="dialogue_19_19")
p(0x034862, "ARBITRE : Bravo,\nChampion !", layout="dialogue_19_19")
p(0x034873, "KAMEIYU : D'accord, je m'avoue vaincu ! Content ?", layout="dialogue_19_19")
p(0x034887, "BEIBEI : Tu es vraiment formidable !", layout="dialogue_19_19")
p(0x0348B5, (
                (
                    (
                        "XIAO LI : Arrête !\n"
                        "Ou j'appelle\n"
                        "la police !"
                    )
                )
            ), layout="dialogue_19_19")

# Picked-up items
p(0x034927, "Rien obtenu.", layout="dialogue_19_19")
p(0x03492F, "Poké Ball reçue !", layout="dialogue_19_19")
p(0x03493B, "Super Ball reçue !", layout="dialogue_19_19")
p(0x034949, "Hyper Ball reçue !", layout="dialogue_19_19")
p(0x03495F, "Potion reçue !", layout="dialogue_19_19")
p(0x034973, "Hyper Potion\nreçue !", layout="dialogue_19_19")
p(0x034990, "Antidote reçu !", layout="dialogue_19_19")
p(0x03499D, "Réveil reçu !", layout="dialogue_19_19")
p(0x0349CC, "Total Soin reçu !", layout="dialogue_19_19")
p(0x0349DA, "Rappel reçu !", layout="dialogue_19_19")
p(0x0349FF, "Super Bonbon reçu !", layout="dialogue_19_19")
p(0x034A0D, "Pierre Feu reçue !", layout="dialogue_19_19")
p(0x034A19, "Pierre Eau reçue !", layout="dialogue_19_19")
p(0x034A25, "Pierre Foudre\nreçue !", layout="dialogue_19_19")
p(0x034A31, "Pierre Plante\nreçue !", layout="dialogue_19_19")
p(0x034A3D, "Pierre Lune reçue !", layout="dialogue_19_19")

# ============================================================
# 53. GARY POST-GAME
# ============================================================

p(
    0x037994,
    "RÉGIS :\nQuoi ? Déjà fini ?\nJ'ai tout donné,\nmais j'ai perdu...\nTant d'efforts...\nEt je perds ?\nMon entraînement\nétait parfait !\nBon... Tu es\nle Champion.\nJ'ai du mal\nà l'admettre...",
    layout="dialogue_19_19",
)

p(
    0x037A51,
    (
        "JESSIE : Oui !\n"
        "Son nom : Kameiyu !\n"
        "Il est développeur\n"
        "chez Nanjing Tech,\n"
        "à Céladopole !"
    ),
    layout="dialogue_19_19",
)

p(0x037AB1, "MIAOUSS : C'est exact, Miaouss !", layout="dialogue_19_19")

p(
    0x037ADC,
    (
        (
            (
                (
                    "KAMEIYU : Sacha !\n"
                    "Te voilà,\n"
                    "comme prévu !\n"
                    "Battons-nous\n"
                    "sans aucun regret !\n"
                    "Alors, prêt ?"
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x037BEF,
    (
        "Cette grotte est\n"
        "très sombre.\n"
        "Avec Flash,\n"
        "un Pokémon peut\n"
        "l'éclairer."
    ),
    layout="dialogue_19_19",
)

# ============================================================
# 54. ADDITIONAL TOWN NPCS
# ============================================================

p(0x034F66, (
                (
                    (
                        (
                            "Pas de Pokémon\n"
                            "sauvage au jardin !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x034F7F, (
                (
                    "Ce Pokémon, je l'ai eu par échange."
                )
            ), layout="dialogue_19_19")
p(0x034F9B, (
                (
                    "Certains Pokémon\n"
                    "n'obéissent pas...\n"
                    "Un Badge aiderait !"
                )
            ), layout="dialogue_19_19")
p(0x034FBD, (
                (
                    "L'enfant paie 50 $. Tu veux visiter ?"
                )
            ), layout="dialogue_19_19")
p(0x034FCE, "50 $ reçus. Merci !", layout="dialogue_19_19")
p(0x034FE7, "Ce mois-ci, on part dans l'espace !", layout="dialogue_19_19")
p(0x03500E, (
                (
                    "Trop de Pokémon ? Envoie-les au PC."
                )
            ), layout="dialogue_19_19")
p(0x035035, (
                (
                    "Tu peux voyager\n"
                    "avec six Pokémon."
                )
            ), layout="dialogue_19_19")
p(0x035048, (
                (
                    (
                        (
                            "J'entends souvent\n"
                            "d'étranges bruits."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0350BD, (
                (
                    "Toi aussi, tu as des Pokémon ? Entraîne-les bien !"
                )
            ), layout="dialogue_19_19")
p(0x035106, (
                (
                    "Rouler à vélo, c'est un vrai plaisir !"
                )
            ), layout="dialogue_19_19")
p(0x03513A, (
                (
                    (
                        "La Team Rocket fait\n"
                        "creuser les Pokémon\n"
                        "pour une raison...\n"
                        "Pas nette !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x035279,
  "Tu crois vraiment\n"
  "aux spectres ?",
  layout="dialogue_19_19")
p(0x035294, "Jamais je ne pardonnerai à la Team Rocket d'avoir tué la mère d'Osselait !", layout="dialogue_19_19")
p(0x0352BA, "La ville est\nen état de siège !", layout="dialogue_19_19")
p(0x035355, 'La Team Rocket...\nQuels sales types !', layout="dialogue_19_19")
p(0x035370, "Tu vas défier la Team Rocket ? Bravo !", layout="dialogue_19_19")
p(0x035397, (
                (
                    (
                        (
                            "J'ai vu le chef de la Team Rocket entrer ici..."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0353B5, (
                (
                    (
                        "Je t'admire !\n"
                        "Je suis avec toi !"
                    )
                )
            ), layout="dialogue_19_19")
p(0x0353D4, "J'ai vu ton combat. T'es très fort !", layout="dialogue_19_19")
p(
    0x0353F0,
    "Kameiyu, de Nanjing Tech, aurait des Pokémon légendaires...",
    layout="dialogue_19_19",
)
p(
    0x035433,
    (
        (
            (
                (
                    "Bienvenue !\n"
                    "Échange tes jetons\n"
                    "contre un prix.\n"
                    "Sans Boîte Jeton..."
                )
            )
        )
    ),
    layout="dialogue_19_19",
)
p(0x03546D,
  "J'adore jouer !\n"
  "Le temps file...",
  layout="dialogue_19_19")
p(0x035486, (
                (
                    (
                        (
                            "Pas de Boîte Jeton.\n"
                            "Pas de jeu."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x0354E1,
    "Où est passé\nce type ?",
    layout="dialogue_19_19",
)
p(0x035500, "Quand mes Pokémon faiblissent, j'achète des soins.", layout="dialogue_19_19")
p(0x03551C, (
                (
                    (
                        (
                            "Tiens... Il y aurait un sous-sol sous le Casino."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x035556,
    "Encore une victoire\naujourd'hui...\nHa ha !",
    layout="dialogue_19_19",
)
p(0x03556A, (
                (
                    "Je bâtissais ici quand des Pokémon m'ont attaqué !"
                )
            ), layout="dialogue_19_19")
p(
    0x035588,
    (
        "Selon la rumeur,\n"
        "le Conseil des 4\n"
        "du Plateau Indigo\n"
        "est redoutable."
    ),
    layout="dialogue_19_19",
)
p(
    0x03559C,
    "Le Président\nn'en finit plus\nquand il parle\nde Pokémon...",
    layout="dialogue_19_19",
)
p(0x0355B7, (
                (
                    (
                        (
                            (
                                (
                                    "Tadmorv vient\n"
                                    "de la boue marine.\n"
                                    "Tu le savais ?"
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0355DD, (
                (
                    "Le Parc Safari\n"
                    "abrite des Pokémon\n"
                    "très spéciaux !"
                )
            ), layout="dialogue_19_19")
p(0x035615, "Où est encore passé\nmon Roucool ?", layout="dialogue_19_19")
p(0x035638, (
                (
                    "Un Pokémon légendaire serait au Parc Safari..."
                )
            ),
  layout="dialogue_19_19")
p(0x03565F, (
                "Tu regardes la TV ?"
            ), layout="dialogue_19_19")
p(
    0x035685,
    "Combien d'espèces\nde Pokémon vivent\ndans ce monde ?",
    layout="dialogue_19_19",
)
p(0x0356AA, (
                (
                    "Défier l'Arène ?\n"
                    "Alors, abandonne."
                )
            ), layout="dialogue_19_19")
p(0x0356CF, "Le vieux maître du dojo est redoutable !", layout="dialogue_19_19")
p(
    0x0356F2,
    (
        (
            "Surpris ? Cela fait des années qu'on vit ici !"
        )
    ),
    layout="dialogue_19_19",
)
p(0x03571F, (
                (
                    "Aujourd'hui,\n"
                    "je suis à plat...\n"
                    "Trop fatigué..."
                )
            ), layout="dialogue_19_19")
p(0x035733, (
                (
                    "L'Eau est fatale aux Pokémon Feu !"
                )
            ), layout="dialogue_19_19")
p(0x035759, (
                (
                    (
                        (
                            (
                                "Un Pokémon rare ?\n"
                                "Sois le bienvenu !"
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x035780, (
                (
                    (
                        (
                            (
                                (
                                    "Mon fossile revit !\n"
                                    "Du Mont Sélénite !"
                                )
                            )
                        )
                    )
                )
            ),
  layout="dialogue_19_19")
p(
    0x0357A3,
    "La technologie\na fait des progrès\nincroyables !",
    layout="dialogue_19_19",
)
p(0x0357C7, (
                (
                    (
                        (
                            "Évoli aurait plus\n"
                            "de trois formes\n"
                            "d'évolution..."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0357DF, (
                "Salut, futur Champion... Bonne chance !"
            ), layout="dialogue_19_19")
p(0x035806, (
                (
                    "Le Conseil des 4\n"
                    "est redoutable.\n"
                    "Sois prudent..."
                )
            ), layout="dialogue_19_19")
p(0x035824, (
                (
                    (
                        "Le type Dragon est\n"
                        "redoutable.\n"
                        "Ses points faibles\n"
                        "sont très rares."
                    )
                )
            ), layout="dialogue_19_19")
p(0x03584D, (
                (
                    (
                        (
                            "Bats-le et avance.\n"
                            "Bonne chance !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(
    0x035874,
    "Mon grand-père\nvoudrait échanger\ndes Pokémon.",
    layout="dialogue_19_19",
)
p(0x0358AD, (
                (
                    "Un interrupteur s'est activé !"
                )
            ), layout="dialogue_19_19")
p(0x0358BD, (
                (
                    (
                        (
                            "Ce beau fossile,\n"
                            "tu n'en veux pas ?!"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0358F6,
  "Certains exploitent\n"
  "leurs Pokémon.\n"
  "Les pires ?\n"
  "La Team Rocket !",
  layout="dialogue_19_19")
p(0x03591B, (
                (
                    "Tout est trop cher.\n"
                    "Personne ne réagit."
                )
            ), layout="dialogue_19_19")
p(
    0x035939,
    (
        (
            (
                "À niveau égal,\n"
                "leur force diffère."
            )
        )
    ),
    layout="dialogue_19_19",
)
p(0x03596B, (
                (
                    (
                        (
                            (
                                (
                                    "Le niveau rend plus fort. Chaque type a ses faiblesses."
                                )
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0359A3, "Ticket Mystik\nreçu !", layout="dialogue_19_19")
p(0x035BF2, (
                (
                    (
                        (
                            "Mes Pokémon\n"
                            "n'obéissent pas...\n"
                            "Un Badge aiderait !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x035C48, (
                (
                    "J'aimerais avoir un Pokémon aussi obéissant !"
                )
            ), layout="dialogue_19_19")
p(0x035CC1, (
                (
                    (
                        (
                            "C'est étrange...\n"
                            "Plus personne\n"
                            "ne fait de vélo,\n"
                            "aujourd'hui !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x035D0E, "Je sens une force mystérieuse...", layout="dialogue_19_19")
p(0x035D2F, (
                (
                    (
                        (
                            "Une serrure\n"
                            "codée..."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x035D42, "Mot de passe obtenu !", layout="dialogue_19_19")
p(0x035D54, "Un mécanisme vient de s'activer...", layout="dialogue_19_19")
p(0x035D65, (
                "Il te manque\n"
                "quelques Badges.\n"
                "Obtiens-les tous,\n"
                "puis reviens !"
            ), layout="dialogue_19_19")
p(0x035DAC, (
                "Désolé, tu n'as pas\n"
                "assez d'argent !"
            ), layout="dialogue_19_19")

# System messages
p(0x035F05, "veut combattre!")
p(0x035F15, "est paralysé!")
p(0x035F23, "Super efficace! ")
p(0x035F34, "Poké Ball")
p(0x035F3D, "Impossible d'y croire!", layout="raw")
p(0x035F57, "A évolué en  ")
p(0x035F65, "N'a pas évolué!")
p(0x035F75, " Veut apprendre")
p(0x035F85, "Mais ne peut pas  ")
p(0x035F98, "Oublier une attaque?", layout="raw")
p(0x035FAE, "Oublie ")
p(0x035FB6, "Adverse. envoie  ")
p(0x0364F0, "Util. Potion Max !")
p(0x03650D, "Pas d'attaque")
p(0x03651B, "S'est endormi!")

# ============================================================
# 55. ADDITIONAL NPC TEXT
# ============================================================

p(
    0x036528,
    (
        (
            (
                "Vive la science ! Les PC échangent Pokémon et objets."
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x03656D,
  "La technologie est incroyable ! Le PC stocke et rappelle "
  "objets et Pokémon !",
  layout="raw")

p(0x0365D0, "Mes Pokémon sont épuisés...", layout="dialogue_19_19")

p(0x0365FE,
  (
      (
          (
              "Tu devrais faire\n"
              "une sieste."
          )
      )
  ),
  layout="dialogue_19_19")

p(
    0x036665,
    (
        (
            (
                "Ah, bien !\n"
                "Ton équipe et toi\n"
                "avez la forme !\n"
                "Sois prudent !"
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x0366A8,
    (
        (
            (
                "SŒUR DE RÉGIS : Papy a une mission pour toi !"
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x0366F3,
    (
        (
            "Tes Poké Balls\n"
            "sont drôlement\n"
            "pratiques !"
        )
    ),
    layout="dialogue_19_19",
)

p(0x03675E, (
                (
                    (
                        (
                            (
                                (
                                    "Tout le journal,\n"
                                    "par cœur !"
                                )
                            )
                        )
                    )
                )
            ),
  layout="dialogue_19_19")

p(
    0x036795,
    (
        (
            "Moi aussi, j'adore les Pokémon !"
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x0367EA,
    (
        (
            (
                "Moi aussi, je veux\n"
                "un vélo !"
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x036837, "Ton Pikachu est adorable !", layout="dialogue_19_19")
p(0x036853, 'Je meurs de faim...', layout="dialogue_19_19")
p(0x036876, "L'Océane a déjà\nlevé l'ancre ?", layout="dialogue_19_19")
p(0x036898, (
                "Comment réveiller\n"
                "ce dormeur ?"
            ), layout="dialogue_19_19")
p(0x0368BC, (
                (
                    (
                        (
                            (
                                "Les Taupiqueur\n"
                                "ont creusé\n"
                                "jusqu'à Argenta !"
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0368F1, "Des esprits hantent la Tour Pokémon.", layout="raw")
p(0x03692B, (
                (
                    (
                        (
                            (
                                'Tous les jours,\non étudie ici\nles Pokémon.'
                            )
                        )
                    )
                )
            ), layout="dialogue_19_19")

# ============================================================
# 56. PC SYSTEM
# ============================================================

p(0x03804B, "Retirer  Déposer", layout="dialogue_19_19")
p(0x03806F, "Le PC s'allume...", layout="dialogue_19_19")
p(0x038080, "Le PC s'éteint...", layout="dialogue_19_19")
p(0x038092, (
                "PROF. CHEN :\n"
                "Cette Poké Ball\n"
                "abrite un Pokémon.\n"
                "Il est pour toi !"
            ), layout="dialogue_19_19")
p(0x0380A6, (
                (
                    (
                        (
                            "PROF. CHEN :\n"
                            "Rapproche-toi\n"
                            "de tes Pokémon."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0380C5, (
                "Salut !\n"
                "Je peux t'aider ?"
            ), layout="dialogue_19_19")
p(0x0380EE, (
                (
                    "MAJOR BOB : Battu ! Prends le Badge Foudre et ceci !"
                )
            ), layout="dialogue_19_19")
p(
    0x0380FD,
    "Merci !",
    layout="dialogue_19_19",
)
p(0x038108, "Bienvenue !", layout="dialogue_19_19")
p(0x038149, "Désolé, impossible de combattre ici pour le moment...", layout="dialogue_19_19")
p(
    0x038173,
    "Même la machine\nd'échange est\nen panne...\nReviens plus tard.",
    layout="dialogue_19_19",
)
p(0x0381D2, (
                "Sacha utilise\n"
                "Coupe !"
            ), layout="dialogue_19_19")
p(0x038230, (
                "Cet arbre peut être\n"
                "coupé !"
            ), layout="dialogue_19_19")

# ============================================================
# 57. MOVE NAMES
# ============================================================

p(0x03117D, "Repli")
p(0x031238, "Vent Glace")
p(0x031252, "Laser Glace")
p(0x03125B, "Blizzard")
p(0x03126B, "Coud'Boue")
p(0x031274, "Tir de Boue")
p(0x03134A, "Balayage")
p(0x031402, "Rafale Psy")
p(0x031506, "Trempette")
p(0x031514, "Charge")
p(0x03151B, "Griffe")
p(0x031530, "Jackpot")
p(0x031538, "Bluff")

# ============================================================
# 58. ITEM NAMES
# ============================================================

p(0x0316EE, "SprBall ")
p(0x0316F7, "HyprBall")
p(0x031700, "MastrBal")
p(0x031709, "Potion")
p(0x031710, "Sup.Pot.")
p(0x031719, "Hyp.Pot.")
p(0x031722, "Max.Pot.")
p(0x03176F, "Huile Max")
p(0x031779, "BonbRare")
p(0x0317F8, "Dent d'Or ")
p(0x031803, "00Cpe CS")
p(0x03180D, "Vol CS")
p(0x031815, "Surf CS")
p(0x03181D, "ForceC")
p(0x031824, "Flash CS")

# Item descriptions
p(0x031A15, "Capturer Pokémon")
p(0x031A24, "Capture Pokémon100%")
p(0x031A37, "Évol. Pokémon Feu ")
p(0x031A4A, "Évol. Pokémon Eau ")
p(0x031A5D, "00000000000000Restaure 20PV")
p(0x031A78, "0Restaure50PV")
p(0x031A86, "0Restaur200 PV")
p(0x031A95, "0Restaur ts PV")
p(0x031AA4, "Guérit Poison")
p(0x031AB2, "Guérit Paralys")
p(0x031ACE, "Guérit le  Gel")
p(0x031AE8, "00Guérit Statut Pokémon")
p(0x031AFF, "Ranime Pokémon")
p(0x031B0E, "000000Restaure10PP 1 Atq")
p(0x031B29, "000Restaure ts PP 1 Atq")
p(0x031B54, "Évol. Pokémon Foudre")
p(0x031B67, "Évol. Pokémon Plante")
p(0x031B7A, "Évol. Pokémon Normal")
p(0x031B8D, "BaseDonnees Poké ")
p(0x031BA0, "Carte Ville")
p(0x031BAB, "000Colis Chen")
p(0x031BCA, "Passe pour l'Océane")
p(0x031BE8, "Permet de voir les fantômes")
p(0x031BFD, "Réveille Pokémon   ")
p(0x031C13, "Dentier en Or      ")
p(0x031C27, "Clé Arène Cram")
p(0x031C4F, "Caïd Rocket=")

# ============================================================
# 59. TRAINER NAMES
# ============================================================

p(0x031E6A, "Régis")      # Gary
p(0x031E6F, "Pierre")     # Brock
p(0x031E75, "Ondine")     # Misty
p(0x031E7B, "Major Bob")  # Lt.Surge
p(0x031E84, "Erika")
p(0x031E8A, "Koga")
p(0x031E8F, "Morgane")    # Sabrina
p(0x031E97, "Auguste")    # Blaine
p(0x031E9E, "Giovanni")
p(0x031EA7, "Olga   ")    # Lorelei
p(0x031EAF, "Aldo ")      # Bruno
p(0x031EB5, "Agatha")
p(0x031EBC, "Peter")      # Lance
p(0x031EC2, "Jessie & James")
p(0x031EE7, "Scout")
p(0x031F0A, "Sbire Rocket>")
p(0x031F18, "Sbire Rocket=")
p(0x031F52, "Crache-Feu")
p(0x031F67, "Topdresseur>")
p(0x031F75, "Loubard")
p(0x031F7E, "Dresseur JR=")
p(0x031F8A, "Intello")
p(0x031F95, "Gamin    ")
p(0x031FA7, "Kimono")        # Kimono Girl
p(0x031FE6, "Karatéka  ")
p(0x031FF1, "Prof.Chen")
p(0x031FFA, "Topdresseur=")
p(0x031C3B, "Dresseur JR>")

# ============================================================
# 60. POKEDEX (set 1 - 0x032xxx)
# ============================================================

p(0x03217A, "De la vapeur jaillit de sa queue quand il pleut", layout="pokedex_13x4")
p(0x0321AF, "Il rentre dans sa carapace face au danger.", layout="pokedex_13x4")
p(0x0321DD, "Ses oreilles gardent son équilibre en nageant.", layout="pokedex_13x4")
p(0x032211, "Ce Pokémon brutal a de puissants jets dorsaux.", layout="pokedex_13x4")
p(0x032244, "Sa carapace protège son corps fragile.", layout="pokedex_13x4")
p(0x032275, "Il se cache dans l'herbe pour manger des feuilles.", layout="pokedex_13x4")
p(0x0322A3, "Il pique ses ennemis avec ses 3 dards venimeux", layout="pokedex_13x4")
p(0x0322D3, "Il projette du sable pour se protéger lui-même", layout="pokedex_13x4")
p(0x032301, "Il rase l'eau pour chasser un Magicarpe.", layout="pokedex_13x4")
p(0x032335, "Il nage et chasse avec ses pattes palmées.", layout="pokedex_13x4")
p(0x03236A, "Il mange les oeufs des Pokémon oiseaux.", layout="pokedex_13x4")
p(0x032399, "Ses motifs ventraux avertissent ses ennemis.", layout="pokedex_13x4")
p(0x0323C8, "Sa queue évacue les décharges dans le sol.", layout="pokedex_13x4")
p(0x0323FB, "Vit en lieux arides loin de l'eau", layout="pokedex_13x4")
p(0x032420, "Ses piquants venimeux le rendent dangereux.", layout="pokedex_13x4")
p(0x032451, "Agressif, il attaque sans hésiter.", layout="pokedex_13x4")
p(0x03247F, "Sa queue brise les os de ses proies.",
  layout="pokedex_13x4")
p(0x0324AF, "Rare, il a beaucoup d'admirateurs", layout="pokedex_13x4")
p(0x0324E0, "En grandissant, ses queues se multiplient.",
  layout="pokedex_13x4")
p(0x032512, "Quand en colère il gonfle à une taille énorme", layout="pokedex_13x4")
p(0x032545, "Il vit dans le noir et voit avec des ultrasons.",
  layout="pokedex_13x4")
p(0x032573, "Ses pétales répandent un pollen toxique.", layout="pokedex_13x4")
p(0x0325A7, "Il absorbe l'énergie des racines des arbres", layout="pokedex_13x4")
p(0x0325D4, "Ses ailes ont des écailles très toxiques.",
  layout="pokedex_13x4")
p(0x032609, "Un groupe de Taupiqueur peut causer des séismes.", layout="pokedex_13x4")
p(0x032637, "Sa migraine renforce ses pouvoirs psy.", layout="pokedex_13x4")
p(0x03266B, "Il s'énerve facilement et attaque sans hésitation", layout="pokedex_13x4")
p(0x0326A0, "Admiré pour sa beauté il court comme s'il volait", layout="pokedex_13x4")
p(0x0326D4, "La spirale de son ventre endort ses ennemis.", layout="pokedex_13x4")
p(0x032709, "Ses ondes donnent de forts maux de tête.",
  layout="pokedex_13x4")
p(0x03273A, "Les arts martiaux le rendent plus fort.",
  layout="pokedex_13x4")
p(0x03276A, "Ses poings projettent ses ennemis au loin.", layout="pokedex_13x4")
p(0x032798, "Attire ses proies avec un arôme puis les avale", layout="pokedex_13x4")
p(0x0327CA, "Pris pour des rochers, on lui marche dessus.",
  layout="pokedex_13x4")
p(0x0327FC, "Il résiste aux explosions de dynamite.", layout="pokedex_13x4")
p(0x032830, "Adore courir il poursuit tout ce qui va vite", layout="pokedex_13x4")
p(0x032862, "Ses ondes magnétiques le font léviter.",
  layout="pokedex_13x4")
p(0x032893, "Il manie son poireau comme une épée.", layout="pokedex_13x4")
p(0x0328C2, "Quand 2 têtes dorment une tête reste éveillée", layout="pokedex_13x4")
p(0x0328EF, "Insensible au froid, il nage vite en eau glacée.", layout="pokedex_13x4")
p(0x032924, "Son odeur affreuse peut faire perdre connaissance.", layout="pokedex_13x4")
p(0x032954, "Son coup de langue aspire la force vitale", layout="pokedex_13x4")
p(0x032986, "Il adore rire des autres quand il les effraye", layout="pokedex_13x4")
p(0x0329BA, "Endort ses ennemis puis dévore leurs rêves", layout="pokedex_13x4")
p(0x0329E8, "Ses pinces servent d' équilibre en marche", layout="pokedex_13x4")
p(0x032A17, "Il peut exploser au moindre stimulus.",
  layout="pokedex_13x4")
p(0x032A47, "Pris pour des oeufs ils attaquent en essaim", layout="pokedex_13x4")
p(0x032A7C, "Il porte le crâne de sa mère décédée et pleure", layout="pokedex_13x4")
p(0x032AAF, "Ses os sont mille fois plus durs que les nôtres.", layout="pokedex_13x4")
p(0x032ADF, "Sa peau blindée repousse même la lave.",
  layout="pokedex_13x4")
p(0x032B12, "Rare, il apporterait le bonheur à tous.", layout="pokedex_13x4")
p(0x032B47, "Des lianes d'algues cachent son identité.", layout="pokedex_13x4")
p(0x032B75, "Il ne fuit pas au combat pour protéger ses petits", layout="pokedex_13x4")
p(0x032BA7, "En danger, il projette de l'encre par la bouche.", layout="pokedex_13x4")
p(0x032BD4, "Il nage en groupe à la saison de la ponte.",
  layout="pokedex_13x4")
p(0x032C04, "Tout membre perdu peut repousser.", layout="pokedex_13x4")
p(0x032C32, "Il mime des objets pour tromper ses ennemis.", layout="pokedex_13x4")
p(0x032C63, "Il balance ses hanches comme s'il dansait.", layout="pokedex_13x4")
p(0x032C97, "Près des centrales, il cause des pannes.",
  layout="pokedex_13x4")
p(0x032CCC, "Ce Pokémon turbulent charge ses ennemis.", layout="pokedex_13x4")
p(0x032CFF, "Énorme et féroce il peut détruire une ville", layout="pokedex_13x4")
p(0x032D32, "Il peut muter au contact de pierres élémentaires.", layout="pokedex_13x4")
p(0x032D60, "Sa queue est souvent prise pour celle d'une sirène.", layout="pokedex_13x4")
p(0x032D91, "Il stocke de l'énergie et atteint 900 degrés.", layout="pokedex_13x4")
p(0x032DC5, "Ce Pokémon ancien nage avec ses tentacules.",
  layout="pokedex_13x4")
p(0x032DFA, "Ressuscité d'un fossile dans ce qui était la mer", layout="pokedex_13x4")
p(0x032E2F, "Très paresseux, il dévore tout.", layout="pokedex_13x4")
p(0x032E5F, "Il guide les égarés dans les blizzards.",
  layout="pokedex_13x4")
p(0x032E93, "Pris pour un mythe, il fut découvert récemment.", layout="pokedex_13x4")
p(0x032EC4, "Ce Pokémon mystique dégage une aura douce.", layout="pokedex_13x4")
p(0x032EF7, "Un savant l'a créé par génie génétique.", layout="pokedex_13x4")
p(0x032F2A, "Son aboiement gronde comme le tonnerre.",
  layout="pokedex_13x4")
p(0x032F5E, "On dit qu'il crée des arcs-en-ciel en volant.",
  layout="pokedex_13x4")
p(0x032F9B, "Ce Pokémon légendaire régnerait sur les mers.",
  layout="pokedex_13x4")
p(0x032FD0, "Selon le mythe, il créa les continents.",
  layout="pokedex_13x4")

# ============================================================
# 61. POKEDEX (set 2 - 0x036xxx-0x037xxx)
# ============================================================

p(0x036950, "Le bulbe sur son dos a un doux parfum", layout="pokedex_13x4")
p(0x036978, "Il cherche la lumière pour obtenir de l'énergie.", layout="pokedex_13x4")
p(0x0369AA, "Il crache du feu bleu et blanc en colère.", layout="pokedex_13x4")
p(0x0369DE, "Son feu peut faire fondre les rochers.", layout="pokedex_13x4")
p(0x036A13, "Ses ventouses lui servent à grimper aux arbres.",
  layout="pokedex_13x4")
p(0x036A46, "Ses ailes étanches lui font braver la pluie.", layout="pokedex_13x4")
p(0x036A79, "Il sort son dard pour empoisonner ses ennemis.",
  layout="pokedex_13x4")
p(0x036AA9, "Il vole sans cesse à la recherche de proies", layout="pokedex_13x4")
p(0x036AD5, "Très commun, il vit en groupes de quarante.", layout="pokedex_13x4")
p(0x036B09, "Il mange des insectes dans l'herbe et vole vite.",
  layout="pokedex_13x4")
p(0x036B3D, "Ses ailes immenses le portent sans repos.",
  layout="pokedex_13x4")
p(0x036B71, "Réunis, ils peuvent causer un orage.",
  layout="pokedex_13x4")
p(0x036BA6, "Ses griffes cassées repoussent en un jour.",
  layout="pokedex_13x4")
p(0x036BD3, "Il préfère les attaques au contact et les morsures.",
  layout="pokedex_13x4")
p(0x036C06, "Son gabarit permet des attaques puissantes.", layout="pokedex_13x4")
p(0x036C3A, "S'il sent le danger il attaque avec ses cornes", layout="pokedex_13x4")
p(0x036C6B, "Timide, il fuit dès qu'il sent des humains.", layout="pokedex_13x4")
p(0x036CA0, "Neuf saints se seraient réincarnés en Feunard.", layout="pokedex_13x4")
p(0x036CD4, "Il chante une mélodie qui endort les ennemis", layout="pokedex_13x4")
p(0x036D04, "Il draine sans fin toute victime mordue.", layout="pokedex_13x4")
p(0x036D39, "Il s'enterre le jour et sème la nuit.", layout="pokedex_13x4")
p(0x036D6B, "Il suinte du nectar pour attirer ses proies.", layout="pokedex_13x4")
p(0x036D97, "Le champignon dorsal absorbe son énergie.",
  layout="pokedex_13x4")
p(0x036DCC, "À l'ombre des arbres, il mange des insectes.", layout="pokedex_13x4")
p(0x036E00, "Il vit sous terre et mange des racines.",
  layout="pokedex_13x4")
p(0x036E33, "Il erre pour trouver des pièces brillantes.",
  layout="pokedex_13x4")
p(0x036E68, "Admiré, il reste difficile à élever.", layout="pokedex_13x4")
p(0x036E9D, "Ses nageoires le font nager avec grâce.",
  layout="pokedex_13x4")
p(0x036ECD, "Furieux, il poursuit sa proie sans relâche.", layout="pokedex_13x4")
p(0x036EFF, "Territorial, il chasse les intrus en aboyant.",
  layout="pokedex_13x4")
p(0x036F30, "Il préfère nager plutôt que marcher.",
  layout="pokedex_13x4")
p(0x036F64, "Ce puissant nageur bat même les champions.",
  layout="pokedex_13x4")
p(0x036F94, "Il lit les pensées et se téléporte en danger.",
  layout="pokedex_13x4")
p(0x036FC8, "Il mémorise tout et n'oublie jamais rien.",
  layout="pokedex_13x4")
p(0x036FFD, "La ceinture qu'il porte limite sa force énorme", layout="pokedex_13x4")
p(0x037032, "Il piège des insectes avec des lianes et les mange", layout="pokedex_13x4")
p(0x037067, "Affamé, il avale tout ce qui bouge.", layout="pokedex_13x4")
p(0x037094, "Il dérive en mer et lance de l'acide.",
  layout="pokedex_13x4")
p(0x0370C6, "Ils piègent leurs proies avec leurs tentacules", layout="pokedex_13x4")
p(0x0370FB, "Il roule sur tout obstacle sans jamais les éviter", layout="pokedex_13x4")
p(0x037130, "Ses sabots sont 10 fois plus durs que les diamants", layout="pokedex_13x4")
p(0x037160, "Il sent la douleur cinq secondes plus tard.", layout="pokedex_13x4")
p(0x037191, "Le Kokiyas sur sa queue mange les restes", layout="pokedex_13x4")
p(0x0371C3, "Les taches solaires le font apparaître.",
  layout="pokedex_13x4")
p(0x0371F3, "Il préfère courir sur ses fortes pattes.", layout="pokedex_13x4")
p(0x037224, "Il adore nager dans une eau à 14 degrés.",
  layout="pokedex_13x4")
p(0x037259, "Il prospère en aspirant les boues polluées", layout="pokedex_13x4")
p(0x037287, "Sa coquille résiste à toutes les attaques.",
  layout="pokedex_13x4")
p(0x0372BA, "Il tire des pics de sa coquille pour se défendre.",
  layout="pokedex_13x4")
p(0x0372EB, "Il n'a pas de forme et semble fait de gaz", layout="pokedex_13x4")
p(0x03731E, "Les grottes qu'il creuse abritent des Taupiqueur.", layout="pokedex_13x4")
p(0x037351, "Il utilisera l'hypnose si on croise son regard", layout="pokedex_13x4")
p(0x037385, "Sa pince broie avec une force de 4,5 tonnes.", layout="pokedex_13x4")
p(0x0373B6, "Il stocke de l'électricité dans son propre corps", layout="pokedex_13x4")
p(0x0373E6, "On dit que Noeunoeuf naît d'une de ses têtes", layout="pokedex_13x4")
p(0x03741A, "Il manie habilement son os comme un boomerang.",
  layout="pokedex_13x4")
p(0x03744B, "Ses coups de pied terrassent ses rivaux.", layout="pokedex_13x4")
p(0x03747C, "Il frappe si vite qu'on ne voit pas ses coups.", layout="pokedex_13x4")
p(0x0374B0, "Sa langue de 2m de long peut causer la paralysie", layout="pokedex_13x4")
p(0x0374E1, "Son gaz interne peut le faire exploser.", layout="pokedex_13x4")
p(0x037516, "Gaz, poussière et bactéries le font grandir.", layout="pokedex_13x4")
p(0x037546, "Ses nageoires et sa queue le font reculer.",
  layout="pokedex_13x4")
p(0x03757B, "À la ponte, il remonte les rivières.",
  layout="pokedex_13x4")
p(0x0375B0, "Sa gemme brille quand il communique.",
  layout="pokedex_13x4")
p(0x0375E5, "Il crée des illusions de lui-même avec son agilité", layout="pokedex_13x4")
p(0x037618, "Né au volcan, son corps est couvert de flammes.", layout="pokedex_13x4")
p(0x037646, "Ses grandes pinces écrasent ses ennemis.", layout="pokedex_13x4")
p(0x037675, "Très faible et peu fiable, il vit partout.", layout="pokedex_13x4")
p(0x0376A7, "Un gentil Pokémon qui lit dans les pensées", layout="pokedex_13x4")
p(0x0376DA, "Il change son ADN pour copier son ennemi.",
  layout="pokedex_13x4")
p(0x03770E, "Il capte des ions négatifs et lance des éclairs.",
  layout="pokedex_13x4")
p(0x03773F, "Programmé, il voyage dans le cyberespace.", layout="pokedex_13x4")
p(0x037771, "Sa lourde coquille rend la capture de proies dure", layout="pokedex_13x4")
p(0x0377A6, "Il tranche ses proies et aspire leurs fluides.", layout="pokedex_13x4")
p(0x0377D9, "Ses crocs visent la gorge de son ennemi.", layout="pokedex_13x4")
p(0x03780A, "Oiseau mystique qui apparaît dans les tempêtes.", layout="pokedex_13x4")
p(0x037838, "Ses ailes font jaillir des gerbes de flammes.",
  layout="pokedex_13x4")
p(0x037869, "Pokémon marin rare, son Q.I. égale le nôtre.", layout="pokedex_13x4")
p(0x03789A, "Si rare que très peu de gens l'ont vu.", layout="pokedex_13x4")
p(0x0378C9, "Son cri ferait entrer les volcans en éruption.",
  layout="pokedex_13x4")
p(0x0378F6, "Il parcourt le monde et purifie l'eau polluée.",
  layout="pokedex_13x4")
p(0x03792A, "On dit que ses déluges gonflent les mers.",
  layout="pokedex_13x4")
p(0x03795F, "Il vit depuis des millions d'années dans l'ozone.",
  layout="pokedex_13x4")

# ============================================================
# 62. POKEMON NAMES (official French names)
# ============================================================

p(0x036036, "Papilusion")
p(0x0360B6, "Sablaireau")
p(0x0360C9, " Nidorina")
p(0x0360E6, " Nidorino")
p(0x0361B5, "Caninos  ")
p(0x0361BF, "Arcanin ")
p(0x036265, "Galopa  ")
p(0x0363CF, "Insécateur")
p(0x036431, "Pyroli ")
p(0x036451, "Kabuto")

# ============================================================
# 63. PADDING / MISCELLANEOUS
# ============================================================

p(0x03F033, "Tu es vraiment coriace...", layout="dialogue_19_19")


# ============================================================
# 64. FIX: MISSING TEXT
#     (19 texts lost during consolidation)
# ============================================================

p(
    0x034CB3,
    (
        (
            (
                "Moi aussi, j'élève\n"
                "des Pokémon forts.\n"
                "Fini les brimades !"
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x034D08,
    (
        (
            "Poké Balls en vente à la Boutique !"
        )
    ),
    layout="dialogue_19_19",
)
# The English patch pointed this Route 1 sign into the end of the previous
# dialogue. It now has its own translation and allocation.
p(
    0x034D3A,
    (
        (
            (
                "Un Pokémon choyé\n"
                "s'attachera à toi."
            )
        )
    ),
    layout="dialogue_19_19",
)

p(
    0x034D4C,
    (
        (
            (
                (
                    "Voler fait peur,\n"
                    "mais te ramène vite\n"
                    "à Bourg Palette."
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x034DE5,
  "Cette Arène Pokémon\n"
  "reste fermée.\n"
  "Qui est donc\n"
  "le Champion ?",
  layout="dialogue_19_19")

p(0x034E8B, (
                (
                    (
                        "La capacité Coupe\n"
                        "tranche ces arbres."
                    )
                )
            ), layout="dialogue_19_19")

p(0x034F38,
  "Les Scouts d'ici\n"
  "sont forts.\n"
  "Mais Pierre est\n"
  "redoutable !",
  layout="dialogue_19_19")

p(
    0x035206,
    (
        (
            (
                (
                    (
                        (
                            "À Lavanville,\n"
                            "la Tour Pokémon\n"
                            "est un cimetière."
                        )
                    )
                )
            )
        )
    ),
    layout="dialogue_19_19",
)

p(0x03523F,
  "Des spectres rôdent\n"
  "à la Tour Pokémon.\n"
  "Ce sont sûrement\n"
  "des Pokémon tués\n"
  "par la Team Rocket.",
  layout="dialogue_19_19")

p(0x0350D6, (
                (
                    "Tu veux compléter ton Pokédex ? Génial !"
                )
            ), layout="dialogue_19_19")

p(
    0x035154,
    "Sans l'objet volé, il faudra tout abandonner...",
    layout="dialogue_19_19",
)

p(0x0331EF, (
                (
                    "Tu as dû en baver pour arriver jusqu'ici !"
                )
            ), layout="dialogue_19_19")
p(0x033224, (
                (
                    "Toi aussi, tu viens défier la Ligue ?"
                )
            ), layout="dialogue_19_19")
p(0x033278, 'Pourquoi es-tu là ?', layout="dialogue_19_19")
p(0x0333BD, (
                (
                    'Magie, tu connais ?'
                )
            ), layout="dialogue_19_19")
p(0x0333E3, "Incroyable...", layout="dialogue_19_19")
p(0x0333FF, "Tu t'es bien battu, mais tu t'arrêtes ici !", layout="dialogue_19_19")
p(0x03345D, 'Pourquoi sont-ils\ntous si faibles ?', layout="dialogue_19_19")
p(0x03349F, "Tu n'iras pas plus loin !", layout="dialogue_19_19")

p(0x0398D1,
  (
      (
          (
              (
                  (
                      (
                          "ONDINE : Ma méthode\n"
                          "est simple : miser\n"
                          "sur le type Eau !\n"
                          "À toi d'affronter\n"
                          "la plus belle fille\n"
                          "du monde !"
                      )
                  )
              )
          )
      )
  ),
  layout="dialogue_19_19")

# ============================================================
# 65. FIX 2: REMAINING OMISSIONS
# ============================================================

p(0x03347F, (
                (
                    "Je manque sûrement d'amour pour eux..."
                )
            ), layout="dialogue_19_19")
p(
    0x034DA2,
    (
        (
            (
                "Chenipan n'est pas venimeux. Aspicot, si !"
            )
        )
    ),
    layout="dialogue_19_19",
)
p(0x033238, "Tu pourrais devenir Champion !", layout="dialogue_19_19")
p(0x033436, 'Je vais me marier !', layout="dialogue_19_19")
p(0x034E1E, "Un os de dragon !\nJe l'ai trouvé !", layout="dialogue_19_19")
p(0x034E32, (
                (
                    (
                        (
                            "Une Potion soigne les Pokémon épuisés."
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03320B, (
                (
                    "À toi de jouer, maintenant."
                )
            ), layout="dialogue_19_19")
p(0x033290, "Tu vises haut !", layout="dialogue_19_19")
p(0x033425, "Dire que j'ai perdu...", layout="dialogue_19_19")
p(0x0334BD, "C'était écrit...", layout="dialogue_19_19")
p(0x034F18, (
                (
                    "Ah... Ces machines\n"
                    "sont captivantes..."
                )
            ), layout="dialogue_19_19")

# ============================================================
# 66. FIX 3: FINAL OMISSIONS
# ============================================================

p(0x033253, "Prépare-toi !", layout="dialogue_19_19")
p(0x03326D, "J'étais prêt !", layout="dialogue_19_19")
p(
    0x0392E5,
    "Ah bon ? Dommage...",
    layout="dialogue_19_19",
)
p(0x03AE18, "Désolé...\nJe m'en mêle pas.", layout="dialogue_19_19")
p(
    0x03CE16,
    "Le Parc regorge\nde Pokémon rares...",
    layout="dialogue_19_19",
)
p(0x03DE25, "Va où tu veux. Ça m'est égal.", layout="dialogue_19_19")

# ============================================================
# 67. FIX 4: DETAILED FINAL AUDIT
#     39 text records and one item hidden in padding
# ============================================================

# -- Battle --
p(0x0302E4, "00Raté!")
p(0x0303BC, "000000Chute")
p(0x030403, "Quoi?")
p(0x03041D, "Oh!Sauvage ")
p(0x03063B, "Critique!")
p(0x03068E, "0000000déjà     ")
p(0x03072D, "Restaure! ")

# -- Menus --
p(0x0305F5, "   00Objet")
p(0x030618, "00PUI :")
p(0x0306C0, "Preci.  ")
p(0x03081F, "00Équipe plei")

# -- HM list (HM menu) --
p(0x033060, "Coupe")     # Cut
p(0x033064, "Vol")       # Fly
# 0x033068 Surf = identique FR
p(0x03306D, "Force   ")  # Strength
# 0x033076 Flash = identique FR
p(0x03307C, "CS01")      # HM01
p(0x033081, "CS02")      # HM02
p(0x033086, "CS03")      # HM03
p(0x03308B, "CS04")      # HM04
p(0x033090, "CS05")      # HM05

# -- Move --
p(0x03129D, "0000Abîme  ")   # Fissure

# -- Item --
p(0x030F8E, "PierrPla")     # LeafSton (inside the padding block)
p(0x0349B3, "Antigel reçu !", layout="dialogue_19_19")  # Ice Heal

# -- League dialogue --
p(0x03344F, "Finalement, non... Tu veux m'épouser ?", layout="dialogue_19_19")  # Unbelievable!

# -- Pokemon names (starter selection screen) --
p(0x035FCD, "Bulbizarre")   # Bulbasaur (9 car -> 10 = tronque a 9)
p(0x035FD7, "Herbizarre")   # Ivysaur
p(0x035FDF, "Florizarre")   # Venusaur
p(0x035FE8, "Salamèche ")   # Charmander; the charset renders e-grave as e
p(0x035FF3, "Reptincel ")   # Charmeleon
p(0x035FFE, "Dracaufeu")    # Charizard

# -- Miscellaneous NPC dialogue --
p(0x039F32, "Léo est sauvé !", layout="dialogue_19_19")  # Run Program.
p(0x03A517, (
                (
                    (
                        "Merci, ça va mieux ! Coupe ? Je suis épuisé... Apprends-la plutôt à un Pokémon."
                    )
                )
            ), layout="dialogue_19_19") # (Rub,rub,rub)
p(0x03AD1E, "Encore perdu...", layout="dialogue_19_19")    # Too tough!
p(0x03BB79,
  (
      "Pas si vite !\n"
      "Tu ne passeras pas."
  ),
  layout="dialogue_19_19")  # Oww! Beaten!
p(0x03BDDA, "Hein..?")       # Why...?
p(0x03C088, "Bon sang...", layout="dialogue_19_19")  # Join...Us...
p(
    0x03C1D6,
    "Partez... Quittez ce lieu !",
    layout="dialogue_19_19",
)
p(0x03CBB2, "L'Eau bat le Feu !", layout="dialogue_19_19")
p(0x03D11F, (
                (
                    (
                        "Je m'incline !"
                    )
                )
            ), layout="dialogue_19_19")  # Aww,bummer!
p(0x03DD98, (
                (
                    "Ah bon ? Dommage..."
                )
            ), layout="dialogue_19_19")     # Torpedoed!

# ============================================================
# 68. FIX 5: BIGRAM/FREQUENCY ANALYSIS
#     133 short names: moves, items, trainers, French TM labels
# ============================================================

# -- Trainer classes --
p(0x031EDD, "Deputy")       # 二当家, Fighting Dojo deputy
p(0x031EF3, "Kinésiste")    # Psychic
p(0x031EFB, "Fillette")     # Lass
p(0x031F00, "Écolier  ")    # Schoolkid
p(0x031F26, "Scientifique") # Scientist
p(0x031F30, "Montagnard")   # Hiker
p(0x031F36, "Nageur> ")     # Swimmer>
p(0x031F3F, "Nageuse=")     # Swimmer=
p(0x031F48, "Gentleman")    # Gentleman
p(0x031F60, "Marin ")       # Sailor
p(0x031F9F, "Prof")         # Teacher, classe officielle Gen 2
p(0x031FB3, "Exorciste")    # Channeler
p(0x031FBD, "Pêcheur  ")    # Fisherman; the charset renders e-circumflex as e
p(0x031FC7, "Rocker")       # Rocker (identique)
p(0x031FCE, "Ornithologue")  # Bird Keeper (11 car -> tronque)
p(0x031FDA, "Motard")       # Biker
p(0x031FE0, "Ninja")        # Ninja (identique)
p(0x032008, "Pokémaniac")   # Pokémaniac
p(0x032013, "Pillard")      # Burglar

# -- Item names --
p(0x031737, "AntiPa")       # P.Heal -> Anti-Paralysie
p(0x03173E, "0Réveil")      # S.Heal -> Réveil
p(0x031746, "Antigel ")     # Ice Heal
p(0x03174F, "AntiBrul")     # BurnHeal
p(0x031758, "Tot.Soin")     # Full Heal, nom officiel R/B
p(0x031761, "Rappel")       # Revive
p(0x031769, "Huile")        # Ether
p(0x031782, "PierrFeu")     # FireSton
p(0x03178B, "PierrEau")     # WatrSton
p(0x031794, "PierrFdr")     # ThunSton
p(0x03179D, "PierrLun")     # MoonSton
p(0x0317A6, "Colis ")       # Parcel
p(0x0317B5, "Carte")        # Map (3 car -> tronque a 3)
p(0x0317B9, "Nautile")      # HelixFosil
p(0x0317C4, "Fos.Dôme  ")   # DomeFossil
p(0x0317CF, "Passe Bateau") # S.S.Ticket
p(0x0317DA, "Limonade")     # Lemonade
p(0x0317E3, "Scope Sylphe") # Silph Scope
p(0x0317EE, "Poké Flûte")   # Poké Flute

# -- Item descriptions --
p(0x031A0F, "Vide ")        # Empty
p(0x031AC1, "Guérit Somml")  # Cures sleep
p(0x031ADC, "Guérit Brulr")  # Cures Burn
p(0x031B42, "Pokémon+1 Niveau ")  # PokémonLevelUp1LV
p(0x031BBC, "Fossile Pokémon")  # PokémonFossil
p(0x031BE0, "Limonad")      # Lemonad
p(0x031C47, "Jongleur")     # Juggler
p(0x031C61, "Jumelles")     # Twins
p(0x031C67, "Pokéfan>")     # Pokéfan

# -- Secret Key --
p(0x030F83, "Clé Secrète")  # Secret Key (inside padding)

# -- TM 01-40 -> CT 01-40 --
p(0x03182D, "CT 01 ")
p(0x031835, "CT 02 ")
p(0x03183D, "CT 03 ")
p(0x031845, "CT 04 ")
p(0x03184D, "CT 05 ")
p(0x031855, "CT 06 ")
p(0x03185D, "CT 07 ")
p(0x031865, "CT 08 ")
p(0x03186D, "CT 09 ")
p(0x031875, "CT 10 ")
p(0x03187D, "CT 11 ")
p(0x031885, "CT 12 ")
p(0x03188D, "CT 13 ")
p(0x031895, "CT 14 ")
p(0x03189D, "CT 15 ")
p(0x0318A5, "CT 16 ")
p(0x0318AD, "CT 17 ")
p(0x0318B5, "CT 18 ")
p(0x0318BD, "CT 19 ")
p(0x0318C5, "CT 20 ")
p(0x0318CD, "CT 21 ")
p(0x0318D5, "CT 22 ")
p(0x0318DD, "CT 23 ")
p(0x0318E5, "CT 24 ")
p(0x0318ED, "CT 25 ")
p(0x0318F5, "CT 26 ")
p(0x0318FD, "CT 27 ")
p(0x031905, "CT 28 ")
p(0x03190D, "CT 29 ")
p(0x031915, "CT 30 ")
p(0x03191D, "CT 31 ")
p(0x031925, "CT 32 ")
p(0x03192D, "CT 33 ")
p(0x031935, "CT 34 ")
p(0x03193D, "CT 35 ")
p(0x031945, "CT 36 ")
p(0x03194D, "CT 37 ")
p(0x031955, "CT 38 ")
p(0x03195D, "CT 39 ")
p(0x031965, "CT 40 ")

# -- Move names --
p(0x031126, "Éruption")      # Erupt
p(0x03112C, "Feu Follet")    # Wisp
p(0x031131, "Écume")         # Bubble
p(0x031177, "Claquoir")      # Clamp
p(0x031196, "Étincelle")     # Spark
p(0x0311BC, "Fatal-Foudre")  # Thunder
p(0x0311CD, "Vol-Vie")       # Absorb, nom officiel R/B et O/A/C
p(0x0311E7, "Fou.")          # Whip, fragment without its own pointer
p(0x0311FF, "Bomb")          # Bomb, fragment without its own pointer
p(0x031224, "Spore")        # Spore (identique)
p(0x03127D, "Tunnel")        # Dig
p(0x031286, "Mas.")          # Club, fragment without its own pointer
p(0x0312BC, "Tomb")          # Tomb, fragment without its own pointer
p(0x0312F2, "Corn")          # Horn, fragment without its own pointer
p(0x0312FC, "Halo")         # Glow (4 car)
p(0x03132B, "Détritus")      # Sludge
p(0x031368, "Vendetta")      # Revenge
p(0x0313B9, "Picpic")        # Peck
p(0x0313BE, "Tornade")       # Gust
p(0x0313D8, "Vol")          # Fly
p(0x0313E3, "Rebond")       # Bounce
p(0x03144A, "Repos")         # Rest
p(0x03145D, "Yoga")          # Mind, fragment without its own pointer
p(0x03146F, "Étonnement")    # Astonish
p(0x031496, "Ouragan")      # Twister
p(0x0314D2, "Morsure")       # Bite
p(0x0314D7, "Mâchouille")    # Crunch
p(0x0314F1, "Queu")          # Tail, fragment without its own pointer
p(0x031523, "Écras'Face")    # Pound
p(0x031541, "Coupe")         # Cut
p(0x031545, "Météores")     # Swift
p(0x03154B, "Écrasement")    # Stomp
p(0x031584, "Explosion")     # Explode
p(0x03159C, "Berceuse")      # Sing
p(0x0315A6, "Bise")          # Kiss, fragment without its own pointer
p(0x0315B9, "Rugissement")   # Growl
p(0x0315BF, "Gonflette")     # Bulk-up
p(0x0315DC, "Fou.")          # Whip, fragment without its own pointer
p(0x0315E1, "Charme")        # Charm
p(0x0315FB, "Soin")          # Recover
p(0x03160A, "Hurlement")     # Roar
p(0x031624, "Riposte")       # Counter
p(0x03162C, "Force")         # Strength

# ============================================================
# 69. POKEMON NAMES (main table 0x035FC0-0x0364F0)
#     105 names translated to their official French names
#     WARNING: truncated to the original English name length
#     Corrigez manuellement si le nom affiche est coupe
# ============================================================

p(0x036008, "Carapuce")     # Squirtle
p(0x036011, "Carabaffe")    # Wartortle
p(0x03601B, "Tortank  ")    # Blastoise
p(0x036025, "Chenipan")     # Caterpie
p(0x03602E, "Chrysacier")   # Metapod
p(0x036041, "Aspicot")      # Weedle
p(0x036048, "Coconfort")    # Kakuna
p(0x03604F, "Dardargnan")   # Beedrill
p(0x036058, "Roucool")      # Pidgey
p(0x03605F, "Roucoups ")    # Pidgeotto
p(0x036069, "Roucarnage")   # Pidgeot
p(0x036079, "Rattatac")     # Raticate
p(0x036082, "Piafabec")     # Spearow
p(0x03608A, "Rapasdepic")   # Fearow
p(0x036091, "Abo  ")        # Ekans
p(0x0360AC, "Sabelette")    # Sandshrew
p(0x0360F9, "Mélofée")      # Clefairy
p(0x036102, "Mélodelfe")    # Clefable
p(0x03610B, "Goupix")       # Vulpix
p(0x036112, "Feunard  ")    # Ninetales
p(0x03611C, "Rondoudou ")   # Jigglypuff
p(0x036127, "Grodoudou ")   # Wigglytuff
p(0x036132, "Nosferapti")   # Zubat
p(0x036138, "Nosferalto")   # Golbat
p(0x03613F, "Mystherbe")    # Oddish
p(0x036146, "Ortide")       # Gloom
p(0x03614C, "Rafflesia")    # Vileplume
p(0x036165, "Mimitoss")     # Venonat
p(0x03616D, "Aéromite")     # Venomoth
p(0x036176, "Taupiqueur")   # Diglett
p(0x03617E, "Triopikeur")   # Dugtrio
p(0x036186, "Miaouss")      # Meowth
p(0x036195, "Psykokwak")    # Psyduck
p(0x03619D, "Akwakwak")     # Golduck
p(0x0361A5, "Férosinge")    # Mankey
p(0x0361AC, "Colossinge")   # Primeape
p(0x0361C8, "Ptitard")      # Poliwag
p(0x0361D0, "Têtarte  ")    # Poliwhirl; the charset renders e-circumflex as e
p(0x0361DA, "Tartard  ")    # Poliwrath
p(0x0361FA, "Machoc")       # Machop
p(0x036201, "Machopeur")    # Machoke
p(0x036209, "Mackogneur")   # Machamp
p(0x036211, "Chétiflor")    # Bellsprout
p(0x03621C, "Boustiflor")   # Weepinbell
p(0x036227, "Empiflor  ")   # Victreebel
p(0x036247, "Racaillou")    # Geodude
p(0x03624F, "Gravalanch")   # Graveler
p(0x036258, "Grolem")       # Golem
p(0x03626E, "Ramoloss")     # Slowpoke
p(0x036277, "Flagadoss")    # Slowbro
p(0x036292, "Canarticho")   # Farfetch'd
p(0x0362AA, "Otaria")       # Seel
p(0x0362AF, "Lamantine")    # Dewgong
p(0x0362B7, "Tadmorv")      # Grimer
p(0x0362BE, "Grotadmorv")   # Muk
p(0x0362C2, "Kokiyas ")     # Shellder
p(0x0362CB, "Crustabri")    # Cloyster
p(0x0362D4, "Fantominus")   # Gastly
p(0x0362DB, "Spectrum")     # Haunter
p(0x0362E3, "Ectoplasma")   # Gengar
p(0x0362EF, "Soporifik")    # Drowzee
p(0x0362F7, "Hypnomade")    # Hypno
p(0x036304, "Krabboss")     # Kingler -> Krabboss
p(0x03630C, "Voltorbe")     # Voltorb
p(0x03631E, "Noeunoeuf")    # Exeggcute
p(0x036328, "Noadkoko ")    # Exeggutor
p(0x036332, "Osselait")     # Cubone
p(0x036339, "Ossatueur")    # Marowak
p(0x036341, "Kicklee  ")    # Hitmonlee
p(0x03634B, "Tygnon    ")   # Hitmonchan
p(0x036356, "Excelangue")   # Lickitung
p(0x036360, "Smogo  ")      # Koffing
p(0x036368, "Smogogo")      # Weezing
p(0x036370, "Rhinocorne")   # Rhyhorn
p(0x036378, "Rhinoféros")   # Rhydon
p(0x03637F, "Leveinard")    # Chansey
p(0x036387, "Saquedeneu")   # Tangela
p(0x03638F, "Kangourex ")   # Kangaskhan
p(0x03639A, "Hypotrempe")   # Horsea
p(0x0363A1, "Hypocéan")     # Seadra
p(0x0363A8, "Poissirène")   # Goldeen
p(0x0363B0, "Poissoroy")    # Seaking
p(0x0363B8, "Stari ")       # Staryu
p(0x0363BF, "Staross")      # Starmie
p(0x0363C7, "M. Mime")      # Mr. Mime
p(0x0363D7, "Lippoutou")    # Jynx
p(0x0363DC, "Élektek")      # Electabuzz
p(0x0363ED, "Scarabrute")   # Pinsir
p(0x0363FB, "Magicarpe")    # Magikarp
p(0x036404, "Léviator")     # Gyarados
p(0x03640D, "Lokhlass")     # Lapras
p(0x036414, "Métamorph")    # Ditto
p(0x03641A, "Évoli")        # Eevee
p(0x036420, "Aquali  ")     # Vaporeon
p(0x036429, "Voltali")      # Jolteon
p(0x036441, "Amonita")      # Omanyte
p(0x036449, "Amonistar")    # Omastar
p(0x036461, "Ptéra")        # Aerodactyl
p(0x03646C, "Ronflex")      # Snorlax
p(0x036474, "Artikodin")    # Articuno
p(0x03647D, "Électhor")     # Zapdos
p(0x036484, "Sulfura")      # Moltres
p(0x03648C, "Minidraco")    # Dratini
p(0x036494, "Draco    ")    # Dragonair
p(0x03649E, "Dracolosse")   # Dragonite

# ============================================================
# 70. DUPLICATE TM TABLE (0x031CB2–0x031DEA)
#     Deuxieme copie de TM 01-40 trouvee via le patch IPS EN
# ============================================================

p(0x031CB2, "CT 01 ")
p(0x031CBA, "CT 02 ")
p(0x031CC2, "CT 03 ")
p(0x031CCA, "CT 04 ")
p(0x031CD2, "CT 05 ")
p(0x031CDA, "CT 06 ")
p(0x031CE2, "CT 07 ")
p(0x031CEA, "CT 08 ")
p(0x031CF2, "CT 09 ")
p(0x031CFA, "CT 10 ")
p(0x031D02, "CT 11 ")
p(0x031D0A, "CT 12 ")
p(0x031D12, "CT 13 ")
p(0x031D1A, "CT 14 ")
p(0x031D22, "CT 15 ")
p(0x031D2A, "CT 16 ")
p(0x031D32, "CT 17 ")
p(0x031D3A, "CT 18 ")
p(0x031D42, "CT 19 ")
p(0x031D4A, "CT 20 ")
p(0x031D52, "CT 21 ")
p(0x031D5A, "CT 22 ")
p(0x031D62, "CT 23 ")
p(0x031D6A, "CT 24 ")
p(0x031D72, "CT 25 ")
p(0x031D7A, "CT 26 ")
p(0x031D82, "CT 27 ")
p(0x031D8A, "CT 28 ")
p(0x031D92, "CT 29 ")
p(0x031D9A, "CT 30 ")
p(0x031DA2, "CT 31 ")
p(0x031DAA, "CT 32 ")
p(0x031DB2, "CT 33 ")
p(0x031DBA, "CT 34 ")
p(0x031DC2, "CT 35 ")
p(0x031DCA, "CT 36 ")
p(0x031DD2, "CT 37 ")
p(0x031DDA, "CT 38 ")
p(0x031DE2, "CT 39 ")
p(0x031DEA, "CT 40 ")

# ============================================================
# 71. FIX 6: ENGLISH LEFTOVERS FOUND BY AUDIT
# ============================================================

p(0x03069F, "Att.")        # Attack
p(0x030775, "Vic!")        # Won!
p(0x0316E9, "Rien")        # None


# ============================================================
# 72. COMPLETE AUDIT: ASCII LABELS STILL IN ENGLISH
# ============================================================

# Battle, stats and shop.
p(0x0301EB, "Vas-y! ")      # Go!
p(0x0303A1, " Monte")       # Rose
p(0x030417, "Ouah! ")       # Wow!
p(0x030485, "Et...")        # And...
p(0x030611, "ObjClé")       # KeyItm
p(0x030621, "Préc.:")       # Acc.:
p(0x03062E, "Sauv. ")       # Wild
p(0x0306A6, "Défense")      # Defense
p(0x0306AF, "Atq.S")        # S.Atk
p(0x0306B5, "D.Sp")         # S.DE
p(0x0306BA, "Vit.")         # Speed
p(0x0307DA, "Envoi ")       # Send
p(0x0308E1, "Ach")          # Buy
p(0x0308E5, "Vnd")          # Sel

# Moves: full names wherever the display width allows them.
p(0x0310FB, "Flammèche")     # Ember
p(0x031313, "Purédpois")     # Smog
p(0x031318, "Acide")         # Acid
p(0x031344, "Toxik")         # Toxic
p(0x031428, "Psyko")         # Psychic
p(0x031441, "Hypnose")       # Hypnosis
p(0x03144F, "Téléport")      # Teleport
p(0x031462, "Hâte")          # Agility
p(0x03146A, "Léchouille")    # Lick
p(0x0315D0, "Armure")        # Harden

# Trainer classes and official names.
p(0x031C36, "Clément")       # Will
p(0x031C70, "Canon")         # Beauty
p(0x031C77, "Médium")        # Medium
p(0x031C7E, "Pokéfan=")       # Pok@Fan=
p(0x032161, "Skieuse")       # Skier
p(0x032167, "Surfer")        # Boarder, classe officielle Gen 2

# Item and Pokemon names that differ in French.
p(0x034969, "Super Potion\nreçue !", layout="dialogue_19_19")
p(
    0x033D5B,
    "MEWTWO : ...",
    layout="dialogue_19_19",
)
p(0x03627F, "Magnéti")       # Magnemite
p(0x036289, "Magnéton")      # Magneton
p(0x036314, "Électrode")     # Electrode

# Dialogue interjections and sound effects.
p(0x03B2D4, (
                (
                    "Tu veux voir de quoi je suis capable ?"
                )
            ), layout="dialogue_19_19")
p(0x03BD9E, "...", layout="dialogue_19_19")
p(0x03BFE7, "Maudissons-le ensemble...", layout="dialogue_19_19")
p(0x03C02D, (
                "Ouh...\n"
                "Un Spectre..."
            ), layout="dialogue_19_19")
p(0x03C04F, "Tu vas gagner ?", layout="dialogue_19_19")
p(0x03C1A2, "Hi hi... Hi hi...", layout="dialogue_19_19")
p(0x03CB5E, "Tu les trouves moches, peut-être ?", layout="dialogue_19_19")
p(0x03D72D, "Ma flamme est éteinte...", layout="dialogue_19_19")
p(0x03D7B3, "Même la Défense cède devant toi...", layout="dialogue_19_19")
p(0x03D8E0, (
                (
                    (
                        (
                            "Les pierres ?\n"
                            "Même pas peur !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x03DCE4, "Je crois que tu as compris !", layout="dialogue_19_19")

# Graphical move-table records. The repacked pipeline explicitly replaces
# these two-byte labels with the official French names.
p(0x031101, "Roue de Feu")        # Flame Wheel
p(0x031108, "Poing de Feu")       # Fire Punch
p(0x03110F, "Lance-Flamme")       # Flamethrower
p(0x031118, "Feu Sacré")          # Sacred Fire
p(0x03111F, "Déflagration")       # Fire Blast
p(0x031138, "Pistolet à O")       # Water Gun
p(0x031142, "Vibraqua")           # Water Pulse
p(0x031149, "Bulles d'O")         # Bubble Beam
p(0x031150, "Octazooka")          # Octazooka
p(0x03115A, "Pince-Masse")        # Crabhammer
p(0x031166, "Hydrocanon")         # Hydro Pump
p(0x031170, "Tourniquet")         # Water Sport
p(0x031186, "Éclair")             # Thunder Shock
p(0x03118F, "Onde de Choc")       # Shock Wave
p(0x03119C, "Poing-Éclair")       # Thunder Punch
p(0x0311A5, "Tonnerre")           # Thunderbolt
p(0x0311AE, "Élecanon")           # Zap Cannon
p(0x0311B5, "Électacle")          # Volt Tackle
p(0x0311C4, "Cage-Éclair")        # Thunder Wave
p(0x0311D4, "Méga-Sangsue")       # Mega Drain
p(0x0311DB, "Feuille Magik")      # Magical Leaf
p(0x0311E2, "Fouet Lianes")       # Vine Whip
p(0x0311EC, "Tranch'Herbe")       # Razor Leaf
p(0x0311F3, "Poing Dard")         # Needle Arm
p(0x0311FA, "Canon Graine")       # Seed Bomb
p(0x031204, "Lance-Soleil")       # Solar Beam
p(0x03120B, "Végé-Attaque")       # Frenzy Plant
p(0x031212, "Siffl'Herbe")        # Grass Whistle
p(0x03121B, "Poudre Dodo")        # Sleep Powder
p(0x03122A, "Para-Spore")         # Stun Spore
p(0x031231, "Poudreuse")          # Powder Snow
p(0x031241, "Brise Glacée")       # Arctic Breeze (custom move)
p(0x031248, "Poing-Glace")        # Ice Punch
p(0x031264, "Glaciation")         # Sheer Cold
p(0x031281, "Massd'Os")           # Bone Club
p(0x03128B, "Séisme")             # Earthquake
p(0x031292, "0000Osmerang")       # Bonemerang; pointer after padding
p(0x0312A9, "Jet de Sable")       # Sand Attack
p(0x0312B0, "Jet-Pierres")        # Rock Throw
p(0x0312B7, "Tomberoche")         # Rock Tomb
p(0x0312C1, "Pouvoir Antique")    # Ancient Power
p(0x0312CA, "Éboulement")         # Rock Slide
p(0x0312D1, "Vampirisme")         # Leech Life
p(0x0312D8, "Double-Dard")        # Twineedle
p(0x0312DF, "Vent Argenté")       # Silver Wind
p(0x0312E6, "Rayon Signal")       # Signal Beam
p(0x0312ED, "Mégacorne")          # Megahorn
p(0x0312F7, "Lumi-Queue")         # Tail Glow
p(0x031301, "Sécrétion")          # String Shot
p(0x031308, "0000Dard-Venin")     # Poison Sting; pointer after padding
p(0x03131D, "Queue-Poison")       # Poison Tail
p(0x031324, "Crochet Venin")      # Poison Fang
p(0x031332, "Bomb-Beurk")         # Sludge Bomb
p(0x031339, "0000Gaz Toxik")      # Poison Gas; pointer after padding
p(0x031353, "Éclate-Roc")         # Rock Smash
p(0x03135A, "Poing-Karaté")       # Karate Chop
p(0x031361, "Double Pied")        # Double Kick
p(0x031370, "Mawashi Geri")       # Rolling Kick
p(0x031379, "Corps Perdu")        # Vital Throw
p(0x031380, "Frappe Atlas")       # Seismic Toss
p(0x031389, "Casse-Brique")       # Brick Break
p(0x031390, "Stratopercut")       # Sky Uppercut
p(0x031399, "Coup-Croix")         # Cross Chop
p(0x0313A0, "Dynamopoing")        # Dynamic Punch
p(0x0313A9, "Poing Boost")        # Power-Up Punch
p(0x0313B2, "Mitra-Poing")        # Focus Punch
p(0x0313C3, "Tranch'Air")         # Air Cutter
p(0x0313CA, "Cru-Aile")           # Wing Attack
p(0x0313D1, "Aéropique")          # Aerial Ace
p(0x0313DC, "Bec Vrille")         # Drill Peck
p(0x0313EA, "Aéroblast")          # Aeroblast
p(0x0313F1, "Piqué")              # Sky Attack
p(0x0313F8, "Choc Mental")        # Confusion
p(0x03140B, "Ball'Brume")         # Mist Ball
p(0x031415, "Choc Psy")           # Psyshock
p(0x03141F, "Psykoud'Boul")       # Zen Headbutt
p(0x031430, "Dévorêve")           # Dream Eater
p(0x031437, "Psycho-Boost")       # Psycho Boost
p(0x031458, "Plénitude")          # Calm Mind
p(0x031478, "Poing Ombre")        # Shadow Punch
p(0x03147F, "Ball'Ombre")         # Shadow Ball
p(0x031486, "Griffe Ombre")       # Shadow Claw
p(0x03148D, "Onde Folie")         # Confuse Ray
p(0x03149E, "Draco-Rage")         # Dragon Rage
p(0x0314A5, "Dracosouffle")       # Dragon Breath
p(0x0314AC, "Draco-Griffe")       # Dragon Claw
p(0x0314B3, "Draco-Choc")         # Dragon Pulse
p(0x0314BA, "Danse Draco")        # Dragon Dance
p(0x0314C1, "Sabotage")           # Knock Off
p(0x0314CB, "Feinte")             # Feint Attack
p(0x0314DE, "Griffe Acier")       # Metal Claw
p(0x0314E5, "Aile d'Acier")       # Steel Wing
p(0x0314EC, "Queue de Fer")       # Iron Tail
p(0x0314F6, "Poing Météore")      # Meteor Mash
p(0x0314FD, "Mur de Fer")         # Iron Defense
p(0x03150D, "Tour Rapide")        # Rapid Spin
p(0x031529, "Vive-Attaque")       # Quick Attack
p(0x031551, "Éclate Griffe")      # Crush Claw
p(0x031558, "Puissance Cachée")   # Hidden Power
p(0x03155F, "Croc de Mort")       # Hyper Fang
p(0x031566, "Coupe-Vent")         # Razor Wind
p(0x03156D, "Damoclès")           # Double-Edge
p(0x031574, "Ultralaser")         # Hyper Beam
p(0x03157B, "Destruction")        # Self-Destruct
p(0x03158C, "Guillotine")         # Guillotine
p(0x031595, "Empal'Korne")        # Horn Drill
p(0x0315A1, "Grobisou")           # Lovely Kiss (Love Kiss in the bootleg)
p(0x0315AB, "Ultrason")           # Supersonic
p(0x0315B2, "Danse-Lames")        # Swords Dance
p(0x0315C7, "Boul'Armure")        # Defense Curl
p(0x0315D7, "Mimi-Queue")         # Tail Whip
p(0x0315E7, "Brouillard")         # Smokescreen
p(0x0315F4, "Reflet")             # Double Team
p(0x03160F, "Cyclone")            # Whirlwind
p(0x03163B, "Poudre Toxik")       # Poison Powder

# Graphical location names aligned with French Red/Blue.
p(0x03216F, "Plateau Indigo")     # Indigo Plateau
p(0x033095, "Bourg Palette")      # Pallet Town
p(0x0330A0, "Jadielle")           # Viridian City
p(0x0330AB, "Forêt de Jade")      # Viridian Forest
p(0x0330B6, "Argenta")            # Pewter City
p(0x0330CC, "Azuria")             # Cerulean City
p(0x0330D7, "Grotte")             # Rock Tunnel (nom Rouge/Bleu)
p(0x0330E2, "Lavanville")         # Lavender Town
p(0x0330ED, "Safrania")           # Saffron City
p(0x0330F8, "Céladopole")         # Celadon City
p(0x033102, "Carmin sur Mer")     # Vermilion City
p(0x03310D, "Parmanie")           # Fuchsia City
p(0x033118, "Cramois'Île")        # Cinnabar Island
p(0x033123, "Route Victoire")     # Victory Road

# Graphical system text and battle-effect messages.
p(0x0301C4, "(c) Nanjing - tous droits réservés.")
p(0x0301F0, "sauvage")
p(0x030381, "subit des dégâts du poison grave !")
p(0x030392, "a trop peur pour agir !")
p(0x0303C8, "a fortement baissé !")
p(0x0303E6, "Merci")
p(0x0303EB, "Merci")
p(0x0303F0, "Merci")
p(0x0303F6, "Merci")
p(0x0303FC, "Merci")
p(0x030458, "veut apprendre")
p(0x030467, "Oui / Non")

p(0x0304C2, "concentre la lumière du soleil !")
p(0x0304CF, "libère l'énergie solaire !")
p(0x0304DB, "s'enfouit sous terre !")
p(0x0304E7, "attaque rapidement !")
p(0x0304F1, "accumule de l'énergie !")
p(0x0304FB, "frappe de toutes ses forces !")
p(0x030505, "accumule de l'énergie !")
p(0x03050F, "frappe de toutes ses forces !")
p(0x030519, "cesse d'accumuler de l'énergie !")
p(0x030523, "s'envole haut dans le ciel !")
p(0x03052D, "frappe au péril de sa vie !")
p(0x030537, "concentre une force mystique !")
p(0x030541, "libère sa force mystique !")
p(0x03054B, "prévoit une attaque !")
p(0x030555, "subit l'attaque Prescience !")
p(0x030567, "dévore le rêve de")
p(0x03056F, " !")
p(0x030575, "entre en colère !")
p(0x03057D, "est maudit !")
p(0x03094A, "est maudit !")

p(0x0306D7, "ne peut pas agir !")
p(0x0306E1, "K.O. en un coup !")
p(0x0306EC, "s'est enfui !")
p(0x0306F5, "ne peut pas fuir !")
p(0x0306FE, "n'est plus empoisonné !")
p(0x030714, "n'est plus paralysé !")
p(0x030720, "n'est plus brûlé !")
p(0x030738, "n'est plus gelé !")
p(0x030744, "n'est plus gravement empoisonné !")
p(0x030750, "n'a plus peur !")
p(0x03077A, "Requis :")
p(0x030782, "Badge Cascade")
p(0x03078C, "Badge Foudre")
p(0x030796, "Badge Âme")
p(0x0307A0, "Badge Prisme")
p(0x0307AA, "Badge Roche")
p(0x0307B9, "ne peut pas être empoisonné !")
p(0x0307C4, "ne peut pas être brûlé !")
p(0x0307CF, "ne peut pas être gelé !")

# Graphical field-move list labels.
p(0x031C87, "CS Coupe")
p(0x031C91, "CS Vol")
p(0x031C99, "CS Surf")
p(0x031CA1, "CS Force")
p(0x031CA9, "CS Flash")

# Graphical League and post-game dialogue (records 204 through 220).
p(0x03329F,
  "RÉGIS : Tiens,\n"
  "Sacha !\n"
  "Quelle surprise !\n"
  "Tu vas à la Ligue ?\n"
  "Tous tes Badges !\n"
  "Pas mal ! Bats-moi.",
  layout="dialogue_19_19")
p(0x03331B,
  "RÉGIS : Zut !\n"
  "J'étais distrait.\n"
  "À ce niveau, jamais\n"
  "tu ne gagneras\n"
  "la Ligue.\n"
  "Entraîne-toi !\n"
  "Je trace. À plus !",
  layout="dialogue_19_19")
p(0x033395,
  "GARDE : Oh !\n"
  "Tes Badges de Ligue\n"
  "sont authentiques !\n"
  "Tu peux passer !",
  layout="dialogue_19_19")
p(
    0x033CF0,
    "ARBITRE :\nDésolé.\nOlga est absente,\nalors la Ligue\nsuspend les défis.\nElle enquête\nà Azuria...",
    layout="dialogue_19_19",
)
p(0x033F45,
  "OLGA : Bienvenue !\n"
  "Je zuis OLGA,\n"
  "du Conzeil des 4 !\n"
  "Ma glaze va figer\n"
  "toute ton équipe !\n"
  "Ach ! Z'est parti !",
  layout="dialogue_19_19")
p(0x033FC5,
  "OLGA : Tu es fort.\n"
  "Z'est bien.\n"
  "J'ai perdu.\n"
  "Passe à la suite !",
  layout="dialogue_19_19")
p(0x033FFF,
  "ALDO : Je suis ALDO\n"
  "du Conseil des 4 !\n"
  "Mes Pokémon et moi,\n"
  "on adore la muscu !\n"
  "Sacha, en garde !\n"
  "À table !",
  layout="dialogue_19_19")
p(0x03407F,
  "ALDO : Perdu...\n"
  "Bien joué !\n"
  "La suite t'attend.",
  layout="dialogue_19_19")
p(0x0340C1,
  "AGATHA :\n"
  "Conseil des 4 !\n"
  "CHEN mise sur toi.\n"
  "Ce vieux machin\n"
  "était fort et beau.\n"
  "Mais le Pokédex\n"
  "ne suffit pas :\n"
  "les Pokémon\n"
  "servent au combat !\n"
  "Montre-moi\n"
  "ce que tu vaux !",
  layout="dialogue_19_19")
p(0x034169,
  "PETER :\n"
  "Je dirige\n"
  "le Conseil des 4 !\n"
  "Les dragons sont\n"
  "des êtres sacrés.\n"
  "Durs à capturer,\n"
  "ils sont presque\n"
  "invincibles !\n"
  "Le glas sonne...\n"
  "Tu vas perdre !",
  layout="dialogue_19_19")
p(0x034207,
  "PETER : Bien joué !\n"
  "Mais pour être\n"
  "le vrai Champion,\n"
  "bats le Dresseur\n"
  "qui nous a vaincus.\n"
  "Il t'attend\n"
  "dans la salle\n"
  "suivante !",
  layout="dialogue_19_19")
p(0x03447C,
  "PROF. CHEN : Bravo,\n"
  "Sacha !\n"
  "Avec Pikachu,\n"
  "tu as tant grandi !\n"
  "Grâce au lien noué\n"
  "avec tes Pokémon,\n"
  "tu as gagné !\n"
  "Suis-moi !",
  layout="dialogue_19_19")
p(0x03456E,
  "PROF. CHEN : Bravo,\n"
  "Sacha !\n"
  "Te voilà Champion\n"
  "de la Ligue !\n"
  "Notons vos noms.\n"
  "Puis rentrons :\n"
  "ta mère t'attend.",
  layout="dialogue_19_19")
p(0x0345E4,
  "MAMAN : Kameiyu, chez Nanjing Tech à Céladopole, aurait des Pokémon invaincus. Tu vas le défier ? Prudence...",
  layout="dialogue_19_19")
p(0x034656,
  "KAMEYU : Sacha, je savais que tu viendrais ! Prêt ?",
  layout="raw")
p(
    0x0347CB,
    "MAMAN :\nTu as terminé\nle Pokédex ?",
    layout="dialogue_19_19",
)
p(0x034953, "Master Ball reçue !", layout="dialogue_19_19")
p(0x034981, "Potion Max reçue !", layout="dialogue_19_19")
p(0x0349BF, "Anti-Brûle reçu !", layout="dialogue_19_19")
p(0x0349E5, "PP Plus reçu !", layout="dialogue_19_19")
p(0x0349F2, "PP Max reçu !", layout="dialogue_19_19")
p(0x034A49, "Colis Chen reçu !",
  layout="dialogue_19_19")
p(0x034A52, "Pokédex reçu !", layout="dialogue_19_19")
p(0x034A60, "Carte reçue !", layout="dialogue_19_19")
p(0x034A6A, "Nautile reçu !",
  layout="dialogue_19_19")
p(0x034A78, "Fossile Dôme reçu !", layout="dialogue_19_19")
p(0x034A86, "Passe Bateau reçu !", layout="dialogue_19_19")
p(0x034A90, "Eau Fraîche reçue !", layout="dialogue_19_19")
p(0x034A9C, "Scope Sylphe reçu !", layout="dialogue_19_19")
p(0x034AAA, "Poké Flûte reçue !", layout="dialogue_19_19")
p(0x034AB6, "Dent d'Or reçue !", layout="dialogue_19_19")
p(0x034AC0, "Ticket Mystik\nreçu !", layout="dialogue_19_19")
p(0x034ACE, "CS01 : Coupe !", layout="dialogue_19_19")
p(0x034ADA, "CS02 : Vol !", layout="dialogue_19_19")
p(0x034C03, "Bienvenue !", layout="dialogue_19_19")
p(0x034C09,
  "Bienvenue !\n"
  "Au Centre Pokémon,\n"
  "nous soignons tous\n"
  "les Pokémon !",
  layout="dialogue_19_19")
p(0x034C2D,
  "Merci !\n"
  "Toute ton équipe\n"
  "a la super pêche !\n"
  "À bientôt !",
  layout="dialogue_19_19")
p(0x034C4B,
  "Désolé, les combats\n"
  "ne sont pas encore\n"
  "disponibles ici...",
  layout="dialogue_19_19")
p(0x034C75,
  "La machine de Troc\n"
  "est aussi en panne.\n"
  "Reviens plus tard.",
  layout="dialogue_19_19")
p(0x034C96, "Salut !\nJe peux t'aider ?",
  layout="dialogue_19_19")
p(0x034CA6, "Merci !\nÀ bientôt !", layout="dialogue_19_19")
p(
    0x034E55,
    "Rattata est petit,\nmais ses crocs\nsont redoutables !",
    layout="dialogue_19_19",
)
p(
    0x034E6D,
    "La Forêt de Jade\nest un vrai\nlabyrinthe.\nSois prudent !",
    layout="dialogue_19_19",
)
p(
    0x034EB8,
    "Certains Pokémon\nvivent seulement\ndans les forêts\nou les grottes.\nExplore partout\npour les trouver !",
    layout="dialogue_19_19",
)
p(0x034EEF,
  "Cette grotte est\n"
  "très sombre.\n"
  "Avec Flash,\n"
  "un Pokémon peut\n"
  "l'éclairer.",
  layout="dialogue_19_19")
p(0x034FE0, "À bientôt !", layout="dialogue_19_19")
p(0x035077,
  (
      (
          "Ces pauvres gens\n"
          "ont été volés.\n"
          "L'odieuse\n"
          "Team Rocket\n"
          "est derrière tout\n"
          "ça. Même la police\n"
          "a du mal à lutter !"
      )
  ),
  layout="dialogue_19_19")
p(
    0x035122,
    "Mon vélo est magnifique !",
    layout="dialogue_19_19",
)
p(
    0x035188,
    "Pff... Rien de neuf\nces temps-ci...",
    layout="dialogue_19_19",
)
p(0x0351AC,
  (
      (
          "Je n'arrive pas\n"
          "à bien élever\n"
          "mon Bulbizarre..."
      )
  ),
  layout="dialogue_19_19")
p(
    0x0351CB,
    "Fais évoluer\ntes Pokémon :\nle Pokédex avance !",
    layout="dialogue_19_19",
)
p(
    0x0351E6,
    "Des Pokémon Spectre\nseraient apparus\nà Lavanville...",
    layout="dialogue_19_19",
)
p(
    0x0352CE,
    "La Tour Pokémon\nabrite beaucoup\nde Spectres.",
    layout="dialogue_19_19",
)
p(0x0352E4,
  (
      (
          "Ici reposent\n"
          "les Pokémon.\n"
          "La Tour est un lieu\n"
          "de recueillement."
      )
  ),
  layout="dialogue_19_19")
p(
    0x035335,
    "M. Fuji peut\napaiser l'âme\nd'Osselait.",
    layout="dialogue_19_19",
)
p(0x0354AB,
  "Échange tes jetons\n"
  "contre des Pokémon.\n"
  "Sans Boîte Jeton,\n"
  "impossible !",
  layout="dialogue_19_19")
p(0x035539, "Quel bel endroit !", layout="dialogue_19_19")
p(0x0358D2,
  (
      (
          "Selon le Dresseur, les Pokémon servent le bien ou le mal !"
      )
  ),
  layout="dialogue_19_19")
p(
    0x0359B7,
    "Un Pokémon surgit\nparfois des herbes,\nsans prévenir.",
    layout="dialogue_19_19",
)
p(
    0x0359DE,
    "Dans les grandes\nvilles, tu verras\nd'excellents\nDresseurs.",
    layout="dialogue_19_19",
)
p(
    0x035A02,
    "Tu es déjà allé\nà Safrania ?\nSes immeubles\nseraient immenses !",
    layout="dialogue_19_19",
)
p(
    0x035A27,
    "J'aimerais avoir\nun Pokémon\nlégendaire...\nOù en trouver ?",
    layout="dialogue_19_19",
)
p(0x035A5F,
  (
      (
          "Tu débutes, non ?\n"
          "Surveille toujours\n"
          "l'état de l'équipe."
      )
  ),
  layout="dialogue_19_19")
p(
    0x035A9F,
    "Grâce à Vol,\nun Pokémon t'emmène\nau loin.",
    layout="dialogue_19_19",
)
p(
    0x035ACA,
    "Il fait beau\naujourd'hui !",
    layout="dialogue_19_19",
)
p(0x035ADA, (
                (
                    "Je suis ravie !\n"
                    "Entre nous...\n"
                    "je suis amoureuse !"
                )
            ), layout="dialogue_19_19")
p(
    0x035AF8,
    "La mer est immense.\nAvec Surf,\ntraverse-la !",
    layout="dialogue_19_19",
)
p(
    0x035B25,
    "Tu connais\nl'Océane,\nà Carmin sur Mer ?\nCe paquebot de luxe\naccueille de riches\nDresseurs.",
    layout="dialogue_19_19",
)
p(0x035B58,
  (
      (
          "La nuit,\n"
          "on peut parfois\n"
          "voir des Mélofée\n"
          "au Mont Sélénite."
      )
  ),
  layout="dialogue_19_19")
p(
    0x035B7C,
    (
        "Tu connais Hoenn ?\n"
        "Je m'y entraînais\n"
        "dans ma jeunesse."
    ),
    layout="dialogue_19_19",
)
p(
    0x035BAB,
    "Quand un Pokémon\na peu de PV,\nutilise vite\nune Potion !",
    layout="dialogue_19_19",
)
p(0x035BCF,
  (
      (
          "Je ne sais pas\n"
          "bien m'occuper\n"
          "des Pokémon.\n"
          "Il me reste tant\n"
          "à apprendre !"
      )
  ),
  layout="dialogue_19_19")
p(0x035C0B,
  (
      (
          (
              "Le Conseil des 4\n"
              "réunit l'élite\n"
              "des Dresseurs\n"
              "de la région.\n"
              "Il siège\n"
              "au Plateau Indigo."
          )
      )
  ),
  layout="dialogue_19_19")
p(0x035C67, (
                (
                    (
                        "J'ai soif...\n"
                        "Qui a de l'eau\n"
                        "pour moi ?"
                    )
                )
            ), layout="dialogue_19_19")
p(0x035C87,
  (
      (
          (
              "Ne bouge pas !\n"
              "Je l'ai déjà dit...\n"
              "Tu bouges encore ?!"
          )
      )
  ),
  layout="dialogue_19_19")
p(0x035C9D,
  (
      "À te voir,\n"
      "tu dois être\n"
      "un sacré Dresseur !"
  ),
  layout="dialogue_19_19")

# Graphical system text and late dialogue still in Chinese/English.
p(0x03805C, "NANJING TECH. TOUS DROITS RÉSERVÉS.",
  layout="dialogue_19_19")
p(0x0380DD, (
                (
                    (
                        (
                            "Un combat suffit :\n"
                            "nous voilà amis !"
                        )
                    )
                )
            ), layout="dialogue_19_19")
p(0x0381A5, "Pas assez d'argent !", layout="dialogue_19_19")
p(0x0381E0, (
                (
                    "Sacha utilise Vol !"
                )
            ),
  layout="dialogue_19_19")
p(0x0381F6, (
                (
                    "Sacha utilise Surf !"
                )
            ),
  layout="dialogue_19_19")
p(0x038208, (
                (
                    "Sacha utilise Force !"
                )
            ),
  layout="dialogue_19_19")
p(0x03821A, (
                (
                    "On peut sans doute\n"
                    "pousser ce rocher."
                )
            ),
  layout="dialogue_19_19")

p(0x038862,
  "Attends un peu. Écoute-moi.",
  layout="dialogue_19_19")
p(0x038880, (
                (
                    (
                        (
                            "Tu veux quand même\n"
                            "y aller ?"
                        )
                    )
                )
            ),
  layout="dialogue_19_19")
p(0x038D23,
  (
      (
          (
              "De grands Dresseurs t'attendent. Sans Badge, passage interdit."
          )
      )
  ),
  layout="dialogue_19_19")

p(0x039D3B, "Prends-en soin !", layout="raw")
p(0x039D60, "Aide Salamèche !", layout="raw")

p(0x03A7BD, "Je voyagerai l'an prochain.",
  layout="dialogue_19_19")
p(0x03A7D8, (
                (
                    (
                        "Je suis trop vieux pour marcher loin."
                    )
                )
            ),
  layout="dialogue_19_19")
p(0x03A7F4, (
                (
                    "Ne traîne pas ici, gamin !"
                )
            ),
  layout="dialogue_19_19")
p(0x03A807, (
                (
                    "J'avais tort. Visite à ta guise."
                )
            ),
  layout="dialogue_19_19")
p(0x03A8BE, "Va-t'en, vite !", layout="dialogue_19_19")
p(0x03A8D2, "J'ai parlé, là ?",
  layout="dialogue_19_19")
p(0x03A8E8,
  (
      (
          (
              (
                  (
                      'Ma fille a ton âge.'
                  )
              )
          )
      )
  ),
  layout="dialogue_19_19")
p(0x03A907, (
                (
                    (
                        "Épouse ma fille !"
                    )
                )
            ),
  layout="dialogue_19_19")
p(0x03AE51, "...", layout="dialogue_19_19")

p(0x03B3DF, "Tu as réussi\nà trouver\ncet endroit ?", layout="dialogue_19_19")
p(0x03B3EB, "On raconte qu'un Pokémon légendaire est apparu par ici. Je suis venue voir.",
  layout="dialogue_19_19")
p(0x03B7F5,
  (
      "La mère d'Osselait\n"
      "fuyait. J'ai vu\n"
      "la Team Rocket\n"
      "la tuer !"
  ),
  layout="dialogue_19_19")

p(0x03C0D6,
  (
      (
          (
              (
                  (
                      (
                          "Je garde\n"
                          "cette affiche. Si\n"
                          "tu me gênes, tu vas\n"
                          "le regretter !"
                      )
                  )
              )
          )
      )
  ),
  layout="dialogue_19_19")
p(0x03C114,
  (
      "Not' cachette va\n"
      "être découverte !\n"
      "J'va prév'nir eul\n"
      "chef !"
  ),
  layout="dialogue_19_19")

p(0x03C18E, "Quelle tristesse...", layout="dialogue_19_19")

p(
    0x03D16B,
    "ORNITHOLOGUE : Avec mes attaques en rafale, tu n'as aucune chance !",
    layout="dialogue_19_19",
)
p(
    0x03D191,
    "ORNITHOLOGUE : J'ai encore parlé trop vite...",
    layout="dialogue_19_19",
)
p(0x03D827, (
                "TEAM ROCKET :\n"
                "Dégage, morveux !"
            ),
  layout="dialogue_19_19")

p(0x03DF0D,
  "Salut ! Je suis scientifique. J'étudie les fossiles de "
  "Pokémon rares. Tu en as un pour moi ?",
  layout="raw")
p(0x03DF7B, "Dommage !")

p(0x03E777,
  (
      (
          (
              "Ici, les gamins sont interdits !"
          )
      )
  ),
  layout="dialogue_19_19")
p(0x03E797,
  "Cramois'Île n'est plus très loin.",
  layout="dialogue_19_19")
p(0x03E82C,
  (
      (
          (
              (
                  "Le volcan entre souvent en éruption à Cramois'Île."
              )
          )
      )
  ),
  layout="dialogue_19_19")
p(0x03E853, "Ici, on étudie\nchaque jour\nles Pokémon.", layout="dialogue_19_19")
p(0x03E874,
  (
      (
          "Ce fossile trouvé\n"
          "au Mont Sélénite\n"
          "semble précieux !"
      )
  ),
  layout="dialogue_19_19")
p(0x03EB91, (
                (
                    "Même le type Feu a ses faiblesses..."
                )
            ),
  layout="dialogue_19_19")
p(0x03EC21,
  (
      (
          "Le Feu craint l'Eau et domine la Glace."
      )
  ),
  layout="dialogue_19_19")
p(0x03ECFD,
  (
      "Futur Champion ! Même moi, j'ignore qui est le Champion à Jadielle..."
  ),
  layout="dialogue_19_19")


# ############################################################
# ############################################################
# ##                                                        ##
# ##          END OF TRANSLATION CORPUS                    ##
# ##                                                        ##
# ############################################################
# ############################################################


# ============================================================
# OUTPUT FILES (do not edit)
# ============================================================

# Write the translated ROM
with open(ROM_OUTPUT, 'wb') as f:
    f.write(rom)

# Create the IPS patch
ips = bytearray(b'PATCH')
i = 0
while i < len(orig):
    while i < len(orig) and orig[i] == rom[i]:
        i += 1
    if i >= len(orig):
        break
    start = i
    while i < len(orig) and orig[i] != rom[i]:
        i += 1
    length = i - start
    d = bytes(rom[start:start+length])
    off = start
    while length > 0:
        chunk = min(length, 65535)
        ips.append((off >> 16) & 0xFF)
        ips.append((off >> 8) & 0xFF)
        ips.append(off & 0xFF)
        ips.append((chunk >> 8) & 0xFF)
        ips.append(chunk & 0xFF)
        ips.extend(d[:chunk])
        d = d[chunk:]
        off += chunk
        length -= chunk
ips.extend(b'EOF')

with open(IPS_OUTPUT, 'wb') as f:
    f.write(ips)

# ============================================================
# REPORT
# ============================================================

changes = sum(1 for a, b in zip(orig, rom) if a != b)

print(f"{'='*50}")
print(f"  POKEMON JAUNE - TRADUCTION FR")
print(f"{'='*50}")
print(f"Patches appliques: {patch_count}")
print(f"Octets modifies:   {changes}")
print(f"ROM:  {ROM_OUTPUT}")
print(f"IPS:  {IPS_OUTPUT} ({len(ips)} octets)")
print(f"Header iNES: {'OK' if rom[:4] == b'NES' + bytes([0x1a]) else 'ERREUR!'}")

if warnings:
    print(f"\nATTENTION ({len(warnings)} avertissements):")
    for w in warnings[:20]:
        print(f"  {w}")
    if len(warnings) > 20:
        print(f"  ... et {len(warnings)-20} de plus")

print(f"\nTermine!")
