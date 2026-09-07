#!/usr/bin/env python3
"""Regression tests for the translated-text allocation and pointer plan."""

from __future__ import annotations

import sys
import json
import os
import random
import subprocess
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    BATTLE_MENU_CHR_START_LOW_EXPANDED,
    BATTLE_MENU_CHR_START_LOW_OFFSET,
    BATTLE_MENU_CHR_START_LOW_ORIGINAL,
    BATTLE_TEXT_CONTROL_CAVE_OFFSET,
    BATTLE_TEXT_CONTROL_CAVE_PATCH,
    BATTLE_TEXT_CONTROL_CAVE_SOURCE,
    BATTLE_TEXT_CONTROL_HOOK_OFFSET,
    BATTLE_TEXT_CONTROL_HOOK_PATCH,
    BATTLE_TEXT_CONTROL_HOOK_SOURCE,
    BATTLE_STATUS_UNCHANGED_SKIP_OFFSET,
    BATTLE_STATUS_UNCHANGED_SKIP_PATCH,
    BATTLE_STATUS_UNCHANGED_SKIP_SOURCE,
    BATTLE_TEXT_CLEAR_WIDTH_OFFSET,
    BATTLE_TEXT_CLEAR_WIDTH_PATCH,
    BATTLE_TEXT_CLEAR_WIDTH_SOURCE,
    FIXED_ANTIDOTE_LABEL_OFFSET,
    FIXED_ANTIDOTE_LABEL_PATCH,
    FIXED_ANTIDOTE_LABEL_SOURCE,
    FreeSpan,
    STRUCTURED_GLYPH_PAIR_COUNT,
    STRUCTURED_GLYPH_PAYLOAD_SIZE,
    STRUCTURED_GLYPH_RECORD_COUNT,
    STRUCTURED_GLYPH_RECORDS_SHA256,
    TRANSLATION_BASE_ROM,
    TranslationRow,
    VERIFIED_POINTER_REDIRECTS,
    allocate_suffix_pooled,
    allocate_best_fit,
    apply_verified_pointer_redirects,
    apply_verified_source_alignment_pointer_redirects,
    assign_pointer_targets_to_rows,
    expand_battle_menu_chr_slots,
    find_text_free_spans,
    has_source_record_terminator,
    move_graphic_reservation_payload,
    normalize_repacked_payload,
    patch_battle_text_line_break_control,
    patch_fixed_antidote_bag_label,
    remove_verified_non_dialogue_pointer_refs,
    sha256,
    verified_all_graphical_text_records,
    verified_dialogue_restoration_payloads,
    verified_field_graphical_text_records,
    verified_structured_glyph_records,
)
from tools.validate_repacked import build_parser, compute_plan  # noqa: E402


class TextFreeSpanTests(unittest.TestCase):
    def test_battle_text_control_uses_verified_hook_and_code_cave(self) -> None:
        size = BATTLE_TEXT_CONTROL_CAVE_OFFSET + len(
            BATTLE_TEXT_CONTROL_CAVE_SOURCE
        )
        source = bytearray(size)
        hook = BATTLE_TEXT_CONTROL_HOOK_OFFSET
        source[hook:hook + len(BATTLE_TEXT_CONTROL_HOOK_SOURCE)] = (
            BATTLE_TEXT_CONTROL_HOOK_SOURCE
        )
        status = BATTLE_STATUS_UNCHANGED_SKIP_OFFSET
        source[status:status + len(BATTLE_STATUS_UNCHANGED_SKIP_SOURCE)] = (
            BATTLE_STATUS_UNCHANGED_SKIP_SOURCE
        )
        clear = BATTLE_TEXT_CLEAR_WIDTH_OFFSET
        source[clear:clear + len(BATTLE_TEXT_CLEAR_WIDTH_SOURCE)] = (
            BATTLE_TEXT_CLEAR_WIDTH_SOURCE
        )
        candidate = bytearray(source)

        patch_battle_text_line_break_control(bytes(source), candidate)

        self.assertEqual(
            bytes(candidate[hook:hook + len(BATTLE_TEXT_CONTROL_HOOK_PATCH)]),
            BATTLE_TEXT_CONTROL_HOOK_PATCH,
        )
        cave = BATTLE_TEXT_CONTROL_CAVE_OFFSET
        self.assertEqual(
            bytes(candidate[cave:cave + len(BATTLE_TEXT_CONTROL_CAVE_PATCH)]),
            BATTLE_TEXT_CONTROL_CAVE_PATCH,
        )
        self.assertEqual(len(BATTLE_TEXT_CONTROL_CAVE_PATCH), 39)
        self.assertEqual(
            bytes(
                candidate[
                    status:status + len(BATTLE_STATUS_UNCHANGED_SKIP_PATCH)
                ]
            ),
            BATTLE_STATUS_UNCHANGED_SKIP_PATCH,
        )
        self.assertEqual(
            bytes(candidate[clear:clear + len(BATTLE_TEXT_CLEAR_WIDTH_PATCH)]),
            BATTLE_TEXT_CLEAR_WIDTH_PATCH,
        )

    def test_fixed_antidote_label_leaves_space_before_quantity(self) -> None:
        source = bytearray(
            FIXED_ANTIDOTE_LABEL_OFFSET + len(FIXED_ANTIDOTE_LABEL_SOURCE)
        )
        start = FIXED_ANTIDOTE_LABEL_OFFSET
        source[start:start + len(FIXED_ANTIDOTE_LABEL_SOURCE)] = (
            FIXED_ANTIDOTE_LABEL_SOURCE
        )
        candidate = bytearray(source)

        patch_fixed_antidote_bag_label(bytes(source), candidate)

        self.assertEqual(
            bytes(candidate[start:start + len(FIXED_ANTIDOTE_LABEL_PATCH)]),
            FIXED_ANTIDOTE_LABEL_PATCH,
        )
        self.assertEqual(FIXED_ANTIDOTE_LABEL_PATCH.split(b"\x0D")[0], b"Antid.")
        self.assertLessEqual(len(b"Antid."), 7)

    def test_move_graphic_reservations_cannot_be_suffix_pooled(self) -> None:
        markers = {
            (move_index, payload_size): move_graphic_reservation_payload(
                move_index,
                payload_size,
            )
            for move_index in range(177)
            for payload_size in (3, 5, 7, 9)
        }
        self.assertEqual(len(set(markers.values())), len(markers))
        for marker in markers.values():
            self.assertNotIn(0x0D, marker)
            self.assertFalse(any(0xB0 <= value <= 0xBF for value in marker))
            self.assertFalse(0x20 <= marker[-1] <= 0x7E)

        values = tuple(markers.values())
        for index, left in enumerate(values):
            for right in values[index + 1 :]:
                self.assertFalse(left.endswith(right))
                self.assertFalse(right.endswith(left))

    def test_move_graphic_reservation_owns_a_disjoint_root(self) -> None:
        marker = move_graphic_reservation_payload(97, 7)
        payloads = {
            0x20: marker,
            0x30: b"MOVE",
            0x40: b"Potion",
            0x50: b"tion",
        }
        spans = {0: [FreeSpan(0x100, 64)]}
        allocations, failures = allocate_suffix_pooled(spans, payloads)
        self.assertFalse(failures)

        marker_start = allocations[0x20]
        marker_end = marker_start + len(marker) + 1
        for source_offset in (0x30, 0x40, 0x50):
            start = allocations[source_offset]
            end = start + len(payloads[source_offset]) + 1
            self.assertFalse(marker_start < end and start < marker_end)

    def test_long_menu_expands_battle_menu_chr_window(self) -> None:
        source = bytearray(BATTLE_MENU_CHR_START_LOW_OFFSET + 1)
        source[BATTLE_MENU_CHR_START_LOW_OFFSET] = (
            BATTLE_MENU_CHR_START_LOW_ORIGINAL
        )
        candidate = bytearray(source)

        expanded = expand_battle_menu_chr_slots(
            bytes(source),
            candidate,
            (b"ATQ.", b"Objet", b"PKMN", b"Fuite"),
        )

        self.assertTrue(expanded)
        self.assertEqual(
            candidate[BATTLE_MENU_CHR_START_LOW_OFFSET],
            BATTLE_MENU_CHR_START_LOW_EXPANDED,
        )

    def test_sixteen_glyph_english_menu_keeps_stock_window(self) -> None:
        source = bytearray(BATTLE_MENU_CHR_START_LOW_OFFSET + 1)
        source[BATTLE_MENU_CHR_START_LOW_OFFSET] = (
            BATTLE_MENU_CHR_START_LOW_ORIGINAL
        )
        candidate = bytearray(source)

        expanded = expand_battle_menu_chr_slots(
            bytes(source),
            candidate,
            (b"Fight", b" Bag", b"PKMN", b"Run"),
        )

        self.assertFalse(expanded)
        self.assertEqual(candidate, source)

    def test_exact_submessage_row_owns_its_pointer(self) -> None:
        parent = TranslationRow(0x100, "parent", 40)
        child = TranslationRow(0x120, "child", 8)
        assigned = assign_pointer_targets_to_rows(
            [
                (parent, 40, b"parent"),
                (child, 8, b"child"),
            ],
            {
                0x100: [0x20],
                0x120: [0x22],
            },
        )

        self.assertEqual(assigned[0x100], [(0x100, [0x20])])
        self.assertEqual(assigned[0x120], [(0x120, [0x22])])

    def test_autonomous_submessages_own_their_exact_live_refs(self) -> None:
        rows = [
            (
                TranslationRow(0x034D08, "Route 1 parent", 67),
                67,
                b"Route 1 parent",
            ),
            (
                TranslationRow(0x034D3A, "Route 1 sign", 17),
                17,
                b"Route 1 sign",
            ),
            (
                TranslationRow(0x03ABAC, "Trainer parent", 47),
                47,
                b"Trainer parent",
            ),
            (
                TranslationRow(0x03ABCB, "Tu m'as eue !", 16),
                16,
                b"Tu m'as eue !",
            ),
        ]
        pointer_entries = {
            0x034D3A: [0x034AFF],
            0x03ABCB: [0x03AE82],
        }

        for row_info in (rows, list(reversed(rows))):
            with self.subTest(order=row_info[0][0].offset):
                assigned = assign_pointer_targets_to_rows(
                    row_info,
                    pointer_entries,
                )

                self.assertEqual(assigned[0x034D08], [])
                self.assertEqual(
                    assigned[0x034D3A],
                    [(0x034D3A, [0x034AFF])],
                )
                self.assertEqual(assigned[0x03ABAC], [])
                self.assertEqual(
                    assigned[0x03ABCB],
                    [(0x03ABCB, [0x03AE82])],
                )

    def test_short_or_unterminated_fill_runs_are_rejected(self) -> None:
        data = bytearray(b"NES\x1A" + b"\0" * 12 + b"\xFF" * 0x8000)
        data[0x40:0x40 + 64] = b"0" * 64
        data[0x100] = 0x0D
        data[0x101:0x101 + 31] = b"0" * 31
        data[0x180] = 0x0D
        data[0x181:0x181 + 32] = b"0" * 32

        spans = find_text_free_spans(
            bytes(data),
            [],
            min_len=4,
            arena_ranges=((0x101, 0x120), (0x181, 0x1A1)),
        )[0]

        self.assertEqual(spans, [FreeSpan(0x181, 32)])

    def test_protected_ranges_are_subtracted_before_use(self) -> None:
        data = bytearray(b"NES\x1A" + b"\0" * 12 + b"\xFF" * 0x8000)
        data[0x80] = 0x0D
        data[0x81:0x81 + 96] = b"0" * 96

        spans = find_text_free_spans(
            bytes(data),
            [(0xA1, 0xC1)],
            min_len=32,
            arena_ranges=((0x81, 0xE1),),
        )[0]

        self.assertEqual(
            spans,
            [FreeSpan(0x81, 32), FreeSpan(0xC1, 32)],
        )

    def test_reviewed_micro_arena_bypasses_only_the_generic_size_floor(
        self,
    ) -> None:
        data = bytearray(b"NES\x1A" + b"\0" * 12 + b"\xFF" * 0x8000)
        data[0x100] = 0x0D
        data[0x101:0x106] = b"0" * 5

        spans = find_text_free_spans(
            bytes(data),
            [],
            min_len=32,
            arena_ranges=(),
            micro_arena_ranges=((0x101, 0x106),),
        )[0]
        self.assertEqual(spans, [FreeSpan(0x101, 5)])

        data[0x103] = ord("X")
        with self.assertRaises(ValueError):
            find_text_free_spans(
                bytes(data),
                [],
                min_len=32,
                arena_ranges=(),
                micro_arena_ranges=((0x101, 0x106),),
            )

    def test_repacked_padding_normalization_preserves_leading_spaces(
        self,
    ) -> None:
        source = b"\xFF" * 16 + b"000Source"
        self.assertEqual(
            normalize_repacked_payload(
                source,
                16,
                9,
                b"000 Salut   ",
                (19,),
            ),
            b" Salut",
        )
        self.assertEqual(
            normalize_repacked_payload(
                source,
                16,
                9,
                b"000 Salut   ",
                (18,),
            ),
            b"000 Salut",
            "an interior target forbids shifting the translated prefix",
        )

    def test_repacked_padding_preserves_runtime_join_separator(self) -> None:
        cases = (
            (0x030230, b"Oh no!   ", b"Oh no! "),
            (0x030262, b" sent out   ", b" sent out "),
            (0x030417, b"Congrats!   ", b"Congrats! "),
        )
        for source_offset, translated, expected in cases:
            with self.subTest(source_offset=hex(source_offset)):
                source = b"\xFF" * source_offset + translated
                self.assertEqual(
                    normalize_repacked_payload(
                        source,
                        source_offset,
                        len(translated),
                        translated,
                        (source_offset,),
                        preserve_runtime_separator=True,
                    ),
                    expected,
                )

    def test_suffix_pool_shares_only_terminated_suffixes(self) -> None:
        payloads = {
            0x20: b"Hyper Potion",
            0x30: b"Potion",
            0x40: b"Potion",
            0x50: b"Vol",
        }
        spans = {0: [FreeSpan(0x100, 64)]}
        allocations, failures = allocate_suffix_pooled(spans, payloads)

        self.assertFalse(failures)
        self.assertEqual(allocations[0x30], allocations[0x40])
        self.assertEqual(
            allocations[0x30],
            allocations[0x20] + len(b"Hyper "),
        )
        self.assertEqual(
            allocations[0x20] + len(payloads[0x20]) + 1,
            allocations[0x30] + len(payloads[0x30]) + 1,
        )
        self.assertNotEqual(allocations[0x50], allocations[0x20])

    def test_best_fit_breaks_equal_size_ties_by_address(self) -> None:
        for spans in (
            [FreeSpan(0x200, 16), FreeSpan(0x100, 16)],
            [FreeSpan(0x100, 16), FreeSpan(0x200, 16)],
        ):
            with self.subTest(order=[span.start for span in spans]):
                inventory = {0: spans}
                self.assertEqual(allocate_best_fit(inventory, 0, 8), 0x100)

    def test_suffix_allocation_is_independent_of_payload_order(self) -> None:
        items = [
            (0x20, b"Hyper Potion"),
            (0x30, b"Potion"),
            (0x40, b"Antidote"),
            (0x50, b"Vol"),
        ]
        expected = None
        for ordered_items in (items, list(reversed(items))):
            inventory = {
                0: [FreeSpan(0x200, 64), FreeSpan(0x100, 64)]
            }
            allocations, failures = allocate_suffix_pooled(
                inventory,
                dict(ordered_items),
            )
            self.assertFalse(failures)
            if expected is None:
                expected = allocations
            else:
                self.assertEqual(allocations, expected)

    def test_global_partition_avoids_best_fit_fragmentation(self) -> None:
        # Best-fit decreasing puts 3 in the 4-byte span, then strands the
        # final 2-byte root.  The feasible partition is 2+2 and 3+2.
        greedy = {
            0: [FreeSpan(0x100, 4), FreeSpan(0x200, 5)],
        }
        self.assertIsNotNone(allocate_best_fit(greedy, 0, 3))
        self.assertIsNotNone(allocate_best_fit(greedy, 0, 2))
        self.assertIsNotNone(allocate_best_fit(greedy, 0, 2))
        self.assertIsNone(allocate_best_fit(greedy, 0, 2))

        spans = {
            0: [FreeSpan(0x100, 4), FreeSpan(0x200, 5)],
        }
        payloads = {
            0x20: b"A",
            0x30: b"B",
            0x40: b"C",
            0x50: b"DX",
        }
        allocations, failures = allocate_suffix_pooled(spans, payloads)

        self.assertFalse(failures)
        self.assertEqual(len(allocations), len(payloads))
        self.assertFalse(spans[0])

    def test_exact_fallback_repairs_cross_span_subset_conflict(self) -> None:
        # Per-span maximum subsets choose 2+2 for the 4-byte span and then
        # 3 for each 5-byte span, stranding the final 3.  A complete packing
        # exists: 3 / 3+2 / 3+2.
        spans = {
            0: [
                FreeSpan(0x100, 4),
                FreeSpan(0x200, 5),
                FreeSpan(0x300, 5),
            ]
        }
        payloads = {
            0x20: b"A",
            0x30: b"B",
            0x40: b"CX",
            0x50: b"DX",
            0x60: b"EX",
        }

        allocations, failures = allocate_suffix_pooled(spans, payloads)

        self.assertFalse(failures)
        self.assertEqual(set(allocations), set(payloads))
        self.assertEqual(sum(span.length for span in spans[0]), 1)

    def test_single_item_span_bound_rejects_impossible_partition(self) -> None:
        # Two 7-byte spans can hold only one root each (minimum root size 5
        # here).  Even with enough aggregate capacity, their unavoidable
        # waste makes the 10-byte span impossible to fill with the leftovers.
        spans = {
            0: [
                FreeSpan(0x100, 7),
                FreeSpan(0x200, 7),
                FreeSpan(0x300, 10),
            ]
        }
        payloads = {
            0x20: b"A" * 6,  # terminated size 7
            0x40: b"B" * 5,  # terminated size 6
            0x60: b"C" * 5,  # terminated size 6
            0x80: b"D" * 4,  # terminated size 5
        }
        _allocations, failures = allocate_suffix_pooled(spans, payloads)
        self.assertTrue(failures)

    def test_small_random_cases_match_an_exact_feasibility_oracle(self) -> None:
        def feasible(capacities: tuple[int, ...], sizes: tuple[int, ...]) -> bool:
            remaining = list(capacities)
            ordered = sorted(sizes, reverse=True)

            def place(index: int) -> bool:
                if index == len(ordered):
                    return True
                size = ordered[index]
                tried: set[int] = set()
                for bin_index in sorted(
                    range(len(remaining)),
                    key=lambda value: (remaining[value], value),
                ):
                    capacity = remaining[bin_index]
                    if capacity < size or capacity in tried:
                        continue
                    tried.add(capacity)
                    remaining[bin_index] -= size
                    if place(index + 1):
                        return True
                    remaining[bin_index] += size
                return False

            return place(0)

        rng = random.Random(0x163B1)
        for case in range(250):
            capacities = tuple(rng.randint(3, 12) for _ in range(rng.randint(1, 4)))
            sizes = tuple(rng.randint(2, 7) for _ in range(rng.randint(1, 8)))
            original_spans = [
                FreeSpan(0x100 + index * 0x100, capacity)
                for index, capacity in enumerate(capacities)
            ]
            payloads = {
                0x20 + index * 0x20: bytes([0x80 + index]) * (size - 1)
                for index, size in enumerate(sizes)
            }
            inventory = {
                0: [FreeSpan(span.start, span.length) for span in original_spans]
            }

            allocations, failures = allocate_suffix_pooled(inventory, payloads)
            oracle = feasible(capacities, sizes)

            with self.subTest(case=case, capacities=capacities, sizes=sizes):
                self.assertEqual(not failures, oracle)
                if oracle:
                    self.assertEqual(set(allocations), set(payloads))

    def test_randomized_allocation_properties_and_determinism(self) -> None:
        rng = random.Random(0x163)
        for case in range(100):
            payloads: dict[int, bytes] = {}
            source_offset = 0x100
            for identity in range(rng.randint(4, 36)):
                payload_length = rng.randint(1, 18)
                # The unique last byte prevents accidental suffix pooling.
                payloads[source_offset] = (
                    bytes([0x80 + identity]) * payload_length
                )
                source_offset += 0x20

            span_start = 0x2000
            original_spans: list[FreeSpan] = []
            for _ in range(rng.randint(1, 9)):
                original_spans.append(
                    FreeSpan(span_start, rng.randint(4, 80))
                )
                span_start += 0x100

            expected = None
            for reverse_payloads, reverse_spans in (
                (False, False),
                (True, False),
                (False, True),
                (True, True),
            ):
                payload_items = list(payloads.items())
                spans = [
                    FreeSpan(span.start, span.length)
                    for span in original_spans
                ]
                if reverse_payloads:
                    payload_items.reverse()
                if reverse_spans:
                    spans.reverse()
                inventory = {0: spans}
                allocations, failures = allocate_suffix_pooled(
                    inventory,
                    dict(payload_items),
                )
                result = (allocations, failures)
                if expected is None:
                    expected = result
                else:
                    self.assertEqual(result, expected, f"case {case}")

                allocated_ranges = sorted(
                    (
                        target,
                        target + len(payloads[source]) + 1,
                    )
                    for source, target in allocations.items()
                )
                for previous, current in zip(
                    allocated_ranges,
                    allocated_ranges[1:],
                ):
                    self.assertLessEqual(
                        previous[1],
                        current[0],
                        f"case {case}",
                    )
                for start, end in allocated_ranges:
                    self.assertTrue(
                        any(
                            span.start <= start
                            and end <= span.start + span.length
                            for span in original_spans
                        ),
                        f"case {case}",
                    )

                used = sum(
                    len(payloads[source]) + 1
                    for source in allocations
                )
                residual = sum(span.length for span in inventory[0])
                self.assertEqual(
                    used + residual,
                    sum(span.length for span in original_spans),
                    f"case {case}",
                )


class VerifiedPointerRedirectTests(unittest.TestCase):
    EXPECTED_REDIRECTS = {
        0x038347: (0x039D3B, 0x039AF5),
        0x03834B: (0x039D74, 0x039AF5),
        0x03834F: (0x039DB8, 0x039AF5),
        0x038353: (0x039DF5, 0x039AF5),
    }

    def setUp(self) -> None:
        self.original = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
        self.entries = {
            expected_target: [ref]
            for ref, (expected_target, _) in self.EXPECTED_REDIRECTS.items()
        }
        self.entries[0x039AF5] = [0x038343]

    def test_all_four_bad_refs_move_to_the_canonical_reply(self) -> None:
        self.assertEqual(
            VERIFIED_POINTER_REDIRECTS,
            self.EXPECTED_REDIRECTS,
        )
        original_entries = {
            target: list(refs)
            for target, refs in self.entries.items()
        }

        redirected = apply_verified_pointer_redirects(
            self.original,
            self.entries,
        )

        self.assertEqual(
            redirected[0x039AF5],
            [0x038343, 0x038347, 0x03834B, 0x03834F, 0x038353],
        )
        for wrong_target in (0x039D3B, 0x039D74, 0x039DB8, 0x039DF5):
            self.assertNotIn(wrong_target, redirected)
        self.assertEqual(
            self.entries,
            original_entries,
            "redirecting must not mutate the source inventory",
        )

    def test_redirect_rejects_a_changed_source_word(self) -> None:
        changed = bytearray(self.original)
        changed[0x038347:0x038349] = b"\x00\x00"

        with self.assertRaisesRegex(
            ValueError,
            r"verified redirect 0x038347: target",
        ):
            apply_verified_pointer_redirects(changed, self.entries)

    def test_redirect_rejects_an_unexpected_inventory_owner(self) -> None:
        entries = {
            target: list(refs)
            for target, refs in self.entries.items()
        }
        entries[0x039D3B].remove(0x038347)
        del entries[0x039D3B]
        entries[0x039AF5].append(0x038347)

        with self.assertRaisesRegex(
            ValueError,
            r"verified redirect 0x038347: owner unexpected",
        ):
            apply_verified_pointer_redirects(self.original, entries)


class VerifiedSourceAlignmentPointerRedirectTests(unittest.TestCase):
    def test_last_move_slots_follow_reviewed_chinese_ownership(self) -> None:
        original = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
        entries = {
            0x031619: [0x0310F3],
            0x031624: [0x0310F5],
            0x03162C: [0x0310F7],
        }

        redirected = apply_verified_source_alignment_pointer_redirects(
            original,
            entries,
        )

        self.assertNotIn(0x031619, redirected)
        self.assertEqual(redirected[0x031624], [0x0310F3])
        self.assertEqual(
            redirected[0x03162C],
            [0x0310F5, 0x0310F7],
        )


class VerifiedEmbeddedGraphicalTextTests(unittest.TestCase):
    EXPECTED_RECORDS = [
        (0x034927, 0x03492D, 6, 3),
        (0x034C03, 0x034C08, 6, 2),
        (0x038445, 0x0384F6, 7, 83),
        (0x03D088, 0x03D0A6, 7, 13),
    ]

    @classmethod
    def setUpClass(cls) -> None:
        cls.original = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()

    def test_four_embedded_records_are_verified_separately(self) -> None:
        standalone = verified_structured_glyph_records(self.original)
        embedded = verified_field_graphical_text_records(self.original)
        combined = verified_all_graphical_text_records(self.original)

        self.assertEqual(embedded, self.EXPECTED_RECORDS)
        self.assertEqual(len(standalone), STRUCTURED_GLYPH_RECORD_COUNT)
        self.assertEqual(combined, standalone + embedded)

    def test_dummy_interior_word_is_never_repointed(self) -> None:
        entries = {
            0x03F186: [0x03D074],
            0x03F26A: [0x03D086],
        }
        filtered = remove_verified_non_dialogue_pointer_refs(
            self.original,
            entries,
        )

        self.assertNotIn(0x03F186, filtered)
        self.assertEqual(filtered[0x03F26A], [0x03D086])
        self.assertEqual(entries[0x03F186], [0x03D074])

    def test_changed_dummy_word_is_rejected(self) -> None:
        changed = bytearray(self.original)
        changed[0x03D074:0x03D076] = b"\0\0"
        with self.assertRaisesRegex(
            ValueError,
            r"verified sentinel 0x03D074: target",
        ):
            remove_verified_non_dialogue_pointer_refs(
                changed,
                {},
            )


class CurrentRomPlanTests(unittest.TestCase):
    KNOWN_POINTER_TABLE_HOLES = (
        (0x033193, 0x03319B),
        (0x0331B3, 0x0331CB),
        (0x038313, 0x038327),
        (0x03AF94, 0x03AFAE),
        (0x03AFEA, 0x03B002),
        (0x03CF3E, 0x03CF5A),
        (0x03D07A, 0x03D082),
    )
    FORMER_FALSE_CONTEXT_REFS = {
        0x031C9C,
        0x0332F6,
        0x03338C,
        0x033FE6,
        0x034010,
        0x034074,
        0x03409A,
        0x0340A5,
        0x0340D2,
        0x034185,
        0x034279,
        0x0345C0,
        0x034649,
        0x034698,
        0x0352F4,
        0x0354B0,
        0x035A6D,
        0x035AD6,
        0x035B0E,
        0x035B54,
        0x035BB6,
        0x03A815,
        0x03EC3B,
    }

    def test_default_plan_avoids_table_holes_and_false_context_refs(self) -> None:
        args = build_parser().parse_args([])
        original, rows, row_refs, allocations, failures, _, _ = (
            compute_plan(args)
        )
        row_by_offset = {
            row.offset: (max_len, encoded)
            for row, max_len, encoded in rows
        }
        restoration_payloads = verified_dialogue_restoration_payloads(
            original
        )
        row_by_offset.update(
            {
                ref: (None, payload)
                for ref, payload in restoration_payloads.items()
            }
        )
        used_refs = {
            ref
            for target_refs in row_refs.values()
            for _, refs in target_refs
            for ref in refs
        }

        self.assertFalse(failures)
        expected_allocations = {
            row.offset
            for row, max_len, _ in rows
            if row_refs[row.offset]
            and has_source_record_terminator(
                original,
                row.offset,
                max_len,
            )
        }
        expected_allocations.update(restoration_payloads)
        self.assertEqual(set(allocations), expected_allocations)
        self.assertTrue(self.FORMER_FALSE_CONTEXT_REFS.isdisjoint(used_refs))

        for old_offset, new_offset in allocations.items():
            size = len(row_by_offset[old_offset][1]) + 1
            new_end = new_offset + size
            for hole_start, hole_end in self.KNOWN_POINTER_TABLE_HOLES:
                self.assertFalse(
                    new_offset < hole_end and new_end > hole_start,
                    (
                        f"translation 0x{old_offset:06X} allocated in "
                        f"pointer-table hole "
                        f"[0x{hole_start:06X},0x{hole_end:06X})"
                    ),
                )

    def test_default_plan_is_independent_of_python_hash_seed(self) -> None:
        script = """
import hashlib
from tools.validate_repacked import build_parser, compute_plan
args = build_parser().parse_args([])
_, _, _, allocations, failures, free_spans, _ = compute_plan(args)
assert not failures, failures
manifest = '\\n'.join(
    f'{source:06X}:{target:06X}'
    for source, target in sorted(allocations.items())
)
residual = '\\n'.join(
    f'{pair}:{span.start:06X}:{span.length}'
    for pair in sorted(free_spans)
    for span in free_spans[pair]
)
print(hashlib.sha256((manifest + '\\n' + residual).encode()).hexdigest())
"""
        outputs = []
        for seed in ("1", "777", "random"):
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = seed
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROM_DIR,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr,
            )
            outputs.append(result.stdout.strip())
        self.assertEqual(len(set(outputs)), 1, json.dumps(outputs))

    def test_untranslated_glyph_records_stay_protected(self) -> None:
        args = build_parser().parse_args([])
        (
            original,
            rows,
            row_refs,
            allocations,
            failures,
            _,
            _,
        ) = compute_plan(args)
        self.assertFalse(failures)

        records = verified_structured_glyph_records(original)
        self.assertEqual(len(records), STRUCTURED_GLYPH_RECORD_COUNT)
        self.assertEqual(
            sum(item[3] for item in records),
            STRUCTURED_GLYPH_PAIR_COUNT,
        )
        self.assertEqual(
            sum(end - start for start, end, _, _ in records),
            STRUCTURED_GLYPH_PAYLOAD_SIZE,
        )
        fingerprint = sha256(
            "\n".join(
                f"{start:06X}-{end:06X}"
                for start, end, _, _ in records
            ).encode("ascii")
        )
        self.assertEqual(
            fingerprint,
            STRUCTURED_GLYPH_RECORDS_SHA256,
        )
        self.assertIn(
            (0x031231, 0x031237, 6, 3),
            records,
            "B1 0D must remain a glyph code, not a delimiter",
        )
        self.assertFalse(
            any(start == 0x031233 for start, _, _, _ in records),
            "the parser must not split Powder Snow after B1 0D",
        )

        glyph_starts = {start for start, _, _, _ in records}
        translated_glyph_starts = {
            row.offset
            for row, _, _ in rows
            if row.offset in glyph_starts
        }
        self.assertEqual(
            len(translated_glyph_starts),
            STRUCTURED_GLYPH_RECORD_COUNT - 18,
        )
        relocatable_glyph_starts = {
            row.offset
            for row, max_len, _ in rows
            if row.offset in translated_glyph_starts
            and row_refs[row.offset]
            and has_source_record_terminator(
                original,
                row.offset,
                max_len,
            )
        }
        self.assertTrue(relocatable_glyph_starts.issubset(allocations))
        fixed_glyph_starts = translated_glyph_starts - set(allocations)
        self.assertTrue(fixed_glyph_starts)
        self.assertTrue(
            all(not row_refs[offset] for offset in fixed_glyph_starts)
        )

        glyph_spans = [
            (start, end)
            for start, end, _, _ in records
            if start not in translated_glyph_starts
        ]
        encoded_by_offset = {
            row.offset: encoded
            for row, _, encoded in rows
        }
        encoded_by_offset.update(
            verified_dialogue_restoration_payloads(original)
        )
        for old_offset, new_offset in allocations.items():
            allocation_end = (
                new_offset + len(encoded_by_offset[old_offset]) + 1
            )
            for glyph_start, glyph_end in glyph_spans:
                self.assertFalse(
                    new_offset < glyph_end
                    and allocation_end > glyph_start,
                    (
                        f"translation 0x{old_offset:06X} allocated in "
                        f"glyph record 0x{glyph_start:06X}-"
                        f"0x{glyph_end:06X}"
                    ),
                )

        used_refs = {
            ref
            for target_refs in row_refs.values()
            for _, refs in target_refs
            for ref in refs
        }
        used_refs.update(
            verified_dialogue_restoration_payloads(original)
        )
        for ref in used_refs:
            for glyph_start, glyph_end in glyph_spans:
                self.assertFalse(
                    ref < glyph_end and ref + 2 > glyph_start,
                    (
                        f"pointer 0x{ref:06X} overlaps glyph record "
                        f"0x{glyph_start:06X}-0x{glyph_end:06X}"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
