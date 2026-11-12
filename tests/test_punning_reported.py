"""A pun this implementation cannot represent is reported, never silent.

Owlready2 maps one IRI to one entity, so a name that is both a class and a
property cannot be held as both. That is a real limit and not a defect. What
*was* a defect is losing the class side without saying so: role classification
crosses a pun downward, so every name subsumed by one is then read as a
property too, and a single unreported line retyped a whole hierarchy.

The reference implementation writes a pun as the pair ``X ⊑ ⊤`` and
``X ⊑ owl:topObjectProperty``. The branch that drops the class half already
carried a comment naming that exact pair, and a guard — ``if target is not
Thing`` — that excluded it from the warning. So the one shape the comment
described was the one shape that passed in silence.
"""

import addle
from owlready2 import ObjectPropertyClass, ThingClass, World

PREFIX = "@prefix : <http://e.org/>\n"

PUNNED = (
    "Reference ⊑ ⊤\n"
    "Reference ⊑ owl:topObjectProperty\n"
    "Dependency ⊑ Reference\n"
    "Component ⊑ ∃Reference.Component\n"
)


def load(body):
    warnings = []
    onto = addle.loads(PREFIX + body, world=World(filename=":memory:"), warnings=warnings)
    return onto, [str(w) for w in warnings]


def test_a_dropped_pun_is_reported():
    _, warnings = load(PUNNED)
    assert any("Reference" in w and "both a class and a property" in w for w in warnings), warnings


def test_the_report_says_what_it_costs():
    """The consequence is the part a reader needs: names beneath it change kind."""
    _, warnings = load(PUNNED)
    pun = [w for w in warnings if "both a class and a property" in w]
    assert pun, warnings
    assert "read as properties" in pun[0], pun[0]


def test_the_outcome_the_warning_describes_is_the_one_that_happens():
    """Assert the cost itself, so the message cannot drift away from the behaviour."""
    onto, _ = load(PUNNED)
    assert isinstance(onto.Reference, ObjectPropertyClass), "the property side survives"
    assert isinstance(onto.Dependency, ObjectPropertyClass), "and the name beneath it follows"
    assert isinstance(onto.Component, ThingClass), "a name not beneath it is unaffected"


def test_an_ordinary_document_reports_no_pun():
    """The boundary. A warning on every document would be worth nothing."""
    _, warnings = load("A ⊑ B\nC ⊑ ∃r.A\nr ⊑ owl:topObjectProperty\n")
    assert not [w for w in warnings if "both a class and a property" in w], warnings


def test_a_non_vacuous_subsumption_keeps_its_own_message():
    """The other half of the branch, which always warned, still says its own thing."""
    _, warnings = load("r ⊑ owl:topObjectProperty\nA ⊑ ∃r.A\nr ⊑ A\n")
    assert any("cannot be represented and is dropped" in w for w in warnings), warnings
