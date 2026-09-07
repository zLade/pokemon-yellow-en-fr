#!/usr/bin/env python3
"""Regression tests for the exhaustive dialogue review export."""

from __future__ import annotations

import unittest

from tools.export_dialogue_review_table import (
    DEFAULT_ALIGNMENT,
    DEFAULT_ANIME_MOTTO_MAIN_MAP,
    DEFAULT_FIDELITY_MAP,
    DEFAULT_NATURALIZATION_MAP,
    DEFAULT_OFFICIAL_GEN1_SHARED_MAP,
    DEFAULT_OFFICIAL_YELLOW_MAP,
    DEFAULT_REMOVED_SOURCE,
    DEFAULT_SOURCE_INVENTORY,
    ROM_DIR,
    build_rows,
)


class ExportDialogueReviewTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = build_rows(
            script_path=ROM_DIR / "script.py",
            alignment_path=DEFAULT_ALIGNMENT,
            source_inventory_path=DEFAULT_SOURCE_INVENTORY,
            removed_source_path=DEFAULT_REMOVED_SOURCE,
            fidelity_map_path=DEFAULT_FIDELITY_MAP,
            naturalization_map_path=DEFAULT_NATURALIZATION_MAP,
            official_yellow_map_path=DEFAULT_OFFICIAL_YELLOW_MAP,
            official_gen1_shared_map_path=(
                DEFAULT_OFFICIAL_GEN1_SHARED_MAP
            ),
            anime_motto_main_map_path=DEFAULT_ANIME_MOTTO_MAIN_MAP,
        )

    def test_verified_live_source_replaces_dummy_pointer_alignment(self) -> None:
        row = next(
            item for item in self.rows if item.offset_or_pointer == "0x03F033"
        )
        self.assertEqual(row.public_id, "D0964")
        self.assertEqual(row.chinese_text, "你真是个难缠的人......")
        self.assertEqual(row.french_text, "Tu es vraiment coriace...")

    def test_live_pointer_sources_replace_containing_offset_matches(self) -> None:
        rows = {row.offset_or_pointer: row for row in self.rows}
        expected = {
            "0x03BEE1": "小次郎:真是不要脸",
            "0x03C33F": "小次郎:你给我记住",
            "0x03D9DD": "得到沙瓦郎",
            "0x03DCAA": "娜梅:你还有什么事嘛!讨厌!",
        }
        for offset, chinese_text in expected.items():
            with self.subTest(offset=offset):
                self.assertEqual(rows[offset].chinese_text, chinese_text)
                self.assertEqual(rows[offset].alignment_confidence, "high")

    def test_reviewed_special_blocks_have_direct_chinese_sources(self) -> None:
        rows = {row.public_id: row for row in self.rows}
        expected = {
            "D0066": "得到无",
            "D0102": "欢迎!",
            "D0249": "精灵取出精灵存放",
            "D0274": (
                "你好!欢迎你光临宠物精灵的世界!大家都叫我大木博士,"
                "在这世界住着被称为宠物精灵的生物!这生物被视为宠物,"
                "或使用于对战等等.而我是研究这宠物精灵的!小智,一个将"
                "属于你的故事,梦想即将开始!"
            ),
            "D0771": "捉鸟人:那里有很多珍贵的精灵...",
        }
        for public_id, chinese_text in expected.items():
            with self.subTest(public_id=public_id):
                self.assertEqual(rows[public_id].chinese_text, chinese_text)
                self.assertEqual(
                    rows[public_id].alignment_confidence,
                    "high",
                )

    def test_gary_cut_dialogue_uses_its_reviewed_live_pointer(self) -> None:
        row = next(item for item in self.rows if item.public_id == "D0502")
        self.assertEqual(row.stable_key, "MAIN:0x03A9D1")
        self.assertEqual(
            row.chinese_text,
            "小茂:听说居合斩的名人也在船上,看了一下竟然是会晕船的老头!"
            "你也去看看吧,再会了!",
        )
        self.assertEqual(row.alignment_confidence, "high")

    def test_collapsed_main_sources_select_the_remaining_live_pointer(self) -> None:
        rows = {row.offset_or_pointer: row for row in self.rows}
        expected = {
            "0x03499D": "得到睡醒药",
            "0x039D74": "得到小火龙",
            "0x039DA8": "铁达尼号上可是有很多厉害的训练师哦!",
            "0x039DE5": "大叔:想过去,先打败我",
        }
        for offset, chinese_text in expected.items():
            with self.subTest(offset=offset):
                self.assertEqual(rows[offset].chinese_text, chinese_text)
                self.assertNotIn("---", rows[offset].chinese_text)

    def test_anti_para_restoration_keeps_existing_public_ids_stable(self) -> None:
        row = next(
            item for item in self.rows
            if item.stable_key == "RESTORED:0x0348F1"
        )
        self.assertEqual(row.public_id, "D1055")
        self.assertEqual(row.french_text, "Anti-Para reçu !")
        self.assertEqual(row.chinese_text, "得到解麻药")
        self.assertEqual(
            row.english_intermediate,
            "SHARED TEXT — displayed text: A S.Heal!",
        )
        unchanged = next(
            item for item in self.rows
            if item.stable_key == "RESTORED:0x038353"
        )
        self.assertEqual(unchanged.public_id, "D1007")

    def test_external_french_source_provenances_are_visible(self) -> None:
        rows = {row.stable_key: row for row in self.rows}
        self.assertEqual(
            rows["MAIN:0x039660"].translation_history,
            "adapted from French Pokemon Yellow",
        )
        self.assertEqual(
            rows["MAIN:0x0396C5"].translation_history,
            "adapted from the French anime motto",
        )
        self.assertEqual(
            rows["MAIN:0x035206"].translation_history,
            "adapted from official French R/B/Y dialogue",
        )
        self.assertEqual(
            rows["RESTORED:0x03AFB0"].translation_history,
            "restored from the Chinese source + adapted from "
            "French Pokemon Yellow",
        )
        self.assertEqual(
            rows["RESTORED:0x03AF96"].translation_history,
            "restored from the Chinese source + adapted from "
            "the French anime motto",
        )

    def test_colons_inside_sentences_are_not_mistaken_for_speakers(self) -> None:
        rows = {row.public_id: row for row in self.rows}
        for public_id in {"D0256", "D0367", "D0450", "D0528", "D0932"}:
            with self.subTest(public_id=public_id):
                self.assertEqual(rows[public_id].speaker, "")
        self.assertEqual(rows["D0301"].speaker, "GARY'S SISTER")


if __name__ == "__main__":
    unittest.main()
