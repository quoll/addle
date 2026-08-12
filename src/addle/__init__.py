"""addle — a DLe parser and writer for Owlready2.

DLe (Description Logic, Extended) is a compact formal syntax for ontologies that
is readable by both people and language models. This package reads DLe documents
into an Owlready2 ontology and writes an Owlready2 ontology back out as DLe.

    >>> import addle
    >>> onto = addle.loads("Animal ⊑ ⊤\\n@doc Animal \\"An animal.\\"\\n")
    >>> print(addle.dumps(onto, include_header=False))

The syntax is documented at https://github.com/quoll/DLe/wiki. The reference
implementation is the Java library `io.github.quoll.owlapi:dlextended-parsers`,
which builds on the OWL API; addle shares its grammar and its encoding of
constructs that OWL has no vocabulary for.
"""

from .errors import DleError, DleSemanticError, DleSyntaxError
from .reader import Reader
from .writer import Writer, header_text

__all__ = [
    "DleError",
    "DleSemanticError",
    "DleSyntaxError",
    "Reader",
    "Writer",
    "dump",
    "dumps",
    "header_text",
    "load",
    "loads",
    "__version__",
]

__version__ = "0.1.0"


def loads(text, world=None, onto=None, base_iri=None, source=None, warnings=None):
    """Parse DLe text and return the Owlready2 ontology it describes.

    Args:
        text: the DLe document.
        world: the Owlready2 ``World`` to build in; defaults to ``default_world``.
        onto: an existing ontology to add to, instead of creating one.
        base_iri: base IRI for the new ontology. Defaults to the document's
            ``@ontology`` declaration, then its default (``:``) prefix.
        source: a name for the document, used in error messages.
        warnings: optional list, extended with any non-fatal problems found.

    Raises:
        DleSyntaxError: if the document does not parse.
    """
    from ._tree import parse_text

    tree, tokens, _ = parse_text(text, source=source)
    reader = Reader(world=world, onto=onto, base_iri=base_iri)
    result = reader.read(tree, tokens)
    if warnings is not None:
        warnings.extend(reader.warnings)
    return result


def load(file, world=None, onto=None, base_iri=None, warnings=None):
    """Parse a DLe document from a path or open text file.

    Accepts anything with a ``read`` method, or a path (``str`` or
    ``os.PathLike``) which is read as UTF-8.
    """
    if hasattr(file, "read"):
        text = file.read()
        source = getattr(file, "name", None)
    else:
        with open(file, encoding="utf-8") as handle:
            text = handle.read()
        source = str(file)
    return loads(
        text, world=world, onto=onto, base_iri=base_iri, source=source, warnings=warnings
    )


def dumps(onto, prefixes=None, include_header=True, warnings=None):
    """Render an Owlready2 ontology as DLe text.

    Args:
        onto: the ontology to render.
        prefixes: extra ``{prefix: namespace}`` entries to use when shortening
            IRIs. The six DLe prefixes are always available.
        include_header: whether to emit the standard explanatory file header.
        warnings: optional list, extended with anything that could not be
            rendered faithfully.
    """
    writer = Writer(onto, prefixes=prefixes, include_header=include_header)
    text = writer.render()
    if warnings is not None:
        warnings.extend(writer.warnings)
    return text


def dump(onto, file, prefixes=None, include_header=True, warnings=None):
    """Write an Owlready2 ontology as DLe to a path or open text file."""
    text = dumps(onto, prefixes=prefixes, include_header=include_header, warnings=warnings)
    if hasattr(file, "write"):
        file.write(text)
        return
    with open(file, "w", encoding="utf-8") as handle:
        handle.write(text)
