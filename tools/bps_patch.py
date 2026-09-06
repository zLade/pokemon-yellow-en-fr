#!/usr/bin/env python3
"""Create and apply deterministic BPS1 patches.

The writer deliberately emits only ``SourceRead`` and ``TargetRead`` actions.
That keeps the implementation small and auditable while still producing a
standards-compliant patch with source, target and patch CRC32 checksums.
The reader accepts all four BPS action types so externally produced patches
can also be verified.
"""

from __future__ import annotations

import argparse
import binascii
import struct
from dataclasses import dataclass
from pathlib import Path


BPS_MAGIC = b"BPS1"


class BpsError(ValueError):
    """Raised when a BPS patch is malformed or fails a checksum."""


def encode_number(value: int) -> bytes:
    if value < 0:
        raise ValueError("BPS numbers must be non-negative")
    output = bytearray()
    while True:
        current = value & 0x7F
        value >>= 7
        if value == 0:
            output.append(0x80 | current)
            return bytes(output)
        output.append(current)
        value -= 1


def decode_number(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 1
    while True:
        if offset >= len(data):
            raise BpsError("truncated BPS variable-length number")
        current = data[offset]
        offset += 1
        value += (current & 0x7F) * shift
        if current & 0x80:
            return value, offset
        shift <<= 7
        value += shift


def _decode_signed(value: int) -> int:
    magnitude = value >> 1
    return -magnitude if value & 1 else magnitude


def _crc32(data: bytes) -> int:
    return binascii.crc32(data) & 0xFFFFFFFF


@dataclass(frozen=True)
class BpsInfo:
    source_size: int
    target_size: int
    metadata: bytes
    source_crc32: int
    target_crc32: int
    patch_crc32: int


def create_patch(
    source: bytes,
    target: bytes,
    *,
    metadata: bytes = b"",
) -> bytes:
    """Return a deterministic BPS1 patch from *source* to *target*."""

    patch = bytearray(BPS_MAGIC)
    patch.extend(encode_number(len(source)))
    patch.extend(encode_number(len(target)))
    patch.extend(encode_number(len(metadata)))
    patch.extend(metadata)

    offset = 0
    while offset < len(target):
        same_position = (
            offset < len(source) and source[offset] == target[offset]
        )
        end = offset + 1
        if same_position:
            while (
                end < len(target)
                and end < len(source)
                and source[end] == target[end]
            ):
                end += 1
            action = 0  # SourceRead
        else:
            while end < len(target):
                if end < len(source) and source[end] == target[end]:
                    break
                end += 1
            action = 1  # TargetRead

        length = end - offset
        patch.extend(encode_number(((length - 1) << 2) | action))
        if action == 1:
            patch.extend(target[offset:end])
        offset = end

    patch.extend(struct.pack("<I", _crc32(source)))
    patch.extend(struct.pack("<I", _crc32(target)))
    patch.extend(struct.pack("<I", _crc32(patch)))
    return bytes(patch)


def inspect_patch(patch: bytes) -> BpsInfo:
    if len(patch) < 16 or not patch.startswith(BPS_MAGIC):
        raise BpsError("invalid or truncated BPS1 patch")
    stored_patch_crc = struct.unpack_from("<I", patch, len(patch) - 4)[0]
    computed_patch_crc = _crc32(patch[:-4])
    if stored_patch_crc != computed_patch_crc:
        raise BpsError(
            "BPS patch checksum mismatch: "
            f"{stored_patch_crc:08x} != {computed_patch_crc:08x}"
        )

    offset = len(BPS_MAGIC)
    source_size, offset = decode_number(patch, offset)
    target_size, offset = decode_number(patch, offset)
    metadata_size, offset = decode_number(patch, offset)
    metadata_end = offset + metadata_size
    if metadata_end > len(patch) - 12:
        raise BpsError("truncated BPS metadata")
    metadata = patch[offset:metadata_end]
    source_crc, target_crc, patch_crc = struct.unpack_from(
        "<III",
        patch,
        len(patch) - 12,
    )
    return BpsInfo(
        source_size=source_size,
        target_size=target_size,
        metadata=metadata,
        source_crc32=source_crc,
        target_crc32=target_crc,
        patch_crc32=patch_crc,
    )


def apply_patch(source: bytes, patch: bytes) -> bytes:
    info = inspect_patch(patch)
    if len(source) != info.source_size:
        raise BpsError(
            f"BPS source size mismatch: {len(source)} != {info.source_size}"
        )
    source_crc = _crc32(source)
    if source_crc != info.source_crc32:
        raise BpsError(
            "BPS source checksum mismatch: "
            f"{source_crc:08x} != {info.source_crc32:08x}"
        )

    offset = len(BPS_MAGIC)
    _, offset = decode_number(patch, offset)
    _, offset = decode_number(patch, offset)
    metadata_size, offset = decode_number(patch, offset)
    offset += metadata_size
    action_end = len(patch) - 12

    target = bytearray()
    source_relative = 0
    target_relative = 0
    while len(target) < info.target_size:
        if offset >= action_end:
            raise BpsError("BPS action stream ended before target was complete")
        command, offset = decode_number(patch, offset)
        action = command & 3
        length = (command >> 2) + 1

        if len(target) + length > info.target_size:
            raise BpsError("BPS action exceeds declared target size")
        if action == 0:  # SourceRead
            start = len(target)
            end = start + length
            if end > len(source):
                raise BpsError("BPS SourceRead exceeds source size")
            target.extend(source[start:end])
        elif action == 1:  # TargetRead
            end = offset + length
            if end > action_end:
                raise BpsError("truncated BPS TargetRead payload")
            target.extend(patch[offset:end])
            offset = end
        elif action == 2:  # SourceCopy
            relative, offset = decode_number(patch, offset)
            source_relative += _decode_signed(relative)
            end = source_relative + length
            if source_relative < 0 or end > len(source):
                raise BpsError("BPS SourceCopy exceeds source size")
            target.extend(source[source_relative:end])
            source_relative = end
        else:  # TargetCopy
            relative, offset = decode_number(patch, offset)
            target_relative += _decode_signed(relative)
            if target_relative < 0 or target_relative >= len(target):
                raise BpsError("BPS TargetCopy starts outside target data")
            for _ in range(length):
                if target_relative >= len(target):
                    raise BpsError("BPS TargetCopy reads unavailable target data")
                target.append(target[target_relative])
                target_relative += 1

    if offset != action_end:
        raise BpsError("unexpected bytes after BPS action stream")
    target_bytes = bytes(target)
    target_crc = _crc32(target_bytes)
    if target_crc != info.target_crc32:
        raise BpsError(
            "BPS target checksum mismatch: "
            f"{target_crc:08x} != {info.target_crc32:08x}"
        )
    return target_bytes


def _read(path: Path) -> bytes:
    return path.read_bytes()


def _command_create(args: argparse.Namespace) -> int:
    source = _read(args.source)
    target = _read(args.target)
    metadata = args.metadata.encode("utf-8")
    patch = create_patch(source, target, metadata=metadata)
    args.patch.parent.mkdir(parents=True, exist_ok=True)
    args.patch.write_bytes(patch)
    if apply_patch(source, patch) != target:
        raise AssertionError("internal BPS roundtrip failed")
    print(f"BPS: {args.patch}")
    print(f"Source: {len(source)} bytes, CRC32={_crc32(source):08x}")
    print(f"Target: {len(target)} bytes, CRC32={_crc32(target):08x}")
    print(f"Patch: {len(patch)} bytes, CRC32={_crc32(patch):08x}")
    return 0


def _command_apply(args: argparse.Namespace) -> int:
    target = apply_patch(_read(args.source), _read(args.patch))
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_bytes(target)
    print(f"Target: {args.target} ({len(target)} bytes)")
    return 0


def _command_verify(args: argparse.Namespace) -> int:
    expected = _read(args.target)
    actual = apply_patch(_read(args.source), _read(args.patch))
    if actual != expected:
        raise BpsError("BPS output differs from expected target")
    info = inspect_patch(_read(args.patch))
    print(
        "BPS PASS "
        f"source={info.source_size} target={info.target_size} "
        f"metadata={info.metadata.decode('utf-8', errors='replace')!r}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create/apply BPS1 patches")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--source", type=Path, required=True)
    create.add_argument("--target", type=Path, required=True)
    create.add_argument("--patch", type=Path, required=True)
    create.add_argument("--metadata", default="")
    create.set_defaults(func=_command_create)

    apply = subparsers.add_parser("apply")
    apply.add_argument("--source", type=Path, required=True)
    apply.add_argument("--patch", type=Path, required=True)
    apply.add_argument("--target", type=Path, required=True)
    apply.set_defaults(func=_command_apply)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--source", type=Path, required=True)
    verify.add_argument("--patch", type=Path, required=True)
    verify.add_argument("--target", type=Path, required=True)
    verify.set_defaults(func=_command_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
