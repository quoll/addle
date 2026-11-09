"""A ≝ name used as an entity.

A definition on its own declares nothing: the reference implementation leaves
the name untyped and writes only the ``rdf:value`` annotation. What makes an
upper-case definition "usable in DL axioms" — as the file header puts it — is
the document going on to *use* it in class or role position.

These are round-trip tests because order is what used to break them. Writing
the annotation first left an IRI carrying triples but no ``rdf:type``, which
Owlready2 hands back as an individual; the later axiom then asked it to become
a class or a property, which is a metaclass change, and Owlready2 refused with
``'_set_ontology' property is not defined.`` or an error about object layouts.
"""

import addle
from owlready2 import ObjectPropertyClass, ThingClass, World

PREFIX = "@prefix : <http://e.org/>\n"


def rewrite(text):
    world = World(filename=":memory:")
    onto = addle.loads(PREFIX + text, world=world)
    return addle.dumps(onto, include_header=False)


def load(text):
    return addle.loads(PREFIX + text, world=World(filename=":memory:"))


def lines(text):
    return [l.strip() for l in text.splitlines()
            if l.strip() and not l.strip().startswith(("#", "@prefix"))]


DEFINED_CLASS = "Senior ≝ ∃x (age(x) > 65)\n"
DEFINED_ROLE = "senior ≝ ∃x (age(x) > 65)\n"


def test_a_defined_name_can_be_subsumed():
    onto = load(DEFINED_CLASS + "Senior ⊑ Person\n")
    assert isinstance(onto.Senior, ThingClass)
    assert onto.Person in onto.Senior.is_a


def test_a_defined_name_can_be_a_superclass():
    onto = load(DEFINED_CLASS + "Retired ⊑ Senior\n")
    assert isinstance(onto.Senior, ThingClass)
    assert onto.Senior in onto.Retired.is_a


def test_a_defined_name_in_role_position_is_a_property():
    onto = load(DEFINED_ROLE + "A ⊑ ∃senior.⊤\n")
    assert isinstance(onto.senior, ObjectPropertyClass)


def test_a_definition_alone_declares_no_entity():
    """The boundary: without a use, the name stays untyped, as in OWLAPI."""
    onto = load(DEFINED_CLASS)
    assert not isinstance(onto.Senior, (ThingClass, ObjectPropertyClass))


def test_a_predicate_restriction_is_not_a_use():
    """∃start,end.before puts `before` in predicate position, not class position.

    The reference implementation declares nothing for it, so neither does this.
    """
    onto = load("before ≝ ∀x (x < x)\nValid ⊑ ∃start,end.before\n")
    assert not isinstance(onto.before, (ThingClass, ObjectPropertyClass))


def test_the_definition_survives_beside_the_axiom_that_uses_it():
    out = rewrite(DEFINED_CLASS + "Senior ⊑ Person\n")
    assert "Senior ≝ ∃x (age(x) > 65)" in lines(out)
    assert "Senior ⊑ Person" in lines(out)


def test_every_shape_rewrites_idempotently():
    for text in (
        DEFINED_CLASS + "Senior ⊑ Person\n",
        DEFINED_CLASS + "Retired ⊑ Senior\n",
        DEFINED_ROLE + "A ⊑ ∃senior.⊤\n",
        "before ≝ ∀x (x < x)\nValid ⊑ ∃start,end.before\n",
        DEFINED_CLASS,
    ):
        once = rewrite(text)
        assert once == rewrite(once), text
