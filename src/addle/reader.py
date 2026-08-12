"""Pass 2: turn a classified parse tree into an Owlready2 ontology.

Runs after :mod:`addle.scanner` has decided what each name denotes. Everything
here is about mapping DLe constructs onto Owlready2's object model — and, where
DLe says something OWL has no vocabulary for, onto the same annotation-based
encoding the Java implementation uses, so documents survive a trip through
either library.
"""

import types

import owlready2
from antlr4 import Token
from owlready2 import (
    AllDisjoint,
    AnnotationProperty,
    AsymmetricProperty,
    ConstrainedDatatype,
    DataProperty,
    FunctionalProperty,
    GeneralClassAxiom,
    Inverse,
    IrreflexiveProperty,
    Not,
    Nothing,
    ObjectProperty,
    OneOf,
    PropertyChain,
    ReflexiveProperty,
    Restriction,
    SymmetricProperty,
    Thing,
    TransitiveProperty,
)
from owlready2.class_construct import Construct
from owlready2.base import EXACTLY, HAS_SELF, MAX, MIN, ONLY, SOME

from ._antlr.DLESyntaxLexer import DLESyntaxLexer
from ._antlr.DLESyntaxParser import DLESyntaxParser as P
from . import scanner
from .errors import DleSemanticError
from .scanner import DATA, OBJECT, ANNOTATION
from .vocab import (
    COMMENT_IRI,
    DB_IRI,
    DEFAULT_NS,
    DOC_IRI,
    FACET_KEYWORDS,
    IMPLICIT_PREFIXES,
    INLINE_COMMENT_IRI,
    LABEL_IRI,
    OWL_NS,
    PREDICATE_IRI,
    RDFS_NS,
    STORAGE_IRI,
    XSD_NS,
    is_datatype_name,
    split_iri,
    synthetic_class_iri,
)

#: XSD/RDF datatype IRI → the Python type Owlready2 uses for it.
_DATATYPE_BY_IRI = {}


def _build_datatype_table():
    base = owlready2.base
    for datatype, abbrev in base._universal_datatype_2_abbrev.items():
        iri = base._universal_abbrev_2_iri.get(abbrev)
        if iri and iri not in _DATATYPE_BY_IRI:
            _DATATYPE_BY_IRI[iri] = datatype
    # `float` is registered against xsd:decimal; xsd:double and xsd:float carry
    # the same Python type even though the IRI is not preserved on write.
    _DATATYPE_BY_IRI.setdefault(XSD_NS + "double", float)
    _DATATYPE_BY_IRI.setdefault(XSD_NS + "float", float)


_build_datatype_table()

_CHARACTERISTICS = {
    P.TransitiveRoleAxiomContext: TransitiveProperty,
    P.FunctionalRoleAxiomContext: FunctionalProperty,
    P.ReflexiveRoleAxiomContext: ReflexiveProperty,
    P.IrreflexiveRoleAxiomContext: IrreflexiveProperty,
    P.SymmetricRoleAxiomContext: SymmetricProperty,
    P.AsymmetricRoleAxiomContext: AsymmetricProperty,
}


class Reader:
    """Builds one Owlready2 ontology from one DLe parse tree."""

    def __init__(self, world=None, onto=None, base_iri=None):
        self.world = world or (onto.world if onto is not None else owlready2.default_world)
        self.onto = onto
        self.requested_base_iri = base_iri
        self.prefixes = dict(IMPLICIT_PREFIXES)
        self.kinds = None
        self.warnings = []
        self._namespaces = {}
        self._entities = {}
        self._key_axioms = []

    # ── entry point ──────────────────────────────────────────────────────────

    def read(self, tree, tokens=None):
        self.kinds = scanner.scan(tree)
        self._read_declarations(tree)
        self._ensure_ontology()
        comments = _CommentIndex(tokens) if tokens is not None else None

        for statement in tree.statement():
            node = statement.getChild(0)
            if isinstance(node, P.AnnotationContext):
                self._annotation(node)
            else:
                self._axiom(node)
            # Comments are attached after the statement they precede, so the
            # entity they describe already exists as the right kind of thing.
            if comments is not None:
                self._attach_comments(comments, statement, node)

        self._apply_key_axioms()
        return self.onto

    # ── document-level declarations ──────────────────────────────────────────

    def _read_declarations(self, tree):
        self.ontology_iri = None
        self.version_iri = None
        self.imports = []

        for decl in tree.prefixDecl():
            prefix = decl.PNAME_NS().getText()[:-1]
            self.prefixes[prefix] = _strip_angle(decl.IRI().getText())
        for decl in tree.ontologyDecl():
            self.ontology_iri = self._iri_ref(decl.iriRef())
        for decl in tree.versionDecl():
            self.version_iri = self._iri_ref(decl.iriRef())
        for decl in tree.importDecl():
            self.imports.append(self._iri_ref(decl.iriRef()))

    def _ensure_ontology(self):
        if self.onto is None:
            base = (
                self.requested_base_iri
                or self.ontology_iri
                or self.prefixes.get("")
                or DEFAULT_NS
            )
            self.onto = self.world.get_ontology(base)

        if self.version_iri:
            self._add_object_triple(
                self.onto.base_iri.rstrip("#/"), OWL_NS + "versionIRI", self.version_iri
            )
        for iri in self.imports:
            self.onto.imported_ontologies.append(self.world.get_ontology(iri))

    # ── names and entities ───────────────────────────────────────────────────

    def _iri_ref(self, ctx):
        if ctx.IRI() is not None:
            return _strip_angle(ctx.IRI().getText())
        return self.expand(ctx.name().getText())

    def expand(self, name):
        """Expand a DLe name to a full IRI using the document's prefix map."""
        if name.startswith("<") and name.endswith(">"):
            return name[1:-1]
        if ":" in name:
            prefix, _, local = name.partition(":")
            namespace = self.prefixes.get(prefix)
            if namespace is None:
                raise DleSemanticError("Unknown prefix %r in name %r" % (prefix, name))
            return namespace + local
        return self.prefixes.get("", DEFAULT_NS) + name

    def _namespace(self, ns_iri):
        ns = self._namespaces.get(ns_iri)
        if ns is None:
            ns = self.onto.get_namespace(ns_iri)
            self._namespaces[ns_iri] = ns
        return ns

    def _new_entity(self, iri, base):
        # Owlready2 takes the target namespace from the enclosing `with` block
        # rather than a constructor argument.
        ns_iri, local = split_iri(iri)
        with self._namespace(ns_iri):
            return types.new_class(local, (base,))

    def entity_for(self, name):
        """The Owlready2 entity for a DLe name, created on first use.

        The kind comes from pass 1, so a name is created as the same kind of
        entity wherever in the document it first happens to be mentioned.
        """
        if name in self._entities:
            return self._entities[name]

        iri = self.expand(name)
        kind = self.kinds.properties.get(name)

        existing = self.world[iri]
        # An IRI that carries triples but no rdf:type comes back from Owlready2
        # as an individual. That happens when an annotation mentioned the name
        # before any axiom did, and it is not the entity we want — fall through
        # and declare the right kind instead.
        if existing is not None and isinstance(existing, type):
            self._entities[name] = existing
            return existing

        if kind == OBJECT:
            entity = self._new_entity(iri, ObjectProperty)
        elif kind == DATA:
            entity = self._new_entity(iri, DataProperty)
        elif kind == ANNOTATION:
            entity = self._new_entity(iri, AnnotationProperty)
        else:
            entity = self._new_entity(iri, Thing)

        self._entities[name] = entity
        return entity

    def individual_for(self, name):
        """The named individual for a DLe name inside a ``{ … }`` enumeration."""
        iri = self.expand(name)
        existing = self.world[iri]
        if existing is not None:
            if not isinstance(existing, owlready2.Thing):
                # OWL allows an IRI to be both a property and an individual;
                # Owlready2 maps one IRI to one entity, so the pun cannot be
                # represented. Report it rather than silently mangling it.
                self.warnings.append(
                    "%s is used both as a property and as an individual; "
                    "Owlready2 cannot represent this punning, so the individual "
                    "reference reuses the property entity" % name
                )
            return existing
        ns_iri, local = split_iri(iri)
        return self._namespace(ns_iri)[local] or Thing(local, namespace=self._namespace(ns_iri))

    def datatype_for(self, name):
        """The Python type Owlready2 uses for a DLe datatype name."""
        iri = self.expand(name)
        datatype = _DATATYPE_BY_IRI.get(iri)
        if datatype is None:
            self.warnings.append(
                "no Owlready2 datatype for %s; treating it as xsd:string" % name
            )
            return str
        return datatype

    # ── raw triples ──────────────────────────────────────────────────────────
    #
    # Annotation assertions are written as triples rather than through the
    # `entity.label = [...]` accessors. That keeps predicate IRIs untyped (as
    # OWLAPI leaves them) and avoids depending on Owlready2 python_name lookup
    # for `@ann` properties whose names are not Python identifiers.

    def _storid(self, iri):
        return self.world._abbreviate(iri)

    def _add_data_triple(self, subject_iri, property_iri, value):
        obj, datatype = self.onto._to_rdf(value)
        self.onto._add_data_triple_spod(
            self._storid(subject_iri), self._storid(property_iri), obj, datatype
        )

    def _add_object_triple(self, subject_iri, property_iri, object_iri):
        self.onto._add_obj_triple_spo(
            self._storid(subject_iri), self._storid(property_iri), self._storid(object_iri)
        )

    # ── annotations ──────────────────────────────────────────────────────────

    def _annotation(self, ctx):
        if isinstance(ctx, P.LabelAnnotationContext):
            self._annotate(ctx.name(), LABEL_IRI, _unquote(ctx.STRING().getText()))

        elif isinstance(ctx, P.DocAnnotationContext):
            self._annotate(ctx.name(), DOC_IRI, _unquote(ctx.STRING().getText()))

        elif isinstance(ctx, P.StorageAnnotationContext):
            self._annotate(ctx.name(), STORAGE_IRI, _unquote(ctx.STRING().getText()))

        elif isinstance(ctx, P.DbAnnotationContext):
            # `@db name` with no string means "stored under its own name".
            text = ctx.STRING()
            value = _unquote(text.getText()) if text is not None else ctx.name().getText()
            self._annotate(ctx.name(), DB_IRI, value)

        elif isinstance(ctx, P.AnnAnnotationContext):
            subject = self.expand(ctx.name(0).getText())
            prop = self.expand(ctx.name(1).getText())
            self.entity_for(ctx.name(1).getText())  # declare the annotation property
            value = ctx.annotationValue()
            if isinstance(value, P.StringAnnotationValueContext):
                self._add_data_triple(subject, prop, _unquote(value.STRING().getText()))
            else:
                self._add_object_triple(subject, prop, self.expand(value.name().getText()))

        elif isinstance(ctx, P.PredicateDefinitionContext):
            # greaterThan(x,y) ≝ x > y  →  rdf:value "greaterThan(x,y) → x > y"
            names = ctx.name()
            args = ",".join(n.getText() for n in names[1:])
            body = _definition_body(ctx.DEFINED_AS_LINE().getText())
            signature = "%s(%s)" % (names[0].getText(), args)
            self._add_data_triple(
                self.expand(names[0].getText()), PREDICATE_IRI, "%s → %s" % (signature, body)
            )

        elif isinstance(ctx, P.FolAnnotationContext):
            body = _definition_body(ctx.DEFINED_AS_LINE().getText())
            self._add_data_triple(
                self.expand(ctx.name().getText()),
                PREDICATE_IRI,
                "%s → %s" % (ctx.name().getText(), body),
            )

    def _annotate(self, name_ctx, property_iri, value):
        name = name_ctx.getText()
        # Predicates are not OWL entities and are deliberately left untyped,
        # exactly as OWLAPI leaves them; only the annotation itself is written.
        if name not in self.kinds.predicates:
            self.entity_for(name)
        self._add_data_triple(self.expand(name), property_iri, value)

    def _attach_comments(self, comments, statement, node):
        subject = self._statement_subject(node)
        if subject is None:
            return
        for text in comments.leading(statement):
            self._add_data_triple(subject, COMMENT_IRI, text)
        trailing = comments.trailing(statement)
        if trailing is not None:
            self._add_data_triple(subject, INLINE_COMMENT_IRI, trailing)

    def _statement_subject(self, node):
        """The IRI a statement's comments should be attached to."""
        try:
            if isinstance(node, (P.LabelAnnotationContext, P.DocAnnotationContext,
                                 P.StorageAnnotationContext, P.DbAnnotationContext)):
                return self.expand(node.name().getText())
            if isinstance(node, P.AnnAnnotationContext):
                return self.expand(node.name(0).getText())
            if isinstance(node, P.PredicateDefinitionContext):
                return self.expand(node.name(0).getText())
            if isinstance(node, P.FolAnnotationContext):
                return self.expand(node.name().getText())
            if isinstance(node, (P.SubClassAxiomContext, P.EquivAxiomContext)):
                name = scanner._single_bare_name(node.classExpr(0))
                if name:
                    return self.expand(name)
                return self._first_property_iri(node.classExpr(0))
            if isinstance(node, P.HasKeyAxiomContext):
                name = scanner._single_bare_name(node.classExpr())
                return self.expand(name) if name else None
            for attr in ("name",):
                if hasattr(node, attr):
                    value = getattr(node, attr)()
                    if value is not None and not isinstance(value, list):
                        return self.expand(value.getText())
        except DleSemanticError:
            return None
        return None

    def _first_property_iri(self, ctx):
        """The IRI of the first role mentioned in a class expression, if any."""
        stack = [ctx]
        while stack:
            node = stack.pop(0)
            if node is None or not hasattr(node, "getChildCount"):
                continue
            if isinstance(node, P.PropertyExprContext):
                return self.expand(node.name().getText())
            for i in range(node.getChildCount()):
                stack.append(node.getChild(i))
        return None

    # ── axioms ───────────────────────────────────────────────────────────────

    def _axiom(self, ctx):
        characteristic = _CHARACTERISTICS.get(type(ctx))
        if characteristic is not None:
            prop = self.entity_for(ctx.name().getText())
            if characteristic not in prop.is_a:
                prop.is_a.append(characteristic)
            return

        if isinstance(ctx, P.DisjointRoleAxiomContext):
            props = [self.entity_for(n.getText()) for n in ctx.name()]
            AllDisjoint(props, ontology=self.onto)
            return

        if isinstance(ctx, (P.AnnPropDomainAxiomContext, P.AnnPropRangeAxiomContext)):
            prop = self.entity_for(ctx.name(0).getText())
            target = self.entity_for(ctx.name(1).getText())
            attr = "domain" if isinstance(ctx, P.AnnPropDomainAxiomContext) else "range"
            getattr(prop, attr).append(target)
            return

        if isinstance(ctx, P.FunctionalPropertyAxiomContext):
            self._cardinality_axiom(ctx)
            return

        if isinstance(ctx, P.HasKeyAxiomContext):
            name = scanner._single_bare_name(ctx.classExpr())
            if name is None:
                self.warnings.append("key() on a complex class expression is not supported")
                return
            keys = [self.entity_for(n.getText()) for n in ctx.keyExpr().name()]
            self._key_axioms.append((self.entity_for(name), keys))
            return

        if isinstance(ctx, P.SubPropertyChainAxiomContext):
            chain = self._chain(ctx.chainExpr())
            target = self.entity_for(ctx.name().getText())
            target.property_chain.append(PropertyChain(chain))
            return

        if isinstance(ctx, P.PropertyChainEquivAxiomContext):
            chain = self._chain(ctx.chainExpr())
            target = self.entity_for(ctx.name().getText())
            target.property_chain.append(PropertyChain(chain))
            return

        if isinstance(ctx, P.ChainedEquivSubAxiomContext):
            exprs = [self._property_expr(e) for e in ctx.propertyExpr()]
            if len(exprs) == 3:
                target = exprs[2]
                target.property_chain.append(PropertyChain([exprs[0], exprs[1]]))
            return

        if isinstance(ctx, P.SubClassAxiomContext):
            self._subclass_axiom(ctx.classExpr(0), ctx.classExpr(1))
            return

        if isinstance(ctx, P.EquivAxiomContext):
            self._equivalence_axiom(ctx.classExpr(0), ctx.classExpr(1))
            return

        self.warnings.append("unhandled axiom form: %s" % type(ctx).__name__)

    def _cardinality_axiom(self, ctx):
        """``≤1 p.⊤`` and friends: a bare cardinality bound on a property."""
        symbol = ctx.cardSymbol().getText()
        number = int(ctx.NUMBER().getText())
        prop = self._property_expr(ctx.propertyExpr())
        filler_is_top = scanner._single_bare_name(ctx.classExpr()) is None and _is_top(
            ctx.classExpr()
        )

        if symbol == "≤" and number == 1 and filler_is_top:
            if FunctionalProperty not in prop.is_a:
                prop.is_a.append(FunctionalProperty)
            return

        # Anything else is a global bound: ⊤ ⊑ (≥n p.C)
        restriction = self._restriction(
            symbol, number, prop, self._filler_or_none(ctx.classExpr())
        )
        self._add_universal_axiom(restriction)

    def _add_universal_axiom(self, target):
        """Assert ``⊤ ⊑ target``.

        Owlready2's ``GeneralClassAxiom`` requires a blank node on the left, so
        it cannot carry ``owl:Thing``. The axiom is written as the triple OWL
        actually uses — ``owl:Thing rdfs:subClassOf X`` — which every RDF
        consumer understands even though no Owlready2 accessor surfaces it.
        """
        if isinstance(target, Construct):
            if target.ontology is None:
                target._set_ontology(self.onto)
        self.onto._add_obj_triple_spo(
            Thing.storid, self._storid(RDFS_NS + "subClassOf"), target.storid
        )

    def _subclass_axiom(self, left, right):
        left_name = scanner._single_bare_name(left)
        right_name = scanner._single_bare_name(right)

        # p ⊑ q between two properties is a sub-property axiom.
        if left_name and right_name and self.kinds.is_property(left_name):
            sub = self.entity_for(left_name)
            sup = self.entity_for(right_name)
            if sup not in sub.is_a:
                sub.is_a.append(sup)
            return

        # ∃p.⊤ ⊑ C  is p's domain.
        domain_prop = self._domain_shape(left)
        if domain_prop is not None:
            self.entity_for(domain_prop).domain.append(self._class_expr(right))
            return

        # ⊤ ⊑ ∀p.C  is p's range.
        range_prop, range_filler = self._range_shape(left, right)
        if range_prop is not None:
            self.entity_for(range_prop).range.append(self._class_expr_or_range(range_filler))
            return

        # p ⊓ q ⊑ ⊥ makes two properties disjoint.
        disjoint = self._disjoint_property_shape(left, right)
        if disjoint is not None:
            AllDisjoint([self.entity_for(n) for n in disjoint], ontology=self.onto)
            return

        # ∃p.Self ⊑ ⊥ is irreflexivity.
        self_prop = self._self_shape(left, right)
        if self_prop is not None:
            prop = self.entity_for(self_prop)
            if IrreflexiveProperty not in prop.is_a:
                prop.is_a.append(IrreflexiveProperty)
            return

        # ⊤ ⊑ X, once the ∀-range idiom above has been ruled out.
        if _is_top(left):
            self._add_universal_axiom(self._class_expr(right))
            return

        target = self._class_expr(right)
        if left_name and self.kinds.is_class(left_name):
            cls = self.entity_for(left_name)
            if target is Thing and cls.is_a == [Thing]:
                return  # `C ⊑ ⊤` is already implied by Owlready2's default
            if target not in cls.is_a:
                cls.is_a.append(target)
            if Thing in cls.is_a and len(cls.is_a) > 1:
                cls.is_a.remove(Thing)
            return

        axiom = GeneralClassAxiom(self._class_expr(left), namespace=self.onto)
        axiom.is_a.append(target)

    def _equivalence_axiom(self, left, right):
        left_name = scanner._single_bare_name(left)
        right_inverse = scanner._single_inverse_name(right)

        # contains ≡ locatedIn⁻
        if left_name and right_inverse and self.kinds.is_property(left_name):
            prop = self.entity_for(left_name)
            prop.inverse_property = self.entity_for(right_inverse)
            return

        if left_name and self.kinds.is_property(left_name):
            prop = self.entity_for(left_name)
            prop.equivalent_to.append(self._class_expr(right))
            return

        if left_name and self.kinds.is_class(left_name):
            cls = self.entity_for(left_name)
            cls.equivalent_to.append(self._class_expr(right))
            return

        # A general concept equivalence. Owlready2's GeneralClassAxiom models
        # subsumption only, so this becomes mutual subsumption — the same
        # semantics, expressed twice. Each direction gets freshly built
        # constructs: a construct is an RDF blank node, and Owlready2 refuses to
        # let one be shared between two axioms.
        forward = GeneralClassAxiom(self._class_expr(left), namespace=self.onto)
        forward.is_a.append(self._class_expr(right))
        backward = GeneralClassAxiom(self._class_expr(right), namespace=self.onto)
        backward.is_a.append(self._class_expr(left))

    # ── axiom shape recognition ──────────────────────────────────────────────

    def _domain_shape(self, left):
        """Role name if ``left`` is exactly ``∃p.⊤``, else None."""
        primary = _unwrap_primary(left)
        if isinstance(primary, (P.SomeValuesFromContext, P.ImplicitSomeValuesFromContext)):
            if _is_top_primary(primary.primary()):
                expr = primary.propertyExpr()
                if isinstance(expr, P.SimplePropertyExprContext):
                    return expr.name().getText()
        return None

    def _range_shape(self, left, right):
        """(role name, filler) if the axiom is ``⊤ ⊑ ∀p.C``, else (None, None)."""
        if not _is_top(left):
            return None, None
        primary = _unwrap_primary(right)
        if isinstance(primary, P.AllValuesFromContext):
            expr = primary.propertyExpr()
            if isinstance(expr, P.SimplePropertyExprContext):
                return expr.name().getText(), primary.primary()
        return None, None

    def _disjoint_property_shape(self, left, right):
        """Property names if the axiom is ``p ⊓ q ⊑ ⊥``, else None."""
        if not _is_bottom(right):
            return None
        if not isinstance(left, P.IntersectionWrapContext):
            return None
        names = _intersection_bare_names(left.intersectionExpr())
        if names and all(self.kinds.is_property(n) for n in names):
            return names
        return None

    def _self_shape(self, left, right):
        """Role name if the axiom is ``∃p.Self ⊑ ⊥``, else None."""
        if not _is_bottom(right):
            return None
        primary = _unwrap_primary(left)
        if isinstance(primary, (P.SomeValuesFromContext, P.ImplicitSomeValuesFromContext)):
            inner = _unwrap_atom_of(primary.primary())
            if isinstance(inner, P.SelfAtomContext):
                expr = primary.propertyExpr()
                if isinstance(expr, P.SimplePropertyExprContext):
                    return expr.name().getText()
        return None

    # ── expressions ──────────────────────────────────────────────────────────

    def _chain(self, ctx):
        return [self._property_expr(e) for e in ctx.propertyExpr()]

    def _property_expr(self, ctx):
        prop = self.entity_for(ctx.name().getText())
        if isinstance(ctx, P.InversePropertyExprContext):
            return self._inverse(prop)
        return prop

    def _inverse(self, prop):
        """``p⁻`` as an Owlready2 property expression.

        ``Inverse`` collapses to the named inverse when the document declared
        one, so ``locatedIn⁻`` becomes ``contains`` rather than an anonymous
        construct. Anonymous inverses get their blank node assigned eagerly:
        ``PropertyChain`` serialises its members through ``_set_list``, which
        needs a storid already in place, and Owlready2 only assigns one when the
        construct is attached to an ontology.
        """
        inverse = Inverse(prop)
        if isinstance(inverse, Construct) and inverse.storid is None:
            inverse.storid = self.onto.world.new_blank_node()
        return inverse

    def _class_expr(self, ctx):
        if ctx is None:
            return Thing
        if isinstance(ctx, P.UnionOfContext):
            return Or_of([self._class_expr(ctx.classExpr()),
                          self._class_expr(ctx.intersectionExpr())])
        if isinstance(ctx, P.IntersectionWrapContext):
            return self._class_expr(ctx.intersectionExpr())
        if isinstance(ctx, P.IntersectionOfContext):
            return And_of([self._class_expr(ctx.intersectionExpr()),
                           self._class_expr(ctx.primary())])
        if isinstance(ctx, P.PrimaryWrapContext):
            return self._class_expr(ctx.primary())
        return self._primary(ctx)

    def _class_expr_or_range(self, ctx):
        """Like :meth:`_class_expr` but tolerates a bare data range."""
        return self._class_expr(ctx)

    def _primary(self, ctx):
        if isinstance(ctx, P.ComplementContext):
            return Not(self._primary(ctx.primary()))

        if isinstance(ctx, (P.MultiRoleSomeValuesFromContext,
                            P.MultiRoleAllValuesFromContext)):
            return self._multi_role(ctx)

        if isinstance(ctx, (P.SomeValuesFromContext, P.ImplicitSomeValuesFromContext)):
            filler = ctx.primary()
            predicate = self._predicate_filler(ctx.propertyExpr(), filler)
            if predicate is not None:
                return self._predicate_class("∃", [ctx.propertyExpr()], predicate)
            prop = self._property_expr(ctx.propertyExpr())
            if isinstance(_unwrap_atom_of(filler), P.SelfAtomContext):
                return Restriction(prop, HAS_SELF, None, True)
            if _is_top_primary(filler):
                return self._exists_top(prop, ctx.propertyExpr())
            return Restriction(prop, SOME, None, self._primary(filler))

        if isinstance(ctx, P.AllValuesFromContext):
            filler = ctx.primary()
            predicate = self._predicate_filler(ctx.propertyExpr(), filler)
            if predicate is not None:
                return self._predicate_class("∀", [ctx.propertyExpr()], predicate)
            prop = self._property_expr(ctx.propertyExpr())
            return Restriction(prop, ONLY, None, self._primary(filler))

        if isinstance(ctx, P.CardinalityRestrictionContext):
            return self._restriction(
                ctx.cardSymbol().getText(),
                int(ctx.NUMBER().getText()),
                self._property_expr(ctx.propertyExpr()),
                self._filler_or_none(ctx.primary()),
            )

        if isinstance(ctx, P.UnqualifiedCardinalityRestrictionContext):
            return self._restriction(
                ctx.cardSymbol().getText(),
                int(ctx.NUMBER().getText()),
                self._property_expr(ctx.propertyExpr()),
                None,
            )

        if isinstance(ctx, P.AtomWrapContext):
            return self._atom(ctx.atom())

        return self._atom(ctx)

    def _exists_top(self, prop, property_expr_ctx):
        """``∃p.⊤``: a min-1 bound, which needs no filler for either kind."""
        name = property_expr_ctx.name().getText()
        if self.kinds.is_data_property(name):
            # There is no Owlready2 spelling for the top data range, and
            # `≥1 p` is exactly equivalent.
            return Restriction(prop, MIN, 1, None)
        return Restriction(prop, SOME, None, Thing)

    def _restriction(self, symbol, number, prop, filler):
        """A cardinality restriction. ``filler`` is already built, or None for ⊤."""
        kind = {"≥": MIN, "≤": MAX, "=": EXACTLY}[symbol]
        return Restriction(prop, kind, number, filler)

    def _filler_or_none(self, ctx):
        """A built filler, or None when the filler is ⊤.

        Owlready2 spells an unqualified cardinality restriction with a filler of
        None, which is how ``≥n p.⊤`` is represented.
        """
        if ctx is None or _is_top(ctx):
            return None
        return self._class_expr(ctx)

    def _multi_role(self, ctx):
        quantifier = "∃" if isinstance(ctx, P.MultiRoleSomeValuesFromContext) else "∀"
        return self._predicate_class(quantifier, ctx.propertyExpr(), ctx.name().getText())

    def _predicate_filler(self, property_expr_ctx, filler):
        """The predicate name if this restriction's filler is a predicate.

        Mirrors ``isPredicateName`` in the Java implementation: a declared
        predicate always wins; a data property's filler is otherwise a data
        range; and an unrecognised lowercase-initial bare name is taken to be a
        predicate by convention.
        """
        atom = _unwrap_atom_of(filler)
        if not isinstance(atom, P.NameAtomContext):
            return None
        name = atom.getText()
        if name in self.kinds.predicates:
            return name

        role = property_expr_ctx.name().getText()
        if self.kinds.is_data_property(role):
            return None
        if self.kinds.is_property(name) or is_datatype_name(name) or ":" in name:
            return None
        if name in self.kinds.class_names:
            return None
        return name if name[:1].islower() else None

    def _predicate_class(self, quantifier, role_ctxs, predicate):
        """A predicate restriction, encoded as a synthetic class.

        OWL has no vocabulary for ``∃r₁,r₂.pred``, so DLe represents one as a
        named class in the ``dle:`` namespace whose ``rdfs:label`` is the
        original expression. The IRI embeds a hash computed exactly as the Java
        implementation computes it, so both mint the *same* class for the same
        expression and the encoding survives a round-trip through either.
        """
        roles = [e.getText() for e in role_ctxs]
        expr = "%s%s.%s" % (quantifier, ",".join(roles), predicate)
        iri = synthetic_class_iri(quantifier, expr, predicate)

        existing = self.world[iri]
        if existing is not None and isinstance(existing, type):
            return existing

        cls = self._new_entity(iri, Thing)
        self._add_data_triple(iri, LABEL_IRI, expr)
        for ctx in role_ctxs:
            self.entity_for(ctx.name().getText())
        return cls

    def _atom(self, ctx):
        if isinstance(ctx, P.TopAtomContext):
            return Thing
        if isinstance(ctx, P.BottomAtomContext):
            return Nothing
        if isinstance(ctx, P.EmptyAtomContext):
            return Nothing
        if isinstance(ctx, P.SelfAtomContext):
            raise DleSemanticError("Self is only valid as a restriction filler")
        if isinstance(ctx, P.NameAtomContext):
            return self._name_atom(ctx.getText())
        if isinstance(ctx, P.InversePropertyAtomContext):
            return Inverse(self.entity_for(ctx.name().getText()))
        if isinstance(ctx, P.ParenAtomContext):
            return self._class_expr(ctx.classExpr())
        if isinstance(ctx, P.OneOfAtomContext):
            return self._one_of(ctx.oneOfList())
        if isinstance(ctx, P.NumericDataRangeAtomContext):
            return self._numeric_range(ctx)
        if isinstance(ctx, P.DataRangeAtomContext):
            return self._datatype_restriction(ctx.datatypeRestriction())
        raise DleSemanticError("unsupported atom: %s" % type(ctx).__name__)

    def _name_atom(self, name):
        if is_datatype_name(name):
            return self.datatype_for(name)
        iri = self.expand(name)
        if iri == OWL_NS + "Thing":
            return Thing
        if iri == OWL_NS + "Nothing":
            return Nothing
        return self.entity_for(name)

    def _one_of(self, ctx):
        elements = []
        for elem in ctx.oneOfElem():
            if isinstance(elem, P.IndividualElemContext):
                elements.append(self.individual_for(elem.name().getText()))
            else:
                elements.append(_literal_value(elem.literal()))
        return OneOf(elements)

    def _numeric_range(self, ctx):
        """``xsd:integer[≥0 ⊓ <10]`` — compact numeric facets."""
        base = self.datatype_for(ctx.name().getText())
        kwargs = {}
        for facet in ctx.numericFacet():
            symbol = facet.getChild(0).getText()
            value = _number(facet.NUMBER().getText())
            kwargs[_COMPACT_FACET_KWARG[symbol]] = value
        return ConstrainedDatatype(base, **kwargs)

    def _datatype_restriction(self, ctx):
        """``[xsd:string ⊓ [matches "…"]]`` — keyword facets."""
        base = self.datatype_for(ctx.name().getText())
        kwargs = {}
        for facet in ctx.facet():
            keyword = facet.name().getText()
            kwarg = FACET_KEYWORDS.get(keyword)
            if kwarg is None:
                self.warnings.append("unknown datatype facet %r; ignored" % keyword)
                continue
            kwargs[kwarg] = _literal_value(facet.literal())
        return ConstrainedDatatype(base, **kwargs)

    # ── deferred axioms ──────────────────────────────────────────────────────

    def _apply_key_axioms(self):
        """Write ``owl:hasKey`` triples directly.

        Owlready2 has no model for key axioms, so they are written as raw RDF.
        That keeps them in the quadstore — reasoners and other serialisers see
        them — even though no Owlready2 accessor exposes them.
        """
        if not self._key_axioms:
            return
        has_key = self._storid(OWL_NS + "hasKey")
        for cls, keys in self._key_axioms:
            bnode = self.world.new_blank_node()
            self.onto._set_list(bnode, keys)
            self.onto._add_obj_triple_spo(cls.storid, has_key, bnode)


# ── helpers ──────────────────────────────────────────────────────────────────

_COMPACT_FACET_KWARG = {
    "≥": "min_inclusive",
    "≤": "max_inclusive",
    ">": "min_exclusive",
    "<": "max_exclusive",
}


def Or_of(parts):
    """``Or`` that flattens nested unions, so ``a ⊔ b ⊔ c`` is one construct."""
    flat = []
    for part in parts:
        if isinstance(part, owlready2.Or):
            flat.extend(part.Classes)
        else:
            flat.append(part)
    return owlready2.Or(flat)


def And_of(parts):
    """``And`` that flattens nested intersections."""
    flat = []
    for part in parts:
        if isinstance(part, owlready2.And):
            flat.extend(part.Classes)
        else:
            flat.append(part)
    return owlready2.And(flat)


def _strip_angle(text):
    return text[1:-1] if text.startswith("<") else text


def _unquote(text):
    """Undo the grammar's STRING token quoting and escapes."""
    body = text[1:-1]
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _definition_body(text):
    """The part of a ``≝`` line after the operator."""
    return text[1:].strip()


def _number(text):
    return float(text) if "." in text else int(text)


def _literal_value(ctx):
    if isinstance(ctx, P.StringLiteralContext):
        return _unquote(ctx.STRING().getText())
    if isinstance(ctx, P.NumberLiteralContext):
        return _number(ctx.NUMBER().getText())
    if isinstance(ctx, P.BoolLiteralContext):
        return ctx.BOOL().getText() == "true"
    raise DleSemanticError("unsupported literal: %s" % type(ctx).__name__)


def _unwrap_primary(ctx):
    """The single ``primary`` inside a class expression, or None."""
    if not isinstance(ctx, P.IntersectionWrapContext):
        return None
    inter = ctx.intersectionExpr()
    if not isinstance(inter, P.PrimaryWrapContext):
        return None
    return inter.primary()


def _unwrap_atom_of(primary):
    return primary.atom() if isinstance(primary, P.AtomWrapContext) else None


def _is_top(ctx):
    return isinstance(_unwrap_atom_of(_unwrap_primary(ctx) or ctx), P.TopAtomContext)


def _is_bottom(ctx):
    return isinstance(_unwrap_atom_of(_unwrap_primary(ctx) or ctx), P.BottomAtomContext)


def _is_top_primary(primary):
    return isinstance(_unwrap_atom_of(primary), P.TopAtomContext)


def _intersection_bare_names(ctx):
    """Bare names of an intersection, or None if any operand is compound."""
    names = []
    while isinstance(ctx, P.IntersectionOfContext):
        atom = _unwrap_atom_of(ctx.primary())
        if not isinstance(atom, P.NameAtomContext):
            return None
        names.insert(0, atom.getText())
        ctx = ctx.intersectionExpr()
    if isinstance(ctx, P.PrimaryWrapContext):
        atom = _unwrap_atom_of(ctx.primary())
        if not isinstance(atom, P.NameAtomContext):
            return None
        names.insert(0, atom.getText())
        return names if len(names) > 1 else None
    return None


class _CommentIndex:
    """Locates ``#`` comment tokens relative to statements.

    DLe comments are on ANTLR's hidden channel, so they never appear in the
    tree. They are recovered here and attached to whatever the following
    statement is about, which is what lets the writer put them back.
    """

    def __init__(self, tokens):
        self.tokens = tokens
        self._consumed = set()
        self._header_end = self._find_header_end()

    def _find_header_end(self):
        """Index just past the leading comment block, which is the file header."""
        tokens = self.tokens.tokens
        end = 0
        for i, token in enumerate(tokens):
            if token.channel == DLESyntaxLexer.HIDDEN:
                end = i + 1
            elif token.type != Token.EOF and token.text.strip():
                break
        return end

    def leading(self, statement):
        start = statement.start.tokenIndex
        hidden = self.tokens.getHiddenTokensToLeft(start, DLESyntaxLexer.HIDDEN) or []
        out = []
        for token in hidden:
            if token.tokenIndex < self._header_end or token.tokenIndex in self._consumed:
                continue
            self._consumed.add(token.tokenIndex)
            out.append(_comment_body(token.text))
        return out

    def trailing(self, statement):
        stop = statement.stop.tokenIndex
        hidden = self.tokens.getHiddenTokensToRight(stop, DLESyntaxLexer.HIDDEN) or []
        for token in hidden:
            if token.line != statement.stop.line or token.tokenIndex in self._consumed:
                continue
            self._consumed.add(token.tokenIndex)
            return _comment_body(token.text)
        return None


def _comment_body(text):
    """A comment's text with only its leading ``#`` removed.

    Only one ``#`` comes off, so rule-off lines like ``########`` survive the
    round-trip instead of collapsing to an empty comment.
    """
    return text[1:].rstrip() if text.startswith("#") else text.rstrip()
