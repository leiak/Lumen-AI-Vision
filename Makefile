.PHONY: install-backend install-frontend test migrate dev-up dev-down prod-build prod-up prod-down logs

install-backend:
	cd backend && pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install

test:
	cd backend && pytest -q

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
