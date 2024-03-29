from __future__ import annotations

import io
import json
import tempfile
import textwrap
import unittest
import contextlib
from unittest import mock

import tuck


class TestCli(unittest.TestCase):
    def run_tuck(self, content: str, argv: list[str]) -> str:
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w+t') as target:
            target.write(content)
            target.flush()

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
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

    def test_edits_overlap_error(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            output = self.run_tuck(
                'print(foo(bar))',
                ['--edits', '--positions', '1:1', '1:8'],
            )

        self.assertIn(
            "Unable to perform wrapping as the resulting edits contain overlaps. ",
            buffer.getvalue(),
        )

        self.assertEqual('', output, "Should be no stdout messages on error")

    def test_no_supported_node_error(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            output = self.run_tuck(
                textwrap.dedent("""
                    try:
                        pass
                    except:
                        pass
                """).lstrip(),
                ['--positions', '1:1'],
            )

        self.assertIn(
            "No supported nodes found (stack: Try)",
            buffer.getvalue(),
        )

        self.assertEqual('', output, "Should be no stdout messages on error")

    def test_handled_error_when_asked_for_edits(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            output = self.run_tuck(
                'print(foo(bar))',
                ['--edits', '--positions', '1:1', '1:8'],
            )

        data = json.loads(buffer.getvalue())
        self.assertEqual(
            {'error': {
                'code': 'edits_overlap',
                'message': tuck.EditsOverlapError().message,
            }},
            data,
        )

        self.assertEqual('', output, "Should be no stdout messages on error")

    def test_target_syntax_error_when_asked_for_edits(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            output = self.run_tuck(
                'invalid code',
                ['--edits', '--positions', '1:1'],
            )

        data = json.loads(buffer.getvalue())
        self.assertEqual(
            {'error': {
                'code': 'target_syntax_error',
                'message': mock.ANY,
            }},
            data,
        )

        self.assertRegex(
            data['error']['message'],
            r'^invalid syntax \(tmp\w+\.py, line 1\)$',
        )

        self.assertEqual('', output, "Should be no stdout messages on error")
