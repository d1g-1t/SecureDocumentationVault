.PHONY: setup up down restart logs shell migrate seed test lint fmt mypy clean

COMPOSE        = docker compose
API_CONTAINER  = securedocvault-api-1
PYTHON         = python

setup: .env
	$(COMPOSE) build --pull
	$(MAKE) up-wait
	$(MAKE) migrate
	$(MAKE) seed
	@echo ""
	@echo "✓ SecureDocVault is ready."
	@echo "  API:     http://localhost:18000/docs"
	@echo "  Grafana: http://localhost:13000  (admin / admin)"
	@echo "  Flower:  http://localhost:15555"
	@echo "  MinIO:   http://localhost:19001"

.env:
	$(PYTHON) -c "import shutil; shutil.copy('.env.example', '.env')"
	@echo ".env created from .env.example — review it before running in production."

up:
	$(COMPOSE) up -d

up-wait:
	$(COMPOSE) up -d --wait
	@echo "Services healthy."

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f

logs-api:
	$(COMPOSE) logs -f api

migrate:
	$(COMPOSE) exec api alembic upgrade head

migrate-history:
	$(COMPOSE) exec api alembic history --verbose

makemigration:
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(MSG)"

seed:
	$(COMPOSE) exec api python -m src.scripts.seed_demo_users

shell:
	$(COMPOSE) exec api bash

py:
	$(COMPOSE) exec api python -c "$(CMD)"

test:
	$(COMPOSE) exec api pytest tests/ \
		--cov=src \
		--cov-report=term-missing \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=80 \
		-v \
		--tb=short \
		-x

test-unit:
	$(COMPOSE) exec api pytest tests/unit/ -v --tb=short

test-integration:
	$(COMPOSE) exec api pytest tests/integration/ --integration -v --tb=short

test-e2e:
	$(COMPOSE) exec api pytest tests/e2e/ -v --tb=short

lint:
	$(COMPOSE) exec api ruff check src/ tests/

fmt:
	$(COMPOSE) exec api ruff format src/ tests/
	$(COMPOSE) exec api ruff check --fix src/ tests/

mypy:
	$(COMPOSE) exec api mypy src/ --ignore-missing-imports

check: lint mypy

clean:
	$(COMPOSE) down -v --remove-orphans
	@echo "All volumes purged."

help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //' | column -t -s ':'
