# Modular CHR assets — inherited French tooling

This directory is intentionally retained as a technical dependency of the
French golden non-regression check. It is **not** the graphics workflow for
the English release.

The English branch keeps the original English font and English menus. Its
title workflow is implemented by `tools/title_screen_tools.py` using canonical
`yellow.nes` as the `YELLOW VERSION` reference. The shared title credits are
rendered as `LUIGA2009, ZLADE, CHPEXO` without importing French menu or font
graphics.

The historical modular-CHR pack itself is ignored locally except for this
README. Its old French snapshots, generated manifests and binary assets are
not part of the tracked English source tree. For current English validation,
use `tools/validate_mapper163.py --profile en-US` and the title/player-menu
probes in `tools/run-mesen-english-regression-suite.ps1`.

The maintained French CHR workflow and its complete documentation remain on
the `fr` branch.
