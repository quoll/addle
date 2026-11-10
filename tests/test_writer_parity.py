"""The spellings addle writes are the ones the reference implementation writes.

Two implementations of one language that render the same ontology differently
cannot be diffed against each other, and a difference in spelling is
indistinguishable from a difference in meaning until someone checks by hand.
Each of these was a divergence, measured against `owltx` rather than assumed.
"""

import pytest
from owlready2 import World

import addle

PREFIX = "@prefix : <http://ex.org/>\n"


def _lines(src):
    onto = addle.loads(PREFIX + src, world=World())
    return [l for l in addle.dumps(onto, include_header=False).splitlines()
            if l.strip() and not l.startswith("@")]


# ── the long keyword spellings ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "short,long_form",
    [
        ("Trans(above)", "Transitive(above)"),
        ("Func(hasMother)", "Functional(hasMother)"),
        ("Ref(sameAge)", "Reflexive(sameAge)"),
        ("Irref(parentOf)", "Irreflexive(parentOf)"),
        ("Sym(beside)", "Symmetric(beside)"),
        ("Asym(taller)", "Asymmetric(taller)"),
    ],
)
def test_the_long_keyword_is_written(short, long_form):
    """Both spellings parse; the long one is written."""
    assert long_form in _lines(short + "\n")


def test_inverse_functional_is_written_as_functional_on_the_inverse():
    """DLe has no separate keyword: `Functional(r⁻)` is how OWL's dedicated
    InverseFunctional axiom is spelled, and nothing was written for it before."""
    assert "Functional(ssn⁻)" in _lines("Functional(ssn⁻)\n")


# ── domains ─────────────────────────────────────────────────────────────────

def test_an_object_property_domain_uses_the_existential_form():
    assert "∃worksAt.⊤ ⊑ Employee" in _lines(
        "∃worksAt.⊤ ⊑ Employee\n⊤ ⊑ ∀worksAt.Company\n")


def test_a_data_property_domain_uses_the_cardinality_form():
    """``∃d.⊤`` would put a data property where a class expression is expected.

    ⊤ is the top concept; the top data range is rdfs:Literal, a different
    thing. DL spells a data property's domain with a bound instead.
    """
    assert "(≥1 salary) ⊑ Employee" in _lines(
        "(≥1 salary) ⊑ Employee\n⊤ ⊑ ∀salary.xsd:integer\n")


def test_the_cardinality_domain_form_is_read():
    """It was not recognised at all, so the property kept no domain."""
    onto = addle.loads(PREFIX + "(≥1 salary) ⊑ Employee\n⊤ ⊑ ∀salary.xsd:integer\n",
                       world=World())
    assert [c.name for c in onto.salary.domain] == ["Employee"]


def test_only_a_bound_of_one_is_a_domain():
    """``(≥2 d) ⊑ C`` is a cardinality axiom and must stay one."""
    assert "(≥1 salary) ⊑ Employee" not in _lines(
        "(≥2 salary) ⊑ Employee\n⊤ ⊑ ∀salary.xsd:integer\n")


def test_the_parenthesised_and_bare_forms_agree():
    bare = _lines("≥1 salary ⊑ Employee\n⊤ ⊑ ∀salary.xsd:integer\n")
    parens = _lines("(≥1 salary) ⊑ Employee\n⊤ ⊑ ∀salary.xsd:integer\n")
    assert bare == parens


# ── facets ──────────────────────────────────────────────────────────────────

def test_mixed_facets_share_one_bracket():
    assert "A ⊑ ∀amount.xsd:integer[≥1 ⊓ totalDigits 3]" in _lines(
        "A ⊑ ∀amount.xsd:integer[≥1 ⊓ totalDigits 3]\n")


def test_comparison_facets_keep_their_symbols():
    assert "A ⊑ ∀n.xsd:integer[≥0 ⊓ <10]" in _lines("A ⊑ ∀n.xsd:integer[≥0 ⊓ <10]\n")


def test_a_keyword_facet_no_longer_uses_the_legacy_shape():
    assert 'A ⊑ ∀s.xsd:string[minLength 3]' in _lines("A ⊑ ∀s.xsd:string[minLength 3]\n")


# ── existence lines ─────────────────────────────────────────────────────────

def test_a_class_named_elsewhere_needs_no_existence_line():
    """``B ⊑ ⊤`` beside ``A ⊑ B`` says nothing the reader does not already learn."""
    lines = _lines("A ⊑ B\n")
    assert "A ⊑ B" in lines
    assert "B ⊑ ⊤" not in lines


def test_a_class_named_nowhere_else_keeps_its_line():
    assert "Lonely ⊑ ⊤" in _lines("A ⊑ B\nLonely ⊑ ⊤\n")


def test_a_name_is_not_found_inside_a_longer_one():
    """``Cat`` must not count as mentioned because ``Catalogue`` appears."""
    assert "Cat ⊑ ⊤" in _lines("A ⊑ Catalogue\nCat ⊑ ⊤\n")


@pytest.mark.parametrize("document", [
    "A ⊑ ∃r.B\n",
    "A ⊑ ∀r.B\n",
    "⊤ ⊑ ∀r.B\n",
])
def test_a_filler_is_a_mention(document):
    """The most ordinary way to name a class, and it was not counted as one.

    A dot separates a role from its filler, and no DLe name contains one:
    ``NameChar`` is ``NameStart | [0-9] | '-'``. Treating the dot as though it
    might be part of a longer name meant ``∃r.B`` did not count as naming ``B``,
    so a filler-only class kept an existence line the reference omits.
    """
    assert "B ⊑ ⊤" not in _lines(document), document


def test_a_disjointness_is_a_mention():
    """Named only in a line that follows the blocks, rather than inside one.

    Disjointness, difference, universal and orphan axioms are rendered after the
    entity blocks. Left out of the reckoning, a class named only there kept its
    existence line: the test is "anywhere else in the document", not "in some
    other block".
    """
    assert "B ⊑ ⊤" not in _lines("A ⊓ B ⊑ ⊥\n")


def test_a_local_part_is_not_a_mention():
    """``B`` in ``skos:B`` is one name's local part, not a mention of ``B``.

    The colon still disqualifies a match, and must: loosening the dot must not
    loosen this, or a class would lose the only line saying it exists.
    """
    assert "B ⊑ ⊤" in _lines("A ⊑ skos:B\nB ⊑ ⊤\n")
