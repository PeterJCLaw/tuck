import io
import sys
import json
import tempfile
import textwrap
import unittest
import contextlib
from typing import List, Iterator

import tuck


@contextlib.contextmanager
def capture_stdout() -> Iterator[io.StringIO]:
    buffer = io.StringIO()
    original, sys.stdout = sys.stdout, buffer
    yield buffer
    sys.stdout = original


class TestCli(unittest.TestCase):
    def run_tuck(self, content: str, argv: List[str]) -> str:
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w+t') as target:
            target.write(content)
            target.flush()

            with capture_stdout() as buffer:
                tuck.main([target.name, *argv])

            target.seek(0)
            new_content = target.read()

        self.assertEqual(
            content,
            new_content,
            "Should not change content of target file",
        )

        return buffer.getvalue()

    def test_output(self) -> None:
        output = self.run_tuck(
            'print(foo)\n',
            ['--positions', '1:1'],
        )

        self.assertEqual(
            "print(\n    foo,\n)\n",
            output,
            "Wrong output",
        )

    def test_diff_output(self) -> None:
        output = self.run_tuck(
            'print(foo)\n',
            ['--diff', '--positions', '1:1'],
        )

        self.assertEqual(
            textwrap.dedent("""
                --- original
                +++ formatted
                @@ -1 +1,3 @@
                -print(foo)
                +print(
                +    foo,
                +)
            """).lstrip(),
            output,
            "Wrong output",
        )

    def test_edits_output(self) -> None:
        output = self.run_tuck(
            'print(foo)\n',
            ['--edits', '--positions', '1:1'],
        )

        data = json.loads(output)

        self.assertEqual(
            {
                'edits': [
                    {'newText': '\n    ', 'range': {
                        'end': {'character': 6, 'line': 0},
                        'start': {'character': 6, 'line': 0},
                    }},
                    {'newText': ',\n', 'range': {
                        'end': {'character': 9, 'line': 0},
                        'start': {'character': 9, 'line': 0},
                    }},
                ],
            },
            data,
            "Wrong output",
        )
