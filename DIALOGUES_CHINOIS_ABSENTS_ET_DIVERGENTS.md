# Dialogues chinois absents ou très divergents

> **État actuel : corrigé.** Ce document conserve l'audit historique qui a
> permis d'identifier les pertes de la traduction anglaise. Les 80 pointeurs
> supprimés, les 4 pointeurs erronés et le message Anti-Para mutualisé ont
> maintenant été restaurés, soit 85 restaurations. Les divergences recensées
> ont été retraduites depuis le chinois. La release actuelle est
> `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b` ;
> son bilan final et les hashes des patchs sont dans
> `CORRECTIONS_FIDELITE_CHINOISE.md`.

Le contrôle final reconstruit temporairement les 12 dérivés dépendant du
français et les compare octet par octet aux fichiers publiés. Il confirme le
bilan 80 suppressions anglaises restaurées sur 80, zéro réplique encore
absente, 85 restaurations au total et 17 caméos. Ce rafraîchissement utilise
les extractions Unicode immuables ; HZK16 n'a pas été réextrait
(`derived_refresh_without_hzk_reextraction`).

## Résultat

Constat historique effectué contre l'ancienne ROM française
`Pokemon_Jaune_FR_repacked_title.nes`
(SHA-256
`22210785ca066222b47cb255c5beeeeff7f0276439e57d65ff884c9bc9cd6298`).

- **80 répliques chinoises étaient absentes de l'anglais et du français.**
  Leurs pointeurs chinois ont été remplacés par des valeurs invalides dans la
  ROM anglaise et n'avaient pas été restaurés dans cette ancienne ROM
  française. Ils le sont dans la release actuelle.
- **110 autres dialogues n'étaient pas traduits dans la ROM anglaise** et y
  restaient sous forme de codes graphiques. Ils possédaient déjà une
  traduction française manuelle et ont été revérifiés depuis la source
  chinoise.
- **56 divergences sémantiques majeures** ont été retenues dans une liste
  conservatrice historique. Elles sont corrigées dans la release actuelle ;
  les simples abréviations ou adaptations stylistiques ne figuraient pas dans
  cette liste.

## Les 80 répliques qui étaient entièrement absentes

| Enregistrements chinois | Nombre | Contenu |
| --- | ---: | --- |
| `#928–933` | 6 | Fin d'une scène de la Team Rocket et répliques après combat |
| `#974–977` | 4 | Explication de Mewtwo par Olga et don du billet de voyage |
| `#990–1001` | 12 | Devise complète de la Team Rocket et annonce de son nouveau chef |
| `#1005` | 1 | Avertissement sur la puissance du nouveau chef Kamiyu |
| `#1318–1327` | 10 | Partie centrale de la devise de la Team Rocket |
| `#1624–1636` | 13 | Rencontre Rocket, devise complète et règlement de comptes |
| `#1638–1639` | 2 | Répliques de Jessie et Miaouss après le combat |
| `#1667–1678` | 12 | Nouvelle récitation complète de la devise Rocket |
| `#1680–1681` | 2 | Répliques après combat |
| `#1810–1823` | 14 | Devise et conclusion d'une rencontre Rocket chez Sylphe |
| `#1968–1971` | 4 | Partie de la dernière devise Rocket |

Les quatre lignes `#974–977` sont les pertes narratives les plus importantes :

1. Sacha demande : « Mewtwo ? »
2. Olga explique que la Team Rocket l'a cloné à partir des gènes de Mew et
   qu'une catastrophe a été évitée.
3. Sacha promet de revenir défier la Ligue.
4. Olga lui offre son billet de voyage mystérieux parce qu'elle doit retourner
   à la Ligue.

La réplique `#1005` avertit Sacha que, malgré sa force, les Pokémon de Kamiyu,
le nouveau chef, le vaincront. Elle manquait également dans l'ancien snapshot
français et est restaurée dans la release actuelle.

## Divergences majeures présentes dans l'ancienne ROM française

Voici les cas narratifs ou fonctionnels les plus nets avant correction. La
colonne française décrit le texte de l'ancien snapshot `22210785`, pas celui
de la release actuelle.

| ID | Sens du chinois | Français historique avant correction |
| --- | --- | --- |
| `#949` | Une fille annonce qu'elle va se marier. | « Le Conseil des 4 vient ensuite ! » |
| `#950` | Elle renonce au mariage et demande Sacha comme mari. | « Incroyable ! » |
| `#973` | Olga affirme que l'anomalie était causée par Mewtwo. | Nouvelle quête Team Rocket et passe pour le Roc Nombri |
| `#1003` | Jessie indique que Kamiyu se trouve chez Nanjing Tech à Céladopole. | Félicitations pour avoir vaincu la Team Rocket |
| `#1009` | Kamiyu attendait Sacha et lui demande s'il est prêt à combattre. | Eusine parle des Pokémon légendaires |
| `#1011` | Kamiyu conseille de visiter Hoenn et de revenir avec le Pokédex complet. | Un Pokémon respecte Sacha et veut le rejoindre |
| `#1017` | Kamiyu reconnaît sa défaite. | « Adieu voyageur ! » |
| `#1019` | Un homme menace d'appeler la police. | « Tes Pokémon peuvent t'emmener partout ! » |
| `#1062–1063` | Élevage des Pokémon, puis puissance de l'informatique. | Les deux dialogues sont inversés |
| `#1066` | Un Pokémon bien élevé devient très proche de son Dresseur. | Panneau « Route 1 : Jadielle / Bourg Palette » |
| `#1077` | Les petits arbres peuvent être coupés. | La CS Flash éclaire les grottes |
| `#1109` | La Team Rocket a capturé et tué la mère d'Osselait. | « Que les âmes Pokémon reposent. » |
| `#1236` | Le vieillard dort et il faut attendre son réveil. | Le vieillard se serait blessé au dos |
| `#1240–1245` | Remise du colis, Poké Ball spéciale et rêve du Prof. Chen. | Répliques décalées entre Sacha, Chen et Régis |
| `#1269–1271` | Obtention du Badge Roche, explication, puis récompense dont la table exécutable confirme qu'il s'agit de la CT35 (Armure). | Flash, reçu de CT35 et description d'Armure étaient décalés |
| `#1305` | Un Rocket propose à Sacha de rejoindre la Team Rocket. | « Donne-moi un fossile et file ! » |
| `#1345–1350` | Troisième, quatrième et cinquième combats du Pont Pépite. | Ordre inversé et quatre mauvais pointeurs |
| `#1384` | Léo parle de sa collection, des 150 espèces et d'un Pokémon légendaire. | « Amuse-toi. » |
| `#1406` | Un gentleman dit venir de Hoenn. | « Mes Pokémon sont mes amis ! » |
| `#1411` | Il évoque les légendes de Johto. | « Quel enfant impoli ! » |
| `#1441–1442` | Sacha masse le capitaine, qui le remercie et lui donne Coupe. | Fragment `raw!`, puis seulement « Frotte, frotte » |
| `#1453` | Obtention de la CT24. | Discours complet du Badge Foudre |
| `#1483–1485` | Refus, acceptation, puis obtention de Bulbizarre. | Les trois branches sont inversées |
| `#1579–1582` | Caméos du graphiste, scénariste, programmeur et boss du jeu. | Quatre dialogues de PNJ sans rapport |
| `#1640` | Le chef Rocket explique son QG, son trafic et donne son nom. | « Je suis impressionné que tu sois là ! » |
| `#1859–1860` | Obtention du Badge Marais, puis de la CT40. | CT40, puis description de Rafale Psy |
| `#1963` | Les Rockets reprochent à Sacha de les avoir mis au chômage. | « Tes Pokémon vont trembler devant moi. » |
| `#1973` | Morgane demande avec agacement ce que veut encore Sacha. | Leçon générale sur les pouvoirs psychiques |

De très longues séries de PNJ et de Dresseurs présentaient aussi des textes
anglais réordonnés ou remplacés, notamment Route Victoire (`#937–954`), les
villes et routes (`#1062–1188`), l'Océane (`#1406–1433`), les routes et
cavernes (`#1461–1545`), la Tour Pokémon et le Repaire Rocket
(`#1546–1681`), les routes maritimes (`#1686–1749` et `#1861–1903`) ainsi que
Sylphe SARL (`#1778–1823`). Ces plages contenaient aussi quelques traductions
correctes ; la liste CSV historique ne retient que les contresens certains.

## Fichiers exploitables

- `dialogues_absent_from_english_and_french.csv` : contrôle de l'état actuel ;
  il contient zéro ligne puisque les 80 pointeurs ont été restaurés.
- `dialogues_removed_from_english.csv` : inventaire historique reproductible
  des 80 suppressions propres à la ROM anglaise.
- `restored_chinese_dialogues.csv` : les 85 restaurations actuelles, dont ces
  80 pertes anglaises, avec source chinoise, état anglais et texte français.
- `dialogues_untranslated_in_english.csv` : les 110 textes graphiques anglais
  sauvés par une traduction française.
- `reviewed_large_dialogue_divergences.csv` : les 56 divergences majeures,
  avec chinois, anglais, français et diagnostic.
- `chinese_french_dialogue_inventory.csv` : inventaire source-centré des
  dialogues encore joignables.
