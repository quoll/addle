PYTHON ?= .venv/bin/python
DLE_CHECKOUT ?= ../dle

.PHONY: help venv test lint grammar-check grammar-generate grammar-update clean

help:
	@echo "make venv              create .venv and install addle in editable mode"
	@echo "make test              run the test suite"
	@echo "make lint              report unused imports and undefined names"
	@echo "make grammar-check     verify the vendored grammar has not drifted"
	@echo "                       (set DLE_CHECKOUT to also diff against the Java copy)"
	@echo "make grammar-generate  regenerate the ANTLR parser after a grammar change"
	@echo "make grammar-update    re-record the grammar hash"

venv:
	python3 -m venv .venv
	$(PYTHON) -m pip install -q --upgrade pip
	$(PYTHON) -m pip install -q -e '.[dev]'

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m pyflakes src/addle/*.py tools/*.py tests/*.py

grammar-check:
	@if [ -d "$(DLE_CHECKOUT)" ]; then \
		$(PYTHON) tools/grammar.py check --against "$(DLE_CHECKOUT)"; \
	else \
		$(PYTHON) tools/grammar.py check; \
	fi

grammar-generate:
	$(PYTHON) tools/grammar.py generate

grammar-update:
	$(PYTHON) tools/grammar.py update

clean:
	rm -rf build dist .pytest_cache src/addle.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
