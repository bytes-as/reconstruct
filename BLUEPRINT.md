# Landfall: build blueprint

The single source of truth for building **Landfall** for **Graph Hacks: Context for AI Agents** (WeMakeDevs x FalkorDB).
Submissions close **Sunday 18 Oct 2026, 11:59 PM IST**. Implementation: Cursor. Product owner and reviewer: the team, with Claude as the spec author. Landfall is the backup project; it shares hosting, conventions and verified FalkorDB facts with the ModelBrain pack but no code.

## 0. Read me first (document map)
| File | What it is | Authority |
|---|---|---|
| `AGENTS.md` | the rules every coding agent follows | binding |
| `BLUEPRINT.md` (this file) | product, architecture, data model, logic | binding |
| `docs/GOALS.md` | 140 numbered goals with acceptance tests: the work list Cursor executes in order | binding; the definition of done |
| `docs/FLOWS.md` | every runtime flow step by step, with failure handling | binding |
| `docs/API.md` | endpoint, type, error and MCP tool contract | binding |
| `docs/UI.md` | every page, state, line of copy and the wording rules | binding |
| `docs/queries.cypher` | every Cypher query, each tested on FalkorDB | binding |
| `docs/REQUIREMENTS.md` | every hackathon rule and judging signal mapped to goals | binding |
| `docs/TASKS.md` | the hour-by-hour board (summary of GOALS by block) | guidance |
| `docs/OPEN_POINTS.md` | what was verified, what is deferred, and why; the query test log | guidance |
| `docs/EXPLAINER.md` | the 2-minute talk track every team member must be able to give | guidance |
| `data/*` | safety facts, molecules, watch list, prewarm list, eval case skeleton, demo tenants, golden hub fixture | binding |

If two files disagree, the order of precedence is: AGENTS.md, GOALS.md, API.md, FLOWS.md, BLUEPRINT.md, UI.md, queries.cypher, the rest. Record the conflict in `docs/TASKS.md` under "Questions for the owner".

Naming rule (avoid clashes): flows are `F0`-`F19`, goals `G001`-`G140`, requirement rows `H1`-`H20` and `S1`-`S27`, query names use the prefixes `SCHEMA`, `I`, `V`, `W`, `D`, `L`, `P`, `R1`, `A`, `T`, `K`, `X` and never start with F, G, H or S.

## 0.1 FalkorDB is the heart (prime constraint)
The sponsor is FalkorDB. The FAQ and rule 2 require it to be the primary graph database supporting a central part of the product; rule 3 disqualifies a graph that is decoration. In Landfall:
- **Every answer is a FalkorDB query.** Identity and listing gate (V1), scope proof (V2), the verdict class itself (V4, a Cypher `CASE` over the version timeline), upstream sources and copy lag (V5, D3), who must act (W1, W2), fan-out (D1, D2), latency (D4), supply families (R1 `algo.WCC`), source hubs (A1 `algo.pageRank`), chokepoints (A2 `algo.betweenness`), label families (A3 `algo.labelPropagation`), upstream closure (W4 `algo.BFS`) and every tenant memory read (T3, T6, T7, T12, T15) run in FalkorDB. There is no other database. Caches hold raw HTTP responses from DailyMed and openFDA only, never answers.
- **Every memory write is a FalkorDB write**: label versions, checks, confirmations, landing events, rulings, bases, decisions, events, tasks, drafts, conversations.
- **We use the sponsor's headline features on screen**: multi-graph tenancy (hub + one graph per organisation + per-visitor sandboxes via `GRAPH.COPY` on one instance), Cypher with bounded multi-type variable-length paths, `shortestPath` as a no-path proof, six graph algorithms (BFS, shortest path, PageRank, betweenness centrality, connected components, community detection), MCP, and FalkorDB Browser (README walkthrough).
- **Proof**: goal G046 stops FalkorDB and shows `/api/landed` returns 503 instead of an answer.

---

## 1. What we are building, in one paragraph

Landfall proves whether a known drug-safety fact actually **landed** on the label of the bottle someone holds, and **who must act** if it did not. A pharmacist, a pharmacy-dispensing agent or a hospital formulary team asks: **"Does the label for this NDC carry the current FDA boxed warning, and if not, who has to fix it?"** Landfall resolves the NDC to its label of record (the DailyMed SPL that an active NDC Directory listing points to), walks the typed chain from the reference drug's labeling change through generic applications and repackager source NDCs to that product, reads the label's real version history, and returns a verdict with the path, the version and date evidence, the upstream source that already carried the warning, and the party able to act. It remembers every verdict per organisation, shares pharmacist-confirmed checks across organisations without revealing who holds what, and when DailyMed publishes a new version that carries the warning, the gap closes, the landing latency is recorded and every dependent ruling reopens for its owner.

**Scope decision (from the final panels):** drugs only, DailyMed and openFDA, montelukast as the hero molecule and zolpidem as the second molecule activated live by fact verification. Aviation (NTSB, FAA AD, FAA registry) is an optional add-on adapter, cut first (section 18).

### The three things a judge must see
1. **Judge input, real finding.** Type NDC `68071-3355-9` (or pick any of the 69 montelukast labels of record). Verdict: **NOT LANDED (revised without it)**. Path `68071-3355 -> ANDA202717 -> NDA020829 (Singulair)`. The DailyMed label of record (version 5, 11 Jul 2024) lacks a coded boxed-warning section and the boxed-warning text; it was revised twice after FDA approved the warning on 29 Apr 2020. Its source product `16729-119` has carried the warning in a coded section since version 14 (21 May 2021): the label was revised 1,147 days after its source already carried it. Who can act: the repackager labeler of record, by updating to the current source label; FDA as the regulator. Census on screen: of 69 labels of record, 54 carry it coded, 2 carry the text uncoded, 9 were revised after the warning without it, 4 were never revised since.
2. **The loop closes, from real history.** The replay scrubber walks a real DailyMed version history: the Accord label (ANDA holder) version 12 (5 Mar 2021) lacks the warning, version 14 (21 May 2021) carries it coded: NOT LANDED flips to LANDED, a `LandingEvent` records 387 days of latency, and every repackager downstream of that source gets a task. A second replay: AvKARE versions 17-20 lack it, version 21 (17 Nov 2025) carries the text but not as a coded section, so machine readers such as openFDA still miss it. The live Watcher is armed on the 13 open gaps.
3. **Compounding and infrastructure.** A pharmacy agent (our example MCP client) asks `landed("68071-3355-9")` before printing patient information and routes the result to a human. Northgate (fictional hospital, strict mode: only pharmacist-confirmed red flags) shows UNKNOWN for a NuCare NDC; Bayview's pharmacist (fictional chain) confirms the absence from the shared check queue; the check reaches tier 2, Northgate's verdict flips and a task lands with its pharmacist. Two FalkorDB graphs side by side; the hub stores only a salted hash.

### Tracks
- **Primary: Track 1, Agents That Act on Connected Data.** Multi-hop typed scope (reference drug -> generic application -> source NDC -> repackager NDC), the verdict decided in Cypher, graph algorithms as MCP tools (BFS, shortest path, PageRank, betweenness, WCC, label propagation), MCP tool selection by other agents, actions (tasks, alternatives, draft notices behind approval), explainable results with path and version evidence.
- **Also name: Track 2** (one graph per organisation and per sandbox; Watcher -> Prover -> owner handoffs through Task nodes with leases; episodic, semantic and procedural memory; conversation history) **and Track 3** (who owns which formulary decision; every decision traced to the ruling, the SPL version, the section code and the check tier; knowledge kept current by reopen-on-change).
- Why Track 1 is primary: the product is an agent that acts on a typed, multi-hop public graph and is called by other agents; Tracks 2 and 3 are native consequences of per-organisation rulings, not the core.

---

## 2. Non-negotiables (rules, ethics, wording)

1. **FalkorDB is load-bearing.** Every verdict comes from Cypher in FalkorDB (V1, V2, V4). If FalkorDB is removed, the product must not work. Never compute scope, timelines or verdict classes in Python and only mirror them into the graph.
2. **Deterministic code and Cypher decide; an LLM never does.** The Matcher is deterministic (section code + phrase key). An LLM may only (a) phrase an explanation from the evidence it is given, (b) phrase a draft notice, (c) choose one of eight templated questions in the Ask add-on. With no LLM key, templates are used and everything works.
3. **Human approval before any outward action, and Landfall never sends anything.** Draft notices to a labeler or a MedWatch report are text a human approves and then copies; the system has no email, fax or posting integration. Internal actions inside a tenant graph (tasks, holds on a formulary entry) also require a named person's click.
4. **Append-only history.** Label versions, checks' confirmers, landing events, rulings, bases, decisions and events are never edited in place. A changed answer is a new ruling that supersedes the old one; a reopen is an event node. The only in-place updates are a check's tier, confirmers and dispute flag (P1, P3, I10), and each change is also recorded as a tenant event.
5. **Wording (legal safety).** Say "the DailyMed label of record (version N, date) lacks a coded boxed-warning section", "carries the boxed-warning text but not as a coded section", "was revised after the warning was added to the reference label without it", "the party able to update this label". Never "non-compliant", "violation", "violating", "illegal", "negligent", "failed to", "unsafe", "dangerous", "stale label" or anything that accuses a named labeler or person. Never imply FDA or NLM endorsement. Every verdict shows: "Automated screening of public FDA and NLM data. Not medical, legal or regulatory advice. Not endorsed by FDA or NLM." Red verdicts are shown only for labels of record behind an active NDC Directory listing (the listing gate).
6. **Data.** Public US-government data only: DailyMed web services and archived SPL files (NLM), openFDA NDC Directory, drug label and Drugs@FDA endpoints (FDA). openFDA content is CC0 (verified); SPL text is submitted by labelers and may carry third-party rights, so **the repo and the graph store no label text**: identifiers, dates, section codes, phrase-key hashes and the Matcher's result only. The UI links to the rendered DailyMed page for any text. Demo organisations, people and inventories are fictional and labelled "(fictional)".
7. **README must include** (rule 10): setup, the graph data model, the Cypher queries and algorithms, the demo video link, the live URL, tracks entered, and AI-assistance disclosure (rule 11). Everyone can explain the model and queries (rule 12).

---

## 3. Architecture

```
               Vercel (Next.js web app)               Other agents (pharmacy agent example, Claude Code, Cursor)
                        |                                              |  MCP (streamable HTTP)
                        v                                              v
        +------------------------------------------- Railway (always-on) ----------------------------------+
        |  services/api  (Python 3.12, FastAPI)                                                              |
        |   - REST API (/api/*)                 - MCP server (/mcp)                                          |
        |   - Agents: Scout, Matcher, Prover, Watcher, Notifier, Publisher (in-process workers)              |
        |   - APScheduler: Watcher every WATCH_INTERVAL_MINUTES, sandbox cleanup every 15 min                |
        |   - Source clients: DailyMed v2 + archives, openFDA (ndc, label, drugsfda); httpx + disk cache     |
        +----------------------------------------------------------------------------------------------------+
                        |  falkordb-py (Redis protocol)
                        v
        FalkorDB (Docker image falkordb/falkordb on Railway with a persistent volume)
          graph "hub"                public layer: molecules, applications, parties, SPL sets and versions,
                                     products, packages, safety facts, checks, landing events
          graph "tenant_bayview"     fictional pharmacy chain: sites, people, stock items, rulings, tasks
          graph "tenant_northgate"   fictional hospital formulary team
          graph "sbx_<id>"           per-visitor sandbox copied from a tenant (GRAPH.COPY), deleted after 2 h
          graph "hubr_<id>"          replay copy of the hub for the loop-closure replay (F11), deleted after 2 h
```

### Hosting decision (verified 17 Oct 2026; same as ModelBrain)
- **Web app on Vercel** (Hobby). Vercel cannot host FalkorDB and Hobby cron runs once a day, so Vercel serves only the Next.js frontend; it calls the API over HTTPS.
- **API, agents and MCP on Railway** (always-on; avoid sleeping free tiers: judges may open the link days later).
- **FalkorDB on Railway in Docker** (`falkordb/falkordb:latest`, persistent volume, `appendonly yes`, `requirepass`, private networking only). Do **not** use the FalkorDB Cloud free tier for the judged deployment (100 MB, no backups, stops after 1 day idle, deleted after 7 days idle). FalkorDB Cloud Startup is the managed fallback.
- Expected cost for the judging window: about $5 to $15 on Railway.
- Keep `docker compose up` working locally (rules accept full local setup).

### Tech choices
| Layer | Choice | Why |
|---|---|---|
| Graph | FalkorDB 4.x via `falkordb` Python client | the sponsor; multi-graph tenancy; Cypher; algorithms |
| API | FastAPI, pydantic v2, httpx, APScheduler, slowapi | typed, async HTTP to DailyMed and openFDA |
| XML | `lxml` (SPL parsing: sections by LOINC code, `asEquivalentEntity` source NDCs) | SPL is HL7 v3 XML |
| MCP | official `mcp` Python SDK **pinned `mcp>=1.10,<2`** (verified 1.30.0), `FastMCP("landfall", stateless_http=True)`, mounted with `app.mount("/", mcp.streamable_http_app())` after all FastAPI routes, lifespan runs `mcp.session_manager.run()`; endpoint `/mcp` | other agents connect over HTTP. mcp 2.x renamed FastMCP; do not upgrade during the event |
| LLM (optional) | OpenRouter (`OPENROUTER_API_KEY`, `LLM_MODEL`) for explanation phrasing, draft phrasing, the Ask router and the eval baseline only | template fallback when no key |
| Web | Next.js (App Router, TypeScript), Tailwind, `react-force-graph-2d` | path and fan-out views |
| Tests | pytest with a FalkorDB service container and the golden fixture `data/fixtures/hub_montelukast.json`; Playwright smoke | golden verdicts must not regress |

Verified on 18 Oct 2026 against `falkordb/falkordb:latest` (module version 42201) with `redis-cli GRAPH.QUERY ... "CYPHER k=v ..."`: every query in `docs/queries.cypher` runs against the real montelukast fixture and both demo tenants, including multi-type bounded paths (`SOURCED_FROM|UNDER|REFERENCES*1..5`), multi-type `shortestPath` (NULL when no path), `algo.BFS(node, depth, NULL)` (follows every outgoing type), `algo.WCC`, `algo.pageRank`, `algo.betweenness`, `algo.labelPropagation`, `percentileDisc`, `FOREACH`+`CASE` conditional writes and `GRAPH.COPY` (fails if the destination exists). MERGE on indexed ids gives idempotent writes. The MCP mount above was verified with mcp 1.30.0 (`initialize`, `tools/list`, `tools/call`) during the ModelBrain build.

FalkorDB container facts (verified): data directory `/var/lib/falkordb/data`; Redis options via `REDIS_ARGS` (`--appendonly yes --requirepass <password>`); module options via `FALKORDB_ARGS`, image default `MAX_QUEUED_QUERIES 25 TIMEOUT 1000 RESULTSET_SIZE 10000`. **Set `TIMEOUT 5000`** (the 1 s default is too tight for ingest batches and the algorithm calls). The image starts with no password and `--protected-mode no`: on Railway always set `requirepass` and keep FalkorDB on private networking.

---

## 4. Data sources (all public, US government)

All endpoints were exercised live on 17-18 Oct 2026 unless marked "verify". Field names only; no label text is copied.

| Need | Endpoint | Verified fields and notes |
|---|---|---|
| SPL sets for a molecule | `GET https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name={name}&pagesize=100&page={n}` | `data[]: {setid, spl_version, title, published_date ("Jul 11, 2024")}`; `metadata: {total_elements, total_pages, current_page, next_page_url, db_published_date}`. Montelukast: **116 sets** |
| SPL sets for an NDC | `GET .../v2/spls.json?ndc={package or product NDC}` | same shape; used for on-demand ingest of a judge's NDC |
| Current SPL XML | `GET .../v2/spls/{setid}.xml` | header `<id root=DOC_ID>`, `<setId root>`, `<versionNumber value>`, `<effectiveTime value=YYYYMMDD>`; sections `<code code="34066-1" codeSystem="2.16.840.1.113883.6.1" displayName="BOXED WARNING SECTION">` (LOINC); per product `<manufacturedProduct>` with own NDC `<code code="68071-3355" codeSystem="2.16.840.1.113883.6.69">` and source NDC `<asEquivalentEntity classCode="EQUIV"><definingMaterialKind><code code="16729-119" codeSystem="2.16.840.1.113883.6.69"/>`; labeler `<representedOrganization><id extension=DUNS><name>`; approval `<approval><id extension="ANDA202717">` (verify per SPL) |
| Version history | `GET .../v2/spls/{setid}/history.json` | `data.history[]: {spl_version, published_date}`; `data.spl: {setid, title}`. Note: a `?version=` parameter on `{setid}.xml` is ignored (verified) |
| Archived versions | `GET https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}` (HTML, modal "label archives") then `GET .../dailymed/getArchivalFile.cfm?archive_id={id}` | the HTML lists `getArchivalFile.cfm?archive_id=N` next to "{date} {version}"; the file is a ZIP holding the SPL XML of that version (verified: NuCare set 549f1d1a, 5 versions, archive ids 270734..809304) |
| NDCs of a set | `GET .../v2/spls/{setid}/ndcs.json` | `data: {spl_version, ndcs:[{ndc}], published_date, title, setid}` |
| Active listing (the gate) | `GET https://api.fda.gov/drug/ndc.json?search=product_ndc:"{ndc}"` (also `generic_name:"{molecule}"&limit=1000`) | `product_ndc, labeler_name, application_number, marketing_category, dosage_form, active_ingredients[{name,strength}], listing_expiration_date (YYYYMMDD), marketing_start_date, spl_id (document id of the label of record), packaging[{package_ndc, description}], openfda.spl_set_id (often missing)`. Montelukast: **118 listings** |
| Labels (fast path and baseline) | `GET https://api.fda.gov/drug/label.json?search=openfda.generic_name:"{molecule}"&limit=100&skip=N` | `set_id, id, version, effective_time, boxed_warning (present only when the SPL has a coded boxed-warning section), openfda.{application_number, manufacturer_name, product_ndc, package_ndc, original_packager_product_ndc, spl_id, spl_set_id, generic_name, brand_name, unii}`. Montelukast: **64 labels** (openFDA is a subset of DailyMed) |
| Applications and holders | `GET https://api.fda.gov/drug/drugsfda.json?search=application_number:{id}` (or `openfda.generic_name:"{m}"`) | `application_number, sponsor_name, products[{brand_name, dosage_form, marketing_status, reference_drug ("Yes"/"No"), reference_standard, active_ingredients}], submissions[{submission_type, submission_number, submission_status, submission_status_date, submission_class_code ("LABELING"), application_docs[{type, url}]}]`. Search by generic name misses applications without an `openfda` block (ANDA203037, ANDA204290, ANDA208621, ANDA204604): always fetch every application number referenced by a product |
| Rate limits | openFDA: 240 requests/min and 1,000/day per IP without a key; 120,000/day with a free key (verified on open.fda.gov). DailyMed: no published limit; we cap ourselves at `DAILYMED_RPS=2` and cache | always send `OPENFDA_API_KEY` in production; cache every response |

**Licensing and terms (verified 18 Oct 2026).** openFDA: "unless otherwise noted, the content, data, documentation, code ... is public domain and made available with a Creative Commons CC0 1.0 Universal dedication"; the openFDA terms note that some works made available by FDA come from private entities and may carry third-party rights, and the API disclaimer says not to rely on openFDA for medical decisions. DailyMed is an NLM service; NLM's web policy says users must determine copyright status of material that is not in the public domain. Our response: store no label text, link to DailyMed for reading, show the disclaimer, never imply endorsement. (`docs/OPEN_POINTS.md` lists the NLM copyright page as JS-rendered and not fully read.)

Ingestion caps: per molecule all DailyMed sets (montelukast 116, zolpidem about 130 expected); archived versions are fetched only for versions published on or after (fact issued - 365 days) and for the current version; at most 2 requests per second to DailyMed; disk cache for XML and ZIPs keyed by `setid@version` (immutable), 6 h for list endpoints.

### Verified demo facts (live checks 17-18 Oct 2026; DailyMed db published 16 Oct 2026, openFDA last_updated 2026-10-16)
- **Fact.** Drugs@FDA: NDA020829 (SINGULAIR tablets, ORGANON, reference drug and reference standard) supplement 73, class LABELING, approved **2020-04-29**; NDA020830 (chewable) S-75 and NDA021409 (granules) S-51 approved the same day. FDA's Drug Safety Communication of 4 Mar 2020 announced the boxed warning. Phrase key: `WARNING: SERIOUS NEUROPSYCHIATRIC EVENTS`; section LOINC `34066-1`.
- **Census.** DailyMed lists 116 montelukast SPL sets; **69** are the label of record for an active NDC Directory listing (`spl_id` equals the set's current document id and `listing_expiration_date` is in the future); the other **47** are not (old or superseded SPLs: without the gate they would be false reds, e.g. Aurobindo set `7636a692` from 2014 lists NDC 65862-574, but the listing points to set `ba42b0a9`). openFDA has 64 of the 69; the 5 others (Unichem, PD-Rx, Cardinal Health, Amneal, RemedyRepack, all published Sep 2026) are DailyMed-only and all carry the coded section.
- **Verdicts on the 69 (fixture run through V4, grace 30 days):** LANDED 54; LANDED_UNCODED 2 (AvKARE set `ed2caffa` v22, AvPAK set `2f90a573` v8: boxed-warning text present, no `34066-1` section, so openFDA has no `boxed_warning` field); NOT_LANDED_REVISED 9 (Proficient Rx 6, NuCare 3); NOT_LANDED_UNREVISED 4 (Proficient Rx, current versions from Oct-Nov 2019). All 13 lacking labels are the label of record for active listings (listing expiration 2026-12-31 or 2027-12-31).
- **Hero NDC.** `68071-3355-9` -> product `68071-3355` (NuCare, ANDA202717, active listing to 2026-12-31) -> set `549f1d1a-81f5-29f5-e054-00144ff8d46c`: v4 (2021-02-16) and v5 (2024-07-11) lack the warning. Source NDC `16729-119` (Accord, set `6eea668f`) first carries it coded in v14 (2021-05-21). Copy lag 1,147 days.
- **Copy lag (D3) finds 14 (repackaged product, source) pairs** whose label was revised after its source carried the warning yet lacks it, e.g. AvKARE 42291-622 (1,697 days), NuCare 68071-4034 (source Macleods 33342-102, 1,509 days), NuCare 68071-4047 (1,155), AvPAK 50268-573 (924), Proficient Rx 63187-550 (487).
- **Closed loops in real history.** Accord `6eea668f` (ANDA holder): v12 2021-03-05 ABSENT -> v14 2021-05-21 CARRIES_CODED (latency 387 days). AvKARE `ed2caffa`: v17-v20 (2022-01-14 .. 2025-01-13) ABSENT -> v21 2025-11-17 CARRIES_UNCODED. AvPAK `2f90a573`: v6, v7 ABSENT -> v8 2025-11-17 CARRIES_UNCODED. Bryant Ranch `3ff4100f`: v1 2020-08-19 ABSENT -> v2 2022-02-08 CODED. American Health Packaging `fb1b2e4e`: v5 2020-10-27 ABSENT -> v6 2021-12-13 CODED. Preferred `09b0bc9e`: v1 2020-04-30 ABSENT (inside grace) -> v2 2021-08-03 CODED.
- **Fastest landings (D4):** Aurobindo 19 days, Lannett 23, Ajanta 27, Macleods 33, Sandoz 36, Dr. Reddy's 43.
- **Authority cases.** (a) Proficient Rx `63187-626` (set `9705627c`, v3 2019-11-21, NOT_LANDED_UNREVISED) is sourced from West-Ward `0143-9650`, whose SPL (set `43b80e54`, 2015) has **no active listing**; Drugs@FDA now names **PHARMOBEDIENT** as holder of ANDA203037 and DailyMed has no Pharmobedient montelukast label: no upstream label of record exists to copy from (AUTHORITY_GAP, section 6.3). (b) Montelukast granules: the reference drug NDA021409 is **Discontinued** and Drugs@FDA lists **ANDA203438 (Ajanta) as reference standard** (W2). (c) Ajanta ANDA203328 and ANDA203432 are Discontinued while Proficient Rx listings under them stay active. (d) Zolpidem: Drugs@FDA lists **COSETTE** as holder of NDA019908 (AMBIEN); DailyMed has an Ambien set by Sanofi-Aventis (v26, 2025-04-15) and one by Cosette (v1, 2025-02-07): holder succession.
- **Second molecule (zolpidem).** Ambien (NDA019908) supplement 46, LABELING, approved 2019-08-18 (letter also names NDA021774 S-27); Ambien SPL v16 (Feb 2019) has no boxed warning, v17 (published 2019-09-03, effective 2019-08-29) has a coded `34066-1` section with the phrase "complex sleep behaviors". openFDA has 116 zolpidem labels; 17 lack the phrase, 13 of them effective on or after 2019-05-01 (Proficient Rx 7, Aphena 4, NuCare 3, others). Shipped as `UNVERIFIED` so the demo can show a pharmacist verifying it (F16).
- **Supply graph (fixture):** A1 PageRank top sources: Camber 31722-726 (8 direct repackagers), Accord 16729-119 (6), Unichem 29300-220 (4). A2 betweenness (exact; samplingSize above the node count): ANDA202843 (Hetero, 24), ANDA200405 (Lannett, 20), ANDA204093 (Hetero, 12). R1 WCC: the Accord family has 7 products, 3 lacking.
- **Crowding (GitHub, 18 Oct 2026):** 0 repositories for `falkordb` + any of: drug label, dailymed, openfda, boxed warning, repackager, pharmacovigilance, drug safety, fda, ndc. The nearest FalkorDB projects work on drug shortages, repurposing and prescribing cascades; none test label landing (details in docs/OPEN_POINTS.md, not for public docs).

---

## 5. Graph model

FalkorDB cannot query across graphs, so the app joins graphs in code: the **hub** answers "what does the public record say about this NDC", the **tenant** answers "who holds it here, what did we decide, who owns it".

### 5.1 Graph `hub` (public facts only)

Nodes
| Label | Key properties |
|---|---|
| `Molecule` | `key` (e.g. `montelukast`), `name`, `unii` |
| `Application` | `id` (`NDA020829`, `ANDA202717`), `kind` (NDA, ANDA, BLA), `sponsor` (Drugs@FDA string), `dosage_forms` (list), `marketing_status`, `reference_drug` (bool), `reference_standard` (bool), `updated_at` |
| `Party` | `id` (`sponsor:<slug>`, `labeler:<slug>`, `agency:fda`), `name`, `kind` (SPONSOR, LABELER, REGULATOR), `duns` (optional). Slug rule in FLOWS F2.4 |
| `LabelSet` | `set_id` (DailyMed setid), `title`, `molecule_key`, `current_version`, `current_doc_id`, `current_published`, `current_published_d`, `label_of_record` (bool, I13), `ingested_at` |
| `LabelVersion` | `id` (`<set_id>#v<version>`), `set_id`, `version`, `doc_id` (known for the current version), `effective` (YYYYMMDD string), `published` (ISO), `published_d`, `archive_id`, `labeler_name`, `observed_at` |
| `Product` | `ndc` (product NDC `68071-3355`), `labeler_name`, `molecule_key`, `dosage_form`, `strength`, `marketing_category`, `listing_spl_id`, `listing_expiration_d`, `in_ndc_directory` |
| `Package` | `ndc` (package NDC `68071-3355-9`, what is printed on the bottle), `description` |
| `SafetyFact` | `id` (`montelukast_bw_2020`), `molecule_key`, `kind` (BOXED_WARNING), `title`, `issued`, `issued_d`, `section_code` (`34066-1`), `phrase_key`, `phrase_key_version`, `source_url`, `status` (UNVERIFIED, ACTIVE, RETIRED), `verifiers` (salted org hashes), `verified_at` |
| `LandingEvent` | `id`, `kind` (LANDED, LANDED_UNCODED), `published`, `latency_days`, `observed` (history, live, replay), `at` |
| `TenantRegistry` / `Sandbox` / `FanOut` | names of fixed tenants; sandbox names with `expires_at` (no tokens); fan-out audit records |

Relationships (all point upstream, from the thing held toward the reference drug)
| Type | From -> To | Properties |
|---|---|---|
| `CONTAINS` | `Application` -> `Molecule` | |
| `REFERENCES` | `Application` (ANDA) -> `Application` (reference drug) | `source: derived_same_molecule_and_form` (I12) |
| `HOLDS` | `Party` -> `Application` | `from_d`, `to_d` (null = current), `source` (drugsfda, spl_publisher) |
| `PUBLISHES` | `Party` -> `LabelSet` | `from_version`, `to_version` |
| `HAS_VERSION` | `LabelSet` -> `LabelVersion` | |
| `DESCRIBES` | `LabelSet` -> `Product` | |
| `UNDER` | `Product` -> `Application` | |
| `SOURCED_FROM` | `Product` (repackaged) -> `Product` (source) | `source` (spl_equivalent, openfda), `observed_at` |
| `PACKAGE_OF` | `Package` -> `Product` | |
| `ISSUED_ON` | `SafetyFact` -> `Application` | `supplement`, `approved` |
| `ABOUT` | `SafetyFact` -> `Molecule` | |
| `CHECKED` | `LabelVersion` -> `SafetyFact` | `result` (CARRIES_CODED, CARRIES_UNCODED, ABSENT), `method` (matcher_xml, matcher_openfda_json, human), `tier`, `phrase_key_version`, `at`, `confirmations`, `confirmers` (salted hashes), `disputed`, `dispute_result` |
| `FOR_SET`, `OF_FACT`, `AT_VERSION` | `LandingEvent` -> `LabelSet` / `SafetyFact` / `LabelVersion` | |

Check tiers (trust grows with use; this is the compounding layer)
| Tier | Meaning | Set by |
|---|---|---|
| 0 | reserved: heuristic match needing review (phrase found but section structure unusual) | Matcher |
| 1 | deterministic Matcher result on the SPL XML (or on openFDA JSON for the fast path) | Matcher (I10) |
| 2 | confirmed by one organisation's pharmacist looking at the rendered DailyMed version | Publisher (P1) |
| 3 | confirmed by two or more independent organisations | Publisher (P1) |
Default verdicts use tier >= 1. **Strict mode** requires tier >= 2 for an ABSENT result to count: a red verdict needs a pharmacist confirmation, otherwise UNKNOWN (a carrying result counts from tier 1, because a matched phrase cannot accuse anyone). A disagreement marks the check `disputed` and every verdict on it becomes UNKNOWN until an admin resolves it (P3).

### 5.2 Graph `tenant_<slug>` (private per organisation; also the sandbox template)

Nodes
| Label | Key properties |
|---|---|
| `Org` | `slug`, `name` ("(fictional)"), `kind` (PHARMACY_CHAIN, HOSPITAL), `state` |
| `Team`, `Site` | `id`, `name`, (`kind` for sites: RETAIL, INPATIENT, OUTPATIENT) |
| `Person` | `id`, `name` ("(fictional)"), `role` (PHARMACIST_IN_CHARGE, FORMULARY_PHARMACIST, P_AND_T_CHAIR, QA_LEAD, BUYER) |
| `StockItem` | `id`, `ndc` (package NDC), `product_ndc`, `display_name`, `qty_band` |
| `FormularyEntry` | `id`, `molecule_key`, `form`, `strength`, `status` (PREFERRED, ALLOWED, HOLD, REMOVED), `title` |
| `Ruling` | `id`, `verdict`, `fact_id`, `set_id`, `strict`, `created_at`, `as_of_d`, `explanation`, `who_must_act` (JSON string) |
| `Basis` | `id`, `kind` (TARGET_VERSION, SOURCE_VERSION, FACT, SCOPE_PATH), `fact_id`, `set_id`, `version_id`, `doc_id`, `published`, `section_code`, `check_result`, `check_tier`, `path` |
| `Decision` | `id`, `kind` (FORMULARY_STATUS, SUPPLIER_SWITCH, PATIENT_INFO), `value`, `at`, `note` |
| `Event` | `id`, `kind` (REOPENED, SUPERSEDED, APPROVED, REJECTED, CONFIRMED_CHECK, FACT_VERIFIED, NOTICE_APPROVED, REVIEWED), `at`, `reason` |
| `Task` | `id`, `kind` (REVIEW_RULING, APPROVE_RULING, PHARMACIST_REVIEW, CONFIRM_CHECK, APPROVE_NOTICE), `state` (OPEN, CLAIMED, AWAITING_APPROVAL, DONE), `lease_until`, `created_by_agent`, `proposed_verdict`, `proposed_ruling_json`, `payload_json` |
| `Draft` | `id`, `kind` (LABELER_NOTICE, MEDWATCH, INTERNAL_MEMO), `to_party`, `title`, `body`, `ready_to_copy` |
| `Conversation`, `Turn` | `id`, `channel` (mcp, web); `tool`, `args_json`, `verdict`, `at` |
| `Playbook` | `kind` (one per task kind), `steps` (list): procedural memory |

Relationships: `(Team)-[:PART_OF]->(Org)`, `(Site)-[:PART_OF]->(Org)`, `(Person)-[:MEMBER_OF]->(Team)`, `(Person)-[:RESPONSIBLE_FOR {from, until}]->(Site)`, `(Person)-[:OWNS {from, until}]->(FormularyEntry)`, `(StockItem)-[:AT]->(Site)`, `(StockItem)-[:LISTED_AS]->(FormularyEntry)`, `(Ruling)-[:FOR]->(StockItem)`, `(Ruling)-[:RESTS_ON]->(Basis)`, `(Ruling)-[:SUPERSEDES]->(Ruling)`, `(Decision)-[:BASED_ON]->(Ruling)`, `(Decision)-[:ON]->(FormularyEntry)`, `(Person)-[:DECIDED]->(Decision)`, `(Event)-[:ON]->(Ruling)`, `(Person)-[:SIGNED]->(Event)`, `(Task)-[:ABOUT]->(Ruling)`, `(Task)-[:ASSIGNED_TO]->(Person)`, `(Task)-[:HANDED_OFF_FROM]->(Task)`, `(Task)-[:FOLLOWS]->(Playbook)`, `(Draft)-[:FOR_TASK]->(Task)`, `(Conversation)-[:HAS_TURN]->(Turn)`, `(Turn)-[:PRODUCED]->(Ruling)`.

Memory types (Track 2): episodic = rulings, events, decisions, turns; semantic = the hub (facts, versions, checks, supply chain); procedural = `Playbook` nodes followed by tasks.

### 5.3 Privacy rule for compounding
The hub never stores which organisation holds which NDC. Confirmations and fact verifications reach the hub only through the Publisher as `sha256(PUBLISHER_SALT + tenant_name)[:16]`. The Scout ingests the whole molecule regardless of holdings, so the presence of any label in the hub reveals nothing. A test asserts no hub property contains a tenant name (G106).

---

## 6. Core logic

### 6.1 Matcher (deterministic carry check; `app/engine/matcher.py`)
Input: one SPL XML (a version) and one ACTIVE or UNVERIFIED `SafetyFact`.
1. Parse with lxml (namespace `urn:hl7-org:v3`). Collect sections with `code/@code`.
2. Normalise text: concatenate text nodes, NFKC, collapse whitespace, upper-case. Never store it.
3. `in_coded` = some section with code == `fact.section_code` (`34066-1`) whose normalised text contains the normalised `phrase_key`.
4. `in_text` = the normalised full document text contains the phrase key.
5. Result: `CARRIES_CODED` if `in_coded`; else `CARRIES_UNCODED` if `in_text`; else `ABSENT`. Tier 1, method `matcher_xml`, `phrase_key_version` from the fact.
6. openFDA fast path (`method: matcher_openfda_json`, used by the eval baseline and for bootstrapping when DailyMed is slow): `CARRIES_CODED` if `boxed_warning` exists and contains the phrase; `CARRIES_UNCODED` if the phrase appears in any other field; else `ABSENT`. The XML result always replaces a JSON result for the same version (I10 keeps tier 1).
7. Store with I10. A changed result on a tier >= 2 check marks it disputed and opens CONFIRM_CHECK tasks (F8.6).

### 6.2 Verdict (`app/engine/verdict.py`; the class is decided in V4)
Input: `ndc` (package or product), optional `fact_id`, `as_of` (default today), `strict` (min tier 2), optional tenant context.
1. **Identity (V1).** No product -> try on-demand ingest (F2.7); still none -> `UNKNOWN` with reason `NDC_NOT_FOUND`.
2. **Facts (V3).** ACTIVE facts for the product's molecule (or the given `fact_id`). None -> empty `results` with the message "No verified safety fact for <molecule> in Landfall yet."
3. For each fact:
   1. **Scope (V2).** If every row has `no_path = true`: `NOT_IN_SCOPE` when scope is complete (the product has no application and a non-finished marketing category such as BULK INGREDIENT, or its application exists with `kind` set, or its molecule differs); otherwise `UNKNOWN` with reason `SCOPE_UNRESOLVED`. The no-path proof lists what was searched (types, depth 5, target applications).
   2. **Listing gate (V1).** `listing_active = false` -> `NOT_ASSESSED_INACTIVE_LISTING`. `record_sets` empty while listing active -> ingest the listing's SPL (F2.7) and retry once; else `UNKNOWN` with reason `LABEL_OF_RECORD_NOT_INGESTED`. In replay mode (`as_of` in the past) the gate is skipped and the response says so (listing history is not public).
   3. **Timeline and class (V4)** on the record set with `as_of_d`, `min_tier` (1 or 2) and `GRACE_DAYS` (30): `LANDED`, `LANDED_UNCODED`, `NOT_LANDED_REVISED` (current ABSENT and at least one version published on or after issued + grace), `NOT_LANDED_UNREVISED` (current ABSENT, no such version), `UNKNOWN` (no checked current version at the tier, or disputed).
   4. **Upstream (V5).** Each source's label of record and first carrying version; `copy_lag_days` = (latest ABSENT revision of the target after that date) - (source first carry), shown when positive.
   5. **Who must act (6.3)** and **alternatives (V6)** for NOT_LANDED_* and LANDED_UNCODED.
4. **Explanation**: template text from the evidence (or LLM phrasing of the same evidence, 6 s timeout, never changes a field).
5. **Persist** (only with tenant + stock item): T1 ruling with bases (TARGET_VERSION, SOURCE_VERSION when upstream exists, FACT, SCOPE_PATH); T2 + SUPERSEDED event when replacing; 409 on stale `expected_ruling_id`.

Verdict classes and the one-line copy are in `docs/UI.md` "Verdict copy". Response type `Landing` is in `docs/API.md`.

### 6.3 Who must act (`app/engine/authority.py`; rows from W1 and W2, rules in code)
W1 returns one row per hop from the held product up its source chain (hop 0 = the held product): label set, publisher, application, application status and current holder, reference drug, its status and holder. Rules, first match wins, for a NOT_LANDED_* or LANDED_UNCODED verdict:
1. **AUTHORITY_GAP** (the orphan case): some hop > 0 has no active listing or no label of record, and no other hop above it has a label that carries the fact. Primary: the current application holder (W1 `application_holder`) "as holder of <application>; no DailyMed label of record was found for it"; also FDA ("the regulator; can require safety labeling changes"). Flag `authority_gap: true`.
2. **SOURCE_CARRIES**: hop 0 lacks the fact, a source hop carries it (V5 first carry exists). Primary: the hop-0 publisher ("labeler of record for this repackaged product; its source label carries the warning since <date>"). Secondary: none. Oversight: FDA.
3. **SOURCE_LACKS**: hop 0 and every source lack it. Primary: the publisher of the top-most source label; secondary: the hop-0 publisher. Oversight: FDA.
4. **OWN_LABEL**: no source hops. Primary: the hop-0 publisher; if it differs from the application holder, the holder is secondary.
5. **REFERENCE_DISCONTINUED** (annotation, any rule): the reference drug's `marketing_status` is Discontinued; add the reference standard from W2 ("FDA lists <application> as reference standard") and FDA.
For LANDED_UNCODED the action text is "re-code the boxed warning as a boxed-warning section so machine readers see it". Never phrase as blame; the copy is in UI "Who can act".

### 6.4 Graph-wide views (the work a per-label script cannot do)
- **Fan-out (D1)**: every label of record in scope of a fact through any number of application and source hops (bounded 5), with its current check; drives the census and the `/facts/[id]` page.
- **Downstream (D2)**: when a source label changes, which repackaged products copy it (bounded 3 hops).
- **Copy lag (D3)**: (repackaged product, source) pairs where the repackaged label was revised after the source already carried the fact, yet lacks it; a temporal comparison along `SOURCED_FROM`.
- **Latency (D4)** per publisher, for label sets that existed before the fact; **landing ledger (D6)**.
- **Supply families (R1, algo.WCC)** over `SOURCED_FROM` and `UNDER`, with carrying and lacking counts; **source hubs (A1, algo.pageRank)**; **chokepoints (A2, algo.betweenness)**; **label families (A3, algo.labelPropagation)**; **upstream closure (W4, algo.BFS)**; **open gaps across all facts for a publisher (W3)**.

### 6.5 Watcher, reopen-on-change and the closed loop (`app/agents/watcher.py`)
1. Watched sets = L3 (all label-of-record sets in scope of active facts) + every set behind any tenant stock item + their source sets (V5); cap 200 per run; rotate.
2. Poll `history.json` per set; if `spl_version` > `LabelSet.current_version`: fetch the new current XML, I5 (new version), I4 (current pointers), I6/I7 (NDCs), I9 (sources), Matcher (I10) for each active fact, I13 (gate).
3. If the new version's result moved from ABSENT to CARRIES_*: D5 `LandingEvent {observed: live}`.
4. Affected sets = {changed set} + D2 downstream sets. For each tenant: T3 -> T4 (REOPENED + REVIEW_RULING task for the site's responsible pharmacist). X5 fan-out record.
5. Prover claims each REVIEW_RULING (T5), recomputes F1 for the stock item, T10 hands an APPROVE_RULING task to the owner with the proposed verdict. Owner approves: T1 + T2 + T13 (APPROVED). Rejects: T13 (REJECTED), old ruling stays.
6. **Replay (F11)** shows the same loop on real history: as-of scrubbing (V4 with past `as_of_d`, read-only) and the replay Watcher, which copies the hub into `hubr_<id>`, hides versions after a date, then re-adds each real historical version through the same change handler so reopen, tasks and the landing ledger run for real in a sandbox.

### 6.6 Compounding (Publisher; `app/engine/publisher.py`)
- **Check confirmations.** `POST /api/tenants/{t}/confirm-check {version_id, fact_id, result, person_id}` writes `Event {CONFIRMED_CHECK}` in the tenant, then P1 on the hub with the salted org hash: agreement raises the tier (2 at one organisation, 3 at two), disagreement marks the check disputed. Any change of tier or dispute reopens rulings in every tenant whose bases rest on that set (T3 -> T4, reason "a pharmacist at another organisation confirmed this check" / "disputed").
- **Fact verification.** `POST /api/facts/{id}/verify` (P2) by a tenant pharmacist: the first verification activates an UNVERIFIED fact; activation triggers the Scout and Matcher for that molecule (F16) so every tenant immediately gets verdicts for it.
- **Landing ledger and latency.** Every observed landing (live, history, replay) is a `LandingEvent`; D4 latencies are public reliability signals that grow with every fact.
- A copycat starting today has the public data but not the pharmacist-confirmed checks, the verified fact library or the landing ledger.

### 6.7 Notifier (drafts only; `app/agents/notifier.py`)
- Trigger: a user clicks "Draft a note" on a NOT_LANDED_* or LANDED_UNCODED verdict (tenant context required), or a tenant rule after APPROVE_RULING.
- Refuses unless the target-version check is tier >= 2 (pharmacist confirmed): "Confirm the check first." This is the false-accusation guard.
- Draft text (template; LLM phrasing optional): states only facts (NDC, set id, version, date, section code, the reference supplement and date, the source label's carrying version), links DailyMed, asks whether an updated label is planned, signs "Prepared with Landfall (automated screening of public data; not legal or regulatory advice)". Kinds: LABELER_NOTICE, MEDWATCH (pre-filled fields to copy into FDA's form), INTERNAL_MEMO.
- `Task {APPROVE_NOTICE}`; approve marks `ready_to_copy = true` and shows a copy button. Nothing is sent by Landfall.

### 6.8 Agents and handoffs (Track 2)
| Agent | Does | Tools |
|---|---|---|
| Scout | ingests molecules, applications, SPL sets, versions, products, packages, sources | DailyMed, openFDA clients; I1-I9, I11-I13 |
| Matcher | checks each version against each fact | lxml; I10 |
| Prover | computes verdicts, writes rulings, proposes on review tasks | V1-V6, W1-W2, T1, T2, T5, T10 |
| Watcher | polls versions, records landings, fans out and reopens | L2, L3, D2, D5, T3, T4, X5 |
| Notifier | drafts notices behind approval | T18, T19 |
| Publisher | confirmations and fact verifications into the hub | P1, P2; T13 |
Task protocol: OPEN -> CLAIMED (lease 2 min, T5) -> AWAITING_APPROVAL -> DONE (T17); stale leases return to OPEN; every transition has an Event; HANDED_OFF_FROM links the chain Watcher -> Prover -> owner.

---

## 7. API (FastAPI, `services/api`)
Summary only. **`docs/API.md` is the authoritative contract.**

| Method and path | Purpose |
|---|---|
| `GET /api/health` | FalkorDB, graphs, hub counts, source status |
| `POST /api/landed` | the verdict (`Landing`) for an NDC; writes a ruling when tenant + stock item are given |
| `GET /api/ndc/{ndc}` | identity, listing, label of record |
| `GET /api/sets/{set_id}/history` | version timeline with checks (L1) |
| `GET /api/products/{ndc}/authority`, `/upstream`, `/proof-path` | W1+W2 with rules, W4 BFS closure, V2 |
| `GET /api/facts`, `/api/facts/{id}`, `/fanout`, `/copy-lag`, `/latency`, `/landings`, `/families` | V3, D1, D3, D4, D6, R1 |
| `GET /api/gaps` | W3 open gaps across facts |
| `GET /api/algo/source-hubs`, `/chokepoints`, `/label-families` | A1, A2, A3 |
| `GET /api/checks/queue`, `POST /api/tenants/{t}/confirm-check`, `POST /api/facts/{id}/verify` | compounding |
| `POST /api/sandbox`, `GET /api/tenants`, tenant overview, trace, decisions, events, tasks, conversations | Tracks 2 and 3 |
| `POST /api/watch/check`, `POST /api/replay/start`, `POST /api/replay/{id}/advance`, `GET /api/replay/{set_id}/timeline` | loop |
| `POST /api/drafts` | Notifier |
| `GET /api/eval` | eval report |

Public access: reads and `/api/landed` without a tenant are open; tenant writes need the sandbox token (visitors) or `ADMIN_TOKEN`. Visitors never write to `tenant_bayview` or `tenant_northgate` directly. Rate limits per IP: landed 30/min, sandbox 3/h, replay start 3/h, admin scout 6/10 min, everything else 120/min (API.md "Conventions").

---

## 8. MCP server (`/mcp`, streamable HTTP)
Tools (exact names; descriptions in `docs/API.md` are verbatim in code):
| Tool | Arguments | Returns |
|---|---|---|
| `landed` | `ndc`, `fact_id?`, `strict?`, `as_of?`, `tenant?`, `token?`, `stock_item_id?` | verdict summary per fact + link |
| `who_must_act` | `ndc`, `fact_id?` | authority rows and the rule result |
| `label_history` | `ndc` or `set_id` | versions with checks and landing events |
| `open_gaps` | `party_id?`, `fact_id?` | labels of record lacking active facts (W3) |
| `fanout` | `fact_id` | census of labels of record in scope (D1) |
| `copy_lag` | `fact_id` | D3 pairs |
| `supply_families` | `fact_id` | R1 WCC families with counts |
| `source_hubs` | none | A1 PageRank |
| `proof_path` | `ndc`, `fact_id` | V2 shortest path or the no-path proof |
| `alternatives` | `ndc`, `fact_id` | V6 |
| `watch` | `tenant`, `token`, `stock_item_id` | marks the stock item watched; its set and sources join the Watcher set |
| `confirm_check` | `version_id`, `fact_id`, `result`, `tenant`, `token`, `person_id` | publisher result |
| `verify_fact` | `fact_id`, `tenant`, `token`, `person_id` | P2 result |

Connect from Claude Code: `claude mcp add --transport http landfall https://<api-host>/mcp`. Demo prompt: "Before you print the patient leaflet for NDC 68071-3355-9, check with landfall whether the label carries the current boxed warning."

## 9. Infrastructure proof: an external agent calls Landfall (`examples/pharmacy_agent/`)
A small Python program (no LLM required) that plays a pharmacy-dispensing agent: it reads `data/dispense_queue.json` (fictional prescriptions with real NDCs), connects to `/mcp` with the official MCP client, calls `landed` for each NDC before "printing", and prints an action per item: proceed, "print the current Medication Guide from the reference label and flag for pharmacist" (NOT_LANDED_*), or "ask pharmacist" (UNKNOWN). With `--tenant` and a sandbox token it also writes turns and rulings. Optional `--llm` lets an OpenRouter model decide which tool to call from the MCP tool list (tool selection). This is the "other agents call it" level-3 requirement made concrete.

---

## 10. Web app (`apps/web`, Next.js on Vercel)
Summary only. **`docs/UI.md` is authoritative.**
1. `/` "Did the warning land?" NDC input, example chips, census strip.
2. `/ndc/[ndc]` Verdict: badge, one-line reason, path graph, version timeline, upstream source card with copy lag, who can act, alternatives, "How we decided" (Cypher), actions, disclaimer.
3. `/facts/[id]` Fan-out census, copy lag table, latency, landing ledger, families, source hubs, chokepoints.
4. `/replay` Loop-closure replay (Accord, AvKARE, others) with scrubber and replay Watcher.
5. `/orgs` Two organisations side by side (Bayview, Northgate), sandbox button, tasks, decisions, trace drawer.
6. `/checks` Shared check queue (confirm what you see on DailyMed), fact verification.
7. `/mcp` Connect instructions, tool list, the pharmacy-agent recording.
8. `/eval` Frozen eval vs baselines with labels hash.
9. `/how-it-works` Graph model, queries, tiers, privacy rule, wording rules.

---

## 11. Demo tenants (fictional, `data/demo_tenants/`)
- **Bayview Community Pharmacy Group (fictional)**, pharmacy chain, CA. Sites #12 Harbor St and #31 Elm Ave. People: Ruth Okafor (PIC #12), Daniel Reyes (PIC #31), Aisha Grant (QA lead, owns both formulary entries), Marco Lin (buyer); all fictional. Stock: `68071-3355-9` (NuCare, NOT_LANDED_REVISED), `63187-626-30` (Proficient Rx, NOT_LANDED_UNREVISED, authority gap), `42291-622-30` (AvKARE, LANDED_UNCODED), `31722-726-90` (Camber, LANDED), `16729-119-15` (Accord, LANDED; the replay label).
- **Northgate Health System (fictional)**, hospital formulary team, OH; runs **strict mode** by policy. Sites inpatient and outpatient. People: Dr. Helen Park (P&T chair, owns zolpidem entry), Samuel Osei (formulary pharmacist, owns montelukast entry), Priya Raman (PIC, both sites), Tom Becker (buyer); all fictional. Stock: `63187-781-30` (Proficient Rx, source Accord), `50268-574-15` (AvPAK, LANDED_UNCODED), `29300-220-13` (Unichem, LANDED), `68071-4034-9` (NuCare, source Macleods; the compounding flip), `68071-5063-9` (NuCare zolpidem; no verdict until the zolpidem fact is verified).
- Expected verdicts above come from the fixture run on 18 Oct 2026 (as of 2026-10-16); goals G049 and G066 re-check them on the live hub. Rulings are written by the API at first start, never by the Cypher files.

---

## 12. Frozen eval (`eval/`)
- **Cases** (`data/eval_cases.csv`, copied to `eval/cases.csv` at G080): chosen before verdict code exists.
  - E-VERDICT: all 69 montelukast labels of record as of 2026-10-16 (one case per set, via one package NDC each).
  - E-GATE: 20 of the 47 DailyMed montelukast sets that are not the label of record for an active listing (expected NOT_ASSESSED or never flagged).
  - E-REPLAY: 12 (set, as_of) pairs from the real histories in section 4 (Accord x3, AvKARE x2, AvPAK x2, Bryant Ranch x2, American Health Packaging x1, Preferred x2).
  - E-WHO: the 15 non-LANDED labels of record (13 lacking + 2 uncoded): expected primary party kind and rule.
  - E-HELDOUT: 30 zolpidem labels of record chosen at random with a fixed seed after the zolpidem fact is verified, labelled before the Matcher runs on zolpidem; scored once at the end.
- **Labels**: `eval/labels.json` written by a human (teammate B) by opening the rendered DailyMed label version (and its archive for replay cases), **before** teammate A merges the verdict code (G080 before G036). Commit `eval/labels.sha256`; quote the hash in the README. Cursor must not write labels (AGENTS.md).
- **Metrics**: verdict accuracy over the 7 classes; **false-red count (target 0)** = cases labelled LANDED or LANDED_UNCODED that Landfall calls NOT_LANDED_*; gate false-red count (target 0); who-must-act accuracy; UNKNOWN rate; replay accuracy; held-out accuracy reported separately.
- **Baselines**: (a) *openFDA field script*: `_missing_:boxed_warning` means lacking (what a 20-line script does); (b) *openFDA text grep*: header phrase anywhere in the label JSON; (c) optional card-only LLM: each model in `EVAL_BASELINE_MODELS` gets the openFDA label JSON for the current version and must answer one of the 7 classes. Report honestly: on the bare carries-or-lacks question, (b) ties Landfall on openFDA's 64 labels; it cannot see the 5 DailyMed-only labels, cannot separate revised from unrevised, cannot apply the listing gate, cannot name who can act, cannot replay or compute copy lag; (a) also produces 2 false reds (the uncoded labels). That table is the answer to "is the graph decoration?".

---

## 13. Repo layout
```
landfall/
  AGENTS.md  BLUEPRINT.md  CURSOR_PROMPT.md  README.md  LICENSE  Makefile  docker-compose.yml  .env.example
  .cursor/rules/landfall.mdc
  docs/GOALS.md  docs/FLOWS.md  docs/API.md  docs/UI.md  docs/queries.cypher  docs/REQUIREMENTS.md
  docs/TASKS.md  docs/OPEN_POINTS.md  docs/EXPLAINER.md  docs/RUNBOOK.md (G121)  docs/evidence/
  data/facts.seed.json  data/molecules.json  data/watchlist.json  data/prewarm.json  data/section_codes.json
  data/dispense_queue.json  data/eval_cases.csv  data/demo_tenants/bayview.cypher  data/demo_tenants/northgate.cypher
  data/fixtures/hub_montelukast.json
  services/api/
    pyproject.toml  Dockerfile
    app/main.py  app/config.py  app/logging.py  app/errors.py  app/llm.py
    app/sources/http.py  app/sources/dailymed.py  app/sources/openfda.py  app/sources/cache.py  app/sources/spl.py
    app/graph/db.py  app/graph/queries.py  app/graph/schema.py  app/graph/fixture.py
    app/engine/matcher.py  app/engine/verdict.py  app/engine/authority.py  app/engine/views.py
    app/engine/publisher.py  app/engine/explain.py  app/engine/replay.py  app/engine/ask.py
    app/agents/scout.py  app/agents/prover.py  app/agents/watcher.py  app/agents/notifier.py  app/agents/tasks.py
    app/mcp_server.py
    app/routes/health.py  app/routes/landed.py  app/routes/facts.py  app/routes/products.py  app/routes/tenants.py
    app/routes/checks.py  app/routes/replay.py  app/routes/eval.py  app/routes/admin.py
    tests/  (fixture loader, golden verdicts, queries-in-sync, wording, privacy, concurrency)
  apps/web/  (Next.js)
  examples/pharmacy_agent/agent.py  examples/pharmacy_agent/requirements.txt
  eval/cases.csv  eval/labels.json  eval/labels.sha256  eval/run_eval.py  eval/baselines.py  eval/report.json
  scripts/smoke.sh  scripts/mcp_smoke.sh  scripts/bench.sh  scripts/load.py  scripts/export.sh  scripts/query_check.py (provided)
```

---

## 14. Build plan (about 22 hours, two people plus Cursor)
H0 is the moment work starts. Person A: backend and graph. Person B: frontend, eval labels, video. Details in `docs/TASKS.md`; acceptance in `docs/GOALS.md`.

| Hours | Person A | Person B | Milestone |
|---|---|---|---|
| 0-1 | scaffold, compose, Railway FalkorDB + API, schema, fixture loader (G001-G019) | Vercel shell, design tokens, eval case list frozen | both deploy "hello"; fixture loads |
| 1-4 | source clients, SPL parser, Scout for montelukast, Matcher (G020-G034) | **labels** for E-VERDICT, E-GATE, E-REPLAY, E-WHO (before verdict code) | live hub has 116 sets, 69 labels of record |
| 4-8 | V1-V4 verdict, authority rules, explanation, `/api/landed` (G035-G054) | home + verdict page + path graph + timeline | **H8: public URL answers NOT LANDED (REVISED) for 68071-3355-9 with path, versions, source, who can act** |
| 8-12 | tenants, rulings, sandbox, tasks, MCP server, pharmacy agent (G055-G079) | orgs page, MCP page; record the pharmacy agent and Claude Code | MCP works from another agent |
| 12-16 | fan-out, copy lag, latency, algorithms, eval runner + baselines (G080-G094) | facts page, eval page | census, copy lag, families on screen; false red 0 |
| 16-19 | Watcher, replay Watcher, Publisher, Notifier, zolpidem verification (G095-G112) | replay page, checks page | all three demo shots work end to end |
| 19-21 | hardening, rate limits, persistence, load (G113-G124) | polish, empty and error states, mobile | stable deployment |
| 21-23 | README (data model, Cypher, setup, tracks, AI disclosure) (G125-G135) | 3-minute video, blog draft | submission assets ready |
| 23-24 | buffer, submit | buffer | submitted |

**Cut order if behind** (cut from the top; never touch the H8 core G035-G054, the README requirements or the eval): 1) aviation adapter and every add-on in section 18; 2) voice-free Ask add-on; 3) replay Watcher (keep as-of scrubbing on `/replay`); 4) Notifier drafts (keep "who can act" text); 5) zolpidem live verification (ship montelukast only; zolpidem fact stays UNVERIFIED and is shown as "awaiting verification"); 6) sandbox copies (fixed tenants read-only for visitors; admin demo); 7) A3 label families; 8) LLM phrasing (templates); 9) `/how-it-works` (move into README).

---

## 15. The 3-minute video
| Time | Shot | Track |
|---|---|---|
| 0:00-0:15 | Cold open: "In April 2020 FDA added its strongest warning to montelukast: serious neuropsychiatric events. Six years later, 13 labels of record behind active listings still lack it. Which bottle is yours?" | hook |
| 0:15-0:55 | Type `68071-3355-9`: NOT LANDED (revised without it). Path through ANDA202717 to Singulair; timeline v4, v5 lacking; source Accord carries since 21 May 2021, copy lag 1,147 days; who can act: the labeler of record for this repackaged product; FDA as regulator. Flip to `63187-626`: authority gap, the source has no active listing and the holder has no label. | Track 1 |
| 0:55-1:20 | The pharmacy agent works through its dispensing queue over MCP, calls `landed`, flags one NDC for the pharmacist; Claude Code asks the same with one prompt. | Track 1 (infrastructure) |
| 1:20-1:50 | Replay: Accord v12 lacking -> v14 carries: NOT LANDED flips to LANDED, LandingEvent 387 days, downstream repackagers get tasks in the sandbox; AvKARE v21 lands as text only. Watcher armed on the 13 open gaps. | Track 1 + Track 3 (loop) |
| 1:50-2:20 | Two org graphs: Northgate (strict) shows UNKNOWN for NuCare 68071-4034; Bayview's pharmacist confirms the absence on DailyMed; tier 1 -> 2; Northgate flips and Priya gets a task; the hub holds a hash, no names. Decision trace: formulary hold -> ruling -> SPL v4 -> section 34066-1 -> tier 2. | Track 2 + Track 3 |
| 2:20-2:40 | Graph-wide: fan-out census 54 / 2 / 9 / 4, copy lag table, WCC families (Accord family 3 of 7), PageRank source hubs; zolpidem fact verified live -> a second molecule lights up. | Track 1 |
| 2:40-2:55 | Eval vs openFDA script and grep baselines: false red 0; what the baselines cannot do. FalkorDB stopped -> 503. | proof |
| 2:55-3:00 | Live URL, MCP command, disclaimer. | close |

---

## 16. Risks and answers
| Risk | Answer |
|---|---|
| "A 20-line openFDA script finds the 13" | It finds the 13 on openFDA's 64 labels and nothing else. It misses 5 DailyMed-only labels of record, false-reds 2 uncoded labels if it trusts the field, flags old SPLs without the listing gate, cannot separate revised from unrevised (needs version history), cannot compute copy lag along source NDCs, cannot name who can act or detect the authority gap, cannot replay or reopen. The eval prints this table (section 12). |
| "The drug path is a 2-3 hop join" | The verdict is a typed path plus a version timeline plus a temporal comparison along `SOURCED_FROM`, over every fact at once (D1, W3), with holder succession (HOLDS intervals), reference-standard fallback (W2), reverse fan-out on change (D2), and algorithms that rank where a fix reaches most labels (A1, A2, R1). |
| False accusation of named labelers | Listing gate; wording rules; tier and dispute model; strict mode; Notifier refuses below tier 2; nothing is ever sent; disclaimer; "label of record on DailyMed" not "the bottle". |
| openFDA lag vs DailyMed | DailyMed is the source of truth; openFDA is used for the listing gate, applications and the baseline only. |
| DailyMed archive HTML changes | Archive ids are parsed from `drugInfo.cfm`; the parser has a recorded fixture test; if it fails, versions still come from `history.json` and current XML, replay falls back to the fixture snapshot. |
| Rate limits | openFDA key, 2 rps cap on DailyMed, immutable cache by `setid@version`, prewarm before judging. |
| Real-world loop takes months | Real historical loops replayed from DailyMed archives; the live Watcher is armed on the 13 open gaps and records any landing. |
| Synthetic organisations look thin | They are labelled; the hub is real; judges can act as an organisation in a sandbox. |
| Scope creep (aviation) | Aviation is add-on ADD6, cut first. |

## 16.5 Decided on 18 Oct 2026 (do not revisit)
- Product: Landfall, drugs only (montelukast hero, zolpidem second). Primary Track 1; also Tracks 2 and 3.
- Hosting: Vercel (web) + Railway (API and FalkorDB in Docker). Not FalkorDB Cloud free tier.
- MCP SDK pinned below 2.0. FalkorDB `TIMEOUT 5000`.
- No label text in the repo or the graph. Section code + phrase key decide carries; the verdict class is decided in Cypher (V4).
- Listing gate is mandatory for any red verdict. Grace window 30 days (display policy, not a legal standard).
- Landfall never sends notices. Repository licence MIT (team confirms ownership, rule 15).

## 17. Submission checklist
- [ ] Live URL (Vercel) and API (Railway) up; `/api/health` green.
- [ ] Public repo with README: setup, graph data model (5.1-5.3), Cypher queries (link `docs/queries.cypher`), algorithms used, MCP connect command, tracks (Track 1 primary; Track 2, Track 3), AI disclosure.
- [ ] Demo video (3 minutes) linked in README and the submission form.
- [ ] `eval/labels.sha256` committed and quoted in README; `/eval` shows results with both baselines.
- [ ] Blog post (side prize) drafted.
- [ ] Everyone can explain V1, V2, V4, V5, W1, D1, D3, R1, A1, P1, T3 and the tiers (`docs/EXPLAINER.md`).
- [ ] LICENSE added and ownership agreed (rule 15).
- [ ] Every goal in `docs/GOALS.md` done or explicitly cut with a reason.

## 18. Add-ons (decided 18 Oct 2026; all after M6 and all cuttable in this order: ADD6, ADD5, ADD4, ADD3, ADD2, ADD1)
| Id | Add-on | What it adds to the graph | Why |
|---|---|---|---|
| ADD1 | OpenRouter gateway | nothing | one key for explanation phrasing, drafts, Ask router, LLM baseline (part of core code path; cutting it means templates only) |
| ADD2 | LLM baseline in the eval | none | measured answer to "is the graph decoration?" |
| ADD3 | Drugs@FDA labeling-supplement watch | `SafetyFact {status: UNVERIFIED}` candidates from new LABELING supplements on reference drugs | knowledge kept current at the source; a pharmacist verifies before it counts |
| ADD4 | Ask the organisation | `Conversation`/`Turn` | LLM picks one of K1-K8; FalkorDB answers with sources |
| ADD5 | `on_reopen` webhook | none | other systems subscribe to reopen events (infrastructure) |
| ADD6 | Aviation adapter (NTSB rec -> FAA AD -> type model -> N-number) | same verdict shape in a separate `hub_aviation` graph | proves generality; **cut first**; only if every core goal is green by H19 |
(Add-on ids are ADD1-ADD6 so they never clash with the query names A1-A3.)
