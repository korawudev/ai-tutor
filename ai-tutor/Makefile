.PHONY: help test lint build deploy restart check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test: ## Run unit tests
	.venv/bin/python -m pytest tests/unit/ -v --tb=short

test-all: ## Run all tests (unit + integration)
	.venv/bin/python -m pytest tests/ -v --tb=short

lint: ## Type-check frontend + backend syntax check
	cd web-app && npx tsc --noEmit
	.venv/bin/python -m py_compile gateway/app/api/runs.py
	.venv/bin/python -m py_compile gateway/app/api/feynman.py

build: ## Build frontend + rebuild gateway container
	cd web-app && npm run build
	docker compose build gateway web-app

deploy: build ## Build + restart services
	docker compose up -d gateway web-app
	@echo "✅ Deployed. Frontend: http://localhost:3000  Gateway: http://localhost:8000"

restart: ## Restart all services
	docker compose restart

check: lint test ## Lint + test (pre-commit gate)
	@echo "✅ All checks passed"

logs: ## Tail gateway logs
	docker compose logs -f gateway --tail 30

clean: ## Clean build cache
	docker compose build --no-cache gateway web-app
