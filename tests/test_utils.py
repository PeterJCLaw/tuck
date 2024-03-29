from __future__ import annotations

import textwrap
import unittest

import tuck
from tuck import Position


class BaseWrapperTestCase(unittest.TestCase):
    def assertTransforms(
        self,
        positions: list[Position],
        content: str,
        expected_output: str,
        *,
        message: str = "Bad transformations",
    ) -> None:
        # Normalise from triple quoted strings
        content = textwrap.dedent(content[1:])
        expected_output = textwrap.dedent(expected_output[1:])

        insertions = tuck.process(positions, content, 'demo.py')
        new_content = tuck.apply_insertions(content, insertions)

        self.assertEqual(expected_output, new_content, message)

    def assertTransform(self, line: int, col: int, content: str, expected_output: str) -> None:
        self.assertTransforms(
            [Position(line, col)],
            content,
            expected_output,
            message="Bad transformation",
        )
