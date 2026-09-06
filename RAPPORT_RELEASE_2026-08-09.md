# Rapport de release — 9 août 2026

## Verdict

La release française finale du bootleg NES
`Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046)` est reproductible et validée.
La ROM canonique est `Pokemon_Jaune_FR_repacked_title.nes`, SHA-256 :

`1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`

Le double build reproduit les artefacts bit à bit. Les validateurs statiques,
la suite Python et la suite Mesen principale normale post-release sont
`PASS`. Les preuves de runtime sont qualifiées précisément plus bas : le
diagnostic Route 1 n'est pas une campagne complète et le matériel mapper 163
physique reste non testé.

## Artefacts canoniques

| Artefact | Base exclusive | SHA-256 |
| --- | --- | --- |
| `Pokemon_Jaune_FR_repacked_title.nes` | — | `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b` |
| `Pokemon_Jaune_FR_repacked_title_from_chinese.bps` | ROM chinoise NJ046 `450d40c0…` | `0a1988e744d7ef4dbf2c172b34973015b8777a0ce498a3b165b59a9825ed1d22` |
| `Pokemon_Jaune_FR_repacked_title_from_english.bps` | ROM anglaise 2015 `d5c308b5…` | `01d1c0cd27d361cfa7fb91623348d63613a14a2dc1ed344bb92c1ca2b6f7f9f7` |
| `Pokemon_Jaune_FR_repacked_title.ips` | `yellow.nes` `69520103…` | `912d9feaf7278f1cf0d139e4805360ad6d2232b68f98f9f9ac8e7e9bca9e5c29` |
| `Pokemon_Jaune_FR_repacked.nes` | — | `fe01711d751243f0afd9937691a1f080587eb97d83bf90587b83c49dabca032f` |
| `Pokemon_Jaune_FR_repacked.ips` | ROM anglaise de travail `d5c308b5…` | `4d7c2c60ccfdbe1b308f7d8b4f5b54f76b0664ddab86cbe8fd61b76b3ac742a7` |

Le BPS construit depuis la ROM chinoise est le livrable conseillé : il rend
la provenance de la traduction explicite et vérifie les CRC de la source, de
la cible et du patch. Le BPS anglais et l'IPS sont fournis pour compatibilité.
Ils n'utilisent pas la même base anglaise : le BPS attend la ROM anglaise 2015
`d5c308b5…`, tandis que l'IPS attend exclusivement `yellow.nes` `69520103…`.
Les deux BPS ont été copiés à la racine, puis comparés bit à bit avec ceux de
`build/release-2026-08-09-final-v2/` : les copies sont identiques et leurs hashes
correspondent au tableau ci-dessus.

La liste exhaustive des hashes, y compris ceux des audits et journaux, est
`build/release-2026-08-09-final-v2/SHA256SUMS`. Le manifeste de construction est
`build/release-2026-08-09-final-v2/release_manifest.json`.

Le contrôle indépendant des patchs est `PASS` pour 3/3 applications : Lunar
IPS 1.03 x64 pour l'IPS et Floating IPS v198 pour chacun des deux BPS. Chaque
sortie est identique octet par octet à la ROM canonique. La preuve est
`build/external-patcher-proof.json`, SHA-256
`3f53aace4f07fbed273baa6ecf20ee5e4ee731dffbf187d5d2e9e5b6dedcb338`.

## Traduction et fidélité chinoise

- Source canonique `script.py`, SHA-256
  `e870f48105bd570d8323bf0c9358b95dbe5e59e6557214196a547cfedcb56180`.
- CSV maître `traduction_base.csv`, SHA-256
  `a4932263753587b744cf3cc614f884c8754e95fec5b486f88c951adf242be803`.
- Avant toute construction, le builder verrouille aussi par SHA-256 le CSV
  des dépassements (`561ff1e5…`), la naturalisation principale (`923a9d3b…`),
  la couche de fidélité chinoise (`0761b3f1…`) et la naturalisation des
  restaurations (`5cbb41c9…`). Une modification de la source éditoriale entre
  la préparation et la construction fait échouer la release.
- La table de relecture contient exactement 1 055 dialogues : 970 dialogues
  principaux et 85 restaurations.
- Le rafraîchissement de l'audit de fidélité confirme 80/80 pointeurs chinois
  supprimés de l'anglais et restaurés en français, zéro réplique encore
  absente de l'anglais et du français, 85 restaurations au total et 17
  caméos. Il a été dérivé des extractions Unicode immuables sans prétendre
  réextraire HZK16 (`derived_refresh_without_hzk_reextraction`).
- Les 970 dialogues principaux sont reliés à leur source chinoise par un
  alignement de confiance `high`; les 85 restaurations portent la provenance
  `source directe`.
- Les 85 restaurations couvrent les 80 pointeurs supprimés de l'anglais, les
  quatre réponses mal pointées du Pont Pépite et le message Anti-Para
  mutualisé à tort dans la ROM anglaise.
- Les noms officiels français de Pokémon sont conservés, tandis que les
  particularités de la version chinoise — Nanjing, Hoenn, Johto, Kameiyu et
  l'équipe de développement — sont maintenues.
- L'inventaire final contient 17 dialogues de caméo ou de mention des
  créateurs : 10 Kameiyu, 2 Beibei, 2 Xiao Li, 1 Xiaohong, 1 Wei Cunfu et
  1 BOSS. Beibei est présent dans `D0064` et `D0632`.
- La récompense de Pierre est `CT35 reçue !`. Le dialogue chinois et la
  table exécutable concordent : CT34 correspond à Onde de Choc et CT35 à
  Armure.
- Les 967 dialogues de terrain produisent 2 518 pages optimisées sans mot
  coupé ni frontière grammaticale forte. Les trois introductions conservent
  leur layout 17/19 ; le validateur compte 2 530 bulles au total.

## Construction et tests statiques

Le build final place 1 819 textes ordinaires et 85 restaurations, soit 1 904
allocations. Le manifeste de pointeurs v2 est recoupé avec l'inventaire
canonique : les 1 912 références attendues sont présentes et vérifiées, dont
les 85 restaurations. Il n'y a aucun échec d'allocation, conflit de
pointeur, chevauchement incompatible ou dépassement fixe.

Le budget résiduel est de 51 octets dans la paire PRG 6, dont le plus grand
bloc mesure 11 octets, et de 135 octets contigus dans la paire PRG 7. Les
planchers de release (40/4 et 128/128) sont respectés. Le rapport démontre que
11 octets est la borne mathématique maximale du plus grand bloc de la paire 6
pour ce corpus, pas un échec de l'allocateur.

Le core normal post-release a découvert 50 modules `tools/test_*.py` et
exécuté 399 tests avec `OK`, sans échec ni saut. Son journal terminal est
`build/runtime-proof-final-1fefecbf-core-normal/run-20260809T163735Z-ba4e9771/static/04a-full-python-test-suite.log.stderr.txt`,
SHA-256 `09a254e66c0445452d8711299b8398ceb6205552ee8a1c20d4f2e37753aef3a6`.

Le gate final renforcé agrège 13 contrôles. Il inclut notamment la
reconstruction `--check` des 12 dérivés de fidélité chinoise, la complétude du
manifeste de pointeurs v2 contre les 1 912 références canoniques et les deux
cas de sauvegarde corrompue par région. Ces derniers utilisent une fixture
Mesen d'un seul octet relatif `$0050`, sans injection mémoire ; leur portée
ne doit pas être étendue à toutes les corruptions possibles.

Les audits de release vérifient notamment le mapper 163, l'aller-retour IPS et
BPS, la provenance, les pointeurs, le budget des banques, la sauvegarde, le
codec de police strict, les accents, le Pokédex 159/159, le découpage et la
couverture graphique. Ils se trouvent sous
`build/release-2026-08-09-final-v2/audits/`.

Le catalogue CHR courant est `build/chr-catalog/current-1fefecbf/`. Il est
lié au SHA de la ROM finale et recense 1 489 assets, 149 chevauchements
déclarés et 853 648 octets placés en liste blanche. `verify.json` et
`roundtrip.json` sont `PASS`, ne changent aucun octet et produisent tous deux
le SHA de sortie exact `1fefecbf…`.

Ce catalogue est une preuve statique exhaustive d'extraction et d'aller-retour
des assets déclarés. Il ne prouve pas que les 1 489 assets ont tous été
affichés dans une partie ; seuls les écrans couverts par les probes Mesen ont
une preuve dynamique.

## Preuves Mesen

Le manifeste principal exact est :

`build/runtime-proof-final-1fefecbf-core-normal/run-20260809T163735Z-ba4e9771/regression_suite_manifest.txt`

Son SHA-256 est
`c75fc00b3ed9d4f3d73ecb01b5783469fba3fc7c89bde296b4e85e2ee7f85f66`.
Il lie explicitement la preuve au SHA `1fefecbf…` et conclut à 45/45 étapes
`PASS` avec `Bootstrap completion gate: False`. En Dendy, NTSC et PAL, la
suite couvre le démarrage, l'activité
mapper 163 passive, l'introduction, les invites, tous les caractères français,
le CHR même-frame, le menu joueur, la campagne prototype et la batterie. Les
deux contrôles Auto/DB confirment aussi la région attendue de la ROM finale et
de la ROM chinoise. Les prototypes contrôleur-only sortent du laboratoire aux
images 10 700, 10 110 et 10 835 respectivement, avec `writes_to_game=0`.

Le bootstrap transitoire de pré-promotion, SHA-256 `947d822184774668…`,
avait le même résultat Mesen mais un test auto-référentiel sauté. Il est
conservé comme historique de la promotion et ne constitue plus la preuve core
active ; le manifeste normal ci-dessus l'a remplacé avec 399 tests sans saut.

Le diagnostic Route 1/Jadielle est `PASS` séparément en Dendy, NTSC et PAL
sous `build/runtime-proof-final-1fefecbf-route1/`. Il atteint l'alignement de
Jadielle à l'image 7 108, après une récupération de combat, avec zéro écriture
du scénario dans la RAM du jeu.

`tools/verify_mesen_route1_matrix.py` agrège ces preuves dans
`build/runtime-proof-final-1fefecbf-route1/route1_matrix.json`. La matrice
conclut `PASS` pour 3/3 régions et inventorie 196 captures. Son SHA-256 est
`e6dd8433056a1f710d83c1f5014f512a007e704bda47fbf3ca1a6edd3b426dc8`.

Cette preuve Route 1 est volontairement qualifiée de diagnostic, pas de
campagne complète : sa portée est `route1_viridian_alignment_only`, chaque
manifeste indique `parcel_route_done=false`, `dialogues=none` et
`writes_to_game=0`.

Le diagnostic séparé
`build/runtime-proof-final-1fefecbf-uninitialized-dendy/uninitialized_diagnostic.json`
est `PASS` en tant que diagnostic, SHA-256
`3d2ff9a11adaf9ad58a975bdfb85a6cad3c1515c66d7c126db5e9b3ea3e62099`.
Il confirme des lectures CPU réelles de RAM non initialisée : 102 lectures de
`$0161` à `$01C6` en Dendy et PAL, 103 jusqu'à `$01C7` en NTSC. Les 30 octets
de la routine fautive sont identiques dans les ROMs chinoise, anglaises et
française. La conclusion reste néanmoins
`inherited_source_engine_quirk_unresolved` et
`harmlessness_not_proven` : le même déclencheur n'a pas été reproduit dans la
ROM chinoise et une régression de déclenchement liée à la traduction n'est pas
exclue.

Les contrôles de sauvegarde corrompue sont `PASS` dans trois preuves dédiées :

- Dendy : `build/runtime-proof-final-1fefecbf-battery-dendy/verification.json`,
  SHA-256 `9427c130f53e6356adf798fab7ba00d033bd40dbe1460e696e9a2039d9c8bf12` ;
- NTSC : `build/runtime-proof-final-1fefecbf-battery-ntsc/verification.json`,
  SHA-256 `9af82e08416da0b14960eba2513e15ed65e5df2e72028c517843921e3add794d` ;
- PAL : `build/runtime-proof-final-1fefecbf-battery-pal/verification.json`,
  SHA-256 `c9b2b6fc978eb8c88e8d0eddcf38173e3ebd386c1f95f21395819c45d7e7f262`.

Chaque région comporte cinq phases : contrôle frais, création, rechargement,
corruption primaire et corruption backup, soit 15 phases `PASS`. Les deux cas
de corruption ne modifient qu'un octet relatif `$0050` (`$0050` dans le bloc
primaire, `$0C50` dans le backup), sans injection mémoire. Le primaire est
restauré depuis le backup et reprend la partie ; le backup corrompu est rejeté
vers le fallback de nouvelle partie. Cette preuve mono-octet sur une
sauvegarde de début de jeu n'est ni un fuzzing multi-octet/troncature/coupure
de courant, ni une preuve de reprise sur toute la campagne.

Ces preuves émulées ne remplacent pas un test sur une cartouche mapper 163
physique ni un parcours manuel exhaustif de toutes les branches optionnelles.
Le protocole à remplir sur le matériel réel est
`CHECKLIST_TEST_MATERIEL_MAPPER163.md`; ses lignes restent explicitement
`NON TESTÉ` tant qu'aucune cartouche n'a été fournie.

## Table de relecture

- CSV canonique : `LISTE_EXHAUSTIVE_DIALOGUES.csv`, 1 055 lignes de dialogue,
  SHA-256 `68fe03318fdd447d5d9be6e1010a8369a796ca27ab52c466edf4cb8762493129`.
- Classeur : `build/LISTE_EXHAUSTIVE_DIALOGUES.xlsx`, SHA-256
  `4fc1679d864ac6daec38ccbef8a284c9136010b292275d0c3de23e51fc1ebc38`.
  Le validateur XLSX strict confirme les valeurs A:N, les identifiants et clés
  stables, le filtre, les volets, la validation des verdicts, les formats
  conditionnels et l'absence de formules ou cellules parasites. Les colonnes
  de relecture O:P restent modifiables et préservables.

## Limites volontaires de l'interface

- Le logo `YELLOW` est conservé dans la release canonique. Une variante
  `JAUNE` est possible et son outillage a été testé, mais elle n'est pas la
  cible publiée afin de ne pas mêler une variante graphique à la validation
  linguistique finale.
- Les choix du titre restent `NOUV` / `CONT`. Les écrire en entier demanderait
  de modifier la géométrie de la tilemap et le code d'affichage, au-delà d'une
  simple traduction sûre.
- Le caractère `œ` est rendu `oe` (et `Œ`, `OE`) dans la ROM. Aucun slot de
  glyphe sûr n'est disponible sans remplacer un signe encore utilisé ou
  modifier le moteur de texte.

Ces choix sont des contraintes explicites, pas des dialogues oubliés.
