class TuckError(Exception):
    """Base type for errors which can be handled."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
