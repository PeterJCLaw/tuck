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

# def search_for_preceding_token(tokens: List[tokenize.TokenInfo], position: Position) -> Optional[tokenize.TokenInfo]:

spam = 'ham'
