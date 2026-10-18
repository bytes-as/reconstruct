# Landfall

Landfall checks whether an FDA boxed warning landed on the DailyMed label of record for a drug NDC, and names the party able to update that label if it did not.

This repository is the Graph Hacks scaffold. The binding spec is `AGENTS.md`, `BLUEPRINT.md` and `docs/GOALS.md`. The graph data model, the Cypher queries, tracks and the AI-assistance disclosure are filled in as those goals land.

## Local setup

Copy `.env.example` to `.env`, then start FalkorDB and the API:

```sh
docker compose up --build
```

FalkorDB answers Redis on port 6379 and the FalkorDB Browser on port 3000. The API listens on port 8000. `GET /api/health` returns `falkordb: "up"` when the graph is reachable. The web app runs separately on port 3001 (`npm run dev -- -p 3001` in `apps/web`) so it does not take the Browser's port. The home page is the NDC check form. The header health dot reads `GET /api/health` from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

If another stack already binds 3000 or 8000, a git-ignored `docker-compose.override.yml` can publish the same services on other host ports. The containers still use 6379 and 8000 on the Compose network. Point `make smoke` at the published API with `API_URL`.

DailyMed and openFDA calls go through one client in `services/api/app/sources/http.py`: a per-host rate limit, a 15 second timeout, retries, and a disk cache.

`make up` and `make down` start and stop the stack. `make test` runs the API tests against FalkorDB. `make fixture` loads the golden fixture. `make smoke` checks `/api/health`. `make seed` and `make reset-tenants` reload the fictional Bayview and Northgate graphs. `make export` writes `exports/falkordb.rdb` (git-ignored). `make eval` reports that scoring is not wired yet.

Automated screening of public FDA and NLM data. Not medical, legal or regulatory advice. Not endorsed by FDA or NLM.
