"""Render an Owlready2 ontology as DLe text.

The output ordering mirrors ``DLESyntaxStorerBase`` in the Java implementation:
a header, ontology-level declarations, prefixes, predicate definitions, then one
block per entity — comments, annotations, logical axioms — separated by blank
lines. Entities in the ``dle:`` namespace are internal encoding artefacts and
are suppressed; their content resurfaces wherever they are referenced.
"""

import datetime
import re
from importlib import resources

import owlready2
from owlready2 import (
    AsymmetricProperty,
    ConstrainedDatatype,
    FunctionalProperty,
    Inverse,
    InverseFunctionalProperty,
    IrreflexiveProperty,
    Not,
    Or,
    OneOf,
    PropertyChain,
    ReflexiveProperty,
    Restriction,
    SymmetricProperty,
    Thing,
    TransitiveProperty,
)
from owlready2.base import EXACTLY, HAS_SELF, MAX, MIN, ONLY, SOME, VALUE
from owlready2.class_construct import LogicalClassConstruct

from .vocab import (
    RDF_NS,
    split_iri,
    COMMENT_IRI,
    COMPACT_FACETS,
    DB_IRI,
    DLE_NS,
    DOC_IRI,
    FACET_OUTPUT,
    IMPLICIT_PREFIXES,
    INLINE_COMMENT_IRI,
    LABEL_IRI,
    OWL_NS,
    PREDICATE_IRI,
    RDFS_NS,
    STORAGE_IRI,
    XSD_NS,
)

TOP = "⊤"
BOTTOM = "⊥"
SUBCLASS = "⊑"
EQUIV = "≡"
AND = "⊓"
OR_OP = "⊔"
NOT = "¬"
AT_LEAST = "≥"

#: Words the grammar keeps for itself, which therefore cannot be written bare.
#: `Self` is the ObjectHasSelf filler, `true` and `false` are the boolean
#: literals, and `key` opens a key expression. `HasKey` is reserved outright.
RESERVED_LOCAL_NAMES = frozenset({"Self", "true", "false", "key", "HasKey"})
SAME = "="
DIFFERENT = "≠"
EXISTS = "∃"
FORALL = "∀"
INVERSE = "⁻"
CHAIN = "∘"

#: Annotation IRIs with their own DLe keyword, in the order DLe documents use.
_KEYWORD_ANNOTATIONS = [
    (LABEL_IRI, "@label"),
    (STORAGE_IRI, "@storage"),
    (DOC_IRI, "@doc"),
]

#: Both spellings parse; these are the ones written. The reference
#: implementation settled on the long forms because they ask less of a reader —
#: and of a language model — than the textbook's abbreviations do.
_CHARACTERISTIC_KEYWORDS = [
    (TransitiveProperty, "Transitive"),
    (FunctionalProperty, "Functional"),
    (ReflexiveProperty, "Reflexive"),
    (IrreflexiveProperty, "Irreflexive"),
    (SymmetricProperty, "Symmetric"),
    (AsymmetricProperty, "Asymmetric"),
]

#: InverseFunctional is Functional applied to the property's inverse, and DLe
#: has no separate keyword for it: `Functional(r⁻)` says it, and is what the
#: reference implementation writes for both spellings.
_INVERSE_FUNCTIONAL_KEYWORD = "Functional"

#: Python type → the datatype IRI to write for it.
_IRI_BY_DATATYPE = {}


def _build_datatype_table():
    base = owlready2.base
    for datatype, abbrev in base._universal_datatype_2_abbrev.items():
        iri = base._universal_abbrev_2_iri.get(abbrev)
        if iri:
            _IRI_BY_DATATYPE.setdefault(datatype, iri)


_build_datatype_table()


def header_text():
    """The standard DLe file header, as shipped with the package."""
    return resources.files(__package__).joinpath("header.txt").read_text(encoding="utf-8")


class Writer:
    """Renders one Owlready2 ontology as DLe text."""

    def __init__(self, onto, prefixes=None, include_header=True):
        self.onto = onto
        self.world = onto.world
        self.include_header = include_header
        self._labels = {}   # dle: synthetic class IRI -> its expression text
        self._inverse_pairs = set()
        self._disjoint_pairs = set()
        self.warnings = []
        self._asserted_object_iris = None
        self._default_ns = None
        self._default_alias = None
        self._inverse_partner_map = None
        # Last: it reads the caches above.
        self.prefixes = self._build_prefixes(prefixes)

    # ── prefixes ─────────────────────────────────────────────────────────────

    def _build_prefixes(self, extra):
        """Prefix map used to shorten IRIs, longest namespace first on output."""
        prefixes = dict(IMPLICIT_PREFIXES)
        # The default prefix is the namespace the document's own entities live
        # in, which is usually the ontology's base IRI and occasionally is not.
        # Using base_iri regardless meant that an ontology IRI differing from the
        # entities' namespace shortened nothing, and every name was written as a
        # bare <http://…> IRI — which is not a name in the grammar, so the
        # document could not be read back at all.
        prefixes[""] = self._default_namespace()
        for namespace in self._unprefixed_namespaces(prefixes):
            prefixes[self._coin_prefix(namespace, prefixes)] = namespace
        if extra:
            prefixes.update(extra)
        return prefixes

    def _unprefixed_namespaces(self, prefixes):
        """Namespaces the document's own entities use that nothing can shorten.

        Owlready2 does not record the prefix names a document declared, so a
        ``@prefix mm:`` is gone by the time the writer runs. Without a prefix for
        it every name in that namespace is written as a bare ``<http://…>`` IRI
        — which is not a ``name`` in the grammar, so the output cannot be read
        back at all. A coined prefix is cosmetic; an unreadable document is not.
        """
        known = set(prefixes.values())
        found = []
        for entity in self._entities():
            iri = getattr(entity, "iri", None)
            if not iri:
                continue
            namespace = split_iri(iri)[0]
            if namespace and namespace not in known and namespace not in found:
                found.append(namespace)
        return found

    @staticmethod
    def _coin_prefix(namespace, taken):
        """A short, readable prefix for a namespace that arrived without one.

        The last meaningful path segment, else the first label of the host:
        ``http://mm.org/`` becomes ``mm``, ``http://ex.org/model/`` becomes
        ``model``. Names are only a convenience, so a collision simply counts up
        rather than trying to be clever about it.
        """
        body = re.sub(r"^[a-z][a-z0-9+.-]*://", "", namespace.rstrip("#/"))
        parts = [part for part in re.split(r"[/#]", body) if part]
        candidate = ""
        # Past the host, newest first: the last path segment names the vocabulary
        # where one exists — http://ex.org/model/ is `model`.
        for part in reversed(parts[1:]):
            cleaned = re.sub(r"[^A-Za-z0-9_-]", "", part)
            if cleaned and not cleaned[0].isdigit():
                candidate = cleaned
                break
        if not candidate and parts:
            # Nothing but a host, so its first label: http://mm.org/ is `mm`.
            candidate = re.sub(r"[^A-Za-z0-9_-]", "", parts[0].split(".")[0])
        if not candidate or candidate[0].isdigit():
            candidate = "ns"
        name, n = candidate, 1
        while name in taken:
            n += 1
            name = "%s%d" % (candidate, n)
        return name

    def _default_namespace(self):
        """The namespace the document's own entities are in.

        The ontology's base IRI is the usual answer and the one to prefer when
        it fits anything. When it does not — an ontology IRI naming the document
        rather than its vocabulary — the namespace shared by most entities is
        what a reader needs declared, since that is what makes their names bare.
        """
        if self._default_ns is None:
            base = self.onto.base_iri
            counts = {}
            for entity in self._entities():
                iri = getattr(entity, "iri", None)
                if not iri:
                    continue
                namespace = split_iri(iri)[0]
                counts[namespace] = counts.get(namespace, 0) + 1
            if counts.get(base) or not counts:
                self._default_ns = base
            else:
                self._default_ns = max(sorted(counts), key=counts.get)
        return self._default_ns

    def _declared_prefixes(self):
        """Prefixes that need an explicit ``@prefix`` line."""
        out = []
        for prefix, namespace in sorted(self.prefixes.items()):
            if IMPLICIT_PREFIXES.get(prefix) == namespace:
                continue
            out.append((prefix, namespace))
        return out

    def shorten(self, iri):
        """The shortest DLe name for an IRI: bare name, CURIE, or ``<iri>``."""
        best = None
        for prefix, namespace in self.prefixes.items():
            if iri.startswith(namespace) and (best is None or len(namespace) > len(best[1])):
                best = (prefix, namespace)
        if best is None:
            return "<%s>" % iri
        prefix, namespace = best
        local = iri[len(namespace) :]
        if not local:
            return "<%s>" % iri
        if prefix != "":
            return "%s:%s" % (prefix, local)
        if local[0].isdigit():
            # `:123` is the DEFAULT_NAME token, which exists for exactly this:
            # NAME cannot begin with a digit, so the bare spelling does not lex.
            # SNOMED identifiers are all of this shape.
            return ":%s" % local
        if local in RESERVED_LOCAL_NAMES:
            # Bare, these are the grammar's own words. `Self` written bare as the
            # filler of a restriction comes back as ObjectHasSelf with the class
            # gone — the document reloads and means something else. Prefixed they
            # are ordinary names, so the fix is to write a prefix.
            return "%s:%s" % (self._alias_for_default_namespace(), local)
        return local

    def _alias_for_default_namespace(self):
        """A named prefix for the default namespace, minted when first needed.

        Only a name the grammar reserves needs it, and such a name is rare, so
        the prefix is not declared unless one turns up.
        """
        if self._default_alias is None:
            namespace = self.prefixes[""]
            alias = self._coin_prefix(namespace, self.prefixes)
            self.prefixes[alias] = namespace
            self._default_alias = alias
        return self._default_alias

    # ── document ─────────────────────────────────────────────────────────────

    def render(self):
        lines = []
        if self.include_header:
            lines.append(header_text().rstrip("\n"))
            lines.append("")

        # The body is rendered first and the declarations are prepended, because
        # rendering can mint a prefix: a name the grammar reserves has to be
        # written prefixed, and the prefix it is given must be declared. Writing
        # the declarations first emitted `ex:Self` with no `@prefix ex:` line,
        # and the document would not read.
        body = list(self._predicate_definitions())
        blocks = [(entity, self._entity_block(entity)) for entity in self._entities()]
        for _entity, block in self._without_redundant_existence(blocks):
            if block:
                body.extend(block)
                body.append("")
        body.extend(self._disjoint_property_lines())
        body.extend(self._different_individual_lines())
        body.extend(self._universal_axioms())
        body.extend(self._orphan_axioms())

        lines.extend(self._ontology_declarations())
        lines.extend(body)

        text = "\n".join(lines)
        return text.rstrip("\n") + "\n"

    def _without_redundant_existence(self, blocks):
        """Drop a block that says only ``C ⊑ ⊤`` when something else names C.

        ``C ⊑ ⊤`` exists so that a class mentioned nowhere else still appears in
        the document. Written beside ``A ⊑ C`` it says nothing the reader does
        not already learn, and the reference implementation omits it — so two
        implementations rendering the same ontology produced documents that
        could not be diffed against each other.

        The test is textual, over the other blocks as rendered, because that is
        exactly the question being asked: does this name appear anywhere else in
        the document.
        """
        existence = {}
        for index, (entity, block) in enumerate(blocks):
            if isinstance(entity, owlready2.ThingClass) and len(block) == 1:
                name = self.shorten(entity.iri)
                if block[0] == "%s %s %s" % (name, SUBCLASS, TOP):
                    existence[index] = name
        if not existence:
            return blocks

        elsewhere = set()
        for index, (_entity, block) in enumerate(blocks):
            for other_index, name in existence.items():
                if other_index == index or name in elsewhere:
                    continue
                if any(_names_in(line, name) for line in block):
                    elsewhere.add(name)
        return [(entity, [] if existence.get(index) in elsewhere else block)
                for index, (entity, block) in enumerate(blocks)]

    def _ontology_declarations(self):
        lines = []
        iri = self.onto.base_iri.rstrip("#/")
        # Only when it says something the default prefix does not. Writing it
        # unconditionally was also lossy: stripping the trailing separator turns
        # `http://ex.org/` into `http://ex.org`, which Owlready2 reads back as
        # `http://ex.org#` — a different namespace, so the second pass could no
        # longer shorten any name.
        version = list(self._object_values(self.onto.base_iri.rstrip("#/"),
                                           OWL_NS + "versionIRI"))
        # A version identifies a version *of a named ontology*, so a document
        # declaring one must name itself — the reference refuses a @version with
        # no @ontology, and addle was producing exactly that.
        if version or iri != self._default_namespace().rstrip("#/"):
            lines.append("@ontology <%s>" % iri)
        for value in version:
            lines.append("@version <%s>" % value)

        for imported in self.onto.imported_ontologies:
            lines.append("@import <%s>" % imported.base_iri.rstrip("#/"))

        for prefix, namespace in self._declared_prefixes():
            lines.append("@prefix %s: <%s>" % (prefix, namespace))

        if lines:
            lines.append("")
        return lines

    def _predicate_definitions(self):
        """``name(args) ≝ body`` lines, recovered from ``rdf:value`` annotations.

        Predicates are not OWL entities, so they get no entity block; their
        comments have to be emitted here or they would be lost.
        """
        predicate_storid = self.world._abbreviate(PREDICATE_IRI)
        blocks = []
        for subject, value in self._data_triples_by_property(predicate_storid):
            if "→" not in value:
                continue
            signature, _, body = value.partition("→")
            definition = "%s ≝ %s" % (signature.strip(), body.strip())
            comments = ["#%s" % text for text in self._data_values(subject, COMMENT_IRI)]
            blocks.append((definition, comments))

        blocks.sort(key=lambda block: block[0])
        lines = []
        for definition, comments in blocks:
            lines.extend(comments)
            lines.append(definition)
        if lines:
            lines.append("")
        return lines

    def _entities(self):
        """Every entity worth a block, in a canonical order.

        Properties come before classes, because DLe documents conventionally
        introduce roles and attributes before the concepts built from them, and
        each group is sorted by name.

        The order is deliberately independent of how the ontology was built.
        Owlready2 iterates in entity-creation order, which for a parsed document
        is the order names are first *mentioned* — not the order they are
        defined. Sorting instead makes output reproducible: writing the same
        ontology twice, or re-reading and rewriting a document, gives identical
        text. The cost is that a document's original section layout is not
        preserved, only its content.
        """
        groups = [
            self.onto.annotation_properties(),
            self.onto.object_properties(),
            self.onto.data_properties(),
            self.onto.classes(),
            self.onto.individuals(),
        ]
        out = []
        for group in groups:
            entities = [e for e in group if not self._is_internal(e)]
            entities.sort(key=lambda e: (e.name, e.iri))
            out.extend(entities)
        return out

    def _is_internal(self, entity):
        """Whether an entity is a ``dle:`` encoding artefact rather than content."""
        return entity.iri.startswith(DLE_NS)

    def _is_external(self, entity):
        """Whether an entity belongs to a standard vocabulary this document uses."""
        return any(
            entity.iri.startswith(namespace)
            for prefix, namespace in IMPLICIT_PREFIXES.items()
            if prefix
        )

    # ── entity blocks ────────────────────────────────────────────────────────

    def _entity_block(self, entity):
        axioms = self._axiom_lines(entity)
        annotations = self._annotation_lines(entity)
        if not (axioms or annotations):
            return []

        body = axioms + annotations
        # A trailing `# …` had no statement of its own in the source. It is put
        # back on the entity's first line, which is deterministic given the
        # canonical ordering, so re-reading and rewriting reproduces it.
        for text in self._data_values(entity.iri, INLINE_COMMENT_IRI):
            body[0] = "%s  #%s" % (body[0], text)

        return self._comment_lines(entity) + body

    def _comment_lines(self, entity):
        return ["#%s" % text for text in self._data_values(entity.iri, COMMENT_IRI)]

    def _annotation_lines(self, entity):
        name = self.shorten(entity.iri)
        lines = []

        for value in self._data_values(entity.iri, DB_IRI):
            # `@db X` and `@db X "id"` differ only in whether the stored
            # identifier is the entity's own name.
            if value == name:
                lines.append("@db %s" % name)
            else:
                lines.append("@db %s %s" % (name, self._annotation_literal(value)))

        for iri, keyword in _KEYWORD_ANNOTATIONS:
            for value in self._data_values(entity.iri, iri):
                lines.append("%s %s %s"
                             % (keyword, name, self._annotation_literal(value)))

        lines.extend(self._other_annotation_lines(entity, name))
        return lines

    def _annotation_literal(self, value):
        """An annotation value as DLe writes it: a quoted string, tagged or typed.

        The grammar admits only a string here, so a value that is not one has to
        carry its datatype explicitly or it comes back as text: ``@label A "3"``
        reads as the string "3", losing the integer it was written from. A
        language tag is written for the same reason — Owlready2's ``locstr``
        carries one, and dropping it changes the literal.

        xsd:string is left implicit, being what an untagged, untyped string
        already means.
        """
        lang = getattr(value, "lang", None)
        if lang:
            return '"%s"@%s' % (_escape(value), lang)
        iri = _datatype_iri(value)
        if iri is None or iri == XSD_NS + "string":
            return '"%s"' % _escape(value)
        return '"%s"^^%s' % (_escape(_lexical(value)), self.shorten(iri))

    def _other_annotation_lines(self, entity, name):
        """``@ann`` lines for annotation properties without a DLe keyword."""
        known = {LABEL_IRI, DOC_IRI, STORAGE_IRI, DB_IRI, COMMENT_IRI,
                 INLINE_COMMENT_IRI, PREDICATE_IRI}
        lines = []
        # Sorted: Owlready2 yields these in creation order, which for a parsed
        # document is the order names were first mentioned. That differs between
        # a document and its own output, so the @ann lines moved about within a
        # block on every pass and the text never settled.
        for prop in sorted(self.onto.annotation_properties(), key=lambda p: p.iri):
            if prop.iri in known:
                continue
            for value in self._data_values(entity.iri, prop.iri):
                lines.append("@ann %s %s %s"
                             % (name, self.shorten(prop.iri),
                                self._annotation_literal(value)))
            for value in self._object_values(entity.iri, prop.iri):
                lines.append("@ann %s %s %s"
                             % (name, self.shorten(prop.iri), self.shorten(value)))
        return lines

    def _axiom_lines(self, entity):
        if isinstance(entity, owlready2.ThingClass):
            return self._class_axioms(entity)
        if isinstance(entity, owlready2.PropertyClass):
            return self._property_axioms(entity)
        if isinstance(entity, owlready2.Thing):
            return self._individual_axioms(entity)
        return []

    def _individual_axioms(self, individual):
        """``a : C`` and the property assertions ``a`` is the subject of.

        ``owl:Thing`` is skipped: Owlready2 gives every new individual Thing in
        its ``is_a``, so writing it would put ``a : ⊤`` in every document that
        names an individual at all, saying nothing.
        """
        name = self.shorten(individual.iri)
        lines = []
        for cls in individual.is_a:
            if cls is Thing:
                continue
            lines.append("%s : %s" % (name, self.concept(cls)))
        lines.extend(self._same_individual_lines(individual, name))
        lines.extend(self._assertion_lines(individual, name))
        lines.extend(self._negative_assertion_lines(individual, name))
        if not lines and not self._is_external(individual) \
                and individual.iri not in self._asserted_objects():
            # Nothing else in the document names this individual, so without a
            # line of its own it would vanish. An individual that is the subject
            # or the object of an assertion is already named by that assertion,
            # and `b : ⊤` beside `(a,b) : r` tells the reader nothing new — which
            # is the rule the reference implementation follows.
            lines.append("%s : %s" % (name, TOP))
        return lines

    def _asserted_objects(self):
        """Every individual that is the object of some object-property assertion.

        Computed once: each individual's block would otherwise re-scan every
        assertion in the document, which is quadratic in the number of them.
        """
        if self._asserted_object_iris is None:
            found = set()
            # Negative assertions name their target too: `¬(a,b) : r` is as much
            # a mention of b as `(a,b) : r` is.
            w = self.world
            for bnode, _, _ in w._get_obj_triples_spo_spo(
                    None, w._abbreviate(RDF_NS + "type"),
                    w._abbreviate(OWL_NS + "NegativePropertyAssertion")):
                for predicate in (OWL_NS + "sourceIndividual", OWL_NS + "targetIndividual"):
                    entity = self._one_object(bnode, w._abbreviate(predicate))
                    if entity is not None and getattr(entity, "iri", None):
                        found.add(entity.iri)
            # `a = b` and `x ≠ y` name their members too.
            for group in self.onto.different_individuals():
                for member in group.entities:
                    if getattr(member, "iri", None):
                        found.add(member.iri)
            for subject in self.onto.individuals():
                for other in subject.equivalent_to:
                    if getattr(other, "iri", None):
                        found.add(other.iri)
                        found.add(subject.iri)
            for prop in self.onto.object_properties():
                for subject in self.onto.individuals():
                    for value in self._values_of(subject, prop):
                        iri = getattr(value, "iri", None)
                        if iri is not None:
                            found.add(iri)
            self._asserted_object_iris = found
        return self._asserted_object_iris

    def _same_individual_lines(self, individual, name):
        """``a = b = c`` for the individuals this one is declared the same as."""
        others = [other for other in individual.equivalent_to
                  if getattr(other, "iri", None)]
        if not others:
            return []
        return ["%s %s %s" % (name, SAME,
                              (" %s " % SAME).join(self.shorten(o.iri)
                                                   for o in others))]

    def _assertion_lines(self, individual, name):
        """``(a,b) : r`` and ``(a,"x") : d`` for every assertion ``a`` makes."""
        lines = []
        for prop in sorted(self.onto.object_properties(), key=lambda p: p.iri):
            for value in self._values_of(individual, prop):
                if getattr(value, "iri", None) is None:
                    continue
                lines.append("(%s,%s) : %s"
                             % (name, self.shorten(value.iri), self.shorten(prop.iri)))
        for prop in sorted(self.onto.data_properties(), key=lambda p: p.iri):
            for value in self._values_of(individual, prop):
                lines.append("(%s,%s) : %s"
                             % (name, self._annotation_literal(value),
                                self.shorten(prop.iri)))
        return lines

    def _negative_assertion_lines(self, individual, name):
        """``¬(a,b) : r`` — OWL's reified negative assertions, read back as RDF.

        Owlready2 has no model for them, so they were written as triples and are
        read back the same way, exactly as keys are.
        """
        w = self.world
        type_of = w._abbreviate(RDF_NS + "type")
        npa = w._abbreviate(OWL_NS + "NegativePropertyAssertion")
        source = w._abbreviate(OWL_NS + "sourceIndividual")
        on_prop = w._abbreviate(OWL_NS + "assertionProperty")
        target_ind = w._abbreviate(OWL_NS + "targetIndividual")
        target_val = w._abbreviate(OWL_NS + "targetValue")

        lines = []
        for bnode, _, _ in w._get_obj_triples_spo_spo(None, type_of, npa):
            subject = self._one_object(bnode, source)
            if subject is None or subject.iri != individual.iri:
                continue
            prop = self._one_object(bnode, on_prop)
            if prop is None:
                continue
            value = self._one_object(bnode, target_ind)
            if value is not None:
                rendered = self.shorten(value.iri)
            else:
                literal = w._get_data_triple_sp_od(bnode, target_val)
                if literal is None:
                    continue
                rendered = self._annotation_literal(w._to_python(*literal[:2]))
            lines.append("%s(%s,%s) : %s"
                         % (NOT, name, rendered, self.shorten(prop.iri)))
        return sorted(lines)

    def _one_object(self, subject_storid, predicate_storid):
        """The single entity a blank node points at, or None."""
        for _, _, obj in self.world._get_obj_triples_spo_spo(
                subject_storid, predicate_storid, None):
            return self.world._get_by_storid(obj)
        return None

    def _values_of(self, individual, prop):
        """What ``individual`` asserts for ``prop``, or nothing."""
        try:
            values = getattr(individual, prop.python_name)
        except AttributeError:
            return []
        if values is None:
            return []
        return list(values) if isinstance(values, list) else [values]

    def _class_axioms(self, cls):
        name = self.shorten(cls.iri)
        lines = []
        # One line per equivalent, not one chained line over all of them.
        # Owlready2 keeps a flat `equivalent_to` list, so `A ≡ B ≡ C` and the
        # pair of axioms `A ≡ B`, `A ≡ C` are indistinguishable once read — and
        # the two spellings have to be told apart on the way out. The separate
        # form is what real documents overwhelmingly contain: the reference
        # corpus has four classes stating two equivalences each and none using
        # the chain. Chaining them merged two axioms into one.
        #
        # The chained form still reads correctly; it comes back as separate
        # lines, which says the same thing in one more axiom.
        for other in cls.equivalent_to:
            lines.append("%s %s %s" % (name, EQUIV, self.concept(other)))
        parents = [p for p in cls.is_a if p is not Thing]
        for parent in parents:
            lines.append("%s %s %s" % (name, SUBCLASS, self.concept(parent)))
        if not lines and not self._is_external(cls):
            # `C ⊑ ⊤` states that C exists. Classes borrowed from rdf/rdfs/owl
            # need no such declaration — they are not this document's to define.
            lines.append("%s %s %s" % (name, SUBCLASS, TOP))
        lines.extend(self._key_lines(cls, name))
        for disjoint in cls.disjoints():
            lines.extend(self._disjoint_lines(disjoint, cls))
        return lines

    def _property_axioms(self, prop):
        name = self.shorten(prop.iri)
        lines = []

        for parent in prop.is_a:
            if parent.namespace is owlready2.owl:
                continue  # characteristics are written in their keyword form
            lines.append("%s %s %s" % (name, SUBCLASS, self.concept(parent)))

        data_property = isinstance(prop, owlready2.DataPropertyClass)
        for value in getattr(prop, "domain", []) or []:
            if data_property:
                # `∃d.⊤` would put a data property where a class expression is
                # expected: ⊤ is the top concept, and the top data range is
                # rdfs:Literal, a different thing. DL spells a data property's
                # domain with a cardinality bound instead.
                lines.append("(%s1 %s) %s %s"
                             % (AT_LEAST, name, SUBCLASS, self.concept(value)))
            else:
                lines.append("%s%s.%s %s %s"
                             % (EXISTS, name, TOP, SUBCLASS, self.concept(value)))
        for value in getattr(prop, "range", []) or []:
            lines.append("%s %s %s%s.%s" % (TOP, SUBCLASS, FORALL, name, self._filler(value)))

        partner = self._inverse_partners().get(prop.iri)
        if partner is not None and prop.iri < partner.iri:
            lines.append("%s %s %s%s" % (name, EQUIV, self.shorten(partner.iri), INVERSE))

        for chain in getattr(prop, "property_chain", []) or []:
            rendered = (" %s " % CHAIN).join(self.concept(p) for p in chain.properties)
            lines.append("%s %s %s" % (rendered, SUBCLASS, name))

        for characteristic, keyword in _CHARACTERISTIC_KEYWORDS:
            if characteristic in prop.is_a:
                lines.append("%s(%s)" % (keyword, name))
        if InverseFunctionalProperty in prop.is_a:
            lines.append("%s(%s%s)" % (_INVERSE_FUNCTIONAL_KEYWORD, name, INVERSE))

        for equivalent in getattr(prop, "equivalent_to", []) or []:
            lines.append("%s %s %s" % (name, EQUIV, self.concept(equivalent)))

        return lines

    def _inverse_partners(self):
        """Every property that has an inverse, mapped to it, from both sides.

        ``p ≡ q⁻`` and ``q ≡ p⁻`` say the same thing, so the pair is written
        once, from the member with the smaller IRI. That needs both members to
        know about it: Owlready2 records ``inverse_property`` on whichever side
        the document stated, so asking only that side meant the pair was written
        from whichever property happened to be reached first — and entities come
        in creation order, which differs between a document and its own output.
        The line moved between blocks on every pass and the text never settled.
        """
        if self._inverse_partner_map is None:
            partners = {}
            for prop in self.onto.properties():
                other = getattr(prop, "inverse_property", None)
                if other is not None and getattr(other, "iri", None):
                    partners[prop.iri] = other
                    partners.setdefault(other.iri, prop)
            self._inverse_partner_map = partners
        return self._inverse_partner_map

    def _key_lines(self, cls, name):
        """``C ⊑ key(a,b)`` lines, read back from raw ``owl:hasKey`` triples."""
        has_key = self.world._abbreviate(OWL_NS + "hasKey")
        lines = []
        for _, _, bnode in self.world._get_obj_triples_spo_spo(cls.storid, has_key, None):
            keys = self.onto._parse_list(bnode)
            rendered = [self._key_member(k) for k in keys]
            if any(part is None for part in rendered):
                self.warnings.append(
                    "a key on %s names something that is not a property; it is omitted"
                    % name)
                continue
            lines.append("%s %s key(%s)" % (name, SUBCLASS, ",".join(rendered)))
        return lines

    def _key_member(self, member):
        """One member of a key: a property, or an inverse of one.

        OWL allows any object property expression in a key, so ``key(r⁻)`` is
        legal and has to come back out as it went in. Anything else — a member
        that did not resolve — returns None so the caller can say so rather than
        raise, a malformed key being the document's problem and not a reason to
        abandon the whole file.
        """
        if member is None:
            return None
        iri = getattr(member, "iri", None)
        if iri is not None:
            return self.shorten(iri)
        prop = getattr(member, "property", None)
        if prop is not None and getattr(prop, "iri", None) is not None:
            return self.shorten(prop.iri) + INVERSE
        return None

    def _disjoint_lines(self, disjoint, entity):
        """``A ⊓ B ⊑ ⊥`` lines for one member of a disjoint set.

        Owlready2 reports the set from every member, so each pair would
        otherwise be written twice — once from each side.
        """
        lines = []
        for other in disjoint.entities:
            if other is entity:
                continue
            pair = frozenset((entity.iri, other.iri))
            if pair in self._disjoint_pairs:
                continue
            self._disjoint_pairs.add(pair)
            lines.append(
                "%s %s %s %s %s"
                % (self.shorten(entity.iri), AND, self.shorten(other.iri), SUBCLASS, BOTTOM)
            )
        return lines

    def _disjoint_property_lines(self):
        """``Disj(r, s, t)`` — one line per disjoint set of properties.

        Written from the ontology rather than from each property, for two
        reasons. Owlready2 reaches a two-member set from either member but a
        larger one from neither — ``r.disjoints()`` is empty for
        ``Disj(r, s, t)`` — so a three-way disjointness was written nowhere at
        all and simply disappeared. And the set is one axiom about n properties,
        which `Disj` says directly where a fan of pairwise ``r ⊓ s ⊑ ⊥`` lines
        only implies it.
        """
        lines = []
        for group in self.onto.disjoints():
            members = [m for m in group.entities
                       if isinstance(m, owlready2.PropertyClass)]
            if len(members) < 2:
                continue
            lines.append("Disj(%s)" % ", ".join(
                sorted(self.shorten(m.iri) for m in members)))
        return sorted(lines)

    def _different_individual_lines(self):
        """``x ≠ y ≠ z`` — one line per AllDifferent set.

        Not attached to any one individual's block: the axiom is about the set,
        and putting it under its first member would imply an order the axiom
        does not have.
        """
        lines = []
        for group in self.onto.different_individuals():
            members = [m for m in group.entities if getattr(m, "iri", None)]
            if len(members) < 2:
                continue
            lines.append((" %s " % DIFFERENT).join(
                self.shorten(m.iri) for m in members))
        return sorted(lines)

    def _universal_axioms(self):
        """``⊤ ⊑ X`` axioms, stored as ``owl:Thing rdfs:subClassOf _:x``."""
        subclass = self.world._abbreviate(RDFS_NS + "subClassOf")
        lines = []
        for _, _, obj in self.world._get_obj_triples_spo_spo(Thing.storid, subclass, None):
            if obj >= 0:
                continue  # a named superclass of owl:Thing is not ours to write
            construct = self.onto._parse_bnode(obj)
            lines.append("%s %s %s" % (TOP, SUBCLASS, self.concept(construct)))
        lines.sort()
        return lines

    def _orphan_axioms(self):
        """General concept inclusions, which belong to no single entity.

        A mutual pair is folded back into a single ``≡`` line: DLe writes general
        concept equivalences directly, and the reader has to split them into two
        subsumptions because that is all Owlready2 models.
        """
        pairs = []
        for axiom in self.onto.general_class_axioms():
            left = self.concept(axiom.left_side)
            for right in axiom.is_a:
                pairs.append((left, self.concept(right)))

        seen = set(pairs)
        lines = []
        emitted = set()
        for left, right in pairs:
            if (left, right) in emitted:
                continue
            if (right, left) in seen and left != right:
                emitted.add((left, right))
                emitted.add((right, left))
                # Order the two sides so the same pair always reads the same way,
                # whichever direction happened to be visited first.
                first, second = sorted((left, right))
                lines.append("%s %s %s" % (first, EQUIV, second))
            else:
                emitted.add((left, right))
                lines.append("%s %s %s" % (left, SUBCLASS, right))
        lines.sort()
        return lines

    # ── concept rendering ────────────────────────────────────────────────────

    def concept(self, concept):
        """Render a class expression, property expression or datatype as DLe."""
        if concept is None:
            return BOTTOM
        if concept is Thing:
            return TOP
        if concept is owlready2.Nothing:
            return BOTTOM

        if isinstance(concept, owlready2.ThingClass):
            synthetic = self._synthetic_label(concept)
            return synthetic if synthetic is not None else self.shorten(concept.iri)

        if isinstance(concept, owlready2.PropertyClass):
            return self.shorten(concept.iri)

        if isinstance(concept, owlready2.Thing):
            return self.shorten(concept.iri)

        if isinstance(concept, LogicalClassConstruct):
            operator = OR_OP if isinstance(concept, Or) else AND
            parts = []
            for part in concept.Classes:
                rendered = self.concept(part)
                if isinstance(part, (LogicalClassConstruct,)):
                    rendered = "(%s)" % rendered
                parts.append(rendered)
            return (" %s " % operator).join(parts)

        if isinstance(concept, Not):
            inner = concept.Class
            rendered = self.concept(inner)
            if isinstance(inner, LogicalClassConstruct):
                rendered = "(%s)" % rendered
            return "%s%s" % (NOT, rendered)

        if isinstance(concept, Inverse):
            return "%s%s" % (self.concept(concept.property), INVERSE)

        if isinstance(concept, Restriction):
            return self._restriction(concept)

        if isinstance(concept, OneOf):
            return "{%s}" % ",".join(self._one_of_element(x) for x in concept.instances)

        if isinstance(concept, ConstrainedDatatype):
            return self._constrained_datatype(concept)

        if isinstance(concept, PropertyChain):
            return (" %s " % CHAIN).join(self.concept(p) for p in concept.properties)

        datatype_iri = _IRI_BY_DATATYPE.get(concept)
        if datatype_iri is not None:
            return self.shorten(datatype_iri)

        self.warnings.append("cannot render %r; emitted as ⊤" % (concept,))
        return TOP

    def _synthetic_label(self, cls):
        """The original expression behind a ``dle:`` synthetic class, if any."""
        if not cls.iri.startswith(DLE_NS):
            return None
        if cls.iri in self._labels:
            return self._labels[cls.iri]
        values = self._data_values(cls.iri, LABEL_IRI)
        label = values[0] if values else None
        self._labels[cls.iri] = label
        return label

    def _restriction(self, restriction):
        prop = self.concept(restriction.property)
        kind = restriction.type

        if kind == SOME:
            return "%s%s.%s" % (EXISTS, prop, self._filler(restriction.value))
        if kind == ONLY:
            return "%s%s.%s" % (FORALL, prop, self._filler(restriction.value))
        if kind == VALUE:
            return "%s%s.{%s}" % (EXISTS, prop, self._one_of_element(restriction.value))
        if kind == HAS_SELF:
            return "%s%s.Self" % (EXISTS, prop)

        symbol = {MIN: "≥", MAX: "≤", EXACTLY: "="}.get(kind)
        if symbol is None:
            self.warnings.append("unknown restriction type %r" % (kind,))
            return TOP

        # An unqualified min-1 bound is exactly ∃p.⊤, and that is how DLe spells
        # it. Owlready2 reports the filler as None when the restriction was just
        # built and as owl:Thing once it has been read back from triples.
        if kind == MIN and restriction.cardinality == 1 and (
            restriction.value is None or restriction.value is Thing
        ):
            return "%s%s.%s" % (EXISTS, prop, TOP)
        if restriction.value is None:
            return "%s%d %s" % (symbol, restriction.cardinality, prop)
        return "%s%d %s.%s" % (
            symbol,
            restriction.cardinality,
            prop,
            self._filler(restriction.value),
        )

    def _filler(self, value):
        """A restriction filler, parenthesised when precedence requires it.

        A quantifier binds tighter than ``⊓``/``⊔``, so ``∀r.(A ⊔ B)`` must keep
        its parentheses or it would re-parse as ``(∀r.A) ⊔ B``.
        """
        rendered = self.concept(value)
        if isinstance(value, LogicalClassConstruct):
            return "(%s)" % rendered
        return rendered

    def _one_of_element(self, value):
        if isinstance(value, (owlready2.Thing, owlready2.ThingClass,
                              owlready2.PropertyClass)):
            return self.shorten(value.iri)
        return _literal(value)

    def _constrained_datatype(self, datatype):
        """``xsd:integer[≥0 ⊓ <10]`` when possible, else the bracketed form."""
        base = self.shorten(_IRI_BY_DATATYPE.get(datatype.base_datatype, XSD_NS + "string"))

        facets = [
            (kwarg, getattr(datatype, kwarg))
            for kwarg in FACET_OUTPUT
            if getattr(datatype, kwarg, None) is not None
        ]
        if not facets:
            return base

        # One bracket, whatever the facets are. A comparison facet is written
        # with its symbol and anything else with its keyword, and the two mix
        # freely — `xsd:integer[≥1 ⊓ totalDigits 3]`. There used to be a second
        # shape for the keyword form, `[xsd:integer ⊓ [totalDigits 3]]`, which
        # the grammar still reads and nothing now writes.
        inner = (" %s " % AND).join(
            "%s%s" % (COMPACT_FACETS[kwarg], _number(value))
            if kwarg in COMPACT_FACETS
            else "%s %s" % (FACET_OUTPUT[kwarg], _literal(value))
            for kwarg, value in facets
        )
        return "%s[%s]" % (base, inner)

    # ── triple access ────────────────────────────────────────────────────────
    #
    # Annotations are read straight from the quadstore rather than through
    # Owlready2 accessors, matching how the reader writes them and keeping
    # untyped subjects (predicates) visible.

    def _data_values(self, subject_iri, property_iri):
        subject = self.world._abbreviate(subject_iri)
        prop = self.world._abbreviate(property_iri)
        out = []
        for _, _, value, datatype in self.world._get_data_triples_spod_spod(
            subject, prop, None, None
        ):
            out.append(self.world._to_python(value, datatype))
        return out

    def _object_values(self, subject_iri, property_iri):
        subject = self.world._abbreviate(subject_iri)
        prop = self.world._abbreviate(property_iri)
        out = []
        for _, _, obj in self.world._get_obj_triples_spo_spo(subject, prop, None):
            iri = self.world._unabbreviate(obj) if obj > 0 else None
            if iri:
                out.append(iri)
        return out

    def _data_triples_by_property(self, property_storid):
        out = []
        for subject, _, value, datatype in self.world._get_data_triples_spod_spod(
            None, property_storid, None, None
        ):
            if subject < 0:
                continue  # a blank node cannot be a DLe predicate
            out.append((self.world._unabbreviate(subject),
                        self.world._to_python(value, datatype)))
        return out


# ── helpers ──────────────────────────────────────────────────────────────────


def _names_in(line, name):
    """Whether ``line`` mentions ``name`` as a whole name rather than a substring.

    ``Cat`` must not be found inside ``Catalogue``, nor ``A`` inside ``A1``.
    """
    return re.search(r"(?<![A-Za-z0-9_:.-])%s(?![A-Za-z0-9_-])" % re.escape(name),
                     line) is not None


def _datatype_iri(value):
    """The datatype IRI Owlready2 would give this Python value, or None."""
    import owlready2.base as base

    abbrev = base._universal_datatype_2_abbrev.get(type(value))
    if abbrev is None:
        return None
    return base._universal_abbrev_2_iri.get(abbrev)


def _lexical(value):
    """The lexical form of a typed value, as RDF spells it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    return str(value)


def _escape(text):
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def _number(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _literal(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(_number(value))
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return '"%s"' % value.isoformat()
    return '"%s"' % _escape(value)


def dumps(onto, prefixes=None, include_header=True):
    """Render ``onto`` as DLe text."""
    return Writer(onto, prefixes=prefixes, include_header=include_header).render()
