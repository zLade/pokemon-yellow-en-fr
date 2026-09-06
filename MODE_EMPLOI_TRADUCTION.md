# Mode d'emploi - traduction FR et validation mapper 163

## État remis — release finale v2 du 9 août 2026 (`1fefecbf`)

Cette section décrit les fichiers canoniques actuellement placés à la racine.

- ROM finale : `Pokemon_Jaune_FR_repacked_title.nes`, SHA-256
  `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`.
- Patch BPS recommandé depuis la ROM chinoise originale :
  `Pokemon_Jaune_FR_repacked_title_from_chinese.bps`,
  SHA-256
  `0a1988e744d7ef4dbf2c172b34973015b8777a0ce498a3b165b59a9825ed1d22`.
  Sa base exclusive est
  `Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes`, SHA-256
  `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed`.
- Patch BPS alternatif depuis la reconstruction anglaise 2015 :
  `Pokemon_Jaune_FR_repacked_title_from_english.bps`,
  SHA-256
  `01d1c0cd27d361cfa7fb91623348d63613a14a2dc1ed344bb92c1ca2b6f7f9f7`.
  Sa base exclusive est `Pokemon Yellow English 9-23-2015.nes`, SHA-256
  `d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac112509d658a9943b`.
- Patch IPS de compatibilité, également basé exclusivement sur `yellow.nes` :
  `Pokemon_Jaune_FR_repacked_title.ips`, SHA-256
  `912d9feaf7278f1cf0d139e4805360ad6d2232b68f98f9f9ac8e7e9bca9e5c29`.
- 1 844 entrées sont compilées : 970 dialogues principaux relus à partir du
  chinois et 85 dialogues chinois restaurés, soit 1 055 lignes dans la table
  exhaustive de relecture. Tous ont une adaptation française éditoriale.
- La source canonique `script.py` a le SHA-256
  `e870f48105bd570d8323bf0c9358b95dbe5e59e6557214196a547cfedcb56180`
  et le CSV maître `traduction_base.csv` le SHA-256
  `a4932263753587b744cf3cc614f884c8754e95fec5b486f88c951adf242be803`.
- Le builder refuse un état éditorial différent : il épingle aussi
  `traductions_trop_longues.csv` (`561ff1e5…`), la naturalisation principale
  (`923a9d3b…`), la fidélité chinoise (`0761b3f1…`) et la naturalisation des
  restaurations (`5cbb41c9…`) avant le build.
- La priorité des sources françaises est : Pokémon Jaune officiel lorsque la
  scène correspond réellement, texte officiel commun à Rouge/Bleu/Jaune,
  adaptation naturelle du chinois, puis anime français en dernier recours.
- Les noms officiels français de la série sont conservés. Les particularités
  du bootleg chinois restent présentes : Nanjing, Kameiyu, Beibei, Hoenn,
  Johto et les caméos de l'équipe de développement.
- L'inventaire contient exactement 17 dialogues de caméo ou de mention des
  créateurs, dont les deux répliques de Beibei. La récompense de Pierre est
  corrigée en `CT35 reçue !`, conformément aux données exécutables et au
  dialogue chinois.
- Les 970 dialogues principaux sont rattachés à une source chinoise de
  confiance `high`; les 85 restaurations utilisent leur `source directe`.
- Le repacking place 1 819 textes ordinaires et 85 restaurations sans échec
  d'allocation, conflit de pointeur, chevauchement incompatible, dépassement
  fixe ni avertissement. Il reste 51 octets dans la paire PRG 6 (plus grand
  bloc : 11) et 135 dans la paire PRG 7 (un bloc de 135). Les planchers
  40/4 et 128/128 sont respectés ; le rapport prouve que 11 octets est la
  borne maximale du plus grand bloc possible dans la paire 6 pour ce corpus.
- Les 967 dialogues de terrain produisent 2 518 pages après optimisation :
  zéro mot coupé et zéro frontière grammaticale forte. Avec les trois
  dialogues d'introduction, le validateur compte 2 530 bulles et conserve le
  layout 17/19 propre à l'introduction.
- Les contrôles mapper 163, Pokédex 159/159, accents et qualité ambitieuse
  passent. Le core normal post-release découvre 50 modules et exécute 399
  tests avec `OK`, sans échec ni saut. Le journal terminal a le SHA-256
  `09a254e66c0445452d8711299b8398ceb6205552ee8a1c20d4f2e37753aef3a6`.
- Le gate final agrège 13 contrôles, dont le `--check` des 12 dérivés de
  fidélité, le manifeste de pointeurs v2 recoupé avec ses 1 912 références
  canoniques et le diagnostic Mesen de sauvegarde corrompue dans trois
  régions.
- La régression Mesen complète est `PASS` en Dendy, NTSC et PAL : 45 étapes,
  dont boot, mapper 163 passif, introduction, caractères français, CHR,
  menu, prototype limité de campagne et batterie. Le diagnostic Route 1 /
  Jadielle est aussi `PASS` dans les trois régions, sans écriture du scénario
  dans la RAM du jeu, sous
  `build/runtime-proof-final-1fefecbf-route1/`. Sa portée est strictement
  `route1_viridian_alignment_only` : `parcel_route_done=false` et aucun
  dialogue n'y est attesté. La matrice 3/3 (196 captures) a le SHA-256
  `e6dd8433056a1f710d83c1f5014f512a007e704bda47fbf3ca1a6edd3b426dc8`.
- Un diagnostic séparé observe de vraies lectures CPU de RAM non initialisée
  `$0161..$01C6` en Dendy. La routine est commune aux ROMs sources, mais le
  défaut reste `inherited_source_engine_quirk_unresolved` et son innocuité
  n'est pas prouvée (`harmlessness_not_proven`). Le diagnostic a le SHA-256
  `3d2ff9a11adaf9ad58a975bdfb85a6cad3c1515c66d7c126db5e9b3ea3e62099`.
- La sauvegarde corrompue a été sondée dans Mesen avec une fixture minimale
  d'un seul octet relatif `$0050` : restauration du primaire depuis le backup
  et rejet d'un backup corrompu vers le fallback, en Dendy, NTSC et PAL. Cela
  ne constitue pas une campagne complète de sauvegarde ni un fuzzing exhaustif.
  Les preuves Dendy/NTSC/PAL ont respectivement les SHA-256 `9427c130…`,
  `9af82e08…` et `c9b2b6fc…`.
- Le core normal 45/45 exact est
  `build/runtime-proof-final-1fefecbf-core-normal/run-20260809T163735Z-ba4e9771/regression_suite_manifest.txt`,
  SHA-256 `c75fc00b3ed9d4f3d73ecb01b5783469fba3fc7c89bde296b4e85e2ee7f85f66`.
  Il porte `Bootstrap completion gate: False`.
  Le prototype contrôleur-only termine aux images Dendy/NTSC/PAL
  10 700/10 110/10 835 avec `writes_to_game=0`.
- La validation sur une cartouche physique n'est pas simulée : utiliser
  `CHECKLIST_TEST_MATERIEL_MAPPER163.md` et conserver le statut `NON TESTÉ`
  jusqu'à une observation réelle.
- Le catalogue CHR lié à la ROM finale se trouve dans
  `build/chr-catalog/current-1fefecbf/` : 1 489 assets, 149 chevauchements
  déclarés et 853 648 octets placés en liste blanche. `Verify` et `Roundtrip`
  sont `PASS` et reproduisent le SHA exact `1fefecbf…`, sans octet changé.
- La table exhaustive couvre 1 055 dialogues. Son CSV a le SHA-256
  `68fe03318fdd447d5d9be6e1010a8369a796ca27ab52c466edf4cb8762493129`
  et son XLSX le SHA-256
  `4fc1679d864ac6daec38ccbef8a284c9136010b292275d0c3de23e51fc1ebc38`.
- Le rafraîchissement de fidélité, dérivé des extractions Unicode épinglées
  sans réextraire HZK16, confirme 80 suppressions anglaises restaurées sur 80,
  zéro réplique encore absente, 85 restaurations au total et 17 caméos.
- Lunar IPS 1.03 x64 et Floating IPS v198 reproduisent tous les trois la ROM
  cible depuis l'IPS et les deux BPS. La preuve 3/3 est
  `build/external-patcher-proof.json`, SHA-256 `3f53aace4f07fbed…`.
- La release reproductible, ses audits, son manifeste et tous les hashes se
  trouvent dans `build/release-2026-08-09-final-v2/`. Le bilan condensé est dans
  `RAPPORT_RELEASE_2026-08-09.md`.

Les deux BPS placés à la racine ont été comparés bit à bit avec leurs copies
dans le dossier de release ; ils sont identiques.

Les sections nommées « Historique » et les exemples qui portent un ancien
préfixe SHA (`1a5c689c`, `22210785`, `eeb4975e`, `42a0d940`, etc.) restent uniquement des
pistes d'audit. Ils ne remplacent ni les hashes ni les preuves de la présente
section.

## Historique — version 22210785 (29 juillet 2026)

Cette section décrit l'ancienne remise `22210785…`. Elle est conservée pour
l'historique et ne décrit plus les fichiers canoniques à la racine.

- ROM :
  `build/final-readable-dialogues-20260729/release/Pokemon_Jaune_FR.nes`,
  SHA-256
  `22210785ca066222b47cb255c5beeeeff7f0276439e57d65ff884c9bc9cd6298`.
- IPS :
  `build/final-readable-dialogues-20260729/release/Pokemon_Jaune_FR.ips`,
  SHA-256
  `d2745b6bcda2a8ff9d7ca33815b024719df1cba282c07dbf9cc643ffc882cdf3`.
- Base exclusive de cet IPS : `yellow.nes`, SHA-256
  `69520103102677b33b47c15fae804dc1a742347a9ee1b02a9195e795eb6e431b`.
- Traduction : 1 844 entrées maîtresses. Les 967 dialogues terrain produisent
  2 583 bulles de 19 caractères au maximum. Le contrôle exhaustif relève
  **0 mot coupé entre deux bulles**, **0 frontière grammaticale forte** et
  0 modification du sens pendant la remise en page. Les 3 dialogues
  d'introduction conservent leur layout spécifique 17 puis 19 caractères.
- Départ du jeu : Mesen a capturé et comparé exactement 36 bulles appartenant
  aux 6 scènes imposées, dont la mère au rez-de-chaussée, l'avertissement de
  Chen à Bourg Palette et son discours initial au laboratoire. Résultat :
  `POKEMON_EARLY_DIALOGUE_BOUNDARY_PASS`, sans écriture du scénario dans la
  RAM du jeu.
- Route 1 et Jadielle : le parcours NTSC atteint Jadielle en 7 108 frames,
  avec 79 points de contrôle, une récupération de combat et 0 écriture du
  scénario dans la RAM du jeu. Résultat :
  `POKEMON_FM3_ROUTE1_VIRIDIAN_TRACE_PASS`.
- Pokédex : 151/151 descriptions accessibles et 8 descriptions étendues en
  `pokedex_13x4`, soit 159 layouts validés, sans césure de mot.
- Cohérence et couverture statiques : 208/208 tests Python réussissent. Les
  audits de qualité, d'accents, de couverture ASCII et des blocs graphiques
  sont `PASS`. Aucun accent certain, contextuel ou ambigu ne reste signalé.
- Mystère des anciens « 317 blocs chinois » : l'inventaire final contient
  321 records, car 4 records étendus ont été ajoutés au contrôle. Les
  303 records porteurs de langage ont tous une traduction française déclarée
  et les 18 autres sont des pictogrammes neutres relus. Les 153 occurrences
  qui utilisent encore un code de la police source se trouvent à l'intérieur
  de records français contrôlés ; elles ne représentent donc pas
  153 dialogues chinois restants. Il ne reste aucun record linguistique non
  classé ou déclaré non traduit.
- Police : 16 glyphes français natifs sur un octet
  (`À Â É Ç Î é ç î ï ô ù û à è ê â`) ; 15 tuiles sont patchées et `é`
  réutilise le glyphe `@` anglais.
- Écran titre : le logo anglais original `YELLOW` est restauré depuis
  `Pokemon Yellow English 9-23-2015.nes`; les choix restent français sous
  leur forme graphique contrainte `NOUV` / `CONT`. Le menu joueur séparé
  reste `OBJETS` / `SACHA` / `CS` / `SAUVER`.
- Le probe linguistique du titre est `PASS` dans Mesen en Dendy, NTSC et PAL,
  chaque fois sous `StrictHardware + FullDebug`; il vérifie octet par octet
  `YELLOW` et `NOUV` / `CONT` dans la CHR-RAM active.
- Pack CHR actif :
  `graphics/chr_modular/manifest-22210785.json` avec
  `graphics/chr_modular/pack-22210785/`, soit 1 489 assets. `Diff`, `Verify`,
  `Roundtrip` et `Compile` sont `PASS`; leurs rapports se trouvent dans
  `build/chr-modular-22210785/` et dans le dossier de remise. Une compilation
  sans retouche reproduit exactement la ROM et l'IPS canoniques.
- Les noms canoniques à la racine étaient synchronisés avec cette remise :
  `Pokemon_Jaune_FR_repacked.*` et `Pokemon_Jaune_FR_repacked_title.*` sont
  bit à bit les mêmes artefacts `22210785…` et `d2745b6b…`. La ROM défectueuse
  `2c0b0362…`, qui appliquait une phase 17/19 incorrecte aux dialogues terrain,
  est conservée uniquement sous
  `build/archive/obsolete-2c0b0362-wrong-dialogue-phase/`.

Preuves principales :

- `build/final-readable-dialogues-20260729/release/audits/dialogue_page_quality_final_recheck.json` ;
- `build/final-readable-dialogues-20260729/release/audits/pokedex_layout.json` ;
- `build/final-readable-dialogues-20260729/release/audits/final_pokedex_runtime.json` ;
- `build/final-readable-dialogues-20260729/release/audits/pokedex_full_151.json` ;
- `build/final-readable-dialogues-20260729/release/audits/french_accents_final_recheck.json` ;
- `build/final-readable-dialogues-20260729/release/audits/quality_ambitious.csv` ;
- `build/final-readable-dialogues-20260729/release/audits/translation_coverage_ascii.txt` ;
- `build/final-readable-dialogues-20260729/release/audits/translation_coverage_glyphs.txt` ;
- `build/final-readable-dialogues-20260729/release/mesen/early-dialogues-dendy/mesen_run_manifest.txt` ;
- `build/final-readable-dialogues-20260729/release/mesen/route1-viridian-ntsc/mesen_run_manifest.txt` ;
- `build/final-readable-dialogues-20260729/release/mesen/title/dendy/mesen_run_manifest.txt` ;
- `build/final-readable-dialogues-20260729/release/mesen/title/ntsc/mesen_run_manifest.txt` ;
- `build/final-readable-dialogues-20260729/release/mesen/title/pal/mesen_run_manifest.txt` ;
- `AUDIT_COHERENCE_GEN1_GEN2_FR.md` ;
- `build/final-readable-dialogues-20260729/release/audits/chr_modular_verify.json` ;
- `build/final-readable-dialogues-20260729/release/audits/chr_modular_roundtrip.json` ;
- `build/final-readable-dialogues-20260729/release/chr-modular-build/compile-report.json`.

Limites : ces preuves ne signifient pas que toutes les branches et tous les
dialogues du jeu ont été parcourus manette en main. La couverture de toutes
les bulles est exhaustive mais statique ; l'exécution Mesen couvre le titre,
les 36 bulles critiques du départ, la Route 1 et l'arrivée à Jadielle. Il
n'existe pas encore d'essai sur une cartouche physique. Le profil PAL est un
timing PAL forcé dans Mesen et ne constitue pas une preuve sur console
française réelle. Le traceur Route 1 journalise 103 lectures de RAM
non initialisée entre `$0161` et `$01C7`, déjà identiques sur la construction
intermédiaire ; le profil de débogage complet reste activé et le manifeste
Mesen conclut néanmoins `PASS`.

La remise précédente `eeb4975e…` et toutes les notes qui la mentionnent plus
bas sont historiques : elles ne valident pas `22210785…`. La variante
`42a0d940…`, qui affichait `JAUNE`, reste sous
`build/final-complete-fr-20260728-extended-clean/`. La remise
`80310612…` est archivée sous `build/archive/pre-extended-clean-80310612/`.

## Historique — ancien artefact 5b479227 remplacé

Ce projet adapte en français le bootleg NES `Lei Dian Huang Bi Ka Qiu Chuan
Shuo (NJ046)`. Ce n'est pas la ROM Game Boy officielle de Pokémon Jaune.

Les valeurs suivantes décrivent l'ancien artefact `5b479227…`, désormais
archivé sous `build/archive/pre-complete-5b479227/`. Elles sont conservées
uniquement pour comprendre l'historique des commandes et ne décrivent plus les
fichiers canoniques à la racine :

- ROM : `Pokemon_Jaune_FR_repacked_title.nes`
- IPS : `Pokemon_Jaune_FR_repacked_title.ips`
- SHA-256 ROM :
  `5b479227c614428226a1d2a201435734fad6afed7d9e0a38c6b9857f2ad5f3ac`
- SHA-256 IPS :
  `75361f70ffdc76eab611f1df694dd10b7c001faac64545efaf7e1af2a58bfd77`
- SHA-256 CSV maître `traduction_base.csv` :
  `71c1d9231fd3c3ea7438256b31ccc5daa7e914111f95c9af7b1feab4a0c2df70`
- SHA-256 inventaire des frontières :
  `30e3d6439d65abc128d76b47f1463c4324971dbc3d17f3d90908a3ee6cec5f91`
- base de l'IPS final : `yellow.nes`

Les validations décrites ici établissent la reproductibilité de l'IPS, la
cohérence des pointeurs, le contrat matériel de la cartouche et le
fonctionnement des scénarios automatisés couverts. L'inventaire exhaustif
compte 317 records graphiques : 299 contiennent du langage et possèdent
désormais une traduction française déclarée ; 18 sont des pictogrammes
neutres relus. Ce bilan résout le statut linguistique des 317 blocs, mais ne
prouve pas l'accessibilité en jeu de chacun d'eux : un accès calculé ou par
enchaînement reste possible hors des pointeurs statiques recensés. Un parcours
humain complet reste utile pour juger le naturel de chaque dialogue en
contexte.

L'ancien artefact racine `fb1151dc...`, dont deux octets de queue de code
étaient corrompus, est conservé uniquement pour diagnostic dans
`build/quarantine/pre-final-v8/`. Il ne doit pas être flashé.

## Matériel émulé : mapper 163, pas mapper 30

Cette ROM utilise le mapper iNES **163**, implémentation Nanjing :

- PRG-ROM : 2 Mio, soit 64 banques commutables de 32 Kio ;
- CHR-ROM : 0 octet ;
- CHR-RAM : 8 Kio ;
- mirroring vertical ;
- batterie et save-RAM de 8 Kio ;
- aucun trainer iNES.

Le lanceur Mesen refuse une ROM qui n'annonce pas le mapper 163, 2 Mio de PRG
et l'absence de CHR-ROM. Le validateur statique contrôle le reste du contrat.
Les procédures mapper 30 du projet Poker ne doivent donc pas être réutilisées
telles quelles : registres, commutation de banques, initialisation et
hypothèses PPU ne sont pas les mêmes.

Le contrôle statique spécifique est :

```powershell
python tools\validate_mapper163.py --rom Pokemon_Jaune_FR_repacked_title.nes
```

Il vérifie notamment le header, le trampoline RESET utilisant
`$5300/$5000/$5200`, les vecteurs, les banques modifiées et l'absence de
CHR-ROM.

## ROM anglaise canonique et base de travail

Les deux ROM anglaises ont des rôles différents :

- `yellow.nes` est la cible canonique reconstruite exactement par l'IPS
  anglais appliqué à la ROM chinoise. C'est aussi la base de l'IPS final ;
- `Pokemon Yellow English 9-23-2015.nes` est une variante historique comportant
  des retouches graphiques. Elle reste la base de mesure des textes pour
  `dump-script`, `audit` et `build-repacked`.

Ne pas remplacer silencieusement l'une par l'autre. Les commandes `check` et
`check-ips` rendent cette provenance explicite.

## Fichiers importants

- `script.py` : source maîtresse des chaînes françaises `p(offset, texte)`.
- `rom_traduction_assistant.py` : provenance, extraction CSV, audit et builds.
- `traduction_base.csv` : extraction courante des entrées de `script.py`.
- `traductions_trop_longues.csv` : textes dépassant leur emplacement source.
- `textes_fixes_trop_longs.csv` : libellés non repointables encore trop longs.
- `tools/validate_repacked.py` : validation des allocations et des pointeurs.
- `tools/validate_mapper163.py` : validation du contrat matériel mapper 163.
- `tools/dialogue_layout.py` : mise en page sémantique des dialogues communs
  en 19 × 19 colonnes et des trois dialogues d'introduction en 17 colonnes
  sur la première ligne, puis 19.
- `tools/dialogue_inventory.py` : application de l'inventaire exhaustif des
  frontières de mots historiques.
- `tools/data/dialogue_boundary_inventory.json` : inventaire versionné des
  frontières, espaces implicites et césures à corriger.
- `tools/validate_dialogue_layout.py` : validation exhaustive de la mise en
  page ; son rapport par défaut est
  `build/audits/dialogue_layout_validation.json`.
- `tools/validate_pokedex_layout.py` : validation sémantique des 151+8
  descriptions en quatre lignes de 13 colonnes.
- `tools/validate_final_pokedex_runtime.py` : déréférence les 159 pointeurs de
  la ROM compilée et compare exactement payloads et terminateurs à
  `script.py`.
- `tools/french_font.py` : codec français, tuiles `à`, `è`, `ê` et exports
  CHR avant/après de la police.
- `tools/audit_quality_ambitious.py` : audit linguistique heuristique.
- `tools/title_screen_tools.py` : patch graphique, exports CHR et rendus BMP.
- `tools/test_title_screen_tools.py` : tests des tuiles et des plages
  graphiques réservées.
- `tools/generate_chr_asset_manifest.py` : catalogue reproductible des sources
  graphiques en PRG-ROM.
- `tools/screen_pack_catalog.py` : inventaire strict des tilemaps et attributs
  des banques d'écrans.
- `tools/chr_asset_pipeline.py` : export, vérification et recompilation des
  assets CHR avec gestion des chevauchements.
- `tools/build-chr-modular.ps1` : wrapper PowerShell du pack
  `graphics\\chr_modular`.
- `tools/run-mesen-pokemon-scenario.ps1` : lance un scénario isolé dans Mesen.
- `tools/run-mesen-battery-persistence.ps1` : suite de persistance batterie.
- `tools/run-mesen-pokemon-regression-suite.ps1` : suite statique et Mesen
  Dendy/NTSC/PAL complète.
- `tools/mesen_mapper163_boot_probe.lua` : démarrage passif.
- `tools/mesen_pokemon_intro_probe.lua` : titre, menu et séquence d'introduction.
- `tools/mesen_pokemon_intro_prompt_probe.lua` : captures de dialogues stabilisés.
- `tools/mesen_mapper163_runtime_probe.lua` : activité des registres Nanjing.
- `tools/mesen_chr_export_probe.lua` : exports CHR-RAM/PPU/nametable/OAM en direct.
- `tools/mesen_title_en_menu_fr_probe.lua` : vérification exacte du logo
  anglais `YELLOW` et des choix français `NOUV` / `CONT` en CHR-RAM live.
- `tools/mesen_player_menu_french_probe.lua` : contrôle graphique en direct du
  menu joueur français.

## Mesen 2.2.1 exact

La référence utilisée est :

- exécutable :
  `..\mesen\portable-2.2.1\Mesen.exe`
- version des réglages : `2.2.1`
- SHA-256 :
  `8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7`

`run-mesen-pokemon-scenario.ps1` vérifie ce hash avant chaque exécution. Par
défaut, il utilise l'installation commune située à la racine dans
`..\mesen\portable-2.2.1`, crée des dossiers de sauvegardes et de savestates
isolés sous la sortie du test, désactive le chargement automatique d'IPS et
restaure les réglages après le test. Le manifeste enregistre les hashes
avant/après.

### Profils matériels et debug

Les tests de validation finale utilisent toujours les deux options :

```powershell
-StrictHardware -FullDebug
```

`StrictHardware` active la dégradation OAM, la corruption de ligne OAM, les
glitches PPU `$2000/$2006`, la restriction d'accès PPU de la première frame,
l'état mapper aléatoire, l'alignement CPU/PPU aléatoire et la RAM initiale
aléatoire.

`FullDebug` demande un arrêt sur BRK, opcode non officiel ou instable, crash
CPU, conflit de bus, lecture OAM dégradée, glitch de scroll, mode de sortie PPU
étendu, accès VRAM invalide, écriture OAM invalide, lecture pendant DMA et
lecture non initialisée.

Un scénario n'est déclaré réussi que si Mesen termine sans arrêt de debug, si
le marqueur Lua attendu est présent, si la région effective est celle demandée,
si les éventuelles captures ne sont pas vides et si ni la ROM ni les réglages
persistants n'ont changé.

Le diagnostic Route 1/Jadielle conserve toutefois dans `mesen.stdout.txt` les
lectures non initialisées héritées de `$0161` à `$01C6/$01C7`. Elles sont
signalées, mais non bloquantes pour ce diagnostic dès lors que le processus,
le marqueur, la région, les contrôles mémoire et l'intégrité des fichiers sont
valides. Cette exception documentée ne s'étend pas aux autres arrêts de debug
et ne transforme pas `parcel_route_done=false` en campagne complète.

## Régions à vérifier

Quatre contrôles sont complémentaires :

- **Dendy forcé** : contrôle principal de compatibilité, car la base de données
  Mesen classe la ROM chinoise source en Dendy ;
- **NTSC forcé** : nécessaire car le header iNES annonce NTSC ;
- **PAL forcé** : contrôle d'exécution au timing 50 Hz émulé d'une console
  française ;
- **Auto avec base de données activée** : sur la ROM finale, dont le CRC n'est
  plus celui de la ROM chinoise, la région effective observée est NTSC.

La validation finale exige les trois profils forcés. Elle ne transforme pas le
header NTSC en header PAL : elle prouve que le code, le mapper, les graphismes
et la sauvegarde fonctionnent lorsque Mesen impose le timing PAL.

Contrôle Auto/DB de la ROM finale :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -ScriptPath .\tools\mesen_mapper163_boot_probe.lua `
  -OutputDirectory .\build\emulator-runs\manual-auto-db-full-debug `
  -Region Auto `
  -EnableGameDatabase `
  -ExpectedEffectiveRegion Ntsc `
  -ExpectedMarker POKEMON_MESEN_PASS `
  -StrictHardware `
  -FullDebug `
  -TimeoutSeconds 60
```

## Provenance, build et validations statiques

Le flux canonique construit deux fois, valide puis publie atomiquement une
release complète, avec IPS, deux BPS, audits, journaux, manifeste et
`SHA256SUMS` :

```powershell
python tools\build_release.py `
  --output-dir build\release-<nouveau-tag> `
  --expect-current-artifacts
```

Pour la remise publiée, le résultat de ce flux est
`build\release-2026-08-09-final-v2`. Les commandes suivantes restent utiles pour
diagnostiquer séparément une étape de bas niveau.

Vérifier que la ROM chinoise et l'IPS anglais reconstruisent exactement
`yellow.nes` :

```powershell
python rom_traduction_assistant.py check
```

Extraire les chaînes de `script.py`, puis reconstruire la ROM repackée :

```powershell
python rom_traduction_assistant.py dump-script
python rom_traduction_assistant.py build-repacked
```

Restaurer le logo anglais, appliquer les menus français et produire l'IPS
final basé sur `yellow.nes` :

```powershell
python tools\title_screen_tools.py patch-french-graphics `
  --rom build\final-dialogue-19x19-20260729\text\Pokemon_Jaune_FR_complete_repacked.nes `
  --base-rom yellow.nes `
  --title-logo english `
  --english-title-rom ".\Pokemon Yellow English 9-23-2015.nes" `
  --out-rom build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.nes `
  --out-ips build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.ips `
  --out build\final-dialogue-19x19-20260729\chr-title-menu-export
```

Vérifier l'aller-retour exact de l'IPS final :

```powershell
python rom_traduction_assistant.py check-ips `
  --base-rom yellow.nes `
  --ips build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.ips `
  --target-rom build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.nes
```

Cette commande doit établir :

```text
yellow.nes
  + build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.ips
  == build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.nes
```

Valider le repack et le matériel :

```powershell
python tools\validate_repacked.py `
  --rom build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.nes
python tools\validate_mapper163.py `
  --rom build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.nes
python tools\validate_pokedex_layout.py
python tools\validate_final_pokedex_runtime.py `
  --rom build\final-dialogue-19x19-20260729\Pokemon_Jaune_FR_title_EN_menus_FR.nes
```

L'état remis correspondant au SHA `1fefecbf...` comporte 1 819 textes
ordinaires et 85 restaurations, soit 1 904 allocations, sans dépassement
fixe, échec d'allocation, chevauchement incompatible, conflit de pointeurs ni
avertissement de construction. Le budget exact est archivé dans
`build/release-2026-08-09-final-v2/audits/text_bank_budget.json` ; les chiffres
d'espace libre des builds antérieurs ne décrivent pas cette remise.

Les deux contrôles Pokédex établissent ensemble : 151 descriptions accessibles
et 8 étendues, 619 lignes physiques, zéro césure lexicale, ainsi que 159/159
pointeurs, payloads et terminateurs exacts dans la ROM finale. Les entrées
#152–159 restent hors de l'interface Pokédex Kanto normale ; leur contenu
compilé est propre sans prétendre qu'elles sont accessibles par ce menu.
Le lot demandé à l'origine comportait 49 descriptions — 45 fiches Kanto et
4 pointeurs étendus. Il est entièrement refait ; le contrôle final élargit la
preuve aux 159 descriptions présentes dans la table compilée.

## Audits de traduction

### Frontières de mots et bulles

Les dialogues communs portant `layout=dialogue_19_19` sont reconstruits par
unités sémantiques avec 19 caractères sur chaque ligne visible. Les trois
messages propres à l'introduction portent `layout=dialogue_intro_17_19` :
17 caractères sur leur première ligne, puis 19. Il y a deux lignes par bulle.
La validation de la remise `1fefecbf` porte sur 970 entrées de mise en page
(967 communes et 3 d'introduction) et établit :

- 814 frontières fautives corrigées ;
- 29 espaces implicites légitimes restaurés ;
- 34 césures artificielles retirées ;
- 2 530 bulles produites et zéro césure de mot restante aux frontières
  validées ;
- 972 emplacements de pointeur vérifiés, 968 cibles distinctes toutes
  rattachées à leur propriétaire exact.

L'inventaire canonique se trouve dans
`tools/data/dialogue_boundary_inventory.json`. Pour le vérifier contre
`script.py` et régénérer le rapport :

```powershell
python tools\validate_dialogue_layout.py `
  --output build\audits\dialogue_layout_validation.json
```

Le rapport de remise
`build/release-2026-08-09-final-v2/audits/dialogue_layout_validation.json`
porte le résultat `PASS`. Une nouvelle divergence de la source maîtresse, une
unité sémantique trop longue ou une frontière non résolue fait échouer ce
contrôle.

Audit des correspondances anglaises probables dans la ROM finale :

```powershell
python rom_traduction_assistant.py audit `
  --french-rom Pokemon_Jaune_FR_repacked_title.nes `
  --output audit_traduction_repacked_title.csv
```

Audit des fragments, mots collés et formulations suspectes :

```powershell
python tools\audit_quality_ambitious.py `
  --csv traduction_base.csv `
  --output audit_qualite_ambitieux.csv `
  --fail-on-high
```

Une occurrence identique telle que `Pikachu` n'est pas nécessairement une
erreur. Inversement, un audit sans suspect ne garantit pas que tous les
dialogues soient exacts ou naturels.

L'audit canonique de cohérence avait relevé 39 corrections certaines et une
harmonisation terminologique. Les 40 points ont été arbitrés et appliqués dans
`script.py` et restent présents dans la remise `1fefecbf`; ils ne constituent plus une liste de
travail restante. `tools/test_coherence_corrections.py` verrouille ces
corrections, et `AUDIT_COHERENCE_GEN1_GEN2_FR.md` conserve les tableaux
d'origine comme piste d'audit historique.

## Scénarios Mesen reproductibles

La commande d'ensemble est :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-pokemon-regression-suite.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -FinalIpsPath .\Pokemon_Jaune_FR_repacked_title.ips `
  -OutputDirectory .\build\runtime-proof-<nouveau-sha>-core `
  -TimeoutSeconds 180
```

Sous Windows, conserver ici un chemin de sortie court : l'arborescence
imbriquée des scénarios batterie et le nom du fichier `.sav` peuvent sinon
dépasser la limite de longueur de chemin.

Cette suite exécute les contrôles statiques, puis les scénarios boot, runtime,
introduction, pages stabilisées, export CHR et menu joueur en Dendy, NTSC et
PAL. Le probe `mesen_player_menu_french_probe.lua` est l'étape
`06-player-menu-fr` de chaque région. Sauf option explicite `-SkipBattery`, la
suite exécute ensuite la persistance batterie. Le résultat à archiver est le
`regression_suite_manifest.txt` du sous-dossier `run-*` créé par la commande.

Cette commande est le flux conseillé pour produire une nouvelle preuve
globale liée au SHA testé. Pour `1fefecbf`, le core normal post-release a
produit 45 étapes `PASS` archivées sous
`build/runtime-proof-final-1fefecbf-core-normal/run-20260809T163735Z-ba4e9771/`.
Le champ `Bootstrap completion gate: False` et le journal `OK` confirment 399
tests sans saut. Le bootstrap antérieur `947d8221…` reste un historique
transitoire de pré-promotion et n'est plus la preuve active.

La régression globale archivée 42/42 sous
`build\r\5adcd8bf-title-en-menu-fr\run-20260728T220348Z-ad61c28c\`
porte exclusivement sur l'ancienne ROM `5adcd8bf…` et l'ancien IPS
`bba4e5a1…`. Elle reste utile comme historique du banc de test mais ne
constitue pas une preuve dynamique de la remise `1fefecbf`.

Le contrat linguistique propre au titre est vérifié séparément par
`mesen_title_en_menu_fr_probe.lua` sous Dendy, NTSC et PAL. Les trois
manifests `PASS`, captures et dumps même-frame se trouvent dans
`build\emulator-checks\title-eeb4975e\`; ils portent tous le SHA exact
`eeb4975e86157e27f572141c62f640462a881ac43993b1e544cda50c0870733d`
et ont été exécutés avec `StrictHardware=True` et `FullDebug=True`.

Les commandes suivantes sont à exécuter trois fois avec
`$region = "Dendy"`, puis `"Ntsc"`, puis `"Pal"`. Les noms de dossiers sont
séparés pour conserver les preuves de chaque profil.

### Introduction

```powershell
$region = "Dendy" # exécuter aussi avec "Ntsc", puis "Pal"
$slug = $region.ToLowerInvariant()

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -ScriptPath .\tools\mesen_pokemon_intro_probe.lua `
  -OutputDirectory ".\build\emulator-runs\manual-intro-$slug-full-debug" `
  -Region $region `
  -ExpectedEffectiveRegion $region `
  -ExpectedMarker POKEMON_INTRO_PASS `
  -StrictHardware `
  -FullDebug `
  -TimeoutSeconds 120
```

Pour capturer uniquement les pages de dialogue une fois leur saisie terminée,
remplacer le script et le marqueur par :

```powershell
-ScriptPath .\tools\mesen_pokemon_intro_prompt_probe.lua
-ExpectedMarker POKEMON_INTRO_PROMPTS_PASS
```

### Activité mapper 163/Nanjing

```powershell
$region = "Dendy" # exécuter aussi avec "Ntsc", puis "Pal"
$slug = $region.ToLowerInvariant()

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -ScriptPath .\tools\mesen_mapper163_runtime_probe.lua `
  -OutputDirectory ".\build\emulator-runs\manual-runtime-$slug-full-debug" `
  -Region $region `
  -ExpectedEffectiveRegion $region `
  -ExpectedMarker MAPPER163_PASS `
  -StrictHardware `
  -FullDebug `
  -TimeoutSeconds 60
```

Ce scénario observe en exécution les écritures des registres Nanjing et les
valeurs de banques. Il ne remplace pas `validate_mapper163.py` ; les deux
contrôles couvrent des propriétés différentes.

### Logo anglais et choix français

```powershell
$region = "Dendy" # exécuter aussi avec "Ntsc", puis "Pal"
$slug = $region.ToLowerInvariant()

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -ScriptPath .\tools\mesen_title_en_menu_fr_probe.lua `
  -OutputDirectory ".\build\emulator-runs\title-eeb4975e-$slug-full-debug" `
  -Region $region `
  -ExpectedEffectiveRegion $region `
  -ExpectedMarker TITLE_EN_MENU_FR_PASS `
  -StrictHardware `
  -FullDebug `
  -TimeoutSeconds 60
```

Ce probe contrôle les cinq tuiles live de `YELLOW`, les sept tuiles de
`NOUV` / `CONT`, leurs tilemaps, puis exporte les captures, le CHR-RAM, la
nametable et la palette dans la même image.

### Export CHR-RAM en direct

```powershell
$region = "Dendy" # exécuter aussi avec "Ntsc", puis "Pal"
$slug = $region.ToLowerInvariant()

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -ScriptPath .\tools\mesen_chr_export_probe.lua `
  -OutputDirectory ".\build\chr-exports\manual-live-$slug-full-debug" `
  -Region $region `
  -ExpectedEffectiveRegion $region `
  -ExpectedMarker POKEMON_CHR_EXPORT_PASS `
  -StrictHardware `
  -FullDebug `
  -TimeoutSeconds 60
```

Le scénario exporte, au titre et au menu stabilisé, le CHR-RAM 8 Kio, la vue
PPU des patterns, la nametable, la palette, l'OAM, l'ombre OAM et une capture
PNG.

### Menu joueur français

```powershell
$region = "Dendy" # exécuter aussi avec "Ntsc", puis "Pal"
$slug = $region.ToLowerInvariant()

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -ScriptPath .\tools\mesen_player_menu_french_probe.lua `
  -OutputDirectory ".\build\emulator-runs\manual-player-menu-fr-$slug-full-debug" `
  -Region $region `
  -ExpectedEffectiveRegion $region `
  -ExpectedMarker POKEMON_PLAYER_MENU_FR_PASS `
  -StrictHardware `
  -FullDebug `
  -TimeoutSeconds 120
```

Ce scénario atteint la chambre sans injection RAM, ouvre le menu joueur et
vérifie dans la même frame les checksums des tuiles `OBJETS`, `SACHA`, `CS` et
`SAUVER`, ainsi que la géométrie de tilemap conservée. Il exporte aussi une
capture, le CHR-RAM 8 Kio, la nametable 4 Kio, la palette et un rapport texte.

## Persistance batterie dans deux processus

La preuve de sauvegarde ne repose pas sur une savestate. La suite :

1. lance un contrôle frais sans sauvegarde ;
2. lance un processus Mesen qui crée une partie et ferme le fichier `.sav` ;
3. lance un nouveau processus Mesen partageant uniquement le dossier de
   sauvegarde, choisit `CONT` et reprend la salle créée.

Les phases création et rechargement sont donc deux processus indépendants. La
suite vérifie aussi que le `.sav` fermé de 8 Kio correspond octet par octet à
la SRAM initiale du second processus, que la capture de la salle créée est
identique à celle reprise et qu'un contrôle frais mène ailleurs.

Exécuter en Dendy, NTSC et PAL :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-battery-persistence.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -OutputDirectory .\build\emulator-runs\manual-battery-persistence-dendy `
  -Region Dendy `
  -TimeoutSeconds 120

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-battery-persistence.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -OutputDirectory .\build\emulator-runs\manual-battery-persistence-ntsc `
  -Region Ntsc `
  -TimeoutSeconds 120

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\run-mesen-battery-persistence.ps1 `
  -RomPath .\Pokemon_Jaune_FR_repacked_title.nes `
  -OutputDirectory .\build\emulator-runs\manual-battery-persistence-pal `
  -Region Pal `
  -TimeoutSeconds 120
```

`StrictHardware` et `FullDebug` valent `true` par défaut dans cette suite.

## Graphismes, exports CHR et retouche manuelle

La cartouche emploie de la CHR-RAM : le dump en direct n'est pas un bloc
CHR-ROM autonome que l'on peut recopier aveuglément dans le fichier NES. Les
données sources du titre sont chargées depuis la banque PRG 28 et leurs plages
se chevauchent :

- source CHR `$1000` : offset fichier `0x0705AB`, 4 096 octets ;
- source CHR `$0000` : offset fichier `0x070FFB`, 4 096 octets ;
- nametable `$2000` : offset fichier `0x071A0B`, 1 024 octets.

Le mapper 163 échange en plus les moitiés physiques de 4 Kio du CHR-RAM à la
scanline 127. Il faut donc vérifier les graphismes dans Mesen, pas seulement
dans un rendu statique.

### Menu joueur

Les libellés du menu ouvert avec `START` ne sont pas des chaînes ASCII. Ce
sont des tuiles NES 2 bpp, deux tuiles de haut, chargées depuis le bloc
`PLAYER_MENU_PT0_FILE` :

- source CHR PT0 : offset fichier `0x0288D5`, 4 096 octets ;
- tilemap visible : offset fichier `0x0295D5` ;
- libellés modifiés : `ITEMS` → `OBJETS`, `Ash` → `SACHA`, `HMs` → `CS`,
  `SAVE` → `SAUVER`.

Le patch remplace uniquement les tuiles graphiques déjà référencées. La
tilemap et sa géométrie restent inchangées. Les exports statiques correspondants
sont produits avec ceux du titre dans :

- `build\final-dialogue-19x19-20260729\chr-title-menu-export\before`
- `build\final-dialogue-19x19-20260729\chr-title-menu-export\after`

Chaque dossier contient le CHR 8 Kio, ses deux moitiés 4 Kio, la nametable
visible, un rendu complet du menu, les blocs `.bin/.bmp` des quatre libellés
du menu joueur et le bloc combiné des tuiles du titre/menu.

Le validateur mapper 163 exige en outre que la banque 5 ne diffère que dans
ces 28 tuiles : 226 octets modifiés, tous dans la plage réservée, avec le hash
du bloc PT0 attendu.

### Catalogue CHR courant (`1fefecbf`)

Le catalogue actif, lié par hash à la ROM finale, est
`build\chr-catalog\current-1fefecbf`. Il contient :

- `chr-assets.manifest.json` et `chr-assets.metadata.csv` ;
- `pack\pack.lock.json` avec les baselines et chevauchements déclarés ;
- `verify.json` et `roundtrip.json`, tous deux `PASS`.

Il couvre 1 489 assets, 149 chevauchements contrôlés et 853 648 octets de ROM
placés en liste blanche. La vérification et l'aller-retour sans modification
produisent zéro octet changé et le SHA de sortie exact
`1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`.
Cette exhaustivité est structurelle : elle ne signifie pas que chacun des
1 489 assets a été affiché dans une partie. La couverture dynamique reste
limitée aux écrans explicitement atteints par les probes Mesen.

### Pack CHR modulaire historique (`eeb4975e`)

Le dossier `graphics\\chr_modular` contient notamment un pack indépendant,
lié par hash à l'ancienne ROM `eeb4975e`, pour reproduire ses retouches
manuelles :

- `manifest-eeb4975e.json` : offsets, tailles et types admis par le
  compilateur pour la ROM de remise ;
- `catalog-eeb4975e.csv` : dimensions, banques, hashes et sémantique connue ;
- `pack-eeb4975e\\baseline` : copie de référence à ne jamais modifier ;
- `pack-eeb4975e\\work` : 1 489 fichiers éditables ;
- `pack-eeb4975e\\previews` : 625 aperçus PNG des assets CHR ;
- `pack-eeb4975e\\pack.lock.json` : hashes et matrice des chevauchements.

Le pack couvre 587 paquets de sprites/portraits bruts, le titre, les menus,
l'introduction, la police UI, une page d'overworld observée dans Mesen, ainsi
que 416 tilemaps 32×30 et 416 tables d'attributs strictement bornées. Les
fichiers importants portent des chemins explicites, par exemple :

- `pack-eeb4975e\\work\\screens\\title_screen\\`
- `pack-eeb4975e\\work\\screens\\player_menu\\`
- `pack-eeb4975e\\work\\screens\\intro_professor\\portrait.chr`
- `pack-eeb4975e\\work\\screens\\intro_player\\portrait.chr`
- `pack-eeb4975e\\work\\sprites\\intro\\pikachu.chr`
- `pack-eeb4975e\\work\\packages\\b50` à `b62`

Un `.chr` doit rester un flux NES 2 bpp de même taille : 16 octets par tuile
8×8. Modifier uniquement `pack-eeb4975e\\work`, jamais `baseline`, les
previews ou le lock. Les aliases physiques sont fusionnés relativement à leur
baseline ; un alias inchangé est ignoré et deux retouches contradictoires sur
le même octet sont rejetées.

Commandes usuelles :

```powershell
.\tools\build-chr-modular.ps1 Diff
.\tools\build-chr-modular.ps1 Verify
.\tools\build-chr-modular.ps1 Roundtrip
.\tools\build-chr-modular.ps1 Compile
```

La compilation écrit une nouvelle ROM, un IPS et un rapport JSON dans
`build\\chr-modular-eeb4975e` sans écraser la source. Sur cette remise
historique, `Diff`, `Verify`, `Roundtrip` et `Compile` réussissent ; les ROM et IPS
produits sont identiques bit à bit aux artefacts `eeb4975e...` et
`b04676da...`.

Les sorties par défaut sont :

- `build\\chr-modular-eeb4975e\\Pokemon_Jaune_FR_CHR_mod.nes` ;
- `build\\chr-modular-eeb4975e\\Pokemon_Jaune_FR_CHR_mod.ips` ;
- `build\\chr-modular-eeb4975e\\compile-report.json`.

Tous les couples actuellement présents dans ce dossier, y compris
`manifest-eeb4975e.json` / `pack-eeb4975e` et les alias `current`, sont des
snapshots historiques. Aucun ne doit être présenté comme lié à la release
`1fefecbf`. Avant une nouvelle retouche graphique, exporter un nouveau couple
`manifest-1fefecbf.json` / `pack-1fefecbf` depuis la ROM finale et vérifier sa
liaison de hash.

La police chinoise HZK16 à `0x040010` reste hors pack : ses plans 1 bit
scindés/entrelacés ne constituent pas un `.chr` NES standard. Le détail complet
et les précautions Mesen figurent dans
`graphics\\chr_modular\\README.md`.

### Export obligatoire avant/après une modification

`patch-french-graphics` exporte automatiquement la source dans `before` et le
résultat dans `after`, avec les données binaires, les planches BMP et un
manifeste. Pour chaque nouvelle retouche, choisir un dossier versionné afin de
ne pas écraser l'export précédent :

```powershell
python tools\title_screen_tools.py patch-french-graphics `
  --rom build\final-dialogue-19x19-20260729\text\Pokemon_Jaune_FR_complete_repacked.nes `
  --base-rom yellow.nes `
  --title-logo english `
  --english-title-rom ".\Pokemon Yellow English 9-23-2015.nes" `
  --out-rom build\retouches\retouche-YYYYMMDD-nom.nes `
  --out-ips build\retouches\retouche-YYYYMMDD-nom.ips `
  --out build\chr-exports\retouche-YYYYMMDD-nom
```

Le patch courant restaure le petit logo anglais `YELLOW`, traduit `NEW` en
`NOUV` condensé, `LOAD` en `CONT` et conserve les quatre libellés graphiques
français du menu joueur énumérés ci-dessus. Le mode historique
`--title-logo french` permet encore de reconstruire l'ancienne variante
`JAUNE`.

Après le patch, lancer `mesen_title_en_menu_fr_probe.lua` et
`mesen_chr_export_probe.lua` en Dendy, NTSC et PAL pour vérifier le contenu
linguistique exact et obtenir l'état réellement chargé en CHR-RAM.

### Planches pour retouche manuelle

Transformer un export Mesen en fichiers 4/8 Kio et planches BMP :

```powershell
python tools\title_screen_tools.py render-dump `
  --chr build\chr-exports\manual-live-dendy-full-debug\new_load_menu_stable_chr_ram_8k.bin `
  --nametable build\chr-exports\manual-live-dendy-full-debug\new_load_menu_stable_nametable_4k.bin `
  --out build\chr-exports\manual-live-dendy-full-debug\manual `
  --prefix new_load_menu
```

Les BMP et `.bin` servent de base de retouche et de comparaison. Pour intégrer
une retouche à la ROM reproductible, reporter les octets de tuiles validés dans
`tools/title_screen_tools.py`, reconstruire le patch, refaire l'export
avant/après, puis relancer `check-ips`, les deux validateurs et les exports
Mesen Dendy/NTSC/PAL. `render-dump` ne réinjecte pas automatiquement un BMP
édité dans la ROM.

### Police française éditable

La police ASCII utilisée par les dialogues contient désormais 16 glyphes
français natifs sur un octet :
`À Â É Ç Î é ç î ï ô ù û à è ê â`. Chaque construction repackée exporte
automatiquement la police avant/après et les glyphes séparément sous
`build\chr-exports`. Pour la remise `eeb4975e`, la police provient du build
textuel `38f4ac99…` et son dossier est :

```text
build\chr-exports\Pokemon_Jaune_FR_complete_repacked-french-font-38f4ac995974
```

Il contient les polices complètes `.chr`, leurs planches BMP, les 16 fichiers
de glyphe de 16 octets, les blocs combinés des 15 tuiles patchées et des
16 glyphes natifs, ainsi qu'un manifeste de hashes. `é` réutilise la tuile
`@` de la base anglaise. Ces fichiers sont destinés aux retouches manuelles ;
une retouche doit ensuite être recompilée, validée et réexportée.

## Preuves conservées pour `5b479227...`

Les preuves ci-dessous sont liées exclusivement à l'ancienne ROM
`5b479227...`. Elles sont conservées pour l'historique et ne valident ni
`eeb4975e...` ni la remise actuelle `1fefecbf...` :

- `build\chr-exports\final-dialogue-spacing-clean-runtime-20260728\before`
- `build\chr-exports\final-dialogue-spacing-clean-runtime-20260728\after`
- `build\chr-exports\final-dialogue-spacing-clean-runtime-20260728\graphics_patch_manifest.txt`
- `build\chr-exports\Pokemon_Jaune_FR_repacked-french-font-e14d5477fa8f`
- `build\r\f5b\run-20260728T154259Z-f84db654\regression_suite_manifest.txt`

Le dossier `chr-exports` contient les planches BMP, les blocs CHR 4/8 Kio et
les blocs de tuiles destinés à la vérification ou à une retouche manuelle. Le
manifeste historique de régression établissait 40 étapes `PASS`, dont les
accents alors disponibles en exécution dans les trois régions et la batterie.
Les chemins génériques `tools\data\dialogue_boundary_inventory.json` et
`build\audits\*.json` ont depuis été régénérés : ils
ne doivent pas servir de preuves du snapshot `5b479227...`.

L'ancien hash `fb1151dc...` désigne une construction corrompue archivée dans
`build\quarantine\pre-final-v8`. Le hash `5b479227...` ne doit être vérifié
que pour reproduire cet ancien snapshot. Pour la remise actuelle, les preuves
canoniques sont celles de la section « État remis — release finale du
9 août 2026 (`1fefecbf`) ».

## Flux conseillé après chaque modification

1. Modifier uniquement les textes maîtres dans `script.py`.
2. Lancer `dump-script`, puis relire le CSV et les dépassements.
3. Lancer `validate_dialogue_layout.py`, les audits qualité/accents et les
   audits de couverture, sans considérer leur silence comme une preuve
   dynamique de toutes les branches du jeu.
4. Lancer `build-repacked` et conserver son export CHR versionné de la police.
5. Pour une retouche graphique de la remise actuelle, créer d'abord
   `manifest-1fefecbf.json` et `pack-1fefecbf` avec l'action `Export`, puis
   modifier uniquement son dossier `work` et lancer `Diff`, `Verify`,
   `Roundtrip` et `Compile`. Pour toute ROM portant un autre SHA, créer un
   nouveau `manifest-<sha>.json` et un nouveau `pack-<sha>` ; ne jamais
   réexporter par-dessus un pack historique.
   Conserver aussi l'export versionné avant/après de
   `patch-french-graphics` lorsque ce patch est utilisé.
6. Lancer `check`, `check-ips`, `validate_repacked.py` et
   `validate_mapper163.py`.
7. Lancer `run-mesen-pokemon-regression-suite.ps1` : le menu joueur fait
   partie des scénarios Dendy, NTSC et PAL avec
   `StrictHardware + FullDebug`.
8. Vérifier dans son manifeste les contrôles Auto/DB, les trois régions et la
   suite batterie.
9. Pour diagnostiquer un affichage, relancer séparément le probe concerné et
   produire une planche manuelle avec `render-dump`.
10. Conserver les manifests, hashes, captures et exports CHR sous un nouveau
    tag correspondant au SHA de la ROM testée.

## Bot Lua de campagne

Le chantier d'automatisation Mesen est décrit dans
`tools\campaign\STATUS_FR.md`. Il comprend désormais :

- un moteur piloté par l'état du jeu et non par une simple macro ;
- un prototype contrôleur-only qui obtient Pikachu, gagne le combat imposé
  contre Régis et sort du laboratoire depuis un démarrage à froid sur la ROM
  précédente `42a0d940`, sous Dendy à l'image 10 545 et sous NTSC à l'image
  10 575, avec `StrictHardware + FullDebug`, sans écriture mémoire, savestate,
  rewind, cheat ni reprise ;
- sous PAL, le même Lua exact n'est **pas robuste aux états de mise sous
  tension randomisés** du profil strict : un run attesté sort du laboratoire
  à l'image 10 545, tandis que le suivant expire dans
  `complete_rival_battle` à l'image 14 931 ; le succès PAL est donc démontré,
  mais la stratégie du bot n'est pas reproductible sur tous ces états ;
- un ancien jalon limité à la sortie de la maison validé en Dendy, PAL et
  NTSC sur le snapshot historique `5b479227`, conservé séparément et non
  présenté comme une exécution sur la remise actuelle ;
- un traceur des vraies acquisitions `SEEN/CAUGHT` ;
- une preuve assistée `SEEN 151 / CAUGHT 151` rejouée sur la ROM précédente
  `42a0d940` en
  Dendy, NTSC et PAL, à l'image 5 600 avec 42 écritures RAM déclarées dans
  chaque run ; elle valide l'écran et les structures, pas 151 captures
  naturelles ;
- la cartographie reproductible de la sauvegarde dans
  `tools\analysis\pokemon_save_layout\README.md`.

Le prototype ne termine pas encore toute l'histoire. Le premier Temple de la
Gloire n'est d'ailleurs pas le dernier endpoint de ce bootleg : le scénario
continue jusqu'au contrôle Kanto et au don de Mew. La table ROM possède huit
noms supplémentaires hors de l'interface Pokédex 151 ; ils devront être
prouvés par leurs rencontres ou acquisitions, jamais en forçant des bits
inexistants.

## Accents

`script.py` encode sur un octet les 16 glyphes natifs nécessaires au corpus :
`À Â É Ç Î é ç î ï ô ù û à è ê â`. Quinze tuiles sont patchées ; `é`
réutilise en `0x40` la tuile `@` déjà redessinée dans la base anglaise.
Les affectations exactes et les contrôles de collision sont définis dans
`tools/french_font.py`. La ligature `œ/Œ` reste volontairement rendue par
`oe/OE`. Pour les dialogues à pointeurs, `build-repacked` déplace les textes
dans la même paire de banques, met à jour les pointeurs, applique la police et
produit son export CHR. Les vrais libellés fixes doivent rester assez courts
pour leur zone d'affichage.
