import tuck

from .test_utils import BaseWrapperTestCase


class TestNodeSearchFailures(BaseWrapperTestCase):
    def test_no_node(self) -> None:
        with self.assertRaises(tuck.NoNodeFoundError):
            self.assertTransform(
                1,
                1,
                """
                # comment
                """,
                "",
            )

    def test_no_supported_node(self) -> None:
        with self.assertRaises(tuck.NoSupportedNodeFoundError):
            self.assertTransform(
                1,
                1,
                """
                try:
                    pass
                except:
                    pass
                """,
                "",
            )

    def test_if_body_unsuitable(self) -> None:
        with self.assertRaises(tuck.NoSuitableNodeFoundError):
            self.assertTransform(
                2,
                6,
                """
                if a or b:
                    raise Exception
                """,
                """
                if a or b:
                    raise Exception
                """,
            )

    def test_function_body_unsuitable(self) -> None:
        with self.assertRaises(tuck.NoSuitableNodeFoundError):
            self.assertTransform(
                2,
                6,
                """
                def foo(first):
                    raise Exception
                """,
                """
                def foo(first):
                    raise Exception
                """,
            )

    def test_function_body_unsuitable_when_not_on_other_node(self) -> None:
        with self.assertRaises(tuck.NoSuitableNodeFoundError):
            self.assertTransform(
                2,
                2,
                """
                def foo():
                    pass
                """,
                """
                def foo():
                    pass
                """,
            )


class TestMultiEditing(BaseWrapperTestCase):
    def test_overlap_same_statement(self) -> None:
        with self.assertRaises(tuck.EditsOverlapError):
            self.assertTransforms(
                [
                    tuck.Position(1, 8),
                    tuck.Position(1, 12),
                ],
                """
                foo = {'abcd': 1234}
                """,
                "",
            )

    def test_overlap_nested_statement(self) -> None:
        with self.assertRaises(tuck.EditsOverlapError):
            self.assertTransforms(
                [
                    tuck.Position(1, 10),
                    tuck.Position(1, 25),
                ],
                """
                foo = {'abcd': bar(ghij=5432)}
                """,
                "",
            )

    def test_same_line(self) -> None:
        # Not completely sure why you'd want to do this, but it proves that
        # we're actually validating that the edits don't overlap, rather that
        # not being in the same statement or something else.
        self.assertTransforms(
            [
                tuck.Position(1, 10),
                tuck.Position(1, 30),
            ],
            """
            func({'abcd': 1234}, bar(ghij=5432))
            """,
            """
            func({
                'abcd': 1234,
            }, bar(
                ghij=5432,
            ))
            """,
        )

    def test_same_line_reverse_order(self) -> None:
        # Not completely sure why you'd want to do this, but it proves that
        # we're actually validating that the edits don't overlap, rather that
        # not being in the same statement or something else.
        self.assertTransforms(
            [
                tuck.Position(1, 30),
                tuck.Position(1, 10),
            ],
            """
            func({'abcd': 1234}, bar(ghij=5432))
            """,
            """
            func({
                'abcd': 1234,
            }, bar(
                ghij=5432,
            ))
            """,
        )

    def test_separate_lines(self) -> None:
        self.assertTransforms(
            [
                tuck.Position(1, 8),
                tuck.Position(2, 8),
            ],
            """
            foo = {'abcd': 1234}
            bar(ghij=5432)
            """,
            """
            foo = {
                'abcd': 1234,
            }
            bar(
                ghij=5432,
            )
            """,
        )
