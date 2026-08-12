"""Writing DLe out again: the text must say what the ontology says."""

import types

import pytest
from owlready2 import DataProperty, ObjectProperty, Thing

import addle
from addle.vocab import DLE_NS


def test_header_is_included_by_default(world):
    onto = addle.loads("Animal ⊑ ⊤\n", world=world)
    assert addle.dumps(onto).startswith("# DLe — Description Logic (Extended)")


def test_header_can_be_omitted(world, render):
    onto = addle.loads("Animal ⊑ ⊤\n", world=world)
    assert not render(onto).startswith("#")


def test_ontology_iri_is_declared(world, render):
    onto = addle.loads("@prefix : <http://example.org/o#>\nAnimal ⊑ ⊤\n", world=world)
    assert "@ontology <http://example.org/o>" in render(onto)


def test_default_prefix_is_declared_so_bare_names_resolve(world, render):
    onto = addle.loads("@prefix : <http://example.org/o#>\nAnimal ⊑ ⊤\n", world=world)
    text = render(onto)
    assert "@prefix : <http://example.org/o#>" in text
    assert "Animal ⊑ ⊤" in text


def test_implicit_prefixes_are_not_redeclared(world, render):
    onto = addle.loads("⊤ ⊑ ∀name.xsd:string\n", world=world)
    assert "@prefix xsd:" not in render(onto)


def test_classes_with_no_axioms_still_appear(world, statements):
    onto = addle.loads("Animal ⊑ ⊤\n", world=world)
    assert "Animal ⊑ ⊤" in statements(onto)


def test_borrowed_vocabulary_is_not_redefined(world, statements):
    """`rdfs:Proposition ⊑ ⊤` would claim to define someone else's class."""
    onto = addle.loads("Statement ⊑ rdfs:Proposition\n", world=world)
    lines = statements(onto)
    assert "Statement ⊑ rdfs:Proposition" in lines
    assert "rdfs:Proposition ⊑ ⊤" not in lines


@pytest.mark.parametrize(
    "text",
    [
        "Both ≡ A ⊓ B",
        "Either ≡ A ⊔ B",
        "NotA ≡ ¬A",
        "Owner ≡ ∃owns.Animal",
        "Careful ≡ ∀owns.Animal",
        "Two ≡ ≥2 owns.Animal",
        "AtMost ≡ ≤3 owns.Animal",
        "Exactly ≡ =1 owns.Animal",
        "Selfish ≡ ∃owns.Self",
    ],
)
def test_class_expressions_round_trip(world, statements, text):
    onto = addle.loads("⊤ ⊑ ∀owns.Animal\n" + text + "\n", world=world)
    assert text in statements(onto)


def test_union_filler_keeps_its_parentheses(world, statements):
    """Without parentheses `∀r.(A ⊔ B)` would re-parse as `(∀r.A) ⊔ B`."""
    onto = addle.loads("⊤ ⊑ ∀owns.(Animal ⊔ Plant)\n", world=world)
    assert "⊤ ⊑ ∀owns.(Animal ⊔ Plant)" in statements(onto)


def test_exists_top_is_written_in_its_dle_form(world, statements):
    onto = addle.loads("⊤ ⊑ ∀name.xsd:string\nNamed ≡ ∃name.⊤\n", world=world)
    assert "Named ≡ ∃name.⊤" in statements(onto)


def test_domain_and_range_use_the_dle_idioms(world, statements):
    onto = addle.loads("∃owns.⊤ ⊑ Person\n⊤ ⊑ ∀owns.Animal\n", world=world)
    lines = statements(onto)
    assert "∃owns.⊤ ⊑ Person" in lines
    assert "⊤ ⊑ ∀owns.Animal" in lines


def test_characteristics_are_written_as_keywords(world, statements):
    onto = addle.loads("Trans(above)\nSym(beside)\n", world=world)
    lines = statements(onto)
    assert "Trans(above)" in lines
    assert "Sym(beside)" in lines


def test_inverse_pair_is_written_once(world, statements):
    """Owlready2 records the inverse on both properties; `p ≡ q⁻` says it once."""
    onto = addle.loads("⊤ ⊑ ∀owns.Animal\nownedBy ≡ owns⁻\n", world=world)
    inverse_lines = [line for line in statements(onto) if "⁻" in line]
    assert len(inverse_lines) == 1


def test_disjoint_pair_is_written_once(world, statements):
    onto = addle.loads("⊤ ⊑ ∀a.Thing\n⊤ ⊑ ∀b.Thing\na ⊓ b ⊑ ⊥\n", world=world)
    bottom_lines = [line for line in statements(onto) if "⊥" in line]
    assert len(bottom_lines) == 1


def test_property_chain(world, statements):
    onto = addle.loads(
        "⊤ ⊑ ∀a.Thing\n⊤ ⊑ ∀b.Thing\n⊤ ⊑ ∀c.Thing\na ∘ b ⊑ c\n", world=world
    )
    assert "a ∘ b ⊑ c" in statements(onto)


def test_has_key(world, statements):
    onto = addle.loads("⊤ ⊑ ∀id.xsd:string\nConcept ⊑ key(id)\n", world=world)
    assert "Concept ⊑ key(id)" in statements(onto)


def test_compact_numeric_facets(world, statements):
    onto = addle.loads("⊤ ⊑ ∀n.xsd:integer[≥1 ⊓ <10]\n", world=world)
    assert "⊤ ⊑ ∀n.xsd:integer[≥1 ⊓ <10]" in statements(onto)


def test_keyword_facets(world, statements):
    onto = addle.loads('⊤ ⊑ ∀id.[xsd:string ⊓ [matches "[A-Z]{3}"]]\n', world=world)
    assert '⊤ ⊑ ∀id.[xsd:string ⊓ [matches "[A-Z]{3}"]]' in statements(onto)


def test_literal_enumeration(world, statements):
    onto = addle.loads('⊤ ⊑ ∀size.{"S","M"}\n', world=world)
    assert '⊤ ⊑ ∀size.{"S","M"}' in statements(onto)


def test_boolean_enumeration(world, statements):
    onto = addle.loads("⊤ ⊑ ∀flag.xsd:boolean\nOn ≡ ∃flag.{true}\n", world=world)
    assert "On ≡ ∃flag.{true}" in statements(onto)


def test_annotations_are_written_in_dle_form(world, statements):
    onto = addle.loads(
        "Animal ⊑ ⊤\n"
        '@db Animal "animal_id"\n'
        '@label Animal "Animal"\n'
        '@storage Animal "t.animal"\n'
        '@doc Animal "Docs."\n',
        world=world,
    )
    lines = statements(onto)
    assert '@db Animal "animal_id"' in lines
    assert '@label Animal "Animal"' in lines
    assert '@storage Animal "t.animal"' in lines
    assert '@doc Animal "Docs."' in lines


def test_db_without_a_string_is_written_back_without_one(world, statements):
    onto = addle.loads("Animal ⊑ ⊤\n@db Animal\n", world=world)
    assert "@db Animal" in statements(onto)


def test_ann_annotation(world, statements):
    onto = addle.loads('Animal ⊑ ⊤\n@ann Animal note "Careful."\n', world=world)
    assert '@ann Animal note "Careful."' in statements(onto)


def test_predicate_definition(world, statements):
    onto = addle.loads("greaterThan(x,y) ≝ x > y\n", world=world)
    assert "greaterThan(x,y) ≝ x > y" in statements(onto)


def test_comments_survive(world, render):
    onto = addle.loads("Animal ⊑ ⊤\n\n# a remark\nPlant ⊑ ⊤\n", world=world)
    assert "# a remark" in render(onto)


def test_rule_off_comments_are_not_flattened(world, render):
    """`########` must not collapse to an empty `#` line."""
    onto = addle.loads("Animal ⊑ ⊤\n\n#####\n# section\nPlant ⊑ ⊤\n", world=world)
    text = render(onto)
    assert "#####" in text
    assert "# section" in text


def test_synthetic_classes_are_not_emitted_as_entities(world, statements):
    onto = addle.loads(
        "afterNow(x) ≝ x > now()\n"
        "⊤ ⊑ ∀when.xsd:dateTime\n"
        "Future ≡ ∃when.afterNow\n",
        world=world,
    )
    lines = statements(onto)
    assert "Future ≡ ∃when.afterNow" in lines
    assert not any(DLE_NS in line or "E_afterNow" in line for line in lines)


def test_general_concept_equivalence_is_folded_back(world, statements):
    """The reader splits `≡` into two subsumptions; the writer must rejoin them."""
    onto = addle.loads(
        "⊤ ⊑ ∀a.xsd:integer\n⊤ ⊑ ∀b.xsd:integer\n∃a.{1} ≡ ∃b.{2}\n", world=world
    )
    lines = [line for line in statements(onto) if line.startswith("∃")]
    assert lines == ["∃a.{1} ≡ ∃b.{2}"]


def test_output_is_independent_of_construction_order(world):
    """Two ontologies with the same content must render identically."""
    onto_a = addle.loads("Animal ⊑ ⊤\nPlant ⊑ ⊤\n", world=world)
    text_a = addle.dumps(onto_a, include_header=False)

    from owlready2 import World

    other = World(filename=":memory:")
    onto_b = addle.loads("Plant ⊑ ⊤\nAnimal ⊑ ⊤\n", world=other)
    text_b = addle.dumps(onto_b, include_header=False)

    assert text_a == text_b


def test_writes_an_ontology_built_by_hand(world):
    """The writer must work on ontologies addle never parsed."""
    onto = world.get_ontology("http://example.org/hand#")
    with onto:
        animal = types.new_class("Animal", (Thing,))
        types.new_class("Dog", (animal,))
        owns = types.new_class("owns", (ObjectProperty,))
        owns.domain = [animal]
        owns.range = [animal]
        types.new_class("age", (DataProperty,)).range = [int]

    text = addle.dumps(onto, include_header=False)
    assert "Dog ⊑ Animal" in text
    assert "∃owns.⊤ ⊑ Animal" in text
    assert "⊤ ⊑ ∀age.xsd:integer" in text


def test_inline_comment_is_written_back(world, render):
    """A trailing `# …` has no statement of its own; it rides the first line."""
    onto = addle.loads("Animal ⊑ ⊤  # a trailing note\n", world=world)
    assert "Animal ⊑ ⊤  # a trailing note" in render(onto)
