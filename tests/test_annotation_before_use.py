"""An annotation may come before what it is about.

Order matters here in a way it does not for OWLAPI, which has no entity identity
to get wrong. Writing a triple on an IRI that carries no ``rdf:type`` leaves
Owlready2 holding an *individual* there, and asking that to become a class or a
property afterwards is a metaclass change it refuses outright.

``_annotate`` already declared its subject first for that reason, which is why
``@label`` and ``@doc`` were unaffected. The ``@ann`` branch declared only the
annotation *property*, so ``@ann A p "x"`` before ``A ⊑ ⊤`` crashed with
``__class__ assignment: 'ThingClass' object layout differs from 'Thing'``.

The tests that matter are the ones asserting the two orders mean the same thing:
not crashing is the symptom, and agreeing is the requirement.
"""

import addle
from owlready2 import DataPropertyClass, ObjectPropertyClass, ThingClass, World

PREFIX = "@prefix : <http://e.org/>\n"


def load(body):
    return addle.loads(PREFIX + body, world=World(filename=":memory:"))


def rewrite(body):
    return addle.dumps(load(body), include_header=False)


def statements(body):
    return sorted(l.strip() for l in rewrite(body).splitlines()
                  if l.strip() and not l.strip().startswith("#"))


# ── The entity is declared, as the right kind ───────────────────────────────

def test_an_annotated_name_can_then_be_a_class():
    onto = load('@ann A p "x"\nA ⊑ ⊤\n')
    assert isinstance(onto.A, ThingClass)


def test_an_annotated_name_can_then_be_subsumed():
    onto = load('@ann A p "x"\nA ⊑ B\n')
    assert onto.B in onto.A.is_a


def test_an_annotated_name_can_then_be_an_object_property():
    onto = load('@ann r p "x"\nA ⊑ ∃r.B\n')
    assert isinstance(onto.r, ObjectPropertyClass)


def test_an_annotated_name_can_then_be_a_data_property():
    onto = load('@ann d p "x"\nA ⊑ ∃d.xsd:string\n')
    assert isinstance(onto.d, DataPropertyClass)


def test_an_annotated_definition_still_follows_its_use():
    """A ≝ name keeps the rule from #12: untyped unless the document uses it."""
    onto = load('f ≝ ∀x (x)\n@ann f p "x"\nA ⊑ ∃f.⊤\n')
    assert isinstance(onto.f, ObjectPropertyClass)

    unused = load('f ≝ ∀x (x)\n@ann f p "x"\n')
    assert not isinstance(unused.f, (ThingClass, ObjectPropertyClass))


# ── The requirement: order does not change meaning ──────────────────────────

def test_either_order_writes_the_same_document():
    for annotation_first, axiom_first in [
        ('@ann A p "x"\nA ⊑ B\n',               'A ⊑ B\n@ann A p "x"\n'),
        ('@ann r p "x"\nA ⊑ ∃r.B\n',            'A ⊑ ∃r.B\n@ann r p "x"\n'),
        ('@ann d p "x"\nA ⊑ ∃d.xsd:string\n',   'A ⊑ ∃d.xsd:string\n@ann d p "x"\n'),
    ]:
        assert statements(annotation_first) == statements(axiom_first), annotation_first


def test_rewriting_is_idempotent():
    once = rewrite('@ann A p "x"\nA ⊑ B\n')
    twice = addle.dumps(addle.loads(once, world=World(filename=":memory:")),
                        include_header=False)
    assert once == twice


# ── Boundaries ──────────────────────────────────────────────────────────────

def test_the_annotation_forms_that_always_worked_still_do():
    """@label, @doc and @db go through _annotate, which always declared first."""
    for document in ('@label A "x"\nA ⊑ ⊤\n',
                     '@doc A "x"\nA ⊑ ⊤\n',
                     '@db A\nA ⊑ ⊤\n'):
        assert isinstance(load(document).A, ThingClass), document


def test_a_name_used_as_an_annotation_value_is_unaffected():
    """The value side never had the fault: it is written as an object, not a subject."""
    onto = load('@ann A p B\nB ⊑ ⊤\n')
    assert isinstance(onto.B, ThingClass)
