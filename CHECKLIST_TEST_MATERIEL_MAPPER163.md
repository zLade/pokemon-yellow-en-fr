# Checklist de validation sur cartouche mapper 163

Cette checklist couvre ce que Mesen ne peut pas prouver : le comportement de
la ROM française `1fefecbf…` sur une vraie cartouche mapper 163 et une vraie
console. Elle ne doit être cochée qu'après observation matérielle.

## Matériel et traçabilité

- [ ] La ROM programmée a le SHA-256
  `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`.
- [ ] La cartouche utilise bien le mapper 163, 2 Mio de PRG, 8 Kio de CHR-RAM
  et une SRAM sauvegardée par pile.
- [ ] Console, révision de carte mère, région, alimentation, câble vidéo,
  programmateur et modèle de cartouche sont consignés.
- [ ] Une vidéo continue ou des photos horodatées accompagnent chaque échec.

| Champ | Valeur |
| --- | --- |
| Console / révision | |
| Région / fréquence | |
| Cartouche / PCB | |
| Programmateur | |
| Alimentation | |
| Affichage / capture | |
| Date et opérateur | |

## Démarrage et graphismes

- [ ] Dix démarrages à froid successifs aboutissent au titre sans écran noir,
  tuile corrompue, redémarrage ni blocage.
- [ ] Le logo `YELLOW`, Pikachu et les choix `NOUV` / `CONT` sont stables.
- [ ] `NOUV` démarre une partie ; `CONT` charge une sauvegarde existante.
- [ ] Le menu joueur affiche `POKÉDEX`, `POKÉMON`, `OBJETS`, le nom du joueur,
  `CS` et `SAUVER` sans corruption CHR.
- [ ] Les changements de salle, combats et menus ne détériorent pas la police
  ou les portraits après au moins 60 minutes de jeu.

## Texte et progression ciblée

- [ ] L'introduction du Prof. Chen est lisible, avec accents et mots entiers.
- [ ] Les cinq invites de nom et les trois pages du probe de glyphes affichent
  correctement `À Â É Ç Î é ç î ï ô ù û à è ê â`.
- [ ] Les premières zones jusqu'à Jadielle ne présentent ni dialogue vide,
  ni mot coupé, ni blocage de progression.
- [ ] Pierre remet `CT35` et la description correspond à `Armure`.
- [ ] Les caméos Beibei (`D0064`, `D0632`), Xiao Li et Kameiyu sont visibles
  dans leurs scènes lorsqu'une sauvegarde de test permet de les atteindre.
- [ ] Les noms officiels français (Pokémon, Team Rocket, Jessie, James,
  Champions et villes) restent cohérents dans les scènes échantillonnées.

## Sauvegarde et endurance

- [ ] Créer une partie, sauvegarder, éteindre 30 secondes, puis reprendre :
  position, équipe, inventaire et progression sont inchangés.
- [ ] Refaire le contrôle après 24 heures hors tension.
- [ ] Effectuer 20 cycles `sauvegarde → extinction → reprise` sans perte ni
  bascule vers une sauvegarde antérieure.
- [ ] Laisser tourner deux heures, dont au moins un combat, un changement de
  zone et plusieurs ouvertures de menu, sans crash ni artefact persistant.

## Critères de résultat

- `PASS` : toutes les cases observables sont cochées, sans corruption ni
  différence reproductible par rapport aux captures Mesen de référence.
- `FAIL` : tout crash, perte de sauvegarde, écran noir, corruption CHR durable,
  dialogue inaccessible ou blocage de progression. Conserver la cartouche en
  l'état et joindre la dernière action, la photo/vidéo et le dump SRAM.
- `NON TESTÉ` : absence du matériel ou scène non atteinte ; ne jamais convertir
  ce statut en `PASS` par inférence depuis l'émulateur.

| Test | Région | Résultat | Preuve / note |
| --- | --- | --- | --- |
| Démarrages à froid | | NON TESTÉ | |
| Titre et menus | | NON TESTÉ | |
| Introduction et glyphes | | NON TESTÉ | |
| Route 1 / Jadielle | | NON TESTÉ | |
| CT35 / Armure | | NON TESTÉ | |
| Caméos | | NON TESTÉ | |
| Sauvegarde immédiate | | NON TESTÉ | |
| Sauvegarde après 24 h | | NON TESTÉ | |
| Endurance 2 h | | NON TESTÉ | |
