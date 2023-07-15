from .test_utils import BaseUnwrapTestCase


class TestUnrapping(BaseUnwrapTestCase):
    def test_class_def(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            class Foo(
                abcd,
                spam='ham',
            ):
                pass
            """,
            """
            class Foo(abcd, spam='ham'):
                pass
            """,
        )

    def test_call(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            foo(
                'abcd',
                1234,
                spam='ham',
            )
            """,
            """
            foo('abcd', 1234, spam='ham')
            """,
        )
