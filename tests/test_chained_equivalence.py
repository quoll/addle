"""``A ≡ B ≡ C`` is one axiom over three operands, not a pair with a tail.

Only the first two were read before, so every operand past the second was
dropped in silence — a document said one thing and came back saying less.
"""

from owlready2 import World

import addle

PREFIX = "@prefix : <http://ex.org/>\n"


def _equiv_lines(onto):
    return [l for l in addle.dumps(onto, include_header=False).splitlines()
            if "≡" in l]


def test_every_operand_is_read(parse):
    onto = parse(PREFIX + "A ≡ B ≡ C\n")
    assert {c.name for c in onto.A.equivalent_to} == {"B", "C"}


def test_nothing_is_dropped_past_the_second(parse):
    onto = parse(PREFIX + "A ≡ B ≡ C ≡ D\n")
    assert {c.name for c in onto.A.equivalent_to} == {"B", "C", "D"}


def test_it_is_written_as_one_chained_line(parse):
    assert _equiv_lines(parse(PREFIX + "A ≡ B ≡ C\n")) == ["A ≡ B ≡ C"]


def test_a_simple_equivalence_is_unchanged(parse):
    assert _equiv_lines(parse(PREFIX + "A ≡ B\n")) == ["A ≡ B"]


def test_an_expression_may_appear_in_the_chain(parse):
    assert _equiv_lines(parse(PREFIX + "A ≡ B ⊓ C ≡ D\n")) == ["A ≡ B ⊓ C ≡ D"]


def test_a_chain_is_stable(parse):
    first = addle.dumps(parse(PREFIX + "A ≡ B ≡ C\n"), include_header=False)
    assert first == addle.dumps(addle.loads(first, world=World()),
                                include_header=False)
