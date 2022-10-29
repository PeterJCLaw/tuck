import ast
import token
import functools
from typing import List, Type, Tuple, TypeVar, Optional

import asttokens.util
from asttokens import ASTTokens

from .exceptions import TuckError

TAst = TypeVar('TAst', bound=ast.AST)


def _first_token(node: ast.AST) -> asttokens.util.Token:
    if isinstance(node, ast.GeneratorExp):
        return _first_token(node.elt)

    return node.first_token  # type: ignore[attr-defined,no-any-return]


def _last_token(node: ast.AST) -> asttokens.util.Token:
    if isinstance(node, ast.GeneratorExp):
        return _last_token(node.generators[-1])

    return node.last_token  # type: ignore[attr-defined,no-any-return]


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
            return NotImplemented  # type: ignore[unreachable]

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
    """
    Visitor which finds the AST node that should be wrapped for a given position.
    """

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
            if (
                # Skip upwards past attributes
                isinstance(node, ast.Attribute)
                or (
                    # Skip upwards past calls when our position was on an
                    # attribute to the left of the actual call. For example: in
                    # `func(foo.bar.baz(4))` we want to wrap the call to `baz`
                    # only when on `baz` itself or within its parentheses.
                    # Otherwise we want to wrap `func`. This is somewhat
                    # complicated by the Python AST including `foo.bar.baz` in
                    # the `Call` node, hence this logic.
                    isinstance(node, ast.Call)
                    and node.func in reversed_stack[:index]
                )
            ):
                offset = index + 1
            else:
                break

        return reversed_stack[offset:]

    def _check_not_in_body(self, node: ast.AST, asttokens: ASTTokens) -> None:
        body = getattr(node, 'body', None)
        if not body or not isinstance(body, list):
            return

        first_token = _first_token(body[0])
        colon = asttokens.find_token(first_token, token.OP, ':', reverse=True)
        body_start = Position(*colon.end)

        if self.target_position > body_start:
            # Don't infer upwards from a function definition or if
            # statement body to the container.
            raise NoSuitableNodeFoundError(self.node_stack)

    def get_found_node(self, asttokens: ASTTokens) -> ast.AST:
        if not self.found:
            raise NoNodeFoundError()

        reversed_stack = self.get_filtered_stack()

        for node, prev_node in zip(
            reversed_stack,
            [None, *reversed_stack],
        ):
            if isinstance(node, self.target_node_types):
                self._check_not_in_body(node, asttokens)
                return node

        raise NoSupportedNodeFoundError(self.node_stack)

    def _get_end_of_node(self, node: ast.AST) -> Position:
        # We want to prefer the node that the position is clearly "within". This
        # means slightly different things for different cases:
        #  - nodes that end with some for of bracket don't really want to
        #    consider the bracket as in practise text editors position their
        #    visible cursor to the left of the character position they're at
        #  - generators sort-of end with a bracket, but don't own the bracket
        #  - due to how Python's AST is structured around attributes and calls,
        #    we don't want to consider the right hand "name" portion of an
        #    attribute as part of the attribute; this is so we're forced to
        #    consider only the parent node rather than a true reflection of the
        #    positions
        last_token = _last_token(node)
        if (
            last_token.type == token.OP and last_token.string in ')}]'
            or isinstance(node, (ast.Attribute, ast.Name, ast.GeneratorExp))
        ):
            return Position(*last_token.start)

        return Position(*last_token.end)

    def generic_visit(self, node: ast.AST) -> None:
        if self.found:
            return

        if not hasattr(node, 'lineno'):
            super().generic_visit(node)
            return

        start = Position.from_node_start(node)
        end = self._get_end_of_node(node)

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

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # JoinedStr is f-strings
        return


def get_current_indent(asttokens: ASTTokens, node: ast.AST) -> int:
    first_token = _first_token(node)
    lineno = first_token.start[0]

    next_tok = tok = first_token
    while lineno == tok.start[0] and tok.type != token.INDENT:
        next_tok = tok
        tok = asttokens.prev_token(tok)

    return next_tok.start[1]  # type: ignore[no-any-return]


class AffectedNodeFinder(ast.NodeVisitor):
    """
    Visitor which finds the first AST node that would be affected by wrapping at
    the given position.

    Nodes which are all on the same line will never be considered matches.
    """

    def __init__(self, position: Position) -> None:
        self.target_position = position

        self._found: bool = False
        self.found_node: Optional[ast.AST] = None

    def generic_visit(self, node: ast.AST) -> None:
        if self._found:
            return

        if not hasattr(node, 'lineno'):
            super().generic_visit(node)
            return

        start = Position.from_node_start(node)
        end = Position.from_node_end(node)

        if end < self.target_position:
            # we're clear before the target
            return

        if start.line > self.target_position.line:
            # we're clear after the target
            return

        if start.line == end.line:
            # not interested in single-line nodes
            return

        if (
            start.line == self.target_position.line
            and start.col >= self.target_position.col
        ):
            self.found_node = node
            return

        super().generic_visit(node)
