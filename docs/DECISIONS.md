# Decisions

Judgement calls made while bringing addle up to the DLe reference implementation,
recorded so they can be revisited. Each says what was decided, and why that rather
than the alternative.

The standing constraint behind most of them: addle builds an **Owlready2**
ontology, while the reference implementation builds an **OWL API** one. Where the
two object models disagree, addle follows Owlready2 — a document that reads into
something Owlready2 itself would not have produced is worse than one that reports
what it could not keep.

---

## 1. Typed literals use Owlready2's own parser

**Question.** `"3"^^xsd:int` — what Python value should that be?

**Decided.** Resolve the datatype IRI through Owlready2's
`_universal_iri_2_abbrev`, then parse the lexical form with the parser from
`_universal_abbrev_2_datatype_parser`. Where there is no parser, keep the text and
warn, naming the datatype.

**Why.** addle's first attempt used a table of its own, built from
`_universal_datatype_2_abbrev`. That table has no entry for `xsd:int`, so a
perfectly ordinary literal was kept as a string and warned about. But Owlready2
*does* read `xsd:int` as `int` — confirmed by loading an OWL/XML file containing
one. The table was the incomplete part, not Owlready2. Using Owlready2's own
parser means a literal read from DLe lands on the same Python value as the same
literal read from OWL/XML, which is the only definition of "right" available here.

**Consequence worth knowing.** The datatype IRI is not preserved exactly:
`"3"^^xsd:int` is read as `int` and written back as `"3"^^xsd:integer`, because
Owlready2 maps `int` to `xsd:integer` on the way out. The value survives; the
subtype does not. That is Owlready2's model, not a choice addle makes.

**Near miss.** The parser table's values are `(python_type, parser)` pairs for
some datatypes and a bare callable for others. Taking element `[0]` works for
`xsd:int`, where the pair is `(int, int)`, and is silently wrong for
`xsd:boolean`, where it is `(bool, _bool_parser)`: `bool("false")` is `True`. The
parser is element `[1]`.

## 2. Language tags become `locstr`

**Question.** `"Fuchs"@de` — the tag is part of the STRING token now.

**Decided.** Owlready2's `locstr`, a `str` subclass carrying `.lang`. The writer
emits the tag back. A tag and a `^^` datatype cannot both apply: RDF types a
tagged literal as `rdf:langString`, so the tag wins and `^^` is ignored there.

**Why.** It is exactly the construct Owlready2 uses for this, so it serialises
correctly through every other Owlready2 backend without addle doing anything.

**Trap for tests.** `locstr.__eq__` compares the tag as well as the text, so
`locstr("Fuchs", "de") == "Fuchs"` is `False`. Compare with `str.__str__(value)`.

## 3. Annotation values carry their datatype on output

**Question.** The grammar admits only a string as an annotation value, so what
happens to an annotation whose value is an `int`?

**Decided.** Write `"3"^^xsd:integer` — quoted, with the datatype — rather than
`"3"`.

**Why.** `@label A "3"` reads back as the string `"3"`. Writing the datatype is
the only way the value survives its own round trip. `xsd:string` is left implicit,
being what an untagged, untyped string already means.

## 4. `Func(r⁻)` is `InverseFunctionalProperty`

**Question.** The role-characteristic keywords now take a `propertyExpr`, so
`Func(r⁻)` parses. OWL has a dedicated axiom for it.

**Decided.** Build `InverseFunctionalProperty(r)`.

**Why.** The two say the same thing and OWL has one axiom for it; the reference
implementation reads and writes both spellings as `Functional(r⁻)`. Doing the same
keeps the two implementations agreeing on the same document. An inverse is also
kind evidence in its own right — only an object property has one — so the scanner
now records `Func(r⁻)` as object-typed where plain `Func(r)` leaves the kind open.

## 5. A doubled inverse cancels at build time

**Question.** `propertyExpr` is recursive, so `r⁻⁻` parses.

**Decided.** Fold it: `r⁻⁻` builds `r`. Owlready2's `Inverse` does not fold, so
the folding is explicit in `_inverse`.

**Why.** An unfolded double inverse reaches the quadstore as a nested anonymous
construct that nothing reads back as the plain property — including addle.

## 6. An inverse may be a key, and is written back as one

**Question.** `C ⊑ key(r⁻)`. OWL allows any object property expression in a key.

**Decided.** Support it on both sides.

**Why.** There is no Owlready2 limitation to defer to here: Owlready2 has no key
model at all, and addle already writes keys as raw `owl:hasKey` triples by hand.
Two defects had to be fixed for it to work, both found by testing the construct
rather than by reading the code:

- the reader assigned the inverse construct a blank-node storid but never wrote
  its `owl:inverseOf` triple, so reading the key list back yielded `None`;
- the writer then called `.iri` on that `None` and **crashed**, taking the whole
  document with it. It now renders an inverse member as `r⁻`, and reports a key
  member it cannot resolve rather than raising.

## 7. Document declarations accept a quoted string

**Question.** `@prefix`, `@ontology`, `@version` and `@import` now accept a string
where they used to require an angle-bracketed IRI.

**Decided.** Both forms, treated identically. No escape processing is applied to
the string form.

**Why.** The grammar change exists because models reach for quotes as often as for
brackets. An IRI has no escapes to process, so processing them would only
introduce a way to corrupt one.
