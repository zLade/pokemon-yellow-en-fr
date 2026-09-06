# Pokémon Jaune NES — branche française

Projet de préservation et de développement de la traduction française du bootleg Famicom **Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046)**.

> Branche canonique : **`fr` (français uniquement)**
> Développement anglais : **`en`**

## État de la version française

- version de référence : **FR 2.0.11** ;
- SHA-256 de la ROM finale créditée (non distribuée) : `efc7ba0837a65d06e0658348d3debaa1194b9cf03b59492a1a8d4dfab346327e` ;
- mapper : **163** ;
- manifeste de pointeurs certifié : **1 916/1 916** ;
- matrice de limites dynamiques certifiée : **101/101** ;
- scénarios Mesen ciblés, dont le curseur interactif d'oubli d'attaque : **PASS** ; test sur matériel réel toujours indiqué comme **NON TESTÉ**.

Aucune ROM n'est enregistrée dans ce dépôt. Les patchs FR actifs sont sous
`releases/fr/2.0.11/`; les versions précédentes restent archivées sous
`releases/fr/`. Les fichiers d'entrée nécessaires doivent être fournis
localement et correspondre aux empreintes documentées avec chaque release.

## Sources canoniques

- `script.py` : corpus français maître ;
- `traduction_base.csv` : table de traduction matérialisée ;
- `rom_traduction_assistant.py` : extraction, repack et restauration ;
- `tools/` : builder, audits, tests et scénarios Mesen ;
- `build/chinese-english-fidelity/extraction/` : données Unicode chinoises épinglées nécessaires au travail de fidélité ;
- `LISTE_EXHAUSTIVE_DIALOGUES.csv` : matrice des 1 055 dialogues.

La procédure complète se trouve dans `MODE_EMPLOI_TRADUCTION.md` et le bilan de la release dans `RAPPORT_RELEASE_2026-08-09.md`.
Les règles de contribution sont dans `CONTRIBUTING.md`, l'historique actif dans
`CHANGELOG.md`, la reproductibilité dans `docs/fr/REPRODUCTIBILITE.md` et le
périmètre des éléments tiers dans `NOTICE.md`.

## Vérifications principales

Après avoir remis les ROM d'entrée ignorées à la racine :

```bash
python3 rom_traduction_assistant.py check
python3 tools/refresh_chinese_fidelity_derivatives.py --check
sha256sum -c releases/fr/2.0.11/SHA256SUMS
python3 -m unittest -v tools.test_validate_french_release
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 tools/build_release.py \
  --output-dir build/release-local \
  --expect-current-artifacts
```

La release FR 2.0.11 reconstruit exactement la cible certifiée à partir de
`yellow.nes` (SHA-256 `69520103…`). Les contrôles indépendants couvrent
l'intégrité IPS, le mapper 163, les 1 916 pointeurs attendus, 101 scénarios de
limites dynamiques, les écrans Mesen ciblés et la correction de la table de
hauteur musicale.

## Organisation des langues

`fr` conserve exclusivement la version française reproductible. Elle ne doit
contenir ni catalogue `locales/en-US`, ni outils de release anglaise, ni
livrables `releases/en`.

La version anglaise vit exclusivement sur `en`. Les deux branches
utilisent certaines infrastructures techniques communes, mais leurs
catalogues et leurs patchs publiés restent séparés. Le script
`tools/validate_branch_separation.py` vérifie ce contrat.

Ce dépôt ne déclare pas de licence globale : le code, les textes, les marques et les données dérivées peuvent relever de régimes différents.
