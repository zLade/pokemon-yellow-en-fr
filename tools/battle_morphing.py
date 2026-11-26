"""Player Morphing effect, entirely within battle PRG bank 4."""

# Both native save checksums end below $7E00. The sound engine clears
# $7E10..$7F0F and keeps its remaining registers through $7F21.
# The reset loop clears this spare byte along with the $7F00 page.
MORPH_FORM_ADDRESS = 0x7FBF


def morphing_patches() -> tuple[tuple[int, bytes, bytes], ...]:
    form = MORPH_FORM_ADDRESS.to_bytes(2, "little").hex(" ")
    # $7D66 retains Ditto's species. The active moves and PP are temporary.
    effect = bytes.fromhex(
        f"AD {form} D0 3F"  # already transformed: preserve original PP
        "AD 66 7D C9 84 D0 38"  # only Ditto
        "AD 46 7D F0 33 C9 84 F0 2F C9 98 B0 2B"
        f"8D {form}"
        "AC A8 7D B9 C9 60 A8"  # visible position -> persistent party slot
        "AD 7E 7D 99 7B 60"  # save the real, already debited Morphing PP
        "A2 03"
        "BD 58 7D 9D 7A 7D C9 FF F0 04 A9 05 D0 02 A9 00"
        "9D 7E 7D CA 10 EA"
        "4C E3 8F"  # reload the player sprite using the same path as battle entry
        "60"
    )
    save_moves = bytes.fromhex(
        f"AD {form} F0 03 4C 30 98"  # copy status, bypass writeback of temporary moves/PP
        "AD 7A 7D 4C 03 98"
    )
    new_combatant = bytes.fromhex(f"A9 00 8D {form} B9 C9 60 60")
    display_species = bytes.fromhex(f"AD {form} D0 03 AD 66 7D 60")
    item_reload = bytes.fromhex("B9 C9 60 4C 40 98")  # retain the form when reloading the same active slot
    reload_moves = bytes.fromhex(
        f"AD {form} F0 03 4C A1 98"  # restore status after an item; keep copied moves and PP
        "B9 63 60 4C 74 98"
    )
    addresses = (0xFB7A, 0xFB7A + len(effect))
    load_address = addresses[1] + len(save_moves)
    display_address = load_address + len(new_combatant)
    item_address = display_address + len(display_species)
    reload_address = item_address + len(item_reload)
    decline_address = reload_address + len(reload_moves)
    # After a trainer sends a new opponent, cancelling a proposed switch
    # keeps our current fighter. A confirmed switch enters at $BB2E.
    decline_switch = bytes.fromhex("AC A8 7D 20") + item_address.to_bytes(2, "little") + bytes.fromhex("4C 31 BB")
    code = effect + save_moves + new_combatant + display_species + item_reload + reload_moves + decline_switch
    if 0xFB7A + len(code) > 0xFC00:
        raise ValueError("Le code de Morphing dépasse la réserve de la banque de combat")
    # The bag's move picker and the party status panel share the live battle
    # buffer. Keep its eight bytes across either menu, including cancellation.
    # The original callers consume carry; PLA, STA and DEX preserve it.
    push_moves = bytes.fromhex("A2 00 BD 7A 7D 48 E8 E0 08 D0 F7")
    pop_moves = bytes.fromhex("A2 07 68 9D 7A 7D CA 10 F9")

    def preserve_menu_moves(target: int) -> bytes:
        jump = target.to_bytes(2, "little")
        return (bytes.fromhex(f"AD {form} D0 03 4C") + jump
                + push_moves + b"\x20" + jump + pop_moves + b"\x60")

    bag = preserve_menu_moves(0xFF25)
    party = preserve_menu_moves(0xFF3F)
    menu_address = 0xF45A
    if menu_address + len(bag + party) > 0xF4A0:
        raise ValueError("Les sauvegardes temporaires débordent de la banque de combat")
    # The XP loop can load and update several party slots. The original call
    # at $BFC4 has already committed the active fighter's HP/status. Let XP
    # operate on real moves, then return the copied form to the same fighter.
    xp_address = 0xFF73
    xp_prefix = bytes.fromhex("A2 00 8E B7 7D 4C CC BF")
    xp_save = b"\x48" + push_moves + bytes.fromhex(f"A9 00 8D {form} 20")
    xp_restore = pop_moves + bytes.fromhex(f"68 8D {form} 60")
    xp_entry = (xp_address + 8 + len(xp_save) + 2 + len(xp_restore)).to_bytes(2, "little")
    xp = (bytes.fromhex(f"AD {form} D0 03 4C") + xp_entry
          + xp_save + xp_entry + xp_restore + xp_prefix)
    # Both battle exits have finished writing the party and loaded A=0.
    # Clear the copied species before the original handoff to the field.
    exit_address = xp_address + len(xp)
    exit_code = bytes.fromhex(f"8D {form} 4C 75 F1")
    exit_tail = bytes.fromhex("A9 00 8D 0E 7D 85 7F 8D 0F 7D 4C 75 F1")
    if exit_address + len(exit_code) > 0xFFC0:
        raise ValueError("La sauvegarde temporaire des gains sort de la réserve")
    return (
        (0x023FD7, xp_prefix[:5], b"\x4c" + xp_address.to_bytes(2, "little") + b"\xea\xea"),
        (0x027F83, bytes(len(xp + exit_code)), xp + exit_code),
        *((address + 0x18010, exit_tail, exit_tail[:-2] + exit_address.to_bytes(2, "little"))
          for address in (0x9E14, 0x9E2D)),
        (0x02345C, bytes.fromhex("20 25 FF"), b"\x20" + menu_address.to_bytes(2, "little")),
        (0x023498, bytes.fromhex("20 3F FF"), b"\x20" + (menu_address + len(bag)).to_bytes(2, "little")),
        (0x023B2D, bytes.fromhex("20 3F FF"), b"\x20" + (menu_address + len(bag)).to_bytes(2, "little")),
        (0x023B3B, bytes.fromhex("AC A8 7D"), b"\x4c" + decline_address.to_bytes(2, "little")),
        (0x02746A, bytes(len(bag + party)), bag + party),
        (0x024BC3, bytes.fromhex("45 CE"), addresses[0].to_bytes(2, "little")),
        (0x021810, bytes.fromhex("AD 7A 7D"), b"\x4c" + addresses[1].to_bytes(2, "little")),
        (0x02184D, bytes.fromhex("B9 C9 60"), b"\x20" + load_address.to_bytes(2, "little")),
        (0x023463, bytes.fromhex("20 3D 98"), b"\x20" + item_address.to_bytes(2, "little")),
        # B after inspecting the team reloads the same fighter. Only the
        # accepted switch at $B493 should initialize a new combatant.
        (0x0234C6, bytes.fromhex("20 3D 98"), b"\x20" + item_address.to_bytes(2, "little")),
        (0x021881, bytes.fromhex("B9 63 60"), b"\x4c" + reload_address.to_bytes(2, "little")),
        *((address + 0x18010, bytes.fromhex("AD 66 7D"), b"\x20" + display_address.to_bytes(2, "little"))
          for address in (0x8FCC, 0x8FE6, 0xEA44, 0xEA8E)),
        (0x027B8A, bytes(len(code)), code),
    )


def patch_morphing(rom: bytearray) -> None:
    for offset, original, replacement in morphing_patches():
        if rom[offset:offset + len(original)] != original:
            raise ValueError(f"Code de Morphing inattendu à 0x{offset:06X}")
        rom[offset:offset + len(original)] = replacement
