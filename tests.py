#!/usr/bin/env python3

import textwrap
import unittest

import wrapper


class TestWrapper(unittest.TestCase):
    def assertTransform(self, line: int, col: int, content: str, expected_output: str) -> None:
        # Normalise from triple quoted strings
        content = textwrap.dedent(content[1:])
        expected_output = textwrap.dedent(expected_output[1:])

        new_content, _ = wrapper.process(wrapper.Position(line, col), content, 'demo.py')

        self.assertEqual(expected_output, new_content, "Bad transformation")

    def test_single_key_dict_literal(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = {'abcd': 1234}
            """,
            """
            foo = {
                'abcd': 1234,
            }
            """,
        )

    def test_indented_single_key_dict_literal(self) -> None:
        self.assertTransform(
            2,
            12,
            """
            if True:
                foo = {'abcd': 1234}
            """,
            """
            if True:
                foo = {
                    'abcd': 1234,
                }
            """,
        )

    def test_multi_key_dict_literal(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = {'key': 1234, 'other': 5678}
            """,
            """
            foo = {
                'key': 1234,
                'other': 5678,
            }
            """,
        )

    def test_ignores_nested_dict(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = {'key': 1234, 'other': {'bar': 5678}}
            """,
            """
            foo = {
                'key': 1234,
                'other': {'bar': 5678},
            }
            """,
        )

    def test_wraps_nested_dict_only(self) -> None:
        self.assertTransform(
            1,
            38,
            """
            foo = {'key': 1234, 'other': {'bar': 5678}}
            """,
            """
            foo = {'key': 1234, 'other': {
                'bar': 5678,
            }}
            """,
        )

    def test_position_at_start(self) -> None:
        self.assertTransform(
            1,
            9,
            """
            foo = {'abcd': 1234}
            #      ^
            """,
            """
            foo = {
                'abcd': 1234,
            }
            #      ^
            """,
        )

    def test_position_on_leaf_key(self) -> None:
        self.assertTransform(
            1,
            12,
            """
            foo = {'abcd': 1234}
            #         ^
            """,
            """
            foo = {
                'abcd': 1234,
            }
            #         ^
            """,
        )

    def test_position_on_leaf_value(self) -> None:
        self.assertTransform(
            1,
            18,
            """
            foo = {'abcd': 1234}
            #               ^
            """,
            """
            foo = {
                'abcd': 1234,
            }
            #               ^
            """,
        )

    def test_position_in_space(self) -> None:
        self.assertTransform(
            1,
            17,
            """
            foo = {'abcd':   1234}
            #              ^
            """,
            """
            foo = {
                'abcd':   1234,
            }
            #              ^
            """,
        )

    def test_single_entry_list_literal(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = ['abcd']
            """,
            """
            foo = [
                'abcd',
            ]
            """,
        )

    def test_multi_entry_list_literal(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = ['abcd', 1234]
            """,
            """
            foo = [
                'abcd',
                1234,
            ]
            """,
        )

    def test_single_entry_tuple_literal(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = ('abcd',)
            """,
            """
            foo = (
                'abcd',
            )
            """,
        )

    def test_multi_entry_tuple_literal(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = ('abcd', 1234)
            """,
            """
            foo = (
                'abcd',
                1234,
            )
            """,
        )

    def test_dict_comprehension(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = {str(k): v for k, v in foo}
            """,
            """
            foo = {
                str(k): v
                for k, v in foo
            }
            """,
        )

    def test_list_comprehension(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = [str(x) for x in range(42)]
            """,
            """
            foo = [
                str(x)
                for x in range(42)
            ]
            """,
        )

    def test_function_call(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo('abcd', 1234, spam='ham')
            """,
            """
            foo(
                'abcd',
                1234,
                spam='ham',
            )
            """,
        )

    def test_function_call_args_kwargs(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo('abcd', *args, foo=42, **kwargs)
            """,
            """
            foo(
                'abcd',
                *args,
                foo=42,
                **kwargs,
            )
            """,
        )

    def test_function_with_nested_call(self) -> None:
        self.assertTransform(
            1,
            6,
            """
            foo(bar=quox('abcd', foo=42), spam='ham')
            """,
            """
            foo(
                bar=quox('abcd', foo=42),
                spam='ham',
            )
            """,
        )

    def test_nested_function_call(self) -> None:
        self.assertTransform(
            1,
            20,
            """
            foo(bar=quox('abcd', foo=42))
            """,
            """
            foo(bar=quox(
                'abcd',
                foo=42,
            ))
            """,
        )

    def test_double_nested_function_call(self) -> None:
        self.assertTransform(
            1,
            30,
            """
            foo(bar=quox(spam=ham('abcd', 'efgh')))
            """,
            """
            foo(bar=quox(spam=ham(
                'abcd',
                'efgh',
            )))
            """,
        )

    def test_nested_function_call_with_preceding_arg(self) -> None:
        self.assertTransform(
            1,
            30,
            """
            foo(spam='ham', bar=quox('abcd', foo=42))
            """,
            """
            foo(spam='ham', bar=quox(
                'abcd',
                foo=42,
            ))
            """,
        )

    def test_function_definition(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            def foo(tokens, position: Optional[int]) -> Optional[str]:
                pass
            """,
            """
            def foo(
                tokens,
                position: Optional[int],
            ) -> Optional[str]:
                pass
            """,
        )

    def test_function_definition_with_kwarg_only(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            def foo(tokens, position: Optional[int], *, bar: bytes) -> Optional[str]:
                pass
            """,
            """
            def foo(
                tokens,
                position: Optional[int],
                *,
                bar: bytes
            ) -> Optional[str]:
                pass
            """,
        )

    def test_function_definition_args_kwargs(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            def foo(first, *args, second, **kwargs) -> Optional[str]:
                pass
            """,
            """
            def foo(
                first,
                *args,
                second,
                **kwargs
            ) -> Optional[str]:
                pass
            """,
        )

    def test_function_definition_spacey_args_kwargs(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            def foo(first, * args, second, ** kwargs) -> Optional[str]:
                pass
            """,
            """
            def foo(
                first,
                * args,
                second,
                ** kwargs
            ) -> Optional[str]:
                pass
            """,
        )


if __name__ == '__main__':
    unittest.main(__name__)
