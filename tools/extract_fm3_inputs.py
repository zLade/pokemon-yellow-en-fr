#!/usr/bin/env python3
"""Extract NES controller bytes from an FCEUX FM2/FM3 input log.

The TASVideos FM3 downloads used by this project are a gzip stream containing
a ZIP archive containing a compact (binary-input) FM3 file.  This tool also
accepts the inner ZIP/FM3 directly.  It deliberately exports only controller
1 input and rejects savestate starts, resets, or unsupported peripherals so a
Mesen replay cannot silently omit part of the source movie's initial state.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


GAMEPAD = 1
NONE = 0


class MovieFormatError(ValueError):
    """Raised when an input movie is unsupported or malformed."""


def _unwrap(data: bytes) -> tuple[bytes, list[str]]:
    wrappers: list[str] = []
    while True:
        if data.startswith(b"\x1f\x8b"):
            data = gzip.decompress(data)
            wrappers.append("gzip")
            continue
        if data.startswith(b"PK\x03\x04"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                files = [
                    info for info in archive.infolist() if not info.is_dir()
                ]
                if len(files) != 1:
                    raise MovieFormatError(
                        "ZIP wrapper must contain exactly one movie file"
                    )
                data = archive.read(files[0])
                wrappers.append(f"zip:{files[0].filename}")
            continue
        return data, wrappers


def _parse_header(data: bytes) -> tuple[dict[str, list[str]], int]:
    # A comment/subtitle value may legally contain "|".  The binary input log
    # begins on its own line, so do not accept the first arbitrary pipe byte.
    line_marker = data.find(b"\n|")
    if line_marker < 0:
        raise MovieFormatError("FM2/FM3 input log marker '|' was not found")
    marker = line_marker + 1
    try:
        header_text = data[:marker].decode("ascii")
    except UnicodeDecodeError as exc:
        raise MovieFormatError("movie header is not ASCII") from exc

    header: dict[str, list[str]] = {}
    lines = header_text.splitlines()
    if not lines or not lines[0].startswith("version "):
        raise MovieFormatError("the first movie header field must be version")
    for line in lines:
        if not line:
            continue
        key, separator, value = line.partition(" ")
        if not separator:
            raise MovieFormatError(f"malformed header line: {line!r}")
        header.setdefault(key, []).append(value)
    return header, marker + 1


def _one(header: dict[str, list[str]], key: str) -> str:
    values = header.get(key)
    if values is None or len(values) != 1:
        raise MovieFormatError(f"expected one {key!r} header field")
    return values[0]


def _integer(
    header: dict[str, list[str]],
    key: str,
    *,
    default: int | None = None,
) -> int:
    values = header.get(key)
    if values is None:
        if default is None:
            raise MovieFormatError(f"expected one {key!r} header field")
        return default
    if len(values) != 1:
        raise MovieFormatError(f"expected one {key!r} header field")
    try:
        value = int(values[0])
    except ValueError as exc:
        raise MovieFormatError(
            f"{key!r} header field is not an integer"
        ) from exc
    if value < -(2**31) or value >= 2**31:
        raise MovieFormatError(f"{key!r} header field is outside int32")
    return value


def extract_controller_bytes(
    container: bytes,
) -> tuple[bytes, dict[str, object]]:
    movie, wrappers = _unwrap(container)
    header, input_start = _parse_header(movie)

    numeric = {
        key: _integer(header, key)
        for key in ("version", "binary", "fourscore", "port0", "port1", "port2")
    }
    numeric.update(
        {
            "emuVersion": _integer(header, "emuVersion"),
            "palFlag": _integer(header, "palFlag", default=0),
            "NewPPU": _integer(header, "NewPPU", default=0),
            "FDS": _integer(header, "FDS", default=0),
            "microphone": _integer(header, "microphone", default=0),
        }
    )
    if numeric["version"] != 3:
        raise MovieFormatError("only FM2/FM3 version 3 is supported")
    if numeric["binary"] != 1:
        raise MovieFormatError("only compact binary input logs are supported")
    if numeric["fourscore"] != 0:
        raise MovieFormatError("Four Score movies are not supported")
    if (
        numeric["port0"] != GAMEPAD
        or numeric["port1"] != NONE
        or numeric["port2"] != NONE
    ):
        raise MovieFormatError(
            "expected one gamepad on port 0 and no other peripherals"
        )
    if numeric["FDS"] != 0 or numeric["microphone"] != 0:
        raise MovieFormatError("FDS and microphone movies are not supported")
    if numeric["palFlag"] not in (0, 1) or numeric["NewPPU"] not in (0, 1):
        raise MovieFormatError("movie timing/PPU flags must be boolean")
    if "savestate" in header:
        raise MovieFormatError(
            "movies starting from an embedded savestate are not supported"
        )

    frame_count = _integer(header, "length")
    if frame_count < 0:
        raise MovieFormatError("movie length must be non-negative")
    record_bytes = frame_count * 2
    log = movie[input_start : input_start + record_bytes]
    if len(log) != record_bytes:
        raise MovieFormatError("binary input log is shorter than declared")

    commands = log[0::2]
    command_frames = [
        frame for frame, command in enumerate(commands) if command != 0
    ]
    if command_frames:
        preview = ", ".join(str(frame) for frame in command_frames[:8])
        raise MovieFormatError(
            "movie contains reset/system commands at frame(s): " + preview
        )

    inputs = log[1::2]
    rom_checksum = _one(header, "romChecksum")
    if not rom_checksum.startswith("base64:"):
        raise MovieFormatError("unsupported romChecksum encoding")
    try:
        checksum_bytes = base64.b64decode(
            rom_checksum.removeprefix("base64:"), validate=True
        )
    except ValueError as exc:
        raise MovieFormatError("invalid base64 ROM checksum") from exc
    if len(checksum_bytes) != 16:
        raise MovieFormatError("ROM checksum is not a 16-byte MD5")
    prg_md5 = checksum_bytes.hex()

    metadata: dict[str, object] = {
        "format_version": numeric["version"],
        "emulator_version": numeric["emuVersion"],
        "frames": frame_count,
        "source_region": "pal" if numeric["palFlag"] else "ntsc",
        "source_new_ppu": bool(numeric["NewPPU"]),
        "starts_from_power_on": True,
        "wrappers": wrappers,
        "rom_filename": _one(header, "romFilename"),
        "rom_prg_md5": prg_md5,
        "authors": [
            value.removeprefix("author ")
            for value in header.get("comment", [])
            if value.startswith("author ")
        ],
        "input_sha256": hashlib.sha256(inputs).hexdigest(),
        "active_frames": sum(value != 0 for value in inputs),
        "button_bits": {
            "a": 0,
            "b": 1,
            "select": 2,
            "start": 3,
            "up": 4,
            "down": 5,
            "left": 6,
            "right": 7,
        },
    }
    return inputs, metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("movie", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--metadata",
        type=Path,
        help="JSON metadata path (default: OUTPUT.json)",
    )
    args = parser.parse_args()

    inputs, metadata = extract_controller_bytes(args.movie.read_bytes())
    metadata_path = args.metadata or Path(str(args.output) + ".json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(inputs)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Extracted {len(inputs)} controller frames to {args.output} "
        f"(SHA-256 {metadata['input_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
