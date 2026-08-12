# addle

[![test](https://github.com/quoll/addle/actions/workflows/test.yml/badge.svg)](https://github.com/quoll/addle/actions/workflows/test.yml)

A [DLe](https://github.com/quoll/DLe/wiki) parser and writer for
[Owlready2](https://owlready2.readthedocs.io/).

DLe — *Description Logic, Extended* — is a compact formal syntax for ontologies
that is readable by both people and language models. It is standard Description
Logic plus a small set of additions: predicate definitions (`≝`), multi-role
predicate restrictions (`∃r₁,…,rₙ.P`), annotations (`@label`, `@doc`, `@db`,
`@storage`, `@ann`), and `#` comments.

`addle` reads a DLe document into an Owlready2 ontology, and writes an Owlready2
ontology back out as DLe.

```python
import addle

onto = addle.load("model.dle")
print(onto.Animal.is_a)

print(addle.dumps(onto))
```

Because the result is an ordinary Owlready2 ontology, everything else Owlready2
does still applies — SPARQL queries, reasoning with HermiT or Pellet, and saving
to RDF/XML or N-Triples.

## Installation

```bash
pip install addle
```

## Command line

```bash
addle model.dle                  # print as DLe (canonically formatted)
addle model.dle model.owl        # convert to RDF/XML
addle model.owl                  # convert RDF/XML back to DLe
addle model.dle -f nt            # N-Triples to stdout
addle model.dle --no-header      # omit the explanatory file header
```

## API

| Function | Purpose |
|---|---|
| `addle.loads(text, ...)` | parse DLe text into an ontology |
| `addle.load(path_or_file, ...)` | parse a DLe document from a path or file object |
| `addle.dumps(onto, ...)` | render an ontology as DLe text |
| `addle.dump(onto, path_or_file, ...)` | write an ontology as DLe |

All four accept `warnings=[]`, which collects anything that could not be
represented faithfully rather than failing or discarding it silently:

```python
warnings = []
onto = addle.loads(text, warnings=warnings)
for warning in warnings:
    print(warning)
```

`loads` and `load` take `world=` to build in a specific Owlready2 `World`,
`onto=` to add to an existing ontology, and `base_iri=` to override the base
IRI. A malformed document raises `addle.DleSyntaxError`, which reports every
diagnostic the parse produced with line and column.

## How DLe maps onto Owlready2

| DLe | Owlready2 |
|---|---|
| `C ⊑ D`, `C ≡ D` | `C.is_a`, `C.equivalent_to` |
| `C ⊓ D`, `C ⊔ D`, `¬C` | `And`, `Or`, `Not` |
| `∃r.C`, `∀r.C` | `Restriction(r, SOME/ONLY, …)` |
| `≥n r.C`, `≤n r.C`, `=n r.C` | `Restriction(r, MIN/MAX/EXACTLY, n, C)` |
| `∃r.Self` | `Restriction(r, HAS_SELF, …)` |
| `r⁻` | `Inverse(r)` |
| `∃r.⊤ ⊑ C` | `r.domain` |
| `⊤ ⊑ ∀r.C` | `r.range` |
| `≤1 r.⊤` | `FunctionalProperty` |
| `Trans(r)`, `Sym(r)`, … | `TransitiveProperty`, `SymmetricProperty`, … |
| `q ∘ r ⊑ s` | `s.property_chain` |
| `r ⊓ s ⊑ ⊥`, `Disj(r,s)` | `AllDisjoint` |
| `{a,b}`, `{"x","y"}` | `OneOf` |
| `xsd:integer[≥0 ⊓ <10]` | `ConstrainedDatatype` |
| `@label`, `@doc`, `@storage`, `@db` | `rdfs:label`, `rdfs:comment`, `rdfs:seeAlso`, `rdfs:isDefinedBy` |
| `@ann X p "v"` | an annotation assertion with property `p` |

Three DLe constructs have no OWL vocabulary, and are encoded exactly as the Java
reference implementation encodes them so that documents can move between the two:

- **Predicate definitions** (`greaterThan(x,y) ≝ x > y`) become an `rdf:value`
  annotation on the predicate IRI, holding `"greaterThan(x,y) → x > y"`.
- **Predicate restrictions** (`∃a,b.greaterThan`) become a named class in the
  `dle:` namespace whose `rdfs:label` is the original expression. The IRI embeds
  a `java.lang.String.hashCode` of that expression, computed identically here, so
  both implementations mint the *same* IRI for the same expression.
- **Comments** become `dle:comment` annotations on the entity that follows them.

Because all three are ordinary annotations, they survive a trip through any OWL
serialiser. Writing the reference document to RDF/XML with Owlready2 and reading
it back reproduces the DLe byte for byte; that is a test, not an aspiration.

## Round-trip behaviour

Reading and writing preserves **content**, not layout. Specifically:

- Output is **canonically ordered** — properties before classes, each group
  sorted by name — so writing is deterministic and idempotent:
  `write(read(write(read(x)))) == write(read(x))`, byte for byte. Owlready2
  iterates entities in creation order, which for a parsed document is the order
  names are first *mentioned*, so preserving source order is not possible;
  sorting makes output reviewable in a diff instead.
- Some axioms are rewritten to an equivalent spelling. `≤1 r.⊤` comes back as
  `Func(r)`; a general concept equivalence is stored as two subsumptions and
  re-folded into `≡` on the way out. Both say the same thing.
- Comments are preserved and reattached to their entity, except the leading
  comment block of a file, which is treated as a header describing the format
  rather than the ontology. This matches the Java implementation.

## Known limitations

These are real gaps, not rough edges to be papered over:

- **OWL punning is not representable.** If an IRI is used as both a property and
  an individual — `∃statementRelationship.{studies}` where `studies` is also a
  property — Owlready2 maps one IRI to one entity and cannot hold both. addle
  reports this through `warnings` and reuses the existing entity.
- **`owl:hasKey` is written as raw RDF.** Owlready2 has no model for key axioms,
  so `C ⊑ key(a,b)` is written directly to the quadstore. It round-trips through
  addle and through RDF, but no Owlready2 accessor exposes it.
- **`⊤ ⊑ X` is written as raw RDF** on `owl:Thing`, for the same reason:
  Owlready2's `GeneralClassAxiom` requires a blank node on its left.
- **Datatype IRIs outside Owlready2's set are approximated.** `xsd:double` and
  `xsd:float` both map to Python `float`, which Owlready2 writes back as
  `xsd:decimal`. Anything unrecognised falls back to `xsd:string` with a warning.
- **The top data range has no Owlready2 spelling.** `∃p.⊤` on a data property is
  stored as the equivalent `≥1 p`, and written back as `∃p.⊤`.

## Relationship to the Java implementation

The reference implementation is
[`io.github.quoll.owlapi:dlextended-parsers`](https://github.com/quoll/DLe),
built on the OWL API. addle is a separate implementation, not a port: the OWL API
discovers parsers and storers through `ServiceLoader`, and Owlready2 has no
comparable extension point, so addle is a top-level library rather than a plugin.

What the two share is the **language**. Two files are copies of their
counterparts in the Java repository, and must never diverge:

| File | Why |
|---|---|
| `grammar/DLESyntax.g4` | defines the language both implementations accept |
| `tests/data/wildlife-reserve-test.dle` | the conformance corpus that proves they agree |

They are copies rather than a submodule deliberately: a submodule is paid for on
every clone, and this grammar changes about once a year. The cost of a copy is
that it can drift silently, so drift is checked instead:

```bash
tools/grammar.py check                       # verify the grammar's recorded hash
tools/grammar.py check --against ../dle      # diff both files against a DLe checkout
tools/grammar.py generate                    # regenerate the parser after a change
tools/grammar.py update                      # re-record the hash
```

The hash check runs as part of the test suite, so it fires on every local run and
in CI. The comparison against the reference implementation runs weekly on GitHub
Actions and opens an issue if the copies diverge — the drift that matters happens
upstream, while nobody is working on addle, so it needs a trigger that isn't
someone's attention.

The generated ANTLR parser is checked into `src/addle/_antlr`, so installing
addle needs neither Java nor the ANTLR tool. Regeneration is only required when
the grammar itself changes.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

## Licence

Apache 2.0, matching the DLe reference implementation. Owlready2 is LGPL-3.0 and
is used as a separately-installed library, which the LGPL permits.
