.PHONY: up down test fixture smoke eval seed reset-tenants export

up:
	@echo "scaffold: implemented in a later goal"

down:
	@echo "scaffold: implemented in a later goal"

test:
	@echo "scaffold: implemented in a later goal"

GRAPH ?= hub_test
fixture:
	docker run --rm --network landfall_default \
	  --env-file .env \
	  -e FALKORDB_HOST=falkordb \
	  -e FALKORDB_PORT=6379 \
	  -e GRAPH=$(GRAPH) \
	  -e LANDFALL_FIXTURE=/repo/data/fixtures/hub_montelukast.json \
	  -v $(CURDIR):/repo \
	  -v $(CURDIR)/services/api/app:/app/app \
	  landfall-api:g003 python -m app.graph.fixture

smoke:
	@echo "scaffold: implemented in a later goal"

eval:
	@echo "scaffold: implemented in a later goal"

seed:
	@echo "scaffold: implemented in a later goal"

reset-tenants:
	@echo "scaffold: implemented in a later goal"

export:
	@echo "scaffold: implemented in a later goal"
