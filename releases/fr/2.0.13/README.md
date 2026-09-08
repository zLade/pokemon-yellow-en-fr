# Pokémon Jaune NJ046 — Français 2.0.13

Ce patch restaure le splash screen « VERSION JAUNE » : le petit mot VERSION à
gauche du logo n'est plus remplacé par JAUNE. Le bandeau inférieur JAUNE, les
crédits et les menus NOUV/CONT sont conservés.

## Application

1. Utiliser une copie propre de la ROM chinoise originale
   **Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes** :
   2 097 168 octets, SHA-256
   `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed`.
2. Appliquer `Pokemon_Jaune_NJ046_FR_v2.0.13.ips` avec un outil IPS.
3. Vérifier la ROM obtenue : SHA-256
   `2846fac5738ad24bc65dd1c24622fe4a1e9fffe94062052e84bfbae1cd34fae3`.

Ne pas appliquer sur la 2.0.12, une traduction anglaise ou le jeu Game Boy.
Le nom du fichier ne suffit pas à identifier la source ; IPS ne la vérifie pas.
`SHA256SUMS` contient l'empreinte du patch, pas celle de la ROM source.

## Périmètre et contrôles

- 73 octets modifiés par rapport à la ROM 2.0.12, uniquement dans les cinq tuiles
  du libellé VERSION ; tous les autres octets sont identiques.
- Textes, routines, musique, palettes, pointeurs et mapper 163 conservés.
- Reconstruction déterministe et indépendante, 1 916 pointeurs, limites
  dynamiques et aller-retour IPS vérifiés par le compilateur.
- Sonde Mesen dédiée au titre et au menu ; cela ne constitue pas un parcours
  complet du jeu ni un test sur cartouche réelle.

Aucune ROM complète n'est distribuée.
