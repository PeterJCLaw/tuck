from .test_utils import BaseWrapperTestCase


class TestDirtyInput(BaseWrapperTestCase):
    def test_class_def_already_tucked(self) -> None:
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
            class Foo(
                abcd,
                spam='ham',
            ):
                pass
            """,
        )

    def test_function_call_already_tucked(self) -> None:
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
            foo(
                'abcd',
                1234,
                spam='ham',
            )
            """,
        )

    def test_function_def_already_tucked(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            def foo(
                abcd,
                spam='ham',
            ):
                pass
            """,
            """
            def foo(
                abcd,
                spam='ham',
            ):
                pass
            """,
        )

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

    def test_function_def_with_internal_trailing_comma(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            def foo(abcd, defg, spam='ham',):
                pass
            """,
            """
            def foo(
                abcd,
                defg,
                spam='ham',
            ):
                pass
            """,
        )

    def test_class_def_with_internal_trailing_comma(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            class Foo(abcd, defg, spam='ham',):
                pass
            """,
            """
            class Foo(
                abcd,
                defg,
                spam='ham',
            ):
                pass
            """,
        )

    def test_function_call_with_trailing_comma_and_comment(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo('abcd', 1234,
                24 * 60 * 60, # 1 day
            )
            """,
            """
            foo(
                'abcd',
                1234,
                24 * 60 * 60, # 1 day
            )
            """,
        )

    def test_function_def_three_line_style(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            def foo(
                abcd, defg, spam='ham'
            ):
                pass
            """,
            """
            def foo(
                abcd,
                defg,
                spam='ham',
            ):
                pass
            """,
        )

    def test_function_def_three_line_style_with_comment(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            def foo(
                abcd, defg, spam='ham'  # foo
            ):
                pass
            """,
            """
            def foo(
                abcd,
                defg,
                spam='ham',  # foo
            ):
                pass
            """,
        )

    def test_class_def_three_line_style(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            class Foo(
                abcd, defg, spam='ham'
            ):
                pass
            """,
            """
            class Foo(
                abcd,
                defg,
                spam='ham',
            ):
                pass
            """,
        )

    def test_class_def_three_line_style_with_comment(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            class Foo(
                abcd, defg, spam='ham'  # foo
            ):
                pass
            """,
            """
            class Foo(
                abcd,
                defg,
                spam='ham',  # foo
            ):
                pass
            """,
        )

    def test_function_call_three_line_style(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            foo(
                'abcd', 1234, spam='ham'
            )
            """,
            """
            foo(
                'abcd',
                1234,
                spam='ham',
            )
            """,
        )

    def test_function_call_three_line_style_with_trailing_comma(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            foo(
                'abcd', 1234, spam='ham',
            )
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
        # the misplacement of comments within already "correctly" wrapped
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

    def test_function_call_partly_wrapped_pep8_style(self) -> None:
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

    def test_three_line_boolean_expression(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            val = (
                foo and bar
            )
            """,
            """
            val = (
                foo and
                bar
            )
            """,
        )

    def test_commented_three_line_boolean_expression(self) -> None:
        self.assertTransform(
            2,
            8,
            """
            val = (
                foo and bar  # bees
            )
            """,
            """
            val = (
                foo and
                bar  # bees
            )
            """,
        )
