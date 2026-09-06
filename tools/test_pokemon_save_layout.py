from __future__ import annotations

import unittest
import random

from pokemon_save_layout import (
    BACKUP_OFFSET,
    BADGES_OFFSET,
    CAUGHT_BITS_OFFSET,
    POKEDEX_STANDARD_COUNT,
    POKEDEX_UNLOCK_MASK,
    POKEDEX_UNLOCK_OFFSET,
    PRIMARY_SIZE,
    SAVE_MAGIC,
    SAVE_MAGIC_OFFSET,
    SAVE_SIZE,
    SEEN_BITS_OFFSET,
    apply_complete_standard_pokedex,
    caught_species,
    party_summary,
    seen_species,
    synchronize_save,
    primary_backup_matches,
    save_magic_valid,
    validate_save_image,
    validate_standard_pokedex,
)


class PokemonSaveLayoutTests(unittest.TestCase):
    def test_complete_standard_pokedex_is_exactly_151(self) -> None:
        primary = bytearray(PRIMARY_SIZE)
        apply_complete_standard_pokedex(primary)
        self.assertEqual(caught_species(primary), list(range(1, 152)))
        self.assertEqual(seen_species(primary), list(range(1, 152)))
        self.assertEqual(primary[POKEDEX_UNLOCK_OFFSET] & POKEDEX_UNLOCK_MASK, 0x20)
        self.assertEqual(primary[CAUGHT_BITS_OFFSET + 18], 0x7F)
        self.assertEqual(primary[SEEN_BITS_OFFSET + 18], 0x7F)
        self.assertEqual(primary[CAUGHT_BITS_OFFSET + 19], 0)
        self.assertEqual(primary[SEEN_BITS_OFFSET + 19], 0)
        self.assertEqual(validate_standard_pokedex(primary), [])

    def test_natural_tas_bitmaps_decode_to_observed_counts(self) -> None:
        primary = bytearray(PRIMARY_SIZE)
        primary[0x31] = 6
        primary[0x32] = 4
        primary[CAUGHT_BITS_OFFSET : CAUGHT_BITS_OFFSET + 19] = bytes.fromhex(
            "00 02 00 03 00 00 80 00 00 00 00 00 00 00 00 00 00 00 00"
        )
        primary[SEEN_BITS_OFFSET : SEEN_BITS_OFFSET + 19] = bytes.fromhex(
            "00 02 10 03 00 00 80 00 00 00 00 00 00 00 00 00 10 00 00"
        )
        self.assertEqual(caught_species(primary), [10, 25, 26, 56])
        self.assertEqual(seen_species(primary), [10, 21, 25, 26, 56, 133])
        self.assertEqual(validate_standard_pokedex(primary), [])

    def test_natural_tas_party_structure(self) -> None:
        primary = bytearray(PRIMARY_SIZE)
        primary[0x30] = 3
        primary[0x33:0x39] = bytes([26, 56, 10, 0, 0, 0])
        primary[0x39:0x3F] = bytes([7, 5, 4, 0, 0, 0])
        primary[0xC9:0xCF] = bytes([1, 0, 2, 3, 4, 5])
        summary = party_summary(primary)
        self.assertEqual(summary.count, 3)
        self.assertEqual(summary.order, (1, 0, 2))
        self.assertEqual(summary.species, (56, 26, 10))
        self.assertEqual(summary.levels, (5, 7, 4))

    def test_synchronize_save_updates_backup_and_magic_only_as_requested(self) -> None:
        save = bytearray(SAVE_SIZE)
        save[:PRIMARY_SIZE] = bytes(index & 0xFF for index in range(PRIMARY_SIZE))
        save[BADGES_OFFSET] = 0xA5
        synchronize_save(save)
        self.assertEqual(
            save[BACKUP_OFFSET : BACKUP_OFFSET + PRIMARY_SIZE],
            save[:PRIMARY_SIZE],
        )
        self.assertEqual(
            save[SAVE_MAGIC_OFFSET : SAVE_MAGIC_OFFSET + len(SAVE_MAGIC)],
            SAVE_MAGIC,
        )
        self.assertTrue(save_magic_valid(save))
        self.assertTrue(primary_backup_matches(save))

    def test_empty_truncated_and_corrupt_saves_are_rejected(self) -> None:
        self.assertEqual(
            validate_save_image(bytes(SAVE_SIZE - 1)),
            [f"save size={SAVE_SIZE - 1}, expected={SAVE_SIZE}"],
        )
        empty = bytearray(SAVE_SIZE)
        errors = validate_save_image(empty)
        self.assertIn("save magic is absent or corrupt", errors)

        valid = bytearray(SAVE_SIZE)
        synchronize_save(valid)
        self.assertEqual(validate_save_image(valid), [])

        valid[SAVE_MAGIC_OFFSET] ^= 1
        self.assertIn("save magic is absent or corrupt", validate_save_image(valid))

    def test_interrupted_primary_or_backup_writes_are_detected(self) -> None:
        baseline = bytearray(SAVE_SIZE)
        baseline[0x50] = 0x42
        synchronize_save(baseline)
        self.assertEqual(validate_save_image(baseline), [])

        primary_torn = bytearray(baseline)
        primary_torn[0x50] ^= 1
        self.assertIn(
            "primary and backup blocks differ",
            validate_save_image(primary_torn),
        )

        backup_torn = bytearray(baseline)
        backup_torn[BACKUP_OFFSET + 0x50] ^= 1
        self.assertIn(
            "primary and backup blocks differ",
            validate_save_image(backup_torn),
        )

    def test_random_single_byte_corruption_in_proven_regions_is_detected(self) -> None:
        rng = random.Random(0x5A163)
        baseline = bytearray(SAVE_SIZE)
        synchronize_save(baseline)
        for index in range(100):
            corrupted = bytearray(baseline)
            relative = rng.randrange(PRIMARY_SIZE)
            if index % 2:
                relative += BACKUP_OFFSET
            corrupted[relative] ^= 1 << rng.randrange(8)
            with self.subTest(index=index, offset=relative):
                self.assertTrue(validate_save_image(corrupted))

    def test_invalid_party_metadata_is_reported(self) -> None:
        save = bytearray(SAVE_SIZE)
        save[0x30] = 7
        synchronize_save(save)
        self.assertTrue(
            any("invalid party count" in item for item in validate_save_image(save))
        )


if __name__ == "__main__":
    unittest.main()
