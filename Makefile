.PHONY: check format lint types ci run

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

run: ## Launch ralph TUI
	uv run ralph $(ARGS)
