import ast
import token
from typing import List, Type, Union, TypeVar, Callable, Iterable

from asttokens import ASTTokens  # type: ignore[import]

from .ast import Position, _last_token, _first_token
from .editing import MutationType, WrappingSummary

TAst = TypeVar('TAst', bound=ast.AST)


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


def generator_is_parenthesised(asttokens: ASTTokens, node: ast.GeneratorExp) -> bool:
    prev_token = asttokens.prev_token(_first_token(node))
    next_token = asttokens.next_token(_last_token(node))
    if prev_token.string == '(' and next_token.string == ')':
        # These parens might be wrapping us
        prev_prev_token = asttokens.prev_token(prev_token)
        if prev_prev_token.string in ('(', ','):
            return True

    return False


def bool_op_is_parenthesised(asttokens: ASTTokens, node: ast.BoolOp) -> bool:
    prev_token = asttokens.prev_token(_first_token(node))
    next_token = asttokens.next_token(_last_token(node))
    if prev_token.string == '(' and next_token.string == ')':
        return True

    return False


def node_start_position(asttokens: ASTTokens, node: ast.AST) -> Position:
    first_token = _first_token(node)
    if (
        isinstance(node, ast.GeneratorExp)
        and generator_is_parenthesised(asttokens, node)
    ):
        first_token = asttokens.prev_token(first_token)

    elif (
        isinstance(node, ast.BoolOp)
        and bool_op_is_parenthesised(asttokens, node)
    ):
        first_token = asttokens.prev_token(first_token)

    return Position(*first_token.start)


def node_start_positions(
    asttokens: ASTTokens,
    nodes: Iterable[ast.AST],
) -> List[Position]:
    return [node_start_position(asttokens, x) for x in nodes]


def wrap_node_start_positions(
    asttokens: ASTTokens,
    nodes: Iterable[ast.AST],
) -> WrappingSummary:
    return [
        (pos, MutationType.WRAP_INDENT)
        for pos in node_start_positions(asttokens, nodes)
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


def append_trailing_comma(
    asttokens: ASTTokens,
    summary: WrappingSummary,
    node: ast.AST,
) -> WrappingSummary:
    # Use the end position of the last content token, rather than the start
    # position of the closing token. This ensures that we put the comma in the
    # right place in constructs like:
    #
    #   func(
    #       'abcd', 'defg'
    #   )
    #
    # Where we want to put the comma immediately after 'defg' rather than just
    # before the closing paren.
    last_body_token = asttokens.prev_token(_last_token(node))
    summary.append((
        Position(*last_body_token.end),
        MutationType.TRAILING_COMMA,
    ))
    return summary


def append_wrap_end(summary: WrappingSummary, node: ast.AST) -> WrappingSummary:
    summary.append((
        Position.from_node_end(node),
        MutationType.WRAP,
    ))
    return summary


@node_wrapper(ast.BoolOp)
def wrap_bool_op(asttokens: ASTTokens, node: ast.BoolOp) -> WrappingSummary:
    summary = wrap_node_start_positions(asttokens, node.values)

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

    if (
        len(node.args) == 1
        and not named_args
        and isinstance(node.args[0], ast.GeneratorExp)
        and not generator_is_parenthesised(asttokens, node.args[0])
    ):
        generator_node = node.args[0]  # type: ast.GeneratorExp
        # The generator needs parentheses adding, as well as wrapping
        summary = [(
            Position.from_node_start(generator_node),
            MutationType.WRAP_INDENT,
        ), (
            Position.from_node_start(generator_node),
            MutationType.OPEN_PAREN,
        ), (
            Position(*_last_token(generator_node).end),
            MutationType.CLOSE_PAREN,
        )]

    else:
        summary = wrap_node_start_positions(asttokens, [*node.args, *named_args])

    if kwargs is not None:
        # find_token rather than prev_token since in Python 3.9 the first token
        # of kwargs _is_ the ** token we're after.
        kwargs_stars = asttokens.find_token(_first_token(kwargs), token.OP, '**', reverse=True)
        summary.append((Position(*kwargs_stars.start), MutationType.WRAP_INDENT))

    append_trailing_comma(asttokens, summary, node)
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
    summary = wrap_node_start_positions(asttokens, args)

    if kwargs is not None:
        # find_token rather than prev_token since in Python 3.9 the first token
        # of kwargs _is_ the ** token we're after.
        kwargs_stars = asttokens.find_token(_first_token(kwargs), token.OP, '**', reverse=True)
        summary.append((Position(*kwargs_stars.start), MutationType.WRAP_INDENT))

    close_paren = asttokens.find_token(_last_token(args[-1]), token.OP, ')')
    args_end = Position(*close_paren.start)

    summary.append((args_end, MutationType.TRAILING_COMMA))
    summary.append((args_end, MutationType.WRAP))

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
    append_trailing_comma(asttokens, summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.DictComp)
def wrap_dict_comp(asttokens: ASTTokens, node: ast.DictComp) -> WrappingSummary:
    summary = wrap_generator_body(asttokens, node.key, node.generators)
    append_wrap_end(summary, node)
    return summary


def wrap_function_def(
    asttokens: ASTTokens,
    node: Union[ast.AsyncFunctionDef, ast.FunctionDef],
) -> WrappingSummary:
    positions = node_start_positions(asttokens, node.args.args)

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

        positions += node_start_positions(asttokens, node.args.kwonlyargs)

    if node.args.kwarg:
        # Account for the ** before the name
        kwargs_stars = asttokens.prev_token(_first_token(node.args.kwarg))
        positions.append(Position(*kwargs_stars.start))

    summary = [
        (Position(pos.line, pos.col), MutationType.WRAP_INDENT)
        for pos in positions
    ]

    close_paren = asttokens.find_token(_last_token(node.args), token.OP, ')')
    args_end = Position(*close_paren.start)

    if not (node.args.kwonlyargs or node.args.kwarg):
        summary.append((args_end, MutationType.TRAILING_COMMA))

    summary.append((args_end, MutationType.WRAP))

    return summary


node_wrapper(ast.AsyncFunctionDef)(wrap_function_def)
node_wrapper(ast.FunctionDef)(wrap_function_def)


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


@node_wrapper(ast.IfExp)
def wrap_if_exp(asttokens: ASTTokens, node: ast.IfExp) -> WrappingSummary:
    if_token = asttokens.find_token(_first_token(node.test), token.NAME, 'if', reverse=True)
    else_token = asttokens.find_token(_last_token(node.test), token.NAME, 'else')

    summary = [(
        Position(*_first_token(node).start),
        MutationType.WRAP_INDENT,
    ), (
        Position(*if_token.start),
        MutationType.WRAP_INDENT,
    ), (
        Position(*else_token.start),
        MutationType.WRAP_INDENT,
    ), (
        Position(*_last_token(node).end),
        MutationType.WRAP,
    )]

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


@node_wrapper(ast.List)
def wrap_list(asttokens: ASTTokens, node: ast.List) -> WrappingSummary:
    summary = wrap_node_start_positions(asttokens, node.elts)
    append_trailing_comma(asttokens, summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.ListComp)
def wrap_list_comp(asttokens: ASTTokens, node: ast.ListComp) -> WrappingSummary:
    summary = wrap_generator_body(asttokens, node.elt, node.generators)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.Set)
def wrap_set(asttokens: ASTTokens, node: ast.Set) -> WrappingSummary:
    summary = wrap_node_start_positions(asttokens, node.elts)
    append_trailing_comma(asttokens, summary, node)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.SetComp)
def wrap_set_comp(asttokens: ASTTokens, node: ast.SetComp) -> WrappingSummary:
    summary = wrap_generator_body(asttokens, node.elt, node.generators)
    append_wrap_end(summary, node)
    return summary


@node_wrapper(ast.Tuple)
def wrap_tuple(asttokens: ASTTokens, node: ast.Tuple) -> WrappingSummary:
    first_token = _first_token(node)
    last_token = _last_token(node)

    is_parenthesised = first_token.string == '(' and last_token.string == ')'

    def needs_parentheses_() -> bool:
        prev_token = asttokens.prev_token(first_token)
        next_token = asttokens.next_token(last_token)
        if prev_token.string in '[' or next_token.string == ']':
            return False

        return True

    needs_parentheses = needs_parentheses_()

    summary = wrap_node_start_positions(asttokens, node.elts)

    if not is_parenthesised:
        if needs_parentheses:
            summary.insert(0, (
                Position.from_node_start(node),
                MutationType.OPEN_PAREN,
            ))

        end_pos = Position(*_last_token(node).end)

        if len(node.elts) > 1:
            summary.append((
                end_pos,
                MutationType.TRAILING_COMMA,
            ))

        summary.append((
            end_pos,
            MutationType.WRAP,
        ))

        if needs_parentheses:
            summary.append((
                end_pos,
                MutationType.CLOSE_PAREN,
            ))

    else:
        if len(node.elts) > 1:
            append_trailing_comma(asttokens, summary, node)

        append_wrap_end(summary, node)

    return summary
