#!/usr/bin/env python3
"""Synthetic tests for the controller-only runtime text-read gate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_english_runtime_text_reads import (
    CASES,
    CRITICAL_RIVAL_BATTLE_KEYS,
    EXPECTED_REGIONS,
    RuntimeTextReadError,
    validate_runtime_text_reads,
)


ROM_HASH = "ab" * 32


def write_range_file(path: Path, offsets: list[int]) -> None:
    lines = [
        "PRG offsets exclude the 16-byte iNES header.",
        "start_hex\tend_inclusive_hex\tbyte_count",
    ]
    lines.extend(f"{offset:06X}\t{offset:06X}\t1" for offset in offsets)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_fixtures(root: Path) -> tuple[Path, Path]:
    records: list[dict[str, object]] = []
    for index, key in enumerate(CRITICAL_RIVAL_BATTLE_KEYS):
        records.append(
            {
                "stable_key": key,
                "final_target": f"0x{0x030010 + index * 2:06X}",
                "payload_length": 1,
            }
        )
    for index, (_group, key, harness) in enumerate(CASES):
        records.append(
            {
                "kind": "restoration",
                "reference": f"0x{harness:06X}",
                "stable_key": key,
                "final_target": f"0x{0x031010 + index * 2:06X}",
                "payload_length": 1,
            }
        )
    while len(records) < 1912:
        index = len(records)
        records.append(
            {
                "kind": "ordinary",
                "stable_key": f"MAIN:fixture-{index:04d}",
                "final_target": f"0x{0x032010 + index * 2:06X}",
                "payload_length": 1,
            }
        )
    pointer_manifest = root / "pointer_manifest.json"
    pointer_manifest.write_text(
        json.dumps(
            {
                "result": "PASS",
                "inputs": {"rom": {"sha256": ROM_HASH}},
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    evidence = root / "mesen"
    critical_offsets = [0x030000 + index * 2 for index in range(8)]
    for region in EXPECTED_REGIONS:
        scenario = evidence / region.casefold() / "08-campaign-start"
        scenario.mkdir(parents=True)
        write_range_file(
            scenario / "campaign_english_prg_reads_all.tsv",
            critical_offsets,
        )
        write_range_file(
            scenario / "campaign_english_prg_reads_battle.tsv",
            critical_offsets,
        )
        (scenario / "campaign_english_text_trace_summary.txt").write_text(
            "mode=controller_only_read_trace\n"
            "writes_to_game=0\n"
            "campaign_status=completed\n"
            "campaign_endpoint=outside_lab_stable\n"
            "battle_seen=true\n",
            encoding="utf-8",
        )
        (scenario / "mesen_run_manifest.txt").write_text(
            f"ROM SHA-256 before: {ROM_HASH}\n"
            f"ROM SHA-256 after: {ROM_HASH}\n"
            f"Region: {region}\n"
            "Expected marker: POKEMON_CAMPAIGN_ENGLISH_TRACE_PASS\n"
            "Expected marker observed: True\n"
            "Strict hardware profile: True\n"
            "Full NES debug-stop profile: True\n"
            "Result: PASS\n",
            encoding="utf-8",
        )
        records_by_key = {record["stable_key"]: record for record in records}
        for group in ("pair6", "pair7"):
            assisted = evidence / region.casefold() / f"critical-{group}"
            assisted.mkdir(parents=True)
            marker = f"POKEMON_CRITICAL_RESTORATIONS_{group.upper()}_PASS"
            (assisted / "mesen_run_manifest.txt").write_text(
                f"ROM SHA-256 before: {ROM_HASH}\n"
                f"ROM SHA-256 after: {ROM_HASH}\n"
                f"Region: {region}\n"
                f"Expected marker: {marker}\n"
                "Expected marker observed: True\n"
                "Strict hardware profile: True\n"
                "Full NES debug-stop profile: True\n"
                "Result: PASS\n",
                encoding="utf-8",
            )
            group_cases = [case for case in CASES if case[0] == group]
            report_lines = [
                "schema=nj046-en2-critical-restoration-runtime-result/v1",
                f"group={group}",
                f"candidate_sha256={ROM_HASH}",
                "mode=assisted_transient_prg_pointer_patch",
                "writes_to_game_ram=0",
                f"payload_count={len(group_cases)}",
                f"patch_writes={len(group_cases) * 2}",
                f"restore_writes={len(group_cases) * 2}",
                "restored=true",
            ]
            for _case_group, key, harness in group_cases:
                record = records_by_key[key]
                report_lines.append(
                    f"payload={key} harness=0x{harness:06X} "
                    f"target={record['final_target']} length=1 "
                    "unique_reads=2/2 events=2"
                )
            report_lines.append("result=PASS")
            (assisted / f"critical_restorations_{group}_validation.txt").write_text(
                "\n".join(report_lines) + "\n",
                encoding="utf-8",
            )
    return pointer_manifest, evidence


class RuntimeTextReadTests(unittest.TestCase):
    def test_three_regions_cover_every_critical_final_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest, evidence = write_fixtures(Path(temporary))
            report = validate_runtime_text_reads(manifest, evidence)
            self.assertEqual(report["result"], "PASS")
            self.assertEqual(set(report["regions"]), set(EXPECTED_REGIONS))
            for region in EXPECTED_REGIONS:
                self.assertEqual(
                    report["regions"][region]["battle_fully_read_payloads"],
                    8,
                )

    def test_one_missing_battle_byte_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest, evidence = write_fixtures(Path(temporary))
            trace = (
                evidence
                / "dendy"
                / "08-campaign-start"
                / "campaign_english_prg_reads_battle.tsv"
            )
            lines = trace.read_text(encoding="utf-8").splitlines()
            trace.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeTextReadError, "critical battle payloads"
            ):
                validate_runtime_text_reads(manifest, evidence)


if __name__ == "__main__":
    unittest.main()
