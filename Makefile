PKG := deltacycle
PYTEST := pytest
UV := uv

.PHONY: help
help:
	@echo Usage: make [options] [target] ...
	@echo Valid targets:
	@echo     test  - PyTest
	@echo     prof  - PyTest with profile report
	@echo     cov   - PyTest with HTML coverage report

.PHONY: test
test:
	@$(PYTEST) --doctest-modules

.PHONY: test_all
test_all:
	@$(UV) run --python=3.12 pytest --doctest-modules
	@$(UV) run --python=3.13 pytest --doctest-modules
	@$(UV) run --python=3.14 pytest --doctest-modules

.PHONY: prof
prof:
	@$(PYTEST) --doctest-modules --profile

.PHONY: cov
cov:
	@$(PYTEST) --doctest-modules --cov=src/$(PKG) --cov-branch --cov-report=html
