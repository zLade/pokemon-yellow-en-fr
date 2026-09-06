# English translation policy

## Source priority

1. Chinese NJ046 source text and pointer context.
2. Official English Pokémon Red/Blue/Yellow wording when NJ046 clearly
   recreates the same scene and does not change its facts.
3. Official English terminology for Pokémon, moves, items, places and named
   characters when it fits the Chinese meaning.
4. The English anime for anime-specific scenes such as Team Rocket material.
5. The 2015 English ROM and French 2.0 only as comparison witnesses.

The French column in `locales/en-US/catalog.csv` is a secondary gloss. It must
not be back-translated into English or treated as the primary source.

## Fidelity rules

- Preserve speaker, actions, facts, numbers, rewards, branches and event order.
- Preserve NJ046-specific material, including Nanjing, Kameiyu, Beibei,
  Xiaohong, Wei Cunfu, Hoenn, Johto and creator cameos.
- Do not import Game Boy or anime details that are absent from Chinese NJ046.
- Natural English is preferred over literal word order, but meaning may not be
  dropped merely to imitate official wording.
- ROM-size compression must be marked and justified in the catalogue.
- The Team Rocket motto may use recognizable English-anime phrasing only where
  it remains compatible with the Chinese line sequence.

## Review record

`locales/en-US/catalog.csv` contains 1,929 rows: 1,844 main entries and 85
restored entries. Each row stores Chinese source text, old English, French
gloss, final English, provenance, review status, encoded length and any
compression justification.

`official_gen1_scene_audit.csv` and
`official_reference_consistency_changes.csv` record the pass against official
English Red/Blue/Yellow scene wording. The catalogue remains the canonical
build input.
