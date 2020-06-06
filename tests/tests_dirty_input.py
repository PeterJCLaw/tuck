from .test_utils import BaseWrapperTestCase


class TestDirtyInput(BaseWrapperTestCase):
    def test_function_call_with_internal_trailing_comma(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo('abcd', 1234, spam='ham',)
            """,
            """
            foo(
                'abcd',
                1234,
                spam='ham',
            )
            """,
        )

    def test_function_call_partly_wrapped_with_comment(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            foo(
                'abcd', 1234,
                # comment
                spam='ham',
            )
            """,
            """
            foo(
                'abcd',
                1234,
                # comment
                spam='ham',
            )
            """,
        )
