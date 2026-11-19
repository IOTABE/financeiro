.PHONY: up down test lint format migrate superuser check

up:
	docker compose -f compose.yaml -f compose.dev.yaml up --build

down:
	docker compose down

test:
	.venv/bin/python manage.py test
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
	.venv/bin/black --check .

format:
	.venv/bin/ruff check --fix .
	.venv/bin/black .

migrate:
	.venv/bin/python manage.py migrate

superuser:
	.venv/bin/python manage.py createsuperuser

check:
	.venv/bin/python manage.py check
	.venv/bin/python manage.py check --deploy
