PROJECTS := momentum_research option_selling factor_regime_rotation nifty500-ml-factors stat_arb
PYTHON ?= python

.PHONY: install test lint format charts

install:  ## install every project (editable) with its dev tools
	for p in $(PROJECTS); do $(PYTHON) -m pip install -e "$$p[dev]" || exit 1; done

test:  ## run each project's tests (no data needed)
	for p in $(PROJECTS); do (cd $$p && $(PYTHON) -m pytest -q) || exit 1; done

lint:  ## ruff check and format check, per project
	for p in $(PROJECTS); do (cd $$p && ruff check . && ruff format --check .) || exit 1; done

format:
	for p in $(PROJECTS); do (cd $$p && ruff format . && ruff check --fix .) || exit 1; done

charts:  ## redraw the README charts from the committed result files
	$(PYTHON) tools/readme_charts.py
