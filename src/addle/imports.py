"""Where an ``@import`` reference points.

Both forms are accepted — ``@import <ref>`` and ``@import "ref"`` — and they
answer different questions. The bracketed form is an IRI reference and is
resolved as one. The quoted form exists because a relative path is the natural
way to name a file beside this one and cannot be carried as an IRI: under RFC
3986 a scheme must be followed by a slash for the path to be hierarchical, so
``file:x.dle`` is opaque, has no path, and cannot be opened.

A relative reference in either form resolves against the document that declared
it, which is the only base that means anything. Handed over as written it names
nothing, and an import that resolves to nothing is not merely a few missing
axioms: what an import declares decides kinds here, so losing one changes how
the importing document reads.

Mirrors ``resolveIriImport`` and ``resolveQuotedImport`` in the Java reference
implementation. The resolved text can differ from Java's in one harmless way:
``urljoin`` writes ``file:///dir/x`` where Java writes ``file:/dir/x``. They
name the same file, and neither reaches a document — an import that resolves
against a file is written back in its relative form.
"""

import os
import re
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import url2pathname

#: Schemes that can actually be retrieved.
#:
#: Deliberately short. A quoted reference carrying any other scheme is far more
#: likely to be a file whose name happens to contain a colon than an ontology
#: anyone can fetch: ``urn:`` and ``mailto:`` say nothing about where to look.
#: Anything unretrievable is read as a path, and ``@import <iri>`` remains the
#: way to name an IRI of any scheme.
RETRIEVABLE_SCHEMES = frozenset({"http", "https", "file"})

#: A Windows path: a drive letter, a colon, then a separator.
_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def first_segment_has_colon(path):
    """Whether the part before the first slash contains a colon."""
    return ":" in path.split("/", 1)[0]


def _scheme(text):
    """The scheme of a reference, or ``None`` if it is relative.

    A bare Windows path is not a scheme, whatever ``urlsplit`` makes of the
    drive letter.
    """
    if _WINDOWS_PATH.match(text):
        return None
    scheme = urlsplit(text).scheme
    return scheme or None


def _resolvable_base(base):
    """``base`` if it is something a relative reference can resolve against.

    A document read from a string or a stream has no location, and one with an
    opaque IRI has no path to be relative to. Leaving the reference alone is
    more use than resolving it against something arbitrary.
    """
    if not base:
        return None
    parts = urlsplit(base)
    if not parts.scheme or not parts.path.startswith("/"):
        return None
    return base


def resolve_iri_import(base, ref):
    """``@import <ref>``: a relative reference against the document, else as written.

    An absolute IRI is the escape hatch and is never touched — it may name a
    scheme only a catalogue can retrieve. The text inside the brackets is an IRI
    reference already, so unlike the quoted form it is not percent-encoded on
    the way through; ``<a%20b.dle>`` names the file ``a b.dle``.
    """
    if _scheme(ref) is not None:
        return ref
    resolvable = _resolvable_base(base)
    if resolvable is None:
        return ref
    return urljoin(resolvable, ref)


def resolve_quoted_import(base, ref):
    """``@import "ref"``: an IRI if it carries a retrievable scheme, else a path.

    A path is taken *literally* — nothing is decoded — so a file really named
    ``a%20b.dle``, or one containing ``#`` or ``?``, names itself rather than
    something else. Reading it literally means percent-*encoding* it to build
    the IRI, which is what lets the writer hand back the same spelling.
    """
    scheme = _scheme(ref)
    if scheme is not None and scheme.lower() in RETRIEVABLE_SCHEMES:
        return ref
    return _resolve_file_path(base, ref)


#: The characters RFC 3986 allows unescaped in a path segment, beyond the
#: unreserved set ``quote`` already leaves alone. Spelled out so the encoding
#: matches the reference implementation character for character: Java's URI
#: constructor escapes exactly what is not a pchar, and a resolved import IRI
#: that differs only in its escaping still compares unequal.
_PCHAR_SAFE = "/:@!$&'()*+,;="


def _resolve_file_path(base, path):
    if _WINDOWS_PATH.match(path):
        return "file:///" + quote(path.replace("\\", "/"), safe=_PCHAR_SAFE)
    # A colon survives the encoding, so a first segment containing one would
    # read back as a scheme. `./` is what keeps it a path.
    safe = "./" + path if first_segment_has_colon(path) else path
    relative = quote(safe, safe=_PCHAR_SAFE)
    resolvable = _resolvable_base(base)
    if resolvable is None:
        return relative
    return urljoin(resolvable, relative)


def relative_import_ref(location, import_iri):
    """How to write ``import_iri`` in a document stored at ``location``.

    The inverse of :func:`resolve_quoted_import`: a file beside the document is
    written as the relative path it came in as, quoted, and anything else as the
    absolute IRI. Returns the text including its brackets or quotes.

    The path is decoded, because a quoted reference is a literal file name —
    writing ``my%20vocab.dle`` for a file named ``my vocab.dle`` would be legal
    and reloadable but not the spelling it arrived in, which is the point of
    keeping the relative form at all.
    """
    if location and urlsplit(location).scheme == "file" \
            and urlsplit(import_iri).scheme == "file":
        directory = PurePosixPath(urlsplit(location).path).parent
        target = PurePosixPath(urlsplit(import_iri).path)
        try:
            relative = target.relative_to(directory)
        except ValueError:
            return "<%s>" % import_iri
        path = unquote(str(relative))
        if path and path != ".":
            # The `./` is for the one character the encoding leaves alone on the
            # way back: a colon in the first segment would read as a scheme.
            if first_segment_has_colon(path):
                path = "./" + path
            return '"%s"' % path.replace("\\", "\\\\").replace('"', '\\"')
    return "<%s>" % import_iri


def document_iri(source):
    """The IRI of the document being read, from whatever ``source`` names.

    ``load`` is given a path and ``loads`` a name for error messages, so this
    accepts either. Anything that is already absolute is left alone; anything
    that is not an existing-looking path yields ``None``, since resolving
    against a guess is worse than not resolving.
    """
    if not source:
        return None
    try:
        text = os.fspath(source)
    except TypeError:
        return None
    # A Path is the common case from `load` and `dump`, and it is never an IRI.
    if not isinstance(source, (str, bytes)):
        text = str(text)
    elif _scheme(text) is not None:
        return text
    try:
        return Path(text).resolve().as_uri()
    except (ValueError, OSError, TypeError):
        return None


# ── what an import declares ─────────────────────────────────────────────────
#
# Kinds here are inferred from how a name is used, and the filler of a
# restriction is what says whether its property is an object or a data
# property. A name the reader does not know is a class, so `⊤ ⊑ ∀live.gl:date`
# made `live` an object property — and the document then went wrong somewhere
# else entirely, on a sub-property axiom hundreds of lines away. The
# declaration was there; it was in the imported document. So imports are read
# before the kinds are settled rather than after.


def declared_datatypes(iris, warn=None, _seen=None):
    """The datatype IRIs declared by the documents ``iris`` names.

    Follows imports transitively, as the reference implementation does by
    asking for the imports closure. Anything that cannot be read contributes
    nothing and is reported through ``warn``: a document is still readable
    without its import, only less well informed, and refusing to parse would
    be a worse answer than parsing with a caveat.

    Only ``file:`` targets are read. A remote import is not fetched — a parser
    that reaches the network is a surprise and a place to hang — so it takes
    the same warning as one that could not be read, which is what it is.
    """
    seen = set() if _seen is None else _seen
    found = set()
    for iri in iris:
        if iri in seen:
            continue
        seen.add(iri)
        text = _read_document(iri, warn)
        if text is None:
            continue
        nested, datatypes = _datatypes_in(text, iri)
        found |= datatypes
        found |= declared_datatypes(nested, warn, seen)
    return found


def _read_document(iri, warn):
    scheme = urlsplit(iri).scheme
    if not scheme:
        # Still relative, so resolution found no base: the document was read
        # from a string or a stream and has no location of its own.
        _warn(warn, iri, "the document has no location to resolve it against")
        return None
    if scheme != "file":
        _warn(warn, iri, "it is not a local file, and imports are not fetched")
        return None
    try:
        return Path(url2pathname(urlsplit(iri).path)).read_text(encoding="utf-8")
    except OSError as problem:
        _warn(warn, iri, problem.strerror or str(problem))
        return None
    except UnicodeDecodeError:
        _warn(warn, iri, "it is not UTF-8 text")
        return None


def _warn(warn, iri, why):
    if warn is None:
        return
    # What the reader needs is not that an import failed but that the failure
    # can have changed the document's meaning, because the place it then goes
    # wrong is rarely near the import.
    warn("could not read import <%s>: %s. Names it declares are unknown here, "
         "so kinds inferred from them may be wrong" % (iri, why))


def _datatypes_in(text, iri):
    """``(imports, datatype IRIs)`` of one document, read for its declarations only.

    A full parse, because a datatype declaration is an ordinary subsumption and
    only the grammar can tell one from a class axiom. Nothing is built from it:
    the importing document wants the names, not the axioms.
    """
    from ._tree import parse_text
    from ._antlr.DLESyntaxParser import DLESyntaxParser as P

    try:
        tree, _tokens, _problems = parse_text(text, source=iri)
    except Exception:
        # A broken import is a missing import; the document that declares it is
        # not the place to report someone else's syntax error.
        return (), set()

    prefixes = _prefixes_of(tree)
    datatypes = set()
    for statement in tree.statement():
        axiom = statement.getChild(0)
        if not isinstance(axiom, P.SubClassAxiomContext):
            continue
        if axiom.getChild(2).getText() != "rdfs:Literal":
            continue
        name = axiom.getChild(0).getText()
        expanded = _expand_with(prefixes, name)
        if expanded is not None:
            datatypes.add(expanded)

    imports = []
    for decl in tree.importDecl():
        target = _import_target(prefixes, iri, decl)
        if target is not None:
            imports.append(target)
    return imports, datatypes


def _prefixes_of(tree):
    from .vocab import IMPLICIT_PREFIXES, WELL_KNOWN_PREFIXES

    prefixes = dict(WELL_KNOWN_PREFIXES)
    prefixes.update(IMPLICIT_PREFIXES)
    for decl in tree.prefixDecl():
        text = decl.IRI()
        value = text.getText()[1:-1] if text is not None else decl.STRING().getText()[1:-1]
        prefixes[decl.PNAME_NS().getText()[:-1]] = value
    return prefixes


def _expand_with(prefixes, name):
    """``name`` as an absolute IRI, or ``None`` if its prefix is not declared."""
    if name.startswith("<") and name.endswith(">"):
        return name[1:-1]
    if ":" in name:
        prefix, _, local = name.partition(":")
        namespace = prefixes.get(prefix)
        return None if namespace is None else namespace + local
    return prefixes.get("", "") + name


def _import_target(prefixes, base, decl):
    text = decl.STRING()
    if text is not None:
        return resolve_quoted_import(base, text.getText()[1:-1])
    ref = decl.iriRef()
    if ref.IRI() is None:
        return _expand_with(prefixes, ref.name().getText())
    return resolve_iri_import(base, ref.IRI().getText()[1:-1])
