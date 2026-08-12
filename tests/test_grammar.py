"""The vendored grammar must stay identical to the reference implementation's.

`grammar/DLESyntax.g4` is a copy of the file in github.com/quoll/DLe. These tests
make drift loud: a silent divergence would mean addle and the Java library accept
different languages while both claiming to implement DLe.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from addle._tree import parse_text
from addle.errors import DleSyntaxError

ROOT = Path(__file__).resolve().parent.parent
GRAMMAR = ROOT / "grammar" / "DLESyntax.g4"
CHECKSUM = ROOT / "grammar" / "DLESyntax.g4.sha256"


def test_grammar_matches_recorded_hash():
    actual = hashlib.sha256(GRAMMAR.read_bytes()).hexdigest()
    expected = CHECKSUM.read_text().split()[0]
    assert actual == expected, (
        "grammar/DLESyntax.g4 changed without re-recording its hash. If the "
        "change is intentional: tools/grammar.py generate && tools/grammar.py update"
    )


def test_generated_parser_matches_grammar_hash():
    """The checked-in parser must have been generated from this grammar."""
    banner = (ROOT / "src" / "addle" / "_antlr" / "DLESyntaxParser.py").read_text(
        encoding="utf-8"
    ).splitlines()[0]
    assert "DLESyntax.g4" in banner
    assert "ANTLR 4.13" in banner, (
        "generated parser is from a different ANTLR version than the pinned runtime"
    )


def test_grammar_tool_check_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "grammar.py"), "check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_reference_document_parses_without_error(reference_document):
    tree, tokens, problems = parse_text(reference_document, strict=False)
    assert problems == []
    assert len(tree.statement()) == 388


@pytest.mark.parametrize(
    "text",
    [
        "Animal ⊑",
        "⊑ Animal",
        "Animal ⊓⊓ Dog",
        "∃.Animal",
        "@label",
    ],
)
def test_malformed_documents_raise(text):
    with pytest.raises(DleSyntaxError):
        parse_text(text)


def test_syntax_error_names_the_source_and_location():
    with pytest.raises(DleSyntaxError) as error:
        parse_text("Animal ⊑\nDog ⊑\n", source="bad.dle")
    assert error.value.problems
    line, column, message = error.value.problems[0]
    assert line == 2 and message
    assert "bad.dle:2" in str(error.value)
