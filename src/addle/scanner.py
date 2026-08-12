"""Pass 1: classify every name in a document as class, property or predicate.

DLe is locally ambiguous about entity types. In ``∃r.C`` the name ``r`` is an
object property if ``C`` is a class expression and a data property if ``C`` is a
datatype — and ``locatedIn ⊑ containedIn`` is syntactically indistinguishable
from ``Animal ⊑ WildlifeConcept``. Neither can be decided without seeing the
whole document, so classification happens in its own pass before any Owlready2
entity is created.

This mirrors ``EntityTypeScanner`` in the Java implementation, including its
propagation of property kinds across sub-property axioms.
"""

from ._antlr.DLESyntaxParser import DLESyntaxParser as P
from .vocab import is_datatype_name

OBJECT = "object"
DATA = "data"
ANNOTATION = "annotation"
UNKNOWN = "unknown"


def _name_text(ctx):
    return ctx.getText() if ctx is not None else None


def _property_name(ctx):
    """The bare name of a ``propertyExpr``, ignoring any inverse marker."""
    if isinstance(ctx, (P.InversePropertyExprContext, P.SimplePropertyExprContext)):
        return _name_text(ctx.name())
    return None


class EntityKinds:
    """The result of pass 1: what kind of thing each name denotes."""

    def __init__(self):
        self.properties = {}       # name -> OBJECT | DATA | ANNOTATION | UNKNOWN
        self.predicates = set()    # names defined with ≝
        self.individuals = set()   # names appearing inside { … }
        self.class_names = set()   # names used in class position
        self.datatypes = set()     # names denoting datatypes
        self._subproperty = []     # (sub, super) candidate pairs

    # ── recording ────────────────────────────────────────────────────────────

    def note_property(self, name, kind=UNKNOWN):
        if name is None:
            return
        current = self.properties.get(name, UNKNOWN)
        # A definite classification always wins over UNKNOWN. When two definite
        # kinds collide the document is inconsistent; DATA wins, matching the
        # Java implementation's `nameToPropertyOrClass`.
        if current == UNKNOWN or kind == DATA:
            self.properties[name] = kind if kind != UNKNOWN else current

    def note_class(self, name):
        if name is None:
            return
        if is_datatype_name(name):
            self.datatypes.add(name)
        else:
            self.class_names.add(name)

    def kind_of_property(self, name):
        return self.properties.get(name, UNKNOWN)

    def is_property(self, name):
        return name in self.properties

    def is_object_property(self, name):
        return self.properties.get(name) == OBJECT

    def is_data_property(self, name):
        return self.properties.get(name) == DATA

    def is_annotation_property(self, name):
        return self.properties.get(name) == ANNOTATION

    def is_class(self, name):
        return (
            name not in self.properties
            and name not in self.predicates
            and not is_datatype_name(name)
        )

    # ── propagation ──────────────────────────────────────────────────────────

    def propagate(self):
        """Spread definite property kinds across sub-property axioms.

        Runs to a fixpoint in both directions: a known sub-property tells us
        about its super-property and vice versa. Anything still unknown at the
        end defaults to an object property, which is OWL's own default.
        """
        changed = True
        while changed:
            changed = False
            for sub, sup in self._subproperty:
                sub_known = sub in self.properties
                sup_known = sup in self.properties
                if not (sub_known or sup_known):
                    # Two names neither of which is a property: an ordinary
                    # subclass axiom, so there is nothing to propagate.
                    continue
                # A property can only be subsumed by a property, so one known
                # side makes the other a property too.
                sub_kind = self.properties.get(sub, UNKNOWN)
                sup_kind = self.properties.get(sup, UNKNOWN)
                if sub_kind != UNKNOWN and sup_kind == UNKNOWN:
                    self.properties[sup] = sub_kind
                    changed = True
                elif sup_kind != UNKNOWN and sub_kind == UNKNOWN:
                    self.properties[sub] = sup_kind
                    changed = True
                elif not sub_known:
                    self.properties[sub] = UNKNOWN
                    changed = True
                elif not sup_known:
                    self.properties[sup] = UNKNOWN
                    changed = True

        for name, kind in self.properties.items():
            if kind == UNKNOWN:
                self.properties[name] = OBJECT

        # A name classified as a property is not also a class.
        self.class_names -= set(self.properties)
        self.class_names -= self.predicates


class _Scanner:
    """Walks the parse tree recording what it learns about each name."""

    def __init__(self):
        self.kinds = EntityKinds()

    # ── entry ────────────────────────────────────────────────────────────────

    def scan(self, tree):
        for statement in tree.statement():
            child = statement.getChild(0)
            if isinstance(child, P.AnnotationContext):
                self._annotation(child)
            elif isinstance(child, P.AxiomContext):
                self._axiom(child)
        self.kinds.propagate()
        return self.kinds

    # ── annotations ──────────────────────────────────────────────────────────

    def _annotation(self, ctx):
        if isinstance(ctx, P.PredicateDefinitionContext):
            self.kinds.predicates.add(_name_text(ctx.name(0)))
        elif isinstance(ctx, P.FolAnnotationContext):
            self.kinds.predicates.add(_name_text(ctx.name()))
        elif isinstance(ctx, P.AnnAnnotationContext):
            self.kinds.note_property(_name_text(ctx.name(1)), ANNOTATION)
        # @label/@doc/@db/@storage tell us nothing about the subject's kind.

    # ── axioms ───────────────────────────────────────────────────────────────

    def _axiom(self, ctx):
        if isinstance(ctx, (P.TransitiveRoleAxiomContext, P.ReflexiveRoleAxiomContext,
                            P.IrreflexiveRoleAxiomContext, P.SymmetricRoleAxiomContext,
                            P.AsymmetricRoleAxiomContext)):
            # These characteristics only exist for object properties.
            self.kinds.note_property(_name_text(ctx.name()), OBJECT)

        elif isinstance(ctx, P.FunctionalRoleAxiomContext):
            # Func() applies to both object and data properties — kind unknown.
            self.kinds.note_property(_name_text(ctx.name()), UNKNOWN)

        elif isinstance(ctx, P.DisjointRoleAxiomContext):
            # Disj() likewise applies to either kind.
            for name in ctx.name():
                self.kinds.note_property(_name_text(name), UNKNOWN)

        elif isinstance(ctx, (P.AnnPropDomainAxiomContext, P.AnnPropRangeAxiomContext)):
            self.kinds.note_property(_name_text(ctx.name(0)), ANNOTATION)
            self.kinds.note_class(_name_text(ctx.name(1)))

        elif isinstance(ctx, P.FunctionalPropertyAxiomContext):
            self.kinds.note_property(_property_name(ctx.propertyExpr()), UNKNOWN)
            self._class_expr(ctx.classExpr())

        elif isinstance(ctx, P.HasKeyAxiomContext):
            self._class_expr(ctx.classExpr())
            for name in ctx.keyExpr().name():
                self.kinds.note_property(_name_text(name), UNKNOWN)

        elif isinstance(ctx, P.SubPropertyChainAxiomContext):
            self._chain(ctx.chainExpr())
            self.kinds.note_property(_name_text(ctx.name()), OBJECT)

        elif isinstance(ctx, P.PropertyChainEquivAxiomContext):
            self.kinds.note_property(_name_text(ctx.name()), OBJECT)
            self._chain(ctx.chainExpr())

        elif isinstance(ctx, P.ChainedEquivSubAxiomContext):
            for expr in ctx.propertyExpr():
                self.kinds.note_property(_property_name(expr), OBJECT)

        elif isinstance(ctx, P.SubClassAxiomContext):
            left, right = ctx.classExpr(0), ctx.classExpr(1)
            self._subsumption(left, right)

        elif isinstance(ctx, P.EquivAxiomContext):
            left, right = ctx.classExpr(0), ctx.classExpr(1)
            self._equivalence(left, right)

    def _subsumption(self, left, right):
        left_name = _single_bare_name(left)
        right_name = _single_bare_name(right)

        # `a ⊑ b` with two bare names is a sub-property axiom when either side is
        # already known to be a property; recorded either way and resolved during
        # propagation.
        if left_name and right_name:
            self.kinds._subproperty.append((left_name, right_name))
            if not self.kinds.is_property(left_name):
                self.kinds.note_class(left_name)
            if not self.kinds.is_property(right_name):
                self.kinds.note_class(right_name)
            return

        # `p⁻` on the right of a subsumption is a property axiom (e.g. symmetry).
        self._class_expr(left)
        self._class_expr(right)

    def _equivalence(self, left, right):
        left_name = _single_bare_name(left)
        right_inverse = _single_inverse_name(right)
        if left_name and right_inverse:
            # `contains ≡ locatedIn⁻` — both sides are object properties.
            self.kinds.note_property(left_name, OBJECT)
            self.kinds.note_property(right_inverse, OBJECT)
            return
        self._class_expr(left)
        self._class_expr(right)

    def _chain(self, ctx):
        for expr in ctx.propertyExpr():
            self.kinds.note_property(_property_name(expr), OBJECT)

    # ── class expressions ────────────────────────────────────────────────────

    def _class_expr(self, ctx):
        if ctx is None:
            return
        if isinstance(ctx, P.UnionOfContext):
            self._class_expr(ctx.classExpr())
            self._class_expr(ctx.intersectionExpr())
        elif isinstance(ctx, P.IntersectionWrapContext):
            self._class_expr(ctx.intersectionExpr())
        elif isinstance(ctx, P.IntersectionOfContext):
            self._class_expr(ctx.intersectionExpr())
            self._class_expr(ctx.primary())
        elif isinstance(ctx, P.PrimaryWrapContext):
            self._class_expr(ctx.primary())
        else:
            self._primary(ctx)

    def _primary(self, ctx):
        if ctx is None:
            return

        if isinstance(ctx, P.ComplementContext):
            self._class_expr(ctx.primary())

        elif isinstance(ctx, (P.MultiRoleSomeValuesFromContext,
                              P.MultiRoleAllValuesFromContext)):
            # ∃r₁,r₂.pred — the filler is a predicate, and multi-role
            # restrictions compare attribute values, so the roles are data
            # properties unless something else proves otherwise.
            for expr in ctx.propertyExpr():
                self.kinds.note_property(_property_name(expr), DATA)
            self.kinds.predicates.add(_name_text(ctx.name()))

        elif isinstance(ctx, (P.SomeValuesFromContext, P.AllValuesFromContext,
                              P.ImplicitSomeValuesFromContext,
                              P.CardinalityRestrictionContext)):
            role = _property_name(ctx.propertyExpr())
            filler = ctx.primary()
            self.kinds.note_property(role, self._filler_kind(filler, role))
            self._filler(filler, role)

        elif isinstance(ctx, P.UnqualifiedCardinalityRestrictionContext):
            self.kinds.note_property(_property_name(ctx.propertyExpr()), UNKNOWN)

        elif isinstance(ctx, P.AtomWrapContext):
            self._atom(ctx.atom())

        else:
            self._atom(ctx)

    def _filler_kind(self, filler, role):
        """Decide the role's kind from the shape of its filler."""
        if filler is None:
            return UNKNOWN

        atom = _unwrap_atom(filler)
        if atom is None:
            # A compound filler (union/intersection) — inspect its leaves.
            return self._compound_filler_kind(filler)

        if isinstance(atom, (P.NumericDataRangeAtomContext, P.DataRangeAtomContext)):
            return DATA
        if isinstance(atom, P.NameAtomContext):
            name = _name_text(atom)
            if is_datatype_name(name):
                return DATA
            if name in self.kinds.predicates:
                return DATA
            return OBJECT
        if isinstance(atom, P.OneOfAtomContext):
            return DATA if _one_of_is_literals(atom.oneOfList()) else OBJECT
        if isinstance(atom, (P.TopAtomContext, P.BottomAtomContext)):
            return UNKNOWN  # ⊤/⊥ are legal for either kind
        if isinstance(atom, P.SelfAtomContext):
            return OBJECT
        if isinstance(atom, P.ParenAtomContext):
            return self._compound_filler_kind(atom.classExpr())
        return UNKNOWN

    def _compound_filler_kind(self, ctx):
        """Kind implied by a union/intersection filler: DATA if any leaf is a datatype."""
        kinds = set()
        for atom in _leaf_atoms(ctx):
            if isinstance(atom, (P.NumericDataRangeAtomContext, P.DataRangeAtomContext)):
                kinds.add(DATA)
            elif isinstance(atom, P.NameAtomContext):
                kinds.add(DATA if is_datatype_name(_name_text(atom)) else OBJECT)
            elif isinstance(atom, P.OneOfAtomContext):
                kinds.add(DATA if _one_of_is_literals(atom.oneOfList()) else OBJECT)
        if DATA in kinds:
            return DATA
        if OBJECT in kinds:
            return OBJECT
        return UNKNOWN

    def _filler(self, filler, role):
        if filler is None:
            return
        atom = _unwrap_atom(filler)
        if isinstance(atom, P.NameAtomContext):
            name = _name_text(atom)
            if name not in self.kinds.predicates:
                self.kinds.note_class(name)
            return
        if isinstance(atom, P.OneOfAtomContext):
            self._one_of(atom.oneOfList(), role)
            return
        if atom is None:
            self._primary(filler)
        else:
            self._atom(atom)

    def _atom(self, ctx):
        if ctx is None:
            return
        if isinstance(ctx, P.NameAtomContext):
            self.kinds.note_class(_name_text(ctx))
        elif isinstance(ctx, P.InversePropertyAtomContext):
            self.kinds.note_property(_name_text(ctx.name()), OBJECT)
        elif isinstance(ctx, P.NumericDataRangeAtomContext):
            self.kinds.datatypes.add(_name_text(ctx.name()))
        elif isinstance(ctx, P.DataRangeAtomContext):
            self.kinds.datatypes.add(_name_text(ctx.datatypeRestriction().name()))
        elif isinstance(ctx, P.OneOfAtomContext):
            self._one_of(ctx.oneOfList(), None)
        elif isinstance(ctx, P.ParenAtomContext):
            self._class_expr(ctx.classExpr())

    def _one_of(self, ctx, role):
        for elem in ctx.oneOfElem():
            if isinstance(elem, P.IndividualElemContext):
                self.kinds.individuals.add(_name_text(elem.name()))


# ── tree shape helpers ───────────────────────────────────────────────────────


def _single_bare_name(ctx):
    """The name text if ``ctx`` is nothing but a single bare name, else None."""
    atom = _unwrap_class_expr_atom(ctx)
    if isinstance(atom, P.NameAtomContext):
        return _name_text(atom)
    return None


def _single_inverse_name(ctx):
    """The name text if ``ctx`` is exactly ``name⁻``, else None."""
    atom = _unwrap_class_expr_atom(ctx)
    if isinstance(atom, P.InversePropertyAtomContext):
        return _name_text(atom.name())
    return None


def _unwrap_class_expr_atom(ctx):
    """Strip the union/intersection/primary wrappers around a lone atom."""
    if not isinstance(ctx, P.IntersectionWrapContext):
        return None
    inter = ctx.intersectionExpr()
    if not isinstance(inter, P.PrimaryWrapContext):
        return None
    return _unwrap_atom(inter.primary())


def _unwrap_atom(primary):
    """The atom inside a ``primary``, or None if it is a restriction."""
    if isinstance(primary, P.AtomWrapContext):
        return primary.atom()
    return None


def _leaf_atoms(ctx):
    """Every atom reachable from a class expression, ignoring restrictions."""
    found = []

    def walk(node):
        if node is None:
            return
        if isinstance(node, P.AtomContext) or isinstance(
            node, (P.NameAtomContext, P.TopAtomContext, P.BottomAtomContext,
                   P.SelfAtomContext, P.OneOfAtomContext, P.NumericDataRangeAtomContext,
                   P.DataRangeAtomContext, P.InversePropertyAtomContext,
                   P.EmptyAtomContext)
        ):
            found.append(node)
            if isinstance(node, P.ParenAtomContext):
                walk(node.classExpr())
            return
        for i in range(node.getChildCount()):
            child = node.getChild(i)
            if hasattr(child, "getChildCount"):
                walk(child)

    walk(ctx)
    return found


def _one_of_is_literals(ctx):
    """Whether a ``{ … }`` enumeration holds literals rather than individuals."""
    return any(isinstance(e, P.LiteralElemContext) for e in ctx.oneOfElem())


def scan(tree):
    """Classify every name in ``tree``. Returns :class:`EntityKinds`."""
    return _Scanner().scan(tree)
