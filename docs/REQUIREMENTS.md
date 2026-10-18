# Requirements traceability

Every requirement and judging signal on the hackathon page (overview, tracks, sponsor section, FAQ), the rules page and the schedule, mapped to where Landfall meets it and the goal in `docs/GOALS.md` that proves it. Source pages: https://www.wemakedevs.org/hackathons/falkordb, `/rules`, `/schedule`, `/resources` (read 17-18 Oct 2026 for the ModelBrain pack; the rows are reused and re-mapped to Landfall).

**Prime constraint: FalkorDB is the heart of the product.** The FAQ says it must be the primary graph database and support a central part of the product; rule 3 disqualifies a graph that is only decoration. Section C lists every FalkorDB capability we use. Row ids: H = hard rule, S = judging signal (query names in `docs/queries.cypher` never start with H or S, so there is no clash).

## H. Hard rules (failing any of these risks disqualification)

| # | Requirement (source) | How Landfall meets it | Goals |
|---|---|---|---|
| H1 | FalkorDB must be the primary graph database and support a central part of the product (FAQ; rule 2) | Every verdict, path, version timeline, fan-out, ruling, task and decision lives in FalkorDB; there is no other database | G010-G016, G035-G048 |
| H2 | The graph must do real work: if the product works without FalkorDB, it is decoration (rule 3) | The verdict class is computed in Cypher (V4) over a typed scope path (V2), the listing gate (V1) and upstream source timelines (V5, D3); algorithms (BFS, shortest path, PageRank, betweenness, WCC, label propagation) drive views and MCP tools; a test proves `/api/landed` returns 503 without FalkorDB; the eval shows what per-label scripts cannot do | G036, G046, G092, G116 |
| H3 | Main coding and the FalkorDB implementation are new work during the event (FAQ; rule 8) | All code written on 18 Oct; only libraries and public data reused; the research fixture is data | G001 |
| H4 | Data must be public, synthetic or own; no private, login-protected, paywalled or personal data (rule 6) | DailyMed (NLM) and openFDA (FDA) public data; openFDA is CC0; no label text stored; fictional organisations, people and inventories; no personal data | G020-G034, G055 |
| H5 | Public source-code repository (rule 10) | GitHub public repo | G125 |
| H6 | README with setup instructions and the graph data model (rule 10) | README "Run locally", "Deploy", "Graph data model" | G126, G127 |
| H7 | The Cypher queries or graph algorithms the product depends on (rule 10) | README "Queries and algorithms" linking `docs/queries.cypher`, explaining V1, V2, V4, V5, W1, D1, D3, R1, A1, A2, W4, P1, T3 | G128 |
| H8 | Demo video showing the working project (rule 10; FAQ) | 3-minute video per BLUEPRINT section 15 | G129 |
| H9 | Live deployment, or complete local setup if it cannot be deployed (rule 10; FAQ "live deployment preferred") | Vercel web + Railway API + Railway FalkorDB; `docker compose up` and fixture mode for offline use | G113-G115, G126 |
| H10 | Name every track entered at submission (rule 5) | Track 1 (primary), Track 2, Track 3 | G131 |
| H11 | AI coding assistants allowed but must be disclosed (rule 11; FAQ) | README "Built with AI assistance" | G130 |
| H12 | Participants understand and can explain the graph model, queries, architecture and decisions (rule 12; FAQ) | `docs/EXPLAINER.md`; every member rehearses | G132 |
| H13 | Not entirely AI-generated without meaningful contribution, verification or understanding (rule 13) | Humans write the eval labels, verify safety facts and phrase keys, confirm checks, review PRs, run the demo | G080, G104, G132 |
| H14 | Solo or up to 4 per team; each person in one team (rule 1) | Team registered on WeMakeDevs | G131 |
| H15 | Respect, no plagiarism, no judging manipulation (rules 16-18) | No copying of other entries; competitor names only in private notes | G134 |
| H16 | Submissions close 18 Oct 2026, 11:59 PM IST (rule 7; schedule) | Build plan ends at H23 with a 1 h buffer; form by 23:00 IST | G131 |
| H17 | Run FalkorDB however suits you: Docker, self-hosted or FalkorDB Cloud; any stack (rule 4) | `falkordb/falkordb:latest` in Docker on Railway and locally | G002, G113 |
| H18 | Frameworks, libraries, public APIs, templates and datasets may be used; original event work is judged (rule 9) | Our work: graph model, ingest, Matcher, verdict Cypher, authority rules, Watcher, Publisher, MCP tools, UI; dependencies listed in README | G127 |
| H19 | IP belongs to the team; agree on ownership before submitting (rule 15) | LICENSE (MIT suggested) after agreement | G125, G134 |
| H20 | WeMakeDevs Code of Conduct applies (rules 16-18) | Respectful conduct; wording rules avoid accusing named companies | G052, G134 |

## S. What the brief and tracks ask for (judging signals)

| # | Signal (source) | Where Landfall shows it | Goals |
|---|---|---|---|
| S1 | "Build a working agent, or a group of agents, with FalkorDB as its context layer. The graph has to shape what the agent does" (challenge) | Scout, Matcher, Prover, Watcher, Notifier and Publisher read and write FalkorDB on every step; the pharmacy agent and Claude Code act on graph answers over MCP | G025-G029, G036, G073, G095 |
| S2 | "An agent that acts on connected data, remembers what it learns, and can show how it got to each answer" (brief) | Acts: tasks, alternatives, draft notices behind approval. Remembers: rulings, decisions, confirmations, landing ledger. Shows: path, version timeline, source evidence and Cypher on every verdict | G036-G053, G060-G067 |
| S3 | Work the graph has to do: "Follow connections across data" | Reference drug -> generic application -> source NDC -> repackaged NDC -> package (V2, W1, W4) | G037, G044, G089 |
| S4 | "Remember across sessions" | Rulings, bases, decisions, events and turns persist per tenant; confirmations and landing events persist in the hub; reopen on change | G056, G060-G067, G083 |
| S5 | "Share state between agents" | Task nodes with leases and HANDED_OFF_FROM; Watcher -> Prover -> owner | G063, G065, G098 |
| S6 | "Connect people, projects, and decisions" | Person RESPONSIBLE_FOR Site, OWNS FormularyEntry, DECIDED Decision, SIGNED Event | G057, G061 |
| S7 | "Show the path behind an answer" | Path graph, timeline, upstream card and the V1/V2/V4 Cypher on every verdict; `proof_path` tool | G053, G070 |
| S8 | "Pick a task where the answer depends on how things connect" | Whether a label carries a warning depends on the chain from the reference drug through applications and source NDCs, and on version timing along that chain | G043, G082 |
| S9 | Track 1 key focus: multi-hop reasoning | V2 multi-type bounded paths, W1 source chains, D1 fan-out up to 5 hops, D3 temporal comparison across SOURCED_FROM | G037, G043, G081, G082 |
| S10 | Track 1: graph queries and algorithms as agent tools | MCP tools `fanout`, `copy_lag`, `supply_families` (WCC), `source_hubs` (PageRank), `proof_path` (shortest path), `who_must_act`, `open_gaps`; BFS upstream closure and betweenness chokepoints in the API | G070, G084-G090 |
| S11 | Track 1: tool selection through MCP | The pharmacy agent (`--llm`) and Claude Code choose among Landfall tools by their descriptions | G068-G074 |
| S12 | Track 1: actions based on what the graph shows | Reopen tasks, pharmacist-review tasks with alternatives, formulary decisions, draft notices behind approval | G079, G098, G107 |
| S13 | Track 1: explainable results | Version and date on every claim, DailyMed links, scope path, tier, Cypher | G052, G053 |
| S14 | Track 2: episodic, semantic and procedural memory | Episodic: rulings, events, decisions, turns. Semantic: the hub. Procedural: Playbook nodes followed by tasks | G058, G077 |
| S15 | Track 2: persistent conversation history | `(Conversation)-[:HAS_TURN]->(Turn)-[:PRODUCED]->(Ruling)` per tenant for MCP and web | G067 |
| S16 | Track 2: shared state and handoffs between agents | Tasks, leases, HANDED_OFF_FROM, approvals | G063, G065, G098 |
| S17 | Track 2: high-concurrency reads and writes | `ro_query` for verdicts; idempotent MERGE ingest; 409 on stale ruling writes; load test | G064, G117 |
| S18 | Track 2: separate memory per user or tenant | One graph per organisation and per sandbox (`GRAPH.COPY`), replay hubs, all on one instance | G059, G062 |
| S19 | Track 3: knowledge from docs, tickets and chats in one graph | Regulatory documents (SPL versions, Drugs@FDA supplements, NDC listings) in the hub; the organisation's stock, formulary decisions and tasks in the tenant | G025-G027, G061 |
| S20 | Track 3: who owns what, and who knows what | Responsible pharmacist per site, owner per formulary entry, who decided and who signed | G057, G061 |
| S21 | Track 3: tracing decisions back to their source | T12: decision -> ruling -> SPL set, version, date, section code, check tier -> DailyMed link | G061 |
| S22 | Track 3: keeping knowledge current as things change | Watcher + landing ledger + reopen + supersede; fact verification and the Drugs@FDA watch | G095-G098, G104, G137 |
| S23 | Track 3: answers with clear sources | Every answer cites the SPL set and version, the Drugs@FDA supplement and the NDC listing | G052, G060 |
| S24 | "What breaks if this service goes down?" style questions (why graphs) | "Which labels must change if this source label or reference labeling changes?" (D1, D2) | G081, G096 |
| S25 | Prize "best agent that uses a graph to make decisions and take action" (Track 1) | Primary track narrative and video | G129 |
| S26 | Side prize: best blog post | Blog post drafted from README | G133 |
| S27 | Top 50 projects get T-shirts | Polish, live URL, clear README | G113-G130 |

## C. FalkorDB capabilities we use (the sponsor section, line by line)

| Sponsor claim | Our use | Goals |
|---|---|---|
| "Traversals are fast enough to run on every step of an agent loop" | Every `landed` call (web, MCP, pharmacy agent) runs V1, V2, V4, V5 live; p95 under 1.5 s cached end to end | G054, G117 |
| "One instance can hold thousands of isolated graphs, so each user, agent, or tenant gets its own" | `hub` + `tenant_*` + `sbx_*` + `hubr_*` on one instance; `GRAPH.COPY` for sandboxes and replay hubs | G059, G062, G100 |
| "Run it locally with Docker" | `docker compose up` with `falkordb/falkordb:latest` | G002 |
| Official clients | `falkordb` Python client | G010 |
| Cypher: match patterns, follow paths, return what the agent needs | All queries in `docs/queries.cypher`, including multi-type bounded paths and the verdict CASE in V4 | G011, G036 |
| Context for AI agents: agent memory, multi-agent state, connected company knowledge | Tenant rulings, decisions and conversations; tasks and handoffs; the organisation's stock graph | G055-G067 |
| Connect your agent stack: MCP | Our MCP server; the pharmacy agent and Claude Code as clients | G068-G074 |
| Connect your agent stack: GraphRAG-SDK, QueryWeaver, Graphiti, Cognee, LangChain, LlamaIndex | Not in the core (explicit ontology); ADD4 "Ask the organisation" uses an LLM only to pick one of 8 templated Cypher questions (K1-K8) | G138 |
| One graph per user or tenant (multigraph topology) | Tenant and sandbox graphs | G059, G062 |
| Graph algorithms as agent tools: shortest path, PageRank, centrality, connected components, community detection | V2 shortestPath (scope proof), A1 PageRank (source hubs), A2 betweenness (chokepoints), R1 WCC (supply families), A3 labelPropagation (label families), W4 algo.BFS (upstream closure) | G041, G084-G089 |
| Explore the graph with FalkorDB Browser | Local compose exposes the Browser on port 3000; README walkthrough with screenshots | G128 |

## F. Add-ons and the signals they strengthen
| Add-on | Signal | Goals |
|---|---|---|
| ADD1 OpenRouter gateway | S11 tool selection (pharmacy agent `--llm`); explanation phrasing | G135, G074 |
| ADD2 LLM baseline | H2 the graph is not decoration (measured) | G136 |
| ADD3 Drugs@FDA labeling-supplement watch | S22 keeping knowledge current | G137 |
| ADD4 Ask the organisation | S11, S23, Track 3 "answer questions with sources" | G138 |
| ADD5 `on_reopen` webhook | infrastructure (other systems subscribe) | G139 |
| ADD6 Aviation adapter | generality of the engine (cut first) | G140 |

## E. Official resources and where we use them
| Resource | Use |
|---|---|
| Getting started: https://docs.falkordb.com/getting-started/ | Block 0 setup |
| Docs and Cypher: https://docs.falkordb.com/ , https://docs.falkordb.com/cypher/ | All queries |
| Docker and Compose: https://docs.falkordb.com/operations/docker | `docker-compose.yml`, Railway service (data path, `REDIS_ARGS`, `FALKORDB_ARGS`) |
| FalkorDB Cloud: https://app.falkordb.cloud/ | Allowed fallback; free tier unsuitable for judging |
| FalkorDB Browser: https://docs.falkordb.com/browser/ | README walkthrough |
| Clients: https://docs.falkordb.com/getting-started/clients | `falkordb` Python client |
| Algorithms: https://docs.falkordb.com/algorithms/ | BFS, WCC, PageRank, betweenness, label propagation, shortest path |
| Integrations: https://docs.falkordb.com/integration/ | MCP |
| Community projects: https://www.falkordb.com/community-projects/ | Check before submission that we do not duplicate a listed project |
| Blog: https://www.wemakedevs.org/blogs/how-to-build-an-agent-that-reasons-over-a-graph | Read in Block 0; align README vocabulary |
| FalkorDB Discord: https://discord.com/invite/Y2mMT9VdMy | Ask if blocked |

## D. Gaps we accept (stated honestly in the README)
- Organisations are fictional; the hub data is real public data.
- The verdict is about the DailyMed label of record behind an active listing, not about the paper insert in a specific bottle.
- On the bare carries-or-lacks question, a text grep over openFDA ties Landfall on openFDA's 64 montelukast labels; the graph's value is the DailyMed-only labels, the listing gate, revised vs unrevised, copy lag, who can act, replay and reopen (eval table).
- Compounding starts with two demo organisations; the mechanism, not the network size, is demonstrated.
- The 30-day grace window is a display policy, not a legal standard.
