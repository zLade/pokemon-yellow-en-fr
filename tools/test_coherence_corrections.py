#!/usr/bin/env python3
"""Regressions for the reviewed Gen 1/2 French coherence corrections."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rom_traduction_assistant import parse_patch_entries
from tools.dialogue_layout import DIALOGUE_LAYOUT, POKEDEX_LAYOUT


CHINESE_FIDELITY_TEXTS = {
    int(offset, 0): text
    for offset, text in json.loads(
        (
            Path(__file__).resolve().parent
            / "data"
            / "chinese_fidelity_dialogue_overrides.json"
        ).read_text(encoding="utf-8")
    ).items()
}

FRENCH_NATURALIZATION_TEXTS = {
    int(offset, 0): text
    for offset, text in json.loads(
        (
            Path(__file__).resolve().parent
            / "data"
            / "french_naturalization_overrides.json"
        ).read_text(encoding="utf-8")
    ).items()
}


EXPECTED_TEXTS = {
    0x0317B9: "Nautile",
    0x031BAB: "000Colis Chen",
    0x032301: "Il rase l'eau pour chasser un Magicarpe.",
    0x033436: "Le Conseil des 4 vient ensuite !",
    0x03365E: (
        "Je suis Aldo du Conseil des 4 ! Grâce à un entraînement "
        "rigoureux, humains et Pokémon deviennent plus forts ! Sacha, "
        "nous allons t'écraser par notre force !"
    ),
    0x033715: (
        "Je suis Agatha du Conseil des 4! Chen s'intéresse à toi! "
        "Ce vieux fou était fort et beau! Maintenant il veut juste jouer "
        "avec son Pokédex! Il a tort! Les Pokémon sont faits pour "
        "combattre ! Sacha! Je vais te montrer comment un vrai "
        "dresseur combat!"
    ),
    0x0338F4: (
        "Je n'arrive pas à croire que mes dragons aient perdu ! Tu es "
        "le Champion de la Ligue! ...ou tu l'aurais été. Un autre "
        "dresseur nommé Régis a battu le Conseil des 4 avant toi! "
        "C'est lui le vrai Champion!"
    ),
    0x033BFE: (
        "Félicitations Sacha ! Voici l'étage des célébrités Pokémon ! "
        "Les Champions de la Ligue et leurs Pokémon y sont consacrés. "
        "Bravo : toi et tes Pokémon êtes célèbres !"
    ),
    0x034A49: "Colis Chen obtenu !",
    0x034A6A: "Nautile obtenu !",
    0x035638: "Entraîne tes Pokémon au même rythme.",
    0x035780: "Évoli peut évoluer en l'un de trois Pokémon.",
    0x0364F0: "Util. Potion Max !",
    0x0365FE: (
        "Sacha, si tu pousses trop tes Pokémon, ils finiront par ne "
        "plus t'aimer. Tu devrais faire une pause !"
    ),
    0x03675E: "J'aime trouver des surnoms à mes Pokémon !",
    0x0386A2: (
        "Chen : Mais je... Bon, d'accord. Ce Pokémon est à toi. "
        "J'allais t'en donner un de toute façon. Sacha, viens ici !"
    ),
    0x0389B4: (
        "Sacha, désolé, mais je n'ai pas besoin de toi ! Je sais : "
        "j'emprunterai une Carte à ma soeur et je lui dirai de ne "
        "pas t'en prêter ! Hahaha !"
    ),
    0x03900E: (
        "Tu sembles très doué comme Dresseur ! Va tester ta force "
        "à l'Arène d'Azuria !"
    ),
    0x0395E5: (
        "Alors celui-ci est à moi ! À Cramois'Île, un laboratoire "
        "étudie comment ressusciter les Pokémon fossilisés !"
    ),
    0x0396E6: "Jessie : Un morveux nous a battus ?",
    0x0397E8: (
        "Hé, Champion ! Ondine est une experte des Pokémon Eau. "
        "Électrocute-les ou utilise des Pokémon Plante !"
    ),
    0x0398D1: (
        "Ondine : Les Dresseurs pros ont chacun leur stratégie. "
        "La mienne, c'est l'offensive totale ! Et la tienne ?"
    ),
    0x03A127: "Je retourne en Forêt de Jade.",
    0x03A504: "Beurk ! J'ai le mal de mer !",
    0x03B329: "Les gens paient cher les crânes d'Osselait.",
    0x03B34F: (
        "J'ai vu la mère d'Osselait mourir en fuyant la Team Rocket !"
    ),
    0x03B516: (
        "Ton Pokédex, ça va ? Je viens de capturer un Osselait ! "
        "Bon, je dois filer : j'ai beaucoup à faire. À plus !"
    ),
    0x03C21F: (
        "Le fantôme était l'âme tourmentée de la mère d'Osselait ! "
        "Apaisée, elle est partie dans l'au-delà."
    ),
    0x03C370: (
        "Fuji : Hein ? Tu es venu me sauver ? Merci. Je suis venu "
        "apaiser l'âme de la mère d'Osselait. Je crois que son esprit "
        "repose en paix. Je dois te remercier. Suis-moi chez moi."
    ),
    0x03D10F: "Tu utilises des CT ?",
    0x03D12B: "J'utilise des CT que j'ai achetées !",
    0x03D31C: "J'aime les techniques de poison et de sommeil.",
    0x03D341: "J'ai rejoint cette Arène pour devenir ninja !",
    0x03DBE1: (
        "J'ai eu la vision de ton arrivée ! Je n'aime pas combattre, "
        "mais je vais te montrer mes pouvoirs !"
    ),
    0x03E1BB: (
        "Hé, Champion ! Auguste est un pro des Pokémon Feu ! "
        "Refroidis ses ardeurs avec des attaques Eau !"
    ),
    0x03E259: "Je vais gagner : j'ai beaucoup étudié !",
    0x03E777: (
        "MEW a donné naissance à un petit. Nous l'avons baptisé MEWTWO."
    ),
    0x03EAB4: (
        "Jessie : Halte, morveux ! On ne peut pas laisser la Team "
        "Rocket perdre ainsi ! James : Tu nous as bien embêtés, mais "
        "la Team Rocket ne sera jamais vaincue ! Miaouss : Miaouss ! "
        "On va te montrer qui commande !"
    ),
    0x03EC46: (
        "James : Je n'arrive pas à y croire ! La Team Rocket battue "
        "par ce morveux ! Jessie : Tu as peut-être gagné cette fois, "
        "mais on reviendra ! Miaouss : Miaouss ! Tu n'as pas fini "
        "d'entendre parler de nous !"
    ),
    0x03F5A3: (
        "Vieil homme : Aïe ! Fille : Désolée, mon grand-père s'est "
        "blessé au dos et ne peut plus bouger."
    ),
}

# Final page-oriented editorial pass.  These remain exact semantic snapshots;
# renderer newlines are compared separately from the wording.
FINAL_EDITORIAL_TEXTS = {
    0x03365E: (
        "Je suis Aldo du Conseil des 4 ! Grâce à un travail rigoureux, "
        "humains et Pokémon gagnent en force ! Sacha, sois prêt ! "
        "On va t'écraser !"
    ),
    0x033715: (
        "Je suis Agatha du Conseil des 4 ! Chen s'intéresse beaucoup "
        "à toi ! Ce vieux fou était fort et beau. Il veut juste jouer "
        "avec son Pokédex ! Il a tort ! Les Pokémon servent à "
        "combattre ! Sacha, regarde donc un vrai Dresseur combattre !"
    ),
    0x0338F4: (
        "Je n'arrive pas à le croire ! Mes dragons ont perdu ! Tu es "
        "le Champion de la Ligue ! Enfin, presque. Un autre Dresseur "
        "nommé Régis a battu le Conseil des 4 avant toi ! C'est lui, "
        "le vrai Champion !"
    ),
    0x033BFE: (
        "Bravo, Sacha ! Voici l'étage des célébrités Pokémon ! Ici, "
        "la Ligue consacre ensemble tous ses Champions et leurs "
        "Pokémon. Toi et tes Pokémon êtes célèbres !"
    ),
    0x0386A2: (
        "Chen : Mais je... Bon, d'accord. Ce Pokémon est pour toi. "
        "Il t'était destiné. Viens ici, Sacha !"
    ),
    0x0389B4: (
        "Sacha, désolé ! Je n'ai nul besoin de toi ! Je sais : "
        "j'emprunterai la Carte à ma sœur puis je lui dirai : "
        "Sacha n'aura rien ! Hahaha !"
    ),
    0x03900E: (
        "Tu sembles être un Dresseur doué ! Va donc tester ta force "
        "à l'Arène d'Azuria !"
    ),
    0x0395E5: (
        "Il est à moi ! À Cramois'Île, un laboratoire étudie comment "
        "ressusciter les Pokémon fossilisés !"
    ),
    0x0397E8: (
        "Hé, Champion ! Ondine est experte en Pokémon Eau. "
        "Électrocute-les ! Ou utilise des Pokémon de type Plante !"
    ),
    0x03B34F: (
        "J'ai vu la mère d'Osselait mourir dans sa fuite face à la "
        "Team Rocket !"
    ),
    0x03C370: (
        "Fuji : Hein ? Tu es venu me sauver ? Merci. Je suis venu "
        "apaiser l'âme de la mère d'Osselait. Son esprit semble "
        "reposer en paix. Suis-moi chez moi."
    ),
    0x03D341: "Je veux être ninja. L'Arène m'aidera.",
    0x03DBE1: (
        "J'ai eu la vision de ton arrivée ! Je n'aime pas combattre. "
        "Mais tu vas voir mes pouvoirs !"
    ),
    0x03E1BB: (
        "Hé, Champion ! Auguste maîtrise les Pokémon Feu ! Calme ses "
        "ardeurs avec des attaques d'Eau !"
    ),
    0x03E777: (
        "MEW a donné vie à un petit. Nous l'avons nommé MEWTWO."
    ),
    0x03EAB4: (
        "Jessie : Halte, morveux ! On ne peut laisser la Team Rocket "
        "perdre ainsi ! James : Tu nous as bien embêtés. Mais la Team "
        "Rocket reste invincible ! Miaouss : Miaouss ! On va te "
        "montrer qui commande !"
    ),
    0x03EC46: (
        "James : Incroyable ! La Team Rocket perd face à ce morveux ! "
        "Jessie : Tu gagnes cette fois. Mais on reviendra ! Miaouss : "
        "Miaouss ! Tu entendras encore parler de nous !"
    ),
}

FIXED_LAYOUT_OFFSETS = {
    0x0317B9,
    0x031BAB,
    0x0364F0,
}

POKEDEX_LAYOUT_OFFSETS = {
    0x032301,
}


class CoherenceCorrectionsTests(unittest.TestCase):
    def test_all_reviewed_texts_are_exact_in_script(self) -> None:
        entries = {
            entry.offset: entry
            for entry in parse_patch_entries(
                apply_dialogue_inventory=False,
            )
        }
        self.assertEqual(len(EXPECTED_TEXTS), 40)
        for offset, expected in EXPECTED_TEXTS.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertIn(offset, entries)
                expected = FRENCH_NATURALIZATION_TEXTS.get(
                    offset,
                    CHINESE_FIDELITY_TEXTS.get(
                        offset,
                        FINAL_EDITORIAL_TEXTS.get(offset, expected),
                    ),
                )
                # Explicit newlines are renderer page controls.  Semantic
                # coherence is checked here; their exact page placement is
                # covered by the dialogue-layout/page-quality regressions.
                self.assertEqual(
                    " ".join(entries[offset].text.split()),
                    " ".join(expected.split()),
                )

    def test_reviewed_layouts_are_explicit_and_not_overridden(self) -> None:
        raw_entries = {
            entry.offset: entry
            for entry in parse_patch_entries(
                apply_dialogue_inventory=False,
            )
        }
        migrated_entries = {
            entry.offset: entry
            for entry in parse_patch_entries()
        }
        for offset in EXPECTED_TEXTS:
            with self.subTest(offset=f"0x{offset:06X}"):
                if offset in FIXED_LAYOUT_OFFSETS:
                    expected_layout = ""
                elif offset in POKEDEX_LAYOUT_OFFSETS:
                    expected_layout = POKEDEX_LAYOUT
                else:
                    expected_layout = DIALOGUE_LAYOUT
                self.assertEqual(raw_entries[offset].layout, expected_layout)
                self.assertEqual(
                    migrated_entries[offset],
                    raw_entries[offset],
                )


if __name__ == "__main__":
    unittest.main()
