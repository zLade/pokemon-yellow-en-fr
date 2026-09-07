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
