# NJ046 Chinese-to-English source audit

## Verdict

The September 23, 2015 English ROM is not a globally faithful translation of
Chinese NJ046. It is useful as a technical base and occasional terminology
reference, but not as the semantic source of record.

The pinned extraction found:

| Measure | Result |
| --- | ---: |
| Chinese text blocks | 1,974 |
| Chinese glyph occurrences | 20,832 |
| Distinct resolved glyph codes | 1,352 |
| Inventoried ordinary entries | 1,844 |
| Structurally aligned entries | 1,829 |
| Old-English entries still stored as graphics | 303 |
| Main dialogue/intro entries | 970 |
| Removed English pointer slots | 80 |
| Bad English pointer redirections | 4 |
| Collapsed Anti-Paralyze message | 1 |
| Total restored dialogue entries | 85 |

The complete English catalogue therefore contains 1,929 rows and 1,055
dialogue/intro records after restorations.

## Representative 2015 English failures

| Pointer | Chinese meaning | 2015 English | Problem |
| --- | --- | --- | --- |
| `0x03005D` | No effect | `Missed!` | wrong battle result |
| `0x03006B` | Badly poisoned | `Flinched` | wrong status |
| `0x030163` | Battle lost | `Won!` | inverted meaning |
| `0x031033` | Rock Smash | `Low Kick` | wrong move |
| `0x03103B` | Double Kick | `Revenge` | wrong move |
| `0x0310AD` | False Swipe | `Scratch` | wrong move |
| `0x0310B5` | Snore | `Fake Out` | wrong move |
| `0x0310DB` | Charm | `Bulk-up` | wrong move |
| `0x03834B` | “Not bad!” | `Got Charmander!` | wrong pointer |

The four pointer sites `0x038347`, `0x03834B`, `0x03834F` and `0x038353`
formed one confirmed post-battle redirection group. Anti-Paralyze at
`0x0348F1` had also been collapsed onto the Awakening message.

## Pinned evidence

The Unicode sources are under `data/source/chinese-english-fidelity/`.
`chinese_records.csv` and `chinese_glyph_map.csv` are immutable inputs. HZK16
is absent, so this branch does not claim a new bitmap-to-Unicode extraction.
Derived tables may be checked from the pinned CSV sources, but that process is
not a replacement HZK16 extraction.

Structural alignment confidence does not prove semantic fidelity. The final
English review is recorded row by row in `locales/en-US/catalog.csv`, with 63
explicit source adjudications and five pointer variants for shared legacy
payloads.
