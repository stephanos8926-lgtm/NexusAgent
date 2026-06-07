.PHONY: test lint format dev clean docs help typecheck security check all

PYTHON = python3
TEST_DIR = tests
SRC_DIR = src

all: lint typecheck test security
	@echo "All checks passed!"

test:
	@echo "Running tests..."
	$(PYTHON) -m pytest $(TEST_DIR) -v --tb=short

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

check: lint typecheck
	@echo "Checking formatting..."
	$(PYTHON) -m ruff format --check $(SRC_DIR) $(TEST_DIR)

dev:
	@echo "Starting development server..."
	$(PYTHON) -m nexusagent.server

clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -f .coverage coverage.xml

docs:
	@echo "No documentation generator configured."

help:
	@echo "Available targets:"
	@echo "  all         - Run all checks"
	@echo "  test        - Run tests"
	@echo "  lint        - Lint code"
	@echo "  lint-fix    - Lint and auto-fix"
	@echo "  format      - Format code"
	@echo "  typecheck   - Type check"
	@echo "  check       - Combined check"
	@echo "  dev         - Start dev server"
	@echo "  clean       - Remove generated files"
	@echo "  docs        - Generate docs"
	@echo "  help        - Show help"
