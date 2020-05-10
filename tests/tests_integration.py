import sys
import unittest

from .test_utils import BaseWrapperTestCase


class TestIntegration(BaseWrapperTestCase):
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

    def test_dict_literal_with_star_star(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = {'key': 1234, **others, 'later': 2}
            """,
            """
            foo = {
                'key': 1234,
                **others,
                'later': 2,
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

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_generator_in_list_literal(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            ["bar", (x for x in 'an'), "foo"]
            """,
            """
            [
                "bar",
                (x for x in 'an'),
                "foo",
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

    def test_dict_comprehension_with_conditional(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = {str(x): x for x in range(42) if x % 3 == 0}
            """,
            """
            foo = {
                str(x): x
                for x in range(42)
                if x % 3 == 0
            }
            """,
        )

    def test_dict_comprehension_with_conditional_and_inner_loop(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = {int(a): a for x in range(42) if x % 3 == 0 for a in str(x)}
            """,
            """
            foo = {
                int(a): a
                for x in range(42)
                if x % 3 == 0
                for a in str(x)
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

    def test_list_comprehension_with_conditional(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = [str(x) for x in range(42) if x % 3 == 0]
            """,
            """
            foo = [
                str(x)
                for x in range(42)
                if x % 3 == 0
            ]
            """,
        )

    def test_list_comprehension_with_conditional_and_inner_loop(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = [a for x in range(42) if x % 3 == 0 for a in str(x)]
            """,
            """
            foo = [
                a
                for x in range(42)
                if x % 3 == 0
                for a in str(x)
            ]
            """,
        )

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_generator_expression(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = (str(x) for x in range(42))
            """,
            """
            foo = (
                str(x)
                for x in range(42)
            )
            """,
        )

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_generator_expression_as_only_argument(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo(str(x) for x in range(42))
            """,
            """
            foo(
                str(x)
                for x in range(42)
            )
            """,
        )

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_generator_expression_as_argument(self) -> None:
        self.assertTransform(
            1,
            20,
            """
            foo('abc', (str(x) for x in range(42)), 'def')
            """,
            """
            foo('abc', (
                str(x)
                for x in range(42)
            ), 'def')
            """,
        )

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_generator_expression_with_conditonal(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = (x for x in range(42) if x % 3 == 0)
            """,
            """
            foo = (
                x
                for x in range(42)
                if x % 3 == 0
            )
            """,
        )

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_generator_expression_with_conditonal_and_inner_loop(self) -> None:
        self.assertTransform(
            1,
            15,
            """
            foo = (a for x in range(42) if x % 3 == 0 for a in str(x))
            """,
            """
            foo = (
                a
                for x in range(42)
                if x % 3 == 0
                for a in str(x)
            )
            """,
        )

    def test_if_expression(self) -> None:
        self.assertTransform(
            1,
            7,
            """
            x = a if foo and bar else b
            """,
            """
            x = (
                a
                if foo and bar
                else b
            )
            """,
        )

    def test_if_expression_parenthesised_test(self) -> None:
        self.assertTransform(
            1,
            7,
            """
            x = a if (foo and bar) else b
            """,
            """
            x = (
                a
                if (foo and bar)
                else b
            )
            """,
        )

    def test_parenthesised_if_expression(self) -> None:
        self.assertTransform(
            1,
            7,
            """
            x = (a if foo and bar else b)
            """,
            """
            x = (
                a
                if foo and bar
                else b
            )
            """,
        )

    def test_if_statement(self) -> None:
        self.assertTransform(
            1,
            1,
            """
            if foo and bar:
                print()
            """,
            """
            if (
                foo and
                bar
            ):
                print()
            """,
        )

    def test_elif_statement(self) -> None:
        self.assertTransform(
            3,
            1,
            """
            if foo and bar:
                print()
            elif foo and bar:
                print()
            """,
            """
            if foo and bar:
                print()
            elif (
                foo and
                bar
            ):
                print()
            """,
        )

    def test_boolean_expression(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            if foo and bar:
                print()
            """,
            """
            if (
                foo and
                bar
            ):
                print()
            """,
        )

    def test_long_boolean_expression(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            if foo and bar and baz:
                print()
            """,
            """
            if (
                foo and
                bar and
                baz
            ):
                print()
            """,
        )

    def test_mixed_boolean_expression_middle_and(self) -> None:
        # Not sure I like this output.
        self.assertTransform(
            1,
            16,
            """
            if foo or bar and baz or spam:
                print()
            """,
            """
            if foo or (
                bar and
                baz
            ) or spam:
                print()
            """,
        )

    def test_mixed_boolean_expression_outer_or(self) -> None:
        # Not sure I like this output.
        self.assertTransform(
            1,
            8,
            """
            if foo or bar and baz or spam:
                print()
            """,
            """
            if (
                foo or
                bar and baz or
                spam
            ):
                print()
            """,
        )

    def test_mixed_boolean_expression_middle_or(self) -> None:
        self.assertTransform(
            1,
            16,
            """
            if foo and bar or baz and spam:
                print()
            """,
            """
            if (
                foo and bar or
                baz and spam
            ):
                print()
            """,
        )

    def test_mixed_boolean_expression_outer_and(self) -> None:
        # Not sure I like this output.
        self.assertTransform(
            1,
            8,
            """
            if foo and bar or baz and spam:
                print()
            """,
            """
            if (
                foo and
                bar
            ) or baz and spam:
                print()
            """,
        )

    def test_parenthesized_boolean_expression(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            if (foo and bar):
                print()
            """,
            """
            if (
                foo and
                bar
            ):
                print()
            """,
        )

    def test_nested_wrapped_entity_in_unwrapped_entity(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            foo = {'a': [
                1,
                2,
            ], 'b': [42]}
            """,
            """
            foo = {
                'a': [
                    1,
                    2,
                ],
                'b': [42],
            }
            """,
        )

    def test_doesnt_wrap_method_on_owning_object(self) -> None:
        self.assertTransform(
            1,
            6,
            """
            foo.bar.baz(arg=value)
            """,
            """
            foo.bar.baz(arg=value)
            """,
        )

    def test_wraps_on_method_name(self) -> None:
        self.assertTransform(
            1,
            10,
            """
            foo.bar.baz(arg=value)
            """,
            """
            foo.bar.baz(
                arg=value,
            )
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

    def test_function_with_generator_arg(self) -> None:
        self.assertTransform(
            1,
            2,
            """
            foo(12, (x for x in 'abc'), 13)
            """,
            """
            foo(
                12,
                (x for x in 'abc'),
                13,
            )
            """,
        )

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_function_with_just_generator_arg(self) -> None:
        self.assertTransform(
            1,
            2,
            """
            foo(x for x in 'abc')
            """,
            """
            foo(
                (x for x in 'abc'),
            )
            """,
        )

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_function_indirect_with_just_generator_arg(self) -> None:
        self.assertTransform(
            1,
            25,
            """
            [foo][0](x for x in 'abc')
            """,
            """
            [foo][0](
                (x for x in 'abc'),
            )
            """,
        )

    @unittest.skipIf(sys.version_info >= (3, 8), "Token handling changes in 3.8+")
    def test_function_indirect_with_just_parenthesised_generator_arg(self) -> None:
        self.assertTransform(
            1,
            27,
            """
            [foo][0]((x for x in 'abc'))
            """,
            """
            [foo][0](
                (x for x in 'abc'),
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

    def test_nested_function_call_already_partially_wrapped(self) -> None:
        self.assertTransform(
            4,
            1,
            """
            foo("abcd {} {}".format(
                'efgh',
                'ijkl',
            ))
            """,
            """
            foo(
                "abcd {} {}".format(
                    'efgh',
                    'ijkl',
                ),
            )
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

    def test_double_nested_function_call_outer_already_partially_wrapped(self) -> None:
        self.assertTransform(
            2,
            30,
            """
            foo(
                bar=quox(spam=ham('abcd', 'efgh')),
            )
            """,
            """
            foo(
                bar=quox(spam=ham(
                    'abcd',
                    'efgh',
                )),
            )
            """,
        )

    def test_double_nested_function_call_outer_already_fully_wrapped(self) -> None:
        self.assertTransform(
            3,
            20,
            """
            foo(
                bar=quox(
                    spam=ham('abcd', 'efgh'),
                ),
            )
            """,
            """
            foo(
                bar=quox(
                    spam=ham(
                        'abcd',
                        'efgh',
                    ),
                ),
            )
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

    def test_indented_nested_function_call(self) -> None:
        self.assertTransform(
            2,
            24,
            """
            if True:
                foo(bar=quox('abcd', foo=42))
            """,
            """
            if True:
                foo(bar=quox(
                    'abcd',
                    foo=42,
                ))
            """,
        )

    def test_indented_nested_function_call_already_partially_wrapped(self) -> None:
        self.assertTransform(
            5,
            5,
            """
            if True:
                foo("abcd {} {}".format(
                    'efgh',
                    'ijkl',
                ))
            """,
            """
            if True:
                foo(
                    "abcd {} {}".format(
                        'efgh',
                        'ijkl',
                    ),
                )
            """,
        )

    def test_indented_double_nested_function_call(self) -> None:
        self.assertTransform(
            2,
            34,
            """
            if True:
                foo(bar=quox(spam=ham('abcd', 'efgh')))
            """,
            """
            if True:
                foo(bar=quox(spam=ham(
                    'abcd',
                    'efgh',
                )))
            """,
        )

    def test_indented_double_nested_function_call_outer_already_partially_wrapped(
        self,
    ) -> None:
        self.assertTransform(
            3,
            34,
            """
            if True:
                foo(
                    bar=quox(spam=ham('abcd', 'efgh')),
                )
            """,
            """
            if True:
                foo(
                    bar=quox(spam=ham(
                        'abcd',
                        'efgh',
                    )),
                )
            """,
        )

    def test_indented_double_nested_function_call_outer_already_fully_wrapped(self) -> None:
        self.assertTransform(
            4,
            24,
            """
            if True:
                foo(
                    bar=quox(
                        spam=ham('abcd', 'efgh'),
                    ),
                )
            """,
            """
            if True:
                foo(
                    bar=quox(
                        spam=ham(
                            'abcd',
                            'efgh',
                        ),
                    ),
                )
            """,
        )

    def test_indented_nested_function_call_with_preceding_arg(self) -> None:
        self.assertTransform(
            2,
            34,
            """
            if True:
                foo(spam='ham', bar=quox('abcd', foo=42))
            """,
            """
            if True:
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

    def test_empty_class_definition(self) -> None:
        self.assertTransform(
            1,
            8,
            """
            class Foo:
                pass
            """,
            """
            class Foo:
                pass
            """,
        )

    def test_class_definition_with_parents(self) -> None:
        self.assertTransform(
            1,
            10,
            """
            class Foo(ParentA, ParentB):
                pass
            """,
            """
            class Foo(
                ParentA,
                ParentB,
            ):
                pass
            """,
        )

    def test_class_definition_with_many_args(self) -> None:
        self.assertTransform(
            1,
            10,
            """
            class Foo(first, * args, second='ham', ** kwargs):
                pass
            """,
            """
            class Foo(
                first,
                * args,
                second='ham',
                ** kwargs,
            ):
                pass
            """,
        )
