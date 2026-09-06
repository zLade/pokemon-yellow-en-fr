# Build and release guide

## Build inputs

No complete ROM is tracked. Restore the inputs named in
`data/source-inputs.sha256` and verify their SHA-256 values before building.
The three relevant bases are:

- Chinese NJ046: `450d40c0…c65ed`;
- 2015 English work base: `d5c308b5…9943b`;
- canonical `yellow.nes`: `69520103…e431b`.

Never use a headerless `.nes.bin` file.

## Static gates

```sh
python3 tools/validate_branch_separation.py --language en
python3 tools/validate_english_catalog.py
python3 tools/refresh_chinese_fidelity_derivatives.py --check
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

The catalogue gate requires:

- 1,844 main entries plus 85 restored entries;
- 1,055 dialogue/intro records;
- 159 Pokédex records;
- 63 completed source adjudications;
- five reviewed pointer variants and three documented storage overlaps;
- no pending review state, empty English payload or unsupported codec byte.

## Release builder

`tools/build_english_release.py` performs two independent builds, checks
catalogue and pointer topology, verifies mapper 163 constraints, regenerates
IPS/BPS patches, runs English-specific evidence gates, and verifies French
non-regression against pinned golden hashes.

```sh
python3 tools/build_english_release.py \
  --chinese-rom 'Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes' \
  --english-2015-rom 'Pokemon Yellow English 9-23-2015.nes' \
  --yellow-rom yellow.nes \
  --audits-dir build/evidence/en/2.0.0/audits \
  --mesen-logs-dir build/evidence/en/2.0.0/mesen \
  --private-dir build/private/en/2.0.0 \
  --dist-dir dist/en/2.0.0 \
  --lunar-ips-exe '<local Lunar IPS executable>' \
  --floating-ips-exe '<local Floating IPS executable>' \
  --floating-ips-archive '<pinned Floating IPS archive>' \
  --external-verified-utc '<YYYY-MM-DDTHH:MM:SSZ>'
```

External patcher paths and the timestamp are mandatory for the final wrapper.
Complete ROM output remains under ignored `build/private`; the distributable
directory contains patches and documentation only.

## Published credited target

The current release patch files under `releases/en/2.0.0/` produce target
SHA-256 `d68597ad34d7772435af7422d37dee1b1e0dc78714b37098c9145290be04b9d4`.
The title is `YELLOW VERSION` with `LUIGA2009, ZLADE, CHPEXO` rendered in the
original title-credit style.

The published `SHA256SUMS` must be checked after download. Each IPS/BPS route
was round-tripped byte-for-byte against the credited target before commit.
