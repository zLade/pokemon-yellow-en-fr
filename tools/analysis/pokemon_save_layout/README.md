# Mémoire de campagne — Pokémon Jaune NES (mapper 163)

Ce document décrit uniquement les champs vérifiés sur la ROM finale française
et sur la ROM chinoise source. Les adresses sont celles du CPU NES ; les
offsets `.sav` commencent à zéro dans le fichier batterie de 8 Kio.

## Blocs persistants

| Rôle | Adresse CPU | Offset `.sav` | Taille | Preuve |
|---|---:|---:|---:|---|
| État principal actif | `$6000-$67FF` | `$0000-$07FF` | 2048 | lectures/écritures en jeu |
| Copie créée par `SAUVER` | `$6C00-$73FF` | `$0C00-$13FF` | 2048 | égalité bit à bit après sauvegarde |
| Marqueur de sauvegarde | `$7C21-$7C24` | `$1C21-$1C24` | 4 | toujours `AA 55 A5 5A` après `SAUVER` |

`$6800-$6BFF` et `$7400-$7FFF` servent aussi de RAM de code, graphismes et
travail. Ils ne doivent pas être traités comme des champs de campagne.

Aucun checksum de l'état principal n'a été observé. Le byte `$7C20` varie
alors que deux états principaux sont identiques ; ce n'est donc pas leur
checksum. Pour éditer un `.sav` de façon conservatrice, modifier le bloc
principal, le recopier à l'offset `$0C00`, puis préserver/rétablir le marqueur
`AA 55 A5 5A`.

### Récupération après une divergence primaire/backup

Un test Mesen 2.2.1 strict et `FullDebug`, sans écriture RAM par le script,
crée d'abord une sauvegarde réelle puis altère une seule copie avant un
second lancement :

- bit inversé à l'offset primaire `$0050` : le jeu restaure le primaire
  depuis le backup et reprend la salle sauvegardée ;
- même bit inversé à l'offset backup `$0C50` : le jeu refuse la reprise et
  retombe sur l'introduction d'une nouvelle partie.

Cette observation décrit uniquement cette divergence mono-octet sur une
sauvegarde de début de partie. Elle ne permet pas d'identifier un éventuel
algorithme d'intégrité, ni de conclure pour les fichiers tronqués, les
corruptions multiples, les coupures pendant l'écriture ou le matériel
mapper-163 physique. Le banc reproductible est
`tools/run-mesen-battery-persistence.ps1` et sa preuve est contrôlée par
`tools/verify_mesen_battery_corruption.py`.

## Pokédex standard #001 à #151

| Champ | CPU | Offset `.sav` | Encodage |
|---|---:|---:|---|
| Pokédex obtenu | `$6000` bit 5 | `$0000` masque `20` | 1 = menu accessible |
| Nombre vus | `$6031` | `$0031` | entier binaire |
| Nombre capturés | `$6032` | `$0032` | entier binaire |
| Capturés / owned | `$609F-$60B1` | `$009F-$00B1` | 19 octets |
| Vus / seen | `$60B3-$60C5` | `$00B3-$00C5` | 19 octets |
| Plus grand numéro vu | `$60C8` | `$00C8` | numéro 1-based |

Pour une espèce `n` de 1 à 151 :

```text
octet = (n - 1) >> 3
masque = 1 << ((n - 1) & 7)
```

Les bits sont donc LSB-first. Le masque complet et sûr est `FF` dix-huit
fois, puis `7F`. Le bit 7 du dernier octet correspondrait à #152 et doit
rester nul. Les octets adjacents `$60B2` et `$60C6` permettraient
techniquement d’adresser d’autres IDs, mais l’interface Pokédex compare le
numéro à `$98` et s’arrête avant #152. Les huit noms supplémentaires trouvés
dans certaines tables ROM ne sont donc pas couverts par la preuve UI des 151
espèces et ne doivent pas être cochés automatiquement.

Preuves dynamiques :

- `$60B3=01`, compteurs `1/0` : Bulbizarre apparaît avec `SEEN 001`,
  `CAUGHT 000` ;
- plus `$609F=01`, compteurs `1/1` : `SEEN 001`, `CAUGHT 001` ;
- masque complet, compteurs `151/151` : l’écran affiche `SEEN 151`,
  `CAUGHT 151` et la liste française ;
- état naturel du TAS public : capturés `[10,25,26,56]`, vus
  `[10,21,25,26,56,133]`, exactement égaux aux compteurs `4/6`.

Captures correspondantes :

- `build/pokedex-ram/probe-seen-001-allzeros-dendy-full-debug/03_pokedex_screen.png`
- `build/pokedex-ram/probe-caught-001-allzeros-dendy-full-debug/03_pokedex_screen.png`
- `build/pokedex-ram/probe-all-151-allzeros-dendy-full-debug/03_pokedex_screen.png`

## Équipe

L’équipe utilise une structure « tableau de champs » de six entrées :

| Champ | CPU | Offset `.sav` |
|---|---:|---:|
| Nombre de Pokémon | `$6030` | `$0030` |
| Espèce par slot de stockage | `$6033 + slot` | `$0033 + slot` |
| Niveau par slot de stockage | `$6039 + slot` | `$0039 + slot` |
| Ordre visible (indices de slots) | `$60C9-$60CE` | `$00C9-$00CE` |

Le record complet possède 18 champs d’un octet, chacun espacé de six :
`$6033 + champ*6 + slot`, jusqu’à `$6099`. Le code de capture et le code de
menu copient ces 18 champs dans les deux sens. Les quatre premiers champs de
combat et les statistiques restantes ne sont pas renommés ici sans preuve
sémantique suffisante.

L’état naturel du TAS confirme `count=3`, slots d’espèces
`[26,56,10]`, niveaux `[7,5,4]` et ordre `[1,0,2,3,4,5]`.

## Badges, argent et drapeaux

| Champ | CPU | Offset `.sav` | Détail |
|---|---:|---:|---|
| Huit badges | `$60C7` | `$00C7` | masque 8 bits, LSB-first |
| Argent | `$6023-$6025` | `$0023-$0025` | trois octets, format non modifié ici |
| Compteur Pokédex du profil | `$6032` | `$0032` | nombre capturé |

L’écran de profil relit `$60C7` huit fois. Injecter `FF` remplace les huit
points d’interrogation par les huit icônes de badge.

Le code expose également des helpers de drapeaux 1-based, LSB-first aux bases
`$6000`, `$6026`, `$6760` et `$6780`. Leur sémantique individuelle dépend de
la carte et du scénario ; il serait dangereux de les remplir globalement.
Le bot de campagne doit observer des objectifs précis (carte, dialogue,
badge, combat) plutôt que forcer tous ces drapeaux.

## Outils reproductibles

- `tools/mesen_pokedex_ram_probe.lua` : ouvre le Pokédex par contrôleur,
  injecte le masque standard exact et refuse tout masque/counter incohérent ;
- `tools/mesen_trainer_ram_probe.lua` : trace l’écran profil et les badges ;
- `tools/pokemon_save_layout.py` : décode/valide les champs et synchronise la
  copie batterie ;
- `tools/test_pokemon_save_layout.py` : tests synthétiques et reproduction des
  valeurs naturelles du TAS ;
- `tools/mesen_battery_corruption_probe.lua` : observe les deux chemins de
  récupération sans injection mémoire ;
- `tools/verify_mesen_battery_corruption.py` : lie les manifests Mesen, les
  fixtures mono-octet, la SRAM et les captures d'écran.
