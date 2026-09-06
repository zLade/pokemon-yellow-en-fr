# Reproductibilité

## Contrôles sans ROM

GitHub Actions vérifie la séparation des langues, l'absence de ROM complète,
les sommes des patchs actifs, les inventaires chinois épinglés et les tests
unitaires qui ne nécessitent pas de ROM.

```sh
python3 tools/validate_branch_separation.py --language fr
python3 -m unittest -v tools.test_validate_french_release
(cd releases/fr/2.0.11 && sha256sum -c SHA256SUMS)
```

## Reconstruction locale

Les ROMs d'entrée doivent être fournies localement et correspondre aux
empreintes de `data/source-roms.sha256`. Mesen est nécessaire aux contrôles
d'affichage. Les ROMs et exécutables ne sont pas distribués avec le projet.

```sh
python3 tools/build_release.py --output-dir build/release-local --expect-current-artifacts
```

La cible FR 2.0.11 a pour SHA-256 :
`efc7ba0837a65d06e0658348d3debaa1194b9cf03b59492a1a8d4dfab346327e`.

Le patch actif s'applique à `yellow.nes`, de SHA-256
`69520103102677b33b47c15fae804dc1a742347a9ee1b02a9195e795eb6e431b`.
Les instructions d'application et les sommes de contrôle sont dans
`releases/fr/2.0.11/`.

Les contrôles de release couvrent la reconstruction exacte, l'intégrité IPS,
le mapper 163, les 1 916 pointeurs attendus et 101 scénarios de limites
dynamiques. Les preuves Mesen doivent correspondre au SHA de la ROM testée.
Les résultats historiques restent liés aux versions indiquées dans leurs rapports.

## Limites de validation

Les tests sur émulateur ne remplacent pas un test matériel. Le fonctionnement
sur une cartouche mapper 163 et une console réelle reste **NON TESTÉ** ; la
procédure est décrite dans `CHECKLIST_TEST_MATERIEL_MAPPER163.md`.
