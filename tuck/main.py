import ast
from typing import List, Tuple, TypeVar, Optional

from asttokens import ASTTokens  # type: ignore[import]

from .ast import Position, NodeFinder, get_current_indent
from .editing import (
    coalesce,
    Insertion,
    INDENT_SIZE,
    MutationType,
    WrappingSummary,
    merge_insertions,
    indent_interim_lines,
)
from .wrappers import WRAPPING_FUNTIONS
from .exceptions import TuckError

TAst = TypeVar('TAst', bound=ast.AST)

WRAPPABLE_NODE_TYPES = tuple(x for x, _ in WRAPPING_FUNTIONS)


class TargetSyntaxError(TuckError):
    def __init__(self, inner: SyntaxError) -> None:
        super().__init__('target_syntax_error', str(inner))


def get_wrapping_summary(asttokens: ASTTokens, node: ast.AST) -> WrappingSummary:
    for ast_type, func in WRAPPING_FUNTIONS:
        if isinstance(node, ast_type):
            return func(asttokens, node)

    if not isinstance(node, WRAPPABLE_NODE_TYPES):
        raise AssertionError("Unable to get wrapping positions for {}".format(node))

    raise AssertionError("Unsupported node type {}".format(node))


def remove_redunant_wrapping_operations(
    asttokens: ASTTokens,
    wrapping_summary: WrappingSummary,
) -> WrappingSummary:
    """
    The initial wrapping summary defines where a correctly tucked statement
    should have various things, however we also need to cope with some or all of
    them already being present.

    This util inspects the actual token stream and removes anything from our
    summary which doesn't need to happen.
    """

    def should_keep(
        position: Position,
        mutation: MutationType,
        previous: Optional[Tuple[Position, MutationType]],
    ) -> bool:
        if mutation == MutationType.TRAILING_COMMA:
            tok = asttokens.get_token(position.line, position.col)
            prev_token = asttokens.prev_token(tok)

            if prev_token.string == ',':
                return False

        elif mutation in (MutationType.WRAP, MutationType.WRAP_INDENT):
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

    wrapping_summary = [
        current
        for prev, current in zip([None, *wrapping_summary], wrapping_summary)
        if should_keep(*current, prev)
    ]

    return wrapping_summary


def determine_insertions(asttokens: ASTTokens, position: Position) -> List[Insertion]:
    finder = NodeFinder(position, WRAPPABLE_NODE_TYPES)
    finder.visit(asttokens.tree)

    node = finder.found_node

    # Note: insertions are actually applied in reverse, though we'll generate
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

    wrapping_summary = indent_interim_lines(asttokens, wrapping_summary)

    wrapping_summary = remove_redunant_wrapping_operations(asttokens, wrapping_summary)

    insertions = [
        (pos, ''.join(mutations[x] for x in mutation_types))
        for pos, mutation_types in coalesce(wrapping_summary)
    ]

    return insertions


def process(
    positions: List[Position],
    content: str,
    filename: str,
) -> List[Insertion]:
    try:
        asttokens = ASTTokens(content, parse=True, filename=filename)
    except SyntaxError as e:
        # Catch syntax errors within the file we were asked to parse. We trust
        # that the error is not within asttokens itself.
        raise TargetSyntaxError(e) from e

    insertions = merge_insertions(
        determine_insertions(asttokens, position)
        for position in positions
    )

    return insertions
