.PHONY: validate api-venv sdk-venv web-install lint typecheck test \
        modularity-check forbidden-filenames-check link-check \
        dependency-boundary-check circular-import-check secret-scan \
        up down test-services-up test-services-down

ROOT := $(CURDIR)
API_DIR := services/api
SDK_DIR := packages/evalforge-sdk
WEB_DIR := apps/web
VENV_BIN := $(ROOT)/$(API_DIR)/.venv/bin
SDK_VENV_BIN := $(ROOT)/$(SDK_DIR)/.venv/bin
PYTHON := python3

$(VENV_BIN)/python:
	$(PYTHON) -m venv $(API_DIR)/.venv
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -e "$(API_DIR)[dev]"

api-venv: $(VENV_BIN)/python

$(SDK_VENV_BIN)/python:
	$(PYTHON) -m venv $(SDK_DIR)/.venv
	$(SDK_VENV_BIN)/pip install --upgrade pip
	$(SDK_VENV_BIN)/pip install -e "$(SDK_DIR)[dev]"

sdk-venv: $(SDK_VENV_BIN)/python

web-install:
	cd $(WEB_DIR) && npm install

lint: api-venv sdk-venv web-install
	$(VENV_BIN)/ruff check $(API_DIR)/src $(API_DIR)/tests $(API_DIR)/alembic
	$(VENV_BIN)/ruff format --check $(API_DIR)/src $(API_DIR)/tests $(API_DIR)/alembic
	$(SDK_VENV_BIN)/ruff check $(SDK_DIR)/src $(SDK_DIR)/tests
	$(SDK_VENV_BIN)/ruff format --check $(SDK_DIR)/src $(SDK_DIR)/tests
	cd $(WEB_DIR) && npm run lint
	cd $(WEB_DIR) && npm run format:check

typecheck: api-venv sdk-venv web-install
	cd $(API_DIR) && $(VENV_BIN)/mypy src
	cd $(SDK_DIR) && $(SDK_VENV_BIN)/mypy src
	cd $(WEB_DIR) && npm run typecheck

test-services-up:
	cd infrastructure && docker compose -f docker-compose.test.yml up -d --wait postgres-test object-storage-test
	cd infrastructure && docker compose -f docker-compose.test.yml run --rm object-storage-test-init

test-services-down:
	cd infrastructure && docker compose -f docker-compose.test.yml down

test: api-venv sdk-venv web-install test-services-up
	cd $(API_DIR) && $(VENV_BIN)/pytest
	cd $(SDK_DIR) && $(SDK_VENV_BIN)/pytest
	cd $(WEB_DIR) && npm test

modularity-check:
	$(PYTHON) scripts/validate_modularity.py

forbidden-filenames-check:
	$(PYTHON) scripts/validate_forbidden_filenames.py

link-check:
	$(PYTHON) scripts/validate_markdown_links.py

dependency-boundary-check:
	$(PYTHON) scripts/validate_dependency_boundaries.py

circular-import-check:
	$(PYTHON) scripts/validate_circular_imports.py

secret-scan:
	$(PYTHON) scripts/validate_no_secrets.py

validate: lint typecheck test modularity-check forbidden-filenames-check \
          link-check dependency-boundary-check circular-import-check secret-scan
	@echo "All validation checks passed."

up:
	cd infrastructure && docker compose up --build -d

down:
	cd infrastructure && docker compose down -v
