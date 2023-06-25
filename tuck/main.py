from __future__ import annotations

import ast
from typing import TypeVar

from asttokens import ASTTokens

from .ast import Position, NodeFinder, get_current_indent
from .editing import (
    Edit,
    coalesce,
    INDENT_SIZE,
    merge_edits,
    MutationType,
    WrappingSummary,
    indent_interim_lines,
)
from .wrappers import WRAPPING_FUNCTIONS
from .exceptions import TuckError

TAst = TypeVar('TAst', bound=ast.AST)

WRAPPABLE_NODE_TYPES = tuple(x for x, _ in WRAPPING_FUNCTIONS)


class TargetSyntaxError(TuckError):
    def __init__(self, inner: SyntaxError) -> None:
        super().__init__('target_syntax_error', str(inner))


def get_wrapping_summary(asttokens: ASTTokens, node: ast.AST) -> WrappingSummary:
    for ast_type, func in WRAPPING_FUNCTIONS:
        if isinstance(node, ast_type):
            return func(asttokens, node)

    if not isinstance(node, WRAPPABLE_NODE_TYPES):
        raise AssertionError(f"Unable to get wrapping positions for {node}")

    raise AssertionError(f"Unsupported node type {node}")


def remove_redundant_wrapping_operations(
    asttokens: ASTTokens,
    wrapping_summary: WrappingSummary,
    node_start: Position,
) -> WrappingSummary:
    """
    The initial wrapping summary defines where a correctly tucked statement
    should have various things, however we also need to cope with some or all of
    them already being present.

    This util inspects the actual token stream and removes anything from our
    summary which doesn't need to happen.
    """

    if not wrapping_summary:
        return wrapping_summary

    def should_keep(
        position: Position,
        mutation: MutationType,
        previous: tuple[Position, MutationType] | None,
    ) -> bool:
        if mutation == MutationType.TRAILING_COMMA:
            tok = asttokens.get_token(position.line, position.col)
            if tok.string == ',':
                return False

            prev_token = asttokens.prev_token(tok)
            if prev_token.string == ',':
                return False

        elif mutation in (MutationType.WRAP, MutationType.WRAP_INDENT):
            if previous is not None:
                previous_pos, previous_op = previous
                if previous_pos == position:
                    return True

            tok = asttokens.get_token(position.line, position.col)
            prev_token = asttokens.prev_token(tok, include_extra=True)

            if prev_token.string == '\n':
                return False

        elif mutation == MutationType.INDENT and previous is not None:
            prev_position, prev_mutation = previous

            if prev_mutation in (
                MutationType.WRAP,
                MutationType.WRAP_INDENT,
            ):
                if prev_position == position:
                    return False

        return True

    # If the first operation is to wrap & indent the very start of the node and
    # we're not actually going to do that, then we need to adjust the rest of
    # the operations to account for the lack of indent.
    first = wrapping_summary[0]
    if (
        first == (node_start, MutationType.WRAP_INDENT)
        and not should_keep(*first, previous=None)
    ):
        wrapping_summary = [
            (
                pos,
                MutationType.WRAP if op == MutationType.WRAP_INDENT else op,
            )
            for pos, op in wrapping_summary
            # TODO: work out if this conditional is necessary and add a test
            # case. It *feels* like it should be needed, but the motivating case
            # didn't actually need this.
            if op != MutationType.INDENT
        ]

    wrapping_summary = [
        current
        for prev, current in zip([None, *wrapping_summary], wrapping_summary)
        if should_keep(*current, prev)
    ]

    return wrapping_summary


def determine_node(asttokens: ASTTokens, position: Position) -> ast.AST:
    finder = NodeFinder(position, WRAPPABLE_NODE_TYPES)
    assert asttokens.tree is not None
    finder.visit(asttokens.tree)
    return finder.get_found_node(asttokens)


def determine_edits(asttokens: ASTTokens, node: ast.AST) -> list[Edit]:
    # Note: edits are actually applied in reverse, though we'll generate
    # them forwards.

    current_indent = get_current_indent(asttokens, node)

    mutations = {
        MutationType.WRAP: "\n" + " " * current_indent,
        MutationType.WRAP_INDENT: "\n" + " " * (current_indent + INDENT_SIZE),
        MutationType.INDENT: " " * INDENT_SIZE,
        MutationType.TRAILING_COMMA: ",",
        MutationType.OPEN_PAREN: "(",
        MutationType.CLOSE_PAREN: ")",
    }

    wrapping_summary = get_wrapping_summary(asttokens, node)

    wrapping_summary = remove_redundant_wrapping_operations(
        asttokens,
        wrapping_summary,
        Position.from_node_start(node),
    )

    wrapping_summary = indent_interim_lines(
        asttokens,
        wrapping_summary,
        root=node,
    )

    edits = [
        Edit.insertion(pos, ''.join(mutations[x] for x in mutation_types))
        for pos, mutation_types in coalesce(wrapping_summary)
    ]

    return edits


def process(
    positions: list[Position],
    content: str,
    filename: str,
) -> list[Edit]:
    try:
        asttokens = ASTTokens(content, parse=True, filename=filename)
    except SyntaxError as e:
        # Catch syntax errors within the file we were asked to parse. We trust
        # that the error is not within asttokens itself.
        raise TargetSyntaxError(e) from e

    nodes = set(
        determine_node(asttokens, position)
        for position in positions
    )

    edits = merge_edits(
        determine_edits(asttokens, node)
        for node in nodes
    )

    edits.sort(key=lambda x: x.range)

    return edits
