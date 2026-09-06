# Preuve contrôleur-only : Chen, Pikachu, Régis et sortie du laboratoire

Date : 28 juillet 2026

> Ce document conserve la preuve historique `42a0d940`. La même route a été
> revalidée sur la remise actuelle
> `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`
> en Dendy, NTSC et PAL ; les manifests courants sont sous
> `build/runtime-proof-final-1fefecbf-core-normal/run-20260809T163735Z-ba4e9771/`
> et leur synthèse figure dans `RAPPORT_RELEASE_2026-08-09.md`.
> Cette revalidation reste un prototype limité, pas une campagne complète ;
> le diagnostic Route 1 séparé s'arrête avec `parcel_route_done=false`.
> Le manifeste normal porte `Bootstrap completion gate: False`. L'ancien
> bootstrap `947d8221…` n'est plus qu'une preuve transitoire historique.

## Périmètre

Cette preuve couvre un démarrage à froid jusqu'à la sortie stable du
laboratoire de Chen :

1. nouvelle partie ;
2. sortie de la maison ;
3. déclenchement de Chen au nord de Bourg Palette ;
4. capture cinématique et retour au laboratoire ;
5. obtention réelle de Pikachu ;
6. victoire dans le combat imposé contre Régis ;
7. sortie stable du laboratoire.

Le script n'appelle que `emu.setInput` pour agir sur le jeu. Il ne contient
aucune écriture mémoire, aucun chargement de savestate, aucun rewind et aucun
cheat.

## Revalidation sur la ROM finale `42a0d940` — 28 juillet 2026

La route a été rejouée sur la ROM finale de SHA-256
`42a0d940d2d93742b00bf5812562d31286093747781aebc8a57e5c63821303e7`,
avec `StrictHardware` et `FullDebug`.

| Région | Verdict campagne | Image terminale | État | Dossier de preuve |
|---|---|---:|---|---|
| Dendy | **PASS** | 10 545 | `outside_lab_stable` | `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-dendy-strict-full-debug-manifest-v2` |
| NTSC | **PASS** | 10 575 | `outside_lab_stable` | `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-ntsc-strict-full-debug-manifest-v2` |
| PAL, run 1 | **PASS** | 10 545 | `outside_lab_stable` | `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-pal-strict-full-debug-manifest-v2` |
| PAL, run 2 | **FAIL** | 14 931 | timeout dans `complete_rival_battle` | `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-pal-strict-full-debug-manifest-v3` |

Les marqueurs des trois succès attestés sont :

```text
POKEMON_CAMPAIGN_PROTOTYPE_PASS mapper=163 region=Dendy frames=10545 endpoint=outside_lab_stable nametable=451EA43C x=80 y=70 mode=controller writes_to_game=0 retries=0
POKEMON_CAMPAIGN_PROTOTYPE_PASS mapper=163 region=Ntsc frames=10575 endpoint=outside_lab_stable nametable=451EA43C x=80 y=70 mode=controller writes_to_game=0 retries=0
POKEMON_CAMPAIGN_PROTOTYPE_PASS mapper=163 region=Pal frames=10545 endpoint=outside_lab_stable nametable=451EA43C x=80 y=70 mode=controller writes_to_game=0 retries=0
```

Ces trois parcours réussis sont exclusivement pilotés par la manette virtuelle. Leurs
journaux d'écritures ne contiennent que l'en-tête. Ils prouvent le périmètre
décrit jusqu'à la sortie stable du laboratoire en Dendy, NTSC et au moins un
run PAL, mais ni la fin du jeu, ni toutes ses branches, ni 151 captures
naturelles.

Commande de reproduction Dendy/NTSC dans de nouveaux dossiers :

```powershell
$rom = '.\build\final-complete-fr-20260728-extended-clean\Pokemon_Jaune_FR_complete.nes'
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
foreach ($region in @('Dendy', 'Ntsc')) {
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

Cette commande n'écrase pas les preuves canoniques `manifest-v2`. Un replay
PAL doit lui aussi recevoir un nouveau dossier ; il peut reproduire le PASS ou
le FAIL documenté ci-dessous.

## Instabilité PAL du prototype

Le même Lua canonique SHA-256 `6849701b…` a donné successivement :

- un PASS dans `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-pal-strict-full-debug-manifest-v2` ;
- un FAIL dans `build/campaign-prototype/oak-pikachu-rival-exit-final-42a0d940-pal-strict-full-debug-manifest-v3`.

Le marqueur du run échoué est :

```text
POKEMON_CAMPAIGN_PROTOTYPE_FAIL frame=14931 state=complete_rival_battle reason=recovery budget exhausted: state complete_rival_battle timed out after 7200 frames
```

Les manifests lient tous les deux ROM, Mesen, profils, Lua et quatre modules
par SHA-256 avant/après. Les anciens échecs identiques et la tentative
temporaire annulée restent archivés, mais ces deux nouveaux runs suffisent à
établir que la route PAL est possible sans prouver une stratégie robuste aux
états de mise sous tension randomisés du profil strict.

Le run FAIL est bien demandé et configuré en PAL. Son champ
`Expected effective region observed: False` signifie seulement que le marqueur
d'échec n'imprime pas `region=Pal` ; il ne constitue pas une observation d'un
autre timing.

La suite générale de régression de la même ROM passe **42/42**
(16 contrôles statiques et 26 étapes Mesen), y compris ses étapes PAL,
avec matériel strict et tous les arrêts de débogage :
`build/r/42a0d940-current-runner/run-20260728T213001Z-b669c855/regression_suite_manifest.txt`.
Cette suite ne joue pas le combat contre Régis. L'alternance PASS/FAIL est
donc une limite prouvée de robustesse du prototype au combat PAL, et non la
preuve d'un crash de la ROM.

## Preuve précédente conservée — remise `80310612`

La remise précédente avait atteint `outside_lab_stable` en Dendy à l'image
10 545, avec `writes_to_game=0` et `retries=0`, dans
`build/campaign-prototype/oak-pikachu-rival-exit-final-80310612-dendy-strict-full-debug`.
Elle reste une preuve historique distincte et ne remplace pas les exécutions
de `42a0d940`.

Les sections suivantes conservent sans les réécrire les paramètres, jalons et
artefacts de l'ancien snapshot `5b479227`. Elles constituent une autre preuve
historique et ne doivent pas être citées comme une exécution sur la remise
`42a0d940`.

## Preuve historique — environnement `5b479227`

- ROM : `Pokemon_Jaune_FR_repacked_title.nes`
- SHA-256 :
  `5b479227c614428226a1d2a201435734fad6afed7d9e0a38c6b9857f2ad5f3ac`
- mapper iNES : 163, CHR-RAM
- Mesen : 2.2.1
- SHA-256 de l'exécutable Mesen :
  `8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7`
- région demandée et effective : Dendy
- base de données Mesen : désactivée
- profil matériel strict : activé
- profil `FullDebug` : activé
- sauvegardes et savestates : dossiers isolés et vides au départ

Commande historique :

```powershell
.\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\build\archive\pre-complete-5b479227\Pokemon_Jaune_FR_repacked_title.nes `
  -ScriptPath .\tools\campaign\mesen_campaign_prototype.lua `
  -OutputDirectory .\build\campaign-prototype\oak-pikachu-rival-exit-final-5b479227-dendy-strict-full-debug `
  -Region Dendy `
  -ExpectedEffectiveRegion Dendy `
  -ExpectedMarker POKEMON_CAMPAIGN_PROTOTYPE_PASS `
  -StrictHardware `
  -FullDebug `
  -TimeoutSeconds 240
```

Marqueur terminal observé :

```text
POKEMON_CAMPAIGN_PROTOTYPE_PASS mapper=163 region=Dendy frames=10545 endpoint=outside_lab_stable nametable=451EA43C x=80 y=70 mode=controller writes_to_game=0 retries=0
```

## Jalons observés dans l'exécution historique `5b479227`

| Image | Jalon | Signature PPU | X | Y | Équipe |
| ---: | --- | ---: | ---: | ---: | --- |
| 3 351 | arrivée au rez-de-chaussée | `E9D58C68` | `C0` | `20` | vide |
| 3 935 | dehors, vue initiale stable | `DD441740` | `80` | `70` | vide |
| 4 032 | couloir est aligné | `FB4BC18C` | `80` | `70` | vide |
| 4 316 | Chen déclenché | `E25FC43C` | `80` | `30` | vide |
| 6 315 | contrôle rendu au laboratoire | `7FFE1D9C` | `80` | `70` | vide |
| 6 383 | joueur aligné sur la balle | `7FFE1D9C` | `B0` | `62` | vide |
| 7 293 | Pikachu obtenu | `7FFE1D9C` | `80` | `60` | `01 / 19 / 05` |
| 7 730 | Régis déclenché | `EB49BC40` | `80` | `90` | Pikachu niv. 5 |
| 7 971 | combat Régis actif | `E27B64D2` | `80` | `90` | Pikachu niv. 5 |
| 9 815 | victoire : « 45 Exp. gagnée ! » | `00A7ECFE` | `80` | `90` | Pikachu niv. 5 |
| 10 285 | retour stable au laboratoire | `7FFE1D9C` | `80` | `90` | Pikachu niv. 5 |
| 10 545 | dehors devant le laboratoire | `451EA43C` | `80` | `70` | Pikachu niv. 5 |

`01 / 19 / 05` signifie une créature dans l'équipe, espèce interne `$19`
(décimal 25, Pikachu), niveau 5. Ces octets sont seulement lus aux adresses
`$6030`, `$6033` et `$6039`.

Le port NES attribue ici 45 points d'expérience, insuffisants pour le niveau
6 ; le niveau restant à 5 n'est donc pas un échec. La victoire est prouvée
séparément par l'écran « Pikachu 45 Exp. gagnée ! », puis par l'écran de
récompense et le retour au laboratoire.

## Artefacts historiques `5b479227`

Le dossier
`build/campaign-prototype/oak-pikachu-rival-exit-final-5b479227-dendy-strict-full-debug`
contient :

- quinze captures `00_...png` à `14_...png` ;
- `campaign_prototype_route.tsv`, source du tableau ci-dessus ;
- `campaign_prototype_journal.tsv`, transitions et succès de chaque état ;
- `campaign_prototype_memory_writes.tsv`, réduit à son en-tête : aucune
  écriture ;
- `mesen_run_manifest.txt`, paramètres, hash avant/après et résultat ;
- `mesen.stdout.txt` et `mesen.stderr.txt`.

Pour cette exécution historique, le hash ROM avant et après est identique. Le
journal ne contient aucune récupération et le marqueur annonce `retries=0`.

## Origine et recalibrage de la route

Le FM3 contrôleur-only original de 43 160 images a été relu avec
`tools/mesen_fm3_early_campaign_trace.lua`. Il établit la topologie du début
de partie sans imposer ses timings à la traduction française : douze
impulsions vers l'est, montée vers Chen, balle à droite dans le laboratoire,
puis descente vers Régis.

Le prototype français attend ensuite ses propres états au lieu de rejouer les
numéros d'image du FM3. Les valeurs à recalibrer après une reconstruction de
la ROM sont regroupées au début de `mesen_campaign_prototype.lua` :
signatures PPU, nombre d'impulsions du couloir est et coordonnées de la balle.
