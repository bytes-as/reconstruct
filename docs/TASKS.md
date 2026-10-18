# Landfall task board

The hour-by-hour summary. The complete, numbered work list with acceptance tests is `docs/GOALS.md`; Cursor works from GOALS.md and ticks both.

H0 = the moment the build starts. A = backend and graph. B = frontend, eval labels, video. Do not start a later block while an earlier block's acceptance criteria fail.

## Block 0 (H0-H1): scaffold, deploy "hello", fixture (G001-G019)
- [ ] A: repo layout (BLUEPRINT 13); `docker compose up` starts FalkorDB + API; schema bootstrap; `queries.py` generated from `docs/queries.cypher` with the sync test. G001 done 18 Oct 2026.
- [ ] A: fixture loader: `make fixture GRAPH=hub_test` loads `data/fixtures/hub_montelukast.json` through the I-queries (counts in G016).
- [ ] A: Railway `falkordb` (volume `/var/lib/falkordb/data`, `REDIS_ARGS`, `FALKORDB_ARGS` with `TIMEOUT 5000`, `requirepass`, private) and `api`.
- [ ] B: Vercel project for `apps/web`; layout, nav, health dot.
- [ ] B: freeze `data/eval_cases.csv` into `eval/cases.csv` (no labels yet).
- **Accept:** both URLs live; health green from the deployed web app; fixture loads with 0 errors.

## Block 1 (H1-H4): sources, Scout, Matcher (G020-G034)
- [ ] A: `http.py` (limiters, retries, cache), `openfda.py`, `dailymed.py` (incl. archive ids from `drugInfo.cfm`), `spl.py` (synthetic SPL tests only; never commit real label text).
- [ ] A: Scout for montelukast (sets, listings, applications fetched by number), history ingest, Matcher, I12, I13; prewarm in the background; `LANDFALL_FIXTURE_MODE`.
- [ ] B: **write `eval/labels.json`** for E-VERDICT, E-GATE, E-REPLAY, E-WHO by opening the rendered DailyMed pages and archives; commit `eval/labels.sha256` **before A merges the verdict engine (G036)**.
- **Accept:** live hub: 116 sets (or the current count), 69 labels of record (or logged diff), checks on the 69 current versions equal the fixture (54 / 2 / 13) or the diff is in OPEN_POINTS.

## Block 2 (H4-H8): verdict (the core; protect it forever) (G035-G054, G135)
- [ ] A: `verdict.py` per FLOWS F1 (class from V4), `authority.py` (6.3 rules), explanation templates, OpenRouter gateway with template fallback, `/api/landed`.
- [ ] A: golden tests on the fixture: hero, uncoded, landed, unrevised + authority gap, no path, census, upstream 1,147 days, as-of replay, strict.
- [ ] B: `/` and `/ndc/[ndc]` (badge, reason, path graph, timeline, upstream card, who can act, alternatives, How we decided, disclaimer).
- **Accept (H8 milestone):** on the public URL a stranger types `68071-3355-9` and sees NOT LANDED (revised without it) with the path, versions 4 and 5, the source carrying since 21 May 2021 and who can act, in under 5 s for a cached NDC.

## Block 3 (H8-H12): organisations, memory, MCP, infrastructure (G055-G079)
- [ ] A: tenant bootstrap and seeded rulings (Northgate strict); rulings with bases; 409; sandbox (GRAPH.COPY); tasks with leases; traces; decisions; conversation turns.
- [ ] A: MCP server at `/mcp` (`landed`, `who_must_act`, `label_history`, `proof_path`, `alternatives`, `watch`); pharmacy agent example over MCP.
- [ ] B: `/orgs` page (two columns, stock, formulary, tasks, traces); `/mcp` page; record Claude Code and the pharmacy agent.
- **Accept:** the pharmacy agent prints the 6 actions of FLOWS F19.3; Claude Code calls `landed` from one prompt; Bayview shows 5 rulings.

## Block 4 (H12-H16): graph-wide views, algorithms, eval (G080-G094)
- [ ] A: fan-out census, copy lag, latency backfill and ledger, WCC families, PageRank source hubs, betweenness chokepoints, open gaps, BFS upstream; MCP tools for them.
- [ ] A+B: `eval/run_eval.py`, `eval/baselines.py` (openFDA field script, openFDA grep; LLM if key); `/eval` page.
- [ ] B: `/facts/[id]` page.
- **Accept:** census 54 / 2 / 9 / 4 on screen; copy lag table shows 14 pairs; false red 0 and gate false red 0 in the report.

## Block 5 (H16-H19): watcher, loop, compounding (G095-G112)
- [ ] A: Watcher (history poll, new version, Matcher, landing, D2 downstream, reopen, handoff, approve/reject).
- [ ] A: replay timeline; replay Watcher on `hubr_<id>` (cuttable); Publisher confirm-check with disputes; fact verification for zolpidem (cuttable); Notifier drafts (cuttable).
- [ ] B: `/replay` page (Accord and AvKARE presets), `/checks` page.
- **Accept:** all three demo shots in BLUEPRINT section 1 run end to end on the deployed site.

## Block 6 (H19-H21): hardening (G113-G124)
- [ ] Rate limits, persistence, export/restore, load test, input validation, prewarm on prod, runbook, mobile, error and empty states, security checks, uptime monitor.
- **Accept:** a cold visitor on a phone gets a verdict; a judge's own montelukast NDC works or shows a clear queued/unknown state.

## Block 7 (H21-H23): submission assets (G125-G134)
- [ ] README: what it is, live URL, video, MCP command, setup (local + deploy + fixture mode), graph data model (BLUEPRINT 5.1-5.3), the queries (link `docs/queries.cypher`; explain V1, V2, V4, V5, W1, D1, D3, R1, A1, A2, W4, P1, T3), algorithms, tracks (Track 1 primary; Track 2, Track 3), eval and labels hash, AI disclosure, limitations and wording disclaimer.
- [ ] Video (3 min) per BLUEPRINT 15. Blog draft.
- **Accept:** BLUEPRINT section 17 fully ticked.

## Block 8 (H23-H24): buffer and submit
- [ ] Submit with all tracks named. Re-check the live URL from a private window.

## Verification log (pre-filled by the spec author on 18 Oct 2026; re-check the starred items during the build)
- FalkorDB queries: all blocks in `docs/queries.cypher` run on `falkordb/falkordb:latest` against the fixture (see OPEN_POINTS "Query test log").
- GRAPH.COPY: works; destination must not exist.
- Multi-type bounded paths and multi-type shortestPath: work.
- algo.BFS(node, depth, NULL): follows every outgoing relationship type; returns `nodes` without the start node.
- * MCP mount with mcp 1.x in the API container (G068).
- DailyMed: `spls.json?drug_name=`, `spls.json?ndc=`, `spls/{setid}.xml`, `history.json`, `ndcs.json`, `drugInfo.cfm` archive ids, `getArchivalFile.cfm` ZIP: all verified.
- openFDA: `drug/ndc.json`, `drug/label.json`, `drug/drugsfda.json`: verified; rate limits verified.

## Questions for the owner
- G001 asks for a first commit message `chore: scaffold Landfall`. The repository already had a pushed first commit, `chore: add Landfall specification and seed data` (18 Oct 2026, `34cf308`). History was not rewritten. The scaffold commit follows it. `eval/labels.json` and `eval/labels.sha256` are not in the tree until a human writes them (G080).
- G002 host ports: owner chose a separate Landfall FalkorDB on 6381 / 3010 / 8010 until the end, rather than sharing the modelbrain database. Spec ports 8000 and 3000 are restored when modelbrain is stopped.
- Deployment (G015, G113, Vercel, Railway) is owned by Arun. The build does not block on it.
- G080 answer key is `eval/labels.json` plus `eval/labels.sha256`. Owner will not label by hand. The file is derived from the verified fixture (no label text). G105 zolpidem held-out stays cuttable and is not in the file.
- `HTTP_CONTACT` is `arunsin997@gmail.com` in local `.env` only. `OPENFDA_API_KEY` is set in local `.env` only. Neither value is committed. 
