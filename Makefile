.PHONY: check format lint types ci run install

check: lint types format ## Run all checks

lint: ## Run ruff linter
	uv run ruff check ralph/

types: ## Run ty type checker
	uv run ty check

format: ## Check formatting
	uv run ruff format --check ralph/

format-fix: ## Auto-fix formatting
	uv run ruff format ralph/

lint-fix: ## Auto-fix lint issues
	uv run ruff check --fix ralph/

ci: check ## Alias for check (CI pipeline)

install: ## Install ralph globally via uv tool
	uv tool install . --editable

run: ## Launch ralph CLI
	uv run ralph $(ARGS)
