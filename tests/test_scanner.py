"""Pass 1 decides what every name denotes; everything downstream depends on it."""

from addle._tree import parse_text
from addle.scanner import DATA, OBJECT, scan


def kinds(text):
    tree, _, _ = parse_text(text)
    return scan(tree)


def test_object_property_from_class_filler():
    k = kinds("⊤ ⊑ ∀owns.Thing\n")
    assert k.properties["owns"] == OBJECT


def test_data_property_from_datatype_filler():
    k = kinds("⊤ ⊑ ∀age.xsd:integer\n")
    assert k.properties["age"] == DATA


def test_data_property_from_union_of_datatypes():
    k = kinds("⊤ ⊑ ∀value.(xsd:integer ⊔ xsd:string)\n")
    assert k.properties["value"] == DATA


def test_data_property_from_literal_enumeration():
    k = kinds('⊤ ⊑ ∀size.{"S","M","L"}\n')
    assert k.properties["size"] == DATA


def test_data_property_from_numeric_facet():
    k = kinds("⊤ ⊑ ∀score.xsd:integer[≥0]\n")
    assert k.properties["score"] == DATA


def test_bare_names_are_classes():
    k = kinds("Animal ⊑ Organism\n")
    assert k.class_names >= {"Animal", "Organism"}
    assert not k.properties


def test_subproperty_axiom_looks_identical_to_subclass_axiom():
    """`a ⊑ b` is a sub-property axiom only because `b` is used as a property."""
    k = kinds("⊤ ⊑ ∀attribute.xsd:string\ntagId ⊑ attribute\n")
    assert k.properties["tagId"] == DATA
    assert "tagId" not in k.class_names


def test_property_kind_propagates_up_a_chain():
    text = (
        "⊤ ⊑ ∀attribute.xsd:string\n"
        "calculatedValue ⊑ attribute\n"
        "calculatedNumber ⊑ calculatedValue\n"
        "populationRisk ⊑ calculatedNumber\n"
    )
    k = kinds(text)
    for name in ["calculatedValue", "calculatedNumber", "populationRisk"]:
        assert k.properties[name] == DATA, name


def test_property_kind_propagates_down_from_a_known_subproperty():
    k = kinds("⊤ ⊑ ∀monitors.Animal\nmonitors ⊑ responsibility\n")
    assert k.properties["responsibility"] == OBJECT


def test_top_filler_leaves_kind_to_other_evidence():
    """`∃p.⊤` says nothing about p's kind; the range axiom decides."""
    k = kinds("∃name.⊤ ⊑ Concept\n⊤ ⊑ ∀name.xsd:string\n")
    assert k.properties["name"] == DATA


def test_unresolved_property_defaults_to_object():
    k = kinds("≤1 unknownRole.⊤\n")
    assert k.properties["unknownRole"] == OBJECT


def test_predicates_are_recorded():
    k = kinds("greaterThan(x,y) ≝ x > y\n")
    assert "greaterThan" in k.predicates
    assert "greaterThan" not in k.class_names


def test_multi_role_restriction_names_a_predicate():
    k = kinds("Rising ≡ ∃now,before.greaterThan\n")
    assert "greaterThan" in k.predicates
    assert k.properties["now"] == DATA


def test_annotation_property_from_ann_form():
    k = kinds('@ann Species note "text"\n')
    assert k.is_annotation_property("note")


def test_transitivity_implies_an_object_property():
    k = kinds("Trans(containedIn)\n")
    assert k.properties["containedIn"] == OBJECT


def test_functional_alone_does_not_decide_kind():
    """Func() applies to both kinds, so a range axiom must still win."""
    k = kinds("Func(id)\n⊤ ⊑ ∀id.xsd:string\n")
    assert k.properties["id"] == DATA


def test_reference_document_classification(reference_document):
    k = kinds(reference_document)
    counts = {}
    for kind in k.properties.values():
        counts[kind] = counts.get(kind, 0) + 1

    assert k.properties["locatedIn"] == OBJECT
    assert k.properties["healthScore"] == DATA
    assert k.properties["curates"] == OBJECT       # only via its super-property
    assert k.properties["calculatedValue"] == DATA  # only via propagation
    assert k.is_annotation_property("example")
    assert len(k.predicates) == 7
    assert counts[OBJECT] == 31
    assert counts[DATA] == 28
