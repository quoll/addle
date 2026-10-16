"""Natural idioms, translated to the declarative axiom they stand for.

Description logic has no notation of its own for several OWL axioms, so they are
written as the constructions that say the same thing: transitivity as a chain,
symmetry as a property related to its own inverse, reflexivity as ``∃r.Self``.
Each is translated back, which matches the reference implementation and is what
the §6.5 design note calls a service the library provides.

The rule governing all of them: translate only when the target is canonical, the
source is an eccentric way of writing it, and no neighbouring case is swept up.
The boundaries matter as much as the translations, so they are tested alongside.
"""

import pytest
from owlready2 import (
    AsymmetricProperty,
    IrreflexiveProperty,
    ReflexiveProperty,
    SymmetricProperty,
    TransitiveProperty,
    World,
)

import addle

# Ranges give the properties a kind before the idioms are read.
PREFIX = ("@prefix : <http://ex.org/>\n"
          "⊤ ⊑ ∀r.C\n⊤ ⊑ ∀s.C\n⊤ ⊑ ∀t.C\n")


def _read(src):
    return addle.loads(PREFIX + src, world=World())


def _lines(src):
    onto = _read(src)
    return [l for l in addle.dumps(onto, include_header=False).splitlines()
            if l.strip() and not l.startswith("@") and "∀" not in l
            and not l.endswith("⊑ ⊤")]


def _is_a(onto, name="r"):
    return onto.search_one(iri="http://ex.org/" + name).is_a


@pytest.mark.parametrize(
    "idiom,characteristic",
    [
        ("r ∘ r ⊑ r", TransitiveProperty),
        ("r ⊑ r⁻", SymmetricProperty),
        ("r⁻ ⊑ r", SymmetricProperty),
        ("r ≡ r⁻", SymmetricProperty),
        ("Disj(r, r⁻)", AsymmetricProperty),
        ("⊤ ⊑ ∃r.Self", ReflexiveProperty),
        ("∃r.Self ⊑ ⊥", IrreflexiveProperty),
    ],
)
def test_the_idiom_becomes_its_axiom(idiom, characteristic):
    assert characteristic in _is_a(_read(idiom + "\n"))


@pytest.mark.parametrize(
    "idiom,keyword",
    [
        ("r ∘ r ⊑ r", "Transitive(r)"),
        ("r ⊑ r⁻", "Symmetric(r)"),
        ("Disj(r, r⁻)", "Asymmetric(r)"),
        ("⊤ ⊑ ∃r.Self", "Reflexive(r)"),
        ("∃r.Self ⊑ ⊥", "Irreflexive(r)"),
    ],
)
def test_the_axiom_is_written_in_its_keyword_form(idiom, keyword):
    """The translation is one-way: what comes back is the declarative form."""
    assert keyword in _lines(idiom + "\n")


# ── the boundaries: what must not be swept up ───────────────────────────────

def test_a_real_chain_is_left_alone():
    assert "r ∘ s ⊑ t" in _lines("r ∘ s ⊑ t\n")


def test_a_chain_into_another_property_is_left_alone():
    """``r ∘ r ⊑ s`` is not transitivity — it says something about s."""
    assert "r ∘ r ⊑ s" in _lines("r ∘ r ⊑ s\n")


def test_a_sub_property_of_another_inverse_is_left_alone():
    """``r ⊑ s⁻`` relates two properties and is an ordinary sub-property axiom."""
    assert "r ⊑ s⁻" in _lines("r ⊑ s⁻\n")
    assert SymmetricProperty not in _is_a(_read("r ⊑ s⁻\n"))


def test_an_inverse_pair_is_left_alone():
    assert "r ≡ s⁻" in _lines("r ≡ s⁻\n")
    assert SymmetricProperty not in _is_a(_read("r ≡ s⁻\n"))


def test_ordinary_disjointness_is_left_alone():
    assert "Disj(r, s)" in _lines("Disj(r, s)\n")
    assert AsymmetricProperty not in _is_a(_read("Disj(r, s)\n"))


def test_a_filler_that_is_not_self_is_left_alone():
    assert "⊤ ⊑ ∃r.C" in _lines("⊤ ⊑ ∃r.C\n")
    assert ReflexiveProperty not in _is_a(_read("⊤ ⊑ ∃r.C\n"))


def test_self_subsumption_says_nothing_and_is_dropped():
    """``r ⊑ r`` is legal and vacuous; Owlready2 refuses it as an inheritance cycle."""
    assert "r ⊑ r" not in _lines("r ⊑ r\n")


# ── disjointness of more than two ───────────────────────────────────────────

def test_a_three_way_disjointness_survives():
    """Owlready2 reaches a two-member set from either member but a larger one
    from neither, so writing it per property lost it entirely."""
    assert "Disj(r, s, t)" in _lines("Disj(r, s, t)\n")


def test_class_disjointness_keeps_its_own_spelling():
    onto = addle.loads("@prefix : <http://ex.org/>\nA ⊓ B ⊑ ⊥\n", world=World())
    lines = addle.dumps(onto, include_header=False).splitlines()
    assert "A ⊓ B ⊑ ⊥" in lines


def test_idioms_are_stable():
    source = PREFIX + "r ∘ r ⊑ r\nDisj(s, t)\n"
    first = addle.dumps(addle.loads(source, world=World()), include_header=False)
    assert first == addle.dumps(addle.loads(first, world=World()),
                                include_header=False)
