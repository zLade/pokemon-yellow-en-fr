#!/usr/bin/env python3
"""Apply and audit the exhaustive 2026-08-16 English text review.

``catalog.csv`` remains the canonical build input.  This module keeps the
editorial changes deterministic, updates the generated/review witnesses, and
emits a row-for-row report covering the complete catalogue plus every pointer
variant.  It deliberately does not touch ROMs or publish release artifacts.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.locales.profiles import ENGLISH_TEXT_PROFILE  # noqa: E402


LOCALE = ROOT / "locales" / "en-US"
CATALOGUE = LOCALE / "catalog.csv"
VARIANTS = LOCALE / "pointer_variants.csv"
REVIEW_BATCHES = LOCALE / "review_batches"
OFFICIAL_AUDIT = LOCALE / "official_gen1_scene_audit.csv"
OFFICIAL_CHANGES = LOCALE / "official_reference_consistency_changes.csv"
REVIEW_SHEET = LOCALE / "ENGLISH_REVIEW_SHEET.csv"
REPORT = LOCALE / "FULL_TEXT_REVIEW_20260816.csv"


@dataclass(frozen=True)
class Revision:
    text: str
    reason: str
    review_class: str = "natural_english"


def r(text: str, reason: str, review_class: str = "natural_english") -> Revision:
    return Revision(text=text, reason=reason, review_class=review_class)


# Only certain corrections belong here.  Ambiguous source readings are kept
# unchanged and recorded in the accompanying review report/documentation.
REVISIONS: Mapping[str, Revision] = {
    # Fixed/system text and executable-context corrections.
    "MAIN:0x030409": r(
        " is evolving!",
        "Removes the contradictory ellipsis-plus-exclamation ending from the dynamic evolution suffix.",
        "dynamic_boundary",
    ),
    # Battle message rows expose 25 interior cells.  The reviewed engine patch
    # clears all 25 between messages; most payloads still stay at or below 24
    # for margin.  Callsites already on row two must be compacted in place
    # rather than carrying a line-break control that would request row three.
    "MAIN:0x0301D7": r(" appeared!", "Keeps the wild-appearance suffix on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030242": r(" broke free!", "Uses the compact Gen I capture-failure formula on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x03024E": r(" was caught!", "Keeps the capture-success suffix on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x0302FA": r(" was badly poisoned!", "Keeps the distinct bad-poison result natural on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x03030E": r(" became confused!", "Keeps the normal confusion result natural on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030324": r(" was hurt by poison!", "Keeps poison damage intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x03034B": r(" was hurt by its burn!", "Keeps burn damage intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030364": r(" hurt itself!", "Uses the concise official battle sense without splitting a word.", "dynamic_layout_24"),
    "MAIN:0x030373": r(" is frozen solid!", "Keeps the frozen/no-action state natural within one row.", "dynamic_layout_24"),
    "MAIN:0x030381": r(" was hurt by poison!", "Keeps the severe-poison damage event clear without overflowing.", "dynamic_layout_24"),
    "MAIN:0x030392": r(" flinched!", "Uses the concise Gen I flinch formula on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x0303A9": r(" won't rise!", "Keeps the stat-limit result grammatical alongside the longest stat label.", "dynamic_layout_24"),
    "MAIN:0x0303D6": r(" won't fall!", "Keeps the stat-limit result grammatical alongside the longest stat label.", "dynamic_layout_24"),
    "MAIN:0x03045F": r(
        "The move ",
        "Starts a complete passive sentence with the forgotten move on row one; the verb is rendered alone on row two.",
        "dynamic_layout_25",
    ),
    "MAIN:0x030485": r(
        "was forgotten!",
        "Completes the forgotten-move sentence on the engine-provided second row instead of leaving an orphan exclamation mark.",
        "dynamic_layout_25",
    ),
    "MAIN:0x03049A": r(
        "Learned move:",
        "Introduces the newly learned move as a complete standalone result before the engine renders its name on row two.",
        "dynamic_layout_25",
    ),
    "MAIN:0x0304AB": r(" didn't learn", "Fits Pokémon plus result on row one; the move is rendered separately on row two.", "dynamic_layout_24"),
    "MAIN:0x0304C2": r(" absorbed sunlight!", "Keeps the charging message intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x0304CF": r(" unleashed solar energy!", "Uses the complete solar-release message within exactly 24 cells.", "dynamic_layout_24"),
    "MAIN:0x0304DB": r(" burrowed underground!", "Keeps the underground message intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x0304E7": r(" attacked swiftly!", "Keeps the swift-attack message intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x0304F1": r(" stored up power!", "Keeps the stored-power message intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x0304FB": r(" struck with full force!", "Uses exactly 24 artifact-free cells on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030505": r(" stored up power!", "Applies the same bounded stored-power formula to the duplicate state.", "dynamic_layout_24"),
    "MAIN:0x03050F": r(" struck with full force!", "Applies the same bounded full-force formula to the duplicate state.", "dynamic_layout_24"),
    "MAIN:0x030519": r(" stopped storing power!", "Keeps the release-cancel message intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030523": r(" flew high into the sky!", "Uses exactly 24 artifact-free cells on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x03052D": r(" risked everything!", "Keeps the one-strike risk in a natural compact formula.", "dynamic_layout_24"),
    "MAIN:0x030537": r(" gathered mystical power!", "Keeps the complete charge wording within the fully cleared 25-cell row.", "dynamic_layout_25"),
    "MAIN:0x030541": r(" released mystic power!", "Keeps the release meaning within 22 second-row cells.", "dynamic_layout_24"),
    "MAIN:0x03054B": r(" foresaw an attack!", "Keeps the foresight message intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030555": r(" hit by Future Sight!", "Keeps the named move and result within one second row.", "dynamic_layout_24"),
    "MAIN:0x030575": r(" flew into a rage!", "Keeps the rage message intact on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x0306FE": r("No longer poisoned!", "Keeps the cured-status sentence on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030714": r("No longer paralyzed!", "Keeps the cured-status sentence on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030720": r("No longer burned!", "Keeps the cured-status sentence on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030738": r("No longer frozen!", "Keeps the cured-status sentence on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x030744": r("No longer badly poisoned!", "Keeps the complete severe-poison cure formula within the fully cleared 25-cell row.", "dynamic_layout_25"),
    "MAIN:0x030750": r("No longer afraid!", "Keeps the cured-flinch sentence on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x0306C0": r("'s Accuracy", "Keeps the full stat name now that all 25 interior cells are cleared between messages.", "dynamic_layout_25"),
    "MAIN:0x03026D": r("No! There's no running\nfrom a Trainer battle!", "Keeps the complete Gen I Trainer-battle escape formula across two bounded rows.", "dynamic_layout_24"),
    "MAIN:0x030290": r("No! That would be\nstealing!", "Keeps the complete Gen I stealing warning across two bounded rows.", "dynamic_layout_24"),
    "MAIN:0x0302CF": r("It's not very effective!", "Uses the canonical effectiveness formula in exactly 24 artifact-free cells.", "dynamic_layout_24"),
    "MAIN:0x03650D": r(" is fully paralyzed!", "Keeps the full-paralysis/no-action result grammatical on the engine-provided second row.", "dynamic_layout_24"),
    "MAIN:0x035F15": r(" is paralyzed!", "Restores the separator used when the already-affected branch joins its status prefix to this payload.", "dynamic_layout_24"),
    "MAIN:0x03043F": r("It knows four moves!", "Keeps the full move-slot warning natural within one artifact-free row.", "dynamic_layout_24"),
    "MAIN:0x030479": r("Which move should be\nforgotten?", "Keeps the complete move-forgetting prompt across two bounded rows.", "dynamic_layout_24"),
    "MAIN:0x030417": r("Congrats! ", "Keeps the evolution result plus a ten-cell Pokémon name within the first physical row.", "dynamic_layout_24"),
    "MAIN:0x035F75": r(
        " wants to learn",
        "Restores the leading join after the Pokémon name; the move itself is rendered on the engine-provided second row.",
        "dynamic_layout_25",
    ),
    "MAIN:0x035FAE": r(
        "Give up on\nlearning ",
        "Splits the complete learning-cancel question at a word boundary so its move name and final question mark remain inside the two-row battle window.",
        "dynamic_layout_25",
    ),
    "MAIN:0x03068E": r("Status unchanged!", "Gives the already-affected branch a complete standalone result before its dedicated routine return.", "dynamic_layout_24"),
    "MAIN:0x0307B9": r("\nCan't be poisoned!", "Moves the poison-immunity result to row two after the Pokémon name.", "dynamic_layout_24"),
    "MAIN:0x0307C4": r("\nCan't be burned!", "Moves the burn-immunity result to row two after the Pokémon name.", "dynamic_layout_24"),
    "MAIN:0x0307CF": r("\nCan't be frozen!", "Moves the freeze-immunity result to row two after the Pokémon name.", "dynamic_layout_24"),
    "MAIN:0x035FB6": r("Enemy is about to use\n", "Places the upcoming Pokémon name alone on the second row.", "dynamic_layout_24"),
    "MAIN:0x030782": r("Cascade Badge", "Uses the official Badge name for the blue/Cut requirement."),
    "MAIN:0x03078C": r("Thunder Badge", "Uses the official Badge name for the orange requirement."),
    "MAIN:0x030796": r("Soul Badge", "Uses the official Badge name for the pink/Surf requirement."),
    "MAIN:0x0307A0": r("Rainbow Badge", "Retains the official Rainbow Badge name."),
    "MAIN:0x0307AA": r("Boulder Badge", "Uses the official Badge name for the gray/Flash requirement."),
    "MAIN:0x030919": r("No Pokédex!", "Replaces a noun-fragment error with a compact natural system message."),
    # The Bag list reserves eight cells for the item name and writes the
    # two-digit quantity immediately afterwards.  Seven-cell labels leave a
    # real separator before that quantity; longer official names are kept in
    # acquisition dialogue, but must be unambiguously abbreviated here.
    "MAIN:0x030F83": r("MystTkt", "Abbreviates Mystic Ticket for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x030F8E": r("LeafSt.", "Abbreviates Leaf Stone for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0316EE": r("Great B", "Abbreviates Great Ball for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0316F7": r("Ultra B", "Abbreviates Ultra Ball for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031700": r("MasterB", "Abbreviates Master Ball for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031710": r("Sup.Pot", "Abbreviates Super Potion for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031719": r("Hyp.Pot", "Abbreviates Hyper Potion for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031722": r("Max.Pot", "Abbreviates Max Potion for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031737": r("PARHeal", "Uses the Gen I PAR abbreviation in the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x03173E": r("Awaken.", "Abbreviates Awakening for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031746": r("IceHeal", "Compacts Ice Heal for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x03174F": r("BurnHl.", "Abbreviates Burn Heal for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031758": r("FullHl.", "Abbreviates Full Heal for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x03176F": r("MaxEth.", "Abbreviates Max Ether for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031779": r("RareCdy", "Abbreviates Rare Candy for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031782": r("FireSt.", "Abbreviates Fire Stone for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x03178B": r("WatrSt.", "Abbreviates Water Stone for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031794": r("ThunSt.", "Abbreviates Thunder Stone for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x03179D": r("MoonSt.", "Abbreviates Moon Stone for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0317A6": r("Parcel", "Uses the unambiguous key noun for Oak's Parcel in the Bag list.", "fixed_item_name_7"),
    "MAIN:0x0317B5": r("TownMap", "Compacts Town Map for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0317B9": r("HelixFs", "Abbreviates Helix Fossil for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0317C4": r("DomeFos", "Abbreviates Dome Fossil for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0317CF": r("S.S.Tkt", "Abbreviates S.S. Ticket for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0317DA": r("FreshWt", "Abbreviates the official Fresh Water name for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0317E3": r("SilphSc", "Abbreviates Silph Scope for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0317EE": r("PokéFlt", "Abbreviates Poké Flute for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x0317F8": r("GoldTth", "Abbreviates Gold Teeth for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x03181D": r("STR HM", "Uses the standard STR abbreviation in the Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031824": r("FlashHM", "Compacts Flash HM for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x035F34": r("PokéB.", "Abbreviates Poké Ball for the seven-cell Bag-list field.", "fixed_item_name_7"),
    "MAIN:0x031C47": r("Juggler", "Matches the official Gen I trainer class used in the same live dialogues."),
    "MAIN:0x031FE6": r("Blackbelt", "Uses the official English Gen I trainer-class name rather than the Japanese loanword Karateka."),
    # Item descriptions use three fixed seven-cell rows (21 cells total).
    "MAIN:0x031A15": r(
        "Catch  Pokémon",
        "Fits the 7x3 item-description grid as 'Catch' / 'Pokémon' without truncation.",
        "fixed_grid_7x3",
    ),
    "MAIN:0x031A24": r("Always catches", "Fits the fixed 7x3 item-description grid and preserves guaranteed capture.", "fixed_grid_7x3"),
    "MAIN:0x031A37": r("Evolvessome   Pokémon", "Fits the fixed 7x3 grid as 'Evolves' / 'some' / 'Pokémon'.", "fixed_grid_7x3"),
    "MAIN:0x031A4A": r("Evolvessome   Pokémon", "Fits the fixed 7x3 grid as 'Evolves' / 'some' / 'Pokémon'.", "fixed_grid_7x3"),
    "MAIN:0x031A5D": r("Restore20 HP", "Fits the fixed 7x3 item-description grid and preserves the exact recovery amount.", "fixed_grid_7x3"),
    "MAIN:0x031A78": r("Restore50 HP", "Fits the fixed 7x3 item-description grid and preserves the exact recovery amount.", "fixed_grid_7x3"),
    "MAIN:0x031A86": r("Restore200 HP", "Fits the fixed 7x3 item-description grid and preserves the exact recovery amount.", "fixed_grid_7x3"),
    "MAIN:0x031A95": r("RestoreAll HP", "Fits the fixed 7x3 item-description grid and preserves full HP recovery.", "fixed_grid_7x3"),
    "MAIN:0x031AA4": r("Cures  poison", "Fits the fixed 7x3 item-description grid and preserves the cured status.", "fixed_grid_7x3"),
    "MAIN:0x031AB2": r("Cures  PAR", "Fits the fixed 7x3 grid; PAR is the official Gen I battle abbreviation.", "fixed_grid_7x3"),
    "MAIN:0x031AC1": r("Cures  sleep", "Fits the fixed 7x3 item-description grid and preserves the awakening effect.", "fixed_grid_7x3"),
    "MAIN:0x031ACE": r("Cures  freeze", "Fits the fixed 7x3 item-description grid and preserves the cured status.", "fixed_grid_7x3"),
    "MAIN:0x031ADC": r("Cures  burns", "Fits the fixed 7x3 item-description grid and preserves the cured status.", "fixed_grid_7x3"),
    "MAIN:0x031AE8": r("Cures  all    status", "Fits the fixed 7x3 grid as 'Cures' / 'all' / 'status'.", "fixed_grid_7x3"),
    "MAIN:0x031AFF": r("Revive half HP", "Fits the fixed 7x3 item-description grid and preserves half-HP revival.", "fixed_grid_7x3"),
    "MAIN:0x031B0E": r("Restore10 PP", "Fits the fixed 7x3 item-description grid and preserves the exact PP recovery.", "fixed_grid_7x3"),
    "MAIN:0x031B29": r("RestoreAll PP", "Fits the fixed 7x3 item-description grid and preserves full PP recovery.", "fixed_grid_7x3"),
    "MAIN:0x031B42": r("Raises level 1", "Fits the fixed 7x3 item-description grid and preserves the one-level increase.", "fixed_grid_7x3"),
    "MAIN:0x031B54": r("Evolvessome   Pokémon", "Fits the fixed 7x3 grid as 'Evolves' / 'some' / 'Pokémon'.", "fixed_grid_7x3"),
    "MAIN:0x031B67": r("Evolvessome   Pokémon", "Fits the fixed 7x3 grid as 'Evolves' / 'some' / 'Pokémon'.", "fixed_grid_7x3"),
    "MAIN:0x031B7A": r("Evolvessome   Pokémon", "Fits the fixed 7x3 grid as 'Evolves' / 'some' / 'Pokémon'.", "fixed_grid_7x3"),
    "MAIN:0x031B8D": r("View   Pokémondata", "Fits the fixed 7x3 grid as 'View' / 'Pokémon' / 'data'.", "fixed_grid_7x3"),
    "MAIN:0x031BA0": r("Gary's map", "Fits the fixed 7x3 item-description grid and preserves the source owner.", "fixed_grid_7x3"),
    "MAIN:0x031BAB": r("Oak's  parcel", "Fits the fixed 7x3 item-description grid and preserves the parcel owner.", "fixed_grid_7x3"),
    "MAIN:0x031BBC": r("AncientPokémonfossil", "Fits the fixed 7x3 grid as 'Ancient' / 'Pokémon' / 'fossil'.", "fixed_grid_7x3"),
    "MAIN:0x031BCA": r("Titanicticket", "Fits the fixed 7x3 grid as 'Titanic' / 'ticket' and preserves the NJ046 ship name.", "fixed_grid_7x3"),
    "MAIN:0x031BE0": r("Lucky  memento", "Fits the fixed 7x3 item-description grid and preserves the lucky-customer memento.", "fixed_grid_7x3"),
    "MAIN:0x031BE8": r("Reveal ghosts", "Fits the fixed 7x3 item-description grid and preserves the supernatural-vision function.", "fixed_grid_7x3"),
    "MAIN:0x031BFD": r("Wakes  Pokémon", "Fits the fixed 7x3 item-description grid and preserves the Poké Flute effect.", "fixed_grid_7x3"),
    "MAIN:0x031C13": r("Gold   Teeth", "Fits the fixed 7x3 item-description grid and preserves the key item's identity.", "fixed_grid_7x3"),
    "MAIN:0x031C27": r("Mew    ticket", "Fits the fixed 7x3 item-description grid and preserves the NJ046 Mew-voyage ticket.", "fixed_grid_7x3"),
    # Dialogue grammar, fidelity, and naturalization.
    "MAIN:0x0333FF": r("BLACK BELT: You've done well, but this is as far as you go!", "Restores the contrast and a complete idiomatic threat."),
    "MAIN:0x033583": r("LORELEI: Welcome to the League! I'm Lorelei of the Elite Four, an Ice-type master! I fear nothing. Anger me and I'll freeze your Pokémon solid! Hahaha! Ready?", "Replaces the unidiomatic title 'Ice Elite Four' while retaining every Chinese-source fact."),
    "MAIN:0x03365E": r("BRUNO: I'm Bruno, the Elite Four's Ground-type master! Training makes people and Pokémon stronger. My team and I live by it! Ash, face our power!", "Recasts the unidiomatic title and keeps the NJ046 Ground-type claim."),
    "MAIN:0x033715": r("AGATHA: I'm Agatha, the Elite Four's Ghost-type master. I hear Oak of Pallet Town is fond of you! He was once strong, but you'd never know it now. A Pokédex isn't enough. Pokémon are for fighting! I'll show you a real battle!", "Repairs the possessive and gives the Oak comparison an explicit subject."),
    "MAIN:0x033861": r("LANCE: I'm Lance, the Elite Four's Dragon-type master! Dragons are sacred legends, hard to catch but supreme when raised well. Common attacks are useless against them! Prepare to lose, Ash!", "Replaces the unidiomatic title without dropping the NJ046 dragon claims."),
    "MAIN:0x0339A9": r("GARY: Ash! A weak rival is no competition! While filling my Pokédex, I found some perfect Pokémon. I'm the world's strongest Trainer!", "Avoids falsely claiming that Gary completed the Pokédex and preserves the source's plural Pokémon."),
    "MAIN:0x033B7F": r("PROF. OAK: Ash! Your victory wasn't yours alone. Your bond with your Pokémon is marvelous! Come with me!", "Repairs the malformed possessive 'Your Pokémon bond'."),
    "MAIN:0x033F45": r("LORELEI: Welcome to the League! I'm Lorelei of the Elite Four, an Ice-type master! I fear nothing. Anger me and I'll freeze your Pokémon solid! Hahaha! Ready?", "Applies the same corrected duplicated Elite Four introduction."),
    "MAIN:0x033FFF": r("BRUNO: I'm Bruno, the Elite Four's Ground-type master! Training makes people and Pokémon stronger. My team and I live by it! Ash, face our power!", "Applies the same corrected duplicated Elite Four introduction."),
    "MAIN:0x0340C1": r("AGATHA: I'm Agatha, the Elite Four's Ghost-type master. I hear Oak of Pallet Town is fond of you! He was once strong, but you'd never know it now. A Pokédex isn't enough. Pokémon are for fighting! I'll show you a real battle!", "Applies the same corrected duplicated Elite Four introduction."),
    "MAIN:0x034169": r("LANCE: I'm Lance, the Elite Four's Dragon-type master! Dragons are sacred legends, hard to catch but supreme when raised well. Common attacks are useless against them! Prepare to lose, Ash!", "Applies the same corrected duplicated Elite Four introduction."),
    "MAIN:0x0345E4": r("MOM: I heard you'll challenge Kameiyu at Nanjing Tech's Celadon development office. They say his Pokémon are undefeated. Be careful...", "Replaces the unidiomatic 'His team is said unbeaten' and preserves the creator-cameo provenance."),
    "MAIN:0x0348B5": r("XIAO LI: Bother me again and I'll call the police!", "Removes the nonstandard ellipsis-plus-exclamation ending."),
    "MAIN:0x0349E5": r("Got Ether!", "The executable item slot and 10-PP description identify Ether, not PP Up.", "executable_context"),
    "MAIN:0x0349F2": r("Got Max Ether!", "The executable item slot and full-PP description identify Max Ether, not PP Max.", "executable_context"),
    "MAIN:0x034DE5": r("I've never seen this Gym's Leader.", "Removes an unsupported claim that the Gym is always closed and translates the Chinese line directly."),
    "MAIN:0x035ADA": r("I'm in love! I'm so happy... Shh!", "Restores subjects and natural clause order to the compressed confession."),
    "MAIN:0x035AF8": r("The sea is vast! With Surf, you can cross it.", "Restores the player as subject and the field move as the means of crossing."),
    "MAIN:0x035B25": r("Have you heard? Rich Trainers sail aboard the Titanic from Vermilion Port!", "Replaces the telegraphic hearsay fragment and preserves ship, port, and passengers."),
    "MAIN:0x035B58": r("Clefairy sometimes visit Mt. Moon at night.", "Uses natural frequency and time expressions."),
    "MAIN:0x035B7C": r("Have you heard of Hoenn? I trained there when I was young.", "Replaces both clipped clauses with natural English."),
    "MAIN:0x035BAB": r("Low on HP? Use a Potion!", "Restores the preposition and official item formula."),
    "MAIN:0x035BCF": r("I'm not good at caring for Pokémon. I need to learn!", "Restores both omitted subjects in natural clauses."),
    "MAIN:0x035BF2": r("My Pokémon disobey me. A Badge may help!", "Supplies the explicit subject and object in the disobedience clause."),
    "MAIN:0x035C0B": r("The Elite Four at Indigo Plateau are the region's best.", "Replaces a colon-fragment with a grammatical statement."),
    "MAIN:0x035C48": r("I wish mine obeyed like yours!", "Restores the omitted subject."),
    "MAIN:0x035C67": r("I'm thirsty... Does anyone have water?", "Restores the speaker and natural question from the Chinese source."),
    "MAIN:0x035C87": r("Don't move! I said, don't move!", "Restores the repeated warning instead of the unidiomatic 'Why move?'."),
    "MAIN:0x035C9D": r("You look like a top Trainer!", "Turns a compressed noun phrase into a complete sentence."),
    "MAIN:0x035CC1": r("Odd! No one rides bikes anymore!", "Restores the source subject and time sense."),
    "MAIN:0x035D0E": r("You sense a mysterious power...", "Uses the natural adjective and source verb."),
    "MAIN:0x035D2F": r("It's a coded lock...", "Restores the missing subject and verb."),
    "MAIN:0x035D42": r("Got a password!", "Restores the natural acquisition article."),
    "MAIN:0x035D65": r("Return when you have all the Badges!", "Replaces a telegraphic imperative fragment with the complete gate instruction."),
    "MAIN:0x035DAC": r("Sorry, not enough money!", "Uses the standard natural shop failure message."),
    "MAIN:0x036528": r("Science is amazing! PCs can transfer Pokémon and items!", "Restores a complete natural version of the science NPC line."),
    "MAIN:0x0365FE": r("MOM: How about a rest?", "Translates the source question instead of reducing it to an order."),
    "MAIN:0x036665": r("You and your Pokémon look great! Take care!", "Restores both subjects and a natural farewell."),
    "MAIN:0x0366A8": r("GARY'S SIS: Grandpa has a task for you!", "Restores a finite verb without changing the source fact."),
    "MAIN:0x0368BC": r("Diglett dug this tunnel all the way to Pewter!", "Replaces the semicolon fragment with a complete source-faithful sentence."),
    "MAIN:0x03692B": r("We study Pokémon here every day.", "Restores the omitted subject and natural adverb placement."),
    "MAIN:0x037ADC": r("KAMEIYU: Ash, I knew you'd come! Let's battle with no regrets. Ready?", "Restores the missing subject and natural invitation in the creator-cameo battle."),
    "MAIN:0x03806F": r("Pokémon System online...", "Uses a natural computer status label."),
    "MAIN:0x038080": r("Pokémon System offline...", "Uses a natural status label and removes contradictory punctuation."),
    "MAIN:0x0380EE": r("SURGE: I lost! Take the Thunder Badge and this gift!", "Restores the verbs and official Badge name in the reward sentence."),
    "MAIN:0x038149": r("Sorry, battles aren't available here yet...", "Replaces the unidiomatic phrase 'system can't battle'."),
    "MAIN:0x038173": r("The trade machine is broken too. Try again later.", "Restores the missing article and auxiliary verb."),
    "MAIN:0x038230": r("This tree can be cut down!", "Uses the official Gen I field-action wording instead of 'cuttable'."),
    "MAIN:0x038715": r("OAK: I just caught this one. It isn't tame yet.", "Replaces two compressed fragments with complete sentences."),
    "MAIN:0x0387F3": r("CLERK: You're from Pallet Town, right? You know Prof. Oak? Please deliver this order to him.", "Restores every source question and the delivery request in natural English."),
    "MAIN:0x038862": r("OLD MAN: Wait! Hear me out.", "Uses the idiomatic request."),
    "MAIN:0x038891": r("SOLDIER: Come in.", "Replaces the unnatural one-word command 'Enter'."),
    "MAIN:0x0388BD": r("OAK: Ash, you two get along! You have the makings of a Trainer!", "Restores the source's assessment in idiomatic English."),
    "MAIN:0x038916": r("ASH delivered Oak's parcel!", "Uses the official-style delivery formula and natural possessive item name."),
    "MAIN:0x038945": r("OAK: My custom Poké Ball! Thanks. I have a favor to ask...", "Makes the final request explicit and grammatical."),
    "MAIN:0x03898D": r("OAK: I dream of a full Pokédex, but I'm too old. I want you two to finish it and make Pokémon history! Now go!", "Uses complete clauses while preserving every source beat."),
    "MAIN:0x0389B4": r("GARY: Leave it to me, Gramps! I don't need your help, Ash! I'll borrow Sis's map and tell her not to lend you one! Ha! Your trip is pointless!", "Uses the official-scene voice while preserving Gary's taunt, map plan, and source-only final insult."),
    "MAIN:0x038AA1": r("OLD MAN: I was out of it last time; my head was pounding... What? I blocked your way? You're filling your Pokédex? Buy Poké Balls at the nearby shop.", "Restores subjects and every step of the source's explanation and advice."),
    "MAIN:0x038C50": r("BUG CATCHER: Want to reach the top? Beat me!", "Replaces the clipped phrase 'Want top?'."),
    "MAIN:0x038CA8": r("BUG CATCHER: You're a Trainer too? Let's battle!", "Restores the source's shared Trainer identity and natural invitation."),
    "MAIN:0x038CD8": r("BUG CATCHER: Don't run away! Fight me!", "Uses a natural imperative and explicit object."),
    "MAIN:0x038E86": r("BROCK: I'm Pewter's Gym Leader! My rock-hard team is mostly Rock-type. Every Trainer fights, even when defeat seems certain! Come on!", "Restores Brock's self-identification and recasts his creed in natural English."),
    "MAIN:0x038F91": r("Got TM35!", "The executable TM table and following Harden explanation prove the Chinese receipt's 34 is a typo.", "executable_context"),
    "MAIN:0x0390EE": r("BUG CATCHER: Pokémon here differ from those in the forest!", "Repairs the malformed comparison 'unlike the forest's'."),
    "MAIN:0x039121": r("YOUNGSTER: Catch more than six Pokémon, and the rest go to the PC.", "Replaces a semicolon fragment with the complete storage rule."),
    "MAIN:0x0391D2": r("BUG CATCHER: Battle me with your latest catch!", "Replaces an unidiomatic versus fragment."),
    "MAIN:0x039303": r("BUG CATCHER: A shady man is prowling the cave. Are you that man?", "Restores the source's suspicion without using an invalid pronoun complement."),
    "MAIN:0x039359": r("LASS: I'm waiting for friends who got separated in the cave.", "Restores the omitted subject and relation."),
    "MAIN:0x039385": r("LASS: I came because I heard there are rare fossils here.", "Restores the causal clause and natural fossil description."),
    "MAIN:0x0395E5": r("SCIENTIST: I hear the Pokémon Lab on far-off Cinnabar revives fossils.", "Replaces a headline fragment with a natural hearsay sentence."),
    "MAIN:0x0399DC": r("GARY: Ash! Still struggling? I caught some great, powerful Pokémon. What did you catch? Show me!", "Clarifies the questions and keeps Gary's source-faithful boast."),
    "MAIN:0x039A24": r("GARY: Bill showed me rare Pokémon and added several pages to my Pokédex. He's a famous collector who built PC Storage. If you use it, thank him!", "Restores articles, subject links, and the conditional thanks."),
    "MAIN:0x039D84": r("YOUNGSTER: Dad and I went to a party on the Titanic at Vermilion Port! Jealous?", "Uses the source's party rather than adding a dance."),
    "MAIN:0x039D3B": r("LASS: Respect!", "Preserves the orphaned catalogue cell byte-for-byte; the exact live restored owner is classified separately.", "shadowed_nonlive"),
    "MAIN:0x039FFF": r("TEAM ROCKET: Hey! Don't trespass in someone's garden! Me? I'm just passing through. Nothing suspicious! What? I look suspicious?", "Restores complete defensive clauses in the Rocket encounter."),
    "MAIN:0x03A03C": r("TEAM ROCKET: Spare me! I won't do it again. I'm leaving... Bye!", "Replaces the isolated noun 'Mercy' with the natural plea."),
    "MAIN:0x03A058": r("GUARD: I'm on duty, and I'm thirsty! You can't pass right now!", "Uses complete natural clauses for the guard's status and current ban."),
    "MAIN:0x03A0D2": r("SCOUT: You taught me a lesson!", "Expresses the source reversal as a natural post-defeat line."),
    "MAIN:0x03A109": r("BUG CATCHER: I caught a great Pokémon. Want to battle?", "Restores the omitted subject and uses a natural invitation."),
    "MAIN:0x03A127": r("BUG CATCHER: I need more training...", "Restores the omitted subject."),
    "MAIN:0x03A14B": r("GIRL: What are you looking at?", "Uses the idiomatic English challenge."),
    "MAIN:0x03A169": r("GIRL: It was a misunderstanding.", "Turns a noun fragment into a sentence."),
    "MAIN:0x03A195": r("SCOUT: Now I'm even madder...", "Restores the omitted subject and comparison."),
    "MAIN:0x03A1FA": r("GENTLEMAN: I'm from Hoenn.", "Restores the omitted subject and full speaker class."),
    "MAIN:0x03A296": r("GENTLEMAN: It's nice to be in Hoenn.", "Replaces the unnatural phrase 'nice to reach'."),
    "MAIN:0x03A2B7": r("GENTLEMAN: Have you heard the legends of Johto?", "Restores the natural question and source noun."),
    "MAIN:0x03A388": r("SAILOR: I see. You're a great Trainer!", "Restores the missing copula and subject."),
    "MAIN:0x03A394": r("SAILOR: I work hard every day.", "Uses natural adverb placement."),
    "MAIN:0x03A433": r("BIG GUY: I'm on a diet!", "Restores the omitted subject."),
    "MAIN:0x03A44D": r("BIG GUY: But I got fat again!", "Restores the subject and source contrast."),
    "MAIN:0x03A504": r("CAPTAIN: Ugh... I'm seasick... I feel awful.", "Uses the official S.S. Anne role and a complete seasickness complaint."),
    "MAIN:0x03A517": r("CAPTAIN: I'm feeling much better. Thank you! You want to see my Cut technique? I could show you if I were well... Take this instead! Teach it to a Pokémon, and you can use Cut anytime!", "Uses the official S.S. Anne role and complete, source-faithful HM explanation."),
    "MAIN:0x03A525": r("SAILOR: The ship has left.", "Restores the missing article and auxiliary."),
    "MAIN:0x03A6AC": r("GENTLEMAN: Lt. Surge is a soldier. Do you want to enlist too?", "Restores the complete question."),
    "MAIN:0x03A6CC": r("SOLDIER: Can you get past me?", "Restores the idiomatic phrasal verb."),
    "MAIN:0x03A7D8": r("GENTLEMAN: I'm too old to walk far.", "Restores the omitted subject and source extent."),
    "MAIN:0x03A7F4": r("SAILOR: Kid, don't wander around!", "Uses the natural phrasal verb."),
    "MAIN:0x03A807": r("SAILOR: My mistake. Look around all you like.", "Replaces the unidiomatic command 'Tour freely'."),
    "MAIN:0x03A821": r("JENNY: Thunder Badge? You may be strong! I caught a Squirtle that caused trouble. Want it?", "Clarifies which Squirtle caused the mischief and the adoption offer."),
    "MAIN:0x03A88A": r("Oh... Who will adopt Squirtle?", "Restores the auxiliary and natural future question."),
    "MAIN:0x03A8D2": r("SAILOR: Did I say something?", "Restores the omitted subject and auxiliary."),
    "MAIN:0x03A957": r("YOUNGSTER: Why bother me while I'm resting?", "Matches the source's interrupted rest rather than assuming sleep."),
    "MAIN:0x03A971": r("TWINS: Is there something on our faces?", "Restores the existential construction."),
    "MAIN:0x03A9FC": r("YOUNGSTER: Why are you so rude?", "Restores the complete question."),
    "MAIN:0x03AA16": r("YOUNGSTER: Fine. No hard feelings.", "Uses an idiomatic no-grudge expression."),
    "MAIN:0x03AB01": r("YOUNGSTER: My stomach hurts. You're off the hook today.", "Replaces the clipped gut fragment with a natural excuse."),
    "MAIN:0x03AB27": r("OLD MAN: They say Diglett dug this tunnel, maybe all the way to Viridian.", "Restores the hearsay frame and destination."),
    "MAIN:0x03ABAC": r("GIRL: You're quite handsome!", "Restores the omitted subject and copula."),
    "MAIN:0x03ABDC": r("YOUNGSTER: Let's make a deal. Give me your Pikachu!", "Replaces two fragments with the explicit source proposal."),
    "MAIN:0x03AC24": r("BUG CATCHER: I didn't expect to see you again!", "Restores the omitted subject and surprise relation."),
    "MAIN:0x03AC37": r("BUG CATCHER: You've gotten even stronger!", "Restores the subject and comparison."),
    "MAIN:0x03AC84": r("MAN: That's it for me this time...", "Uses a natural post-defeat admission."),
    "MAIN:0x03AC97": r("YOUNGSTER: You've been warned. Run!", "Turns a label-like fragment into an idiomatic warning."),
    "MAIN:0x03ACCD": r("YOUNGSTER: Try all you like; you're no match!", "Replaces an ungrammatical semicolon compression."),
    "MAIN:0x03AD29": r("GIRL: Let me get a look at you.", "Uses the idiomatic form of the source request."),
    "MAIN:0x03AD9E": r("STAFF: I have to find it.", "Restores the omitted subject."),
    "MAIN:0x03ADB0": r("STAFF: I'm not afraid of the dark.", "Uses the idiomatic English expression."),
    "MAIN:0x03ADF0": r("GIRL: Will you protect me?", "Restores the auxiliary question."),
    "MAIN:0x03AE18": r("MAN: Sorry. It's none of my business.", "Uses the idiomatic expression for the source retraction."),
    "MAIN:0x03AE24": r("STAFF: I do boring work all day.", "Restores the subject and verb."),
    "MAIN:0x03B058": r("STAFF: Tomorrow will be easier, right?", "Restores the complete tag question."),
    "MAIN:0x03B0BB": r("GIRL: I'm looking for a boyfriend.", "Restores the omitted subject and verb."),
    "MAIN:0x03B0FB": r("MAN: Pokémon evolve as they level up!", "Uses official natural level-up terminology."),
    "MAIN:0x03B21F": r("BOY: It was a mistake. Sorry.", "Turns the noun fragment into a sentence."),
    "MAIN:0x03B244": r("MAN: Careful! If it caves in, we're done for!", "Uses a natural conditional rather than the noun 'cave-in' as agent."),
    "MAIN:0x03B2C2": r("GIRL: I won't do it again...", "Restores the omitted subject."),
    "MAIN:0x03B3C2": r("NUN: Pokémon Tower was built to soothe the spirits of dead Pokémon.", "Turns a colon-fragment into a complete source-faithful sentence."),
    "MAIN:0x03B3EB": r("GIRL: I heard a Legendary Pokémon was seen nearby, so I came too.", "Restores the omitted subject and uses natural sighting language."),
    "MAIN:0x03B44A": r("GIRL: I can't forget my dead Clefairy... Oh no, I'm crying again...", "Restores the source's renewed crying as a natural reaction."),
    "MAIN:0x03B47A": r("GIRL: Are you here to mourn too? You really care about Pokémon!", "Replaces two clipped fragments with complete clauses."),
    "MAIN:0x03B5E8": r("BOY: Do you know how terrifying poison is?", "Restores the complete idiomatic question."),
    "MAIN:0x03B687": r("LASS: Even ordinary Pokémon can be extraordinary!", "Preserves the source wordplay in natural English."),
    "MAIN:0x03B6B3": r("LASS: A plain Trainer like you must train plain Pokémon!", "Repairs the malformed vocative while preserving the insult."),
    "MAIN:0x03B6D9": r("STAFF: Today's not my day.", "Uses an idiomatic unlucky-day expression."),
    "MAIN:0x03B739": r("ELDER: Look how energetic I am!", "Uses a natural rendering of the vigor boast."),
    "MAIN:0x03B754": r("STAFF: I can't stand my Grimer army!", "Restores the omitted subject."),
    "MAIN:0x03B77E": r("ELDER: Nothing is more beautiful than fire.", "Restores the superlative as a complete sentence."),
    "MAIN:0x03B7B5": r("LASS: You weren't hypnotized?", "Restores the omitted subject."),
    "MAIN:0x03B7F5": r("GIRL: I saw Team Rocket kill Cubone's mother as she fled!", "Restores the witness subject and the mother's flight."),
    "MAIN:0x03B835": r("GIRL: Hey! Only girls are allowed in here!", "Restores the complete access rule."),
    "MAIN:0x03B8D8": r("GIRL: You weren't peeking? Many people like you come here!", "Restores subjects in both clauses."),
    "MAIN:0x03B8F9": r("LASS: Don't bring Bug- or Fire-type Pokémon here!", "Uses grammatical compound type modifiers."),
    "MAIN:0x03B968": r("WOMAN: What's your hobby?", "Translates the source question precisely."),
    "MAIN:0x03B97A": r("WOMAN: I have a blind date next week...", "Restores the omitted subject and verb."),
    "MAIN:0x03BA87": r("MAN: The Poké Flute makes a special sound people can't hear. It wakes sleeping Pokémon.", "Splits an overloaded semicolon into two natural source-faithful sentences."),
    "MAIN:0x03BAB6": r("BEIBEI: I know everything, even the world inside games! This Eevee is yours!", "Replaces the unidiomatic 'I know all' while preserving the creator cameo."),
    "MAIN:0x03BC7A": r("ROCKET: If you've got the nerve, go find our Boss!", "Restores the conditional clause."),
    "MAIN:0x03BD1A": r("KAMEIYU: I wrote the script... Pikachu is cute, right?", "Uses a complete creator-credit sentence."),
    "MAIN:0x03BD3F": r("WEI CUNFU: I'm the programmer. Nice to meet you!", "Replaces the vague greeting with the source's polite introduction."),
    "MAIN:0x03BDB1": r("NUN: What did I do? Sorry! I was possessed by an evil force...", "Replaces a semicolon fragment with a natural possession statement."),
    "MAIN:0x03BDE2": r("GIOVANNI: Ha! You made it here! This is Team Rocket HQ, where we trade Pokémon worldwide. I'm Boss Giovanni! Resist me, and you'll suffer!", "Restores complete clauses in Giovanni's NJ046-specific headquarters speech."),
    "MAIN:0x03BE5E": r("JAMES: How dare you come here and cause trouble again!", "Removes an unsupported Boss-meeting claim and translates the Chinese Rocket threat."),
    "MAIN:0x03BF2D": r("GIOVANNI: I-impossible! You truly love your Pokémon. I can't understand it... I have business to attend to. I'm off! (He vanishes.)", "Repairs clipped clauses while retaining the displayed source stage direction."),
    "MAIN:0x03C008": r("NUN: Give me... your soul!", "Uses natural dramatic word order and punctuation."),
    "MAIN:0x03C15A": r("NUN: I've come to my senses.", "Uses the idiomatic recovery phrase."),
    "MAIN:0x03C1D6": r("Leave! Get out of here!", "Removes an ellipsis after an exclamation and restores the location."),
    "MAIN:0x03C424": r("MR. FUJI: Ash, you'll never finish the Pokédex without loving your Pokémon. This may help!", "Repairs the conditional logic and the gift transition."),
    "MAIN:0x03C54E": r("ROCKET: With Silph, we can sell Pokémon for more!", "Restores the omitted subject and auxiliary."),
    "MAIN:0x03C55B": r("ROCKET: Darn you for getting in my way!", "Replaces an unnatural curse construction with the direct source complaint."),
    "MAIN:0x03C58E": r("ROCKET: I've spotted someone suspicious!", "Turns a label fragment into the source alert."),
    "MAIN:0x03C5E5": r("ROCKET: Impressive! You've made it this far, but reaching the President's office won't be easy!", "Restores the missing article and a natural contrast."),
    "MAIN:0x03C70E": r("ROCKET: I'm a Silph employee and a member of Team Rocket.", "Uses the complete official organization name in a natural reveal."),
    "MAIN:0x03C765": r("GARY: Hahaha! I knew you'd come, Ash! Team Rocket gave you trouble? I don't care! Show me how much stronger you've gotten!", "Repairs the source questions and the ungrammatical final challenge."),
    "MAIN:0x03C861": r("ROCKET: I'm also one of the four Rocket Brothers!", "Restores the definite article."),
    "MAIN:0x03CAFB": r("FISHERMAN: This is a famous fishing spot.", "Replaces the unidiomatic phrase 'Fishing is famous here'."),
    "MAIN:0x03CB0E": r("FISHERMAN: Don't you like fishing?", "Restores the full official trainer-class label and question."),
    "MAIN:0x03CB20": r("FISHERMAN: Many Pokémon swim here too!", "Uses the full official trainer-class label."),
    "MAIN:0x03CB39": r("FISHERMAN: Water-types are the cutest!", "Restores the article and full official trainer-class label."),
    "MAIN:0x03CB64": r("FISHERMAN: Can't you see me fishing?", "Uses the full official trainer-class label."),
    "MAIN:0x03CB80": r("FISHERMAN: Oh well... You scared all the fish away.", "Restores the missing article and idiomatic particle."),
    "MAIN:0x03CB91": r("FISHERMAN: I caught a good one. Want to see?", "Restores the omitted subject and complete question."),
    "MAIN:0x03CBB2": r("FISHERMAN: Water beats Fire!", "Uses the full official trainer-class label."),
    "MAIN:0x03CBF5": r("SCOUT: I don't want anything from you.", "Turns a noun fragment into the complete contextual statement."),
    "MAIN:0x03CC09": r("SCOUT: I'm not suspicious!", "Restores the omitted subject."),
    "MAIN:0x03CC2E": r("GIRL: Get lost, stranger!", "Replaces the unnatural plural imperative with a direct source dismissal."),
    "MAIN:0x03CC54": r("GIRL: Sorry. I mistook you for someone else.", "Explains the source misunderstanding in natural English."),
    "MAIN:0x03CCE8": r("BEAUTY: You're right.", "Restores the omitted subject and copula."),
    "MAIN:0x03CD39": r("GIRL: I was too hard on you.", "Restores the omitted subject and source regret."),
    "MAIN:0x03CD4C": r("BIRD KEEPER: I specialize in bird Pokémon.", "Uses a natural statement of the speaker's specialty and full class label."),
    "MAIN:0x03CD9C": r("BIRD KEEPER: I have nothing to say.", "Restores the omitted subject and verb."),
    "MAIN:0x03CDBD": r("BIKER: I shouldn't have pushed you.", "Restores the omitted subject and idiomatic verb."),
    "MAIN:0x03CDFD": r("BIRD KEEPER: Have you been to the Safari Zone?", "Restores the auxiliary and article."),
    "MAIN:0x03CE16": r("BIRD KEEPER: There are many rare Pokémon there...", "Restores the existential construction."),
    "MAIN:0x03D0A7": r("BEAUTY: Don't go! Stay and chat with me.", "Restores both complete imperatives."),
    "MAIN:0x03D0D3": r("BIKER: I like strong people!", "Uses natural English for the source preference."),
    "MAIN:0x03D0FB": r("BIRD KEEPER: Well? Nice, isn't it?", "Repairs the malformed tag punctuation."),
    "MAIN:0x03D16B": r("BIRD KEEPER: My attack barrage leaves you no chance!", "Restores the missing object."),
    "MAIN:0x03D191": r("BIRD KEEPER: I boasted again...", "Restores the omitted subject."),
    "MAIN:0x03D1AF": r("BIKER: You look like trouble!", "Uses an idiomatic rendering of the source suspicion."),
    "MAIN:0x03D20F": r("BIRD KEEPER: You've seen my power. Now get lost!", "Restores tense and sequence."),
    "MAIN:0x03D25A": r("BIRD KEEPER: I raise bird Pokémon for a living.", "Restores the subject and expresses the profession naturally."),
    "MAIN:0x03D276": r("BIRD KEEPER: I'm entering the Pokémon League this year!", "Restores the subject and article."),
    "MAIN:0x03D2EE": r("NINJA: Your ninjutsu is impressive!", "Turns a noun phrase into a complete compliment."),
    "MAIN:0x03D2FD": r("NINJA: Strength alone fails! Technique matters most!", "Replaces the unidiomatic phrase 'Technique is best'."),
    "MAIN:0x03D39A": r("NINJA: I haven't fought this seriously in ages.", "Restores the subject, verb, and natural time expression."),
    "MAIN:0x03D3B7": r("NINJA: Let's see if you can get past me!", "Uses the idiomatic challenge."),
    "MAIN:0x03D406": r("NINJA: You truly are strong.", "Restores the omitted subject and copula."),
    "MAIN:0x03D4EF": r("I see. Come again!", "Uses a natural Safari refusal farewell."),
    "MAIN:0x03D58E": r("WARDEN: My Gold Teeth are gone... Did I drop them in the Safari Zone?", "Restores the possessive subject, verb, and article."),
    "MAIN:0x03D667": r("SWIMMER: I haven't seen you around.", "Replaces a noun fragment with a natural recognition line."),
    "MAIN:0x03D683": r("SWIMMER: You're the strongest Trainer I've seen!", "Restores the subject and copula."),
    "MAIN:0x03D692": r("SWIMMER: Stare again and I'll hit you!", "Replaces a semicolon compression with the source conditional and uses the official common Gen I Swimmer class."),
    "MAIN:0x03D6A4": r("SWIMMER: I won't do it again!", "Restores the omitted subject and object and uses the official common Gen I Swimmer class."),
    "MAIN:0x03D700": r("SWIMMER: I was kidding!", "Turns a gerund fragment into a sentence."),
    "MAIN:0x03D7CB": r("PRESIDENT: Thank you, young man! You saved me when I needed help most. I won't forget it. Take this gift!", "Expands the unclear speaker abbreviation and keeps the source gratitude."),
    "MAIN:0x03D8C2": r("BLACK BELT: Our master is a god of combat! Be ready before you face him!", "Restores the missing copula and natural warning while using the official Gen I class; the separately labelled dojo Master remains MASTER."),
    "MAIN:0x03D8FC": r("DEPUTY: I'm the dojo's second-in-command! How dare you challenge us! I won't forgive you. Take this!", "Corrects the source role and uses complete natural challenge clauses."),
    "MAIN:0x03D910": r("DEPUTY: Wait until our Master deals with you!", "Removes an unsupported self-deprecating addition."),
    "MAIN:0x03D933": r("MASTER: I'm this dojo's Master. You'll regret challenging me!", "Restores the source role and threat without adding mercy."),
    "MAIN:0x03DA59": r("PSYCHIC: Saffron once had two Gyms. The dojo next door was defeated...", "Restores the complete history and full speaker class."),
    "MAIN:0x03DABF": r("PSYCHIC: Psychic power is an unseen force!", "Restores the missing article and full speaker class."),
    "MAIN:0x03DB22": r("PSYCHIC: You'll need mighty psychic power to beat Sabrina!", "Restores the source requirement as a grammatical sentence."),
    "MAIN:0x03DB40": r("PSYCHIC: Pokémon take after their Trainers. Did you know?", "Uses a natural idiom for shared character."),
    "MAIN:0x03DBCF": r("PSYCHIC: If you don't want to learn, never mind...", "Restores the source's learning choice rather than changing it to training."),
    "MAIN:0x03DDCC": r("SWIMMER: The sea is the source of all life.", "Restores the article and clear class label."),
    "MAIN:0x03DE25": r("SWIMMER: Go wherever you want. It's none of my concern...", "Replaces two clipped clauses with natural English and uses the official common Gen I Swimmer class."),
    "MAIN:0x03DEBF": r("SWIMMER: Sorry. I know you're busy.", "Restores the source's knowledge clause."),
    "MAIN:0x03DF87": r("DOCTOR: A Helix Fossil from an ancient Omanyte! My machine can revive it. Hand it over!", "Uses a consistent speaker label and grammatical fossil identification."),
    "MAIN:0x03DFC0": r("The machine revived Omanyte!", "Restores the missing article."),
    "MAIN:0x03E005": r("DOCTOR: A Dome Fossil from an ancient Kabuto! My machine can revive it. Hand it over!", "Uses a consistent speaker label and grammatical fossil identification."),
    "MAIN:0x03E03E": r("The machine revived Kabuto!", "Restores the missing article."),
    "MAIN:0x03E0A9": r("SCIENTIST: The volcano destroyed this lab.", "Restores the missing article and uses the natural destruction verb."),
    "MAIN:0x03E0C7": r("SCIENTIST: There should still be rare Pokémon inside...", "Restores the existential construction."),
    "MAIN:0x03E11B": r("SCIENTIST: Feel free to look around.", "Uses the idiomatic invitation."),
    "MAIN:0x03E186": r("THIEF: Oh no! You found me!", "Restores the subject and source discovery."),
    "MAIN:0x03E259": r("SCIENTIST: Fire is the strongest!", "Restores the missing article and full class label."),
    "MAIN:0x03E27A": r("SCIENTIST: I need to do more research...", "Restores the omitted subject and verb."),
    "MAIN:0x03E2C0": r("SCIENTIST: Do you know what Pokémon like?", "Restores the complete question."),
    "MAIN:0x03E347": r("THIEF: I'm a reformed thief.", "Turns two noun fragments into an idiomatic sentence."),
    "MAIN:0x03E376": r("BLAINE: I'm a fiery man and the Leader of Cinnabar Island's Gym! Behold my Fire Pokémon!", "Uses the grammatical official location and restores the article before Blaine's role."),
    "MAIN:0x03E3D0": r("BLAINE: Ha ha! You earned the Volcano Badge. I admit defeat. It boosts every Pokémon's Attack!", "Restores the Badge article and uses natural defeat and effect clauses."),
    "MAIN:0x03E502": r("SWIMMER: Hi! Want to battle?", "Uses a natural invitation and the official common Gen I Swimmer class."),
    "MAIN:0x03E580": r("TAMER: You can't beat the Boss without stamina! BLACK BELT: My rage has peaked!", "Uses complete natural clauses for both speakers and the official Gen I Blackbelt class."),
    "MAIN:0x03E5B4": r("BLACK BELT: I need more training... TAMER: I understand Pokémon best!", "Restores subjects and a natural specialty claim while using the official Gen I class."),
    "MAIN:0x03E612": r("BLACK BELT: I wish I were as strong as the Boss! TAMER: Time to go!", "Uses the grammatical English subjunctive and official Gen I class."),
    "MAIN:0x03E6E9": r("TAMER: Darn! Do you know who I am? BLACK BELT: Strong Trainers win in style!", "Restores the complete natural question and official full class label."),
    "MAIN:0x03E732": r("BLACK BELT: I lost; the Boss will be angry... TAMER: I'm a genius!", "Replaces two clipped fragments with complete clauses and uses the official Gen I class."),
    "MAIN:0x03E82C": r("BEAUTY: Cinnabar's volcano erupts often.", "Corrects the impossible claim that the island itself erupts."),
    "MAIN:0x03E853": r("SCIENTIST: We study Pokémon here every day.", "Restores the subject and natural adverb placement."),
    "MAIN:0x03E8A0": r("GIOVANNI: Ha! You've discovered my hideout. Now that you've found me, I won't hold back! Face the power of Giovanni, the strongest Trainer!", "Restores Giovanni's explicit source name in complete natural challenge clauses."),
    "MAIN:0x03E954": r("GIOVANNI: I lost, though I hate admitting it. Take the promised Earth Badge. You'll be a great Trainer. My Pokémon journey starts anew; I'll disband Team Rocket for now. If fate allows, we'll meet again!", "Repairs articles and the unidiomatic final fate clause."),
    "MAIN:0x03EC21": r("SCIENTIST: Fire loses to Water but beats Ice.", "Turns a comma splice into a grammatical contrast."),
    "MAIN:0x03ECFD": r("GUIDE: Future Champ! Even I don't know Viridian Gym's Leader...", "Uses the established full guide label."),
    "MAIN:0x03F5A3": r("GIRL: Grandpa fell asleep here? We'll have to wait until he wakes up.", "Restores the subject and complete waiting clause."),
    # Additional complete-clause pass after the row-for-row editorial audit.
    "MAIN:0x033CB1": r("MOM: I heard a cave near Cerulean is in turmoil. Even Lorelei of the Elite Four went to investigate...", "Restores the omitted hearsay subject."),
    "MAIN:0x033CF0": r("REFEREE: Sorry. Lorelei's away, so League challenges are paused. It seems she went to Cerulean to investigate trouble...", "Restores the omitted subject and natural passive status."),
    "MAIN:0x033EF8": r("SAILOR: Quite a magical trip, right? Lorelei is back, so Champion challenges are open again!", "Turns the opening noun fragment into a natural question."),
    "MAIN:0x0347A2": r("KAMEIYU: Amazing! You collected every Kanto Pokémon. Take this Mew! Congratulations! You completed the Pokédex!", "Turns the completion fragment into a full congratulatory sentence."),
    "MAIN:0x03675E": r("You memorized the diary entry!", "Uses a complete natural system message."),
    "MAIN:0x037994": r("GARY: What? Is it really over? I gave it everything and still lost! I worked so hard to get here... Why did I lose? I couldn't have raised my Pokémon wrong... Fine. You're the new Pokémon League Champion. I hate to admit it.", "Restores every source beat in natural official-scene English."),
    "MAIN:0x037BEF": r("It's pitch-dark. I wish I knew Flash!", "Restores both omitted subjects."),
    "MAIN:0x038D11": r("GENTLEMAN: You don't want to join...?", "Restores the complete question and full speaker label."),
    "MAIN:0x038D23": r("GUARD: Strong Trainers are ahead. You have no Badge, so I can't let you pass.", "Turns two gate fragments into complete causal clauses."),
    "MAIN:0x038E60": r("SCOUT: You're strong, but Brock is stronger.", "Restores the missing subject and copula."),
    "MAIN:0x0391B2": r("YOUNGSTER: I lost again...", "Turns the repeated verb fragment into a natural defeat line."),
    "MAIN:0x039278": r("LASS: If you don't want to fight, avoid eye contact.", "Restores the source conditional in natural English."),
    "MAIN:0x039334": r("BUG CATCHER: I was fooled! The man I saw was with Team Rocket!", "Restores the speaker and the source's complete identification."),
    "MAIN:0x03949D": r("ROCKET: We're doing important work! Go home, kid!", "Restores the omitted subject and verb."),
    "MAIN:0x039F3F": r("BILL: Thanks! Did you come to see my collection? Take this reward!", "Restores the complete question and gift instruction."),
    "MAIN:0x039F8C": r("BILL: The Titanic has docked at Vermilion Harbor, and many Trainers are aboard. I have a ticket, but I don't like parties. Why don't you go?", "Restores articles, subjects, and the source's invitation."),
    "MAIN:0x039DE5": r("MAN: Want to get past me? Beat me first!", "Completes the challenge's phrasal object."),
    "MAIN:0x03A283": r("YOUNGSTER: I must train more.", "Restores the omitted subject."),
    "MAIN:0x03A324": r("LASS: I love the sea!", "Restores the omitted subject."),
    "MAIN:0x03A3C8": r("SAILOR: Who are you?", "Uses the standard complete question."),
    "MAIN:0x03AD7A": r("STAFF: I admire your courage!", "Turns the adjective fragment into the source's complete compliment."),
    "MAIN:0x03B117": r("MAN: I think Rock Pokémon are the strongest!", "Restores the source opinion frame and article."),
    "MAIN:0x03B144": r("BOY: I just broke up with my girlfriend.", "Restores the omitted subject and idiomatic verb."),
    "MAIN:0x03B267": r("MAN: I'm glad we met.", "Restores the omitted subject and copula."),
    "MAIN:0x03B516": r("GARY: Jerk! I went easy on you, but you didn't hold back! How's your Pokédex? I caught a Cubone, but I haven't found its evolved form, Marowak. It must not be around here, so I'm leaving. Unlike you, I'm busy... See ya!", "Replaces the clipped rival speech with complete clauses while retaining every source beat."),
    "MAIN:0x03B792": r("ELDER: That was too much fire...", "Turns the noun fragment into a natural battle reaction."),
    "MAIN:0x03B870": r("WOMAN: Look at my Pokémon! Grass-types are easy to raise.", "Restores the object and natural type wording."),
    "MAIN:0x03B993": r("ERIKA: What lovely weather! Welcome to Celadon Gym. I'm Erika, and I enjoy flower arranging. Oh! You're here for a battle? How annoying! I won't lose!", "Uses complete official-scene clauses without dropping the source hobby or reaction."),
    "MAIN:0x03B9F1": r("ERIKA: You're very strong! Please take the Rainbow Badge. It lets you use Strength!", "Restores the compliment's subject and a natural award formula."),
    "MAIN:0x03BC31": r("ROCKET: If you oppose Team Rocket, you'll get nowhere!", "Restores the complete source conditional."),
    "MAIN:0x03BFE7": r("NUN: Join me in a curse...", "Uses the natural invitation syntax."),
    "MAIN:0x03C370": r("MR. FUJI: Did you come to rescue me? Thank you... I came to calm the spirit of Marowak, Cubone's mother. It seems she has gone to heaven. Thank you for coming all this way. Now, come home with me.", "Restores every source sentence and relation in natural English."),
    "MAIN:0x03C8B1": r("ROCKET: I just heard that a kid is lurking nearby!", "Restores the omitted hearsay subject and complete clause."),
    "MAIN:0x03CD81": r("BIRD KEEPER: Don't think beating my big brother will make me submit!", "Restores the source warning as a complete sentence."),
    "MAIN:0x03D5B0": r("WARDEN: My Gold Teeth! Thank you, and sorry for the trouble! Don't tell anyone, but I lost my dentures and was too embarrassed to show my face at the office. Take this reward!", "Uses complete natural clauses while preserving the secret and reward."),
    "MAIN:0x03D65B": r("SWIMMER: Go out with me!", "Uses the natural English dating invitation and the official common Gen I Swimmer class."),
    "MAIN:0x03D6CF": r("SWIMMER: It's nothing.", "Restores the omitted subject and copula."),
    "MAIN:0x03D72D": r("SWIMMER: My fire has gone out...", "Uses the natural idiom for the extinguished flame."),
    "MAIN:0x03D7B3": r("SWIMMER: Not bad! Even high Defense can't stop you...", "Restores the contrast and explicit subject."),
    "MAIN:0x03D7BA": r("SWIMMER: I'll make you understand, no matter what...", "Completes the source determination clause."),
    "MAIN:0x03D801": r("BLACK BELT: You still won't apologize?", "Restores the complete question and uses the official Gen I trainer class."),
    "MAIN:0x03D8AF": r("TAEKWONDO: I heard you're strong, so I won't hold back!", "Restores the omitted subject and causal link."),
    "MAIN:0x03D8E0": r("BLACK BELT: Nothing hard scares me!", "Uses a complete natural rendering of the source boast and official Gen I class."),
    "MAIN:0x03DB61": r("PSYCHIC: Hmm... I see you understand.", "Restores the source realization as a complete clause."),
    "MAIN:0x03DBB5": r("PSYCHIC: Oh? You don't want to learn psychic powers?", "Restores the complete source question and learning verb."),
    "MAIN:0x03DCE4": r("SWIMMER: Now you understand!", "Uses natural English word order."),
    "MAIN:0x03DCEB": r("SKIER: What? My hearing isn't good!", "Uses the concise official class label and a complete hearing complaint."),
    "MAIN:0x03DD07": r("SKIER: Now I hear you.", "Uses the concise official class label."),
    "MAIN:0x03DD27": r("SKIER: Have you been to the Seafoam Islands?", "Uses the concise official class label and complete question."),
    "MAIN:0x03DD43": r("SKIER: They say a Legendary Pokémon lives there...", "Uses the concise official class label and complete hearsay clause."),
    "MAIN:0x03DD98": r("SWIMMER: Really? That's too bad...", "Restores the complete reaction and uses the official common Gen I Swimmer class."),
    "MAIN:0x03DE0C": r("SWIMMER: Where are you going?", "Restores the complete question and uses the official common Gen I Swimmer class."),
    "MAIN:0x03E13F": r("SCIENTIST: How careless of me...", "Restores the speaker in the reaction."),
    "MAIN:0x03E233": r("SCIENTIST: I'm burning up...", "Restores the omitted subject and auxiliary."),
    "MAIN:0x03E2EA": r("THIEF: I've been to many Gyms, but this one is the easiest to rob!", "Restores the subject and grammatical comparison."),
    "MAIN:0x03E41A": r("SWIMMER: No team can beat my Magikarp!", "Recasts the stilted peerless claim in natural English."),
    "MAIN:0x03E433": r("SWIMMER: What a disaster... I lost badly.", "Turns the noun fragment into a natural defeat line."),
    "MAIN:0x03E483": r("SWIMMER: Just seeing you annoys me!", "Uses natural emphasis for the source irritation."),
    "MAIN:0x03E565": r("BLACK BELT: The Pokémon League? You're ambitious, kid! TAMER: Don't be afraid.", "Gives both speakers complete natural clauses and uses the official Gen I class."),
    "MAIN:0x03E5E2": r("TAMER: Please... BLACK BELT: Come on!", "Expands the embedded speaker label to the official Gen I class while preserving the interrupted plea."),
    "MAIN:0x03F426": r("OAK: Gary, I have a favor to ask of you both. I made the Pokédexes on the table. They automatically record data on discovered Pokémon and add pages, making them handy guides. Ash, Gary, they're yours!", "Restores the request and explanation as complete natural clauses."),
    "RESTORED:0x033139": r("JAMES: A black hole! A dark future with no tomorrow awaits us!", "Keeps the NJ046 black-hole wordplay in natural English."),
    "RESTORED:0x03313B": r("MEOWTH: That's right!", "Normalizes duplicated exclamation punctuation."),
    "RESTORED:0x033197": r("ASH: Count on it!", "Uses a natural affirmative promise."),
    "RESTORED:0x0331C9": r("JAMES: We follow a new Boss now. We're not who we used to be!", "Normalizes duplicated exclamation punctuation."),
    "RESTORED:0x038353": r("SCOUT: You're the first to beat all of us!", "Restores the omitted subject and auxiliary."),
    "RESTORED:0x03AFB0": r("JESSIE: What an awful feeling...", "Restores the omitted determiner and complete exclamation."),
    "RESTORED:0x03B004": r("JESSIE: What an awful feeling...", "Restores the omitted determiner and complete exclamation."),
    # Pokédex prose: only certain grammatical/naturalness fixes.
    "MAIN:0x0321AF": r("Its hard shell can fire powerful bubbles.", "Uses the natural battle verb and count noun.", "pokedex_prose"),
    "MAIN:0x032244": r("Before hardening, it leaks when struck.", "Replaces the unnatural phrase 'hits draw fluid'.", "pokedex_prose"),
    "MAIN:0x032A7C": r("After losing its mother, its face stays hidden.", "Clarifies the source relation in natural English.", "pokedex_prose"),
    "MAIN:0x032B47": r("Seaweed-like growths cover it. It moves with ease.", "Replaces the unidiomatic phrase 'moves lightly'.", "pokedex_prose"),
    "MAIN:0x032DC5": r("This extinct Pokémon was revived from a fossil.", "Turns a noun fragment into a complete Pokédex sentence.", "pokedex_prose"),
    "MAIN:0x032E93": r("This phantom Pokémon lives underwater.", "Uses the standard one-word adverb.", "pokedex_prose"),
    "MAIN:0x032EC4": r("This new life-form can alter the weather.", "Replaces the vague noun phrase 'new life'.", "pokedex_prose"),
    "MAIN:0x032F5E": r("Its rainbow body is the subject of ancient lore.", "Uses natural modifier and legend syntax.", "pokedex_prose"),
    "MAIN:0x032FD0": r("A mysterious Hoenn Pokémon rules the land.", "Turns the source title into a complete natural Pokédex sentence.", "pokedex_prose"),
    "MAIN:0x036A79": r("It hardens to guard itself from danger.", "Replaces the malformed phrase 'danger makes it hard for safety'.", "pokedex_prose"),
    "MAIN:0x036B3D": r("Its huge wings carry it through the sky.", "Removes the redundant phrase 'fly in the sky'.", "pokedex_prose"),
    "MAIN:0x036C3A": r("Its spines emit potent poison when threatened.", "Uses natural verb and adjective order.", "pokedex_prose"),
    "MAIN:0x036D97": r("Larger than most bugs, it likes damp places.", "Clarifies the comparison and joins the clauses naturally.", "pokedex_prose"),
    "MAIN:0x036E68": r("Many people love this creature.", "Uses concise idiomatic English for widespread popularity.", "pokedex_prose"),
    "MAIN:0x036F64": r("It is a skilled, amazingly fast swimmer.", "Turns a noun fragment into a complete sentence.", "pokedex_prose"),
    "MAIN:0x036FC8": r("Its abilities surpass any computer.", "Matches the source ability comparison rather than inventing reaction speed.", "pokedex_prose"),
    "MAIN:0x037130": r("Its diamond-hard hooves crush anything.", "Replaces the incomplete object 'crush all'.", "pokedex_prose"),
    "MAIN:0x03792A": r("A mysterious Hoenn Pokémon rules the seabed.", "Turns the source title into a complete natural Pokédex sentence.", "pokedex_prose"),
    "MAIN:0x03795F": r("A mysterious Hoenn Pokémon rules the sky.", "Turns the source title into a complete natural Pokédex sentence.", "pokedex_prose"),
    "MAIN:0x03DF0D": r("PRESIDENT: Thanks for saving me! I'll never forget it. Oh! I must give you a gift! How about this?", "Preserves the shadowed containing-offset row byte-for-byte; the exact live owner is classified separately.", "shadowed_nonlive"),
}


# These were size-driven abbreviations, not official Gen I labels.  Replacing
# them at the beginning of dialogue payloads is deterministic and reviewable.
SPEAKER_PREFIXES: Mapping[str, str] = {
    "BUG: ": "BUG CATCHER: ",
    "GENT: ": "GENTLEMAN: ",
    "YNGSTR: ": "YOUNGSTER: ",
    "BIRD KPR: ": "BIRD KEEPER: ",
    "M.SWIM: ": "SWIMMER: ",
    "F.SWIM: ": "SWIMMER: ",
    "SWIM BOY: ": "SWIMMER: ",
    "SWIM GIRL: ": "SWIMMER: ",
    "SWIMMER GIRL: ": "SWIMMER: ",
    "M.SKIER: ": "SKIER: ",
    "F.SKIER: ": "SKIER: ",
    "PSY: ": "PSYCHIC: ",
    "SCI: ": "SCIENTIST: ",
    "DOC: ": "DOCTOR: ",
    "REF: ": "GUIDE: ",
    "PRES: ": "PRESIDENT: ",
    "KARATE: ": "BLACK BELT: ",
    "KARATEKA: ": "BLACK BELT: ",
}

# Red/Blue/Yellow do not prepend a generic Trainer class to a field dialogue:
# the overworld sprite and encounter already identify the speaker.  Keeping
# those labels on hundreds of one-speaker payloads is also a material waste of
# the fixed PRG text bank.  Proper names remain, and multi-speaker payloads
# retain labels because the speaker switch would otherwise be ambiguous.
CONTEXTUAL_SPEAKER_LABELS = frozenset(
    {
        "AUNTIE", "ATTENDANT", "BEAUTY", "BIG GUY", "BIKER",
        "BIRD KEEPER", "BLACK BELT", "BOSS", "BOY", "BUG CATCHER",
        "CAPTAIN", "CHANNELER", "CHILD", "CLERK", "DEPUTY", "DOCTOR",
        "ELDER", "FISHERMAN", "GENTLEMAN", "GIRL", "GUARD", "GUIDE",
        "JUGGLER", "LASS", "MAN", "MASTER", "MEDIUM", "MOM", "NINJA",
        "NUN", "OFFICER", "OLD MAN", "PRESIDENT", "PSYCHIC", "REFEREE",
        "ROCKER", "ROCKET", "ROCKET WOMAN", "SAILOR", "SCIENTIST",
        "SCOUT", "SECRETARY", "SKIER", "SOLDIER", "STAFF", "SWIMMER",
        "TAEKWONDO", "TAMER", "TEAM ROCKET", "THIEF", "TRADER", "TWINS",
        "WARDEN", "WOMAN", "YOUNGSTER",
    }
)
# These catalogue rows are historical containing/overlap cells, not live ROM
# surfaces after pointer restoration.  Pin the exact live owner and target so
# an editorial scan cannot mistake them for untranslated field dialogue.
SHADOWED_NONLIVE_ROWS: Mapping[str, tuple[str, str, str]] = {
    "MAIN:0x039D3B": ("0x038347", "RESTORED:0x038347", "0x03A2CE"),
    "MAIN:0x03DF0D": ("0x03CF60", "MAIN:0x03D7CB", "0x03B1E6"),
}
SPEAKER_LABEL_RE = re.compile(r"^([A-Z][A-Z .'-]*): ")
EMBEDDED_SPEAKER_LABEL_RE = re.compile(r" [A-Z][A-Z .'-]*: ")


VARIANT_REVISIONS: Mapping[str, Revision] = {
    "MAIN:0x0302FA@0x03006B": r(
        " was badly poisoned!",
        "Keeps the primary bad-poison pointer byte-identical to its bounded MAIN payload.",
        "dynamic_layout_24",
    ),
    "MAIN:0x031A15@0x031971": r(
        "Catch  Pokémon",
        "Fits the fixed 7x3 description grid as 'Catch' / 'Pokémon'.",
        "fixed_grid_7x3",
    ),
    "MAIN:0x031A15@0x031973": r(
        "Better than a Poké B.",
        "Fits the fixed 7x3 grid as 'Better' / 'than a' / 'Poké B.' and preserves the explicit Poké Ball comparison.",
        "fixed_grid_7x3",
    ),
    "MAIN:0x031A15@0x031975": r(
        "Better than a Great B",
        "Fits the fixed 7x3 grid as 'Better' / 'than a' / 'Great B' and preserves the explicit Great Ball comparison.",
        "fixed_grid_7x3",
    ),
}

FIXED_GRID_7X3_KEYS = frozenset(
    key
    for key, revision in REVISIONS.items()
    if revision.review_class == "fixed_grid_7x3"
)

# Earlier review notes for these rows asserted the wrong executable item/TM
# identity.  Their corrected evidence must replace, rather than supplement,
# that stale claim.  Fixed-grid rows likewise use the renderer constraint as
# their complete, authoritative fidelity note.
AUTHORITATIVE_COMMENT_KEYS = frozenset(
    {"MAIN:0x0349E5", "MAIN:0x0349F2", "MAIN:0x038F91"}
    | set(FIXED_GRID_7X3_KEYS)
)


REPORT_FIELDS = (
    "surface",
    "stable_key",
    "domain",
    "source_text",
    "previous_english",
    "reviewed_english",
    "status",
    "review_class",
    "reason",
    "encoded_length",
    "layout",
)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or ()), list(reader)


def render_csv(fields: Sequence[str], rows: Sequence[Mapping[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def domain(row: Mapping[str, str]) -> str:
    layout = row.get("layout", "")
    if row.get("stable_key") in SHADOWED_NONLIVE_ROWS:
        return "shadowed_nonlive"
    if layout.startswith("dialogue_"):
        return "dialogue"
    if layout == "pokedex_13x4":
        return "pokedex"
    if row.get("record_type") == "RESTORED":
        return "restored"
    return "fixed_or_dynamic"


def normalize_speaker(text: str, layout: str) -> tuple[str, str]:
    if not layout.startswith("dialogue_"):
        return text, ""
    for abbreviated, full in SPEAKER_PREFIXES.items():
        if text.startswith(abbreviated):
            return full + text[len(abbreviated):], (
                f"Normalizes nonstandard speaker abbreviation {abbreviated.strip()!r} "
                f"to {full.strip()!r}."
            )
    return text, ""


def omit_contextual_speaker_label(
    text: str,
    layout: str,
) -> tuple[str, str]:
    """Drop a redundant generic label from a one-speaker field dialogue."""

    if not layout.startswith("dialogue_"):
        return text, ""
    match = SPEAKER_LABEL_RE.match(text)
    if match is None or match.group(1) not in CONTEXTUAL_SPEAKER_LABELS:
        return text, ""
    if EMBEDDED_SPEAKER_LABEL_RE.search(text[match.end():]):
        return text, ""
    return text[match.end():], (
        f"Omits the contextual one-speaker label {match.group(1)!r}, as in "
        "official Gen I field dialogue; the sprite and encounter retain the "
        "speaker identity."
    )


def revised_catalogue(
    rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    by_key = {row.get("stable_key", ""): row for row in rows}
    missing = sorted(set(REVISIONS) - set(by_key))
    if missing:
        raise ValueError("review revisions reference missing catalogue keys: " + ", ".join(missing))

    result: list[dict[str, str]] = []
    report: list[dict[str, str]] = []
    changed: dict[str, str] = {}
    for source in rows:
        row = dict(source)
        key = row["stable_key"]
        if key in FIXED_GRID_7X3_KEYS:
            row["layout"] = "fixed_grid_7x3"
        previous = row.get("english_v2", "")
        revision = REVISIONS.get(key)
        text = revision.text if revision else previous
        text, prefix_reason = normalize_speaker(text, row.get("layout", ""))
        text, omission_reason = omit_contextual_speaker_label(
            text, row.get("layout", "")
        )
        reasons = [
            part
            for part in (
                revision.reason if revision else "",
                prefix_reason,
                omission_reason,
            )
            if part
        ]
        classes = [revision.review_class] if revision else []
        if prefix_reason:
            classes.append("speaker_label")
        if omission_reason:
            classes.append("contextual_label_omission")

        payload = ENGLISH_TEXT_PROFILE.format_text(text, row.get("layout", ""))
        row["english_v2"] = text
        row["encoded_length"] = str(len(payload))
        reason = " ".join(reasons)
        if revision is not None or prefix_reason:
            marker = "Full-text review: " + reason
            old_comment = row.get("fidelity_comment", "").strip()
            base_comment = old_comment.split(" Full-text review:", 1)[0]
            if base_comment.startswith("Full-text review:"):
                base_comment = ""
            if key in AUTHORITATIVE_COMMENT_KEYS or omission_reason:
                base_comment = ""
            row["fidelity_comment"] = (base_comment + " " + marker).strip()

        if text != previous:
            changed[key] = row["fidelity_comment"]
            status = "corrected"
        else:
            if not reason:
                reason = "Reviewed against Chinese source, runtime role, and English style; no certain change required."
            status = "reviewed_no_change"

        if key in SHADOWED_NONLIVE_ROWS:
            reference, live_owner, final_target = SHADOWED_NONLIVE_ROWS[key]
            status = "shadowed_nonlive"
            classes = ["shadowed_nonlive"]
            reason = (
                f"Non-live overlap cell: reference {reference} resolves to "
                f"{live_owner} at final target {final_target}; this MAIN row "
                "is not a displayed ROM surface."
            )
            row["fidelity_comment"] = reason

        report.append(
            {
                "surface": "catalogue",
                "stable_key": key,
                "domain": domain(row),
                "source_text": row.get("chinese_text", ""),
                "previous_english": previous,
                "reviewed_english": text,
                "status": status,
                "review_class": "+".join(classes) if classes else "full_corpus_review",
                "reason": reason,
                "encoded_length": str(len(payload)),
                "layout": row.get("layout", ""),
            }
        )
        result.append(row)
    return result, report, changed


def revised_variants(
    rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    known = {row.get("variant_key", "") for row in rows}
    missing = sorted(set(VARIANT_REVISIONS) - known)
    if missing:
        raise ValueError("review revisions reference missing pointer variants: " + ", ".join(missing))
    result: list[dict[str, str]] = []
    report: list[dict[str, str]] = []
    for source in rows:
        row = dict(source)
        key = row["variant_key"]
        previous = row.get("english_v2", "")
        revision = VARIANT_REVISIONS.get(key)
        text = revision.text if revision else previous
        layout = "fixed_grid_7x3" if key.startswith("MAIN:0x031A15@") else ""
        ENGLISH_TEXT_PROFILE.format_text(text, layout)
        row["english_v2"] = text
        if revision:
            row["fidelity_comment"] = revision.reason
        report.append(
            {
                "surface": "pointer_variant",
                "stable_key": key,
                "domain": "fixed_or_dynamic",
                "source_text": row.get("chinese_text", ""),
                "previous_english": previous,
                "reviewed_english": text,
                "status": "corrected" if text != previous else "reviewed_no_change",
                "review_class": revision.review_class if revision else "full_corpus_review",
                "reason": revision.reason if revision else "Reviewed; no certain change required.",
                "encoded_length": str(len(ENGLISH_TEXT_PROFILE.format_text(text, layout))),
                "layout": layout,
            }
        )
        result.append(row)
    return result, report


def update_csv_column(
    path: Path,
    key_field: str,
    value_field: str,
    final_texts: Mapping[str, str],
) -> str:
    fields, rows = read_csv(path)
    for row in rows:
        key = row.get(key_field, "")
        if key in final_texts:
            row[value_field] = final_texts[key]
    return render_csv(fields, rows)


def update_review_batches(
    final_rows: Mapping[str, Mapping[str, str]],
) -> dict[Path, str]:
    rendered: dict[Path, str] = {}
    for path in sorted(REVIEW_BATCHES.glob("*.review.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        dirty = False
        for entry in document.get("entries", []):
            key = entry.get("stable_key", "")
            final = final_rows.get(key)
            if final is None:
                continue
            for field in ("english_v2", "fidelity_comment"):
                value = final.get(field, "")
                if entry.get(field) != value:
                    entry[field] = value
                    dirty = True
        if dirty:
            rendered[path] = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    return rendered


def preserve_correction_provenance(
    report: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Keep the original before/after witness after canonical data is updated.

    The first ``--apply`` reads the pre-review catalogue, so its report records
    the true previous wording.  Later deterministic checks read the corrected
    catalogue.  Reuse that witness when the reviewed payload is unchanged,
    while still regenerating live metadata such as layout and encoded length.
    """

    if not REPORT.exists():
        return list(report)
    _, previous_rows = read_csv(REPORT)
    previous = {
        (row.get("surface", ""), row.get("stable_key", "")): row
        for row in previous_rows
    }
    result: list[dict[str, str]] = []
    for source in report:
        row = dict(source)
        witness = previous.get((row["surface"], row["stable_key"]))
        if (
            row["status"] == "corrected"
            and witness is not None
            and witness.get("status") == "corrected"
            and witness.get("reviewed_english") == row["previous_english"]
        ):
            row["previous_english"] = witness.get(
                "previous_english", row["previous_english"]
            )
        if (
            row["status"] == "reviewed_no_change"
            and witness is not None
            and witness.get("status") == "corrected"
            and witness.get("reviewed_english") == row["reviewed_english"]
        ):
            row["previous_english"] = witness.get(
                "previous_english", row["previous_english"]
            )
            row["status"] = "corrected"
            if row["review_class"] == "full_corpus_review":
                row["review_class"] = witness.get(
                    "review_class", row["review_class"]
                )
            if row["reason"].startswith("Reviewed against Chinese source"):
                row["reason"] = witness.get("reason", row["reason"])
        if (
            row["status"] == "shadowed_nonlive"
            and witness is not None
            and witness.get("status") == "shadowed_nonlive"
            and witness.get("reviewed_english") == row["reviewed_english"]
        ):
            row["previous_english"] = witness.get(
                "previous_english", row["previous_english"]
            )
        result.append(row)
    return result


def harmonize_review_metadata(
    rows: Sequence[dict[str, str]],
    report: Sequence[Mapping[str, str]],
) -> None:
    """Remove size notes that describe superseded wording.

    The previous English pass documented many deliberate abbreviations.  This
    review expands those labels and repairs the prose, so notes that still say
    e.g. ``PP Up is unchanged`` or ``abbreviates the speaker`` are no longer
    valid evidence.  Preserve whether a row was size-driven, but describe the
    final payload and its actual renderer constraint.
    """

    reviewed = {row["stable_key"]: row for row in report}
    no_compression = {
        "MAIN:0x030409",
        "MAIN:0x0349E5",
        "MAIN:0x0349F2",
        "MAIN:0x038F91",
    }
    for row in rows:
        witness = reviewed.get(row["stable_key"])
        if witness is None or witness.get("status") != "corrected":
            continue
        classes = set(filter(None, witness.get("review_class", "").split("+")))
        if row["stable_key"] in no_compression:
            row["compression"] = "no"
            row["compression_justification"] = ""
        elif "fixed_grid_7x3" in classes:
            row["compression"] = "yes"
            row["compression_justification"] = (
                "The item-description renderer exposes three seven-cell rows; "
                "the final payload fits all 21 cells without a split or stale tile."
            )
        elif "fixed_item_name_7" in classes:
            row["compression"] = "yes"
            row["compression_justification"] = (
                "The Bag list reserves eight cells for the item name and writes "
                "the two-digit quantity immediately after them; this unambiguous "
                "label uses at most seven cells, leaving a visible separator."
            )
        elif "pokedex_prose" in classes:
            row["compression"] = "yes"
            row["compression_justification"] = (
                "Rephrased to fit the four 13-cell Pokédex lines without "
                "splitting a word or dropping the source fact."
            )
        elif "contextual_label_omission" in classes:
            row["compression"] = "yes"
            row["compression_justification"] = (
                "Uses official Gen I field-dialogue style: the visible sprite "
                "and encounter identify the sole speaker, so no redundant "
                "class label consumes text-bank space."
            )
        elif row.get("compression") == "yes":
            label_note = (
                " and uses an unambiguous full speaker label"
                if "speaker_label" in classes
                else ""
            )
            row["compression_justification"] = (
                "Uses complete, natural English"
                + label_note
                + " while respecting dialogue pagination and ROM bank limits; "
                "no displayed word is truncated."
            )


def build_outputs() -> tuple[dict[Path, str], dict[str, int]]:
    catalog_fields, catalog_rows = read_csv(CATALOGUE)
    variant_fields, variant_rows = read_csv(VARIANTS)
    revised_rows, catalog_report, changed_comments = revised_catalogue(catalog_rows)
    revised_variant_rows, variant_report = revised_variants(variant_rows)
    catalog_report = preserve_correction_provenance(catalog_report)
    variant_report = preserve_correction_provenance(variant_report)
    harmonize_review_metadata(revised_rows, catalog_report)
    final_by_key = {row["stable_key"]: row for row in revised_rows}
    final_texts = {key: row["english_v2"] for key, row in final_by_key.items()}

    outputs: dict[Path, str] = {
        CATALOGUE: render_csv(catalog_fields, revised_rows),
        VARIANTS: render_csv(variant_fields, revised_variant_rows),
        REPORT: render_csv(REPORT_FIELDS, catalog_report + variant_report),
        OFFICIAL_AUDIT: update_csv_column(
            OFFICIAL_AUDIT, "stable_key", "english_v2", final_texts
        ),
        OFFICIAL_CHANGES: update_csv_column(
            OFFICIAL_CHANGES, "stable_key", "revised_english_v2", final_texts
        ),
    }
    outputs.update(update_review_batches(final_by_key))

    stats = {
        "catalogue_rows": len(revised_rows),
        "pointer_variants": len(revised_variant_rows),
        "corrected_catalogue_rows": sum(
            row["status"] == "corrected" for row in catalog_report
        ),
        "corrected_pointer_variants": sum(
            row["status"] == "corrected" for row in variant_report
        ),
        "shadowed_nonlive_rows": sum(
            row["status"] == "shadowed_nonlive" for row in catalog_report
        ),
        "live_surfaces": sum(
            row["status"] != "shadowed_nonlive"
            for row in catalog_report + variant_report
        ),
        "report_rows": len(catalog_report) + len(variant_report),
    }
    return outputs, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    outputs, stats = build_outputs()
    stale = [
        path
        for path, rendered in outputs.items()
        if not path.exists() or path.read_text(encoding="utf-8") != rendered
    ]
    if args.check:
        if stale:
            print("English full-text review is stale:")
            for path in stale:
                print(f"  {path.relative_to(ROOT)}")
            return 1
        print(json.dumps({"result": "PASS", **stats}, indent=2))
        return 0

    for path, rendered in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="")

    # The human-facing sheet is a generated derivative of the canonical CSV
    # and official-reference witnesses.
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "export_english_review_sheet.py")],
        cwd=ROOT,
        check=True,
    )
    print(json.dumps({"result": "APPLIED", **stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
