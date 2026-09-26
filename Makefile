.PHONY: install-backend install-frontend test migrate dev-up dev-down prod-build prod-up prod-down logs e2e-test test-up test-down

install-backend:
	cd backend && pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install

test:
	cd backend && pytest -q
	cd edge && pytest -q

e2e-test:
	cd backend && rm -f visual_recognition.db && pytest -q tests/test_e2e_simulation.py --tb=short -s

migrate:
	cd backend && alembic upgrade head

dev-up:
	docker compose up -d

dev-down:
	docker compose down

prod-build:
	docker compose -f docker-compose.prod.yml build

prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down

logs:
	docker compose -f docker-compose.prod.yml logs -f

test-up:
	docker compose -f docker-compose.test.yml run --rm e2e-runner

test-down:
	docker compose -f docker-compose.test.yml down -v
