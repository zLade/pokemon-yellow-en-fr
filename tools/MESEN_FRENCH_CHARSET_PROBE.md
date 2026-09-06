# Preuve Mesen exhaustive du charset français

Le probe `mesen_intro_french_accents_probe.lua` couvre les 16 glyphes natifs
du build français :

`À Â É Î Ç à â ç è é ê î ï ô ù û`

Le `é` utilise la tuile `@` déjà fournie par la base anglaise ; les 15 autres
tuiles sont produites par `tools/french_font.py`. `œ` reste volontairement
encodé `oe` et ne fait donc pas partie des glyphes natifs.

## Mode assisté, sans modification du fichier ROM

Le probe localise l'enregistrement canonique d'introduction issu de
`p(0x035E82, ...)`, même si le repacking l'a déplacé. Dans la mémoire PRG-ROM
chargée par Mesen uniquement, il remplace temporairement cet enregistrement
de 104 octets par un enregistrement diagnostique de même longueur. Les
16 glyphes tiennent sur la seconde ligne de la première page.

Cette substitution change exactement 91 octets dans l'image émulée. Elle ne
touche ni le fichier `.nes`, ni la RAM CPU, ni la PPU, ni les registres mapper,
ni la sauvegarde. L'enregistrement original est restauré et relu avant que le
probe puisse produire un résultat `PASS`. Le manifeste de lancement du runner
vérifie séparément que le SHA-256 du fichier ROM est identique avant et après
l'exécution.

Il s'agit donc d'une preuve runtime assistée et explicitement déclarée comme
telle, pas d'une preuve de progression `controller-only`.

## Assertions runtime

Pour chaque glyphe, le probe exige sur la même page terminée :

1. la lecture par le CPU de son octet encodé dans l'enregistrement ;
2. la correspondance exacte des 16 octets de sa tuile dans la ROM ;
3. la lecture des 8 lignes bitmap réellement consommées par le moteur ;
4. au moins 32 écritures PPU `$2007` après cette lecture ;
5. les deux IDs de tuiles générés dans chacune des deux nametables miroir.

Il exige également la lecture des 104/104 octets diagnostiques, la capture des
trois pages et la restauration vérifiée de l'enregistrement original.

Les attentes générées depuis le codec et la police canoniques se trouvent dans
`tools/data/mesen_french_charset_probe_expected.json`. Le test
`tools/test_mesen_french_charset_probe.py` empêche le probe Lua, le manifeste,
le texte d'introduction et `french_font.py` de diverger silencieusement.

## Artifacts attendus

- `french_charset_exhaustive_validation.txt`
- trois captures `french_charset_exhaustive_page_*_frame_*.png`
- pour chaque page : CHR-RAM, espace PPU, nametables, palette et OAM
- `mesen.stdout.txt`, `mesen.stderr.txt` et `mesen_run_manifest.txt` du runner

Le marqueur de succès est :

`POKEMON_FRENCH_CHARSET_EXHAUSTIVE_PASS`

## Exécution future

La ROM doit d'abord avoir été reconstruite avec le charset étendu. Le probe
échoue avant toute substitution si une seule tuile ne correspond pas au
manifeste.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath Pokemon_Jaune_FR_repacked_title.nes `
  -ScriptPath tools\mesen_intro_french_accents_probe.lua `
  -OutputDirectory build\emulator-runs\french-charset-exhaustive-ntsc `
  -Region Ntsc `
  -ExpectedMarker POKEMON_FRENCH_CHARSET_EXHAUSTIVE_PASS `
  -StrictHardware `
  -FullDebug `
  -TimeoutSeconds 120
```

La suite complète appelle ce même probe en Dendy, NTSC et PAL. Aucun résultat
runtime n'est revendiqué tant que ces exécutions n'ont pas effectivement été
lancées sur la ROM reconstruite.
