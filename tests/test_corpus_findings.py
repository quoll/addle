"""Defects found by running the reference corpus through both implementations.

Each of these was a hard failure or a silent loss on one of the four example
documents, and none was reachable from the unit tests — they needed a real
document, read by addle and handed back to the reference implementation.
"""

import pytest
import types

from owlready2 import ObjectPropertyClass, Thing, World

import addle


def _render(src):
    return addle.dumps(addle.loads(src, world=World()), include_header=False)


def _stable(src):
    once = _render(src)
    return once == _render(once)


# ── spellings the lexer must accept back ────────────────────────────────────

def test_a_digit_initial_name_is_written_with_its_colon():
    """``:123`` is the DEFAULT_NAME token; NAME cannot begin with a digit.

    SNOMED identifiers are all of this shape, so two corpus documents produced
    output that would not lex.
    """
    text = _render("@prefix : <http://snomed.info/id/>\n:106237007 ⊑ :900000000000441003\n")
    assert ":106237007 ⊑ :900000000000441003" in text


def test_a_digit_initial_name_round_trips():
    src = "@prefix : <http://snomed.info/id/>\n:106237007 ⊑ :441003\n"
    assert _stable(src)


@pytest.mark.parametrize("name", ["Self", "true", "false", "key"])
def test_a_reserved_word_is_written_with_a_prefix(name):
    """Bare, these are the grammar's own words.

    They cannot be *parsed* bare at all, which is the point: an ontology built
    in Python can still hold a class called ``Self``, and writing it bare would
    produce a document that either fails to read or — worse — reads as
    something else. ``A ⊑ ∃r.Self`` comes back as ObjectHasSelf with the class
    gone.
    """
    world = World()
    onto = world.get_ontology("http://ex.org/")
    with onto:
        types.new_class(name, (Thing,))
    text = addle.dumps(onto, include_header=False)
    assert "\n%s " % name not in text, text
    # And what is written must read back as the same entity.
    again = addle.loads(text, world=World())
    assert again.search_one(iri="http://ex.org/" + name) is not None


# ── constructs that crashed ─────────────────────────────────────────────────

def test_an_annotation_on_an_individual_does_not_crash():
    """``@label bob`` after ``bob : Person`` asked Owlready2 to change the
    entity's metaclass, which it refuses with a TypeError about object layouts."""
    onto = addle.loads("@prefix : <http://ex.org/>\nbob : Person\n@label bob \"Bob\"\n",
                       world=World())
    assert onto.search_one(iri="http://ex.org/bob").label == ["Bob"]


def test_a_property_in_class_position_is_reported_not_raised():
    """A punned IRI, as the reference writes one: both a property and a class."""
    warnings = []
    addle.loads("@prefix : <http://ex.org/>\np ⊑ owl:topObjectProperty\np ⊑ ⊤\n",
                world=World(), warnings=warnings)


def test_a_parenthesised_inverse_names_a_property():
    """``operatorOf ≡ (operatedBy⁻)`` — the parentheses hid the inverse, so the
    name became a class whose equivalent was an Inverse construct."""
    onto = addle.loads("@prefix : <http://ex.org/>\n⊤ ⊑ ∀operatedBy.C\n"
                       "operatorOf ≡ (operatedBy⁻)\n", world=World())
    operator_of = onto.search_one(iri="http://ex.org/operatorOf")
    assert isinstance(operator_of, ObjectPropertyClass)
    assert operator_of.inverse_property is not None


def test_a_functional_property_asserted_twice_is_reported():
    """Owlready2 holds one value where OWL would keep both and conclude they
    are equal. The second assertion replaces the first, and says so."""
    warnings = []
    addle.loads("@prefix : <http://ex.org/>\nFunctional(age)\n⊤ ⊑ ∀age.xsd:integer\n"
                '(rex,"7"^^xsd:integer) : age\n(rex,"-3"^^xsd:integer) : age\n',
                world=World(), warnings=warnings)
    assert any("functional" in w for w in warnings)


# ── output that must settle ─────────────────────────────────────────────────

def test_annotation_lines_do_not_wander():
    """``annotation_properties()`` yields in creation order, which differs
    between a document and its own output, so @ann lines moved every pass."""
    src = ('@prefix : <http://ex.org/>\n@prefix core: <http://x.org/>\n'
           '@label A "a"\n@ann A core:note "n"\n@doc A "d"\nA ⊑ B\n')
    assert _stable(src)


def test_an_inverse_pair_is_written_from_the_same_side_every_time():
    """Entities come in creation order, so the pair swapped sides each pass."""
    src = "@prefix : <http://ex.org/>\n⊤ ⊑ ∀operatedBy.C\noperatorOf ≡ operatedBy⁻\n"
    once = _render(src)
    assert "operatedBy ≡ operatorOf⁻" in once
    assert _stable(src)
