# Landfall flows

Every flow the product runs, step by step. Each step names the component, the query (from `docs/queries.cypher`) or endpoint (from `docs/API.md`), and what happens on failure. If code behaves differently from this file, the code is wrong.

Conventions
- Hub graph: `hub`. Tenant graphs: `tenant_bayview`, `tenant_northgate`. Sandboxes: `sbx_<8 hex>`. Replay hubs: `hubr_<8 hex>`.
- `now` is epoch milliseconds (UTC) for tenant timestamps. Comparable dates in the hub are day numbers (`*_d`, days since 1970-01-01 UTC); ISO strings sit next to them. `today_d` is computed in UTC at request time unless `AS_OF_OVERRIDE` is set (frozen eval).
- Ids are prefixed: `rul_`, `bas_`, `evt_`, `task_`, `drf_`, `dec_`, `job_`, `sbx_`, `hubr_`, `land_`, `fan_`, `conv_`, `turn_`.
- "Template text" means the deterministic explanation in `app/engine/explain.py`.
- Section code `34066-1` is the LOINC code of the SPL BOXED WARNING SECTION. NDC code system `2.16.840.1.113883.6.69`. LOINC code system `2.16.840.1.113883.6.1`.

---

## F0. Startup (API process boot)
1. Load config (`.env.example` lists all). Missing `OPENFDA_API_KEY` -> warning (1,000 openFDA requests per day per IP).
2. Connect to FalkorDB (`FALKORDB_HOST/PORT/PASSWORD`), 10 tries with 2 s backoff; if still down, start anyway and report `falkordb: "down"` on `/api/health`.
3. Run SCHEMA_HUB on `hub` and SCHEMA_TENANT on each existing tenant and sandbox graph (idempotent; ignore "already indexed").
4. Load `data/molecules.json`, `data/facts.seed.json` and `data/section_codes.json` into memory. Facts are written to the hub later (step 7) because I11 needs the molecule and the applications to exist.
5. If `LANDFALL_FIXTURE_MODE=1`: load `data/fixtures/hub_montelukast.json` into `hub` with the fixture loader (G016) and skip step 7's network ingest.
6. **Tenant bootstrap**: for each fixed tenant (`bayview`, `northgate`): if the graph does not exist, `GRAPH.DELETE` (ignore missing), SCHEMA_TENANT, run `data/demo_tenants/<slug>.cypher` (one statement), X1. Tenant policy: `northgate.strict = true`, `bayview.strict = false` (in `app/config.py` `TENANT_POLICIES`, not in the graph). After the hub has facts (step 7 or fixture), **seed rulings**: T8 lists stock items; for each, run F1 with the tenant's policy and `persist = true` (T1). Never run twice: skip a stock item that already has a ruling.
7. **Prewarm** (background task; never blocks startup): for each molecule with `ingest: true`, run F2 (Scout, history, Matcher), then I11 for its facts, I12, I10 for every version, I13, then the latency backfill (F12.3). Then seed rulings (step 6) if not yet seeded.
8. Start APScheduler jobs: Watcher every `WATCH_INTERVAL_MINUTES` (F9), sandbox and replay cleanup every 15 minutes (F7.5, F11.6), daily Scout refresh at 04:00 UTC (F2 without history for unchanged sets), ADD3 daily if enabled (F17).
9. Mount the MCP server at `/mcp` (F5) after all routes. Serve.

## F1. Landed verdict (web, API, MCP and the pharmacy agent all call this)
Input: `ndc`, optional `fact_id`, `as_of` (ISO date, default today), `strict` (default: the tenant's policy, else false), optional `tenant` + `token` + `stock_item_id` + `expected_ruling_id`.
1. **Validate and normalise.** Strip spaces. Accept dashed forms `4-4-2`, `5-3-2`, `5-4-1` (package) and `4-4`, `5-3`, `5-4` (product). An undashed 10-digit value is ambiguous: return 422 `INVALID_INPUT` with hint "Use the dashed NDC printed on the label, e.g. 68071-3355-9". An 11-digit billing NDC (5-4-2 with a padded zero) -> try removing the leading zero of each segment to find a match among dashed forms in the hub; if exactly one matches use it, else 422 with the hint. `as_of` in the future -> 422. `fact_id` must match `^[a-z0-9_]{3,64}$`.
2. **Identity (V1)** with `as_of_d`. No row -> on-demand ingest (F2.7); if it finishes within 8 s re-run V1, otherwise return 202 `{status:"QUEUED", job_id}`. Still no row after ingest -> respond with one result `UNKNOWN`, reason `NDC_NOT_FOUND`, hint "This NDC is not in the NDC Directory or DailyMed."
3. **Facts (V3)** for `molecule_key` with `include_unverified = false`; if `fact_id` is given, use only it (any molecule; it may be UNVERIFIED only if `include_unverified` is requested by an admin). None -> `results: []` and `message: "No verified safety fact for <molecule> in Landfall yet."`.
4. **Scope (V2)** per fact. If any row has `no_path = false`, take the first such row (shortest) as `scope.path`/`scope.rels`. If all rows have `no_path = true`:
   - scope is **complete** when the product has no UNDER edge and its `marketing_category` is one of BULK INGREDIENT, BULK INGREDIENT FOR HUMAN PRESCRIPTION COMPOUNDING, DRUG FOR FURTHER PROCESSING; or every application the product is UNDER has `kind` set; or the product's `molecule_key` differs from the fact's -> `NOT_IN_SCOPE` with `proof = {searched: "SOURCED_FROM|UNDER|REFERENCES*1..5", targets: [rld ids], from: product_ndc}`;
   - otherwise -> `UNKNOWN`, reason `SCOPE_UNRESOLVED`, and queue an ingest of the missing application (F2.3).
5. **Listing gate.** If `as_of` is today: `listing_active = false` -> `NOT_ASSESSED_INACTIVE_LISTING` ("No active NDC Directory listing points to this label"). `record_sets` empty -> ingest the set whose current document id equals `listing_spl_id` (F2.7 by `spls.json?ndc=`), retry V1 once; still empty -> `UNKNOWN`, reason `LABEL_OF_RECORD_NOT_INGESTED`. If `as_of` is in the past (replay): skip the gate, use the record set if any else the only described set, and set `replay: true`, `gate_skipped: true`.
6. **Timeline and class (V4)** on the record set: `min_tier = 2` if strict else 1; `grace_days = GRACE_DAYS` (30). The returned `verdict` string is the verdict. If it is `UNKNOWN`, set the reason: `NOT_CHECKED` (current version has no check), `ABSENCE_NOT_CONFIRMED` (strict and ABSENT at tier 1), or `DISPUTED`.
7. **Upstream (V5)** for the product with `as_of_d`. For each source with a first carry: `copy_lag_days = max(published_d of target versions with result ABSENT and published_d > source_first_carry_d) - source_first_carry_d`, computed from the V4 `versions` list; omit when no such version.
8. **Who must act** (F4) for NOT_LANDED_* and LANDED_UNCODED.
9. **Alternatives (V6)** for NOT_LANDED_* and LANDED_UNCODED; labelled "in Landfall's catalogue".
10. **Explanation**: template from the evidence; if `OPENROUTER_API_KEY` is set and the daily budget allows, the LLM may rephrase the template using only the evidence JSON (6 s timeout); on any error use the template. The LLM output never replaces a field.
11. **Persist (only with tenant + stock_item_id)**:
    1. Authorise: `token` must be the sandbox token or `ADMIN_TOKEN`; fixed tenants are read-only for visitors (403 `READ_ONLY_TENANT`).
    2. If `expected_ruling_id` is given and the stock item's latest ruling (T6 filtered) has a different id -> 409 `STALE_RULING` with the latest ruling.
    3. One ruling per fact: T1 with bases `TARGET_VERSION` (current version: set id, version id, doc id, published, section code, check result, tier), `SOURCE_VERSION` (each upstream source's first carrying version, if any), `FACT` (fact id, phrase key version), `SCOPE_PATH` (path list).
    4. If an active ruling for the same stock item and fact exists: T2 and T13 `SUPERSEDED` signed by the acting person (or `system`).
    5. T11 turn when the call came through MCP or the web with a tenant.
12. **Respond** with `Landing` (API.md) including `cypher.v1`, `cypher.v2`, `cypher.v4` (exact text), the parameters, `computed_ms` and the disclaimer.

Failure handling: FalkorDB error -> 503 `GRAPH_UNAVAILABLE`; source unavailable and the NDC is not in the hub -> 503 `SOURCE_UNAVAILABLE` with `retry_after_s`; any other exception -> 500 `INTERNAL` with the request id.

## F2. Ingest (Scout)
Input: `molecule` (from `data/molecules.json`: `{key, drug_name, generic_name, ingest}`) or a single NDC (F2.7).
1. **Sets.** `spls_by_drug_name(drug_name)` over all pages. For each set: `spl_xml(setid)` -> parse (spl.py) -> I4 (`labeler_id = "labeler:" + slug(labeler_name)`), I5 for the current version (`doc_id`, `effective`, `published` from the list entry), I6 + I7 for each product NDC in the XML (molecule key from the molecule), I9 for each `asEquivalentEntity` source NDC (`source: "spl_equivalent"`), I8 for each package NDC from `ndcs(setid)`.
2. **Listings.** `ndc_by_generic(generic_name)` (limit 1000; page with `skip` if `meta.results.total` > 1000) and, for every product NDC seen in step 1 and not returned, `ndc_by_product(ndc)`. For each listing: I6 with `listing_spl_id = spl_id`, `listing_expiration_d` from `listing_expiration_date`, `application_id = application_number`, `strength` = active ingredient strengths joined by ";", `dosage_form`, `marketing_category`, `in_ndc_directory = true`; I8 for each `packaging[].package_ndc`. Products seen only in SPL keep `in_ndc_directory = false` and no listing.
3. **Applications.** Collect every `application_id` from products. `drugsfda_by_generic(generic_name)` plus `drugsfda_by_application(id)` for each id not returned (generic-name search misses applications without an `openfda` block). For each: I2 (`kind` from the prefix NDA/ANDA/BLA, `dosage_forms` = distinct product dosage forms, `marketing_status` = "Prescription" if any product is, else the first product's status, `reference_drug` = any product "Yes", `reference_standard` = any product "Yes", `molecule_key`), I3 with `party_id = "sponsor:" + slug(sponsor_name)`, `from_d = null`, `source = "drugsfda"`. A 404 leaves the placeholder (I6 MERGE) without `kind`; F1.4 then answers SCOPE_UNRESOLVED instead of NOT_IN_SCOPE.
4. **Slug rule** (used for every Party id): lower-case; `&` -> ` and `; remove the words inc, llc, lp, ltd, limited, co, corp, corporation, company, l.p. (with an optional trailing dot); replace every run of non-alphanumerics with `-`; trim `-`. DUNS from the SPL is stored as `Party.duns` but never used as the id.
5. **History.** For every set: `history(setid)` and `archive_ids(setid)`. Let `cutoff_d` = (earliest `issued_d` among ACTIVE and UNVERIFIED facts of the molecule) - 365. For every listed version: I5 with dates (and `archive_id` when known). For versions with `published_d >= cutoff_d` and an archive id: `archived_xml(archive_id)` -> parse -> the Matcher (F3). Versions are written in ascending order. A set whose archive page cannot be parsed keeps versions from `history.json` only and is logged `ARCHIVE_PARSE_FAILED <setid>`.
6. **HTTP rules** (all sources): one shared async client; per-host limiters (DailyMed `DAILYMED_RPS`, openFDA 4 rps); 15 s timeout; on 429 sleep `Retry-After` (default 20 s) and retry up to 3 times; on 5xx and timeouts retry 3 times with 1, 2, 4 s; disk cache: list endpoints 6 h, `spls/{setid}.xml` keyed by the version in `history.json` (re-fetch only when the version changes), archive ZIPs forever. Every request sends `User-Agent: Landfall/1.0 (+HTTP_CONTACT)` and openFDA requests send `api_key` when set.
7. **On-demand NDC** (from F1.2 or F1.5): `ndc_by_package` or `ndc_by_product` -> listing; `spls_by_ndc(ndc)` -> set ids; for each set run steps 1, 3 and 5 for that set only (history limited to the cutoff of the molecule's facts; if the molecule is not in `data/molecules.json`, skip history and the Matcher, and F1.3 will answer "No verified safety fact"). Create job `job_<id>`; emit SSE events `started`, `set`, `version`, `done`, `error`. Caps: 5 sets, 60 archived versions per job.
8. After any ingest: I12 for the molecule, I10 via the Matcher for new versions, I13 with `today_d`.

## F3. Matcher
Input: one parsed SPL version and the molecule's ACTIVE and UNVERIFIED facts.
1. For each fact: compute `in_coded` and `in_text` exactly as BLUEPRINT 6.1 (normalised text never stored or logged).
2. I10 with `result`, `method: "matcher_xml"`, `tier: 1`, `phrase_key_version`.
3. If I10 returns `disputed = true` and it was not disputed before: for each tenant, T3 with `[set_id]` -> T19 `CONFIRM_CHECK` task for the owner with payload `{version_id, fact_id}`; and T4-style reopen with reason "matcher result changed on a confirmed check".
4. openFDA fast path (`method: "matcher_openfda_json"`) only when the XML is unavailable after retries; logged `FASTPATH <setid> v<version>`.

## F4. Who must act
Input: the product NDC, the fact, the V4 and V5 results.
1. W1 with `as_of_d`; W2 for the product's molecule and dosage form when any hop's `rld_status` is `Discontinued`.
2. Apply BLUEPRINT 6.3 rules in order (AUTHORITY_GAP, SOURCE_CARRIES, SOURCE_LACKS, OWN_LABEL) and the REFERENCE_DISCONTINUED annotation.
3. Output `who_must_act = {rule, primary:{party, role, reason}, secondary:[...], oversight:{party:"FDA", role:"regulator", reason}, authority_gap: bool, annotations:[...], rows:[W1 rows]}`. Roles and reasons use the copy in UI "Who can act".
4. FDA is always the oversight party. Never name a person.

## F5. MCP (other agents)
1. Clients connect to `https://<api>/mcp` (streamable HTTP, stateless). `tools/list` returns the tools in API.md with their verbatim descriptions and JSON schemas.
2. `landed(ndc, fact_id?, strict?, as_of?, tenant?, token?, stock_item_id?)` calls F1. If F1 returns QUEUED, the tool polls the job up to 20 s, then re-runs F1; if still queued returns `{status:"QUEUED", job_id, hint:"call again in a few seconds"}`.
3. Text result format (first lines): `LANDFALL: NOT LANDED (revised without it) - montelukast boxed warning (FDA, 2020-04-29)`; then `Label of record: DailyMed set 549f1d1a..., version 5, 2024-07-11 (no coded boxed-warning section; text absent)`; then `Path: 68071-3355 -> ANDA202717 -> NDA020829`; then `Source 16729-119 carries it since 2021-05-21 (copy lag 1147 days)` when present; then `Who can act: <primary party> (<role>); regulator: FDA`; then `Suggested action for a dispensing agent: print the current Medication Guide from the reference label and ask a pharmacist`; then `Details: <WEB_BASE_URL>/ndc/68071-3355-9`; then the disclaimer. The full `Landing` is returned as structured content.
4. Tools that write (`watch`, `confirm_check`, `verify_fact`, and `landed` with tenant) require `tenant` + `token`; fixed tenants accept only `ADMIN_TOKEN`.
5. Rate limit per MCP session: 30 calls per minute.
6. Every call with a tenant writes T11.

## F6. Tenant ruling with concurrency control
See F1.11. Rulings are never edited; "change" = new ruling + SUPERSEDES + Event SUPERSEDED. A UI that shows a ruling sends its id as `expected_ruling_id` on "Re-check"; a 409 shows "Someone updated this item a moment ago" with the newer ruling and a "Use the latest" button.

## F7. Sandbox (a visitor acts as an organisation)
1. `POST /api/sandbox {template: "bayview" | "northgate"}`; 3 per hour per IP; at most 50 live sandboxes (oldest deleted first).
2. Name `sbx_<8 hex>`; `GRAPH.COPY tenant_<template> sbx_<id>` (fails if the destination exists: regenerate the id, retry once). The sandbox inherits the template's policy (strict for Northgate).
3. Token = 32 random bytes, urlsafe; keep `{name, sha256(token), template, expires_at = now + SANDBOX_TTL_MINUTES}` in memory; X2 in the hub (name, expiry, template; never the token).
4. Return `{tenant: "sbx_<id>", token, expires_at, template}`; the web app keeps the token in sessionStorage and sends `X-Tenant-Token`.
5. Cleanup every 15 minutes: X3 -> `GRAPH.DELETE` each -> X4. An API restart loses in-memory tokens: sandboxes become unusable and are cleaned at expiry (documented in the runbook).

## F8. Confirm a check -> Publisher -> verdicts flip (compounding)
1. On `/checks` (or from a verdict page), a person in tenant A opens the DailyMed version link, looks for the boxed-warning section and the phrase, and clicks "I see: coded / text only / absent". `POST /api/tenants/{t}/confirm-check {version_id, fact_id, result, person_id}` with token.
2. API checks that the person exists in the tenant (else 422) and that the version is in the public check queue (F8.7, else 409 `NOT_IN_QUEUE`). Tenant record: if the tenant has an active ruling resting on that set (T3 with `[set_id]`), write T13 `CONFIRMED_CHECK` on it signed by the person (reason `"<version_id> <result>"`); otherwise write T11 with `tool: "confirm_check"` and the arguments. The hub write in step 3 happens in both cases.
3. Publisher: `org_hash = sha256(PUBLISHER_SALT + tenant_graph_name)[:16]`; P1 on the hub -> `{result, tier, confirmations, disputed}`.
4. If the tier or the dispute flag changed: for every tenant in the registry (and live sandboxes), T3 with `[set_id]` -> T4 with reason "a pharmacist at another organisation confirmed this check" (or "this check is disputed"); X5 record `{trigger:"confirm_check"}`.
5. The Prover handles the review tasks (F9.5). In strict tenants a confirmed ABSENT turns UNKNOWN into NOT_LANDED_*; that is the demo flip (G101: Bayview confirms `56429f04-97b6-06a9-e054-00144ff88e88#v4`, Northgate's `ng_si_4` flips).
6. Disagreement (`disputed = true`): verdicts on that check become UNKNOWN (`DISPUTED`); T19 `CONFIRM_CHECK` tasks in every tenant resting on it; an admin resolves with `POST /api/admin/checks/resolve` (P3) after reading the label, then the same reopen as step 4.
7. Check queue (`GET /api/checks/queue`): D1 rows over every ACTIVE fact whose current check is ABSENT or CARRIES_UNCODED at tier < 3, with the DailyMed link `https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=<set_id>` and, for archived versions, `https://dailymed.nlm.nih.gov/dailymed/getArchivalFile.cfm?archive_id=<id>`.
8. The UI shows "confirmed by N independent organisations" and never names them.

## F9. Watcher -> landing -> fan-out -> reopen -> handoff -> approve -> supersede
1. **Watch set** every `WATCH_INTERVAL_MINUTES`: L3 (limit 500) + sets behind every tenant StockItem (V1 per held NDC; cache the mapping for the run) + their source sets (V5) + `data/watchlist.json`. Deduplicate; process at most 200 per run, rotating by a persisted cursor (in memory; restart starts at 0).
2. **Poll** `history(setid)` (cache bypass). If the max `spl_version` equals `LabelSet.current_version` (L2): skip.
3. **New version**: `spl_xml(setid)` -> I5 (new version, `published` from history), I4 (current pointers), I6/I7/I8/I9 for its products and sources, the Matcher for every ACTIVE and UNVERIFIED fact (F3), I13.
4. **Landing and fan-out**: if a fact's result on the new current version is CARRIES_* and the previous current version was ABSENT: D5 `{kind: LANDED or LANDED_UNCODED, observed: "live"}`. Affected sets = `[setid]` + D2 downstream set ids. For each tenant: T3 with affected sets -> for each row T4 (`agent: "watcher"`, reason "DailyMed published version <n> on <date>" or "the source label <source set> changed"). X5 `{trigger:"watcher", set_id, summary_json: {changed, downstream, tenants:{name: count}}}`.
5. **Handoff**: the Prover (in-process worker, every 30 s) lists OPEN REVIEW_RULING tasks (T16 with state OPEN) per tenant, claims each (T5), recomputes F1 for the ruling's stock item and fact (no persist), then T10 with `proposed_verdict` and `proposed_ruling_json` (the full Landing result) to the owner.
6. **Approve** (`POST /api/tasks/{id}/approve {person_id}`): read `proposed_ruling_json` from the HANDED_OFF_FROM review task; T1 (new ruling with its bases), T2 (supersedes the old), T13 `APPROVED` signed by the person, T17 on both tasks; if the new verdict is NOT_LANDED_*, T19 `PHARMACIST_REVIEW` for the site's responsible person (G079). **Reject** (`/reject {person_id, reason}`): T13 `REJECTED`, T17; the old ruling stays active and the UI shows "reviewed, kept".
7. Failure: a source error leaves the set for the next run; a FalkorDB error aborts the run and logs it.

## F10. Notifier -> approval -> ready to copy (never sent)
1. Trigger: "Draft a note" on a verdict page in a tenant context (`POST /api/drafts {tenant, stock_item_id, fact_id, kind}`), allowed only for NOT_LANDED_* and LANDED_UNCODED.
2. Guard: the TARGET_VERSION check must be tier >= 2 and not disputed; otherwise 409 `CHECK_NOT_CONFIRMED` "Confirm the check on /checks first."
3. Draft (template in `app/agents/notifier.py`; LLM may rephrase): title "Question about the boxed warning on DailyMed set <set_id>"; body states: the NDC, the set id, version and published date, that the label lacks a coded boxed-warning section (or carries the text uncoded), the reference supplement (application, supplement, approval date), the source label's first carrying version when known, the DailyMed links, and asks whether an updated label is planned; signature "Prepared with Landfall (automated screening of public FDA and NLM data; not legal or regulatory advice)". MEDWATCH kind fills a field list (product, NDC, labeler, description) to copy into FDA's form. INTERNAL_MEMO is addressed to the organisation's own team.
4. T19 `APPROVE_NOTICE` assigned to the tenant's QA lead or P&T chair; T18 stores the draft.
5. Approve -> T21 (sets `ready_to_copy = true`; the only update a draft ever gets), T13 `NOTICE_APPROVED` when the task is about a ruling, T17. The UI shows a copy button and the DailyMed link. No code path sends the draft.

## F11. Replay (the loop closes on real history)
1. **Timeline (read-only)**: `GET /api/replay/{set_id}/timeline?fact_id=` -> L1 versions; for each distinct version `published` date, V4 with `as_of_d = published_d` (and once at today); plus D6 rows for that set. The `/replay` page scrubs these points.
2. Presets (UI): Accord `6eea668f-a2fa-447f-b2d5-4c754d13d9fa` (v12 2021-03-05 -> v14 2021-05-21), AvKARE `ed2caffa-a75c-1c27-ae30-2d8280eaea7d` (v20 2025-01-13 -> v21 2025-11-17), Bryant Ranch `3ff4100f-...` (v1 -> v2), American Health Packaging `fb1b2e4e-...` (v5 -> v6). Full set ids come from the hub at runtime.
3. **Replay Watcher** (cuttable): `POST /api/replay/start {set_id, from: "2021-03-01", template: "bayview"}` (rate limit 3/h/IP):
   1. `GRAPH.COPY hub hubr_<id>`; run X6 on `hubr_<id>` (deletes that set's versions published after `from_d` with their CHECKED edges, and points the set at the latest remaining version). X6 must never run on `hub`: `app/engine/replay.py` asserts the graph name starts with `hubr_`.
   2. `GRAPH.COPY tenant_<template> sbx_<id>`; seed a ruling for each stock item against `hubr_<id>` with `as_of = from` semantics.
   3. Return `{replay_id, hub: "hubr_<id>", tenant: "sbx_<id>", token, next_version}`.
4. `POST /api/replay/{id}/advance`: take the next hidden version from the real `hub` (L1 gives its version, dates, archive id and stored checks) and apply it to `hubr_<id>` through the Watcher change handler (F9.3-F9.4): I5, I10 with the stored result and method, I4 with the new current pointers, then landing and fan-out with `observed: "replay"`; return the landing (if any), reopened rulings and tasks.
5. The Prover and approvals work in the sandbox as in F9.5-F9.6.
6. Cleanup: replay graphs expire with their sandbox (2 h) via F7.5.

## F12. Graph-wide views
1. **Fan-out** `GET /api/facts/{id}/fanout`: D1 with `as_of_d = today_d`, `min_tier`; then V4 per set for the class (cached for 10 minutes per fact and hub change counter); census = counts per class.
2. **Copy lag** `GET /api/facts/{id}/copy-lag`: D3.
3. **Latency backfill** (after prewarm and after each history ingest): for each set and ACTIVE fact, walk L1 in version order; at the first version whose result is CARRIES_* and whose previous checked version was ABSENT (or which is the first checked version after the fact with an earlier unchecked pre-fact version), D5 with `observed: "history"` and id `land_<set_id>_<fact_id>`. Endpoints `/latency` (D4) and `/landings` (D6).
4. **Families** `GET /api/facts/{id}/families`: R1. **Source hubs** A1, **chokepoints** A2, **label families** A3 (cached 10 minutes).
5. **Open gaps** `GET /api/gaps?party_id=&fact_id=`: W3 (filter by fact in code).
6. **Upstream closure** `GET /api/products/{ndc}/upstream`: W4.

## F13. Eval
1. `data/eval_cases.csv` (lines starting with `#` are comments) is copied to `eval/cases.csv` (frozen) and `eval/labels.json` + `eval/labels.sha256` are committed by a human before the verdict engine (G080).
2. `python eval/run_eval.py --api <url> [--as-of 2026-10-16]` calls `/api/landed` for E-VERDICT, E-GATE and E-WHO cases (with `AS_OF_OVERRIDE` semantics via the `as_of` field) and the replay timeline for E-REPLAY; writes `eval/report.json`.
3. `python eval/baselines.py` computes (a) openFDA field script, (b) openFDA text grep, (c) LLM baseline if `OPENROUTER_API_KEY` and `EVAL_BASELINE_MODELS` are set; merges into the report with the "cannot do" columns.
4. `GET /api/eval` serves the report; `/eval` renders it with the labels hash.

## F14. Deploy
1. Railway `falkordb`: image `falkordb/falkordb:latest`, volume at `/var/lib/falkordb/data`, `REDIS_ARGS="--appendonly yes --requirepass ${FALKORDB_PASSWORD}"`, `FALKORDB_ARGS="MAX_QUEUED_QUERIES 25 TIMEOUT 5000 RESULTSET_SIZE 10000"`, private networking only.
2. Railway `api`: `services/api/Dockerfile`; env from `.env.example`; health check `/api/health`; **one replica** (APScheduler jobs must run once).
3. Vercel: root `apps/web`; env `NEXT_PUBLIC_API_URL`; production branch `main`.
4. After deploy: `scripts/smoke.sh <api> <web>` (health, landed for the hero and the five Bayview NDCs, fan-out census, MCP `tools/list`).

## F15. Failure modes (applies everywhere)
| Failure | Behaviour |
|---|---|
| FalkorDB down | `/api/health` `falkordb: "down"`; endpoints 503 `GRAPH_UNAVAILABLE`; web maintenance banner |
| DailyMed or openFDA 429 | limiter waits; requests that would exceed 8 s return 202 QUEUED |
| Source 5xx or timeout | retries; then cached data (`stale: true` on the response) or 503 `SOURCE_UNAVAILABLE` with `retry_after_s` |
| NDC not found | 200 with result UNKNOWN `NDC_NOT_FOUND` and a hint (not a 404: the query itself succeeded) |
| Archive page unparsable | versions from `history.json` only; replay for that set unavailable; log `ARCHIVE_PARSE_FAILED` |
| SPL XML unparsable | that version gets no check (UNKNOWN `NOT_CHECKED`); log `SPL_PARSE_FAILED <setid> v<n>` |
| Molecule without a verified fact | `results: []` with the message; never a verdict |
| LLM error | template text; never blocks a verdict |
| Concurrent ruling write | 409 `STALE_RULING` |
| Sandbox expired | 401 `SANDBOX_EXPIRED` with a "create a new sandbox" action |
| openFDA daily quota exhausted | 503 `SOURCE_UNAVAILABLE` for new NDCs; hub answers continue |

## F16. Fact verification and the second molecule
1. `/checks` lists facts with `status = UNVERIFIED` (V3 with `include_unverified = true`, admin listing) with their source link, issued date, supplements and phrase key.
2. A pharmacist in a tenant clicks "I verified this fact against the FDA source" -> `POST /api/facts/{id}/verify {tenant, person_id}` with token -> P2 with the salted org hash -> T11 turn (or T13 when a ruling context exists).
3. If the status changed to ACTIVE: start a job: F2 for the fact's molecule (if `data/molecules.json` has it with `ingest: false`, flip it in memory to true for this run), then the Matcher, I13, latency backfill, then seed rulings for every tenant StockItem whose product molecule matches (F0.6 rule: only items without a ruling for that fact).
4. Demo: Northgate's P&T chair verifies `zolpidem_bw_2019`; zolpidem label sets appear on `/facts/zolpidem_bw_2019`; Northgate `ng_si_5` gets its first ruling.
5. Cut fallback: the zolpidem fact stays UNVERIFIED and is shown as "awaiting verification".

## F17. Drugs@FDA labeling-supplement watch (add-on ADD3, cuttable)
1. Daily: for every `Application` with `reference_drug = true` whose molecule is in `data/molecules.json`, `drugsfda_by_application(id)`; any submission with `submission_class_code = "LABELING"`, `submission_status = "AP"` and a date newer than the last seen becomes a candidate `SafetyFact {id: "<molecule>_<application>_s<number>", status: "UNVERIFIED", kind: "LABELING_CHANGE", phrase_key: null}` through I11 (with `issued_on` that application).
2. Candidates appear on `/checks` with "needs a phrase key"; an admin adds the phrase key and section code (`POST /api/admin/facts/{id}`), then a pharmacist verifies (F16).

## F18. Ask the organisation (add-on ADD4, cuttable)
1. `POST /api/tenants/{t}/ask {question}`; templates K1-K8 (`app/engine/ask.py`) with names, descriptions and parameter schemas.
2. Router: with an LLM key, the LLM returns `{template, params}` JSON validated against the schemas; without a key, a keyword router chooses. Invalid -> "I can answer these questions: ..." with the list.
3. Run the template with `ro_query`; answer = rows + the Cypher + sources (ruling ids, set ids, version ids); T11 turn.

## F19. An external agent calls Landfall (infrastructure)
1. `examples/pharmacy_agent/agent.py --api <url> [--tenant <sbx> --token <t>] [--llm]` loads `data/dispense_queue.json` (fictional prescriptions).
2. It opens an MCP session to `<url>/mcp`, lists tools, and for each queue item calls `landed(ndc)` (with `--llm`, an OpenRouter model chooses the tool from the tool list and the agent executes the call).
3. It maps each result to an action and prints one line per item. Expected on the live hub as of 2026-10-16 (before zolpidem verification):
| Queue item | NDC | Verdict | Action printed |
|---|---|---|---|
| rx-001 | 68071-3355-9 | NOT_LANDED_REVISED | FLAG: print the current Medication Guide from the reference label; pharmacist review |
| rx-002 | 31722-726-90 | LANDED | PROCEED |
| rx-003 | 42291-622-30 | LANDED_UNCODED | PROCEED (warning text present; not machine-coded) |
| rx-004 | 63187-626-30 | NOT_LANDED_UNREVISED | FLAG: print the current Medication Guide from the reference label; pharmacist review |
| rx-005 | 68071-5063-9 | no verified fact (zolpidem) | PROCEED with standard checks (no verified safety fact in Landfall) |
| rx-006 | 12345-6789-01 | UNKNOWN (NDC_NOT_FOUND) | ASK PHARMACIST: NDC not found |
4. The agent never acts outward; it prints. With `--tenant` it writes turns and rulings in that sandbox.
