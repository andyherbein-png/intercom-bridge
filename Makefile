PYTHON  := venv/bin/python
PIP     := venv/bin/pip
PYTEST  := venv/bin/pytest
RUFF    := venv/bin/ruff

.PHONY: all install test lint run emulate clean

all: install

## Set up virtual environment and install all dependencies (including dev tools).
install:
	python3 -m venv venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

## Run the test suite with pytest.
test:
	$(PYTEST) tests/ -v

## Lint source and tests with ruff.
lint:
	$(RUFF) check src/ tests/

## Launch the main application.
run:
	$(PYTHON) -m src.main

## Launch in macOS emulation mode — no real hardware required.
## BlueZ D-Bus, PipeWire, and GPIO are all stubbed out.
## Emulation control API available at http://localhost:5000/api/emulation/*
emulate: venv
	EMULATION_MODE=1 MINIHOP_CONFIG=/tmp/minihop-emulate/config.json \
	    $(PYTHON) -m src.main

## Remove the venv and all generated artefacts.
clean:
	rm -rf venv .pytest_cache .ruff_cache
	find . -path ./venv -prune -o -name "*.pyc" -print -o \
	    -type d -name "__pycache__" -print | xargs rm -rf
