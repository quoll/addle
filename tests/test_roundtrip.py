"""Round-trip conformance.

These are the tests that matter most for interoperability: a document must mean
the same thing after a trip through Owlready2 and back, and writing must be
idempotent so that output is reviewable in a diff.
"""

import pytest
from owlready2 import World

import addle


def rewrite(text):
    """Read ``text`` and write it out again in a throwaway world."""
    world = World(filename=":memory:")
    onto = addle.loads(text, world=world)
    return addle.dumps(onto, include_header=False)


def logical_statements(text):
    """Every non-comment, non-blank line, as a multiset-friendly sorted list."""
    return sorted(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def test_reference_document_rewrite_is_idempotent(reference_document):
    """write(read(write(read(x)))) == write(read(x)) — byte for byte."""
    once = rewrite(reference_document)
    twice = rewrite(once)
    assert once == twice


def test_reference_document_statements_are_stable(reference_document):
    once = rewrite(reference_document)
    twice = rewrite(once)
    assert logical_statements(once) == logical_statements(twice)


def test_reference_document_survives_three_generations(reference_document):
    once = rewrite(reference_document)
    assert rewrite(rewrite(once)) == once


def test_reference_document_entity_counts_are_preserved(reference_document):
    first = World(filename=":memory:")
    onto_1 = addle.loads(reference_document, world=first)

    second = World(filename=":memory:")
    onto_2 = addle.loads(addle.dumps(onto_1, include_header=False), world=second)

    def counts(onto):
        return (
            len(list(onto.classes())),
            len(list(onto.object_properties())),
            len(list(onto.data_properties())),
            len(list(onto.annotation_properties())),
        )

    assert counts(onto_1) == counts(onto_2)


def test_reference_document_comments_are_preserved(reference_document):
    """Section comments are content: losing them loses the document's structure."""
    source_comments = {
        line.strip()
        for line in reference_document.splitlines()
        if line.strip().startswith("#")
    }
    written = rewrite(reference_document)
    written_comments = {
        line.strip() for line in written.splitlines() if line.strip().startswith("#")
    }
    # The four-line file header is documentation about DLe itself, not about any
    # entity, so it is not carried through as an annotation.
    header = {
        "# DLe — Description Logic (Extended)",
        "# Synthetic parser regression document.",
        "# This file intentionally avoids enterprise architecture terminology while exercising",
        "# the DLe syntax features used by the original foundation model.",
    }
    assert source_comments - header <= written_comments


def test_header_is_reparseable():
    """The header addle writes must itself be valid DLe (it is all comments)."""
    world = World(filename=":memory:")
    onto = addle.loads("Animal ⊑ ⊤\n", world=world)
    text = addle.dumps(onto)
    again = World(filename=":memory:")
    addle.loads(text, world=again)  # must not raise


@pytest.mark.parametrize(
    "document",
    [
        "Animal ⊑ ⊤\n",
        "Animal ⊑ Organism\nDog ⊑ Animal\n",
        "⊤ ⊑ ∀owns.Animal\nOwner ≡ ∃owns.Animal\n",
        "⊤ ⊑ ∀name.xsd:string\n≤1 name.⊤\n",
        '⊤ ⊑ ∀size.{"S","M","L"}\n',
        "⊤ ⊑ ∀n.xsd:integer[≥0 ⊓ <100]\n",
        "Trans(above)\nSym(beside)\nAsym(over)\nRef(near)\n",
        "⊤ ⊑ ∀a.Thing\n⊤ ⊑ ∀b.Thing\n⊤ ⊑ ∀c.Thing\na ∘ b ⊑ c\n",
        "⊤ ⊑ ∀owns.Animal\nownedBy ≡ owns⁻\n",
        'Animal ⊑ ⊤\n@db Animal "a"\n@label Animal "A"\n@doc Animal "d"\n',
        "greaterThan(x,y) ≝ x > y\n",
        "afterNow(x) ≝ x > now()\n⊤ ⊑ ∀when.xsd:dateTime\nF ≡ ∃when.afterNow\n",
        "Both ≡ A ⊓ ¬B\n",
        "⊤ ⊑ ∀id.xsd:string\nConcept ⊑ key(id)\n",
        "⊤ ⊑ ∀owns.Animal\n≥2 owns.Animal\n",
        "⊤ ⊑ ∀owns.Animal\nSelfish ≡ ∃owns.Self\n",
        "⊤ ⊑ ∀a.Thing\n⊤ ⊑ ∀b.Thing\na ⊓ b ⊑ ⊥\n",
    ],
    ids=lambda d: d.splitlines()[-1][:40],
)
def test_small_documents_are_idempotent(document):
    once = rewrite(document)
    assert rewrite(once) == once


def test_multi_role_restriction_keeps_its_expression(world):
    document = (
        "greaterThan(x,y) ≝ x > y\n"
        "⊤ ⊑ ∀a.xsd:integer\n"
        "⊤ ⊑ ∀b.xsd:integer\n"
        "Rising ≡ ∃a,b.greaterThan\n"
    )
    once = rewrite(document)
    assert "Rising ≡ ∃a,b.greaterThan" in once
    assert rewrite(once) == once


def test_document_survives_a_trip_through_rdf_xml(tmp_path, reference_document):
    """The real interoperability test: does the encoding survive generic OWL tooling?

    DLe stores multi-role restrictions, predicate definitions and comments as
    ordinary annotations precisely so they pass through any OWL serialiser
    untouched. Writing RDF/XML with Owlready2 and reading it back must therefore
    reproduce the DLe exactly.
    """
    direct = rewrite(reference_document)

    first = World(filename=":memory:")
    onto = addle.loads(reference_document, world=first)
    path = tmp_path / "reference.owl"
    onto.save(file=str(path), format="rdfxml")

    second = World(filename=":memory:")
    reloaded = second.get_ontology(str(path)).load()
    via_rdf = addle.dumps(reloaded, include_header=False)

    assert via_rdf == direct


def test_synthetic_iris_are_stable_across_rewrites():
    """A synthetic class must keep its IRI, or RDF-level identity would drift."""
    document = (
        "afterNow(x) ≝ x > now()\n"
        "⊤ ⊑ ∀when.xsd:dateTime\n"
        "Future ≡ ∃when.afterNow\n"
    )
    first = World(filename=":memory:")
    onto_1 = addle.loads(document, world=first)
    iri_1 = onto_1.Future.equivalent_to[0].iri

    second = World(filename=":memory:")
    onto_2 = addle.loads(addle.dumps(onto_1, include_header=False), world=second)
    iri_2 = onto_2.Future.equivalent_to[0].iri

    assert iri_1 == iri_2


def test_inline_comments_are_idempotent():
    once = rewrite("Animal ⊑ Organism  # note\nPlant ⊑ Organism\n")
    assert "# note" in once
    assert rewrite(once) == once
