"""ROM-free tests and local builds; exact release requires NJ046_VERIFY_RELEASE=1."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import build_english_release as builder


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class PitchTests(unittest.TestCase):
    def test_exact_guarded_delta(self):
        self.assertEqual(len(builder.PITCH_BEFORE), 80)
        self.assertEqual(len(builder.PITCH_AFTER), 80)
        original = bytes(builder.PITCH_START) + builder.PITCH_BEFORE + b"tail"
        result = builder.apply_pitch(original)
        self.assertEqual(len(result), len(original))
        self.assertEqual(sum(a != b for a, b in zip(original, result)), 69)
        self.assertEqual(result[:builder.PITCH_START], original[:builder.PITCH_START])
        self.assertEqual(result[builder.PITCH_START + 80:], b"tail")
        self.assertEqual(result[builder.PITCH_START:builder.PITCH_START + 80], builder.PITCH_AFTER)
        with self.assertRaises(builder.BuildError):
            builder.apply_pitch(result)

    def test_wrong_and_short_inputs(self):
        for candidate in (b"", bytes(builder.PITCH_START + 80)):
            with self.assertRaises(builder.BuildError):
                builder.apply_pitch(candidate)


class SourceTests(unittest.TestCase):
    def test_source_hash_and_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.nes"
            path.write_bytes(b"test")
            with patch.object(builder, "ROM_SIZE", 4), patch.dict(
                builder.EXPECTED_ROM_SHA256, {"yellow": builder.sha256(b"test")}
            ):
                self.assertEqual(builder.read_source_rom(path, "yellow"), b"test")
                path.write_bytes(b"fail")
                with self.assertRaises(builder.BuildError):
                    builder.read_source_rom(path, "yellow")
                path.write_bytes(b"short")
                with self.assertRaises(builder.BuildError):
                    builder.read_source_rom(path, "yellow")

    def test_release_pin_is_explicit(self):
        self.assertFalse(builder.build_parser().parse_args(["build"]).verify_release)
        self.assertTrue(builder.build_parser().parse_args(["build", "--verify-release"]).verify_release)
        with self.assertRaises(builder.BuildError):
            builder.verify_release(b"edited rom", b"edited ips")

    def test_check_uses_only_default_static_inputs(self):
        with patch.object(builder.catalog, "validate_all", return_value={"result": "PASS"}) as validate:
            with patch.object(builder, "read_source_rom", side_effect=AssertionError("ROM read")):
                report = builder.check()
                self.assertEqual(report["result"], "PASS")
                self.assertEqual(report["move_labels"]["records"], 114)
        validate.assert_called_once_with(*[builder.DATA_INPUTS[key] for key in
                                          ("catalogue", "adjudications", "variants", "overlaps", "cameos")])

    def test_real_rom_free_check(self):
        self.assertEqual(builder.check()["result"], "PASS")

    def test_explicit_core_inputs_and_outputs(self):
        args = builder.core_command(Path("english.nes"), Path("output"))
        self.assertEqual(args[args.index("--profile") + 1], "en-US")
        self.assertEqual(args[args.index("--move-labels-csv") + 1], str(builder.DATA_INPUTS["move_labels"]))
        self.assertEqual(args[args.index("--csv") + 1], str(builder.DATA_INPUTS["catalogue"]))
        self.assertIn("--bank-budget-output", args)

    def test_input_records_detect_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.csv"
            path.write_bytes(b"before")
            first = builder.input_records([path])
            self.assertEqual(first, builder.input_records([path, path]))
            path.write_bytes(b"after")
            self.assertNotEqual(first, builder.input_records([path]))

    def test_provenance_is_explicit_and_ignores_ambient_imports(self):
        paths = builder.source_paths()
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(all(path.is_file() for path in paths))
        expected = builder.input_records(paths)
        unrelated = SimpleNamespace(__file__=str(builder.ROOT / "tools" / "deleted_unrelated.py"))
        with patch.dict(sys.modules, {"tools.unrelated_module": unrelated}):
            self.assertEqual(builder.source_paths(), paths)
            self.assertEqual(builder.input_records(builder.source_paths()), expected)


class MoveLabelChecks(unittest.TestCase):
    def test_current_indices_and_edited_wording_are_valid(self):
        self.assertEqual(len(builder.EXPECTED_MOVE_INDICES), 114)
        rows = builder.read_rows(builder.DATA_INPUTS["move_labels"])
        rows[0]["line_1"] = "Edited"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "moves.csv"
            write_rows(path, rows)
            self.assertEqual(builder.check_move_labels(path)["records"], 114)

    def test_missing_file_is_not_silently_skipped_by_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(builder.DATA_INPUTS, {"move_labels": Path(temporary) / "missing.csv"}):
                with self.assertRaises(OSError):
                    builder.check()

    def test_invalid_labels_and_ownership_are_rejected(self):
        for problem in ("missing", "duplicate", "wrong_index", "long", "non_ascii"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as temporary:
                rows = builder.read_rows(builder.DATA_INPUTS["move_labels"])
                if problem == "missing":
                    rows.pop()
                elif problem == "duplicate":
                    rows[1]["move_index"] = rows[0]["move_index"]
                elif problem == "wrong_index":
                    rows[0]["move_index"] = "0"
                elif problem == "long":
                    rows[0]["line_1"] = "123456789"
                else:
                    rows[0]["line_1"] = "\u2603"
                path = Path(temporary) / "moves.csv"
                write_rows(path, rows)
                with self.assertRaises((ValueError, RuntimeError)):
                    builder.check_move_labels(path)


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.root_patch = patch.object(builder, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.git_patch = patch.object(builder, "run_git", side_effect=lambda *a:
                                      subprocess.CompletedProcess(a, 0, b"", b""))
        self.git_patch.start()
        self.addCleanup(self.git_patch.stop)

    def test_empty_destination_allowed_nonempty_preserved(self):
        out = self.root / "build" / "en"
        self.assertEqual(builder.safe_destination(out, []), out)
        out.mkdir(parents=True)
        self.assertEqual(builder.safe_destination(out, []), out)
        sentinel = out / "keep.txt"
        sentinel.write_text("keep")
        with self.assertRaises(builder.BuildError):
            builder.safe_destination(out, [])
        self.assertEqual(sentinel.read_text(), "keep")

    def test_source_overlap_root_escape_and_metadata_rejected(self):
        for out, inputs in ((self.root, []), (self.root.parent / "outside", []),
                            (self.root / ".git" / "out", []),
                            (self.root / "source", [self.root / "source" / "input.nes"])):
            with self.subTest(out=out), self.assertRaises(builder.BuildError):
                builder.safe_destination(out, inputs)

    def test_unignored_or_tracked_rejected(self):
        out = self.root / "releases" / "new"
        with patch.object(builder, "run_git", return_value=subprocess.CompletedProcess([], 1, b"", b"")):
            with self.assertRaises(builder.BuildError):
                builder.safe_destination(out, [])
        with patch.object(builder, "run_git", return_value=subprocess.CompletedProcess([], 0, b"tracked\0", b"")):
            with self.assertRaises(builder.BuildError):
                builder.safe_destination(out, [])
        with patch.object(builder, "run_git", side_effect=lambda *a:
                          subprocess.CompletedProcess(a, int(a[0] == "check-ignore"), b"", b"")):
            with self.assertRaisesRegex(builder.BuildError, "must be ignored"):
                builder.safe_destination(out, [])

    def test_staging_directory_must_be_ignored(self):
        replies = [subprocess.CompletedProcess([], code, b"", b"") for code in (0, 0, 1)]
        with patch.object(builder, "run_git", side_effect=replies):
            with self.assertRaisesRegex(builder.BuildError, "temporary build"):
                builder.safe_destination(self.root / "outputs", [])

    def test_existing_file_destination_is_preserved(self):
        target = self.root / "output"
        target.write_text("source")
        with self.assertRaises(builder.BuildError):
            builder.safe_destination(target, [])
        self.assertEqual(target.read_text(), "source")

    def test_link_rejected(self):
        link = self.root / "link"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("Creating symlinks is not permitted")
        with self.assertRaises(builder.BuildError):
            builder.safe_destination(link / "output", [])


@unittest.skipUnless(all(p.is_file() for p in builder.DEFAULT_ROMS.values()),
                     "Optional integration requires all three local source ROMs")
class LocalIntegrationTests(unittest.TestCase):
    def test_edited_catalog_changes_output_and_failed_build_does_not_publish(self):
        parent = builder.ROOT / "build"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="en-edited-test-", dir=parent) as temporary:
            work = Path(temporary)
            baseline_args = builder.build_parser().parse_args(["build", "--output-dir", str(work / "baseline")])
            baseline = builder.build(baseline_args)
            rows = builder.read_rows(builder.DATA_INPUTS["catalogue"])
            row = next(row for row in rows if row["stable_key"] == "MAIN:0x037BEF")
            choices = ("It's pitch-dark. I wish I had Flash!", "It's pitch-dark. I wish I knew Flash!")
            row["english_v2"] = next(text for text in choices if text != row["english_v2"])
            edited = work / "catalog.csv"
            write_rows(edited, rows)
            with patch.dict(builder.DATA_INPUTS, {"catalogue": edited}):
                args = builder.build_parser().parse_args(["build", "--output-dir", str(work / "edited")])
                report = builder.build(args)
                self.assertNotEqual(report["outputs"], baseline["outputs"])
                self.assertEqual(report["checks"]["pointers"]["pointer_records"], 1912)
                args.output_dir = work / "failed-core"
                with patch.object(builder, "build_core", side_effect=builder.BuildError("injected failure")):
                    with self.assertRaisesRegex(builder.BuildError, "injected failure"):
                        builder.build(args)
                self.assertFalse(args.output_dir.exists())
                self.assertEqual(list(work.glob(".en-build-*")), [])

    def test_normal_build_is_deterministic_and_preserves_inputs(self):
        parent = builder.ROOT / "build"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="en-builder-test-", dir=parent) as temporary:
            work = Path(temporary)
            before = builder.input_records(list(builder.DEFAULT_ROMS.values()))
            reports = []
            for number in (1, 2):
                output = work / str(number)
                argv = ["build", "--output-dir", str(output)]
                report = builder.build(builder.build_parser().parse_args(argv))
                reports.append(report)
                for name in (builder.ROM_FILENAME, builder.IPS_FILENAME):
                    self.assertEqual(report["outputs"][name]["sha256"], builder.sha256((output / name).read_bytes()))
                self.assertEqual(report["checks"]["pointers"]["pointer_records"], 1912)
                self.assertEqual(report["checks"]["move_labels"], 114)
                self.assertEqual(report["runtime_validation"], "NOT RUN")
                self.assertEqual(json.loads((output / builder.REPORT_FILENAME).read_text(encoding="utf-8")), report)
                with self.assertRaises(builder.BuildError):
                    builder.build(builder.build_parser().parse_args(argv))
            self.assertEqual(reports[0], reports[1])
            self.assertEqual(reports[0]["release_verification"], "NOT REQUESTED")
            self.assertEqual(reports[1]["release_verification"], "NOT REQUESTED")
            self.assertEqual(before, builder.input_records(list(builder.DEFAULT_ROMS.values())))


@unittest.skipUnless(os.environ.get("NJ046_VERIFY_RELEASE") == "1"
                     and all(p.is_file() for p in builder.DEFAULT_ROMS.values()),
                     "Exact release test requires NJ046_VERIFY_RELEASE=1 and all three source ROMs")
class ExactReleaseIntegrationTests(unittest.TestCase):
    def test_published_release_rom_and_ips(self):
        parent = builder.ROOT / "build"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="en-release-test-", dir=parent) as temporary:
            output = Path(temporary) / "release"
            args = builder.build_parser().parse_args(["build", "--verify-release", "--output-dir", str(output)])
            report = builder.build(args)
            self.assertEqual(report["outputs"][builder.ROM_FILENAME]["sha256"], builder.RELEASE_ROM_SHA256)
            self.assertEqual(report["outputs"][builder.IPS_FILENAME]["sha256"], builder.RELEASE_IPS_SHA256)
            self.assertEqual(report["release_verification"], "PASS")
            published = builder.ROOT / "releases" / "en" / "2.0.2" / "Pokemon_Yellow_NJ046_EN_v2.0.2.ips"
            self.assertEqual((output / builder.IPS_FILENAME).read_bytes(), published.read_bytes())


if __name__ == "__main__":
    unittest.main()
