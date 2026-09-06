#!/usr/bin/env python3
"""Mutation tests for the cross-deliverable final completion gate."""

from __future__ import annotations

from contextlib import ExitStack
import csv
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.verify_final_completion import (
    CHR_DIR,
    CORE_MANIFEST,
    EXTERNAL_PATCHER_PROOF,
    ROUTE1_DIR,
    UNINITIALIZED_DIAGNOSTIC,
    _read_dialogues,
    build_report,
    validate_cameos,
    validate_chr,
    validate_dialogues,
    validate_documentation,
    validate_external_patchers,
    validate_runtime,
    validate_battery_corruption,
    validate_uninitialized_read,
)


ROOT = Path(__file__).resolve().parents[1]


def copy_file(relative: str | Path, target_root: Path) -> Path:
    relative_path = Path(relative)
    target = target_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative_path, target)
    return target


class FinalCompletionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _header, cls.dialogues = _read_dialogues(
            ROOT / "LISTE_EXHAUSTIVE_DIALOGUES.csv"
        )

    def test_report_checks_all_local_deliverables(self) -> None:
        names = (
            "validate_release", "validate_external_patchers", "validate_dialogues",
            "validate_cameos", "validate_fidelity_derivatives", "validate_pointer_manifest",
            "validate_xlsx", "validate_runtime", "validate_uninitialized_read",
            "validate_battery_corruption", "validate_chr", "validate_documentation",
        )
        with ExitStack() as stack:
            checks = []
            for name in names:
                result = {"name": name, "result": "PASS", "errors": []}
                value = (result, []) if name == "validate_dialogues" else result
                checks.append(stack.enter_context(patch(
                    "tools.verify_final_completion." + name, return_value=value
                )))
            report = build_report(ROOT)
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["summary"]["checks_total"], len(names))
        self.assertEqual(report["summary"]["checks_passed"], len(names))
        for check in checks:
            check.assert_called_once()

    @unittest.skipIf(
        os.environ.get("POKEMON_RELEASE_ACTIVE") == "1"
        or os.environ.get("POKEMON_MESEN_BOOTSTRAP") == "1",
        (
            "le gate post-publication ne peut pas valider la release ou "
            "la preuve Mesen en cours de construction"
        ),
    )
    def test_real_final_evidence_passes_all_local_checks(self) -> None:
        if os.environ.get("POKEMON_VERIFY_FR_200_ARCHIVE") != "1":
            self.skipTest(
                "preuve historique FR 2.0.0; utiliser "
                "tools/validate_french_release.py pour FR 2.0.1"
            )
        report = build_report(ROOT)
        self.assertEqual(
            report["result"],
            "PASS",
            {check["name"]: check["errors"] for check in report["checks"]},
        )
        self.assertEqual(report["summary"]["checks_passed"], 12)
        self.assertEqual(report["summary"]["physical_mapper163"], "NON_TESTE")
        release_check = next(
            check for check in report["checks"]
            if check["name"] == "deterministic_release"
        )
        self.assertGreaterEqual(release_check["evidence"]["inputs_checked"], 200)

    def test_missing_chinese_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target_root = Path(directory)
            target = copy_file("LISTE_EXHAUSTIVE_DIALOGUES.csv", target_root)
            with target.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                header = list(reader.fieldnames or [])
                rows = list(reader)
            rows[0]["texte_chinois_source"] = ""
            with target.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)
            check, _rows = validate_dialogues(target_root)
        self.assertEqual(check["result"], "FAIL")
        self.assertTrue(
            any("texte_chinois_source" in error for error in check["errors"])
        )

    def test_beibei_inventory_mutation_is_rejected(self) -> None:
        relative = Path(
            "build/chinese-english-fidelity/extraction/creator_cameo_dialogues.csv"
        )
        with tempfile.TemporaryDirectory() as directory:
            target_root = Path(directory)
            target = copy_file(relative, target_root)
            text = target.read_text(encoding="utf-8-sig")
            target.write_text(
                text.replace(",Beibei,Compliment,", ",Kameiyu,Compliment,", 1),
                encoding="utf-8",
            )
            check = validate_cameos(target_root, self.dialogues)
        self.assertEqual(check["result"], "FAIL")
        self.assertTrue(any("Beibei" in error or "distribution" in error for error in check["errors"]))

    def test_mutated_external_bps_proof_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target_root = Path(directory)
            copy_file(EXTERNAL_PATCHER_PROOF, target_root)
            for relative in (
                "Pokemon_Jaune_FR_repacked_title.nes",
                "yellow.nes",
                "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes",
                "Pokemon Yellow English 9-23-2015.nes",
                "Pokemon_Jaune_FR_repacked_title.ips",
                "Pokemon_Jaune_FR_repacked_title_from_chinese.bps",
                "Pokemon_Jaune_FR_repacked_title_from_english.bps",
            ):
                copy_file(relative, target_root)
            path = target_root / EXTERNAL_PATCHER_PROOF
            proof = json.loads(path.read_text(encoding="utf-8"))
            proof["roundtrips"][1]["output_sha256"] = "0" * 64
            path.write_text(json.dumps(proof), encoding="utf-8")
            check = validate_external_patchers(target_root)
        self.assertEqual(check["result"], "FAIL")
        self.assertTrue(any("output hash" in error for error in check["errors"]))

    def _runtime_root(self, target_root: Path) -> None:
        copy_file(CORE_MANIFEST, target_root)
        core_parent = CORE_MANIFEST.parent
        copy_file(
            core_parent
            / "static"
            / "04a-full-python-test-suite.log.stderr.txt",
            target_root,
        )
        for slug in ("dendy", "ntsc", "pal"):
            copy_file(
                core_parent
                / "mesen"
                / slug
                / "07-campaign-prototype/mesen_run_manifest.txt",
                target_root,
            )
            copy_file(ROUTE1_DIR / slug / "mesen_run_manifest.txt", target_root)
        copy_file(ROUTE1_DIR / "route1_matrix.json", target_root)

    def test_failed_core_runtime_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target_root = Path(directory)
            self._runtime_root(target_root)
            path = target_root / CORE_MANIFEST
            original = path.read_text(encoding="utf-8-sig")
            path.write_text(
                original.replace("Result: PASS", "Result: FAIL", 1),
                encoding="utf-8",
            )
            check = validate_runtime(target_root)
            self.assertEqual(check["result"], "FAIL")
            self.assertIn("core Mesen suite is not PASS", check["errors"])

            path.write_text(
                original.replace(
                    "Bootstrap completion gate: False",
                    "Bootstrap completion gate: True",
                    1,
                ),
                encoding="utf-8",
            )
            check = validate_runtime(target_root)
            self.assertEqual(check["result"], "FAIL")
            self.assertIn(
                "core Mesen manifest is still a bootstrap run",
                check["errors"],
            )

            path.write_text(original, encoding="utf-8")
            log_path = (
                target_root
                / CORE_MANIFEST.parent
                / "static"
                / "04a-full-python-test-suite.log.stderr.txt"
            )
            python_log = log_path.read_text(encoding="utf-8-sig")
            log_path.write_text(
                python_log.replace("\nOK\n", "\nOK (skipped=1)\n", 1),
                encoding="utf-8",
            )
            check = validate_runtime(target_root)
            self.assertEqual(check["result"], "FAIL")
            self.assertTrue(
                any("unskipped terminal OK" in error for error in check["errors"])
            )

    def test_real_uninitialized_read_diagnostic_is_qualified_and_current(self) -> None:
        if os.environ.get("POKEMON_VERIFY_FR_200_ARCHIVE") != "1":
            self.skipTest("diagnostic historique lié à la ROM FR 2.0.0")
        check = validate_uninitialized_read(ROOT)
        self.assertEqual(check["result"], "PASS", check["errors"])
        self.assertEqual(
            check["evidence"]["safety_conclusion"],
            "harmlessness_not_proven",
        )

    def test_uninitialized_read_harmlessness_overclaim_is_rejected(self) -> None:
        rebuilt = json.loads(
            (ROOT / UNINITIALIZED_DIAGNOSTIC).read_text(encoding="utf-8")
        )
        mutated = json.loads(json.dumps(rebuilt))
        mutated["claims"]["harmlessness_proven"] = True
        with tempfile.TemporaryDirectory() as directory:
            target_root = Path(directory)
            target = target_root / UNINITIALIZED_DIAGNOSTIC
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(mutated), encoding="utf-8")
            with patch(
                "tools.verify_final_completion.build_uninitialized_report",
                return_value=rebuilt,
            ):
                check = validate_uninitialized_read(target_root)
        self.assertEqual(check["result"], "FAIL")
        self.assertTrue(any("stale" in error for error in check["errors"]))

    def test_real_battery_corruption_matrix_is_current(self) -> None:
        check = validate_battery_corruption(ROOT)
        self.assertEqual(check["result"], "PASS", check["errors"])
        self.assertEqual(
            set(check["evidence"]["regions"]),
            {"Dendy", "Ntsc", "Pal"},
        )

    def test_chr_roundtrip_change_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target_root = Path(directory)
            for filename in ("verify.json", "roundtrip.json"):
                copy_file(CHR_DIR / filename, target_root)
            path = target_root / CHR_DIR / "roundtrip.json"
            report = json.loads(path.read_text(encoding="utf-8"))
            report["physical_changed_bytes"] = 1
            path.write_text(json.dumps(report), encoding="utf-8")
            check = validate_chr(target_root)
        self.assertEqual(check["result"], "FAIL")
        self.assertIn("roundtrip.json: physical changes are not zero", check["errors"])

    def test_stale_campaign_status_is_rejected(self) -> None:
        required = (
            "RAPPORT_RELEASE_2026-08-09.md",
            "MODE_EMPLOI_TRADUCTION.md",
            "CORRECTIONS_FIDELITE_CHINOISE.md",
            "DIALOGUES_CHINOIS_ABSENTS_ET_DIVERGENTS.md",
            "AUDIT_COHERENCE_GEN1_GEN2_FR.md",
            "CHECKLIST_TEST_MATERIEL_MAPPER163.md",
            "tools/campaign/STATUS_FR.md",
        )
        with tempfile.TemporaryDirectory() as directory:
            target_root = Path(directory)
            for relative in required:
                copy_file(relative, target_root)
            status = target_root / "tools/campaign/STATUS_FR.md"
            status.write_text(
                status.read_text(encoding="utf-8").replace(
                    "État courant — 9 août 2026", "État historique", 1
                ),
                encoding="utf-8",
            )
            check = validate_documentation(target_root)
        self.assertEqual(check["result"], "FAIL")
        self.assertTrue(any("campaign status" in error for error in check["errors"]))


if __name__ == "__main__":
    unittest.main()
