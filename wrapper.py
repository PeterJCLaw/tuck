#!/usr/bin/env python3

import ast
import enum
import json
import difflib
import argparse
import functools
from typing import Dict, List, Tuple, Union, Iterable

from asttokens import ASTTokens

INDENT_SIZE = 4


class MutationType(enum.Enum):
    WRAP = 'wrap'
    WRAP_INDENT = 'wrap_indent'
    TRAILING_COMMA = 'trailing_comma'


WrappingSummary = List[Tuple['Position', MutationType]]
Insertion = Tuple['Position', str]

LSP_Range = Dict[str, Dict[str, int]]
LSP_TextEdit = Dict[str, Union[str, LSP_Range]]


@functools.total_ordering
class Position:
    """
    A position within a document, compatible with Python AST positions.

    Line numbers are one-based, columns are zero-based.
    """

    @classmethod
    def from_node_start(cls, node: ast.AST) -> 'Position':
        return cls(
            *node.first_token.start,  # type: ignore # `first_token` is added by asttokens
        )

    @classmethod
    def from_node_end(cls, node: ast.AST) -> 'Position':
        return cls(
            *node.last_token.start,  # type: ignore # `last_token` is added by asttokens
        )

    def __init__(self, line: int, col: int) -> None:
        self.line = line
        self.col = col

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented

        return self.line == other.line and self.col == other.col

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented

        if self.line < other.line:
            return True

        if self.line > other.line:
            return False

        return self.col < other.col

    def __repr__(self) -> str:
        return 'Position(line={}, col={})'.format(self.line, self.col)


class NodeFinder(ast.NodeVisitor):
    def __init__(self, position: Position) -> None:
        self.target_position = position

        self.node_stack = []  # type: List[ast.AST]

        self.found = False

    @property
    def found_node(self) -> ast.AST:
        if not self.found:
            raise ValueError("No node found!")

        try:
            return next(
                node
                for node in reversed(self.node_stack)
                if isinstance(node, WRAPPABLE_NODE_TYPES)
            )
        except StopIteration:
            raise ValueError(
                "No supported nodes found (stack: {})".format(
                    " > ".join(type(x).__name__ for x in self.node_stack),
                ),
            ) from None

    def get_indent_size(self) -> int:
        if not self.found:
            raise ValueError("No node found!")

        # Ideally the first match on the given line
        found_node = self.found_node
        for node in self.node_stack:
            position = Position.from_node_start(node)
            if position.line == found_node.lineno:
                return position.col

        # Fall back to the most recent column
        return self.node_stack[-1].col_offset

    def generic_visit(self, node):
        if self.found:
            return

        if not hasattr(node, 'lineno'):
            super().generic_visit(node)
            return

        start = Position.from_node_start(node)
        end = Position.from_node_end(node)

        if end < self.target_position:
            # we're clear before the target
            return

        if start > self.target_position:
            # we're clear after the target
            return

        # we're on the path to finding the desired node
        self.node_stack.append(node)

        super().generic_visit(node)

        self.found = True


WRAPPING_FUNTIONS = []


def node_wrapper(ast_type):
    def wrapper(func):
        WRAPPING_FUNTIONS.append((ast_type, func))
        return func
    return wrapper


def node_start_positions(nodes: Iterable[ast.AST]) -> List[Position]:
    return [Position.from_node_start(x) for x in nodes]


def wrap_node_start_positions(nodes: Iterable[ast.AST]) -> WrappingSummary:
    return [
        (Position(pos.line, pos.col), MutationType.WRAP_INDENT)
        for pos in node_start_positions(nodes)
    ]


def append_trailing_comma(summary: WrappingSummary, node: ast.AST) -> WrappingSummary:
    summary.append((
        Position.from_node_end(node),
        MutationType.TRAILING_COMMA,
    ))
    return summary


def append_wrap_end(summary: WrappingSummary, node: ast.AST) -> WrappingSummary:
    summary.append((
        Position.from_node_end(node),
        MutationType.WRAP,
    ))
    return summary


@node_wrapper(ast.Call)
def wrap_call(asttokens: ASTTokens, node: ast.Call) -> WrappingSummary:
    named_args = node.keywords
    kwargs = None
    if named_args and named_args[-1].arg is None:
        named_args = node.keywords[:-1]
        kwargs = node.keywords[-1]

    summary = wrap_node_start_positions(node.args + named_args)

    if kwargs is not None:
        kwargs_stars = asttokens.prev_token(kwargs.first_token)
        summary.append((Position(*kwargs_stars.start), MutationType.WRAP_INDENT))

    append_trailing_comma(summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.Dict)
def wrap_dict(asttokens: ASTTokens, node: ast.Dict) -> WrappingSummary:
    summary = wrap_node_start_positions(node.keys)
    append_trailing_comma(summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.DictComp)
def wrap_dict_comp(asttokens: ASTTokens, node: ast.DictComp) -> WrappingSummary:
    summary = wrap_node_start_positions([node.key, *node.generators])
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.FunctionDef)
def wrap_function_def(asttokens: ASTTokens, node: ast.FunctionDef) -> WrappingSummary:
    positions = node_start_positions(node.args.args)

    if node.args.vararg:
        # Account for the * before the name
        args_star = asttokens.prev_token(node.args.vararg.first_token)
        positions.append(Position(*args_star.start))

    if node.args.kwonlyargs:
        # Account for the unnamed *
        if not node.args.vararg:
            comma = asttokens.prev_token(node.args.kwonlyargs[0].first_token)
            args_star = asttokens.prev_token(comma)
            positions.append(Position(*args_star.start))

        positions += node_start_positions(node.args.kwonlyargs)

    if node.args.kwarg:
        # Account for the ** before the name
        kwargs_stars = asttokens.prev_token(node.args.kwarg.first_token)
        positions.append(Position(*kwargs_stars.start))

    summary = [
        (Position(pos.line, pos.col), MutationType.WRAP_INDENT)
        for pos in positions
    ]

    close_paren = asttokens.next_token(node.args.last_token)
    args_end = Position(*close_paren.start)

    if not (node.args.kwonlyargs or node.args.kwarg):
        summary.append((args_end, MutationType.TRAILING_COMMA))

    summary.append((args_end, MutationType.WRAP))

    return summary


@node_wrapper(ast.List)
def wrap_list(asttokens: ASTTokens, node: ast.List) -> WrappingSummary:
    summary = wrap_node_start_positions(node.elts)
    append_trailing_comma(summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.ListComp)
def wrap_list_comp(asttokens: ASTTokens, node: ast.ListComp) -> WrappingSummary:
    summary = wrap_node_start_positions([node.elt, *node.generators])
    append_wrap_end(summary, node)
    return summary


WRAPPABLE_NODE_TYPES = tuple(x for x, _ in WRAPPING_FUNTIONS)


def get_wrapping_summary(asttokens: ASTTokens, node: ast.AST) -> WrappingSummary:
    for ast_type, func in WRAPPING_FUNTIONS:
        if isinstance(node, ast_type):
            return func(asttokens, node)

    if not isinstance(node, WRAPPABLE_NODE_TYPES):
        raise AssertionError("Unable to get wrapping positions for {}".format(node))

    raise AssertionError("Unsupported node type {}".format(node))


def determine_insertions(asttokens: ASTTokens, position: Position) -> List[Insertion]:
    finder = NodeFinder(position)
    finder.visit(asttokens.tree)

    node = finder.found_node

    # Note: insertions are actually applied in reverse, though we'll generate
    # them forwards:
    #  - Leave the { where it is
    #  - Insert a newline plus indent before each of the keys
    #  - Leave the values unchanged
    #  - Wrap the }

    current_indent = finder.get_indent_size()

    mutations = {
        MutationType.WRAP: "\n" + " " * current_indent,
        MutationType.WRAP_INDENT: "\n" + " " * (current_indent + INDENT_SIZE),
        MutationType.TRAILING_COMMA: ",",
    }

    wrapping_summary = get_wrapping_summary(asttokens, node)

    insertions = [
        (pos, mutations[mutation_type])
        for pos, mutation_type in wrapping_summary
    ]

    return insertions


def apply_insertions(content: str, insertions: List[Insertion]) -> str:
    new_content = content.splitlines(keepends=True)

    for position, insertion in reversed(insertions):
        line = position.line - 1
        col = position.col

        text = new_content[line]
        new_content[line] = text[:col].rstrip() + insertion + text[col:]

    return "".join(new_content)


def process(position: Position, content: str, filename: str) -> Tuple[str, List[Insertion]]:
    asttokens = ASTTokens(content, parse=True, filename=filename)

    insertions = determine_insertions(asttokens, position)

    new_content = apply_insertions(content, insertions)

    return new_content, insertions


def insertion_as_lsp_data(position: Position, new_text: str) -> LSP_TextEdit:
    """
    Convert an expanded `Insertion` to a Language Server Protocol compatible
    dictionaries for display as JSON.

    Note: in LSP line numbers are zero-based, while our `Position`s are
    one-based.
    """
    pos = {'line': position.line - 1, 'character': position.col}
    return {
        'range': {'start': pos, 'end': pos},
        'newText': new_text,
    }


def print_edits(insertions: List[Insertion]) -> None:
    data = [insertion_as_lsp_data(*x) for x in insertions]
    print(json.dumps(data))


def parse_position(position: str) -> Position:
    line, col = [int(x) for x in position.split(':')]
    return Position(line, col)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Wrap the python statement at a given position within a text document.",
    )
    parser.add_argument(
        'file',
        type=argparse.FileType(mode='r'),
        help="The file to read from. Use '-' to read from STDIN."
    )
    parser.add_argument(
        '--position',
        required=True,
        type=parse_position,
        help=(
            "The position within the file to wrap at. "
            "Express in LINE:COL format, with 1-based line numbers."
        ),
    )
    parser.add_argument('--mode', choices=('wrap', 'unwrap'), default='wrap')
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--diff',
        action='store_true',
        help="Print the changes as a unified diff rather than printing the new content.",
    )
    group.add_argument(
        '--edits',
        action='store_true',
        help=(
            "Print the changes as language-server-protocol compatible edits, "
            "rather than printing the new content."
        ),
    )
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    content = args.file.read()

    new_content, insertions = process(args.position, content, args.file.name)

    if args.diff:
        print("".join(difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            'original',
            'formatted',
        )))
    elif args.edits:
        print_edits(insertions)
    else:
        print(new_content)


if __name__ == '__main__':
    main(parse_args())
