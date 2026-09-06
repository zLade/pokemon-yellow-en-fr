# English 2.0 validation status

## Verified

- 1,929 catalogue rows: 1,844 main and 85 restored.
- 1,055 dialogue/intro records and 159 Pokédex records.
- All source records resolved; 63 manual adjudications recorded.
- All 80 removed English slots restored.
- All four bad pointer redirections corrected.
- Anti-Paralyze restored as a distinct message.
- Five variants split two shared legacy payloads into their correct meanings.
- Strict English codec and English pagination gates pass.
- No complete ROM is tracked; release output is IPS/BPS only.
- All three published patch routes reproduce the same credited target.
- Mapper 163 static validation passes for target `d68597ad…`.
- The true `YELLOW VERSION` title and the three credits passed their targeted
  Mesen scenario.
- French golden non-regression remains a required English-builder gate.

## Editorial qualification

The English corpus received an AI-assisted full source review, including a
consistency pass against official English Red/Blue/Yellow references where
NJ046 imitates the corresponding scene. Official language was retained only
when compatible with Chinese NJ046. A complete human editorial playthrough is
still pending.

## Not claimed

- No new HZK16 extraction; HZK16 is absent.
- No complete human playthrough.
- No proof that every dialogue branch was naturally visited.
- No proof that inherited uninitialized-RAM behavior is harmless.
- No physical mapper-163 hardware test.
- No affiliation with Nintendo, Game Freak or The Pokémon Company.
