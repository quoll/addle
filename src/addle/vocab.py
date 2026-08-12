"""Namespaces, annotation IRIs and datatype mappings for DLe.

The values here are the contract between addle and the Java `dlextended-parsers`
implementation. Changing any of them breaks cross-implementation round-trips, so
they are kept in one place and mirrored by the conformance tests.
"""

DEFAULT_NS = "http://quoll.github.io/DLe/ontology#"
DLE_NS = "http://quoll.github.io/DLe/vocab#"
OWL_NS = "http://www.w3.org/2002/07/owl#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"

#: Prefixes every DLe document may use without declaring them.
IMPLICIT_PREFIXES = {
    "": DEFAULT_NS,
    "dle": DLE_NS,
    "owl": OWL_NS,
    "rdf": RDF_NS,
    "rdfs": RDFS_NS,
    "xsd": XSD_NS,
}

# ── Annotation IRIs ──────────────────────────────────────────────────────────
# DLe's annotation forms map onto existing RDFS properties rather than inventing
# new ones, so annotated ontologies stay meaningful to tools that know nothing
# about DLe.

LABEL_IRI = RDFS_NS + "label"           # @label
DOC_IRI = RDFS_NS + "comment"           # @doc
STORAGE_IRI = RDFS_NS + "seeAlso"       # @storage
DB_IRI = RDFS_NS + "isDefinedBy"        # @db
PREDICATE_IRI = RDF_NS + "value"        # name(args) ≝ body
COMMENT_IRI = DLE_NS + "comment"        # leading `#` comment lines
INLINE_COMMENT_IRI = DLE_NS + "inlineComment"  # trailing `#` comment

#: `@ann`-reachable annotation IRIs keyed by the DLe keyword that produces them.
ANNOTATION_IRIS = {
    "label": LABEL_IRI,
    "doc": DOC_IRI,
    "storage": STORAGE_IRI,
    "db": DB_IRI,
}

# ── Datatypes ────────────────────────────────────────────────────────────────

#: Non-`xsd:` CURIEs that nonetheless denote datatypes (RDF 1.2 datatype names).
_RDF_DATATYPE_NAMES = frozenset({
    "rdf:PlainLiteral",
    "rdf:langString",
    "rdf:dirLangString",
    "rdf:HTML",
    "rdf:XMLLiteral",
    "rdf:JSON",
    "rdfs:Literal",
})


def is_datatype_name(name: str) -> bool:
    """Whether a DLe name denotes a datatype rather than a class.

    Mirrors `EntityTypeScanner.isDataTypeName` in the Java implementation: every
    `xsd:` name qualifies, plus a fixed set of RDF/RDFS datatype names.
    """
    return name.startswith("xsd:") or name in _RDF_DATATYPE_NAMES


#: Facet keyword (as written in DLe) → Owlready2 ``ConstrainedDatatype`` kwarg.
FACET_KEYWORDS = {
    "matches": "pattern",
    "pattern": "pattern",
    "xsd:pattern": "pattern",
    "length": "length",
    "xsd:length": "length",
    "minLength": "min_length",
    "min-length": "min_length",
    "xsd:minLength": "min_length",
    "maxLength": "max_length",
    "max-length": "max_length",
    "xsd:maxLength": "max_length",
    "min": "min_inclusive",
    "minInclusive": "min_inclusive",
    "xsd:minInclusive": "min_inclusive",
    "max": "max_inclusive",
    "maxInclusive": "max_inclusive",
    "xsd:maxInclusive": "max_inclusive",
    "minExclusive": "min_exclusive",
    "xsd:minExclusive": "min_exclusive",
    "maxExclusive": "max_exclusive",
    "xsd:maxExclusive": "max_exclusive",
    "totalDigits": "total_digits",
    "xsd:totalDigits": "total_digits",
    "fractionDigits": "fraction_digits",
    "xsd:fractionDigits": "fraction_digits",
}

#: Owlready2 ``ConstrainedDatatype`` kwarg → the DLe keyword used to write it.
FACET_OUTPUT = {
    "pattern": "matches",
    "length": "length",
    "min_length": "minLength",
    "max_length": "maxLength",
    "min_inclusive": "min",
    "max_inclusive": "max",
    "min_exclusive": "minExclusive",
    "max_exclusive": "maxExclusive",
    "total_digits": "totalDigits",
    "fraction_digits": "fractionDigits",
}

#: Facets writable with the compact bracket form, e.g. ``xsd:integer[≥0 ⊓ <10]``.
COMPACT_FACETS = {
    "min_inclusive": "≥",
    "max_inclusive": "≤",
    "min_exclusive": ">",
    "max_exclusive": "<",
}


def java_string_hash(s: str) -> int:
    """Reproduce ``java.lang.String.hashCode()`` as a signed 32-bit int.

    Synthetic class IRIs for multi-role restrictions embed this hash. Computing
    it identically is what makes addle and the Java implementation mint the
    *same* IRI for the same expression, so the two can round-trip a document
    through RDF without the synthetic classes diverging.
    """
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h - 0x100000000 if h >= 0x80000000 else h


def synthetic_class_iri(quantifier: str, expr: str, predicate: str) -> str:
    """IRI for the synthetic class standing in for a multi-role restriction."""
    prefix = "E_" if quantifier == "∃" else "A_"
    return "%s%s%s_%08x" % (
        DLE_NS,
        prefix,
        predicate,
        java_string_hash(expr) & 0xFFFFFFFF,
    )


def split_iri(iri: str) -> tuple[str, str]:
    """Split an IRI into (namespace, local name) at the last ``#`` or ``/``."""
    hash_at = iri.rfind("#")
    slash_at = iri.rfind("/")
    cut = max(hash_at, slash_at)
    if cut < 0:
        return "", iri
    return iri[: cut + 1], iri[cut + 1 :]
