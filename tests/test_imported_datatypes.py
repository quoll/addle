"""A datatype an import declares is a datatype here.

Kinds are inferred from how a name is used, and the filler of a restriction is
what says whether its property is an object or a data property. A name the
reader does not know is a class, so ``⊤ ⊑ ∀live.gl:date-interval`` made ``live``
an object property — and the document then went wrong somewhere else entirely,
on a sub-property axiom hundreds of lines away.

The declaration was there; it was in the imported document, and imports were
read after the kinds had been settled. They are read first now.
"""

import owlready2
import pytest
from owlready2 import World

import addle
import addle.imports

VOCAB = ("@ontology <http://example.org/v>\n"
         "@prefix gl: <http://example.org/types/>\n"
         "@prefix : <http://example.org/v#>\n"
         "gl:date-interval ⊑ rdfs:Literal\n")

DOC_HEAD = ("@ontology <http://example.org/f>\n"
            "@prefix gl: <http://example.org/types/>\n"
            "@prefix mm: <http://example.org/mm/>\n"
            "@prefix : <http://example.org/f#>\n")

# Every @ directive precedes every statement, as the grammar requires, so the
# import belongs in the head and the kind statement below it.
FIELD = "mm:Field ⊑ owl:topDataProperty\n"

#: The shape foundation-rdf.dle has: a domain, a range, and a super-property.
LIVE = ("live ⊑ mm:Field\n"
        "∃live.⊤ ⊑ Application\n"
        "⊤ ⊑ ∀live.gl:date-interval\n")


def write(directory, name, text):
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def kind_of(onto, iri):
    entity = onto.world[iri]
    if entity is None:
        return None
    if owlready2.DatatypeProperty in entity.is_a:
        return "data"
    if owlready2.ObjectProperty in entity.is_a:
        return "object"
    return type(entity).__name__


def test_a_datatype_declared_in_an_import_makes_its_property_a_data_property(tmp_path):
    write(tmp_path, "vocab.dle", VOCAB)
    doc = write(tmp_path, "doc.dle", DOC_HEAD + "@import <vocab.dle>\n" + FIELD + LIVE)

    onto = addle.load(doc, world=World())
    assert kind_of(onto, "http://example.org/f#live") == "data", \
        "live ranges on an imported datatype, so it is a data property"
    assert kind_of(onto, "http://example.org/mm/Field") == "data", \
        "and so its super-property stays one"


def test_the_quoted_import_form_carries_the_same_knowledge(tmp_path):
    write(tmp_path, "vocab.dle", VOCAB)
    doc = write(tmp_path, "doc.dle", DOC_HEAD + '@import "vocab.dle"\n' + FIELD + LIVE)
    assert kind_of(addle.load(doc, world=World()), "http://example.org/f#live") == "data"


def test_an_import_in_a_subdirectory_is_found(tmp_path):
    write(tmp_path, "ontology/vocab.dle", VOCAB)
    doc = write(tmp_path, "doc.dle",
                DOC_HEAD + "@import <ontology/vocab.dle>\n" + FIELD + LIVE)
    assert kind_of(addle.load(doc, world=World()), "http://example.org/f#live") == "data"


def test_the_importing_document_may_use_its_own_prefix(tmp_path):
    """What is shared is the IRI, not the spelling.

    The two documents are written by different people and need not agree on
    what to call a namespace, so matching on the name as written would work
    only by luck.
    """
    write(tmp_path, "vocab.dle", VOCAB)
    doc = write(tmp_path, "doc.dle",
                "@ontology <http://example.org/f>\n"
                "@prefix other: <http://example.org/types/>\n"
                "@prefix mm: <http://example.org/mm/>\n"
                "@prefix : <http://example.org/f#>\n"
                "@import <vocab.dle>\n" + FIELD
                + "live ⊑ mm:Field\n⊤ ⊑ ∀live.other:date-interval\n")
    assert kind_of(addle.load(doc, world=World()), "http://example.org/f#live") == "data"


def test_an_import_of_an_import_is_followed(tmp_path):
    """The reference asks for the imports closure, so this follows them too."""
    write(tmp_path, "deep.dle", VOCAB)
    write(tmp_path, "middle.dle",
          "@ontology <http://example.org/m>\n@prefix : <http://example.org/m#>\n"
          "@import <deep.dle>\n")
    doc = write(tmp_path, "doc.dle", DOC_HEAD + "@import <middle.dle>\n" + FIELD + LIVE)
    assert kind_of(addle.load(doc, world=World()), "http://example.org/f#live") == "data"


def test_imports_that_import_each_other_are_each_read_once(tmp_path, monkeypatch):
    """A cycle is someone else's mistake, not a reason to walk in circles.

    Counting the reads rather than only checking the answer, because an
    unguarded walk gets the right answer anyway: it recurses until Python's
    stack runs out, the RecursionError is caught as an unreadable import, and
    the whole thing unwinds looking like success. The defect is the thousand
    reads, so the thousand reads are what this asserts against.
    """
    write(tmp_path, "a.dle",
          "@ontology <http://example.org/a>\n@prefix : <http://example.org/a#>\n"
          "@import <b.dle>\n")
    write(tmp_path, "b.dle",
          "@ontology <http://example.org/b>\n@prefix gl: <http://example.org/types/>\n"
          "@prefix : <http://example.org/b#>\n@import <a.dle>\n"
          "gl:date-interval ⊑ rdfs:Literal\n")
    doc = write(tmp_path, "doc.dle", DOC_HEAD + "@import <a.dle>\n" + FIELD + LIVE)

    reads = []
    original = addle.imports._read_document
    monkeypatch.setattr(addle.imports, "_read_document",
                        lambda iri, warn: (reads.append(iri), original(iri, warn))[1])

    onto = addle.load(doc, world=World())
    assert kind_of(onto, "http://example.org/f#live") == "data", \
        "the datatype is declared round the cycle, so it still arrives"
    assert sorted(reads) == sorted(set(reads)), "each document read once: %s" % reads
    assert len(reads) == 2, reads


def test_without_the_import_the_name_is_still_unknown(tmp_path):
    """The boundary. Nothing says it is a datatype, so the old reading stands."""
    doc = write(tmp_path, "doc.dle", DOC_HEAD + FIELD + LIVE)
    assert kind_of(addle.load(doc, world=World()), "http://example.org/f#live") == "object"


# ── when an import cannot be read ───────────────────────────────────────────

def _warnings_for(doc):
    collected = []
    addle.load(doc, world=World(), warnings=collected)
    return collected


@pytest.mark.parametrize(
    "ref,why",
    [
        ("<nowhere.dle>", "a file that is not there"),
        ("<http://example.org/remote>", "a remote document, which is not fetched"),
    ],
)
def test_an_import_that_cannot_be_read_warns_about_kinds(tmp_path, ref, why):
    """Not merely that an import failed: that the failure can change the reading.

    Since what an import declares decides kinds here, losing one changes how
    the document reads — and the place it then goes wrong is rarely near the
    import. The warning has to say so, or the reader looks in the wrong place.
    """
    doc = write(tmp_path, "doc.dle", DOC_HEAD + "@import %s\n" % ref + FIELD + "A ⊑ ⊤\n")
    warnings = _warnings_for(doc)
    assert warnings, "a failed import should warn (%s)" % why
    assert "kinds inferred" in warnings[0], warnings[0]


def test_an_import_that_cannot_be_read_is_not_fatal(tmp_path):
    """Less informed, not refused. A document is still readable without it."""
    doc = write(tmp_path, "doc.dle", DOC_HEAD + "@import <nowhere.dle>\nA ⊑ ⊤\n")
    onto = addle.load(doc, world=World(), warnings=[])
    assert onto.world["http://example.org/f#A"] is not None


def test_an_import_that_is_there_warns_about_nothing(tmp_path):
    write(tmp_path, "vocab.dle", VOCAB)
    doc = write(tmp_path, "doc.dle", DOC_HEAD + "@import <vocab.dle>\n" + FIELD + LIVE)
    assert _warnings_for(doc) == []


def test_an_import_that_does_not_parse_is_treated_as_missing(tmp_path):
    """Someone else's syntax error is not this document's to report."""
    write(tmp_path, "broken.dle", "⊑ ⊑ ⊑ not a document\n")
    doc = write(tmp_path, "doc.dle", DOC_HEAD + "@import <broken.dle>\n" + FIELD + "A ⊑ ⊤\n")
    onto = addle.load(doc, world=World(), warnings=[])
    assert onto.world["http://example.org/f#A"] is not None


def test_a_document_read_from_text_has_nowhere_to_resolve_an_import(tmp_path):
    """No location, so the import cannot be found — and the warning says why
    that matters rather than leaving the reader to find out later."""
    warnings = []
    addle.loads(DOC_HEAD + "@import <vocab.dle>\n" + FIELD + "A ⊑ ⊤\n",
                world=World(), warnings=warnings)
    assert warnings and "kinds inferred" in warnings[0]
