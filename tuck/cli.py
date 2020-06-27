import sys
import json
import difflib
import argparse
from typing import Dict, List, Union

from .ast import Position
from .main import process
from .editing import Insertion, apply_insertions
from .exceptions import TuckError

FAIL = '\033[91m'
ENDC = '\033[0m'


LSP_Range = Dict[str, Dict[str, int]]
LSP_TextEdit = Dict[str, Union[str, LSP_Range]]


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
    edits = [insertion_as_lsp_data(*x) for x in insertions]
    print(json.dumps({'edits': edits}))


def parse_position(position: str) -> Position:
    line, col = [int(x) for x in position.split(':')]
    return Position(line, col)


def parse_args(argv: List[str]) -> argparse.Namespace:
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
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    with args.file:
        content = args.file.read()

    try:
        insertions = process(args.positions, content, args.file.name)
    except TuckError as e:
        if args.edits:
            # Assume the consumer is a tool looking for JSON
            print(
                json.dumps({'error': {'code': e.code, 'message': e.message}}),
                file=sys.stderr,
            )
        else:
            print(FAIL + e.message + ENDC, file=sys.stderr)
        return

    if args.diff:
        new_content = apply_insertions(content, insertions)
        print(
            "".join(difflib.unified_diff(
                content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                'original',
                'formatted',
            )),
            end='',
        )
    elif args.edits:
        print_edits(insertions)
    else:
        new_content = apply_insertions(content, insertions)
        print(new_content, end='')


def main(argv: List[str] = sys.argv[1:]) -> None:
    return run(parse_args(argv))
