.PHONY: up down test fixture smoke eval seed reset-tenants export

API_IMAGE ?= landfall-api:g003
API_URL ?= http://localhost:8000
GRAPH ?= hub_test

up:
	docker compose up -d --build

down:
	docker compose down

test:
	docker run --rm --network landfall_default \
	  -e FALKORDB_HOST=falkordb \
	  -e FALKORDB_PORT=6379 \
	  -e ADMIN_TOKEN=test-admin-token \
	  -e PUBLISHER_SALT=test-publisher-salt \
	  -e LANDFALL_FIXTURE=/repo/data/fixtures/hub_montelukast.json \
	  -v $(CURDIR):/repo \
	  -v $(CURDIR)/services/api/app:/app/app \
	  -v $(CURDIR)/services/api/tests:/app/tests \
	  -w /app \
	  $(API_IMAGE) pytest tests -q

fixture:
	docker run --rm --network landfall_default \
	  --env-file .env \
	  -e FALKORDB_HOST=falkordb \
	  -e FALKORDB_PORT=6379 \
	  -e GRAPH=$(GRAPH) \
	  -e LANDFALL_FIXTURE=/repo/data/fixtures/hub_montelukast.json \
	  -v $(CURDIR):/repo \
	  -v $(CURDIR)/services/api/app:/app/app \
	  $(API_IMAGE) python -m app.graph.fixture

smoke:
	API_URL=$(API_URL) scripts/smoke.sh

eval:
	python3 eval/run_eval.py

seed:
	docker run --rm --network landfall_default \
	  --env-file .env \
	  -e FALKORDB_HOST=falkordb \
	  -e FALKORDB_PORT=6379 \
	  -v $(CURDIR):/repo \
	  -v $(CURDIR)/services/api/app:/app/app \
	  -w /app \
	  $(API_IMAGE) python -m app.graph.tenants seed

reset-tenants:
	docker run --rm --network landfall_default \
	  --env-file .env \
	  -e FALKORDB_HOST=falkordb \
	  -e FALKORDB_PORT=6379 \
	  -v $(CURDIR):/repo \
	  -v $(CURDIR)/services/api/app:/app/app \
	  -w /app \
	  $(API_IMAGE) python -m app.graph.tenants reset

export:
	scripts/export.sh
