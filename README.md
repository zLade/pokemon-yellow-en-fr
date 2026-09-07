# Pokémon Jaune NES — traduction française

Traduction française du jeu Famicom non officiel **Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046)**. Cette branche `fr` contient les sources françaises ; la version anglaise se trouve sur [la branche en](https://github.com/zLade/pokemon-yellow-en-fr/tree/en).

Release de référence : **2.0.12**, avec correction de la hauteur musicale, sur **mapper 163**. Aucune ROM complète n'est distribuée. Voir [la notice](NOTICE.md) pour les éléments tiers et [CHANGELOG.md](CHANGELOG.md) pour les versions.

## Jouer

Appliquer le [patch IPS français 2.0.12](releases/fr/2.0.12/Pokemon_Jaune_NJ046_FR_v2.0.12.ips) à une copie propre de la ROM chinoise originale `Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes` avec un outil IPS. Il ne s'applique pas à Pokémon Jaune sur Game Boy.

- Entrée : 2 097 168 octets, SHA-256 `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed`.
- Résultat : SHA-256 `efc7ba0837a65d06e0658348d3debaa1194b9cf03b59492a1a8d4dfab346327e`.

Utiliser un émulateur compatible mapper 163, par exemple Mesen 2.2.1. Les détails du patch figurent dans [le dossier de release](releases/fr/2.0.12/README.md).

La 2.0.12 change uniquement la base du patch : la ROM obtenue est identique à la 2.0.11. Ne pas appliquer ce nouvel IPS sur une traduction anglaise ou une ROM déjà patchée. Un IPS ne vérifie pas lui-même la bonne ROM de départ : contrôler son SHA-256.

## Sources de traduction

Trois fichiers éditables dans `traduction/` :

| Fichier | Rôle |
| --- | --- |
| [catalogue.csv](traduction/catalogue.csv) | 1 931 entrées : dialogues, menus et textes, dont 85 restaurations chinoises. Modifier `fr_text`. |
| [pointer_variants.csv](traduction/pointer_variants.csv) | 5 variantes liées à des pointeurs confondus dans la base anglaise de 2015. Modifier `fr_text` ; la première variante de chaque groupe doit rester cohérente avec le catalogue. |
| [move_labels_two_line.csv](traduction/move_labels_two_line.csv) | 94 noms d'attaques graphiques. Modifier `full_name`, `line_1` et `line_2`. |

Conserver le CSV UTF-8, les espaces de début/fin et les retours à la ligne dans les cellules : ils peuvent être nécessaires pour assembler un nom et un fragment de phrase. Ne pas modifier les identifiants, indices, pointeurs, offsets, `record_type`, `layout` ni `max_len` pour une correction de texte.

`chinese_text` est la référence linguistique ; `source_en` est la traduction historique de 2015, pas une autorité. `source_alignment` indique une correspondance unique, multiple, restaurée ou non alignée. Plusieurs textes chinois peuvent partager un texte anglais : ne pas supposer une correspondance certaine. Les lignes `RESTORED` rétablissent des textes absents ou confondus dans la base anglaise. Une entrée vide est volontaire et réservée par les contrôles structurels.

### Dictionnaire des colonnes

Les tableaux ci-dessous décrivent toutes les colonnes des trois CSV éditables.
**Modifier** désigne le travail habituel de traduction ; **Note** une information
éditoriale à actualiser seulement si la correction le justifie ; **Conserver**
une donnée source ou technique à ne pas changer. Ces indications ne sont pas
des valeurs à saisir dans le CSV. Ne pas renommer les colonnes, ajouter/supprimer
des entrées ou renuméroter les identifiants pour corriger une phrase.

#### Catalogue principal

| Colonne | Signification | Consigne |
| --- | --- | --- |
| `stable_key` | Identifiant permanent, par exemple `MAIN:0x0301C4`, à citer dans une correction ou un signalement. | Conserver. |
| `record_type` | `MAIN` : entrée principale ; `RESTORED` : texte chinois rétabli après une omission ou une confusion dans la base anglaise. | Conserver. |
| `offset_hex` | Adresse source hexadécimale qui identifie l'entrée pour le moteur, pas nécessairement son adresse après déplacement dans la ROM finale. | Conserver. |
| `layout` | Règle de mise en page et d'encodage de cette entrée, détaillée ci-dessous. | Conserver. |
| `max_len` | Capacité de stockage source en octets, pas nombre de lettres autorisées à l'écran. Une cellule vide laisse le moteur déterminer la capacité applicable. | Conserver, y compris les cellules vides ; ne pas augmenter pour faire passer un texte. |
| `chinese_text` | Texte chinois de référence, parfois associé à plusieurs entrées sources. | Conserver ; signaler séparément une erreur d'extraction ou de correspondance. |
| `source_en` | Texte historique de la base anglaise de 2015, potentiellement erroné. | Conserver : c'est une comparaison, pas le texte français à modifier. |
| `fr_text` | Traduction française actuelle utilisée pour construire la ROM. | **Modifier cette colonne pour corriger le texte.** Préserver espaces de raccord, retours à la ligne et contrôles. |
| `source_alignment` | État de la correspondance avec le chinois : `unique`, `multiple`, `restaure` ou `non_aligne`. | Conserver sauf réexamen de la source ; ce n'est pas une note de qualité de la traduction. |

`unique` indique une correspondance unique, `multiple` plusieurs sources
associées, `restaure` une entrée restaurée et `non_aligne` l'absence de
correspondance établie. Ne pas inventer une source pour remplir une cellule.

`dialogue_19_19` et `dialogue_intro_17_19` sélectionnent les règles de
largeur des lignes de dialogue ; `pokedex_13x4` sélectionne une description
sur quatre lignes de treize colonnes. Un `layout` vide ou `raw` ne signifie
pas « espace illimité » : les emplacements fixes, les noms insérés pendant le
jeu et les routines de combat imposent aussi des limites. Le moteur gère les
déplacements de texte ; les capacités source ne sont pas des compteurs à
recalculer manuellement après une correction.

#### Variantes liées aux pointeurs

Un pointeur indique au jeu où lire un texte. Son adresse dans la table est
différente de l'adresse du texte visé. Certaines situations chinoises distinctes
partageaient un même texte anglais : ces variantes permettent de les séparer.

| Colonne | Signification | Consigne |
| --- | --- | --- |
| `main_offset_hex` | Adresse de l'entrée MAIN du catalogue à laquelle appartient la variante. | Conserver. |
| `pointer_reference_hex` | Adresse du pointeur qui sélectionne ce contexte précis. | Conserver ; ne pas la confondre avec l'adresse du texte. |
| `chinese_text` | Sens chinois propre à ce contexte. | Conserver et utiliser comme référence. |
| `fr_text` | Texte français destiné à ce pointeur. | **Modifier.** La première variante de chaque groupe doit rester identique au texte MAIN correspondant ; les autres gardent leur sens distinct. |
| `review_status` | État de relecture ; le chargeur exige actuellement `reviewed`. | Note : ne pas marquer une variante comme relue sans relecture, ni changer le statut pour contourner un contrôle. |
| `fidelity_comment` | Explication du sens, des différences entre contextes et des choix de formulation. | Note : actualiser en français lorsque la correction le nécessite. Ce commentaire n'est pas affiché en jeu. |

#### Noms d'attaques graphiques

| Colonne | Signification | Consigne |
| --- | --- | --- |
| `move_index` | Indice de l'attaque dans la table de ce jeu NES ; ce n'est pas un numéro de ligne à renuméroter ni nécessairement un identifiant Game Boy. | Conserver, y compris sa présentation. |
| `full_name` | Nom complet lisible servant à identifier l'attaque et aux rapports. | **Modifier** pour corriger le nom ; ce champ seul ne redessine pas le libellé en jeu. |
| `line_1` | Première ligne réellement dessinée dans le libellé graphique. | **Modifier**, avec 1 à 8 glyphes encodés. |
| `line_2` | Seconde ligne réellement dessinée dans le libellé graphique. | **Modifier**, avec 1 à 8 glyphes encodés ; le chargeur actuel exige une seconde ligne non vide. |

Exemple : `Roue de Feu` conserve son nom complet dans `full_name`, avec
`Roue` dans `line_1` et `de Feu` dans `line_2`. Conserver le nom complet
même si les lignes affichées nécessitent une abréviation. Cette limite de huit
glyphes concerne ce tableau graphique, pas tous les dialogues. Le fichier ne
contient que les remplacements graphiques sélectionnés, pas toutes les attaques
du jeu. Ajouter ou retirer un indice demande une vérification technique des
allocations graphiques et des tests.

Pour une correction ordinaire, modifier `fr_text`, répercuter la modification
dans la première variante si elle existe, puis lancer les contrôles ci-dessous.
Ne pas changer une source, un pointeur ou une limite pour contourner une erreur.
Les fichiers de `data/source/` et `data/validation/` sont des références et
des garde-fous, pas des tableaux supplémentaires à mettre à jour à chaque phrase.

## Contribuer

1. Créer une branche de travail à partir de `fr` et modifier les cellules concernées.
2. Garder le sens chinois et un français naturel. Utiliser les noms et termes français de Rouge/Bleu/Jaune lorsqu'ils conviennent au contexte ; conserver les caméos propres à NJ046.
3. Préférer les mots complets, puis les abréviations officielles si nécessaire. Ne raccourcir davantage que si la fenêtre l'impose. Les attaques graphiques peuvent occuper deux lignes.
4. Lancer les contrôles ci-dessous et vérifier les écrans modifiés en jeu : bordures, raccords, curseurs, effacement du message précédent.
5. Proposer une pull request vers `fr` avec contexte, texte avant/après et résultats des tests. Ne pas joindre de ROM complète ni de sauvegarde personnelle.

Les 101 fragments dynamiques ont des attentes explicites dans `tools/validate_french_dynamic_fragments.py`. Une modification intentionnelle nécessite de revoir ensemble texte, espaces de raccord, limites et test associé ; ne pas désactiver un contrôle pour faire passer une compilation.

## Contrôler sans ROM

Python 3.12 ou plus récent, sans dépendance Python externe. Depuis la racine :

```bash
python build.py check
python -m unittest discover -s tools -p "test_*.py"
python tools/validate_branch_separation.py --language fr
```

Les tests exigeant une ROM locale sont explicitement ignorés si elle est absente. GitHub Actions vérifie les sources, les tests sans ROM et l'empreinte du patch publié.

Avec les deux ROMs disponibles, `NJ046_VERIFY_RELEASE=1` active aussi le test d'intégration de reconstruction exacte ; sous PowerShell, définir `$env:NJ046_VERIFY_RELEASE = '1'` avant de lancer les tests. `POKEMON_FINAL_ROM_UNDER_TEST` permet de désigner une ROM compilée pour le test de conservation des fins de banques.

## Compiler

Fournir les deux images suivantes, ignorées par Git. La compilation vérifie taille et SHA-256, pas seulement les noms.

| Nom à la racine | SHA-256 |
| --- | --- |
| `Pokemon Yellow English 9-23-2015.nes` | `d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac112509d658a9943b` |
| `Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes` | `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed` |

```bash
python build.py build
```

La base anglaise de 2015 reste une référence technique interne pour le repack. L'image chinoise fournit le sprite restauré du dojo et sert de base au patch IPS final. Les options `--english` et `--chinese` acceptent d'autres emplacements. Pour appliquer le patch publié, seule la ROM chinoise est nécessaire.

Les résultats sont dans `build/fr/` : ROM, IPS, rapport et manifeste des pointeurs. Une destination non vide est refusée ; choisir un nouveau dossier, par exemple `--output-dir build/essai-2`. Les ROMs sources et le patch publié ne sont pas modifiés.

Pour reproduire exactement les octets de la release :

```bash
python build.py build --verify-release --output-dir build/verification-2.0.12
```

Omettre `--verify-release` après une modification de traduction : le résultat peut différer de la release tout en passant les contrôles de sécurité.

Les contrôles comprennent deux compilations déterministes, la reconstruction indépendante des banques de texte, les 1 916 propriétaires de pointeurs, les limites des messages dynamiques et attaques, les marges des banques, le mapper 163 avant la correction musicale strictement bornée et l'aller-retour IPS.

## Tests en jeu

Un build réussi ne prouve pas que tout le jeu a été parcouru. Vérifier notamment les noms longs, les débuts/fins de combat, le curseur Oui/Non d'oubli d'attaque, l'effacement des messages, le Pokéshop et les sauvegardes.

Des diagnostics Mesen autonomes restent dans `tools/` : démarrage/mapper, accents, menus et persistance de sauvegarde. Le lanceur PowerShell conserve les preuves et contrôle l'intégrité de la ROM. Exemple :

```powershell
./tools/run-mesen-pokemon-scenario.ps1 -RomPath ./build/fr/Pokemon_Jaune_NJ046_FR.nes -ScriptPath ./tools/mesen_mapper163_boot_probe.lua -OutputDirectory ./build/mesen-boot -MesenPath /chemin/vers/Mesen.exe
```

Chaque sonde décrit ses conditions et son marqueur de réussite dans son code ; fournir `-ExpectedMarker` si nécessaire. La sonde d'accents est assistée, pas une preuve de parcours naturel. Le build ne lance pas Mesen automatiquement. Le matériel réel reste à tester.

## Organisation

- `traduction/` : les trois sources éditables.
- `data/source/` : extraction chinoise et correspondance des glyphes en lecture seule.
- `data/validation/` : structure attendue, propriété des pointeurs et indices graphiques, sans deuxième copie des traductions.
- `tools/` : moteur, contrôles, tests et diagnostics ciblés.
- `releases/fr/2.0.12/` : patch courant, version et empreintes.
- `build/` : résultats locaux générés, non suivis par Git.

Le point d'entrée public est `build.py`. Les versions antérieures restent accessibles dans l'historique Git.
