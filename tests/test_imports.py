"""How ``@import`` names its target.

Three forms are accepted: an IRI, a prefixed name, and a double-quoted string.
The string exists because a relative path is the natural way to name a file
beside this one, and it cannot be carried as an IRI — under RFC 3986 a scheme
must be followed by a slash for the path to be hierarchical, so ``file:x.dle``
is opaque, has no path, and cannot be opened. A relative reference in either
form resolves against the document that declared it, which is the only base
that means anything.

The expected strings are the reference implementation's, taken from its
``ImportResolutionTest``, with one normalisation: ``urljoin`` writes
``file:///dir/x`` where Java writes ``file:/dir/x``. They name the same file.
"""

import pytest
from owlready2 import World

import addle
from addle.imports import (
    document_iri,
    first_segment_has_colon,
    relative_import_ref,
    resolve_iri_import,
    resolve_quoted_import,
)

BASE = "file:/dir/doc.dle"


def norm(iri):
    """``file:/x`` and ``file:///x`` are the same file; compare them as one."""
    return iri.replace("file:///", "file:/")


# ── @import "ref" ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "ref,expected",
    [
        # retrievable schemes pass through untouched
        ("http://example.org/x", "http://example.org/x"),
        ("https://example.org/x", "https://example.org/x"),
        ("file:/abs/v.dle", "file:/abs/v.dle"),
        # unretrievable schemes are file names whose first segment has a colon
        ("urn:x:y", "file:/dir/urn:x:y"),
        ("mailto:bob@example.org", "file:/dir/mailto:bob@example.org"),
        ("classpath:v.dle", "file:/dir/classpath:v.dle"),
        ("a:b.dle", "file:/dir/a:b.dle"),
        # ordinary paths
        ("v.dle", "file:/dir/v.dle"),
        ("sub/deep.dle", "file:/dir/sub/deep.dle"),
        ("../beside.dle", "file:/beside.dle"),
        # literal names: nothing is decoded, everything is encoded to build the IRI
        ("my vocab.dle", "file:/dir/my%20vocab.dle"),
        ("a%20b.dle", "file:/dir/a%2520b.dle"),
        ("a#b.dle", "file:/dir/a%23b.dle"),
        ("a?b.dle", "file:/dir/a%3Fb.dle"),
        ("100%.dle", "file:/dir/100%25.dle"),
    ],
)
def test_a_quoted_reference_is_a_path_unless_it_can_be_fetched(ref, expected):
    assert norm(resolve_quoted_import(BASE, ref)) == expected


def test_a_windows_path_is_recognised():
    """A drive letter looks like a scheme, so it gets its own case."""
    assert norm(resolve_quoted_import(BASE, "C:\\vocab.dle")) == "file:/C:/vocab.dle"
    assert norm(resolve_quoted_import(BASE, "C:/vocab.dle")) == "file:/C:/vocab.dle"
    assert norm(resolve_quoted_import(BASE, "D:\\a b\\v.dle")) == "file:/D:/a%20b/v.dle"


def test_with_no_base_a_path_is_left_as_it_stands():
    assert resolve_quoted_import(None, "v.dle") == "v.dle"
    assert resolve_quoted_import(None, "my v.dle") == "my%20v.dle", \
        "still escaped, so what is written can be read back"
    # A string source has an opaque document IRI; there is nothing to resolve to.
    assert resolve_quoted_import("string:ontology", "v.dle") == "v.dle"
    # An absolute reference never needed a base.
    assert resolve_quoted_import(None, "http://example.org/x") == "http://example.org/x"


# ── @import <ref> ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "ref,expected",
    [
        ("vocab-rdf.dle", "file:/dir/vocab-rdf.dle"),
        ("ontology/vocab.dle", "file:/dir/ontology/vocab.dle"),
        ("../beside.dle", "file:/beside.dle"),
        ("./here.dle", "file:/dir/here.dle"),
    ],
)
def test_a_relative_iri_resolves_against_the_document(ref, expected):
    assert norm(resolve_iri_import(BASE, ref)) == expected


@pytest.mark.parametrize(
    "ref",
    [
        "http://example.org/vocab.dle",
        "https://example.org/v",
        "file:/elsewhere/v.dle",
        "urn:example:vocab",
    ],
)
def test_an_absolute_iri_is_left_alone(ref):
    """The escape hatch for any scheme, including one only a catalogue can fetch."""
    assert resolve_iri_import(BASE, ref) == ref


def test_with_no_base_a_relative_iri_is_left_alone():
    assert resolve_iri_import(None, "vocab.dle") == "vocab.dle"
    assert resolve_iri_import(None, "http://e.org/v") == "http://e.org/v"
    assert resolve_iri_import("string:ontology", "v.dle") == "v.dle"


def test_an_iri_reference_is_not_encoded_again():
    """Unlike the quoted form the text is an IRI reference already, so
    ``<a%20b.dle>`` names the file ``a b.dle``."""
    assert norm(resolve_iri_import(BASE, "a%20b.dle")) == "file:/dir/a%20b.dle"


def test_the_first_segment_is_what_decides_a_colon():
    assert first_segment_has_colon("a:b.dle")
    assert first_segment_has_colon("urn:x:y")
    assert not first_segment_has_colon("sub/a:b.dle")
    assert not first_segment_has_colon("v.dle")


# ── writing it back ─────────────────────────────────────────────────────────

def test_a_file_beside_the_document_is_written_relative():
    """The inverse of resolving, so the pair can be moved together."""
    location = "file:///dir/doc.dle"
    assert relative_import_ref(location, "file:///dir/v.dle") == '"v.dle"'
    assert relative_import_ref(location, "file:///dir/sub/v.dle") == '"sub/v.dle"'
    # Decoded, because a quoted reference is a literal file name.
    assert relative_import_ref(location, "file:///dir/my%20v.dle") == '"my v.dle"'
    # A colon in the first segment would read back as a scheme.
    assert relative_import_ref(location, "file:///dir/a%3Ab.dle") == '"./a:b.dle"'


def test_anything_not_beside_the_document_is_written_absolute():
    location = "file:///dir/doc.dle"
    assert relative_import_ref(location, "http://example.org/v") == "<http://example.org/v>"
    assert relative_import_ref(location, "file:///other/v.dle") == "<file:///other/v.dle>"
    # Nowhere to be relative to.
    assert relative_import_ref(None, "file:///dir/v.dle") == "<file:///dir/v.dle>"


def test_a_document_read_from_a_string_has_no_location():
    assert document_iri(None) is None
    assert document_iri("") is None
    assert document_iri("http://example.org/doc.dle") == "http://example.org/doc.dle"


# ── end to end ──────────────────────────────────────────────────────────────

VOCAB = ("@ontology <http://example.org/v>\n"
         "@prefix : <http://example.org/v#>\n"
         "Borrowed ⊑ ⊤\n")
DOC_HEAD = ("@ontology <http://example.org/f>\n"
            "@prefix : <http://example.org/f#>\n")


def _imports_of(onto):
    return [o.base_iri.rstrip("#/") for o in onto.imported_ontologies]


@pytest.mark.parametrize("form", ["<vocab.dle>", '"vocab.dle"'])
def test_a_relative_import_resolves_to_the_file_beside_the_document(tmp_path, form):
    """The case the unit tests above cannot reach: the parser has to call them.

    Each of those passes whether or not the reader resolves anything, because
    they exercise the resolver directly. This one goes through ``load``, which
    is where the fault was.
    """
    (tmp_path / "vocab.dle").write_text(VOCAB, encoding="utf-8")
    doc = tmp_path / "doc.dle"
    doc.write_text(DOC_HEAD + "@import %s\nA ⊑ ⊤\n" % form, encoding="utf-8")

    onto = addle.load(doc, world=World())
    assert _imports_of(onto) == [(tmp_path / "vocab.dle").resolve().as_uri()]


def test_an_import_in_a_subdirectory_resolves_too(tmp_path):
    (tmp_path / "ontology").mkdir()
    (tmp_path / "ontology" / "vocab.dle").write_text(VOCAB, encoding="utf-8")
    doc = tmp_path / "doc.dle"
    doc.write_text(DOC_HEAD + "@import <ontology/vocab.dle>\nA ⊑ ⊤\n", encoding="utf-8")

    onto = addle.load(doc, world=World())
    assert _imports_of(onto) == [
        (tmp_path / "ontology" / "vocab.dle").resolve().as_uri()
    ]


def test_an_absolute_import_is_recorded_as_written(tmp_path):
    doc = tmp_path / "doc.dle"
    doc.write_text(DOC_HEAD + "@import <http://example.org/v>\nA ⊑ ⊤\n", encoding="utf-8")
    assert _imports_of(addle.load(doc, world=World())) == ["http://example.org/v"]


def test_a_document_read_from_text_keeps_its_import_relative():
    """Nothing to resolve against, so the reference stands and still writes back."""
    onto = addle.loads(DOC_HEAD + "@import <vocab.dle>\nA ⊑ ⊤\n", world=World())
    assert _imports_of(onto) == ["vocab.dle"]
    assert "@import <vocab.dle>" in addle.dumps(onto, include_header=False)


def test_a_resolved_import_is_written_back_as_the_path_it_came_in_as(tmp_path):
    """Resolving must not make the pair of files unmovable.

    An absolute `file:` IRI reloads only where it was written. Writing the
    relative form back is what lets a document and its vocabulary be copied
    somewhere else together, and it is what the reference implementation does.
    """
    (tmp_path / "vocab.dle").write_text(VOCAB, encoding="utf-8")
    doc = tmp_path / "doc.dle"
    doc.write_text(DOC_HEAD + "@import <vocab.dle>\nA ⊑ ⊤\n", encoding="utf-8")

    onto = addle.load(doc, world=World())
    out = tmp_path / "out.dle"
    addle.dump(onto, out, include_header=False)
    assert '@import "vocab.dle"' in out.read_text(encoding="utf-8")

    # And it is still a relative reference when read back.
    again = addle.load(out, world=World())
    assert _imports_of(again) == [(tmp_path / "vocab.dle").resolve().as_uri()]


def test_without_a_destination_the_absolute_form_is_written(tmp_path):
    """`dumps` with nowhere to go cannot know what the path would be relative to,
    and an absolute IRI is the honest answer rather than a guess."""
    (tmp_path / "vocab.dle").write_text(VOCAB, encoding="utf-8")
    doc = tmp_path / "doc.dle"
    doc.write_text(DOC_HEAD + "@import <vocab.dle>\nA ⊑ ⊤\n", encoding="utf-8")

    text = addle.dumps(addle.load(doc, world=World()), include_header=False)
    assert "@import <%s>" % (tmp_path / "vocab.dle").resolve().as_uri() in text
