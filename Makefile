.PHONY: test lint format dev clean docs help typecheck security check all sbom docker-lint security-scan install

PYTHON = python3
TEST_DIR = tests
SRC_DIR = src

all: lint typecheck test security

	@echo "All checks passed!"

install:
	@echo "Installing dependencies..."
	pip install -e ".[dev]"

test:
	@echo "Running tests..."
	$(PYTHON) -m pytest $(TEST_DIR) -v --tb=short

test-cov:
	@echo "Running tests with coverage..."
	$(PYTHON) -m pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing --cov-report=html

lint:
	@echo "Running ruff lint..."
	$(PYTHON) -m ruff check $(SRC_DIR) $(TEST_DIR)

lint-fix:
	@echo "Running ruff lint with auto-fix..."
	$(PYTHON) -m ruff check $(SRC_DIR) $(TEST_DIR) --fix

format:
	@echo "Formatting code..."
	$(PYTHON) -m ruff format $(SRC_DIR) $(TEST_DIR)

typecheck:
	@echo "Running mypy..."
	$(PYTHON) -m mypy $(SRC_DIR)

basedpyright:
	@echo "Running basedpyright..."
	$(PYTHON) -m basedpyright $(SRC_DIR)

interrogate:
	@echo "Running interrogate..."
	$(PYTHON) -m interrogate $(SRC_DIR)

pydocstyle:
	@echo "Running pydocstyle..."
	$(PYTHON) -m pydocstyle $(SRC_DIR)

security:
	@echo "Running security checks..."
	$(PYTHON) -m ruff check $(SRC_DIR) --select=S,B

security-scan:
	@echo "Running security scan..."
	$(PYTHON) -m pip_audit --format=json --output=pip-audit.json || true
	$(PYTHON) -m gitleaks detect --source=. --verbose --report-format=json --report-path=gitleaks.json || true

docker-lint:
	@echo "Linting Dockerfile..."
	docker run --rm -i hadolint/hadolint < Dockerfile

sbom:
	@echo "Generating SBOM..."
	$(PYTHON) -m cyclonedx_py environment --output-format json --output-file sbom.json
	@echo "SBOM generated: sbom.json"

check: lint typecheck
	@echo "Checking formatting..."
	$(PYTHON) -m ruff format --check $(SRC_DIR) $(TEST_DIR)

dev:
	@echo "Starting development server..."
	$(PYTHON) -m nexusagent.server

docs:
	@echo "Serving documentation..."
	$(PYTHON) -m mkdocs serve

docs-build:
	@echo "Building documentation..."
	$(PYTHON) -m mkdocs build

clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	rm -f .coverage coverage.xml
	rm -f sbom.json pip-audit.json gitleaks.json

help:
	@echo "Targets:"
	@echo "  all            - Run all checks (lint, typecheck, test, security)"
	@echo "  install        - Install dependencies"
	@echo "  test           - Run tests"
	@echo "  test-cov       - Tests with coverage"
	@echo "  lint           - Lint code"
	@echo "  lint-fix       - Lint and auto-fix"
	@echo "  format         - Format code"
	@echo "  typecheck      - Type check (mypy)"
	@echo "  basedpyright   - Type check (basedpyright)"
	@echo "  interrogate    - Docstring coverage check"
	@echo "  pydocstyle     - Docstring style check"
	@echo "  security       - Security scan (ruff S,B)"
	@echo "  security-scan  - Full security scan (pip-audit, gitleaks)"
	@echo "  docker-lint    - Lint Dockerfile (hadolint)"
	@echo "  sbom           - Generate SBOM (cyclonedx-py)"
	@echo "  check          - Combined check (lint + typecheck)"
	@echo "  dev            - Start dev server"
	@echo "  docs           - Serve docs locally"
	@echo "  docs-build     - Build docs"
	@echo "  clean          - Remove generated files"
	@echo "  help           - Show help"