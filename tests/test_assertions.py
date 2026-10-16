"""Individual assertions: ``a : C``, ``(a,b) : r``, ``(a,"x") : d``, and their negations.

These are statements about individuals rather than about classes, and none of
them parsed before. Each is checked in both directions — what it builds, and
what it is written back as — because a form that reads but does not write turns
a document into a smaller one every time it passes through.
"""

import pytest

import addle
from addle.errors import DleSemanticError

PREFIX = "@prefix : <http://ex.org/>\n"


def _lines(render_fn, onto):
    return [l for l in render_fn(onto).splitlines()
            if l.strip() and not l.startswith("@")]


# ── class assertions ────────────────────────────────────────────────────────

def test_an_individual_is_given_its_class(parse):
    onto = parse(PREFIX + "a : Person\n")
    individual = onto.search_one(iri="http://ex.org/a")
    assert onto.Person in individual.is_a


def test_a_class_assertion_is_written_back(parse, render):
    onto = parse(PREFIX + "a : Person\n")
    assert "a : Person" in _lines(render, onto)


def test_an_individual_may_be_given_a_class_expression(parse):
    onto = parse(PREFIX + "a : Person ⊓ Adult\n")
    individual = onto.search_one(iri="http://ex.org/a")
    assert len(individual.is_a) > 1


def test_a_lone_individual_survives_the_round_trip(parse, render):
    """``lonely : ⊤`` is the only thing naming it, so the line has to stay."""
    onto = parse(PREFIX + "lonely : ⊤\n")
    assert "lonely : ⊤" in _lines(render, onto)


def test_an_individual_named_by_an_assertion_needs_no_type_line(parse, render):
    """``(a,b) : r`` already names b; ``b : ⊤`` beside it would say nothing."""
    onto = parse(PREFIX + "(a,b) : knows\n")
    assert "b : ⊤" not in _lines(render, onto)
    assert "a : ⊤" not in _lines(render, onto)


def test_a_datatype_cannot_be_asserted_as_a_class(parse):
    with pytest.raises(DleSemanticError):
        parse(PREFIX + "a : xsd:string\n")


# ── the unspaced form, and which reading wins ───────────────────────────────

def test_a_lone_prefixed_name_is_an_assertion_when_the_prefix_is_not_declared(parse):
    onto = parse(PREFIX + "a:Person\n")
    assert onto.Person in onto.search_one(iri="http://ex.org/a").is_a


def test_a_lone_prefixed_name_is_refused_when_the_prefix_is_declared(parse):
    """``p:Person`` is a name, not a statement, once ``p:`` means something."""
    with pytest.raises(DleSemanticError):
        parse(PREFIX + "@prefix p: <http://p.org/>\np:Person\n")


def test_the_separator_must_be_bare(parse):
    with pytest.raises(DleSemanticError):
        parse(PREFIX + "@prefix p: <http://p.org/>\na p: Person\n")


def test_the_second_reading_wins_when_only_its_prefix_is_declared(parse):
    """``a:p:C`` with ``p:`` declared is the individual a of class p:C."""
    onto = parse(PREFIX + "@prefix p: <http://p.org/>\na:p:C\n")
    assert onto.search_one(iri="http://p.org/C") in \
        onto.search_one(iri="http://ex.org/a").is_a


def test_both_prefixes_declared_is_ambiguous_and_refused(parse):
    with pytest.raises(DleSemanticError):
        parse(PREFIX + "@prefix e: <http://e.org/>\n@prefix p: <http://p.org/>\ne:p:C\n")


# ── property assertions ─────────────────────────────────────────────────────

def test_an_object_assertion_relates_two_individuals(parse):
    onto = parse(PREFIX + "(a,b) : knows\n")
    assert onto.search_one(iri="http://ex.org/b") in \
        onto.search_one(iri="http://ex.org/a").knows


def test_a_data_assertion_carries_a_literal(parse):
    onto = parse(PREFIX + '(a,"42") : age\n')
    assert onto.search_one(iri="http://ex.org/a").age == ["42"]


def test_a_typed_data_assertion_keeps_its_type(parse):
    onto = parse(PREFIX + '(a,"42"^^xsd:integer) : age\n')
    assert onto.search_one(iri="http://ex.org/a").age == [42]


def test_assertions_are_written_back(parse, render):
    onto = parse(PREFIX + '(a,b) : knows\n(a,"42") : age\n')
    lines = _lines(render, onto)
    assert "(a,b) : knows" in lines
    assert '(a,"42") : age' in lines


def test_an_object_assertion_makes_its_property_an_object_property(parse):
    onto = parse(PREFIX + "(a,b) : knows\n")
    assert onto.search_one(iri="http://ex.org/knows") in list(onto.object_properties())


def test_a_data_assertion_makes_its_property_a_data_property(parse):
    onto = parse(PREFIX + '(a,"x") : note\n')
    assert onto.search_one(iri="http://ex.org/note") in list(onto.data_properties())


# ── negative assertions ─────────────────────────────────────────────────────

def test_a_negative_object_assertion_round_trips(parse, render):
    onto = parse(PREFIX + "¬(a,b) : knows\n")
    assert "¬(a,b) : knows" in _lines(render, onto)


def test_a_negative_data_assertion_round_trips(parse, render):
    onto = parse(PREFIX + '¬(a,"7") : age\n')
    assert '¬(a,"7") : age' in _lines(render, onto)


def test_a_negative_assertion_is_not_a_positive_one(parse):
    """The whole point: ``¬(a,b) : r`` must not assert ``r(a,b)``."""
    onto = parse(PREFIX + "¬(a,b) : knows\n")
    subject = onto.search_one(iri="http://ex.org/a")
    assert not getattr(subject, "knows", [])


def test_positive_and_negative_assertions_coexist(parse, render):
    onto = parse(PREFIX + "(a,b) : knows\n¬(a,c) : knows\n")
    lines = _lines(render, onto)
    assert "(a,b) : knows" in lines
    assert "¬(a,c) : knows" in lines


# ── idempotence, which is the property that matters ─────────────────────────

def test_a_document_of_assertions_is_stable(parse, render):
    source = (PREFIX + 'a : Person\n(a,b) : knows\n(a,"42") : age\n'
              '¬(a,c) : knows\n¬(a,"7") : age\nlonely : ⊤\n')
    first = render(parse(source))
    second = render(addle.loads(first))
    assert first == second
