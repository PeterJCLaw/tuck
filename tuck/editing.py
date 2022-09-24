import enum
import itertools
from typing import Set, List, Tuple, Iterable, Sequence

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

    # Add indentations for things which were already wrapped somewhat. We're
    # only interested in lines which appear inside nodes that are themselves
    # going to be impacted by the wrapping and assume that outside of those
    # cases things are already in the right place. This assumption may turn out
    # to be invalid, in which case a new approach may be needed here.

    lines_to_indent: Set[int] = set()

    for position, mutation_type in wrapping_summary:
        if mutation_type not in (
            MutationType.INDENT,
            MutationType.WRAP_INDENT,
        ):
            continue

        finder = AffectedNodeFinder(position)
        assert asttokens.tree is not None
        finder.visit(asttokens.tree)

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
