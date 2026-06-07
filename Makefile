.PHONY: test lint format dev clean docs help

# Variables
PYTHON = python3
PIP = pip
TEST_DIR = tests
SRC_DIR = src
DOCS_DIR = docs

# Test target: run pytest
test:
	@echo "Running tests..."
	$(PYTHON) -m pytest $(TEST_DIR) -v

# Lint target: run ruff and mypy
lint:
	@echo "Running linting..."
	$(PYTHON) -m ruff check $(SRC_DIR) $(TEST_DIR)
	$(PYTHON) -m mypy $(SRC_DIR)

# Format target: format code with ruff
format:
	@echo "Formatting code..."
	$(PYTHON) -m ruff format $(SRC_DIR) $(TEST_DIR)

# Dev target: run the development server (using the nexus-server script)
dev:
	@echo "Starting development server..."
	$(PYTHON) -m nexusagent.server

# Clean target: remove generated files
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	rm -f .coverage
	rm -f coverage.xml
	rm -f htmlcov

# Docs target: generate documentation (if using mkdocs or similar, otherwise placeholder)
docs:
	@echo "Generating documentation..."
	# If you have a documentation tool like mkdocs, uncomment and adjust:
	# mkdocs build --site-dir docs/build
	@echo "No documentation generator configured. Add mkdocs or sphinx configuration to generate docs."

# Help target: display available targets
help:
	@echo "Available targets:"
	@echo "  test   - Run tests with pytest"
	@echo "  lint   - Lint code with ruff and mypy"
	@echo "  format - Format code with ruff"
	@echo "  dev    - Start development server"
	@echo "  clean  - Remove generated files"
	@echo "  docs   - Generate documentation"
	@echo "  help   - Show this help message"