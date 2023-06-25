from __future__ import annotations

import ast
import enum
import itertools
import dataclasses
from typing import List, Tuple, Iterable, Sequence

from asttokens import ASTTokens

from .ast import Position, AffectedNodeFinder
from .exceptions import TuckError

INDENT_SIZE = 4


class MutationType(enum.Enum):
    WRAP = 'wrap'
    WRAP_INDENT = 'wrap_indent'
    INDENT = 'indent'
    TRAILING_COMMA = 'trailing_comma'
    OPEN_PAREN = 'open_paren'
    CLOSE_PAREN = 'close_paren'


WrappingSummary = List[Tuple[Position, MutationType]]


@dataclasses.dataclass(frozen=True, order=True)
class Range:
    start: Position
    end: Position

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(f"Start must be before end ({self.start} > {self.end})")


@dataclasses.dataclass(frozen=True)
class Edit:
    range: Range  # noqa: A003
    new_text: str

    @classmethod
    def insertion(cls, position: Position, new_text: str) -> Edit:
        return cls(Range(position, position), new_text)

    @classmethod
    def deletion(cls, start: Position, end: Position) -> Edit:
        return cls(Range(start, end), '')


class EditsOverlapError(TuckError):
    def __init__(self) -> None:
        super().__init__(
            'edits_overlap',
            "Unable to perform wrapping as the resulting edits contain overlaps. "
            "Consider wrapping the positions one at a time instead. ",
        )


def indent_interim_lines(
    asttokens: ASTTokens,
    wrapping_summary: WrappingSummary,
    root: ast.AST,
) -> WrappingSummary:
    if not wrapping_summary:
        # No changes to be made
        return wrapping_summary

    first_line = wrapping_summary[0][0].line
    last_line = wrapping_summary[-1][0].line

    if first_line == last_line:
        # Everything was on one line to start with, nothing for us to do.
        return wrapping_summary

    # Add indentations for things which were already wrapped somewhat. We're
    # only interested in lines which appear inside nodes that are themselves
    # going to be impacted by the wrapping and assume that outside of those
    # cases things are already in the right place. This assumption may turn out
    # to be invalid, in which case a new approach may be needed here.

    lines_to_indent: set[int] = set()

    for position, mutation_type in wrapping_summary:
        if mutation_type not in (
            MutationType.INDENT,
            MutationType.WRAP_INDENT,
        ):
            continue

        finder = AffectedNodeFinder(position)
        finder.visit(root)

        if finder.found_node is not None:
            node = finder.found_node
            start, end = Position.from_node_start(node), Position.from_node_end(node)
            # Don't consider the first line (we know there's already an edit for
            # that) and do consider the last line.
            lines_to_indent.update(range(start.line + 1, end.line + 1))

    for line in lines_to_indent:
        tok = asttokens.get_token(line, 0)
        if tok.start[0] != line:
            # We've got the last token on the previous line, but we want the
            # first on this line.
            tok = asttokens.next_token(tok, include_extra=True)

            assert tok.start[0] == line, "Token unexpectedly on wrong line"

        if tok.string == '\n':
            # Empty lines don't need indenting
            continue

        wrapping_summary.append(
            (Position(*tok.start), MutationType.INDENT),
        )

    wrapping_summary.sort(key=lambda x: x[0])

    return wrapping_summary


def coalesce(summary: WrappingSummary) -> Iterable[tuple[Position, list[MutationType]]]:
    for pos, grouped in itertools.groupby(summary, lambda x: x[0]):
        yield pos, [x for _, x in grouped]


def all_are_disjoint(grouped: Iterable[list[Range]]) -> bool:
    ranges = sorted(
        Range(min(ranges).start, max(ranges).end)
        for ranges in grouped
        if ranges
    )

    for lower, upper in zip(ranges, ranges[1:]):
        if upper.start < lower.end:
            return False

    return True


def merge_edits(grouped_edits: Iterable[list[Edit]]) -> list[Edit]:
    flat_edits = []
    ranges: list[list[Range]] = []

    for edits in grouped_edits:
        flat_edits.extend(edits)
        ranges.append([x.range for x in edits])

    if not all_are_disjoint(ranges):
        raise EditsOverlapError()

    return flat_edits


def apply_edits(content: str, edits: Sequence[Edit]) -> str:
    new_content = content.splitlines(keepends=True)

    for edit in reversed(edits):
        end_line = edit.range.end.line - 1
        end_col = edit.range.end.col

        right = new_content[end_line][end_col:]

        start_line = edit.range.start.line - 1
        start_col = edit.range.start.col

        left = new_content[start_line][:start_col]

        if edit.new_text.startswith('\n'):
            # TODO: now we have full edit support, rather than just insertions,
            # we should be able handle this at an earlier stage and thus in a
            # way that also works for editors.
            left = left.rstrip()

        new_content[start_line:end_line + 1] = [left + edit.new_text + right]

    return "".join(new_content)
