"""What the grammar gained when it was resynced with the reference implementation.

Each of these parsed as an error before the sync, so every test here is a new
capability rather than a guard on an old one. They are grouped by the part of
the grammar that changed: the STRING token, the recursive ``propertyExpr``, and
the unified facet bracket.
"""

import datetime

import pytest
from owlready2 import InverseFunctionalProperty
from owlready2.util import locstr

import addle

PREFIX = "@prefix : <http://ex.org/>\n@prefix ex: <http://ex.org/>\n"


def _label(parse, document):
    onto = parse(PREFIX + document + "\nA ⊑ B\n")
    return onto.search_one(iri="http://ex.org/A").label[0]


# ── strings: language tags and datatypes ────────────────────────────────────

def test_a_language_tag_becomes_a_locstr(parse):
    value = _label(parse, '@label A "Fuchs"@de')
    assert isinstance(value, locstr)
    # locstr compares its tag as well as its text, so the text is compared as text.
    assert str.__str__(value) == "Fuchs"
    assert value.lang == "de"


def test_a_regional_language_tag_is_kept_whole(parse):
    assert _label(parse, '@label A "Hanzi"@zh-Hant').lang == "zh-Hant"


@pytest.mark.parametrize(
    "literal,expected",
    [
        ('"3"^^xsd:int', 3),
        ('"3"^^xsd:integer', 3),
        ('"1.5"^^xsd:decimal', 1.5),
        ('"true"^^xsd:boolean', True),
        # The case that fails if the type is used in place of the parser:
        # bool("false") is True.
        ('"false"^^xsd:boolean', False),
        ('"2024-01-05"^^xsd:date', datetime.date(2024, 1, 5)),
    ],
)
def test_a_datatype_is_applied_the_way_owlready2_applies_it(parse, literal, expected):
    assert _label(parse, "@label A " + literal) == expected


def test_an_unknown_datatype_keeps_the_text_and_says_so(parse):
    warnings = []
    onto = parse(PREFIX + '@label A "q"^^ex:nosuch\nA ⊑ B\n', warnings=warnings)
    assert onto.search_one(iri="http://ex.org/A").label[0] == "q"
    assert any("ex:nosuch" in w for w in warnings)


def test_an_at_sign_inside_a_string_is_not_a_language_tag(parse):
    assert str.__str__(_label(parse, '@label A "a@b.com"')) == "a@b.com"


def test_a_tagged_literal_survives_into_the_store(parse):
    """The tag has to reach the quadstore, not just the Python value."""
    onto = parse(PREFIX + '@label A "Fuchs"@de\nA ⊑ B\n')
    text = addle.dumps(onto, include_header=False)
    assert '"Fuchs"@de' in text


# ── declarations may name their IRI with a string ───────────────────────────

def test_a_prefix_may_be_declared_with_a_string(parse):
    onto = parse('@prefix : <http://ex.org/>\n@prefix p: "http://p.org/"\np:A ⊑ B\n')
    assert onto.search_one(iri="http://p.org/A") is not None


def test_an_ontology_iri_may_be_a_string(parse):
    onto = parse('@prefix : <http://ex.org/>\n@ontology "http://ex.org/o"\nA ⊑ B\n')
    assert onto.base_iri.rstrip("#/") == "http://ex.org/o"


def test_a_name_may_begin_with_a_digit(parse):
    onto = parse("@prefix : <http://ex.org/>\n:1stClass ⊑ B\n")
    assert onto.search_one(iri="http://ex.org/1stClass") is not None


# ── propertyExpr is recursive ───────────────────────────────────────────────

@pytest.mark.parametrize("spelling", ["r⁻", "(r)⁻", "(r⁻)", "((r)⁻)"])
def test_an_inverse_may_be_parenthesised(parse, statements, spelling):
    onto = parse(PREFIX + "A ⊑ ∃%s.B\n" % spelling)
    assert "A ⊑ ∃r⁻.B" in statements(onto)


def test_a_doubled_inverse_cancels(parse, statements):
    onto = parse(PREFIX + "A ⊑ ∃r⁻⁻.B\n")
    assert "A ⊑ ∃r.B" in statements(onto)


def test_functional_on_an_inverse_is_inverse_functional(parse):
    onto = parse(PREFIX + "Functional(r⁻)\n")
    assert InverseFunctionalProperty in onto.search_one(iri="http://ex.org/r").is_a


def test_the_short_spelling_agrees(parse):
    onto = parse(PREFIX + "Func(r⁻)\n")
    assert InverseFunctionalProperty in onto.search_one(iri="http://ex.org/r").is_a


def test_functional_on_a_plain_property_is_unchanged(parse):
    from owlready2 import FunctionalProperty

    onto = parse(PREFIX + "Functional(r)\n")
    is_a = onto.search_one(iri="http://ex.org/r").is_a
    assert FunctionalProperty in is_a
    assert InverseFunctionalProperty not in is_a


def test_an_inverse_may_be_a_key(parse, statements):
    """OWL allows any object property expression in a key, so ``r⁻`` is legal."""
    onto = parse(PREFIX + "C ⊑ key(r⁻,s)\n")
    assert "C ⊑ key(r⁻,s)" in statements(onto)


def test_a_predicate_reference_may_be_parenthesised(parse):
    onto = parse(PREFIX + "A ⊑ ∃d₁,d₂.(sameValue)\n")
    assert onto.search_one(iri="http://ex.org/A") is not None


# ── one facet bracket, both spellings ───────────────────────────────────────

def test_comparison_and_keyword_facets_share_one_bracket(parse):
    onto = parse(PREFIX + "A ⊑ ∀d.xsd:integer[≥1 ⊓ totalDigits 3]\n")
    restriction = onto.search_one(iri="http://ex.org/A").is_a[-1]
    constrained = restriction.value
    assert constrained.min_inclusive == 1
    assert constrained.total_digits == 3


def test_a_keyword_facet_alone(parse):
    onto = parse(PREFIX + "A ⊑ ∀d.xsd:string[minLength 3]\n")
    assert onto.search_one(iri="http://ex.org/A").is_a[-1].value.min_length == 3


def test_a_parenthesised_facet_value(parse):
    onto = parse(PREFIX + "A ⊑ ∀d.xsd:string[minLength (3)]\n")
    assert onto.search_one(iri="http://ex.org/A").is_a[-1].value.min_length == 3


def test_an_unknown_facet_is_reported_not_silently_dropped(parse):
    warnings = []
    parse(PREFIX + 'A ⊑ ∀d.xsd:string[nosuchFacet "x"]\n', warnings=warnings)
    assert any("nosuchFacet" in w for w in warnings)


# ── datatype names resolve the way Owlready2 resolves them ──────────────────

@pytest.mark.parametrize("name", ["xsd:integer", "xsd:int", "xsd:token", "xsd:date"])
def test_an_xsd_subtype_is_a_datatype_not_a_fallback_string(parse, name):
    """``xsd:int`` and ``xsd:token`` are datatypes Owlready2 knows.

    They are absent from its Python-type-to-abbreviation table, which is what
    addle used to read, so both degraded to ``xsd:string`` with a warning. The
    IRI-to-abbreviation table has them.
    """
    warnings = []
    parse(PREFIX + "A ⊑ ∀d.%s\n" % name, warnings=warnings)
    assert not [w for w in warnings if "no Owlready2 datatype" in w]


def test_an_unknown_datatype_still_warns(parse):
    """Only an xsd: name is treated as a datatype at all; ex:nosuch is a class."""
    warnings = []
    parse(PREFIX + "A ⊑ ∀d.xsd:nosuch\n", warnings=warnings)
    assert any("no Owlready2 datatype" in w for w in warnings)
