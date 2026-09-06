# État du bot de campagne Pokémon Jaune NES

## État courant — 9 août 2026

La remise actuellement publiée est
`Pokemon_Jaune_FR_repacked_title.nes`, SHA-256
`1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`.
La suite Mesen finale a rejoué le prototype contrôleur-only jusqu'à la sortie
stable du laboratoire dans les trois régions, sous matériel strict et
`FullDebug` : Dendy à l'image 10 700, NTSC à l'image 10 110 et PAL à l'image
10 835. Chaque run conclut `writes_to_game=0`.
Le manifeste normal post-release est
`build/runtime-proof-final-1fefecbf-core-normal/run-20260809T163735Z-ba4e9771/regression_suite_manifest.txt`,
SHA-256 `c75fc00b3ed9d4f3d73ecb01b5783469fba3fc7c89bde296b4e85e2ee7f85f66`.
Il porte `Bootstrap completion gate: False` et son journal conclut 399 tests
`OK` sans saut. Le bootstrap `947d8221…` reste un historique transitoire de
pré-promotion, pas la preuve active.

Le diagnostic complémentaire Route 1 atteint également l'entrée de Jadielle
en Dendy, NTSC et PAL. Il reste volontairement distinct d'une campagne
complète : sa portée est `route1_viridian_alignment_only`, il termine avec
`parcel_route_done=false` et `dialogues=none`, et le Colis de Chen ainsi que
la suite du jeu ne sont pas automatisés. Les trois runs déclarent
`writes_to_game=0`. Les preuves courantes sont recensées dans
`RAPPORT_RELEASE_2026-08-09.md` et agrégées dans
`build/runtime-proof-final-1fefecbf-route1/route1_matrix.json`.
La matrice valide 3/3 régions et 196 captures ; son SHA-256 est
`e6dd8433056a1f710d83c1f5014f512a007e704bda47fbf3ca1a6edd3b426dc8`.

Deux diagnostics complémentaires ne changent pas cette portée :

- la lecture de RAM CPU non initialisée `$0161..$01C6` observée en Dendy reste
  `inherited_source_engine_quirk_unresolved` et
  `harmlessness_not_proven` ; seule la routine commune aux ROMs sources est
  prouvée, pas l'innocuité du comportement. Le rapport dédié a le SHA-256
  `3d2ff9a11adaf9ad58a975bdfb85a6cad3c1515c66d7c126db5e9b3ea3e62099` ;
- la corruption de sauvegarde est testée dans Mesen en Dendy, NTSC et PAL par
  deux cas contrôlés fondés sur une fixture d'un seul octet relatif `$0050`,
  sans injection mémoire. Ce test ne remplace pas des reprises de campagne à
  tous les jalons ni un fuzzing exhaustif du format. Les trois rapports ont
  les SHA-256 `9427c130…`, `9af82e08…` et `c9b2b6fc…`.

Aucun de ces résultats n'est une preuve sur cartouche mapper 163 physique :
le matériel réel reste `NON TESTÉ`.

## Historique du développement — état au 29 juillet 2026

Date d'origine de la section : 29 juillet 2026

## Réponse courte

Un bot Lua Mesen capable de terminer toute cette ROM et d'obtenir tous les
Pokémon est techniquement réalisable, mais il n'est **pas encore complet**.
Le socle, la route contrôleur-only jusqu'à Chen, l'obtention naturelle de
Pikachu, la victoire imposée contre Régis, la sortie du laboratoire, la Route
1 et l'entrée dans Jadielle sont maintenant prouvés en NTSC sur la remise
courante. Une continuation gère aussi trois combats sauvages et s'arrête
hors combat sur un écran extérieur. En PAL, le prototype a réussi une fois
puis échoué au run suivant avec le même Lua : la route est démontrée, mais
instable pendant le combat contre Régis. Le traçage des captures naturelles
et la vérification assistée du Pokédex sont également opérationnels.

Une macro à frames fixes n'est pas suffisante : le TAS public de 43 160 frames
va jusqu'au Mont Sélénite sur la ROM chinoise, mais se désynchronise et reste
dans la chambre sur la traduction française. Le moteur local attend donc des
états réels du jeu avant chaque action.

## Trois niveaux de preuve

| Mode | Modifie le jeu par | Ce qu'il prouve |
|---|---|---|
| `controller` | manette virtuelle uniquement | parcours réellement rejouable |
| `assisted` | manette + écritures RAM listées et journalisées | couverture rapide d'un écran ou d'une structure |
| `exhaustive` à construire | rencontre imposée, puis menus/combat/capture réels | sprites, noms, dialogues et logique de capture de chaque espèce |

Une écriture directe des bitmaps Pokédex n'est jamais présentée comme une
capture gagnée en combat.

## Reprise au-delà de Jadielle — 29 juillet 2026

La ROM courante à cette date `Pokemon_Jaune_FR_repacked.nes`, SHA-256
`de3df81ad00f51559cbe3a78f1882cc565167b89fbc201d22a66a569ae05bd1b`,
a passé le nouveau jalon NTSC avec `StrictHardware=True` et
`FullDebug=True` :

- sortie naturelle du laboratoire par le prototype ;
- traversée de la Route 1 et réalignement à l'entrée de Jadielle ;
- continuation désormais prolongée jusqu'à l'image logique 17 100 ;
- cinq combats sauvages terminés à la manette ;
- point terminal hors combat, dans une zone extérieure habitée, en `(80,70)`
  avec la signature PPU `B8D5F7DA` ;
- `writes_to_game=0`, aucun savestate, rewind ou cheat ;
- deux nouvelles espèces vues pendant ce run, aucune capturée.

Le manifest autoportant et les captures de l'extension sont dans
`build/campaign-continuation/extended-17100-de3df81a-ntsc-r1`. Le jalon
précédent à 11 950 reste conservé dans
`build/campaign-continuation/viridian-next-event-de3df81a-ntsc-r5`.
Les 17 tests statiques du bridge, de la continuation et du runner passent.
Cette preuve ne signifie pas que le film FM3 est encore synchronisé avec son
parcours chinois : après Jadielle, ses entrées servent seulement de matériau
de continuation, entouré de récupérations pilotées par l'état réel du jeu.
L'extension parcourt davantage le monde et survit aux combats, mais ne prouve
pas encore un nouvel objectif scénaristique nommé ni une nouvelle capture.

Le défaut corrigé pendant cette reprise confondait le début de la fenêtre de
trace (image 7 100) avec le début de la prise de contrôle (image 6 407). Dans
un état strict randomisé, le bot reprenait la main trop tard, quittait
Jadielle vers le sud et finissait à Bourg Palette. Les deux seuils sont
désormais indépendants.

### Objectif Arène d'Argenta

Le développement vers la première Arène est engagé, mais Pierre n'est pas
encore atteint. Un replay complet des 43 160 entrées de référence passe sous
Mesen NTSC strict/debug dans
`build/campaign-continuation/full-reference-de3df81a-ntsc-r1` :
six combats sauvages sont récupérés, les dialogues hors combat peuvent
désormais être avancés à la manette et `writes_to_game=0`. Ce replay termine
toutefois encore dans une zone de Jadielle sans nouvel objectif scénario.

Le prochain verrou prouvé est le Colis de Chen. Un probe court et opt-in
cartographie l'intérieur atteint à l'image 7 100, journalise les lectures du
dialogue français attendu à `$0387F3` et exporte 2 Kio de RAM hôte sans
écrire dans le jeu. Les essais ont montré que cet intérieur ne contient pas
le PNJ du Colis : le PNJ violet parle de la Team Rocket, le PNJ bleu et le
personnage vert du comptoir utilisent d'autres scripts. Cette route
expérimentale a donc été retirée de la continuation principale afin de ne
pas créer un faux jalon. Le probe isolé est
`mesen_fm3_parcel_route_probe_after_prototype.lua`.

La route minimale restante avant Pierre est : identifier le bon warp de la
Boutique de Jadielle, obtenir et attester le Colis, revenir chez Chen,
attester le Pokédex, traverser la Forêt de Jade, entrer dans l'Arène
d'Argenta, puis gagner le combat.

## Revalidation historique de la remise du 28 juillet 2026

La route contrôleur-only a été rejouée sur la ROM finale de SHA-256
`42a0d940d2d93742b00bf5812562d31286093747781aebc8a57e5c63821303e7`
avec `StrictHardware` et `FullDebug` :

| Région | Résultat | Image terminale | État terminal | Dossier |
|---|---|---:|---|---|
| Dendy | **PASS** | 10 545 | `outside_lab_stable` | `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-dendy-strict-full-debug-manifest-v2` |
| NTSC | **PASS** | 10 575 | `outside_lab_stable` | `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-ntsc-strict-full-debug-manifest-v2` |
| PAL, run attesté 1 | **PASS** | 10 545 | `outside_lab_stable` | `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-pal-strict-full-debug-manifest-v2` |
| PAL, run attesté 2 | **FAIL campagne** | 14 931 | timeout dans `complete_rival_battle` | `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-pal-strict-full-debug-manifest-v3` |

Les trois succès attestés sont entièrement `controller-only`, avec
`writes_to_game=0`, `retries=0`, la signature extérieure `451EA43C` et les
coordonnées `(80,70)`. La portée s'arrête à la sortie stable du laboratoire :
ce n'est ni un bot ayant terminé le jeu, ni une preuve de capture naturelle
des 151 Pokémon.

Les deux nouveaux runs PAL sont autoportants : leurs manifests enregistrent
le même SHA Lua `6849701b…`, les mêmes quatre modules, la même ROM, Mesen
`8ef403d6…`, `StrictHardware=True` et `FullDebug=True`. Le premier gagne et
sort ; le suivant expire après 7 200 images dans `complete_rival_battle`.
Les anciens échecs à l'image 14 931 restent cohérents avec cette instabilité.

La suite générale de régression de cette même ROM passe **42/42**
(16 contrôles statiques et 26 étapes Mesen), PAL inclus, sous matériel
strict et `FullDebug` :
`build/r/42a0d940-current-runner/run-20260728T213001Z-b669c855/regression_suite_manifest.txt`.
Elle couvre notamment boot, runtime, introduction, glyphes, CHR, menu et
batterie, mais pas le combat contrôleur-only contre Régis. L'alternance
PASS/FAIL de la campagne PAL est donc une limite de robustesse du bot et ne
constitue pas la preuve d'un crash de la ROM.

## Ce qui fonctionnait sur la remise `42a0d940`

- machine à états avec prédicats, timeout, récupération et journal ;
- file de touches garantissant une phase de relâchement ;
- garde mémoire : tout appel qui passe par le harness est refusé en mode
  `controller`; liste blanche et journal en mode `assisted` ;
- démarrage à froid, nouvelle partie, chambre, rez-de-chaussée, contournement
  de la table puis sortie réelle de la maison par signatures PPU et
  coordonnées, sans RAM write, savestate, rewind ni cheat ;
- route extérieure prouvée par douze impulsions vers l'est puis montée,
  déclenchement de Chen, capture automatique et retour au laboratoire ;
- interaction réelle avec la balle et preuve SRAM en lecture seule de
  l'équipe `count=01 / species=19 / level=05`, soit Pikachu #025 niveau 5 ;
- combat imposé contre Régis réellement joué à la manette, avec captures
  Évoli/Pikachu, signature de victoire `00A7ECFE` et texte
  « Pikachu 45 Exp. gagnée ! » en Dendy, NTSC et dans le run PAL réussi ;
- retour au laboratoire (`7FFE1D9C`) puis sortie extérieure stable
  `(80,70)`, signature `451EA43C`, à l'image 10 545 en Dendy/PAL réussi et
  10 575 en NTSC, avec zéro écriture mémoire et zéro récupération ;

La route complète est reproductible en Dendy/NTSC et démontrée sous PAL, mais
la stratégie du bot n'est pas robuste d'un état de mise sous tension strict
randomisé au suivant pendant le combat contre Régis.

Le probe assisté `SEEN 151 / CAUGHT 151` est désormais rejoué sur `42a0d940`
en Dendy, NTSC et PAL. Les trois runs passent à l'image 5 600 avec
`writes=42`, en enregistrant les adresses modifiées :
`build/campaign-assisted/pokedex-151-final-42a0d940-<region>-strict-full-debug-v2`.
Il s'agit d'une preuve assistée des bitmaps, des compteurs et de l'écran,
jamais d'une série de captures naturelles, d'un affichage individuel des 151
fiches ou d'une preuve de persistance après sauvegarde/rechargement.

## Preuve précédente conservée — remise `80310612`

La remise précédente avait validé cette route en Dendy à l'image 10 545 dans
`build/campaign-prototype/oak-pikachu-rival-exit-final-80310612-dendy-strict-full-debug`,
avec `writes_to_game=0` et `retries=0`. Cette preuve reste historique et ne
remplace pas les exécutions de la remise actuelle `42a0d940`.

## Preuves historiques conservées — snapshots `5b479227` et `dadf7f02`

Les points ci-dessous décrivent le socle validé sur l'ancien snapshot
`5b479227`, sauf le probe assisté explicitement rattaché à `dadf7f02`.
Ils restent utiles pour le développement du bot, mais ne doivent pas être
présentés comme des replays de campagne exécutés sur `42a0d940` :

- premier écran extérieur stable `(80,70)`, signature PPU `DD441740`, validé
  avec `StrictHardware` et `FullDebug` en Dendy à la frame 3 935, en NTSC à la
  frame 3 940 et en PAL à la frame 3 935 ;
- zéro écriture mémoire du jeu et zéro récupération/réessai sur les trois
  exécutions, toutes réalisées sur l'ancienne ROM de SHA-256
  `5b479227c614428226a1d2a201435734fad6afed7d9e0a38c6b9857f2ad5f3ac` ;
- extraction et replay Mesen d'un FM3 public de 43 160 frames ;
- trace naturelle des transitions Pokédex du TAS : capturés
  `[10,25,26,56]`, vus `[10,21,25,26,56,133]`, avec PNG à chaque nouvelle
  acquisition ;
- cartographie sûre de la sauvegarde, de l'équipe, des badges et des 151 bits
  `SEEN`/`CAUGHT` ;
- probe assisté français affichant `SEEN 151 / CAUGHT 151`, validé Dendy,
  PAL et NTSC avec matériel strict et tous les arrêts de débogage sur la ROM
  historique SHA-256 `dadf7f026154ceeb8bfc43b981399a0930ce924d9de8a0462e04e63f1830dc10` ;
- preuves séparées conservées dans
  `build/campaign-prototype/oak-pikachu-rival-exit-final-5b479227-dendy-strict-full-debug`,
  `build/campaign-prototype/outside-final-5b479227-dendy-strict-full-debug`,
  `build/campaign-prototype/outside-final-5b479227-ntsc-strict-full-debug` et
  `build/campaign-prototype/outside-final-5b479227-pal-strict-full-debug`.

Les outils de traçage, la cartographie de sauvegarde et les probes issus de
ces travaux restent utilisables ; seule la portée de leurs exécutions
historiques est distinguée ici de la remise actuelle.

## Portée exacte des espèces

La table de noms de la ROM contient 159 entrées :

- les 151 espèces de Kanto ;
- Raikou, Entei, Suicune, Lugia et Ho-Oh ;
- Kyogre, Groudon et Rayquaza.

L'interface Pokédex, elle, compare explicitement le numéro à `$98` et s'arrête
avant l'ID 152. Ses bitmaps prouvés ne couvrent donc que #001 à #151. Les huit
espèces bonus devront être vérifiées par leurs combats, cadeaux, équipe ou
stockage ; elles ne doivent pas être cochées dans un faux « Pokédex 159 ».

## Fin réelle à viser

Le premier Temple de la Gloire n'est pas la fin complète de ce bootleg. Les
dialogues révèlent encore la Grotte Inconnue, le Roc Nombri, un retour de la
Team Rocket, un nouveau passage à la Ligue, Kameyu, le contrôle des Pokémon de
Kanto, puis le don de Mew et le contrôle final par la mère du héros.

Les endpoints finaux à prouver séparément sont donc :

1. Temple de la Gloire ;
2. scénario post-Ligue terminé ;
3. Mew obtenu ;
4. Pokédex Kanto 151/151 conservé après sauvegarde et rechargement.

Aucun rouleau de générique conventionnel n'est encore prouvé dans cette ROM.

## Fichiers principaux

- `mesen_campaign_prototype.lua` : route contrôleur-only actuelle ;
- `EVIDENCE_OAK_LAB_FR.md` : environnement et jalons exacts de la preuve
  Chen/Pikachu/Régis/sortie ;
- `engine.lua`, `input_queue.lua`, `memory_guard.lua` : moteur ;
- `ram_map.lua`, `species_plan.lua` : données prouvées et objectifs 151/159 ;
- `../mesen_fm3_input_replay.lua` : replay d'entrées FCEUX ;
- `../mesen_fm3_early_campaign_trace.lua` : jalons de référence
  Chen/laboratoire/Pikachu/Régis sur le FM3 original ;
- `../mesen_fm3_pokedex_trace.lua` : trace des acquisitions naturelles ;
- `../mesen_pokedex_151_assisted_probe.lua` : preuve assistée 151/151 ;
- `../pokemon_save_layout.py` et
  `../analysis/pokemon_save_layout/README.md` : sauvegarde vérifiée.

## Travail restant avant de dire « le jeu est fini »

1. remplacer la continuation FM3 après Jadielle par des jalons de navigation
   nommés et pilotés par l'état réel, parmi les 416 écrans ;
2. généraliser les détecteurs de dialogues, menus, combats et transitions ;
3. stabiliser le combat contre Régis en PAL, puis implémenter la stratégie
   combat/soin/achat/capture au-delà de ce premier combat ;
4. inventorier la méthode d'obtention réelle des 151, puis des huit bonus ;
5. construire les jalons jusqu'au Temple de la Gloire et à Mew ;
6. sauvegarder à chaque jalon et vérifier la reprise dans un second processus ;
7. rejouer la route finale depuis un cold boot, sans écriture RAM ni
   chargement d'état, sous Dendy, PAL et NTSC avec `StrictHardware` et
   `FullDebug`.

Tant que ces sept points ne sont pas terminés, le résultat doit être nommé
« prototype de campagne » ou « vérification assistée », pas « partie complète
151/159 contrôleur-only ».
