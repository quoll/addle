"""Reading DLe into Owlready2: each construct must land on the right object."""

import owlready2
from owlready2 import (
    And,
    ConstrainedDatatype,
    FunctionalProperty,
    Inverse,
    IrreflexiveProperty,
    Not,
    OneOf,
    Or,
    Thing,
    TransitiveProperty,
)
from owlready2.base import MAX, MIN, ONLY, SOME

from addle.vocab import DLE_NS, OWL_NS, PREDICATE_IRI, RDFS_NS


def test_default_prefix_sets_the_base_iri(parse):
    onto = parse("@prefix : <http://example.org/o#>\nAnimal ⊑ ⊤\n")
    assert onto.base_iri == "http://example.org/o#"
    assert onto.Animal is not None


def test_ontology_declaration_wins_over_default_prefix(parse):
    onto = parse(
        "@prefix : <http://example.org/names#>\n"
        "@ontology <http://example.org/onto>\n"
        "Animal ⊑ ⊤\n"
    )
    assert onto.base_iri.startswith("http://example.org/onto")


def test_subclass_axiom(parse):
    onto = parse("Animal ⊑ Organism\n")
    assert onto.Organism in onto.Animal.is_a


def test_top_subsumption_does_not_add_a_parent(parse):
    onto = parse("Animal ⊑ ⊤\n")
    assert onto.Animal.is_a == [Thing]


def test_intersection_and_union(parse):
    onto = parse("Both ≡ A ⊓ B\nEither ≡ A ⊔ B\n")
    assert isinstance(onto.Both.equivalent_to[0], And)
    assert isinstance(onto.Either.equivalent_to[0], Or)


def test_union_is_flattened(parse):
    onto = parse("Any ≡ A ⊔ B ⊔ C\n")
    union = onto.Any.equivalent_to[0]
    assert isinstance(union, Or)
    assert len(union.Classes) == 3


def test_complement(parse):
    onto = parse("NotAnimal ≡ ¬Animal\n")
    assert isinstance(onto.NotAnimal.equivalent_to[0], Not)


def test_some_values_from(parse):
    onto = parse("Owner ≡ ∃owns.Animal\n")
    restriction = onto.Owner.equivalent_to[0]
    assert restriction.type == SOME
    assert restriction.value is onto.Animal


def test_all_values_from(parse):
    onto = parse("Careful ≡ ∀owns.Animal\n")
    assert onto.Careful.equivalent_to[0].type == ONLY


def test_cardinality_restrictions(parse):
    onto = parse("A ≡ ≥2 owns.Animal\nB ≡ ≤3 owns.Animal\nC ≡ =1 owns.Animal\n")
    assert (onto.A.equivalent_to[0].type, onto.A.equivalent_to[0].cardinality) == (MIN, 2)
    assert (onto.B.equivalent_to[0].type, onto.B.equivalent_to[0].cardinality) == (MAX, 3)
    assert onto.C.equivalent_to[0].cardinality == 1


def test_exists_top_on_object_property(parse):
    onto = parse("Owner ≡ ∃owns.⊤\n⊤ ⊑ ∀owns.Animal\n")
    restriction = onto.Owner.equivalent_to[0]
    assert restriction.type == SOME
    assert restriction.value is Thing


def test_exists_top_on_data_property_becomes_min_one(parse):
    """There is no Owlready2 spelling for the top data range; ≥1 p is exact."""
    onto = parse("Named ≡ ∃fullName.⊤\n⊤ ⊑ ∀fullName.xsd:string\n")
    restriction = onto.Named.equivalent_to[0]
    assert restriction.type == MIN
    assert restriction.cardinality == 1
    # Owlready2 reports an unqualified filler as None when freshly built and as
    # owl:Thing once re-read from triples.
    assert restriction.value in (None, Thing)


def test_domain_idiom(parse):
    onto = parse("∃owns.⊤ ⊑ Person\n⊤ ⊑ ∀owns.Animal\n")
    assert onto.owns.domain == [onto.Person]


def test_range_idiom(parse):
    onto = parse("⊤ ⊑ ∀owns.Animal\n")
    assert onto.owns.range == [onto.Animal]


def test_data_property_range_is_a_python_type(parse):
    onto = parse("⊤ ⊑ ∀fullName.xsd:string\n")
    assert onto.fullName.range == [str]
    assert issubclass(onto.fullName, owlready2.DataProperty)


def test_entity_named_like_an_ontology_attribute_is_reachable(parse):
    """`onto.name` is Owlready2's own attribute, so subscripting is required."""
    onto = parse("⊤ ⊑ ∀name.xsd:string\n")
    assert onto["name"].range == [str]


def test_subproperty_axiom(parse):
    onto = parse("⊤ ⊑ ∀relationship.Thing\nowns ⊑ relationship\n")
    assert onto.relationship in onto.owns.is_a


def test_inverse_property(parse):
    onto = parse("⊤ ⊑ ∀owns.Animal\nownedBy ≡ owns⁻\n")
    assert onto.ownedBy.inverse_property is onto.owns


def test_inverse_inside_a_restriction(parse):
    onto = parse("⊤ ⊑ ∀hasCurator.Animal\nCurated ≡ ∃hasCurator⁻.Person\n")
    restriction = onto.Curated.equivalent_to[0]
    assert isinstance(restriction.property, Inverse)


def test_property_characteristics(parse):
    onto = parse("Trans(above)\nSym(beside)\nIrref(beside)\n")
    assert TransitiveProperty in onto.above.is_a
    assert owlready2.SymmetricProperty in onto.beside.is_a
    assert IrreflexiveProperty in onto.beside.is_a


def test_max_one_bound_means_functional(parse):
    onto = parse("⊤ ⊑ ∀fullName.xsd:string\n≤1 fullName.⊤\n")
    assert FunctionalProperty in onto.fullName.is_a


def test_other_cardinality_bound_becomes_a_universal_axiom(parse):
    """`≥2 owns.Animal` means ⊤ ⊑ ≥2 owns.Animal, written as RDF on owl:Thing.

    Owlready2's GeneralClassAxiom cannot hold owl:Thing on its left, so the
    triple is written directly rather than through that class.
    """
    onto = parse("⊤ ⊑ ∀owns.Animal\n≥2 owns.Animal\n")
    subclass = onto.world._abbreviate(RDFS_NS + "subClassOf")
    bnodes = [
        obj
        for _, _, obj in onto.world._get_obj_triples_spo_spo(Thing.storid, subclass, None)
        if obj < 0
    ]
    assert len(bnodes) == 1
    restriction = onto._parse_bnode(bnodes[0])
    assert restriction.type == MIN
    assert restriction.cardinality == 2


def test_property_chain(parse):
    onto = parse("⊤ ⊑ ∀a.Thing\n⊤ ⊑ ∀b.Thing\n⊤ ⊑ ∀c.Thing\na ∘ b ⊑ c\n")
    chains = list(onto.c.property_chain)
    assert len(chains) == 1
    assert [p for p in chains[0].properties] == [onto.a, onto.b]


def test_property_chain_with_inverse(parse):
    onto = parse("⊤ ⊑ ∀a.Thing\n⊤ ⊑ ∀b.Thing\n⊤ ⊑ ∀c.Thing\na ∘ b⁻ ⊑ c\n")
    chain = list(onto.c.property_chain)[0]
    assert isinstance(list(chain.properties)[1], Inverse)


def test_disjoint_properties_from_intersection(parse):
    onto = parse("⊤ ⊑ ∀a.Thing\n⊤ ⊑ ∀b.Thing\na ⊓ b ⊑ ⊥\n")
    assert any(set(d.entities) == {onto.a, onto.b} for d in onto.a.disjoints())


def test_disjoint_role_keyword(parse):
    onto = parse("⊤ ⊑ ∀a.Thing\n⊤ ⊑ ∀b.Thing\nDisj(a,b)\n")
    assert list(onto.a.disjoints())


def test_self_restriction_bottom_means_irreflexive(parse):
    onto = parse("⊤ ⊑ ∀beside.Thing\n∃beside.Self ⊑ ⊥\n")
    assert IrreflexiveProperty in onto.beside.is_a


def test_individual_enumeration(parse):
    onto = parse("⊤ ⊑ ∀status.Thing\nA ≡ ∃status.{active}\n")
    assert isinstance(onto.A.equivalent_to[0].value, OneOf)


def test_literal_enumeration(parse):
    onto = parse('⊤ ⊑ ∀size.xsd:string\nSmall ≡ ∃size.{"S"}\n')
    one_of = onto.Small.equivalent_to[0].value
    assert list(one_of.instances) == ["S"]


def test_boolean_and_numeric_literals(parse):
    onto = parse(
        "⊤ ⊑ ∀flag.xsd:boolean\n⊤ ⊑ ∀count.xsd:integer\n"
        "A ≡ ∃flag.{true}\nB ≡ ∃count.{3}\n"
    )
    assert list(onto.A.equivalent_to[0].value.instances) == [True]
    assert list(onto.B.equivalent_to[0].value.instances) == [3]


def test_compact_numeric_facets(parse):
    onto = parse("⊤ ⊑ ∀n.xsd:integer[≥1 ⊓ <10]\n")
    datatype = onto.n.range[0]
    assert isinstance(datatype, ConstrainedDatatype)
    assert datatype.base_datatype is int
    assert datatype.min_inclusive == 1
    assert datatype.max_exclusive == 10


def test_keyword_facets(parse):
    onto = parse('⊤ ⊑ ∀id.[xsd:string ⊓ [matches "[A-Z]{3}"]]\n')
    datatype = onto.id.range[0]
    assert datatype.base_datatype is str
    assert datatype.pattern == "[A-Z]{3}"


def test_general_concept_equivalence_becomes_two_subsumptions(parse):
    """Owlready2 models only subsumption for anonymous left-hand sides."""
    onto = parse(
        "⊤ ⊑ ∀a.xsd:integer\n⊤ ⊑ ∀b.xsd:integer\n"
        '∃a.{1} ≡ ∃b.{2}\n'
    )
    assert len(list(onto.general_class_axioms())) == 2


def test_has_key(parse):
    onto = parse("⊤ ⊑ ∀id.xsd:string\nConcept ⊑ key(id)\n")
    has_key = onto.world._abbreviate(OWL_NS + "hasKey")
    triples = list(onto.world._get_obj_triples_spo_spo(onto.Concept.storid, has_key, None))
    assert len(triples) == 1
    assert onto._parse_list(triples[0][2]) == [onto.id]


# ── annotations ──────────────────────────────────────────────────────────────


def test_label_and_doc(parse):
    onto = parse('Animal ⊑ ⊤\n@label Animal "An Animal"\n@doc Animal "Docs."\n')
    assert onto.Animal.label == ["An Animal"]
    assert onto.Animal.comment == ["Docs."]


def test_storage_and_db(parse):
    onto = parse('Animal ⊑ ⊤\n@storage Animal "table.animal"\n@db Animal "animal_id"\n')
    assert onto.Animal.seeAlso == ["table.animal"]
    assert onto.Animal.isDefinedBy == ["animal_id"]


def test_db_without_a_string_uses_the_name(parse):
    onto = parse("Animal ⊑ ⊤\n@db Animal\n")
    assert onto.Animal.isDefinedBy == ["Animal"]


def test_ann_with_a_custom_property(parse):
    onto = parse('Animal ⊑ ⊤\n@ann Animal note "Careful."\n')
    values = [
        onto.world._to_python(v, d)
        for _, _, v, d in onto.world._get_data_triples_spod_spod(
            onto.world._abbreviate(onto.Animal.iri),
            onto.world._abbreviate(onto.base_iri + "note"),
            None,
            None,
        )
    ]
    assert values == ["Careful."]


def test_escapes_in_string_literals(parse):
    onto = parse(r'Animal ⊑ ⊤' + '\n' + r'@doc Animal "a \"quote\" and \\ backslash"' + "\n")
    assert onto.Animal.comment == ['a "quote" and \\ backslash']


def test_predicate_definition_is_stored_as_rdf_value(parse):
    onto = parse("greaterThan(x,y) ≝ x > y\n")
    subject = onto.world._abbreviate(onto.base_iri + "greaterThan")
    values = [
        onto.world._to_python(v, d)
        for _, _, v, d in onto.world._get_data_triples_spod_spod(
            subject, onto.world._abbreviate(PREDICATE_IRI), None, None
        )
    ]
    assert values == ["greaterThan(x,y) → x > y"]


def test_comments_are_preserved_as_annotations(parse):
    from addle.vocab import COMMENT_IRI

    onto = parse("Animal ⊑ ⊤\n\n# A remark\nPlant ⊑ ⊤\n")
    subject = onto.world._abbreviate(onto.Plant.iri)
    values = [
        onto.world._to_python(v, d)
        for _, _, v, d in onto.world._get_data_triples_spod_spod(
            subject, onto.world._abbreviate(COMMENT_IRI), None, None
        )
    ]
    assert values == [" A remark"]


def test_leading_header_block_is_not_attached_to_an_entity(parse):
    """The file header is documentation about the format, not about an entity."""
    from addle.vocab import COMMENT_IRI

    onto = parse("# DLe — header line\n# more header\n\nAnimal ⊑ ⊤\n")
    subject = onto.world._abbreviate(onto.Animal.iri)
    values = list(
        onto.world._get_data_triples_spod_spod(
            subject, onto.world._abbreviate(COMMENT_IRI), None, None
        )
    )
    assert values == []


# ── predicate restrictions ───────────────────────────────────────────────────


def test_multi_role_restriction_becomes_a_synthetic_class(parse):
    onto = parse(
        "greaterThan(x,y) ≝ x > y\n"
        "⊤ ⊑ ∀a.xsd:integer\n⊤ ⊑ ∀b.xsd:integer\n"
        "Rising ≡ ∃a,b.greaterThan\n"
    )
    synthetic = onto.Rising.equivalent_to[0]
    assert synthetic.iri.startswith(DLE_NS)
    assert synthetic.label == ["∃a,b.greaterThan"]


def test_single_role_predicate_restriction_also_becomes_a_class(parse):
    onto = parse(
        "afterNow(x) ≝ x > now()\n"
        "⊤ ⊑ ∀when.xsd:dateTime\n"
        "Future ≡ ∃when.afterNow\n"
    )
    synthetic = onto.Future.equivalent_to[0]
    assert synthetic.iri.startswith(DLE_NS)
    assert synthetic.label == ["∃when.afterNow"]


def test_synthetic_iri_matches_the_java_implementation(parse):
    """The IRI embeds a java.lang.String.hashCode of the expression text.

    Both implementations must mint the same IRI or the same document parsed by
    each would produce different RDF.
    """
    onto = parse(
        "afterNow(x) ≝ x > now()\n"
        "⊤ ⊑ ∀migrationDate.xsd:date\n"
        "MigrationInFuture ≡ ∃migrationDate.afterNow\n"
    )
    assert (
        onto.MigrationInFuture.equivalent_to[0].iri
        == DLE_NS + "E_afterNow_3ce45e2f"
    )


def test_same_expression_reuses_one_synthetic_class(parse):
    onto = parse(
        "afterNow(x) ≝ x > now()\n"
        "⊤ ⊑ ∀when.xsd:dateTime\n"
        "A ≡ ∃when.afterNow\nB ≡ ∃when.afterNow\n"
    )
    assert onto.A.equivalent_to[0] is onto.B.equivalent_to[0]


# ── whole document ───────────────────────────────────────────────────────────


def test_reference_document(world, reference_document):
    import addle

    warnings = []
    onto = addle.loads(reference_document, world=world, warnings=warnings)

    assert onto.base_iri == "http://example.org/wildlife-test#"
    assert len(list(onto.object_properties())) == 31
    assert len(list(onto.data_properties())) == 28
    assert len(list(onto.annotation_properties())) == 3

    # The only warnings should be the two genuine OWL punning cases, where an
    # IRI is used as both a property and an individual.
    assert len(set(warnings)) == 2
    assert all("punning" in w for w in warnings)

    assert TransitiveProperty in onto.containedIn.is_a
    assert onto.contains.inverse_property is onto.locatedIn
    assert onto.healthScore.range and isinstance(onto.healthScore.range[0], OneOf)
