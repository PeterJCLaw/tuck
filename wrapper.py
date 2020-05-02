#!/usr/bin/env python3

import ast
import enum
import json
import token
import difflib
import argparse
import functools
import itertools
from typing import Dict, List, Type, Tuple, Union, TypeVar, Callable, Iterable

import asttokens.util  # type: ignore[import]
from asttokens import ASTTokens

TAst = TypeVar('TAst', bound=ast.AST)
INDENT_SIZE = 4


class MutationType(enum.Enum):
    WRAP = 'wrap'
    WRAP_INDENT = 'wrap_indent'
    TRAILING_COMMA = 'trailing_comma'
    OPEN_PAREN = 'open_paren'
    CLOSE_PAREN = 'close_paren'


WrappingSummary = List[Tuple['Position', MutationType]]
Insertion = Tuple['Position', str]

LSP_Range = Dict[str, Dict[str, int]]
LSP_TextEdit = Dict[str, Union[str, LSP_Range]]


class EditsOverlapError(Exception):
    pass


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


WRAPPING_FUNTIONS = []


def node_wrapper(ast_type: Type[TAst]) -> Callable[
    [Callable[[ASTTokens, TAst], WrappingSummary]],
    Callable[[ASTTokens, TAst], WrappingSummary],
]:
    def wrapper(
        func: Callable[[ASTTokens, TAst], WrappingSummary],
    ) -> Callable[[ASTTokens, TAst], WrappingSummary]:
        WRAPPING_FUNTIONS.append((ast_type, func))
        return func
    return wrapper


def node_start_positions(nodes: Iterable[ast.AST]) -> List[Position]:
    return [Position.from_node_start(x) for x in nodes]


def wrap_node_start_positions(nodes: Iterable[ast.AST]) -> WrappingSummary:
    return [
        (pos, MutationType.WRAP_INDENT)
        for pos in node_start_positions(nodes)
    ]


def wrap_generator_body(
    asttokens: ASTTokens,
    elt: ast.expr,
    generators: List[ast.comprehension],
) -> WrappingSummary:
    start_positions = [Position.from_node_start(elt)]

    for generator in generators:
        start_positions.append(Position.from_node_start(generator))
        for compare in generator.ifs:
            if_token = asttokens.prev_token(_first_token(compare))
            assert if_token.string == 'if'
            start_positions.append(Position(*if_token.start))

    return [(x, MutationType.WRAP_INDENT) for x in start_positions]


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


@node_wrapper(ast.Attribute)
def wrap_attribute(asttokens: ASTTokens, node: ast.Attribute) -> WrappingSummary:
    # Actively choose not to wrap attributes, mostly so that in things like:
    # func("a long string with a {placeholder} and then a ".format(placeholder=value))
    # attempting to wrap on the string doesn't wrap the .format(), which is
    # unlikely to be intended. More likely the user wants to wrap the `func()`
    # call's arguments, but that's harder to support.
    # Better to do nothing than do something we believe is likely wrong.
    return []


@node_wrapper(ast.BoolOp)
def wrap_bool_op(asttokens: ASTTokens, node: ast.BoolOp) -> WrappingSummary:
    summary = wrap_node_start_positions(node.values)

    summary.append((
        Position(*_last_token(node).end),
        MutationType.WRAP,
    ))

    # Work out if we have parentheses already, if not we need to add some
    if asttokens.prev_token(_first_token(node)).string != '(':
        summary.insert(0, (
            Position.from_node_start(node),
            MutationType.OPEN_PAREN,
        ))
        summary.append((
            Position(*_last_token(node).end),
            MutationType.CLOSE_PAREN,
        ))

    return summary


@node_wrapper(ast.Call)
def wrap_call(asttokens: ASTTokens, node: ast.Call) -> WrappingSummary:
    named_args = node.keywords
    kwargs = None
    if named_args and named_args[-1].arg is None:
        named_args = node.keywords[:-1]
        kwargs = node.keywords[-1]

    summary = wrap_node_start_positions([*node.args, *named_args])

    if kwargs is not None:
        kwargs_stars = asttokens.prev_token(_first_token(kwargs))
        summary.append((Position(*kwargs_stars.start), MutationType.WRAP_INDENT))

    append_trailing_comma(summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.ClassDef)
def wrap_class_def(asttokens: ASTTokens, node: ast.ClassDef) -> WrappingSummary:
    if not node.bases and not node.keywords:
        return []

    named_args = node.keywords
    kwargs = None
    if named_args and named_args[-1].arg is None:
        named_args = node.keywords[:-1]
        kwargs = node.keywords[-1]

    args = [*node.bases, *named_args]
    summary = wrap_node_start_positions(args)

    if kwargs is not None:
        kwargs_stars = asttokens.prev_token(_first_token(kwargs))
        summary.append((Position(*kwargs_stars.start), MutationType.WRAP_INDENT))
        summary.append((Position(*_last_token(kwargs).end), MutationType.TRAILING_COMMA))
        summary.append((Position(*_last_token(kwargs).end), MutationType.WRAP))

    else:
        last_token_before_body = asttokens.next_token(_last_token(args[-1]))

        summary.append((
            Position(*last_token_before_body.start),
            MutationType.TRAILING_COMMA,
        ))
        summary.append((
            Position(*last_token_before_body.start),
            MutationType.WRAP,
        ))

    return summary


@node_wrapper(ast.Dict)
def wrap_dict(asttokens: ASTTokens, node: ast.Dict) -> WrappingSummary:
    positions = []

    for key, value in zip(node.keys, node.values):
        if key is not None:
            positions.append(Position.from_node_start(key))
        else:
            kwargs_stars = asttokens.prev_token(_first_token(value))
            positions.append(Position(*kwargs_stars.start))

    summary = [(x, MutationType.WRAP_INDENT) for x in positions]
    append_trailing_comma(summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.DictComp)
def wrap_dict_comp(asttokens: ASTTokens, node: ast.DictComp) -> WrappingSummary:
    summary = wrap_generator_body(asttokens, node.key, node.generators)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.FunctionDef)
def wrap_function_def(asttokens: ASTTokens, node: ast.FunctionDef) -> WrappingSummary:
    positions = node_start_positions(node.args.args)

    if node.args.vararg:
        # Account for the * before the name
        args_star = asttokens.prev_token(_first_token(node.args.vararg))
        positions.append(Position(*args_star.start))

    if node.args.kwonlyargs:
        # Account for the unnamed *
        if not node.args.vararg:
            comma = asttokens.prev_token(_first_token(node.args.kwonlyargs[0]))
            args_star = asttokens.prev_token(comma)
            positions.append(Position(*args_star.start))

        positions += node_start_positions(node.args.kwonlyargs)

    if node.args.kwarg:
        # Account for the ** before the name
        kwargs_stars = asttokens.prev_token(_first_token(node.args.kwarg))
        positions.append(Position(*kwargs_stars.start))

    summary = [
        (Position(pos.line, pos.col), MutationType.WRAP_INDENT)
        for pos in positions
    ]

    close_paren = asttokens.next_token(_last_token(node.args))
    args_end = Position(*close_paren.start)

    if not (node.args.kwonlyargs or node.args.kwarg):
        summary.append((args_end, MutationType.TRAILING_COMMA))

    summary.append((args_end, MutationType.WRAP))

    return summary


@node_wrapper(ast.GeneratorExp)
def wrap_generator_exp(asttokens: ASTTokens, node: ast.GeneratorExp) -> WrappingSummary:
    summary = wrap_generator_body(asttokens, node.elt, node.generators)

    next_token = asttokens.next_token(_last_token(node))
    if next_token.string == ')':
        summary.append((
            Position(*next_token.start),
            MutationType.WRAP,
        ))

    return summary


@node_wrapper(ast.If)
def wrap_if(asttokens: ASTTokens, node: ast.If) -> WrappingSummary:
    if isinstance(node.test, ast.BoolOp):
        return wrap_bool_op(asttokens, node.test)
    return []


@node_wrapper(ast.List)
def wrap_list(asttokens: ASTTokens, node: ast.List) -> WrappingSummary:
    summary = wrap_node_start_positions(node.elts)
    append_trailing_comma(summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.ListComp)
def wrap_list_comp(asttokens: ASTTokens, node: ast.ListComp) -> WrappingSummary:
    summary = wrap_generator_body(asttokens, node.elt, node.generators)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.Tuple)
def wrap_tuple(asttokens: ASTTokens, node: ast.Tuple) -> WrappingSummary:
    summary = wrap_node_start_positions(node.elts)
    if len(node.elts) > 1:
        append_trailing_comma(summary, node)
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


def get_current_indent(asttokens: ASTTokens, node: ast.AST) -> int:
    first_token = _first_token(node)
    lineno = first_token.start[0]

    next_tok = tok = first_token
    while lineno == tok.start[0] and tok.type != token.INDENT:
        next_tok = tok
        tok = asttokens.prev_token(tok)

    return next_tok.start[1]  # type: ignore


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


def determine_insertions(asttokens: ASTTokens, position: Position) -> List[Insertion]:
    finder = NodeFinder(position)
    finder.visit(asttokens.tree)

    node = finder.found_node

    # Note: insertions are actually applied in reverse, though we'll generate
    # them forwards.

    current_indent = get_current_indent(asttokens, node)

    mutations = {
        MutationType.WRAP: "\n" + " " * current_indent,
        MutationType.WRAP_INDENT: "\n" + " " * (current_indent + INDENT_SIZE),
        MutationType.TRAILING_COMMA: ",",
        # TODO: would be nice if we didn't need to include a space here
        MutationType.OPEN_PAREN: " (",
        MutationType.CLOSE_PAREN: ")",
    }

    wrapping_summary = get_wrapping_summary(asttokens, node)

    insertions = [
        (pos, ''.join(mutations[x] for x in mutation_types))
        for pos, mutation_types in coalesce(wrapping_summary)
    ]

    indent_interim_lines(insertions)

    return insertions


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wrap the python statement at a given position within a text document.",
    )
    parser.add_argument(
        'file',
        type=argparse.FileType(mode='r'),
        help="The file to read from. Use '-' to read from STDIN.",
    )
    parser.add_argument(
        '--positions',
        required=True,
        nargs='+',
        type=parse_position,
        help=(
            "The positions within the file to wrap at. "
            "Express in LINE:COL format, with 1-based line numbers. "
            "When multiple locations are specified, they must appear within "
            "distinct statements. It is an error if the edits overlap."
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

    new_content, insertions = process(args.positions, content, args.file.name)

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
