"""Quick Attack priority for the ordinary two-move battle path."""


def quick_attack_priority_patches() -> tuple[tuple[int, bytes, bytes], ...]:
    # $7DEB and $7DEC select the four move slots. Values outside those slots
    # use the original order logic, including item, switch and skipped turns.
    code = bytes.fromhex(
        "AE EB 7D E0 04 B0 20 AC EC 7D C0 04 B0 19"
        "BD 7A 7D C9 8C D0 09"  # player move ID, $8C = Quick Attack
        "B9 58 7D C9 8C F0 0B 38 60"  # only the player: carry set
        "B9 58 7D C9 8C D0 02 18 60"  # only the opponent: carry clear
        "4C 7E A0"  # same priority: stock effective-speed comparison
    )
    return (
        (0x022060, bytes.fromhex("20 7E A0"), bytes.fromhex("20 50 FB")),
        (0x027B60, bytes(len(code)), code),
    )


def patch_quick_attack_priority(rom: bytearray) -> None:
    for offset, original, replacement in quick_attack_priority_patches():
        end = offset + len(original)
        if rom[offset:end] != original:
            raise ValueError(f"Unexpected turn-order code at 0x{offset:06X}")
        rom[offset:end] = replacement
