"""Exceptions raised by addle."""


class DleError(Exception):
    """Base class for every error addle raises."""


class DleSyntaxError(DleError):
    """A DLe document could not be parsed.

    Carries every diagnostic the parse produced, not just the first, because a
    single mistyped operator often cascades.
    """

    def __init__(self, problems, source=None):
        self.problems = list(problems)
        self.source = source
        where = source or "<string>"
        detail = "\n".join(
            "  %s:%d:%d %s" % (where, line, col, msg) for line, col, msg in self.problems
        )
        count = len(self.problems)
        super().__init__(
            "%d syntax error%s in %s:\n%s" % (count, "" if count == 1 else "s", where, detail)
        )


class DleSemanticError(DleError):
    """A document parsed, but describes something that cannot be built."""
