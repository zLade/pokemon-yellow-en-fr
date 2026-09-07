"""Regression checks for English dialogue-validation metadata."""

from collections import Counter
import unittest

from tools.validate_dialogue_layout import NON_DIALOGUE_BOUNDARY_EXEMPTIONS


class DialogueValidationMetadataTests(unittest.TestCase):
    def test_english_exemption_labels_preserve_the_exact_offset_set(self) -> None:
        self.assertEqual(
            set(NON_DIALOGUE_BOUNDARY_EXEMPTIONS),
            {
                0x030392, 0x0304C2, 0x0304CF, 0x0304DB, 0x0304F1,
                0x0304FB, 0x030505, 0x03050F, 0x030519, 0x030541,
                0x030555, 0x0306FE, 0x030744, 0x0307B9, 0x0307C4,
                0x0307CF, 0x031AE8, 0x031B29, 0x031B54, 0x031B67,
                0x031B7A,
            },
        )
        self.assertEqual(
            Counter(NON_DIALOGUE_BOUNDARY_EXEMPTIONS.values()),
            {"battle_message": 16, "item_interface": 5},
        )


if __name__ == "__main__":
    unittest.main()
