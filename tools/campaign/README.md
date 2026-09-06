# Squelette de campagne Mesen

Ce dossier contient les briques testables du futur script de campagne. Il ne
prétend pas encore terminer le jeu : il sépare volontairement le pilotage
normal et les aides mémoire afin que les résultats restent auditables.

## État de la remise actuelle

Sur la ROM finale SHA-256
`1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`,
le prototype contrôleur-only passe en Dendy, NTSC et PAL jusqu'à la sortie
stable du laboratoire, avec respectivement 10 700, 10 110 et 10 835 images,
`writes_to_game=0`, matériel strict et `FullDebug`. Le manifeste normal se
trouve sous
`build/runtime-proof-final-1fefecbf-core-normal/run-20260809T163735Z-ba4e9771/`.
Il porte explicitement `Bootstrap completion gate: False` et son journal
conclut 399 tests `OK` sans saut. Le bootstrap `947d8221…` n'est conservé que
comme historique transitoire de pré-promotion.

Le probe Route 1/Jadielle passe lui aussi dans les trois régions, mais ne doit
pas être présenté comme un parcours complet : il termine avec
`parcel_route_done=false`, `dialogues=none` et la portée
`route1_viridian_alignment_only`. Voir `RAPPORT_RELEASE_2026-08-09.md` pour la
qualification exacte et les hashes des preuves. Les commandes et résultats
`42a0d940` ci-dessous sont conservés comme historique reproductible.

Le diagnostic de RAM non initialisée demeure
`inherited_source_engine_quirk_unresolved` et
`harmlessness_not_proven`. Le contrôle de sauvegarde corrompue couvre deux
cas par région avec une fixture d'un octet relatif `$0050`, sans injection ;
il ne prouve ni une campagne complète ni tous les types de corruption. Le
matériel mapper 163 physique reste `NON TESTÉ`.

## Modules

- `engine.lua` : machine à états. Chaque étape déclare obligatoirement
  `entry`, `success`, `timeout` et `recovery`; une étape ne peut donc pas
  attendre indéfiniment.
- `input_queue.lua` : file d'entrées manette. Une phase neutre est toujours
  envoyée entre deux actions, et `abort()` relâche immédiatement les boutons.
- `memory_guard.lua` : mode `controller` strictement sans écriture, ou mode
  `assisted` limité à une liste blanche et accompagné d'un journal TSV.
- `ram_map.lua` : uniquement les offsets actuellement prouvés par les sondes.
- `species_plan.lua` : plan numérique configurable pour 151 entrées
  canoniques ou les 159 cases de la table de cette ROM.
- `mesen_campaign_prototype.lua` : route manette à états, du démarrage à froid
  à la victoire contre Régis puis à la sortie stable du laboratoire.

Les identifiants 152 à 159 portent réellement les noms **Raikou, Entei,
Suicune, Lugia, Ho-Oh, Kyogre, Groudon et Rayquaza** dans la table de la ROM.
Ils ne font toutefois pas partie du Pokédex de Kanto : l'interface et les
bitfields prouvés s'arrêtent à 151. Leur nom dans la table ne prouve pas à lui
seul qu'ils soient tous capturables en jeu. Les drapeaux de scénario et la
position cartographique ne seront ajoutés à `ram_map.lua` qu'après une preuve
ciblée.

## Contrat mémoire actuel

| Domaine | Adresse | Usage prouvé | Écriture |
| --- | ---: | --- | --- |
| `nesMemory` | `$6000` | le masque `$20` déverrouille l'accès au Pokédex | seulement `ancienne_valeur OR $20`, en mode assisté |
| `nesMemory` | `$6030` | taille de l'équipe | lecture seule dans le prototype |
| `nesMemory` | `$6031` | compteur d'espèces vues (0–151) | lecture seule dans le harness |
| `nesMemory` | `$6032` | compteur d'espèces capturées (0–151) | lecture seule dans le harness |
| `nesMemory` | `$6033` | espèce du premier emplacement d'équipe | lecture seule dans le prototype |
| `nesMemory` | `$6039` | niveau du premier emplacement d'équipe | lecture seule dans le prototype |
| `nesMemory` | `$609F-$60B1` | bitmap capturé, IDs 1–151, LSB-first | lecture seule dans le harness |
| `nesMemory` | `$60B3-$60C5` | bitmap vu, IDs 1–151, LSB-first | lecture seule dans le harness |
| `nesMemory` | `$60C8` | espèce sélectionnée, numéro 1-based | lecture seule dans le harness |
| `nesDebug` | `$0304` | coordonnée écran X du joueur (OAM shadow) | lecture seule |
| `nesDebug` | `$0306` | coordonnée écran Y du joueur (OAM shadow) | lecture seule |

Preuves : `tools/mesen_pokedex_ram_probe.lua`,
`tools/mesen_campaign_house_exit_probe.lua`,
`tools/mesen_fm3_early_campaign_trace.lua` et
`tools/pokemon_save_layout.py`.

## Auto-test dans Mesen

Le scénario `mesen_framework_smoke.lua` teste la reprise après timeout, les
relâchements de manette, les deux modes mémoire, la liste blanche et les plans
151/159. Il n'écrit jamais dans la mémoire du jeu.

```powershell
.\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\build\final-complete-fr-20260728-extended-clean\Pokemon_Jaune_FR_complete.nes `
  -ScriptPath .\tools\campaign\mesen_framework_smoke.lua `
  -OutputDirectory .\build\campaign-framework-smoke-42a0d940-dendy-strict-full-debug `
  -Region Dendy `
  -ExpectedEffectiveRegion Dendy `
  -ExpectedMarker POKEMON_CAMPAIGN_FRAMEWORK_PASS `
  -StrictHardware `
  -FullDebug
```

Pour intégrer une route, appeler `inputQueue:tick()` depuis
`emu.eventType.inputPolled`, puis `engine:tick()` une fois par
`emu.eventType.endFrame`. La fonction `recovery` d'une étape doit appeler
`inputQueue:abort()` avant de repositionner ou de réessayer.

## Route manette prouvée

Le prototype attend les signatures PPU de la chambre (`E8ABD336`), du
rez-de-chaussée (`E9D58C68`), du premier extérieur (`DD441740`) et du
laboratoire (`7FFE1D9C`). Il contourne la table de la maison, parcourt le
couloir est de Bourg Palette par douze impulsions prouvées, déclenche Chen,
avance la capture et le retour au laboratoire, puis interagit avec la balle.

L'obtention de Pikachu n'est pas déduite de l'image : elle est exigée en
lecture seule dans l'équipe persistante (`count=01`, `species=19`, `level=05`,
où `$19` vaut le numéro national 25). Le combat imposé contre Régis exige
ensuite une signature d'écran de combat, la signature de victoire
`00A7ECFE` (« Pikachu 45 Exp. gagnée ! »), le retour durable au laboratoire,
puis 120 images stables dehors après la porte.

```powershell
$rom = '.\build\final-complete-fr-20260728-extended-clean\Pokemon_Jaune_FR_complete.nes'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
foreach ($region in @('Dendy', 'Ntsc', 'Pal')) {
  $slug = $region.ToLowerInvariant()
  .\tools\run-mesen-pokemon-scenario.ps1 `
    -RomPath $rom `
    -ScriptPath .\tools\campaign\mesen_campaign_prototype.lua `
    -OutputDirectory ".\build\campaign-prototype\oak-pikachu-rival-exit-final-42a0d940-$slug-replay-$tag" `
    -Region $region `
    -ExpectedEffectiveRegion $region `
    -ExpectedMarker POKEMON_CAMPAIGN_PROTOTYPE_PASS `
    -StrictHardware `
    -FullDebug `
    -TimeoutSeconds 240
}
```

Sur la ROM SHA-256
`42a0d940d2d93742b00bf5812562d31286093747781aebc8a57e5c63821303e7`,
la preuve stricte se termine dehors devant le laboratoire, en `(80,70)` et
avec la signature `451EA43C` :

- Dendy : **PASS** à l'image 10 545 ;
- NTSC : **PASS** à l'image 10 575 ;
- PAL : un **PASS** à l'image 10 545, puis un **FAIL** à l'image 14 931 avec
  le même Lua et les mêmes profils.

Les trois marqueurs PASS annoncent `endpoint=outside_lab_stable`,
`mode=controller`, `writes_to_game=0` et `retries=0`. Chaque dossier contient
les captures PNG, le journal complet des états, les coordonnées et l'équipe à
chaque jalon, le nametable extérieur initial et un journal d'écritures mémoire
vide, hormis son en-tête. Les fichiers de preuve sont écrits sur l'hôte ; le
jeu n'est piloté que par `emu.setInput`.

Sous PAL, la route est donc possible, mais la stratégie du bot n'est pas
robuste aux états de mise sous tension randomisés du profil strict pendant le
combat. Les
manifests autoportants sont les dossiers suffixés
`pal-strict-full-debug-manifest-v2` (PASS) et
`pal-strict-full-debug-manifest-v3` (FAIL). Une ancienne tentative temporaire
suffixée `attempt3` a été annulée et n'est pas la version canonique.
La commande ci-dessus crée volontairement un nouveau dossier `replay-*` :
elle ne remplace donc aucun de ces manifests canoniques et son run PAL peut
reproduire l'un ou l'autre résultat.
La suite générale de régression
`build/r/42a0d940-current-runner/run-20260728T213001Z-b669c855/regression_suite_manifest.txt`
passe **42/42** (16 contrôles statiques et 26 étapes Mesen), PAL inclus :
cette non-robustesse du combat est une limite du bot, pas un crash prouvé de
la ROM.

Ce prototype ne termine pas le jeu, ne parcourt pas toutes ses branches et ne
prouve aucune série de 151 captures naturelles. Les preuves antérieures
`80310612` et `5b479227` restent documentées séparément dans
`EVIDENCE_OAK_LAB_FR.md`.

Les constantes dépendantes du rendu de cette ROM sont groupées au début de
`mesen_campaign_prototype.lua` afin de pouvoir les recalibrer après une
reconstruction : signatures de chambre/maison/extérieur/laboratoire/victoire,
nombre d'impulsions à Bourg Palette et coordonnées de la balle.
