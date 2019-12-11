#!/usr/bin/env python

import ast
import difflib
import argparse
import functools
from typing import List, Tuple

import asttokens


@functools.total_ordering
class Position:
    @classmethod
    def from_node_start(cls, node: ast.AST) -> 'Position':
        return cls(node.lineno, node.col_offset)

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

        return self.node_stack[-1]

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

        if not self.found:
            has_children = bool(tuple(ast.iter_child_nodes(node)))
            if not has_children:
                # we're the bottom node which contains the target position and
                # we have no children. We are therefore a leaf and should be
                # discarded.
                self.node_stack.pop()

        self.found = True


def determine_insertions(tree: ast.AST, position: Position) -> List[Tuple[Position, str]]:
    finder = NodeFinder(position)
    finder.visit(tree)

    node = finder.found_node

    assert isinstance(node, ast.Dict), "Only supports dicts for now, not {}".format(node)

    # Note: insertions are actually applied in reverse, though we'll generate
    # them forwards:
    #  - Leave the { where it is
    #  - Insert a newline plus indent before each of the keys
    #  - Leave the values unchanged
    #  - Wrap the }

    def insertion_position(node: ast.AST) -> Position:
        return Position(node.lineno, node.col_offset + 1)

    current_indent = finder.get_indent_size()
    wrap = "\n" + " " * current_indent
    wrap_indented = "\n" + " " * (current_indent + 4) # TODO: Make 4 variable

    insertions = []  # type: List[Tuple[Position, str]]

    last_line = node.lineno
    for key_node in node.keys:
        if key_node.lineno == last_line:
            insertions.append((insertion_position(key_node), wrap_indented))

    end_pos = Position.from_node_end(node)

    # TODO: conditional on whether it's already wrapped?
    insertions.append((end_pos, ','))
    insertions.append((end_pos, wrap))

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
    tree = asttokens.ASTTokens(content, parse=True, filename=filename).tree

    insertions = determine_insertions(tree, position)

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
