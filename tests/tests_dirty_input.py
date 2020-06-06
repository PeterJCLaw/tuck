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
        # We accept the misplacement of the comment here, rather than causing
        # the misplacement of comments withing already "correctly" wrapped
        # nested blocks.
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

    def test_function_call_partly_wrapped_hugging_opening_paren(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            foo('abcd',
                spam='ham',
            )
            """,
            """
            foo(
                'abcd',
                spam='ham',
            )
            """,
        )

    def test_function_call_partly_wrapped_hugging_parens(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            foo('abcd',
                spam='ham')
            """,
            """
            foo(
                'abcd',
                spam='ham',
            )
            """,
        )

    def test_function_call_partly_wrapped_hugging_trailing_paren(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            foo(
                'abcd',
                spam='ham')
            """,
            """
            foo(
                'abcd',
                spam='ham',
            )
            """,
        )

    def test_function_call_partly_wrapped_complex(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            foo('abcd', 1234,
                spam='ham', bees='spam')
            """,
            """
            foo(
                'abcd',
                1234,
                spam='ham',
                bees='spam',
            )
            """,
        )
