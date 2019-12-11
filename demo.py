from typing import List, Optional

# Literals
foo = {'key': 1234, 'other': {'bar': 5678}}

foo = {'key': 1234, 'other': 5678}

bar = ['abcd', 1234]

bar = ['abcd', 1234, {'key': 1234, 'other': {'bar': 5678}}, foo]

# Comprehensions

foo_comp = {str(k): v for k, v in foo}

bar_comp = [str(x) for x in bar]

# Function call

foo('abcd', 1234, spam='ham')

# Function definition


def simple(tokens: List[str], position: Optional[int]) -> Optional[str]:
    pass


def has_kwarg_only(tokens, position: Optional[int], *, bar: bytes) -> Optional[str]:
    pass


def has_varargs_and_kwargs(first, *args, second, **kwargs) -> Optional[str]:
    pass


spam = 'ham'
