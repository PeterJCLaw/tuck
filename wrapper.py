#!/usr/bin/env python

import ast
import enum
import difflib
import argparse
import functools
from typing import List, Tuple, Iterable

from asttokens import ASTTokens

INDENT_SIZE = 4


class MutationType(enum.Enum):
    WRAP = 'wrap'
    WRAP_INDENT = 'wrap_indent'
    TRAILING_COMMA = 'trailing_comma'


WrappingSummary = List[Tuple['Position', MutationType]]


@functools.total_ordering
class Position:
    @classmethod
    def from_node_start(cls, node: ast.AST) -> 'Position':
        return cls(
            *node.first_token.start,  # type: ignore # `first_token` is added by asttokens
        )

    @classmethod
    def from_node_end(cls, node: ast.AST) -> 'Position':
        return cls(
            *node.last_token.end,  # type: ignore # `last_token` is added by asttokens
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
        (Position(pos.line, pos.col + 1), MutationType.WRAP_INDENT)
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
    summary = wrap_node_start_positions(node.args + node.keywords)
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


def determine_insertions(asttokens: ASTTokens, position: Position) -> List[Tuple[Position, str]]:
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


def apply_insertions(content: str, insertions: List[Tuple[Position, str]]) -> str:
    new_content = content.splitlines(keepends=True)

    for position, insertion in reversed(insertions):
        line = position.line - 1
        col = position.col - 1

        text = new_content[line]
        new_content[line] = text[:col].rstrip() + insertion + text[col:]

    return "".join(new_content)


def process(position: Position, content: str, filename: str) -> str:
    asttokens = ASTTokens(content, parse=True, filename=filename)

    insertions = determine_insertions(asttokens, position)

    new_content = apply_insertions(content, insertions)

    return new_content


def parse_position(position: str) -> Position:
    line, col = [int(x) for x in position.split(':')]
    return Position(line, col)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=argparse.FileType(mode='r'))
    parser.add_argument('--position', required=True, type=parse_position)
    parser.add_argument('--mode', choices=('wrap', 'unwrap'), default='wrap')
    parser.add_argument('--diff', action='store_true')
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    content = args.file.read()

    new_content = process(args.position, content, args.file.name)

    if args.diff:
        print("".join(difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            'original',
            'formatted',
        )))
    else:
        print(new_content)


if __name__ == '__main__':
    main(parse_args())
