"""Read the English catalogue directory or an explicit single-file fixture."""
from __future__ import annotations

import csv
import io
from pathlib import Path

PART_NAMES = ("catalog_part_1.csv", "catalog_part_2.csv")
GITHUB_CSV_LIMIT = 512 * 1024


def catalogue_paths(path: str | Path) -> tuple[Path, ...]:
    path = Path(path)
    return tuple(path / name for name in PART_NAMES) if path.is_dir() else (path,)


def catalogue_bytes(path: str | Path) -> bytes:
    paths = catalogue_paths(path)
    if len(paths) == 1:
        return paths[0].read_bytes()
    chunks = []
    header = None
    seen = set()
    for part in paths:
        raw = part.read_bytes()
        if len(raw) > GITHUB_CSV_LIMIT:
            raise ValueError(f"{part.name} exceeds GitHub's 512 KiB CSV limit; rebalance complete rows between the two parts")
        text = raw.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
        if len(rows) < 2 or not rows[0] or len(set(rows[0])) != len(rows[0]):
            raise ValueError(f"{part.name}: missing rows or invalid header")
        if header is None:
            header = rows[0]
        elif rows[0] != header:
            raise ValueError(f"{part.name}: catalogue headers differ")
        key_column = header.index("stable_key")
        for row in rows[1:]:
            if len(row) != len(header):
                raise ValueError(f"{part.name}: inconsistent column count")
            key = row[key_column]
            if not key or key in seen:
                raise ValueError(f"{part.name}: missing or duplicate stable_key {key!r}")
            seen.add(key)
        # Headers have no embedded newline. Preserve every data byte, including
        # whitespace and quoted multiline fields, without rewriting the CSV.
        if any("\n" in field or "\r" in field for field in header):
            raise ValueError("Multiline catalogue headers are unsupported")
        body = text.split("\n", 1)[1]
        chunks.append(text if len(chunks) == 0 else body)
        if not chunks[-1].endswith("\n"):
            chunks[-1] += "\n"
    return "".join(chunks).encode("utf-8")


def open_csv(path: str | Path) -> io.StringIO:
    return io.StringIO(catalogue_bytes(path).decode("utf-8-sig"), newline="")
