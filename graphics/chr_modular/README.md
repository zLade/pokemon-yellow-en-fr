# Pack CHR modulaire — Pokémon Jaune NES

Ce dossier permet de retoucher les graphismes chargés en CHR-RAM puis de
recompiler une ROM et un IPS sans modifier la ROM française source.

Le snapshot actif est exclusivement `22210785`. Il conserve le logo anglais
`YELLOW` et les choix français abrégés `NOUV` / `CONT`. Les snapshots
précédents `eeb4975e`, `5adcd8bf` (anciens textes français) et `42a0d940`
(logo `JAUNE`),
ainsi que les alias `manifest-current.json`, `pack-current/` et
`build/chr-modular-current/`, sont conservés pour l'historique et ne doivent
plus être utilisés.

## Où modifier

Modifier uniquement les fichiers sous `pack-22210785/work/` :

- `screens/title_screen/chr0.chr` : source du pattern table `$1000` du titre ;
- `screens/title_screen/chr1.chr` : source du pattern table `$0000` du titre ;
- `screens/title_screen/nametable.bin` et `palette.bin` : disposition et
  palette du titre ;
- `screens/player_menu/` : graphismes et disposition du menu joueur ;
- `screens/intro_professor/` et `screens/intro_player/` : portraits et écrans
  d'introduction ;
- `sprites/intro/pikachu.chr` : sprite de Pikachu de l'introduction ;
- `screens/overworld/` : page CHR observée en jeu dans la chambre ;
- `fonts/ui_ascii_font.chr` : police ASCII/UI ;
- `packages/b50/` à `packages/b62/` : 587 paquets de sprites et portraits
  NES 2 bpp, chacun dans son propre `.chr` ;
- `screen-packs/tilemap/` et `screen-packs/attributes/` : 416 dispositions
  d'écran 32×30 et leurs 416 tables d'attributs 8×8.

Le fichier `catalog-22210785.csv` donne pour chaque asset son offset, sa
taille, son SHA-256, sa banque, ses dimensions, son nombre de tuiles, sa
famille et sa politique de réinjection. Les paquets encore sans nom certain
restent numérotés par banque et index afin d'éviter de leur attribuer un
Pokémon ou un dresseur incorrect.

`screen-pack-catalog-22210785.json` conserve en plus les 96 structures
complètes des
banques d'écrans, y compris leurs pointeurs CHR dont la longueur n'est pas
prouvée statiquement. Ces pointeurs sont documentés mais ne sont pas compilés
comme de faux blocs 4 Kio.

## Format d'édition

Les `.chr` sont des tuiles NES brutes 8×8, 2 bits par pixel, 16 octets par
tuile. Conserver impérativement la taille exacte de chaque fichier. Ne pas
renommer, supprimer, ajouter ni redimensionner un asset.

Les PNG sous `pack-22210785/previews/` sont des aperçus monochromes de
l'export initial. Ils servent à repérer un fichier mais ne sont pas réinjectés
et ne se mettent pas à jour après une retouche. Les fichiers sous
`pack-22210785/baseline/` et `pack-22210785/pack.lock.json` sont les
références de sécurité : ne pas les modifier.

Certaines vues se chevauchent volontairement dans la ROM. Le compilateur
compare chaque fichier à sa baseline :

- un alias resté inchangé n'écrase pas une retouche ;
- deux alias proposant le même octet sont acceptés ;
- deux retouches contradictoires sur le même octet arrêtent la compilation
  avec l'offset et les deux assets concernés.

## Vérifier et compiler

Depuis PowerShell, à la racine du projet :

```powershell
.\tools\build-chr-modular.ps1 Diff
.\tools\build-chr-modular.ps1 Verify
.\tools\build-chr-modular.ps1 Roundtrip
.\tools\build-chr-modular.ps1 Compile
```

`Compile` produit par défaut pour le snapshot actif :

- `build\chr-modular-22210785\Pokemon_Jaune_FR_CHR_mod.nes`
- `build\chr-modular-22210785\Pokemon_Jaune_FR_CHR_mod.ips`
- `build\chr-modular-22210785\compile-report.json`

Le rapport énumère les octets réellement modifiés, leurs plages physiques,
les hashes de chaque asset et l'aller-retour IPS. La ROM source
`Pokemon_Jaune_FR_repacked_title.nes` n'est jamais écrasée.

Sur le pack `22210785`, `Diff`, `Verify`, `Roundtrip` et `Compile` réussissent.
Sans retouche, les sorties sous `build\chr-modular-22210785` sont identiques
bit à bit aux
artefacts canoniques :

- ROM SHA-256 :
  `22210785ca066222b47cb255c5beeeeff7f0276439e57d65ff884c9bc9cd6298` ;
- IPS SHA-256 :
  `d2745b6bcda2a8ff9d7ca33815b024719df1cba282c07dbf9cc643ffc882cdf3`.

L'action `Export` refuse de s'exécuter si le dossier cible existe déjà afin de
ne pas effacer des retouches. Pour chaque future ROM, générer un manifeste
versionné et choisir un nouveau dossier `pack-<sha>/` avec `-ManifestPath` et
`-PackPath`. Le pack `22210785` livré ne doit donc pas être réexporté
par-dessus.

Le couple actif `manifest-22210785.json` / `pack-22210785/` contient les
16 glyphes français et 1 489 assets. Tous les couples `current`, `5adcd8bf`,
`42a0d940`, `80310612`, `ae22c291`, `eeb4975e` ou sans suffixe sont des snapshots
historiques laissés intacts.

## Contrôle Mesen après une retouche

Toujours tester la ROM compilée dans Mesen avec `StrictHardware` et
`FullDebug`. Le mapper 163 emploie de la CHR-RAM et échange les deux moitiés
physiques de 4 Kio à la scanline 127 ; une planche statique ne suffit donc pas.

Le validateur canonique attend les cinq tuiles anglaises de `YELLOW` et les
sept tuiles françaises de `NOUV` / `CONT`. Le probe
`tools\mesen_title_en_menu_fr_probe.lua` les compare octet par octet dans la
CHR-RAM réellement chargée, avec leurs tilemaps. Après une retouche
volontaire, les hashes peuvent logiquement changer : le rapport du pipeline
prouve alors la portée du patch, et les scénarios Mesen doivent être contrôlés
visuellement en Dendy, NTSC et PAL.

## Périmètre connu

Le manifeste contient 1 489 assets : 625 CHR et 864 blocs de disposition ou
d'attributs. Les 587 paquets autonomes représentent 22 790 tuiles
(`0x59060` octets CHR).

La police chinoise HZK16 à `0x040010` n'est pas exportée en `.chr` : ses plans
1 bit sont scindés et entrelacés, ce n'est pas un flux NES 2 bpp directement
réinjectable. Les textes français utilisent la police traduite ; exposer
HZK16 comme un faux `.chr` risquerait de corrompre les glyphes.
