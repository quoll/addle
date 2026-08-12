#!/usr/bin/env python3
"""Manage the vendored copy of the DLe grammar.

`grammar/DLESyntax.g4` is a copy of the grammar in the Java reference
implementation (github.com/quoll/DLe). The two must stay identical: they define
the same language, and a divergence would silently make documents written by one
implementation unreadable by the other.

Rather than sharing the file through a submodule — infrastructure paid for on
every clone, for a file that changes about once a year — the copy is checked
against a recorded hash. Drift then becomes impossible to *miss* rather than
impossible to happen.

    tools/grammar.py check              verify the copy matches grammar/DLESyntax.g4.sha256
    tools/grammar.py check --against P  also compare against the Java copy at path P
    tools/grammar.py update             re-record the hash after an intentional change
    tools/grammar.py generate           regenerate src/addle/_antlr from the grammar
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAMMAR = ROOT / "grammar" / "DLESyntax.g4"
CHECKSUM = ROOT / "grammar" / "DLESyntax.g4.sha256"
GENERATED = ROOT / "src" / "addle" / "_antlr"

#: Must match the antlr4-python3-runtime pin in pyproject.toml. ANTLR's
#: generated code and its runtime are only compatible within a minor version.
ANTLR_VERSION = "4.13.1"

#: Where the Java implementation keeps the same file, relative to a DLe checkout.
JAVA_GRAMMAR_PATH = (
    "parsers/src/main/antlr4/org/semanticweb/owlapi/dlesyntax/DLESyntax.g4"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_check(args):
    actual = digest(GRAMMAR)
    status = 0

    if CHECKSUM.exists():
        expected = CHECKSUM.read_text().split()[0]
        if actual != expected:
            print(
                "grammar/DLESyntax.g4 has changed but its hash has not.\n"
                "  recorded: %s\n  actual:   %s\n"
                "If the change is intentional, regenerate the parser and re-record:\n"
                "  tools/grammar.py generate && tools/grammar.py update" % (expected, actual),
                file=sys.stderr,
            )
            status = 1
    else:
        print("no recorded hash; run tools/grammar.py update", file=sys.stderr)
        status = 1

    if args.against:
        other = Path(args.against)
        if other.is_dir():
            other = other / JAVA_GRAMMAR_PATH
        if not other.exists():
            print("cannot compare: %s does not exist" % other, file=sys.stderr)
            return 1
        if digest(other) != actual:
            print(
                "grammar has diverged from the reference implementation:\n  %s\n"
                "The two must define the same language. Reconcile them before releasing."
                % other,
                file=sys.stderr,
            )
            status = 1
        else:
            print("grammar matches %s" % other)

    if status == 0:
        print("grammar hash OK (%s)" % actual[:16])
    return status


def cmd_update(args):
    actual = digest(GRAMMAR)
    CHECKSUM.write_text("%s  DLESyntax.g4\n" % actual)
    print("recorded %s" % actual)
    return 0


def _antlr_command():
    """An ANTLR invocation, preferring a complete jar, falling back to Maven's."""
    jar = os.environ.get("ANTLR_JAR")
    if jar:
        return ["java", "-jar", jar]

    home = Path.home()
    complete = home / ".m2" / "repository" / "org" / "antlr" / "antlr4"
    tool = complete / ANTLR_VERSION / ("antlr4-%s.jar" % ANTLR_VERSION)
    if not tool.exists():
        return None

    # The Maven artifact is not shaded, so its dependencies must be on the
    # classpath explicitly.
    def version_key(path):
        # Compare version components numerically. Sorting the strings instead
        # would rank 4.9.3 above 4.13.1 and silently generate code against the
        # wrong runtime — the ATN then fails to deserialise at import time.
        parts = path.parent.name.split("-")[0].split(".")
        return tuple(int(p) if p.isdigit() else -1 for p in parts)

    def newest(group, artifact):
        base = home / ".m2" / "repository" / Path(group.replace(".", "/")) / artifact
        jars = [
            jar
            for jar in base.glob("*/%s-*.jar" % artifact)
            if not jar.name.endswith(("-sources.jar", "-javadoc.jar"))
        ]
        return max(jars, key=version_key) if jars else None

    def exact(group, artifact, version):
        path = (
            home / ".m2" / "repository" / Path(group.replace(".", "/")) / artifact
            / version / ("%s-%s.jar" % (artifact, version))
        )
        return path if path.exists() else None

    deps = [
        tool,
        # Must be the tool's own version: the runtime on the classpath is what
        # serialises the ATN embedded in the generated code.
        exact("org.antlr", "antlr4-runtime", ANTLR_VERSION),
        newest("org.antlr", "antlr-runtime"),
        newest("org.antlr", "ST4"),
        newest("org.glassfish", "javax.json"),
        newest("com.ibm.icu", "icu4j"),
        newest("org.abego.treelayout", "org.abego.treelayout.core"),
    ]
    missing = [name for name, jar in zip(
        ["antlr4", "antlr4-runtime", "antlr-runtime", "ST4", "javax.json", "icu4j",
         "treelayout"], deps) if jar is None]
    if missing:
        print("missing ANTLR dependencies in ~/.m2: %s" % ", ".join(missing), file=sys.stderr)
        return None
    return ["java", "-cp", ":".join(str(d) for d in deps), "org.antlr.v4.Tool"]


def cmd_generate(args):
    command = _antlr_command()
    if command is None:
        print(
            "Could not find the ANTLR %s tool.\n"
            "Set ANTLR_JAR to an antlr-%s-complete.jar, or install it via Maven.\n"
            "Generated sources are checked in, so this is only needed after a "
            "grammar change." % (ANTLR_VERSION, ANTLR_VERSION),
            file=sys.stderr,
        )
        return 1

    staging = ROOT / "build" / "antlr"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    result = subprocess.run(
        command
        + [
            "-Dlanguage=Python3",
            "-visitor",
            "-no-listener",
            "-o",
            str(staging),
            str(GRAMMAR),
        ],
        cwd=ROOT,
    )
    if result.returncode != 0:
        return result.returncode

    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / "__init__.py").write_text(
        '"""ANTLR-generated lexer, parser and visitor for the DLe grammar.\n\n'
        "Do not edit: regenerate with ``tools/grammar.py generate``.\n"
        '"""\n'
    )
    produced = []
    for path in sorted(staging.rglob("*")):
        if path.suffix in {".py", ".interp", ".tokens"}:
            shutil.copy(path, GENERATED / path.name)
            produced.append(path.name)
    shutil.rmtree(ROOT / "build")

    print("generated %d files into %s" % (len(produced), GENERATED.relative_to(ROOT)))
    print("remember: tools/grammar.py update")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="verify the vendored grammar has not drifted")
    check.add_argument(
        "--against",
        metavar="PATH",
        help="a DLe checkout, or a path to its DLESyntax.g4, to compare against",
    )
    check.set_defaults(func=cmd_check)

    update = sub.add_parser("update", help="re-record the grammar hash")
    update.set_defaults(func=cmd_update)

    generate = sub.add_parser("generate", help="regenerate the ANTLR parser")
    generate.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
