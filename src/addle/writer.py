"""Render an Owlready2 ontology as DLe text.

The output ordering mirrors ``DLESyntaxStorerBase`` in the Java implementation:
a header, ontology-level declarations, prefixes, predicate definitions, then one
block per entity — comments, annotations, logical axioms — separated by blank
lines. Entities in the ``dle:`` namespace are internal encoding artefacts and
are suppressed; their content resurfaces wherever they are referenced.
"""

import datetime
from importlib import resources

import owlready2
from owlready2 import (
    AsymmetricProperty,
    ConstrainedDatatype,
    FunctionalProperty,
    Inverse,
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

_CHARACTERISTIC_KEYWORDS = [
    (TransitiveProperty, "Trans"),
    (FunctionalProperty, "Func"),
    (ReflexiveProperty, "Ref"),
    (IrreflexiveProperty, "Irref"),
    (SymmetricProperty, "Sym"),
    (AsymmetricProperty, "Asym"),
]

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
        self.prefixes = self._build_prefixes(prefixes)
        self._labels = {}   # dle: synthetic class IRI -> its expression text
        self._inverse_pairs = set()
        self._disjoint_pairs = set()
        self.warnings = []

    # ── prefixes ─────────────────────────────────────────────────────────────

    def _build_prefixes(self, extra):
        """Prefix map used to shorten IRIs, longest namespace first on output."""
        prefixes = dict(IMPLICIT_PREFIXES)
        # The ontology's own base IRI becomes the default prefix, which is what
        # makes a round-tripped document use bare names again.
        prefixes[""] = self.onto.base_iri
        if extra:
            prefixes.update(extra)
        return prefixes

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
        return local if prefix == "" else "%s:%s" % (prefix, local)

    # ── document ─────────────────────────────────────────────────────────────

    def render(self):
        lines = []
        if self.include_header:
            lines.append(header_text().rstrip("\n"))
            lines.append("")

        lines.extend(self._ontology_declarations())
        lines.extend(self._predicate_definitions())

        for entity in self._entities():
            block = self._entity_block(entity)
            if block:
                lines.extend(block)
                lines.append("")

        lines.extend(self._universal_axioms())
        lines.extend(self._orphan_axioms())

        text = "\n".join(lines)
        return text.rstrip("\n") + "\n"

    def _ontology_declarations(self):
        lines = []
        iri = self.onto.base_iri.rstrip("#/")
        lines.append("@ontology <%s>" % iri)

        version = self._object_values(self.onto.base_iri.rstrip("#/"), OWL_NS + "versionIRI")
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
                lines.append('@db %s "%s"' % (name, _escape(value)))

        for iri, keyword in _KEYWORD_ANNOTATIONS:
            for value in self._data_values(entity.iri, iri):
                lines.append('%s %s "%s"' % (keyword, name, _escape(value)))

        lines.extend(self._other_annotation_lines(entity, name))
        return lines

    def _other_annotation_lines(self, entity, name):
        """``@ann`` lines for annotation properties without a DLe keyword."""
        known = {LABEL_IRI, DOC_IRI, STORAGE_IRI, DB_IRI, COMMENT_IRI,
                 INLINE_COMMENT_IRI, PREDICATE_IRI}
        lines = []
        for prop in self.onto.annotation_properties():
            if prop.iri in known:
                continue
            for value in self._data_values(entity.iri, prop.iri):
                lines.append('@ann %s %s "%s"'
                             % (name, self.shorten(prop.iri), _escape(value)))
            for value in self._object_values(entity.iri, prop.iri):
                lines.append("@ann %s %s %s"
                             % (name, self.shorten(prop.iri), self.shorten(value)))
        return lines

    def _axiom_lines(self, entity):
        if isinstance(entity, owlready2.ThingClass):
            return self._class_axioms(entity)
        if isinstance(entity, owlready2.PropertyClass):
            return self._property_axioms(entity)
        return []

    def _class_axioms(self, cls):
        name = self.shorten(cls.iri)
        lines = []
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

        for value in getattr(prop, "domain", []) or []:
            lines.append("%s%s.%s %s %s" % (EXISTS, name, TOP, SUBCLASS, self.concept(value)))
        for value in getattr(prop, "range", []) or []:
            lines.append("%s %s %s%s.%s" % (TOP, SUBCLASS, FORALL, name, self._filler(value)))

        inverse = getattr(prop, "inverse_property", None)
        if inverse is not None and self._claim_inverse_pair(prop, inverse):
            lines.append("%s %s %s%s" % (name, EQUIV, self.shorten(inverse.iri), INVERSE))

        for chain in getattr(prop, "property_chain", []) or []:
            rendered = (" %s " % CHAIN).join(self.concept(p) for p in chain.properties)
            lines.append("%s %s %s" % (rendered, SUBCLASS, name))

        for characteristic, keyword in _CHARACTERISTIC_KEYWORDS:
            if characteristic in prop.is_a:
                lines.append("%s(%s)" % (keyword, name))

        for equivalent in getattr(prop, "equivalent_to", []) or []:
            lines.append("%s %s %s" % (name, EQUIV, self.concept(equivalent)))

        for disjoint in prop.disjoints():
            lines.extend(self._disjoint_lines(disjoint, prop))

        return lines

    def _claim_inverse_pair(self, prop, inverse):
        """Whether this property should be the one to write the inverse axiom.

        Owlready2 records ``inverse_property`` on both members of a pair, but
        ``p ≡ q⁻`` and ``q ≡ p⁻`` say the same thing — so only the first member
        seen writes it.
        """
        pair = frozenset((prop.iri, inverse.iri))
        if pair in self._inverse_pairs:
            return False
        self._inverse_pairs.add(pair)
        return True

    def _key_lines(self, cls, name):
        """``C ⊑ key(a,b)`` lines, read back from raw ``owl:hasKey`` triples."""
        has_key = self.world._abbreviate(OWL_NS + "hasKey")
        lines = []
        for _, _, bnode in self.world._get_obj_triples_spo_spo(cls.storid, has_key, None):
            keys = self.onto._parse_list(bnode)
            rendered = ",".join(self.shorten(k.iri) for k in keys)
            lines.append("%s %s key(%s)" % (name, SUBCLASS, rendered))
        return lines

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

        if all(kwarg in COMPACT_FACETS for kwarg, _ in facets):
            inner = (" %s " % AND).join(
                "%s%s" % (COMPACT_FACETS[kwarg], _number(value)) for kwarg, value in facets
            )
            return "%s[%s]" % (base, inner)

        inner = (" %s " % AND).join(
            "[%s %s]" % (FACET_OUTPUT[kwarg], _literal(value)) for kwarg, value in facets
        )
        return "[%s %s %s]" % (base, AND, inner)

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
