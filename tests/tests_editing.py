import unittest

import tuck.editing
from tuck import Range, Position


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
