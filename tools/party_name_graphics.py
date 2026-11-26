"""Pack the longest species names into their reserved party-list CHR blocks."""

if __package__:
    from .french_font import decode_game_text
    from .shop_item_graphics import FONT
else:
    from french_font import decode_game_text
    from shop_item_graphics import FONT


PARTY_FONT = {
    **FONT,
    "C": ("0000", "0111", "1000", "1000", "1000", "1000", "0111", "0000"),
    "D": ("0000", "1110", "1001", "1001", "1001", "1001", "1110", "0000"),
    "G": ("0000", "0111", "1000", "1000", "1011", "1001", "0111", "0000"),
    "I": ("000", "111", "010", "010", "010", "010", "111", "000"),
    "K": ("0000", "1001", "1010", "1100", "1010", "1001", "1001", "0000"),
    "N": ("0000", "1001", "1101", "1101", "1011", "1011", "1001", "0000"),
    "O": ("0000", "0110", "1001", "1001", "1001", "1001", "0110", "0000"),
    "É": ("0010", "1111", "1000", "1110", "1000", "1000", "1111", "0000"),
    "c": ("000", "000", "011", "100", "100", "100", "011", "000"),
    "f": ("000", "011", "010", "111", "010", "010", "010", "000"),
    "h": ("000", "100", "100", "110", "101", "101", "101", "000"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101", "00000"),
    "q": ("000", "000", "011", "101", "101", "011", "001", "001"),
    "w": ("00000", "00000", "10001", "10001", "10101", "10101", "01010", "00000"),
    "z": ("000", "000", "111", "001", "010", "100", "111", "000"),
    "è": ("100", "010", "010", "101", "111", "100", "011", "000"),
}

PARTY_HOOK = 0x06BB11  # $BB01: draw a name after selecting its species
PARTY_CODE_OFFSET = 0x06E7AF  # $E79F, zero-filled in pair 13
PARTY_CPU_ADDRESS = 0xE79F
PARTY_CODE_LIMIT = 0x06FC10
SPECIES_END = 160  # IDs 1–159, including the game's extra Johto/Hoenn species
SPECIES_POINTERS = 0x030975


def party_name_bitmap(name: str) -> bytes:
    """Return the width in CHR columns and the lower-tile ink planes."""
    rows = ["0".join(PARTY_FONT[letter][y] for letter in name) for y in range(8)]
    columns = (len(rows[0]) + 7) // 8
    if columns > 8:
        raise ValueError(f"Le nom {name!r} dépasse le bloc CHR d’un membre de l’équipe")
    rows = [row.ljust(columns * 8, "0") for row in rows]
    return bytes([columns]) + bytes(
        int(row[x:x + 8], 2) for x in range(0, columns * 8, 8) for row in rows
    )


def party_name_patches(rom: bytes | bytearray) -> tuple[tuple[int, bytes, bytes], ...]:
    prefix = bytes.fromhex("A5 6A C9 A0 B0 0F AA")
    fallback = bytes.fromhex("F0 02 D0 03 4C 11 8D")
    draw = bytes.fromhex(
        "A0 00 B1 04 85 06"  # width of this name
        "A5 15 29 7F 8D 00 20 2C 02 20"  # rendering is already off; mask NMI during upload
        "A5 0A 0A 0A 0A 0A 85 07"  # first tile = high byte of CHR address times 16
        "A5 0F 8D 06 20 A5 0E 8D 06 20 A5 07 A6 06"
        "8D 07 20 18 69 02 CA D0 F7"  # upper name tiles in the nametable
        "A5 0E 18 69 20 48 A5 0F 69 00 8D 06 20 68 8D 06 20"
        "A5 07 09 01 A6 06 8D 07 20 18 69 02 CA D0 F7"  # lower name tiles
        "A5 0A 8D 06 20 A5 09 8D 06 20 C8"
        "A9 00 A2 10 8D 07 20 CA D0 FA"  # upper tile is blank
        "A2 08 B1 04 8D 07 20 C8 CA D0 F7"  # lower tile is the ink plane and eight zero bytes
        "A9 00 A2 08 8D 07 20 CA D0 FA C6 06 D0 DD"
        "A5 15 8D 00 20 A9 0D 60"
    )
    pointer_low = PARTY_CPU_ADDRESS + len(prefix) + 10 + len(fallback) + len(draw)
    pointer_high = pointer_low + SPECIES_END
    first_tiles = pointer_high + SPECIES_END
    starts = [0]
    tiles = bytearray()
    for species in range(1, SPECIES_END):
        ref = SPECIES_POINTERS + 2 * species
        addr = int.from_bytes(rom[ref:ref + 2], "little") + 0x028010
        end = rom.index(0x0D, addr, min(addr + 24, 0x038010))
        name = decode_game_text(bytes(rom[addr:end])).strip()
        if len(name) <= 8:
            starts.append(0)
            continue
        starts.append(first_tiles + len(tiles))
        tiles.extend(party_name_bitmap(name))
    lookup = (
        b"\xBD" + pointer_low.to_bytes(2, "little") + b"\x85\x04"
        + b"\xBD" + pointer_high.to_bytes(2, "little") + b"\x85\x05"
    )
    code_and_tiles = (
        prefix + lookup + fallback + draw
        + bytes(address & 0xFF for address in starts)
        + bytes(address >> 8 for address in starts)
        + tiles
    )
    if PARTY_CODE_OFFSET + len(code_and_tiles) > PARTY_CODE_LIMIT:
        raise ValueError("Les noms d’espèces dépassent l’espace disponible en banque 13")
    return (
        (PARTY_HOOK, bytes.fromhex("20 11 8D"), b"\x20" + PARTY_CPU_ADDRESS.to_bytes(2, "little")),
        (PARTY_CODE_OFFSET, bytes(len(code_and_tiles)), code_and_tiles),
    )


def patch_party_names(rom: bytearray) -> None:
    for offset, original, replacement in party_name_patches(rom):
        end = offset + len(original)
        if rom[offset:end] != original:
            raise ValueError(f"Code de liste d’équipe inattendu à 0x{offset:06X}")
        rom[offset:end] = replacement
