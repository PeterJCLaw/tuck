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
