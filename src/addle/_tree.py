"""Parse-tree construction: text in, ANTLR tree out.

Kept separate from the semantic layers so that both passes (and the tests) share
one definition of "how a DLe document becomes a tree", including error handling.
"""

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from ._antlr.DLESyntaxLexer import DLESyntaxLexer
from ._antlr.DLESyntaxParser import DLESyntaxParser
from .errors import DleSyntaxError


class _Collector(ErrorListener):
    """Gathers every diagnostic instead of printing to stderr and continuing."""

    def __init__(self):
        self.problems = []

    def syntaxError(self, recognizer, offending, line, column, msg, e):
        self.problems.append((line, column, msg))


def parse_text(text, source=None, strict=True):
    """Parse DLe text.

    Returns ``(tree, tokens, problems)``. With ``strict`` (the default) any
    syntax error raises :class:`~addle.errors.DleSyntaxError`; passing
    ``strict=False`` returns the partial tree alongside the diagnostics, which is
    what the CLI uses to report as much as it can about a broken document.
    """
    collector = _Collector()

    lexer = DLESyntaxLexer(InputStream(text))
    lexer.removeErrorListeners()
    lexer.addErrorListener(collector)

    tokens = CommonTokenStream(lexer)
    parser = DLESyntaxParser(tokens)
    parser.removeErrorListeners()
    parser.addErrorListener(collector)

    tree = parser.ontology()

    if collector.problems and strict:
        raise DleSyntaxError(collector.problems, source)
    return tree, tokens, collector.problems
