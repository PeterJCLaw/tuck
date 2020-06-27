import enum
import itertools
from typing import List, Tuple, Iterable, Sequence

from asttokens import ASTTokens  # type: ignore[import]

from .ast import Position
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
Insertion = Tuple[Position, str]


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
) -> WrappingSummary:
    if not wrapping_summary:
        # No changes to be made
        return wrapping_summary

    first_line = wrapping_summary[0][0].line
    last_line = wrapping_summary[-1][0].line

    if first_line == last_line:
        # Everything was on one line to start with, nothing for us to do.
        return wrapping_summary

    # Add indentations for things which were already wrapped somewhat. We don't
    # want to touch the first line (since that's the line we're splitting up),
    # but we do want to indent anything which was already on the last line we're
    # touching.
    for line in range(first_line + 1, last_line + 1):
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


def coalesce(summary: WrappingSummary) -> Iterable[Tuple[Position, List[MutationType]]]:
    for pos, grouped in itertools.groupby(summary, lambda x: x[0]):
        yield pos, [x for _, x in grouped]


def all_are_disjoint(grouped: Iterable[List[Position]]) -> bool:
    ranges = sorted(
        (min(positions), max(positions))
        for positions in grouped
        if positions
    )

    for (_, lower_end), (upper_start, _) in zip(ranges, ranges[1:]):
        if upper_start < lower_end:
            return False

    return True


def merge_insertions(grouped_insertions: Iterable[List[Insertion]]) -> List[Insertion]:
    flat_insertions = []
    positions = []  # type: List[List[Position]]

    for insertions in grouped_insertions:
        flat_insertions.extend(insertions)
        positions.append([x for x, _ in insertions])

    if not all_are_disjoint(positions):
        raise EditsOverlapError()

    return flat_insertions


def apply_insertions(content: str, insertions: Sequence[Insertion]) -> str:
    new_content = content.splitlines(keepends=True)

    for position, insertion in reversed(insertions):
        line = position.line - 1
        col = position.col

        text = new_content[line]
        left, right = text[:col], text[col:]

        if insertion.startswith('\n'):
            # TODO: ideally we'd have full edit support, rather than just
            # insertions, which would mean we could handle this at an earler
            # stage and thus in a way that also works for editors.
            left = left.rstrip()

        new_content[line] = left + insertion + right

    return "".join(new_content)
