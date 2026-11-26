"""Compact French item names for the shop list in PRG pair 4."""

SHOP_ITEM_NAMES = (
    "Poké Ball", "Super Ball", "Hyper Ball", "Master Ball", "Potion",
    "Super Potion", "Hyper Potion", "Max Potion", "Antidote", "Anti-Para",
    "Réveil", "Antigel", "Anti-Brûle", "Total Soin", "Rappel", "Huile",
    "Huile Max", "Super Bonbon", "Pierre Feu", "Pierre Eau",
    "Pierre Foudre", "Pierre Plante", "Pierre Lune",
)

# Lengths of the existing visible labels, in item ID order (1–23).
# Keep their draw cadence when the complete name fits the same number of tiles.
STOCK_COLUMNS = (6, 7, 7, 7, 6, 7, 7, 7, 6, 6, 6, 7, 7, 7, 6, 5, 7, 7, 5, 5, 5, 6, 6)

FONT = {
    " ": ("00",) * 8,
    "-": ("000", "000", "000", "000", "111", "000", "000", "000"),
    "A": ("0000", "0110", "1001", "1001", "1111", "1001", "1001", "0000"),
    "B": ("0000", "1110", "1001", "1110", "1001", "1001", "1110", "0000"),
    "E": ("0000", "1111", "1000", "1110", "1000", "1000", "1111", "0000"),
    "F": ("0000", "1111", "1000", "1110", "1000", "1000", "1000", "0000"),
    "H": ("0000", "1001", "1001", "1111", "1001", "1001", "1001", "0000"),
    "L": ("000", "100", "100", "100", "100", "100", "111", "000"),
    "M": ("00000", "10001", "11011", "10101", "10001", "10001", "10001", "00000"),
    "P": ("0000", "1110", "1001", "1001", "1110", "1000", "1000", "0000"),
    "R": ("0000", "1110", "1001", "1001", "1110", "1010", "1001", "0000"),
    "S": ("0000", "0111", "1000", "0110", "0001", "0001", "1110", "0000"),
    "T": ("000", "111", "010", "010", "010", "010", "010", "000"),
    "a": ("000", "000", "110", "001", "111", "101", "111", "000"),
    "b": ("000", "100", "100", "110", "101", "101", "110", "000"),
    "d": ("000", "001", "001", "011", "101", "101", "011", "000"),
    "e": ("000", "000", "010", "101", "111", "100", "011", "000"),
    "é": ("001", "010", "010", "101", "111", "100", "011", "000"),
    "g": ("000", "000", "011", "101", "101", "011", "001", "110"),
    "i": ("0", "1", "0", "1", "1", "1", "1", "0"),
    "k": ("000", "100", "100", "101", "110", "101", "101", "000"),
    "l": ("0", "1", "1", "1", "1", "1", "1", "0"),
    "n": ("000", "000", "110", "101", "101", "101", "101", "000"),
    "o": ("000", "000", "010", "101", "101", "101", "010", "000"),
    "p": ("000", "000", "110", "101", "101", "110", "100", "100"),
    "r": ("000", "000", "110", "101", "100", "100", "100", "000"),
    "s": ("000", "000", "011", "100", "010", "001", "110", "000"),
    "t": ("000", "010", "111", "010", "010", "010", "011", "000"),
    "u": ("000", "000", "101", "101", "101", "101", "011", "000"),
    "û": ("010", "101", "000", "101", "101", "101", "011", "000"),
    "v": ("000", "000", "101", "101", "101", "101", "010", "000"),
    "x": ("000", "000", "101", "101", "010", "101", "101", "000"),
    "y": ("000", "000", "101", "101", "101", "011", "001", "110"),
}

NAME_COLUMNS = 7
ITEM_DRAW_OFFSET = 0x026643               # $E633: JSR $891C
ITEM_CODE_OFFSET = 0x0275C2               # $F5B2: after Achat/Vente graphics
ITEM_CODE_ADDRESS = 0xF5B2
ITEM_CODE_LIMIT = 0x027C10


def shop_name_tiles(text: str, columns: int = NAME_COLUMNS) -> bytes:
    """Return the high plane of the lower tile of each two-tile column."""
    width = columns * 8
    rows = ["0".join(FONT[letter][y] for letter in text) for y in range(8)]
    if len(rows[0]) > width:
        raise ValueError(f"Le nom {text!r} dépasse les {width} pixels de la liste")
    rows = [row.ljust(width, "0") for row in rows]
    return bytes(
        0xFF ^ int(row[x:x + 8], 2)
        for x in range(0, width, 8)
        for row in rows
    )


def shop_item_name_patches() -> tuple[tuple[int, bytes, bytes], ...]:
    # $E633 receives the item ID in A and the draw position in $09/$0A
    # (CHR) and $0E/$0F (nametable). Zero retains the native empty-stock path.
    prefix = bytes.fromhex("C9 01 90 04 C9 18 90 03 4C 1C 89 AA CA")
    draw_column = bytes.fromhex(
        "20 CD F2 A9 03 8D 00 07 A9 01 8D 01 07 8D 05 07"
        "A5 0F 8D 02 07 A5 0E 8D 03 07 18 69 20 8D 07 07 A5 0F 69 00 8D 06 07"
        "A5 0A 0A 0A 0A 0A 85 07 A5 09 4A 4A 4A 4A 05 07 8D 04 07 18 69 01 8D 08 07"
        "A9 20 8D 09 07 A5 0A 8D 0A 07 A5 09 8D 0B 07"
        # Fill 24 bytes of solid background. Overlay the eight bitmap rows.
        "A2 0C A9 FF 9D 00 07 E8 E0 24 D0 F8"
        "A0 00 B1 04 99 24 07 C8 C0 08 D0 F6"
        "A9 FF 85 2D"
        # Advance the graphics pointer, CHR address and nametable position.
        "A5 04 18 69 08 85 04 90 02 E6 05"
        "A5 09 18 69 20 85 09 90 02 E6 0A"
        "E6 0E D0 02 E6 0F C6 06"
    )
    loop = ITEM_CODE_ADDRESS + len(prefix) + 15
    end_loop = bytes.fromhex("F0 03 4C") + loop.to_bytes(2, "little") + bytes.fromhex("60")
    pointer_low = loop + len(draw_column) + len(end_loop)
    pointer_high = pointer_low + len(SHOP_ITEM_NAMES)
    column_table = pointer_high + len(SHOP_ITEM_NAMES)
    first_tiles = column_table + len(SHOP_ITEM_NAMES)
    columns = tuple(
        max(stock, (sum(len(FONT[letter][0]) + 1 for letter in name) + 6) // 8)
        for stock, name in zip(STOCK_COLUMNS, SHOP_ITEM_NAMES, strict=True)
    )
    if max(columns) > NAME_COLUMNS:
        raise ValueError("Un nom d’objet dépasse les sept cases du magasin")
    starts = []
    tiles = bytearray()
    for width, name in zip(columns, SHOP_ITEM_NAMES, strict=True):
        starts.append(first_tiles + len(tiles))
        tiles.extend(shop_name_tiles(name, width))
    lookup = (
        b"\xBD" + pointer_low.to_bytes(2, "little") + b"\x85\x04"
        + b"\xBD" + pointer_high.to_bytes(2, "little") + b"\x85\x05"
        + b"\xBD" + column_table.to_bytes(2, "little") + b"\x85\x06"
    )
    code_and_tiles = (
        prefix + lookup + draw_column + end_loop
        + bytes(address & 0xFF for address in starts)
        + bytes(address >> 8 for address in starts)
        + bytes(columns) + tiles
    )
    if ITEM_CODE_OFFSET + len(code_and_tiles) > ITEM_CODE_LIMIT:
        raise ValueError("Les noms d’objets dépassent l’espace disponible en banque 4")
    return (
        (ITEM_DRAW_OFFSET, bytes.fromhex("20 1C 89"), b"\x20" + ITEM_CODE_ADDRESS.to_bytes(2, "little")),
        (ITEM_CODE_OFFSET, bytes(len(code_and_tiles)), code_and_tiles),
    )


def patch_shop_item_names(rom: bytearray) -> None:
    for offset, original, replacement in shop_item_name_patches():
        end = offset + len(original)
        if rom[offset:end] != original:
            raise ValueError(f"Code de liste boutique inattendu à 0x{offset:06X}")
        rom[offset:end] = replacement
