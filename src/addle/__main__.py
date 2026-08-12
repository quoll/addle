"""Command line entry point: ``addle`` / ``python -m addle``.

Converts between DLe and the RDF serialisations Owlready2 can read and write.
"""

import argparse
import sys

from owlready2 import World

from . import __version__, dumps, loads
from .errors import DleError

#: Output format aliases → the name Owlready2 uses, or None for DLe.
FORMATS = {
    "dle": None,
    "rdfxml": "rdfxml",
    "owl": "rdfxml",
    "xml": "rdfxml",
    "ntriples": "ntriples",
    "nt": "ntriples",
}

_SUFFIX_FORMATS = {
    ".dle": "dle",
    ".owl": "rdfxml",
    ".rdf": "rdfxml",
    ".xml": "rdfxml",
    ".nt": "ntriples",
    ".ntriples": "ntriples",
}


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="addle",
        description="Convert between DLe and RDF serialisations of an ontology.",
    )
    parser.add_argument("input", help="input file; use - for stdin (DLe only)")
    parser.add_argument(
        "output", nargs="?", help="output file; defaults to stdout"
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=sorted(FORMATS),
        help="output format; inferred from the output file name, else dle",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="omit the explanatory header when writing DLe",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="do not report warnings"
    )
    parser.add_argument("--version", action="version", version="addle " + __version__)
    return parser


def _infer_format(args):
    if args.format:
        return args.format
    if args.output:
        for suffix, name in _SUFFIX_FORMATS.items():
            if args.output.endswith(suffix):
                return name
    return "dle"


def _read_ontology(args, world, warnings):
    """Load the input as DLe if it looks like DLe, otherwise let Owlready2 try."""
    if args.input == "-":
        return loads(sys.stdin.read(), world=world, source="<stdin>", warnings=warnings)
    if args.input.endswith(".dle"):
        with open(args.input, encoding="utf-8") as handle:
            return loads(handle.read(), world=world, source=args.input, warnings=warnings)
    return world.get_ontology(args.input).load()


def main(argv=None):
    args = _build_parser().parse_args(argv)
    warnings = []
    world = World(filename=":memory:")

    try:
        onto = _read_ontology(args, world, warnings)
    except DleError as error:
        print(error, file=sys.stderr)
        return 1
    except OSError as error:
        print("addle: %s" % error, file=sys.stderr)
        return 1

    target = _infer_format(args)
    owlready_format = FORMATS[target]

    if owlready_format is None:
        text = dumps(onto, include_header=not args.no_header, warnings=warnings)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(text)
        else:
            sys.stdout.write(text)
    elif args.output:
        onto.save(file=args.output, format=owlready_format)
    else:
        # Owlready2 writes bytes, so go through the raw stdout buffer.
        onto.save(file=sys.stdout.buffer, format=owlready_format)

    if warnings and not args.quiet:
        for warning in dict.fromkeys(warnings):
            print("addle: warning: %s" % warning, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
