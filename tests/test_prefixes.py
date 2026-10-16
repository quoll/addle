"""Every namespace the document uses gets a prefix, so every name stays a name.

Owlready2 does not record the prefix names a document declared, so by the time
the writer runs a ``@prefix mm:`` is gone. Without one, names in that namespace
are written as bare ``<http://…>`` IRIs — and a bare IRI is not a ``name`` in the
grammar, so the output cannot be read back at all. The coined names are only a
convenience; the IRIs they stand for are exact.
"""

import pytest
from owlready2 import World

import addle


def _render(src):
    return addle.dumps(addle.loads(src, world=World()), include_header=False)


def _prefix_lines(text):
    return [l for l in text.splitlines() if l.startswith("@prefix")]


def test_no_name_is_written_as_a_bare_iri():
    text = _render("@prefix : <http://ex.org/>\n@prefix mm: <http://mm.org/>\n"
                   "A ⊑ ∃mm:rel.B\n")
    axioms = [l for l in text.splitlines() if l.strip() and not l.startswith("@")]
    assert not [l for l in axioms if "<http" in l], axioms


@pytest.mark.parametrize(
    "namespace,expected",
    [
        ("http://mm.org/", "mm"),             # nothing but a host
        ("http://ex.org/model/", "model"),    # a path segment names the vocabulary
        ("http://snomed.info/id/", "id"),
        ("http://ex.org/v2#", "v2"),          # a hash fragment
    ],
)
def test_a_readable_prefix_is_coined(namespace, expected):
    text = _render("@prefix : <http://ex.org/>\n@prefix p: <%s>\nA ⊑ ∃p:rel.B\n"
                   % namespace)
    assert "@prefix %s: <%s>" % (expected, namespace) in _prefix_lines(text)


def test_colliding_names_are_counted_apart():
    text = _render("@prefix : <http://ex.org/>\n@prefix a: <http://one.org/model/>\n"
                   "@prefix b: <http://two.org/model/>\nA ⊑ ∃a:r.B ⊓ ∃b:s.C\n")
    lines = _prefix_lines(text)
    assert "@prefix model: <http://one.org/model/>" in lines
    assert "@prefix model2: <http://two.org/model/>" in lines


def test_the_output_can_be_read_back():
    """The point of all of it."""
    src = "@prefix : <http://ex.org/>\n@prefix mm: <http://mm.org/>\nA ⊑ ∃mm:rel.B\n"
    once = _render(src)
    onto = addle.loads(once, world=World())
    assert onto.search_one(iri="http://mm.org/rel") is not None


def test_a_second_pass_is_stable():
    """The coined name is only chosen once; after that it is in the document."""
    src = "@prefix : <http://ex.org/>\n@prefix mm: <http://mm.org/>\nA ⊑ ∃mm:rel.B\n"
    once = _render(src)
    assert once == addle.dumps(addle.loads(once, world=World()), include_header=False)


def test_implicit_prefixes_are_not_recoined():
    text = _render("@prefix : <http://ex.org/>\nA ⊑ ∀d.xsd:integer\n")
    assert not [l for l in _prefix_lines(text) if "XMLSchema" in l]
