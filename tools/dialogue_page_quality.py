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
            flag("strong", f"titre abrégé final « {left_units[-1]} »")
        if (left_last, right_first) in PROTECTED_UNIT_PAIRS:
            flag(
                "strong",
                "nom composé séparé "
                f"« {left_units[-1]} | {right_units[0]} »",
            )
        if left_last in STRONG_END_UNITS:
            flag("strong", f"mot-outil final « {left_units[-1]} »")
        if left_last in MEDIUM_END_CONTRACTIONS:
            flag("medium", f"groupe verbal final « {left_units[-1]} »")
        if left_last.endswith(("qu'", "lorsqu'", "puisqu'")):
            flag("strong", f"contraction finale « {left_units[-1]} »")
        if left_last in MEDIUM_END_UNITS:
            flag("medium", f"modifieur final « {left_units[-1]} »")

        if right_first in STRONG_START_UNITS:
            flag("strong", f"complément initial « {right_units[0]} »")
        elif right_first in MEDIUM_START_UNITS:
            flag("medium", f"liaison initiale « {right_units[0]} »")

        if (
            len(left_units) == 1
            and len(encode_game_text(left_units[0])) <= 8
            and not _clause_end(left_page)
        ):
            flag("weak", f"fragment final très court « {left_units[0]} »")

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
            f"ligne de dialogue invalide ({length} octets, largeur {width})"
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
            reason.startswith(("nom composé", "titre abrégé"))
            for reason in reasons
        )
    )
    strong_end = int(
        any(
            reason.startswith(
                (
                    "mot-outil final",
                    "contraction finale",
                )
            )
            for reason in reasons
        )
    )
    strong_start = int(
        any(
            reason.startswith("complément initial")
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
                    "groupe verbal final",
                    "liaison initiale",
                    "modifieur final",
                )
            )
            for reason in reasons
        )
    )
    singleton = int(
        any(
            reason.startswith("fragment final très court")
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
                f"page {index + 1} invalide ({len(raw)} > {width})"
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
                f"page {index + 1} trop longue ({len(raw)} > {width})"
            )
        if not raw:
            raise ValueError(f"page {index + 1} vide")
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
            raise ValueError(f"unité vide après encodage: {unit!r}")
        if len(encoded) > 19:
            raise ValueError(
                "unité lexicale trop longue pour une page de dialogue "
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
                "unité trop longue pour la page courante "
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
                f"{exact_pages} page(s) autorisée(s), "
                f"{minimum_pages} minimum"
            )
        if max_pages is not None and exact_pages > max_pages:
            raise ValueError(
                f"{exact_pages} page(s) exigée(s), limite {max_pages}"
            )
    if max_pages is not None and max_pages < minimum_pages:
        raise ValueError(
            f"limite de {max_pages} page(s), "
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
            "aucun découpage de dialogue compatible"
            + (f" avec {limit} page(s)" if limit is not None else "")
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
        raise ValueError(f"layout de dialogue inconnu: {layout!r}")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages doit être positif")
    if preserve_encoded_length and not preserve_minimum_page_count:
        raise ValueError(
            "preserve_encoded_length exige "
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
        raise ValueError("page de dialogue forcée vide")

    raw_lines: list[bytes] = []
    if preserve_forced_pages and len(source_pages) > 1:
        for source_page in source_pages:
            units = _encoded_units(source_page)
            raw = _join_encoded_units(units, 0, len(units))
            width = dialogue_line_width(len(raw_lines), layout)
            if len(raw) > width:
                raise ValueError(
                    "page de dialogue forcée trop longue "
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
            f"{len(raw_lines)} page(s) explicite(s), limite {max_pages}"
        )

    semantic = _semantic_bytes(text)
    visible = b" ".join(line.rstrip(b" ") for line in raw_lines)
    if visible != semantic:
        raise AssertionError(
            "l'optimisation a modifié le texte ou l'ordre des unités"
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


def compare_script_dialogue_quality(
    script_path: str | Path,
    *,
    sample_limit: int = 30,
    preserve_minimum_page_count: bool = True,
    preserve_encoded_length: bool = True,
) -> dict[str, object]:
    """Compare the current greedy wrapper with the opt-in DP on one script."""
    from rom_traduction_assistant import (
        pair_for_offset,
        parse_patch_entries,
    )

    rows = [
        entry
        for entry in parse_patch_entries(script_path)
        if entry.layout == DIALOGUE_LAYOUT
    ]
    greedy_pages = 0
    dp_pages = 0
    greedy_bytes = 0
    dp_bytes = 0
    greedy_score = 0
    dp_score = 0
    semantic_mismatches = 0
    forced_page_rows = 0
    improved_rows = 0
    unchanged_rows = 0
    worsened_rows = 0
    greedy_issues_all: list[PageBoundaryIssue] = []
    dp_issues_all: list[PageBoundaryIssue] = []
    samples: list[dict[str, object]] = []
    bytes_by_pair: dict[int, dict[str, int]] = {}
    residual_strong_rows: list[dict[str, object]] = []
    encoded_growth_candidates: list[dict[str, object]] = []

    for entry in rows:
        greedy = wrap_dialogue_lines_greedy(entry.text, entry.layout)
        plan = optimise_dialogue_pages(
            entry.text,
            entry.layout,
            preserve_minimum_page_count=(
                preserve_minimum_page_count
            ),
            preserve_encoded_length=preserve_encoded_length,
        )
        safe_plan = (
            plan
            if (
                preserve_minimum_page_count
                and preserve_encoded_length
            )
            else optimise_dialogue_pages(
                entry.text,
                entry.layout,
                preserve_minimum_page_count=True,
                preserve_encoded_length=True,
            )
        )
        growth_plan = (
            plan
            if (
                preserve_minimum_page_count
                and not preserve_encoded_length
            )
            else optimise_dialogue_pages(
                entry.text,
                entry.layout,
                preserve_minimum_page_count=True,
                preserve_encoded_length=False,
            )
        )
        greedy_issues = audit_dialogue_pages(greedy)
        dp_issues = plan.issues
        greedy_counts = _issue_counts(greedy_issues)
        dp_counts = _issue_counts(dp_issues)
        before_weight = _weighted_issue_count(greedy_counts)
        after_weight = _weighted_issue_count(dp_counts)

        if after_weight < before_weight:
            improved_rows += 1
        elif after_weight > before_weight:
            worsened_rows += 1
        else:
            unchanged_rows += 1

        if "\n" in entry.text or "\r" in entry.text:
            forced_page_rows += 1
        greedy_pages += len(greedy)
        dp_pages += len(plan.lines)
        greedy_bytes += sum(len(line) for line in greedy)
        dp_bytes += sum(len(line) for line in plan.lines)
        pair = pair_for_offset(entry.offset)
        pair_bytes = bytes_by_pair.setdefault(
            pair,
            {"greedy": 0, "dynamic_programming": 0},
        )
        pair_bytes["greedy"] += sum(len(line) for line in greedy)
        pair_bytes["dynamic_programming"] += sum(
            len(line)
            for line in plan.lines
        )
        greedy_score += score_dialogue_pages(greedy, entry.layout)
        dp_score += plan.score
        greedy_issues_all.extend(greedy_issues)
        dp_issues_all.extend(dp_issues)

        strong_issues = [
            issue
            for issue in dp_issues
            if issue.severity == "strong"
        ]
        if strong_issues:
            residual_strong_rows.append(
                {
                    "offset_hex": f"0x{entry.offset:06X}",
                    "prg_pair": pair,
                    "source_text": entry.text,
                    "strong_issue_count": len(strong_issues),
                    "dp_pages": [
                        decode_game_text(line).rstrip()
                        for line in plan.lines
                    ],
                    "strong_boundaries": [
                        _issue_report_row(issue)
                        for issue in strong_issues
                    ],
                }
            )

        safe_strong = sum(
            issue.severity == "strong"
            for issue in safe_plan.issues
        )
        growth_strong = sum(
            issue.severity == "strong"
            for issue in growth_plan.issues
        )
        strong_gain = safe_strong - growth_strong
        safe_size = sum(len(line) for line in safe_plan.lines)
        growth_size = sum(
            len(line)
            for line in growth_plan.lines
        )
        if strong_gain > 0:
            encoded_growth_candidates.append(
                {
                    "offset_hex": f"0x{entry.offset:06X}",
                    "prg_pair": pair,
                    "source_text": entry.text,
                    "delta_encoded_bytes": growth_size - safe_size,
                    "strong_before": safe_strong,
                    "strong_after": growth_strong,
                    "strong_gain": strong_gain,
                    "safe_encoded_bytes": safe_size,
                    "growth_encoded_bytes": growth_size,
                    "safe_pages": [
                        decode_game_text(line).rstrip()
                        for line in safe_plan.lines
                    ],
                    "growth_pages": [
                        decode_game_text(line).rstrip()
                        for line in growth_plan.lines
                    ],
                }
            )

        expected_semantic = _semantic_bytes(entry.text)
        greedy_semantic = b" ".join(
            line.rstrip(b" ")
            for line in greedy
        )
        dp_semantic = b" ".join(
            line.rstrip(b" ")
            for line in plan.lines
        )
        if (
            greedy_semantic != expected_semantic
            or dp_semantic != expected_semantic
        ):
            semantic_mismatches += 1

        if before_weight > after_weight:
            samples.append(
                {
                    "offset_hex": f"0x{entry.offset:06X}",
                    "greedy_issue_counts": greedy_counts,
                    "dp_issue_counts": dp_counts,
                    "greedy_pages": [
                        decode_game_text(line).rstrip()
                        for line in greedy
                    ],
                    "dp_pages": [
                        decode_game_text(line).rstrip()
                        for line in plan.lines
                    ],
                }
            )

    greedy_counts = _issue_counts(greedy_issues_all)
    dp_counts = _issue_counts(dp_issues_all)
    samples.sort(
        key=lambda row: (
            -_weighted_issue_count(row["greedy_issue_counts"]),
            row["offset_hex"],
        )
    )
    residual_strong_rows.sort(
        key=lambda row: row["offset_hex"]
    )
    encoded_growth_candidates.sort(
        key=lambda row: row["offset_hex"]
    )
    growth_summary_by_pair: dict[int, dict[str, int]] = {}
    for row in encoded_growth_candidates:
        pair = int(row["prg_pair"])
        summary = growth_summary_by_pair.setdefault(
            pair,
            {
                "candidate_rows": 0,
                "delta_encoded_bytes": 0,
                "strong_gain": 0,
            },
        )
        summary["candidate_rows"] += 1
        summary["delta_encoded_bytes"] += int(
            row["delta_encoded_bytes"]
        )
        summary["strong_gain"] += int(row["strong_gain"])
    return {
        "schema_version": 1,
        "script": str((ROM_DIR / script_path).resolve()),
        "common_dialogue_rows": len(rows),
        "forced_page_rows": forced_page_rows,
        "semantic_mismatches": semantic_mismatches,
        "configuration": {
            "preserve_minimum_page_count": (
                preserve_minimum_page_count
            ),
            "preserve_encoded_length": preserve_encoded_length,
        },
        "greedy": {
            "pages": greedy_pages,
            "encoded_bytes": greedy_bytes,
            "score": greedy_score,
            "issue_counts": greedy_counts,
        },
        "dynamic_programming": {
            "pages": dp_pages,
            "encoded_bytes": dp_bytes,
            "score": dp_score,
            "issue_counts": dp_counts,
        },
        "delta_dp_minus_greedy": {
            "pages": dp_pages - greedy_pages,
            "encoded_bytes": dp_bytes - greedy_bytes,
            "score": dp_score - greedy_score,
            "strong_issues": (
                dp_counts["strong"] - greedy_counts["strong"]
            ),
            "medium_issues": (
                dp_counts["medium"] - greedy_counts["medium"]
            ),
            "weak_issues": dp_counts["weak"] - greedy_counts["weak"],
        },
        "rows": {
            "improved": improved_rows,
            "unchanged": unchanged_rows,
            "worsened": worsened_rows,
        },
        "encoded_bytes_by_prg_pair": {
            str(pair): {
                **values,
                "delta": (
                    values["dynamic_programming"]
                    - values["greedy"]
                ),
            }
            for pair, values in sorted(bytes_by_pair.items())
        },
        "residual_strong_rows": residual_strong_rows,
        "encoded_growth_candidates": encoded_growth_candidates,
        "encoded_growth_candidate_summary": {
            "candidate_rows": len(encoded_growth_candidates),
            "delta_encoded_bytes": sum(
                int(row["delta_encoded_bytes"])
                for row in encoded_growth_candidates
            ),
            "strong_gain": sum(
                int(row["strong_gain"])
                for row in encoded_growth_candidates
            ),
            "by_prg_pair": {
                str(pair): values
                for pair, values in sorted(
                    growth_summary_by_pair.items()
                )
            },
        },
        "samples": samples[:sample_limit],
        "limits": [
            (
                "Le score est une heuristique française, pas une analyse "
                "grammaticale ou sémantique complète."
            ),
            (
                "Les noms propres, locutions, effets de style et changements "
                "de locuteur peuvent produire des faux positifs ou négatifs."
            ),
            (
                "Le mode d'intégration par défaut conserve exactement le "
                "nombre minimal de pages et interdit toute hausse de la "
                "longueur encodée. Les modes d'audit peuvent lever l'une ou "
                "l'autre contrainte."
            ),
            (
                "Les retours ligne explicites sont autoritaires et ne sont "
                "pas déplacés automatiquement."
            ),
            (
                "Cet audit couvre le renderer de dialogue terrain; menus, "
                "combats, Pokédex et textes graphiques ont d'autres contrats."
            ),
            (
                "Une relecture humaine et un parcours dynamique Mesen restent "
                "nécessaires avant de qualifier la traduction de fluide."
            ),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare le découpage glouton et un découpage français par "
            "programmation dynamique pour les dialogues terrain."
        )
    )
    parser.add_argument("--script", default="script.py")
    parser.add_argument("--output")
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument(
        "--allow-extra-pages",
        action="store_true",
        help=(
            "autorise le score linguistique à ajouter des pages; "
            "désactivé par défaut pour conserver la taille"
        ),
    )
    parser.add_argument(
        "--allow-encoded-growth",
        action="store_true",
        help=(
            "conserve Nmin mais autorise une dernière page plus longue; "
            "utile uniquement pour l'audit"
        ),
    )
    args = parser.parse_args()

    report = compare_script_dialogue_quality(
        args.script,
        sample_limit=max(0, args.samples),
        preserve_minimum_page_count=not args.allow_extra_pages,
        preserve_encoded_length=not (
            args.allow_extra_pages
            or args.allow_encoded_growth
        ),
    )
    if args.output:
        output = (
            Path(args.output)
            if Path(args.output).is_absolute()
            else ROM_DIR / args.output
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"- Rapport : {output}")

    greedy = report["greedy"]
    dp = report["dynamic_programming"]
    delta = report["delta_dp_minus_greedy"]
    print("Qualité des pages de dialogue terrain")
    print(f"- Dialogues : {report['common_dialogue_rows']}")
    print(
        "- Pages minimales conservées : "
        f"{report['configuration']['preserve_minimum_page_count']}"
    )
    print(
        "- Longueur encodée non croissante : "
        f"{report['configuration']['preserve_encoded_length']}"
    )
    print(
        "- Greedy : "
        f"{greedy['pages']} pages, {greedy['encoded_bytes']} octets, "
        f"suspects {greedy['issue_counts']}"
    )
    print(
        "- DP : "
        f"{dp['pages']} pages, {dp['encoded_bytes']} octets, "
        f"suspects {dp['issue_counts']}"
    )
    print(f"- Delta DP-greedy : {delta}")
    print(f"- Lignes sémantiques modifiées : {report['semantic_mismatches']}")
    return 1 if report["semantic_mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
