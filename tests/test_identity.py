"""``a = b`` and ``x ≠ y``: which individuals are one thing, and which are not.

Both are n-ary in OWL — ``SameIndividual(a b c)`` is one axiom about three
individuals, not three axioms about pairs — and both are written back that way.
"""

import addle

PREFIX = "@prefix : <http://ex.org/>\n"


def _lines(render, onto):
    return [l for l in render(onto).splitlines()
            if l.strip() and not l.startswith("@")]


def test_two_individuals_may_be_the_same(parse):
    onto = parse(PREFIX + "a = b\n")
    assert onto.search_one(iri="http://ex.org/b") in \
        onto.search_one(iri="http://ex.org/a").equivalent_to


def test_sameness_chains(parse):
    onto = parse(PREFIX + "a = b = c\n")
    same = onto.search_one(iri="http://ex.org/a").equivalent_to
    assert {o.iri for o in same} == {"http://ex.org/b", "http://ex.org/c"}


def test_sameness_is_written_back_as_one_line(parse, render):
    assert "a = b = c" in _lines(render, parse(PREFIX + "a = b = c\n"))


def test_two_individuals_may_differ(parse):
    onto = parse(PREFIX + "x ≠ y\n")
    groups = list(onto.different_individuals())
    assert len(groups) == 1
    assert {e.iri for e in groups[0].entities} == \
        {"http://ex.org/x", "http://ex.org/y"}


def test_difference_is_one_set_not_a_chain_of_pairs(parse):
    """``x ≠ y ≠ z`` is one AllDifferent over three, not three pairs."""
    onto = parse(PREFIX + "x ≠ y ≠ z\n")
    groups = list(onto.different_individuals())
    assert len(groups) == 1
    assert len(groups[0].entities) == 3


def test_difference_is_written_back_as_one_line(parse, render):
    assert "x ≠ y ≠ z" in _lines(render, parse(PREFIX + "x ≠ y ≠ z\n"))


def test_members_need_no_separate_existence_line(parse, render):
    """The identity line already names them, so ``b : ⊤`` would add nothing."""
    lines = _lines(render, parse(PREFIX + "a = b\nx ≠ y\n"))
    assert "b : ⊤" not in lines
    assert "y : ⊤" not in lines


def test_a_lone_individual_is_still_kept(parse, render):
    lines = _lines(render, parse(PREFIX + "a = b\nlonely : ⊤\n"))
    assert "lonely : ⊤" in lines


def test_identity_statements_are_stable(parse, render):
    source = PREFIX + "a = b = c\nx ≠ y ≠ z\nlonely : ⊤\n"
    first = render(parse(source))
    assert first == render(addle.loads(first))
