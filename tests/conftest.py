import pytest
from owlready2 import World

import addle

DATA = __import__("pathlib").Path(__file__).parent / "data"


@pytest.fixture
def world():
    """A fresh in-memory world per test, so tests cannot leak entities."""
    return World(filename=":memory:")


@pytest.fixture
def parse(world):
    """Parse DLe text into an ontology in this test's world."""

    def _parse(text, **kwargs):
        return addle.loads(text, world=world, **kwargs)

    return _parse


@pytest.fixture
def render():
    """Render an ontology without the boilerplate header."""

    def _render(onto, **kwargs):
        return addle.dumps(onto, include_header=False, **kwargs)

    return _render


@pytest.fixture
def statements(render):
    """Rendered logical statements only: no comments, prefixes or blank lines."""

    def _statements(onto):
        out = []
        for line in render(onto).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("@prefix"):
                continue
            if line.startswith("@ontology") or line.startswith("@version"):
                continue
            out.append(line)
        return out

    return _statements


@pytest.fixture(scope="session")
def reference_document():
    return (DATA / "wildlife-reserve-test.dle").read_text(encoding="utf-8")
