import ast
import token
import functools
from typing import List, Type, Tuple, TypeVar

import asttokens.util  # type: ignore[import]
from asttokens import ASTTokens

from .exceptions import TuckError

TAst = TypeVar('TAst', bound=ast.AST)


def _first_token(node: ast.AST) -> asttokens.util.Token:
    return node.first_token  # type: ignore[attr-defined]


def _last_token(node: ast.AST) -> asttokens.util.Token:
    return node.last_token  # type: ignore[attr-defined]


@functools.total_ordering
class Position:
    """
    A position within a document, compatible with Python AST positions.

    Line numbers are one-based, columns are zero-based.
    """

    @classmethod
    def from_node_start(cls, node: ast.AST) -> 'Position':
        return cls(*_first_token(node).start)

    @classmethod
    def from_node_end(cls, node: ast.AST) -> 'Position':
        return cls(*_last_token(node).start)

    def __init__(self, line: int, col: int) -> None:
        self.line = line
        self.col = col

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented

        return self.line == other.line and self.col == other.col

    def __lt__(self, other: 'Position') -> bool:
        if not isinstance(other, Position):
            return NotImplemented  # type: ignore  # unreachable

        if self.line < other.line:
            return True

        if self.line > other.line:
            return False

        return self.col < other.col

    def __repr__(self) -> str:
        return 'Position(line={}, col={})'.format(self.line, self.col)


class NodeSearchError(TuckError, ValueError):
    """Base type for all node search errors."""


class NoNodeFoundError(NodeSearchError):
    def __init__(self) -> None:
        super().__init__('no_node_found', "No AST nodes were found!")


class NoSuitableNodeFoundError(NodeSearchError):
    def __init__(self, node_stack: List[ast.AST]) -> None:
        self.node_stack = node_stack
        super().__init__(
            'no_suitable_node_found',
            "No suitable node found (stack: {})".format(
                " > ".join(type(x).__name__ for x in node_stack),
            ),
        )


class NoSupportedNodeFoundError(NodeSearchError):
    def __init__(self, node_stack: List[ast.AST]) -> None:
        self.node_stack = node_stack
        super().__init__(
            'no_supported_node_found',
            "No supported nodes found (stack: {})".format(
                " > ".join(type(x).__name__ for x in node_stack),
            ),
        )


class NodeFinder(ast.NodeVisitor):
    def __init__(self, position: Position, node_types: Tuple[Type[ast.AST], ...]) -> None:
        self.target_position = position
        self.target_node_types = node_types

        self.node_stack = []  # type: List[ast.AST]

        self.found = False

    def get_filtered_stack(self) -> List[ast.AST]:
        """
        In some cases we want to skip over the actual place in the AST and
        onwards to a parent node. This filtering achieves that.

        For convenience we also return the stack in reversed order, so that the
        nodes closest to the target position are at the front of the list.
        """
        reversed_stack = list(reversed(self.node_stack))

        offset = 0
        for index, node in enumerate(reversed_stack):
            if isinstance(node, ast.Attribute):
                # We want to skip self and immediate parent
                offset = index + 2
            else:
                break

        return reversed_stack[offset:]

    @property
    def found_node(self) -> ast.AST:
        if not self.found:
            raise NoNodeFoundError()

        reversed_stack = self.get_filtered_stack()

        for node, prev_node in zip(
            reversed_stack,
            [None, *reversed_stack],
        ):
            if isinstance(node, self.target_node_types):
                if prev_node and prev_node in getattr(node, 'body', ()):
                    # Don't infer upwards from a function definition or if
                    # statement body to the container.
                    raise NoSuitableNodeFoundError(self.node_stack)

                return node

        raise NoSupportedNodeFoundError(self.node_stack)

    def generic_visit(self, node: ast.AST) -> None:
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


def get_current_indent(asttokens: ASTTokens, node: ast.AST) -> int:
    first_token = _first_token(node)
    lineno = first_token.start[0]

    next_tok = tok = first_token
    while lineno == tok.start[0] and tok.type != token.INDENT:
        next_tok = tok
        tok = asttokens.prev_token(tok)

    return next_tok.start[1]  # type: ignore
