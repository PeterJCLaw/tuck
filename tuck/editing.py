import enum
import itertools
from typing import List, Tuple, Iterable

from .ast import Position

INDENT_SIZE = 4


class MutationType(enum.Enum):
    WRAP = 'wrap'
    WRAP_INDENT = 'wrap_indent'
    TRAILING_COMMA = 'trailing_comma'
    OPEN_PAREN = 'open_paren'
    CLOSE_PAREN = 'close_paren'


WrappingSummary = List[Tuple['Position', MutationType]]
Insertion = Tuple['Position', str]


class EditsOverlapError(Exception):
    pass


def indent_interim_lines(insertions: List[Insertion]) -> None:
    if not insertions:
        # No changes to be made
        return

    first_line = insertions[0][0].line
    last_line = insertions[-1][0].line

    if first_line == last_line:
        # Everything was on one line to start with, nothing for us to do.
        return

    # Add indentations for things which were already wrapped somewhat. We don't
    # want to touch the first line (since that's the line we're splitting up),
    # but we do want to indent anything which was already on the last line we're
    # touching.
    for line in range(first_line + 1, last_line + 1):
        insertions.append(
            (Position(line, 0), " " * INDENT_SIZE),
        )

    insertions.sort(key=lambda x: x[0])


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


def apply_insertions(content: str, insertions: List[Insertion]) -> str:
    new_content = content.splitlines(keepends=True)

    for position, insertion in reversed(insertions):
        line = position.line - 1
        col = position.col

        text = new_content[line]
        # TODO: This rstrip() doesn't appear in the --edits output, leading to
        # incorect wrapping in editors.
        new_content[line] = text[:col].rstrip() + insertion + text[col:]

    return "".join(new_content)
