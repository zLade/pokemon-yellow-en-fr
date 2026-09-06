#!/usr/bin/env python3
"""Generate byte-level IPS/BPS evidence with the official Windows patchers.

The script is intended to run either from native Windows Python or from WSL
with Windows interoperability enabled.  Lunar IPS applies an IPS patch in
place, so every source ROM and patch is first copied into an isolated temporary
directory.  The original release inputs are only read and are hashed again
after all three patcher invocations.

Only a complete PASS report is published.  A command failure, a changed input,
or one byte differing from the target ROM leaves an existing report untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent

SCHEMA = "pokemon-yellow-nes-external-patcher-proof/v1"
LUNAR_VERSION = "1.03 x64"
FLIPS_VERSION = "v198 Windows"
FLIPS_SOURCE = "https://github.com/Alcaro/Flips/releases/tag/v198"


class ProofError(RuntimeError):
    """The external patcher evidence could not be certified."""


@dataclass(frozen=True)
class ToolPins:
    """Known hashes for the exact official patcher distribution files."""

    lunar_executable_sha256: str
    flips_executable_sha256: str
    flips_archive_sha256: str


OFFICIAL_TOOL_PINS = ToolPins(
    lunar_executable_sha256=(
        "9e67a1f3105092bda45cf02ac638e2d014e9a1aa28cc9a78c801881eb72f82be"
    ),
    flips_executable_sha256=(
        "ca6b364ccb23ab83ff0f4458f589eac001e7baf74315decde73c878a8eb519fd"
    ),
    flips_archive_sha256=(
        "802bfb315dca08a2f765dd6864472ecbb2b482681045c573d5e4b657b8e5295d"
    ),
)


@dataclass(frozen=True)
class ProofConfig:
    root: Path
    target_rom: Path
    ips_base: Path
    ips_patch: Path
    chinese_base: Path
    chinese_bps: Path
    english_base: Path
    english_bps: Path
    lunar_executable: Path
    flips_executable: Path
    flips_archive: Path
    output: Path
    temp_parent: Path
    verified_utc: str
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class FileSnapshot:
    size: int
    sha256: str


CommandRunner = Callable[
    [Sequence[str], Path, float], subprocess.CompletedProcess[str]
]
PathConverter = Callable[[Path], str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(path: Path) -> FileSnapshot:
    return FileSnapshot(size=path.stat().st_size, sha256=sha256_file(path))


def files_are_identical(left: Path, right: Path) -> bool:
    """Compare regular files byte for byte without loading a ROM into memory."""

    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as left_handle, right.open("rb") as right_handle:
        while True:
            left_chunk = left_handle.read(1024 * 1024)
            right_chunk = right_handle.read(1024 * 1024)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ProofError(f"{label} absent ou non régulier : {resolved}")
    return resolved


def display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def canonical_verified_utc(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None:
        raise ProofError(
            "--verified-utc doit respecter exactement YYYY-MM-DDTHH:MM:SSZ"
        )
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ProofError(f"--verified-utc invalide : {value}") from exc
    return value


def default_command_runner(
    command: Sequence[str], cwd: Path, timeout: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _is_wsl() -> bool:
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text(
            encoding="ascii", errors="ignore"
        )
    except OSError:
        return False
    return "microsoft" in release.casefold()


def windows_path(path: Path) -> str:
    """Return a path understood by a Windows executable on Windows or WSL."""

    resolved = path.resolve()
    if os.name == "nt":
        return str(resolved)
    if not _is_wsl():
        raise ProofError(
            "les patchers Windows exigent Windows ou WSL avec interopérabilité"
        )
    try:
        converted = subprocess.run(
            ["wslpath", "-w", "--", str(resolved)],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProofError(f"conversion wslpath impossible pour {resolved}: {exc}") from exc
    value = converted.stdout.strip()
    if converted.returncode != 0 or not value:
        detail = converted.stderr.strip() or f"code {converted.returncode}"
        raise ProofError(f"conversion wslpath impossible pour {resolved}: {detail}")
    return value


def _archive_members_matching_hash(archive: Path, wanted_sha256: str) -> list[str]:
    matches: list[str] = []
    try:
        with zipfile.ZipFile(archive) as bundle:
            for info in sorted(bundle.infolist(), key=lambda item: item.filename):
                if info.is_dir():
                    continue
                digest = hashlib.sha256()
                with bundle.open(info, "r") as member:
                    for chunk in iter(lambda: member.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() == wanted_sha256:
                    matches.append(info.filename)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ProofError(f"archive Flips ZIP illisible : {archive}: {exc}") from exc
    return matches


def _run_checked(
    runner: CommandRunner,
    command: Sequence[str],
    cwd: Path,
    timeout: float,
    label: str,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = runner(command, cwd, timeout)
    except subprocess.TimeoutExpired as exc:
        raise ProofError(f"{label} a dépassé {timeout:g} secondes") from exc
    except OSError as exc:
        raise ProofError(f"impossible de lancer {label}: {exc}") from exc
    if completed.returncode != 0:
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        detail = stderr or stdout or "aucune sortie"
        if len(detail) > 1000:
            detail = detail[-1000:]
        raise ProofError(f"{label} a échoué (code {completed.returncode}) : {detail}")
    return completed


def _copy_regular(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _normal_command(executable: Path, *arguments: Path | str) -> list[str]:
    normalized = [executable.name]
    for argument in arguments:
        normalized.append(argument.name if isinstance(argument, Path) else argument)
    return normalized


def _roundtrip_record(
    *,
    format_name: str,
    tool: str,
    base: Path,
    patch: Path,
    output: Path,
    target: Path,
    root: Path,
    command: Sequence[str],
    returncode: int,
) -> dict[str, object]:
    output_hash = sha256_file(output)
    if output_hash != sha256_file(target) or not files_are_identical(output, target):
        raise ProofError(
            f"sortie {format_name} non identique à la ROM cible : {output.name}"
        )
    return {
        "format": format_name,
        "tool": tool,
        "base": display_path(base, root),
        "base_size": base.stat().st_size,
        "base_sha256": sha256_file(base),
        "patch": display_path(patch, root),
        "patch_size": patch.stat().st_size,
        "patch_sha256": sha256_file(patch),
        "output_size": output.stat().st_size,
        "output_sha256": output_hash,
        "byte_identical_to_target": True,
        "command": list(command),
        "returncode": returncode,
        "result": "PASS",
    }


def _input_paths(config: ProofConfig) -> dict[str, Path]:
    return {
        "target ROM": config.target_rom,
        "base IPS": config.ips_base,
        "patch IPS": config.ips_patch,
        "base BPS chinoise": config.chinese_base,
        "patch BPS chinoise": config.chinese_bps,
        "base BPS anglaise": config.english_base,
        "patch BPS anglaise": config.english_bps,
        "Lunar IPS": config.lunar_executable,
        "Floating IPS": config.flips_executable,
        "archive Floating IPS": config.flips_archive,
    }


def _validated_config(config: ProofConfig) -> ProofConfig:
    if config.timeout_seconds <= 0:
        raise ProofError("le délai d'exécution doit être strictement positif")
    root = config.root.expanduser().resolve()
    if not root.is_dir():
        raise ProofError(f"racine absente : {root}")
    values = {
        field: require_file(path, label)
        for field, path, label in (
            ("target_rom", config.target_rom, "ROM cible"),
            ("ips_base", config.ips_base, "base IPS"),
            ("ips_patch", config.ips_patch, "patch IPS"),
            ("chinese_base", config.chinese_base, "base chinoise"),
            ("chinese_bps", config.chinese_bps, "BPS chinoise"),
            ("english_base", config.english_base, "base anglaise"),
            ("english_bps", config.english_bps, "BPS anglaise"),
            ("lunar_executable", config.lunar_executable, "Lunar IPS"),
            ("flips_executable", config.flips_executable, "Floating IPS"),
            ("flips_archive", config.flips_archive, "archive Floating IPS"),
        )
    }
    output = config.output.expanduser().resolve()
    protected = set(values.values())
    if output in protected:
        raise ProofError("la preuve de sortie ne peut écraser aucun fichier d'entrée")
    temp_parent = config.temp_parent.expanduser().resolve()
    temp_parent.mkdir(parents=True, exist_ok=True)
    if not temp_parent.is_dir():
        raise ProofError(f"parent temporaire non valide : {temp_parent}")
    return ProofConfig(
        root=root,
        output=output,
        temp_parent=temp_parent,
        verified_utc=canonical_verified_utc(config.verified_utc),
        timeout_seconds=config.timeout_seconds,
        **values,
    )


def generate_proof(
    config: ProofConfig,
    *,
    pins: ToolPins = OFFICIAL_TOOL_PINS,
    runner: CommandRunner = default_command_runner,
    path_converter: PathConverter = windows_path,
) -> dict[str, object]:
    """Run the three official patch applications and return a PASS report."""

    config = _validated_config(config)
    originals = _input_paths(config)
    before = {label: snapshot(path) for label, path in originals.items()}

    lunar_hash = before["Lunar IPS"].sha256
    flips_hash = before["Floating IPS"].sha256
    archive_hash = before["archive Floating IPS"].sha256
    expected_tools = (
        ("Lunar IPS 1.03 x64", lunar_hash, pins.lunar_executable_sha256),
        ("Floating IPS v198", flips_hash, pins.flips_executable_sha256),
        ("archive Floating IPS v198", archive_hash, pins.flips_archive_sha256),
    )
    for label, actual, expected in expected_tools:
        if actual != expected:
            raise ProofError(
                f"{label} non officiel ou altéré : {actual} (attendu {expected})"
            )

    archive_members = _archive_members_matching_hash(config.flips_archive, flips_hash)
    if not archive_members:
        raise ProofError(
            "l'exécutable Floating IPS fourni n'existe pas octet pour octet "
            "dans l'archive officielle fournie"
        )

    target_hash = before["target ROM"].sha256
    roundtrips: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(
        prefix=".external-patcher-proof-", dir=config.temp_parent
    ) as temporary:
        work = Path(temporary)

        ips_patch_copy = work / "input.ips"
        ips_output = work / "ips-output.nes"
        _copy_regular(config.ips_patch, ips_patch_copy)
        _copy_regular(config.ips_base, ips_output)
        lunar_command = [
            str(config.lunar_executable),
            "-ApplyIPS",
            path_converter(ips_patch_copy),
            path_converter(ips_output),
        ]
        lunar_completed = _run_checked(
            runner,
            lunar_command,
            work,
            config.timeout_seconds,
            "Lunar IPS",
        )
        if not ips_output.is_file():
            raise ProofError("Lunar IPS n'a pas produit de ROM")
        roundtrips.append(
            _roundtrip_record(
                format_name="IPS",
                tool="lunar_ips",
                base=config.ips_base,
                patch=config.ips_patch,
                output=ips_output,
                target=config.target_rom,
                root=config.root,
                command=_normal_command(
                    config.lunar_executable, "-ApplyIPS", ips_patch_copy, ips_output
                ),
                returncode=lunar_completed.returncode,
            )
        )

        for slug, base, patch in (
            ("chinese", config.chinese_base, config.chinese_bps),
            ("english", config.english_base, config.english_bps),
        ):
            base_copy = work / f"{slug}-base.nes"
            patch_copy = work / f"{slug}.bps"
            output = work / f"{slug}-output.nes"
            _copy_regular(base, base_copy)
            _copy_regular(patch, patch_copy)
            flips_command = [
                str(config.flips_executable),
                "--apply",
                path_converter(patch_copy),
                path_converter(base_copy),
                path_converter(output),
            ]
            completed = _run_checked(
                runner,
                flips_command,
                work,
                config.timeout_seconds,
                f"Floating IPS ({slug})",
            )
            if not output.is_file():
                raise ProofError(f"Floating IPS ({slug}) n'a pas produit de ROM")
            roundtrips.append(
                _roundtrip_record(
                    format_name="BPS",
                    tool="floating_ips",
                    base=base,
                    patch=patch,
                    output=output,
                    target=config.target_rom,
                    root=config.root,
                    command=_normal_command(
                        config.flips_executable,
                        "--apply",
                        patch_copy,
                        base_copy,
                        output,
                    ),
                    returncode=completed.returncode,
                )
            )

    after = {label: snapshot(path) for label, path in originals.items()}
    changed = [label for label in originals if after[label] != before[label]]
    if changed:
        raise ProofError(
            "fichier(s) source modifié(s) pendant la vérification : "
            + ", ".join(changed)
        )

    generator_path = Path(__file__).resolve()
    return {
        "schema": SCHEMA,
        "result": "PASS",
        "verified_utc": config.verified_utc,
        "generator": {
            "path": display_path(generator_path, config.root),
            "sha256": sha256_file(generator_path),
        },
        "target": {
            "path": display_path(config.target_rom, config.root),
            "size": before["target ROM"].size,
            "sha256": target_hash,
        },
        "tools": {
            "lunar_ips": {
                "version": LUNAR_VERSION,
                "path": display_path(config.lunar_executable, config.root),
                "size": before["Lunar IPS"].size,
                "sha256": lunar_hash,
            },
            "floating_ips": {
                "version": FLIPS_VERSION,
                "source": FLIPS_SOURCE,
                "path": display_path(config.flips_executable, config.root),
                "size": before["Floating IPS"].size,
                "archive_path": display_path(config.flips_archive, config.root),
                "archive_size": before["archive Floating IPS"].size,
                "archive_sha256": archive_hash,
                "executable_sha256": flips_hash,
                "executable_archive_members": archive_members,
            },
        },
        "roundtrips": roundtrips,
    }


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def generate_and_write(
    config: ProofConfig,
    *,
    pins: ToolPins = OFFICIAL_TOOL_PINS,
    runner: CommandRunner = default_command_runner,
    path_converter: PathConverter = windows_path,
) -> dict[str, object]:
    proof = generate_proof(
        config, pins=pins, runner=runner, path_converter=path_converter
    )
    atomic_write_json(config.output.expanduser().resolve(), proof)
    return proof


def _root_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--target-rom", default="Pokemon_Jaune_FR_repacked_title.nes"
    )
    parser.add_argument("--ips-base", default="yellow.nes")
    parser.add_argument(
        "--ips-patch", default="Pokemon_Jaune_FR_repacked_title.ips"
    )
    parser.add_argument(
        "--chinese-base",
        default="Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes",
    )
    parser.add_argument(
        "--chinese-bps",
        default="Pokemon_Jaune_FR_repacked_title_from_chinese.bps",
    )
    parser.add_argument(
        "--english-base", default="Pokemon Yellow English 9-23-2015.nes"
    )
    parser.add_argument(
        "--english-bps",
        default="Pokemon_Jaune_FR_repacked_title_from_english.bps",
    )
    parser.add_argument(
        "--lunar-ips-exe",
        required=True,
        help="chemin WSL/Windows vers Lunar IPS 1.03 x64",
    )
    parser.add_argument(
        "--floating-ips-exe",
        required=True,
        help="chemin WSL/Windows vers flips.exe v198",
    )
    parser.add_argument(
        "--floating-ips-archive",
        required=True,
        help="archive ZIP officielle contenant exactement flips.exe v198",
    )
    parser.add_argument("--output", default="build/external-patcher-proof.json")
    parser.add_argument(
        "--temp-parent",
        help="parent du répertoire temporaire (défaut : dossier de sortie)",
    )
    parser.add_argument(
        "--verified-utc",
        help="horodatage reproductible YYYY-MM-DDTHH:MM:SSZ (défaut : maintenant)",
    )
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser


def config_from_args(args: argparse.Namespace) -> ProofConfig:
    root = args.root.expanduser().resolve()
    output = _root_path(root, args.output)
    temp_parent = (
        _root_path(root, args.temp_parent) if args.temp_parent else output.parent
    )
    return ProofConfig(
        root=root,
        target_rom=_root_path(root, args.target_rom),
        ips_base=_root_path(root, args.ips_base),
        ips_patch=_root_path(root, args.ips_patch),
        chinese_base=_root_path(root, args.chinese_base),
        chinese_bps=_root_path(root, args.chinese_bps),
        english_base=_root_path(root, args.english_base),
        english_bps=_root_path(root, args.english_bps),
        lunar_executable=_root_path(root, args.lunar_ips_exe),
        flips_executable=_root_path(root, args.floating_ips_exe),
        flips_archive=_root_path(root, args.floating_ips_archive),
        output=output,
        temp_parent=temp_parent,
        verified_utc=canonical_verified_utc(args.verified_utc),
        timeout_seconds=args.timeout_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = config_from_args(args)
        proof = generate_and_write(config)
    except (ProofError, OSError, zipfile.BadZipFile) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    print(
        "PASS : 3/3 sorties IPS/BPS sont identiques octet pour octet à "
        f"{proof['target']['sha256']}"
    )
    print(config.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
