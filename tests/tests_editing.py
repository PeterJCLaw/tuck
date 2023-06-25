from __future__ import annotations

import textwrap
import unittest

import tuck.editing
from tuck import Range, Position
from tuck.editing import Edit


class TestApplyEdits(unittest.TestCase):
    def assertEdits(
        self,
        edits: list[Edit],
        content: str,
        expected_output: str,
        *,
        message: str = "Bad edits",
    ) -> None:
        # Normalise from triple quoted strings
        content = textwrap.dedent(content[1:])
        expected_output = textwrap.dedent(expected_output[1:])

        new_content = tuck.apply_edits(content, edits)

        self.assertEqual(expected_output, new_content, message)

    def test_single_insertion(self) -> None:
        self.assertEdits(
            [
                Edit(Range(Position(1, 4), Position(1, 4)), '123 '),
            ],
            '''
            abc def
            ''',
            '''
            abc 123 def
            ''',
        )

    def test_single_insertion_new_line(self) -> None:
        self.assertEdits(
            [
                Edit(Range(Position(2, 0), Position(2, 0)), '123\n'),
            ],
            '''
            abc
            def
            ''',
            '''
            abc
            123
            def
            ''',
        )

    def test_single_insertion_within_line(self) -> None:
        self.assertEdits(
            [
                Edit(Range(Position(2, 2), Position(2, 2)), '-123-'),
            ],
            '''
            abc
            def
            ''',
            '''
            abc
            de-123-f
            ''',
        )

    def test_multiple_insertions_single_line(self) -> None:
        self.assertEdits(
            [
                Edit(Range(Position(1, 3), Position(1, 3)), '-123-'),
                Edit(Range(Position(1, 7), Position(1, 7)), '-456-'),
            ],
            '''
            abc def
            ''',
            '''
            abc-123- def-456-
            ''',
        )

    def test_multiple_insertions_new_line(self) -> None:
        self.assertEdits(
            [
                Edit(Range(Position(1, 4), Position(1, 4)), '123\n'),
                Edit(Range(Position(2, 0), Position(2, 0)), '456\n'),
            ],
            '''
            abc
            def
            ''',
            '''
            abc
            123
            456
            def
            ''',
        )


class TestAllAreDisjoint(unittest.TestCase):
    def position_range(self, line: int, col: int) -> Range:
        position = Position(line, col)
        return Range(position, position)

    def test_ok(self) -> None:
        self.assertTrue(tuck.editing.all_are_disjoint([
            [self.position_range(1, 1), self.position_range(2, 1)],
            [self.position_range(3, 1), self.position_range(4, 1)],
            [self.position_range(5, 1), self.position_range(6, 1)],
        ]))

    def test_first_two_overlap(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [self.position_range(1, 1), self.position_range(2, 10)],
            [self.position_range(2, 1), self.position_range(4, 1)],
            [self.position_range(5, 1), self.position_range(6, 1)],
        ]))

    def test_first_and_last_overlap(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [self.position_range(2, 1), self.position_range(4, 1)],
            [self.position_range(5, 1), self.position_range(6, 1)],
            [self.position_range(1, 1), self.position_range(2, 10)],
        ]))

    def test_last_overlaps_with_all_others(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [self.position_range(1, 1), self.position_range(2, 10)],
            [self.position_range(3, 1), self.position_range(4, 1)],
            [self.position_range(6, 1), self.position_range(2, 1)],
        ]))

    def test_overlap_three_of_four(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [self.position_range(1, 1), self.position_range(2, 10)],
            [self.position_range(1, 1), self.position_range(4, 1)],
            [self.position_range(1, 1), self.position_range(6, 1)],
            [self.position_range(10, 1), self.position_range(6, 1)],
        ]))

    def test_all_overlap(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [self.position_range(1, 1), self.position_range(2, 10)],
            [self.position_range(3, 1), self.position_range(1, 1)],
            [self.position_range(6, 1), self.position_range(2, 1)],
        ]))
