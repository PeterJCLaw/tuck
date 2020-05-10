import ast
from typing import List, Tuple, TypeVar

from asttokens import ASTTokens  # type: ignore[import]

from .ast import Position, NodeFinder, get_current_indent
from .editing import (
    coalesce,
    Insertion,
    INDENT_SIZE,
    MutationType,
    WrappingSummary,
    apply_insertions,
    merge_insertions,
    indent_interim_lines,
)
from .wrappers import WRAPPING_FUNTIONS

TAst = TypeVar('TAst', bound=ast.AST)

WRAPPABLE_NODE_TYPES = tuple(x for x, _ in WRAPPING_FUNTIONS)


def get_wrapping_summary(asttokens: ASTTokens, node: ast.AST) -> WrappingSummary:
    for ast_type, func in WRAPPING_FUNTIONS:
        if isinstance(node, ast_type):
            return func(asttokens, node)

    if not isinstance(node, WRAPPABLE_NODE_TYPES):
        raise AssertionError("Unable to get wrapping positions for {}".format(node))

    raise AssertionError("Unsupported node type {}".format(node))


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
        MutationType.TRAILING_COMMA: ",",
        MutationType.OPEN_PAREN: "(",
        MutationType.CLOSE_PAREN: ")",
    }

    wrapping_summary = get_wrapping_summary(asttokens, node)

    insertions = [
        (pos, ''.join(mutations[x] for x in mutation_types))
        for pos, mutation_types in coalesce(wrapping_summary)
    ]

    indent_interim_lines(insertions)

    return insertions


def process(
    positions: List[Position],
    content: str,
    filename: str,
) -> Tuple[str, List[Insertion]]:
    asttokens = ASTTokens(content, parse=True, filename=filename)

    insertions = merge_insertions(
        determine_insertions(asttokens, position)
        for position in positions
    )

    new_content = apply_insertions(content, insertions)

    return new_content, insertions
