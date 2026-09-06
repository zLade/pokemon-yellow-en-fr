#!/usr/bin/env python3
"""Language-neutral topology for the 85 NJ046 dialogue restorations.

The 2015 English patch damaged source-side pointer slots in three different
ways: 80 pointers became invalid, four were redirected to unrelated English
text, and the distinct Parlyz Heal message was collapsed onto Awakening.

This module deliberately contains no translated text.  A locale catalogue is
valid only when its keys match :data:`RESTORATION_REFERENCES` exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class RestorationKind(str, Enum):
    """Structural defect introduced by the English patch."""

    REMOVED = "removed"
    MISWIRED = "miswired"
    COLLAPSED = "collapsed"


@dataclass(frozen=True, slots=True)
class RestorationSlot:
    """One source pointer slot that needs a new locale-specific payload.

    ``observed_english_target`` is ``None`` for an invalidated pointer.  For a
    miswired or collapsed pointer it records the exact target that must be
    observed in the pristine 2015 English base before any repair is applied.

    ``reviewed_replacement_target`` is only populated for the four miswired
    Nugget Bridge replies.  It identifies their reviewed canonical owner in
    the existing allocator; it is not translated content and a locale remains
    free to allocate a distinct payload for every restoration slot.
    """

    reference: int
    kind: RestorationKind
    observed_english_target: int | None = None
    reviewed_replacement_target: int | None = None

    def __post_init__(self) -> None:
        if self.reference < 0:
            raise ValueError("a restoration reference cannot be negative")
        if self.kind is RestorationKind.REMOVED:
            if self.observed_english_target is not None:
                raise ValueError("a removed slot must expect an invalid pointer")
            if self.reviewed_replacement_target is not None:
                raise ValueError("a removed slot cannot have a redirect target")
        elif self.kind is RestorationKind.MISWIRED:
            if self.observed_english_target is None:
                raise ValueError("a miswired slot needs its observed base target")
            if self.reviewed_replacement_target is None:
                raise ValueError("a miswired slot needs its reviewed target")
        elif self.kind is RestorationKind.COLLAPSED:
            if self.observed_english_target is None:
                raise ValueError("a collapsed slot needs its shared base target")
            if self.reviewed_replacement_target is not None:
                raise ValueError("a collapsed slot must receive a distinct payload")


# These references are copied from the source-side pointer inventory, not from
# the French catalogue.  Keeping the set explicit prevents a locale from
# silently defining (and therefore changing) structural coverage.
REMOVED_ENGLISH_POINTER_REFERENCES = frozenset(
    {
        0x033137,
        0x033139,
        0x03313B,
        0x03313D,
        0x03313F,
        0x033141,
        0x033193,
        0x033195,
        0x033197,
        0x033199,
        0x0331B3,
        0x0331B5,
        0x0331B7,
        0x0331B9,
        0x0331BB,
        0x0331BD,
        0x0331BF,
        0x0331C1,
        0x0331C3,
        0x0331C5,
        0x0331C7,
        0x0331C9,
        0x0331D1,
        0x038313,
        0x038315,
        0x038317,
        0x038319,
        0x03831B,
        0x03831D,
        0x03831F,
        0x038321,
        0x038323,
        0x038325,
        0x03AF94,
        0x03AF96,
        0x03AF98,
        0x03AF9A,
        0x03AF9C,
        0x03AF9E,
        0x03AFA0,
        0x03AFA2,
        0x03AFA4,
        0x03AFA6,
        0x03AFA8,
        0x03AFAA,
        0x03AFAC,
        0x03AFB0,
        0x03AFB2,
        0x03AFEA,
        0x03AFEC,
        0x03AFEE,
        0x03AFF0,
        0x03AFF2,
        0x03AFF4,
        0x03AFF6,
        0x03AFF8,
        0x03AFFA,
        0x03AFFC,
        0x03AFFE,
        0x03B000,
        0x03B004,
        0x03B006,
        0x03CF3E,
        0x03CF40,
        0x03CF42,
        0x03CF44,
        0x03CF46,
        0x03CF48,
        0x03CF4A,
        0x03CF4C,
        0x03CF4E,
        0x03CF50,
        0x03CF52,
        0x03CF54,
        0x03CF56,
        0x03CF58,
        0x03D07A,
        0x03D07C,
        0x03D07E,
        0x03D080,
    }
)

# ``reference: (unrelated English target, reviewed canonical owner)``.
MISWIRED_ENGLISH_POINTER_TARGETS = MappingProxyType(
    {
        0x038347: (0x039D3B, 0x039AF5),
        0x03834B: (0x039D74, 0x039AF5),
        0x03834F: (0x039DB8, 0x039AF5),
        0x038353: (0x039DF5, 0x039AF5),
    }
)

# Anti-Para/Parlyz Heal was incorrectly made to share Awakening's payload.
COLLAPSED_ENGLISH_POINTER_TARGETS = MappingProxyType(
    {0x0348F1: 0x03499D}
)

REMOVED_ENGLISH_POINTER_COUNT = len(REMOVED_ENGLISH_POINTER_REFERENCES)
BAD_ENGLISH_POINTER_COUNT = len(MISWIRED_ENGLISH_POINTER_TARGETS)
COLLAPSED_ENGLISH_POINTER_COUNT = len(COLLAPSED_ENGLISH_POINTER_TARGETS)
EXPECTED_RESTORATION_COUNT = 85


def _build_topology() -> Mapping[int, RestorationSlot]:
    slots = {
        reference: RestorationSlot(reference, RestorationKind.REMOVED)
        for reference in REMOVED_ENGLISH_POINTER_REFERENCES
    }
    slots.update(
        {
            reference: RestorationSlot(
                reference,
                RestorationKind.MISWIRED,
                observed_target,
                reviewed_target,
            )
            for reference, (
                observed_target,
                reviewed_target,
            ) in MISWIRED_ENGLISH_POINTER_TARGETS.items()
        }
    )
    slots.update(
        {
            reference: RestorationSlot(
                reference,
                RestorationKind.COLLAPSED,
                observed_target,
            )
            for reference, observed_target in (
                COLLAPSED_ENGLISH_POINTER_TARGETS.items()
            )
        }
    )
    return MappingProxyType(dict(sorted(slots.items())))


RESTORATION_TOPOLOGY = _build_topology()
RESTORATION_REFERENCES = frozenset(RESTORATION_TOPOLOGY)

if REMOVED_ENGLISH_POINTER_COUNT != 80:
    raise AssertionError(
        f"{REMOVED_ENGLISH_POINTER_COUNT} removed pointers instead of 80"
    )
if BAD_ENGLISH_POINTER_COUNT != 4:
    raise AssertionError(
        f"{BAD_ENGLISH_POINTER_COUNT} miswired pointers instead of 4"
    )
if COLLAPSED_ENGLISH_POINTER_COUNT != 1:
    raise AssertionError(
        f"{COLLAPSED_ENGLISH_POINTER_COUNT} collapsed pointer instead of 1"
    )
if len(RESTORATION_TOPOLOGY) != EXPECTED_RESTORATION_COUNT:
    raise AssertionError(
        f"{len(RESTORATION_TOPOLOGY)} restorations instead of "
        f"{EXPECTED_RESTORATION_COUNT}"
    )


def validate_restoration_catalogue(
    catalogue: Mapping[int, object],
    *,
    label: str = "restoration catalogue",
) -> None:
    """Require a locale catalogue to cover exactly the neutral topology."""

    references = set(catalogue)
    missing = RESTORATION_REFERENCES - references
    unknown = references - RESTORATION_REFERENCES
    if not missing and not unknown:
        return

    details: list[str] = []
    if missing:
        details.append(
            "missing "
            + ", ".join(f"0x{reference:06X}" for reference in sorted(missing))
        )
    if unknown:
        details.append(
            "unknown "
            + ", ".join(f"0x{reference:06X}" for reference in sorted(unknown))
        )
    raise ValueError(f"{label}: " + "; ".join(details))
