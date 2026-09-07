# Historique des versions françaises

## Français 2.0.12

- IPS final applicable directement à la ROM chinoise originale NJ046.
- ROM obtenue strictement identique à la 2.0.11.
- Compilation à partir de deux ROMs : source chinoise et base technique anglaise de 2015.


Ce fichier recense les évolutions visibles de la branche française. Aucune ROM
complète n'est distribuée.

## Français 2.0.11 — 26 août 2026

- Ajout de la table de hauteur musicale NES corrigée.
- Conservation byte à byte de tous les textes, graphismes et mécanismes de la
  version française 2.0.10 hors des 69 octets musicaux attendus.
- Nouveau patch IPS combiné applicable directement à la base canonique
  la précédente base intermédiaire.
- Démarrage Mesen 2.2.1 Dendy et manifeste 1 916/1 916 : PASS.
- Cible finale SHA-256
  `efc7ba0837a65d06e0658348d3debaa1194b9cf03b59492a1a8d4dfab346327e`.

## Français 2.0.10 — 24 août 2026

- Relecture complète des dialogues, menus et messages de début et de fin de
  combat dans un français naturel fidèle à Pokémon Rouge/Bleu/Jaune.
- Correction des libellés graphiques français, des artefacts de fenêtres et
  du curseur interactif de l'écran d'oubli d'attaque.
- Mise en page sur deux lignes des attaques longues et contrôle des bordures
  sur les variantes dynamiques.
- Certification indépendante du patch IPS, du mapper 163, des 1 916 pointeurs
  et des 101 scénarios de limites dynamiques.
- Cible finale SHA-256
  `f292c39ebc0b6c4e55ae1d39a6fc4417b0b9823a96667b4f7bae6294d9a334b1`.

## Français 2.0.1 — 12 août 2026

- Conservation intégrale du corpus français validé en version 2.0.
- Ajout des crédits `LUIGA2009, ZLADE, CHPEXO` à l'écran-titre en conservant
  le style graphique d'origine.
- Validation active des trois routes de patch, du delta graphique exact, du
  mapper 163 et de la capture Mesen titre/menu liée au SHA de la 2.0.1.
- Vérification byte à byte des 20 tuiles de crédits chargées en CHR-RAM et de
  leurs 20 références dans la nametable capturée par Mesen.
- Publication de trois routes IPS/BPS conduisant à la même ROM mapper 163,
  SHA-256 `78b1deb554a37541399574c2b94fa1a06327e4de51339fa2b8f555350deef85f`.

## Français 2.0.0 — 9 août 2026

- Release française complète issue de la ROM chinoise NJ046 et de son
  extraction Unicode épinglée.
- 1 844 entrées ordinaires et 85 restaurations compilées sans troncature.
- Validation statique, double build déterministe, IPS/BPS, mapper 163 et suite
  Mesen Dendy/NTSC/PAL documentés pour la cible
  `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`.

Le test sur cartouche mapper 163 réelle reste non effectué.
