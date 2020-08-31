# Tuck

[![CircleCI](https://circleci.com/gh/PeterJCLaw/tuck.svg?style=svg)](https://circleci.com/gh/PeterJCLaw/tuck)

Semi-automated Python formatting.

The aim of this tool is to build up developer-assistance tooling for python
formatting. In general it will only format things when it needs to or when
directly instructed to.

## Usage

Most usage of Tuck is expected to be within editor extensions:

- [VSCode Tuck Extension](https://marketplace.visualstudio.com/items?itemName=peterjclaw.tuck)

Tuck can be also used as a command line tool:

``` bash
python -m tuck --positions <line>:<col> -- file.py
```

## Style

The wrapped statement style which Tuck targets aims to reduce diff noise without
concern for vertical space.

**Example**: Function definition

``` python
def foo(bar: str, quox: int = 0) -> float:
    return 4.2
```

wraps to:

``` python
def foo(
    bar: str,
    quox: int = 0,
) -> float:
    return 4.2
```

**Example**: List comprehension

``` python
[x for x in 'aBcD' if x.isupper()]
```

wraps to:

``` python
[
    x
    for x in 'aBcD'
    if x.isupper()
]
```
