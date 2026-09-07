#!/usr/bin/env python3
"""Page-aware French line breaking and quality audit for field dialogue.

The ordinary NJ046 field renderer shows one 19-column line per input wait.
Keeping words intact is therefore necessary but not sufficient: a greedy
wrapper can still produce sequences such as ``Ne sors|pas`` or
``affronter le|Conseil``.  This module offers a separate, opt-in dynamic
programming wrapper that strongly avoids those grammatical orphans.

It deliberately does not replace :mod:`tools.dialogue_layout`.  The scoring
is a French-language heuristic, so its output still needs editorial review
and runtime validation before being compiled into a release.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from tools.dialogue_layout import (  # noqa: E402
    DIALOGUE_LAYOUT,
    INTRO_DIALOGUE_LAYOUT,
    dialogue_line_width,
    semantic_units,
    wrap_dialogue_lines_greedy,
)
from tools.french_font import decode_game_text, encode_game_text  # noqa: E402


# The relative size of these weights is intentional.  A grammatical orphan
# must cost much more than an under-filled page, while a natural punctuation
# boundary should be allowed to beat the greedy "fill every column" choice.
STRONG_BOUNDARY_PENALTY = 12_000
MEDIUM_BOUNDARY_PENALTY = 3_000
WEAK_BOUNDARY_PENALTY = 700
ADDITIONAL_REASON_PENALTY = 250
SENTENCE_BOUNDARY_REWARD = 500
CLAUSE_BOUNDARY_REWARD = 180
UNPUNCTUATED_BOUNDARY_PENALTY = 90
PAGE_COST = 420
RAGGEDNESS_FACTOR = 3
LAST_PAGE_RAGGEDNESS_DIVISOR = 6

SEVERITY_RANK = {
    "none": 0,
    "weak": 1,
    "medium": 2,
    "strong": 3,
}

# Ending a page on one of these almost always separates a grammatical unit
# from its complement.  The list is intentionally conservative and uses
# complete semantic units rather than substrings (``aujourd'hui`` must not be
# treated like a contraction ending in ``hui``).
STRONG_END_UNITS = frozenset(
    {
        "à", "afin", "au", "aux", "avec", "car",
        "ce", "ces", "cet", "cette", "chez", "chaque",
        "quelques", "dans", "de", "des", "du",
        "elle", "elles", "en", "et", "il", "ils", "je",
        "la", "le", "les", "leur", "leurs", "lorsque",
        "ma", "mais", "me", "mes", "mon", "ne", "ni",
        "nos", "notre", "nous", "on", "ou", "par", "parce",
        "parmi", "pour", "puisque", "qu'", "quand", "que",
        "quel", "quelle", "quelles", "quels", "qui",
        "sa", "sans", "se", "ses", "son", "sous", "sur",
        "ta", "te", "tes", "ton", "tu", "un", "une",
        "vers", "vos", "votre", "vous",
    }
)

MEDIUM_END_CONTRACTIONS = frozenset(
    {
        "c'est", "c'était", "c'étaient", "ce sont",
        "j'ai", "j'avais", "j'aurai", "j'aurais", "j'étais",
        "t'as", "t'avais", "t'auras", "t'aurais", "t'es",
        "n'est", "n'était", "n'étaient", "n'a", "n'avait",
        "qu'il", "qu'elle", "qu'on", "qu'ils", "qu'elles",
    }
)

MEDIUM_END_UNITS = frozenset(
    {
        "a", "ai", "allons", "allez", "as", "avons", "avez",
        "aussi", "beaucoup", "bien", "encore", "moins",
        "dois", "doit", "doivent", "devons", "devez",
        "es", "est", "étaient", "étais", "était", "êtes",
        "plus", "peu", "tellement", "trop", "très",
        "avoir", "être", "faire", "aller", "venir", "ont",
        "peuvent", "peut", "peux", "pouvez", "pouvons",
        "sera", "serai", "seras", "serez", "serons", "seront",
        "sommes", "sont", "suis", "va", "vais", "vas", "vont",
    }
)

PROTECTED_UNIT_PAIRS = frozenset(
    {
        ("bourg", "palette"),
        ("conseil", "des"),
        ("major", "bob"),
        ("mont", "sélénite"),
        ("poké", "ball"),
        ("poké", "balls"),
        ("prof", "chen"),
        ("professeur", "chen"),
        ("team", "rocket"),
    }
)

# These beginnings normally belong with material on the preceding page.
# They are ignored when that preceding page ends a sentence.
STRONG_START_UNITS = frozenset(
    {
        "pas", "jamais", "rien", "personne",
        "me", "te", "se", "lui",
    }
)

MEDIUM_START_UNITS = frozenset(
    {
        "à", "au", "aux", "avec", "aussi", "dans", "de", "des",
        "dont", "du", "en", "encore", "et", "mais", "moins", "ou",
        "par", "pour", "plus", "puis", "que", "qui", "sans",
        "sous", "sur", "trop", "très",
    }
)

_SENTENCE_END_RE = re.compile(r"(?:[.!?…]|\.{2,})[»”\"')\]]*$")
_CLAUSE_END_RE = re.compile(r"[,;:][»”\"')\]]*$")
_EDGE_PUNCTUATION_RE = re.compile(
    r"^[^0-9a-zà-ÿœ'-]+|[^0-9a-zà-ÿœ'-]+$",
    re.IGNORECASE,
)
_NON_TERMINAL_ABBREVIATIONS = frozenset(
    {
        "dr.",
        "m.",
        "mlle.",
        "mme.",
        "prof.",
    }
)


@dataclass(frozen=True)
class PageBoundaryIssue:
    """One suspicious boundary between two rendered dialogue pages."""

    boundary_after_page: int
    severity: str
    penalty: int
    reasons: tuple[str, ...]
    left_page: str
    right_page: str


@dataclass(frozen=True)
class DialoguePagePlan:
    """Deterministic DP result and its independently recomputed audit."""

    lines: tuple[bytes, ...]
    score: int
    quality_vector: tuple[int, ...]
    issues: tuple[PageBoundaryIssue, ...]
    semantic_bytes: bytes
    forced_page_breaks: int


@dataclass(frozen=True)
class _PartialPlan:
    cost: tuple[int, ...]
    lines: tuple[bytes, ...]


def _normalise_unit(unit: str) -> str:
    value = unit.casefold().replace("’", "'").strip()
    previous = None
    while value and value != previous:
        previous = value
        value = _EDGE_PUNCTUATION_RE.sub("", value)
    return value


def _abbreviation_end(text: str) -> bool:
    units = _page_units(text)
    if not units:
        return False
    last = units[-1].casefold().replace("’", "'").strip("»”\"') ]")
    return last in _NON_TERMINAL_ABBREVIATIONS


def _sentence_end(text: str) -> bool:
    return (
        not _abbreviation_end(text)
        and bool(_SENTENCE_END_RE.search(text.rstrip()))
    )


def _clause_end(text: str) -> bool:
    return bool(_CLAUSE_END_RE.search(text.rstrip()))


def _page_units(text: str) -> list[str]:
    return semantic_units(text.strip())


def _severity_penalty(severity: str, reason_count: int) -> int:
    base = {
        "none": 0,
        "weak": WEAK_BOUNDARY_PENALTY,
        "medium": MEDIUM_BOUNDARY_PENALTY,
        "strong": STRONG_BOUNDARY_PENALTY,
    }[severity]
    return base + max(0, reason_count - 1) * ADDITIONAL_REASON_PENALTY


def assess_page_boundary(
    left_page: str,
    right_page: str,
    boundary_after_page: int = 1,
) -> PageBoundaryIssue | None:
    """Classify an awkward French boundary without changing either page."""
    left_units = _page_units(left_page)
    right_units = _page_units(right_page)
    if not left_units or not right_units:
        return None

    left_terminal = _sentence_end(left_page)
    left_last = _normalise_unit(left_units[-1])
    right_first = _normalise_unit(right_units[0])
    severity = "none"
    reasons: list[str] = []

    def flag(level: str, reason: str) -> None:
        nonlocal severity
        if SEVERITY_RANK[level] > SEVERITY_RANK[severity]:
            severity = level
        reasons.append(reason)

    if not left_terminal:
        if _abbreviation_end(left_page):
            flag("strong", f"trailing abbreviated title « {left_units[-1]} »")
        if (left_last, right_first) in PROTECTED_UNIT_PAIRS:
            flag(
                "strong",
                "split compound name "
                f"« {left_units[-1]} | {right_units[0]} »",
            )
        if left_last in STRONG_END_UNITS:
            flag("strong", f"trailing function word « {left_units[-1]} »")
        if left_last in MEDIUM_END_CONTRACTIONS:
            flag("medium", f"trailing verb phrase « {left_units[-1]} »")
        if left_last.endswith(("qu'", "lorsqu'", "puisqu'")):
            flag("strong", f"trailing contraction « {left_units[-1]} »")
        if left_last in MEDIUM_END_UNITS:
            flag("medium", f"trailing modifier « {left_units[-1]} »")

        if right_first in STRONG_START_UNITS:
            flag("strong", f"leading complement « {right_units[0]} »")
        elif right_first in MEDIUM_START_UNITS:
            flag("medium", f"leading connective « {right_units[0]} »")

        if (
            len(left_units) == 1
            and len(encode_game_text(left_units[0])) <= 8
            and not _clause_end(left_page)
        ):
            flag("weak", f"very short trailing fragment « {left_units[0]} »")

    if not reasons:
        return None
    return PageBoundaryIssue(
        boundary_after_page=boundary_after_page,
        severity=severity,
        penalty=_severity_penalty(severity, len(reasons)),
        reasons=tuple(reasons),
        left_page=left_page.rstrip(),
        right_page=right_page.rstrip(),
    )


def audit_dialogue_pages(
    lines: Sequence[bytes | str],
) -> tuple[PageBoundaryIssue, ...]:
    """Return every strong/medium/weak linguistic boundary suspect."""
    decoded = tuple(
        decode_game_text(line).rstrip()
        if isinstance(line, bytes)
        else line.rstrip()
        for line in lines
    )
    issues: list[PageBoundaryIssue] = []
    for index, (left, right) in enumerate(
        zip(decoded, decoded[1:]),
        start=1,
    ):
        issue = assess_page_boundary(left, right, index)
        if issue is not None:
            issues.append(issue)
    return tuple(issues)


def _boundary_score(left_page: str, right_page: str) -> int:
    issue = assess_page_boundary(left_page, right_page)
    score = issue.penalty if issue is not None else 0
    if _sentence_end(left_page):
        score -= SENTENCE_BOUNDARY_REWARD
    elif _clause_end(left_page):
        score -= CLAUSE_BOUNDARY_REWARD
    else:
        score += UNPUNCTUATED_BOUNDARY_PENALTY
    return score


def _line_score(length: int, width: int, *, last: bool) -> int:
    if length < 1 or length > width:
        raise ValueError(
            f"invalid dialogue line ({length} bytes, width {width})"
        )
    gap = width - length
    raggedness = RAGGEDNESS_FACTOR * gap * gap
    if last:
        raggedness //= LAST_PAGE_RAGGEDNESS_DIVISOR
    return PAGE_COST + raggedness


def _add_quality_vectors(
    *vectors: tuple[int, ...],
) -> tuple[int, ...]:
    if not vectors:
        return (0,) * 10
    return tuple(
        sum(vector[index] for vector in vectors)
        for index in range(10)
    )


def _boundary_quality_vector(
    left_page: str,
    right_page: str,
) -> tuple[int, ...]:
    """Lexicographic linguistic objective for one page boundary.

    The first component is the total number of strong suspects.  No amount
    of punctuation reward or raggedness improvement can therefore justify
    introducing an extra strong orphan.
    """
    issue = assess_page_boundary(left_page, right_page)
    reasons = issue.reasons if issue is not None else ()
    protected = int(
        any(
            reason.startswith(("split compound name", "trailing abbreviated title"))
            for reason in reasons
        )
    )
    strong_end = int(
        any(
            reason.startswith(
                (
                    "trailing function word",
                    "trailing contraction",
                )
            )
            for reason in reasons
        )
    )
    strong_start = int(
        any(
            reason.startswith("leading complement")
            for reason in reasons
        )
    )
    strong_total = int(
        protected
        or strong_end
        or strong_start
        or (issue is not None and issue.severity == "strong")
    )
    medium = int(
        any(
            reason.startswith(
                (
                    "trailing verb phrase",
                    "leading connective",
                    "trailing modifier",
                )
            )
            for reason in reasons
        )
    )
    singleton = int(
        any(
            reason.startswith("very short trailing fragment")
            for reason in reasons
        )
    )
    sentence = int(_sentence_end(left_page))
    clause = int(_clause_end(left_page))
    unpunctuated = int(not sentence and not clause)
    return (
        strong_total,
        protected,
        medium,
        singleton,
        strong_end,
        strong_start,
        unpunctuated,
        -sentence,
        -clause,
        0,
    )


def _line_quality_vector(
    length: int,
    width: int,
    *,
    last: bool,
) -> tuple[int, ...]:
    scalar = _line_score(length, width, last=last) - PAGE_COST
    return (0, 0, 0, 0, 0, 0, 0, 0, 0, scalar)


def quality_vector_dialogue_pages(
    lines: Sequence[bytes | str],
    layout: str = DIALOGUE_LAYOUT,
) -> tuple[int, ...]:
    """Return the exact lexicographic objective used by the optimiser."""
    if not lines:
        return (0,) * 10
    decoded: list[str] = []
    lengths: list[int] = []
    for index, line in enumerate(lines):
        raw = (
            line.rstrip(b" ")
            if isinstance(line, bytes)
            else encode_game_text(line.rstrip())
        )
        width = dialogue_line_width(index, layout)
        if not raw or len(raw) > width:
            raise ValueError(
                f"page {index + 1} invalid ({len(raw)} > {width})"
            )
        lengths.append(len(raw))
        decoded.append(decode_game_text(raw))

    vector = (0,) * 10
    for index, length in enumerate(lengths):
        last = index == len(lengths) - 1
        vector = _add_quality_vectors(
            vector,
            _line_quality_vector(
                length,
                dialogue_line_width(index, layout),
                last=last,
            ),
        )
        if not last:
            vector = _add_quality_vectors(
                vector,
                _boundary_quality_vector(
                    decoded[index],
                    decoded[index + 1],
                ),
            )
    return vector


def score_dialogue_pages(
    lines: Sequence[bytes | str],
    layout: str = DIALOGUE_LAYOUT,
) -> int:
    """Score an existing page sequence with the same objective as the DP."""
    if not lines:
        return 0
    decoded: list[str] = []
    lengths: list[int] = []
    for index, line in enumerate(lines):
        raw = (
            line.rstrip(b" ")
            if isinstance(line, bytes)
            else encode_game_text(line.rstrip())
        )
        width = dialogue_line_width(index, layout)
        if len(raw) > width:
            raise ValueError(
                f"page {index + 1} too long ({len(raw)} > {width})"
            )
        if not raw:
            raise ValueError(f"page {index + 1} empty")
        lengths.append(len(raw))
        decoded.append(
            decode_game_text(raw)
            if isinstance(raw, bytes)
            else str(raw)
        )

    score = 0
    for index, length in enumerate(lengths):
        last = index == len(lengths) - 1
        score += _line_score(
            length,
            dialogue_line_width(index, layout),
            last=last,
        )
        if not last:
            score += _boundary_score(decoded[index], decoded[index + 1])
    return score


def _encoded_units(text: str) -> tuple[tuple[str, bytes], ...]:
    result: list[tuple[str, bytes]] = []
    for unit in semantic_units(text):
        encoded = encode_game_text(unit)
        if not encoded:
            raise ValueError(f"empty unit after encoding: {unit!r}")
        if len(encoded) > 19:
            raise ValueError(
                "lexical unit too long for a dialogue page "
                f"({len(encoded)} > 19): {unit!r}"
            )
        result.append((unit, encoded))
    return tuple(result)


def _join_encoded_units(
    units: Sequence[tuple[str, bytes]],
    start: int,
    end: int,
) -> bytes:
    return b" ".join(encoded for _, encoded in units[start:end])


def _plan_key(plan: _PartialPlan) -> tuple[object, ...]:
    # Prefer fewer pages at equal cost, then fuller earlier pages, then raw
    # bytes for a completely deterministic final tie break.
    return (
        plan.cost,
        len(plan.lines),
        tuple(-len(line) for line in plan.lines),
        plan.lines,
    )


def _minimum_page_count(
    units: Sequence[tuple[str, bytes]],
    layout: str,
    starting_line_index: int,
) -> int:
    """Return the greedy/minimal number of ordered, width-bounded pages."""
    unit_index = 0
    line_index = starting_line_index
    page_count = 0
    while unit_index < len(units):
        width = dialogue_line_width(line_index, layout)
        end = unit_index + 1
        first = _join_encoded_units(units, unit_index, end)
        if len(first) > width:
            unit, encoded = units[unit_index]
            raise ValueError(
                "unit too long for the current page "
                f"({len(encoded)} > {width}): {unit!r}"
            )
        while end < len(units):
            candidate = _join_encoded_units(
                units,
                unit_index,
                end + 1,
            )
            if len(candidate) > width:
                break
            end += 1
        unit_index = end
        line_index += 1
        page_count += 1
    return page_count


def _optimise_unforced_text(
    text: str,
    layout: str,
    starting_line_index: int = 0,
    *,
    exact_pages: int | None = None,
    max_pages: int | None = None,
    last_page_max_length: int | None = None,
) -> tuple[bytes, ...]:
    units = _encoded_units(text)
    if not units:
        return ()
    minimum_pages = _minimum_page_count(
        units,
        layout,
        starting_line_index,
    )
    if exact_pages is not None:
        if exact_pages < minimum_pages:
            raise ValueError(
                f"{exact_pages} page(s) allowed, "
                f"{minimum_pages} minimum"
            )
        if max_pages is not None and exact_pages > max_pages:
            raise ValueError(
                f"{exact_pages} page(s) required, limit {max_pages}"
            )
    if max_pages is not None and max_pages < minimum_pages:
        raise ValueError(
            f"limit of {max_pages} page(s), "
            f"{minimum_pages} minimum"
        )

    @lru_cache(maxsize=None)
    def solve(
        unit_index: int,
        line_index: int,
        pages_remaining: int | None,
    ) -> _PartialPlan | None:
        if (
            pages_remaining is not None
            and (
                pages_remaining < 1
                or pages_remaining > len(units) - unit_index
            )
        ):
            return None
        width = dialogue_line_width(line_index, layout)
        candidates: list[_PartialPlan] = []
        for end in range(unit_index + 1, len(units) + 1):
            line = _join_encoded_units(units, unit_index, end)
            if len(line) > width:
                break
            if end == len(units):
                if (
                    pages_remaining in {None, 1}
                    and (
                        last_page_max_length is None
                        or len(line) <= last_page_max_length
                    )
                ):
                    candidates.append(
                        _PartialPlan(
                            _line_quality_vector(
                                len(line),
                                width,
                                last=True,
                            ),
                            (line,),
                        )
                    )
                continue

            if pages_remaining == 1:
                continue
            next_pages_remaining = (
                None
                if pages_remaining is None
                else pages_remaining - 1
            )
            remainder = solve(
                end,
                line_index + 1,
                next_pages_remaining,
            )
            if remainder is None:
                continue
            next_page = decode_game_text(remainder.lines[0])
            cost = _add_quality_vectors(
                _line_quality_vector(
                    len(line),
                    width,
                    last=False,
                ),
                _boundary_quality_vector(
                    decode_game_text(line),
                    next_page,
                ),
                remainder.cost,
            )
            candidates.append(
                _PartialPlan(cost, (line,) + remainder.lines)
            )

        if not candidates:
            return None
        return min(candidates, key=_plan_key)

    plans: list[_PartialPlan] = []
    if exact_pages is not None:
        plan = solve(0, starting_line_index, exact_pages)
        if plan is not None:
            plans.append(plan)
    elif max_pages is not None:
        for page_count in range(
            minimum_pages,
            min(max_pages, len(units)) + 1,
        ):
            plan = solve(0, starting_line_index, page_count)
            if plan is not None:
                plans.append(plan)
    else:
        plan = solve(0, starting_line_index, None)
        if plan is not None:
            plans.append(plan)

    if not plans:
        limit = exact_pages if exact_pages is not None else max_pages
        raise ValueError(
            "no compatible dialogue page plan"
            + (f" with {limit} page(s)" if limit is not None else "")
        )
    return min(plans, key=_plan_key).lines


def _semantic_bytes(text: str) -> bytes:
    return b" ".join(
        encode_game_text(unit)
        for unit in semantic_units(text)
    )


def optimise_dialogue_pages(
    text: str,
    layout: str = DIALOGUE_LAYOUT,
    *,
    preserve_forced_pages: bool = True,
    preserve_minimum_page_count: bool = True,
    preserve_encoded_length: bool = True,
    max_pages: int | None = None,
) -> DialoguePagePlan:
    """Return a deterministic minimum-cost page plan.

    Newlines are authoritative page breaks by default.  Each explicitly
    authored page must fit its renderer width; the optimiser never merges it
    with a neighbour.  By default, optimisation is restricted to the greedy
    minimum page count and encoded payload length, so integrating it cannot
    add input waits or consume more repack space.
    """
    if layout not in {DIALOGUE_LAYOUT, INTRO_DIALOGUE_LAYOUT}:
        raise ValueError(f"unknown dialogue layout: {layout!r}")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive")
    if preserve_encoded_length and not preserve_minimum_page_count:
        raise ValueError(
            "preserve_encoded_length requires "
            "preserve_minimum_page_count"
        )
    if not text.strip():
        return DialoguePagePlan(
            lines=(),
            score=0,
            quality_vector=(0,) * 10,
            issues=(),
            semantic_bytes=b"",
            forced_page_breaks=0,
        )

    source_pages = text.splitlines() if preserve_forced_pages else [text]
    if any(not page.strip() for page in source_pages):
        raise ValueError("empty forced dialogue page")

    raw_lines: list[bytes] = []
    if preserve_forced_pages and len(source_pages) > 1:
        for source_page in source_pages:
            units = _encoded_units(source_page)
            raw = _join_encoded_units(units, 0, len(units))
            width = dialogue_line_width(len(raw_lines), layout)
            if len(raw) > width:
                raise ValueError(
                    "forced dialogue page too long "
                    f"({len(raw)} > {width}): {source_page!r}"
                )
            raw_lines.append(raw)
    else:
        greedy_lines = wrap_dialogue_lines_greedy(text, layout)
        minimum_pages = len(greedy_lines)
        exact_pages = (
            minimum_pages
            if preserve_minimum_page_count
            else None
        )
        raw_lines.extend(
            _optimise_unforced_text(
                text,
                layout,
                exact_pages=exact_pages,
                max_pages=max_pages,
                last_page_max_length=(
                    len(greedy_lines[-1])
                    if preserve_encoded_length
                    else None
                ),
            )
        )

    if max_pages is not None and len(raw_lines) > max_pages:
        raise ValueError(
            f"{len(raw_lines)} explicit page(s), limit {max_pages}"
        )

    semantic = _semantic_bytes(text)
    visible = b" ".join(line.rstrip(b" ") for line in raw_lines)
    if visible != semantic:
        raise AssertionError(
            "optimization changed the text or unit order"
        )

    padded = tuple(
        line
        if index == len(raw_lines) - 1
        else line.ljust(dialogue_line_width(index, layout), b" ")
        for index, line in enumerate(raw_lines)
    )
    issues = audit_dialogue_pages(padded)
    return DialoguePagePlan(
        lines=padded,
        score=score_dialogue_pages(padded, layout),
        quality_vector=quality_vector_dialogue_pages(
            padded,
            layout,
        ),
        issues=issues,
        semantic_bytes=semantic,
        forced_page_breaks=max(0, len(source_pages) - 1),
    )


def wrap_dialogue_lines_dp(
    text: str,
    layout: str = DIALOGUE_LAYOUT,
    *,
    preserve_forced_pages: bool = True,
    preserve_minimum_page_count: bool = True,
    preserve_encoded_length: bool = True,
    max_pages: int | None = None,
) -> tuple[bytes, ...]:
    """Convenience API returning only the encoded DP-selected pages."""
    return optimise_dialogue_pages(
        text,
        layout,
        preserve_forced_pages=preserve_forced_pages,
        preserve_minimum_page_count=preserve_minimum_page_count,
        preserve_encoded_length=preserve_encoded_length,
        max_pages=max_pages,
    ).lines


def _issue_counts(
    issues: Iterable[PageBoundaryIssue],
) -> dict[str, int]:
    counts = {"strong": 0, "medium": 0, "weak": 0}
    for issue in issues:
        counts[issue.severity] += 1
    counts["total"] = sum(counts.values())
    return counts


def _weighted_issue_count(counts: dict[str, int]) -> int:
    return (
        counts["strong"] * 100
        + counts["medium"] * 10
        + counts["weak"]
    )


def _issue_report_row(
    issue: PageBoundaryIssue,
) -> dict[str, object]:
    return {
        "boundary_after_page": issue.boundary_after_page,
        "severity": issue.severity,
        "penalty": issue.penalty,
        "reasons": list(issue.reasons),
        "left_page": issue.left_page,
        "right_page": issue.right_page,
    }
