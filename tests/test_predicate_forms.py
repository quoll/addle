"""Assertions and keys written as predicates, which is how a model writes them.

``C(a)``, ``r(a,b)``, ``d(a,"x")`` and ``HasKey(C () (d))`` are how first-order
logic and OWL say what DLe says with ``a : C``, ``(a,b) : r`` and
``C ⊑ key(d)``. All four are accepted on input; none are written, so a document
in these forms normalises to the DL spelling on its first round trip.

The forms sit last in the grammar's axiom rule, which is what keeps
``Transitive(parent)`` a transitivity declaration rather than an assertion that
``parent`` is an instance of a class called ``Transitive`` — both readings match,
and the first alternative wins. That is a decision, so it is pinned here.
"""

import pytest
from owlready2 import (
    AsymmetricProperty,
    FunctionalProperty,
    IrreflexiveProperty,
    ReflexiveProperty,
    SymmetricProperty,
    TransitiveProperty,
    World,
)

import addle

PREFIX = "@prefix : <http://ex.org/>\n@prefix myns: <http://my.org/>\n"


def _lines(render, onto):
    return [l for l in render(onto).splitlines()
            if l.strip() and not l.startswith("@")]


# ── the three assertion spellings ───────────────────────────────────────────

def test_a_unary_predicate_is_a_class_assertion(parse):
    onto = parse(PREFIX + "Dog(rex)\n")
    assert onto.Dog in onto.search_one(iri="http://ex.org/rex").is_a


def test_a_binary_predicate_with_two_names_is_an_object_assertion(parse):
    onto = parse(PREFIX + "likes(alice, bob)\n")
    assert onto.search_one(iri="http://ex.org/bob") in \
        onto.search_one(iri="http://ex.org/alice").likes


def test_a_binary_predicate_with_a_literal_is_a_data_assertion(parse):
    onto = parse(PREFIX + 'age(alice, "42")\n')
    assert onto.search_one(iri="http://ex.org/alice").age == ["42"]


def test_the_predicate_form_says_what_the_dl_form_says(parse, render):
    assert _lines(render, parse(PREFIX + "Dog(rex)\n")) == \
        _lines(render, parse(PREFIX + "rex : Dog\n"))


def test_the_predicate_forms_are_not_written_back(parse, render):
    """Input only: the writer keeps one spelling."""
    lines = _lines(render, parse(PREFIX + 'Dog(rex)\nlikes(alice, bob)\n'))
    assert "rex : Dog" in lines
    assert "(alice,bob) : likes" in lines
    assert not any("Dog(" in l for l in lines)


# ── the functional-syntax key ───────────────────────────────────────────────

def test_a_functional_syntax_key_is_read(parse, render):
    assert "C ⊑ key(id)" in _lines(render, parse(PREFIX + "HasKey(C () (id))\n"))


def test_both_key_groups_are_kept_apart(parse):
    """The split is read from the parentheses, not inferred.

    Nothing else in the document says what kind either property is, and they
    must still land on opposite sides.
    """
    onto = parse(PREFIX + "HasKey(C (hasPart) (serial))\n")
    assert [p.name for p in onto.object_properties()] == ["hasPart"]
    assert [p.name for p in onto.data_properties()] == ["serial"]


def test_a_key_on_a_complex_class_is_reported(parse):
    warnings = []
    parse(PREFIX + "HasKey(A ⊓ B () (id))\n", warnings=warnings)
    assert any("complex class" in w for w in warnings)


# ── the keyword rule ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "spelling,characteristic",
    [
        ("Transitive(parent)", TransitiveProperty),
        ("Trans(parent)", TransitiveProperty),
        ("Symmetric(parent)", SymmetricProperty),
        ("Sym(parent)", SymmetricProperty),
        ("Asymmetric(parent)", AsymmetricProperty),
        ("Reflexive(parent)", ReflexiveProperty),
        ("Irreflexive(parent)", IrreflexiveProperty),
        ("Functional(parent)", FunctionalProperty),
    ],
)
def test_a_keyword_is_never_an_assertion(parse, spelling, characteristic):
    onto = parse(PREFIX + spelling + "\n")
    assert characteristic in onto.search_one(iri="http://ex.org/parent").is_a


def test_a_keyword_form_asserts_nothing_about_any_class(parse):
    onto = parse(PREFIX + "Transitive(parent)\n")
    assert not list(onto.individuals())


def test_a_namespaced_keyword_is_an_ordinary_class(parse):
    """The way out for anyone who means a class called Transitive."""
    onto = parse(PREFIX + "myns:Transitive(parent)\n")
    individual = onto.search_one(iri="http://ex.org/parent")
    assert "http://my.org/Transitive" in [c.iri for c in individual.is_a
                                          if hasattr(c, "iri")]


# ── what the forms must not disturb ─────────────────────────────────────────

def test_a_predicate_definition_is_still_a_definition(parse, render):
    """Same shape, followed by ``≝``. Settled by the trailing token, not order."""
    onto = parse(PREFIX + "Foo(x, y) ≝ x is related to y\n")
    assert any("≝" in l for l in render(onto).splitlines())


def test_a_punned_class_assertion_is_refused_not_mangled(parse):
    """``ComponentType(Person)`` where Person is a class.

    Owlready2 maps one IRI to one entity, so the pun cannot be represented.
    Appending to the class's ``is_a`` would make it ``Person ⊑ ComponentType``
    — a different axiom, not a lossy version of the right one.
    """
    warnings = []
    onto = parse(PREFIX + "Person ⊑ Animal\nComponentType(Person)\n", warnings=warnings)
    lines = _lines(lambda o: addle.dumps(o, include_header=False), onto)
    assert "Person ⊑ ComponentType" not in lines
    assert any("cannot be represented" in w or "punning" in w for w in warnings)


def test_predicate_forms_are_stable(parse, render):
    source = PREFIX + 'Dog(rex)\nlikes(alice, bob)\nage(alice, "42")\nHasKey(C () (id))\n'
    first = render(parse(source))
    assert first == render(addle.loads(first, world=World()))
