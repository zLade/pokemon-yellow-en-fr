# Contribuer à la branche française

La branche française canonique est `fr`. La version anglaise est maintenue
séparément sur `en`.

## Règles

- Ne jamais committer de ROM complète, sauvegarde, état d'émulateur ou
  exécutable propriétaire. Seuls les sources, données de validation et patchs
  IPS/BPS peuvent être versionnés.
- Modifier le corpus maître dans `script.py` et régénérer ses dérivés avec les
  outils existants ; ne pas corriger uniquement une ROM construite.
- Conserver les clés, pointeurs et preuves de provenance chinoise.
- Préserver les contraintes de pagination et ne jamais accepter de troncature.
- Garder les catalogues et livrables anglais hors de `fr`.

## Contrôles sans ROM

```sh
python3 tools/validate_branch_separation.py --language fr
(cd releases/fr/2.0.11 && sha256sum -c SHA256SUMS)
python3 -m unittest -v \
  tools.test_validate_branch_separation \
  tools.test_dialogue_layout \
  tools.test_dialogue_page_quality \
  tools.test_dialogue_inventory \
  tools.test_coherence_corrections \
  tools.test_french_naturalization \
  tools.test_apply_dialogue_page_plan
```

La régénération complète des dérivés chinois, le build intégral et Mesen
nécessitent les ROMs d’entrée ayant les SHA-256
documentés. Publier les résultats des tests, jamais les ROMs elles-mêmes.
