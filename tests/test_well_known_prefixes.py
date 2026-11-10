"""A well-known prefix is bound on first use, not required in advance.

The file header has always said the standard prefixes are implicitly declared.
For ``skos:`` and ``dcterms:`` that was untrue in both implementations: each was
rejected in every position. Rather than retract the claim, the prefix is now
bound the first time a name uses it.

What gets written follows from that and needs no rule of its own. The writer
declares every prefix that is not implicit, so binding on use already means
"declare it when used, omit it otherwise" — a document that never names one
never reaches the line that binds it.

These are mostly round-trip tests. The requirement is not only that the names
resolve but that adDLe and the reference implementation write the *same*
document, and the prefix a namespace is written with is part of that.
"""

import addle
import pytest
from owlready2 import World

PREFIX = "@prefix : <http://e.org/>\n"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCTERMS = "http://purl.org/dc/terms/"


def load(body):
    return addle.loads(PREFIX + body, world=World(filename=":memory:"))


def rewrite(body):
    return addle.dumps(load(body), include_header=False)


def lines(text):
    return [l.strip() for l in text.splitlines()
            if l.strip() and not l.strip().startswith("#")]


def refusal(body):
    with pytest.raises(Exception) as caught:
        load(body)
    return str(caught.value)


# Axioms first in these documents: `@ann` on a subject that a later axiom turns
# into a class is a separate, pre-existing defect, and not what is under test.

def test_skos_needs_no_declaration():
    onto = load("A ⊑ ⊤\n@ann A skos:prefLabel \"x\"\n")
    assert onto.search(iri=SKOS + "prefLabel"), "skos: should bind without an @prefix line"


def test_dcterms_needs_no_declaration():
    """The namespace ends in ``/``, alone among the six the header names.

    The whole IRI is asserted rather than just that the prefix resolved: one
    that quietly gained or lost its final separator would send every name
    somewhere else without failing anywhere visible.
    """
    onto = load("A ⊑ ⊤\n@ann A dcterms:creator \"c\"\n")
    assert onto.search(iri=DCTERMS + "creator"), "dcterms:creator is " + DCTERMS + "creator"


def test_it_is_not_only_annotations():
    """Resolution is shared, so every position gains it at once."""
    onto = load("A ⊑ ∃skos:broader.B\n")
    assert onto.search(iri=SKOS + "broader")


def test_a_documents_own_binding_wins():
    onto = load("@prefix skos: <http://mine#>\nA ⊑ ⊤\n@ann A skos:note \"x\"\n")
    assert onto.search(iri="http://mine#note")
    assert not onto.search(iri=SKOS + "note"), "a declared binding must not be overwritten"


def test_another_vocabulary_is_still_refused():
    """The boundary: the header names six prefixes, so a seventh still needs declaring."""
    assert "Unknown prefix" in refusal("A ⊑ ⊤\n@ann A foaf:name \"x\"\n")


# ── What gets written ───────────────────────────────────────────────────────

def test_an_unused_vocabulary_is_not_declared():
    written = rewrite("Person ⊑ Agent\n")
    assert "skos" not in written and "dcterms" not in written, written


def test_a_used_vocabulary_is_declared_and_reads_back():
    written = rewrite("A ⊑ ⊤\n@ann A skos:prefLabel \"x\"\n")
    assert "@prefix skos: <%s>" % SKOS in lines(written), written
    assert addle.loads(written, world=World(filename=":memory:")).search(iri=SKOS + "prefLabel")


def test_the_usual_prefix_is_used_rather_than_one_coined_from_the_path():
    """Writing ``core:`` for SKOS would be a different document for one ontology.

    The writer builds its own prefix map — Owlready2 does not keep the names a
    document declared — and coins a prefix from a namespace's last path segment
    for anything it cannot shorten. For these two that produced ``core:`` and
    ``terms:``, which parse back to the same IRIs but do not match what the
    reference implementation writes.
    """
    written = lines(rewrite("A ⊑ ⊤\n@ann A skos:prefLabel \"x\"\n"
                            "@ann A dcterms:creator \"c\"\n"))
    assert "@prefix skos: <%s>" % SKOS in written, written
    assert "@prefix dcterms: <%s>" % DCTERMS in written, written
    assert not any(l.startswith("@prefix core:") or l.startswith("@prefix terms:")
                   for l in written), written


def test_rewriting_is_idempotent():
    once = rewrite("A ⊑ ⊤\n@ann A skos:prefLabel \"x\"\n@ann A dcterms:creator \"c\"\n")
    twice = addle.dumps(addle.loads(once, world=World(filename=":memory:")),
                        include_header=False)
    assert once == twice


# ── Order independence ──────────────────────────────────────────────────────

def test_ambiguity_does_not_depend_on_position():
    """``skos:a:C`` must mean the same thing wherever it appears.

    Binding on use makes the prefix map grow as the document is read, and this
    decision turns on a prefix existing rather than on what it expands to. Asked
    against the live map, the first document read as the individual ``skos`` of
    class ``a:C``, silently, while the second — identical but for an earlier
    mention — raised the ambiguity.
    """
    with_prefixes = "@prefix a: <http://ex/a#>\n"
    first = refusal(with_prefixes + "skos:a:C\n")
    later = refusal(with_prefixes + "X ⊑ ⊤\n@ann X skos:note \"e\"\nskos:a:C\n")
    assert "ambiguous" in first, first
    assert "ambiguous" in later, later


def test_a_lone_well_known_name_is_not_a_statement():
    assert "not a statement" in refusal("skos:Concept\n")
