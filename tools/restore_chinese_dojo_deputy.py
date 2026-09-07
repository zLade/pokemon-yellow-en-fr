#!/usr/bin/env python3
"""Restore the original NJ046 Fighting Dojo deputy in a translated ROM."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rom_builder import make_ips  # noqa: E402


CHINESE_SHA256 = (
    "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e6"
    "5271e2f7b40c65ed"
)
SPRITE_PACKAGE_START = 0x1CA271
SPRITE_PACKAGE_END = 0x1CA47C
SPRITE_PACKAGE_SHA256 = (
    "abb3b8cb27f8d383412c1620bcb23d11996afbc3aa73aa17"
    "2af6062057ee9dd6"
)
DOJO_EVENT_START = 0x0C26B2
DOJO_EVENT_END = 0x0C2736
DOJO_EVENT_SHA256 = (
    "08c431c656e2221c9409e0ef38fcdb062206af46076f6615"
    "b66122dcb1971940"
)


class RestorationError(ValueError):
    """The ROM is not a safe target for the original cameo restoration."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def restore(candidate: bytes, chinese: bytes) -> bytes:
    if sha256(chinese) != CHINESE_SHA256:
        raise RestorationError("Chinese NJ046 source hash mismatch")
    if len(candidate) != len(chinese):
        raise RestorationError("candidate/source ROM size mismatch")

    sprite = chinese[SPRITE_PACKAGE_START:SPRITE_PACKAGE_END]
    event = chinese[DOJO_EVENT_START:DOJO_EVENT_END]
    if sha256(sprite) != SPRITE_PACKAGE_SHA256:
        raise RestorationError("Chinese dojo deputy sprite package mismatch")
    if sha256(event) != DOJO_EVENT_SHA256:
        raise RestorationError("Chinese dojo battle event data mismatch")
    if candidate[DOJO_EVENT_START:DOJO_EVENT_END] != event:
        raise RestorationError(
            "candidate dojo battle event differs from the Chinese original"
        )

    restored = bytearray(candidate)
    restored[SPRITE_PACKAGE_START:SPRITE_PACKAGE_END] = sprite
    # This is intentionally idempotent today.  Keeping the event copy here
    # makes the battle-data restoration explicit and guards future builds.
    restored[DOJO_EVENT_START:DOJO_EVENT_END] = event
    return bytes(restored)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--chinese-rom", type=Path, required=True)
    parser.add_argument("--out-rom", type=Path, required=True)
    parser.add_argument("--base-rom", type=Path)
    parser.add_argument("--out-ips", type=Path)
    args = parser.parse_args()
    if bool(args.base_rom) != bool(args.out_ips):
        parser.error("--base-rom and --out-ips must be supplied together")

    restored = restore(args.rom.read_bytes(), args.chinese_rom.read_bytes())
    args.out_rom.parent.mkdir(parents=True, exist_ok=True)
    args.out_rom.write_bytes(restored)
    if args.out_ips:
        base = args.base_rom.read_bytes()
        if len(base) != len(restored):
            raise RestorationError("IPS base/candidate ROM size mismatch")
        args.out_ips.parent.mkdir(parents=True, exist_ok=True)
        args.out_ips.write_bytes(make_ips(base, restored))

    print(
        "Chinese dojo deputy restored: "
        f"sprite 0x{SPRITE_PACKAGE_START:06X}-0x{SPRITE_PACKAGE_END:06X}, "
        f"battle event 0x{DOJO_EVENT_START:06X}-0x{DOJO_EVENT_END:06X}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
