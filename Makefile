.PHONY: help check-python install test test-cov lint lint-fix format format-check typecheck qa clean dev setup-hooks

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# Python version check
PYTHON_VERSION := $(shell python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
REQUIRED_MAJOR := 3
REQUIRED_MINOR := 10

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "$(BLUE)CDD Agent - Development Commands$(NC)"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

check-python: ## Check Python version (3.10+ required)
	@printf "Checking Python version... "
	@python -c "import sys; sys.exit(0 if sys.version_info >= ($(REQUIRED_MAJOR), $(REQUIRED_MINOR)) else 1)" \
		&& echo "$(GREEN)✓ Python $(PYTHON_VERSION)$(NC)" \
		|| (echo "$(RED)✗ Python $(PYTHON_VERSION) (3.10+ required)$(NC)" && \
		    echo "$(YELLOW)Install with: pyenv install 3.10.13 && pyenv local 3.10.13$(NC)" && exit 1)

install: check-python ## Install dependencies with Poetry
	@echo "$(BLUE)Installing dependencies...$(NC)"
	poetry install
	@echo "$(GREEN)✓ Dependencies installed$(NC)"
	@$(MAKE) setup-hooks

test: check-python ## Run test suite
	@echo "$(BLUE)Running tests...$(NC)"
	poetry run pytest

test-cov: check-python ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	poetry run pytest --cov=cdd_agent --cov-report=term-missing

lint: check-python ## Run linters (ruff)
	@echo "$(BLUE)Running linters...$(NC)"
	poetry run ruff check src/ tests/

lint-fix: check-python ## Run linters and auto-fix issues
	@echo "$(BLUE)Running linters with auto-fix...$(NC)"
	poetry run ruff check --fix src/ tests/

format: check-python ## Format code with ruff
	@echo "$(BLUE)Formatting code...$(NC)"
	poetry run ruff format src/ tests/
	@echo "$(GREEN)✓ Code formatted$(NC)"

format-check: check-python ## Check code formatting without changes
	@echo "$(BLUE)Checking code formatting...$(NC)"
	poetry run ruff format --check src/ tests/

typecheck: check-python ## Run type checker (mypy)
	@echo "$(BLUE)Running type checker...$(NC)"
	poetry run mypy src/

qa: check-python format-check lint typecheck test ## Run all quality checks (format, lint, typecheck, test)
	@echo "$(GREEN)✓ All quality checks passed!$(NC)"

clean: ## Clean up cache files and build artifacts
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf dist/ build/ .coverage htmlcov/
	@echo "$(GREEN)✓ Cleaned up$(NC)"

setup-hooks: ## Setup git pre-commit hooks
	@bash setup-hooks.sh

dev: install ## Setup development environment
	@echo "$(GREEN)✓ Development environment ready!$(NC)"
	@echo ""
	@echo "Quick start:"
	@echo "  make test       - Run tests"
	@echo "  make format     - Format code"
	@echo "  make lint       - Check code quality"
	@echo "  poetry run cdd-agent --help"
