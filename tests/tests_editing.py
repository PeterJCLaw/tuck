import unittest

import tuck.editing
from tuck import Position


class TestAllAreDisjoint(unittest.TestCase):
    def test_ok(self) -> None:
        self.assertTrue(tuck.editing.all_are_disjoint([
            [Position(1, 1), Position(2, 1)],
            [Position(3, 1), Position(4, 1)],
            [Position(5, 1), Position(6, 1)],
        ]))

    def test_first_two_overlap(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [Position(1, 1), Position(2, 10)],
            [Position(2, 1), Position(4, 1)],
            [Position(5, 1), Position(6, 1)],
        ]))

    def test_first_and_last_overlap(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [Position(2, 1), Position(4, 1)],
            [Position(5, 1), Position(6, 1)],
            [Position(1, 1), Position(2, 10)],
        ]))

    def test_last_overlaps_with_all_others(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [Position(1, 1), Position(2, 10)],
            [Position(3, 1), Position(4, 1)],
            [Position(6, 1), Position(2, 1)],
        ]))

    def test_overlap_three_of_four(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [Position(1, 1), Position(2, 10)],
            [Position(1, 1), Position(4, 1)],
            [Position(1, 1), Position(6, 1)],
            [Position(10, 1), Position(6, 1)],
        ]))

    def test_all_overlap(self) -> None:
        self.assertFalse(tuck.editing.all_are_disjoint([
            [Position(1, 1), Position(2, 10)],
            [Position(3, 1), Position(1, 1)],
            [Position(6, 1), Position(2, 1)],
        ]))
