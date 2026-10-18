# Landfall API contract

Base URL: `https://<api-host>` (Railway). All JSON. Times are ISO-8601 UTC strings in responses; epoch ms (tenant timestamps) and day numbers (`*_d`, hub dates) inside the graph. This file is the contract between `services/api`, `apps/web`, the MCP server, the pharmacy agent and the eval; change it here first.

## Conventions
- Auth headers: `X-Tenant-Token` (sandbox token from `POST /api/sandbox`) or `Authorization: Bearer <ADMIN_TOKEN>`.
- Request id: every response has header `X-Request-Id`; log lines carry it.
- Error envelope (all non-2xx):
```json
{ "error": { "code": "INVALID_INPUT", "message": "NDC '6807133559' is ambiguous.", "hint": "Use the dashed NDC printed on the label, e.g. 68071-3355-9.", "retry_after_s": null } }
```
- Error codes: `INVALID_INPUT` 422, `NOT_FOUND` 404 (unknown set, fact, task, tenant; an unknown NDC is a 200 UNKNOWN result, not an error), `UNAUTHORIZED` 401, `SANDBOX_EXPIRED` 401, `READ_ONLY_TENANT` 403, `STALE_RULING` 409, `CHECK_NOT_CONFIRMED` 409, `NOT_IN_QUEUE` 409, `RATE_LIMITED` 429, `GRAPH_UNAVAILABLE` 503, `SOURCE_UNAVAILABLE` 503, `INTERNAL` 500.
- Rate limits (per IP): landed 30/min, sandbox 3/h, replay start 3/h, admin scout 6/10 min, everything else 120/min. 429 includes `retry_after_s`.
- Validation patterns: NDC dashed `^\d{4,5}-\d{3,4}(-\d{1,2})?$` (normalisation in FLOWS F1.1); set id `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`; version id = set id + `#v` + digits; fact id `^[a-z0-9_]{3,64}$`; tenant `^(tenant_[a-z]+|sbx_[0-9a-f]{8})$`; dates `YYYY-MM-DD`.

## Shared types
```ts
type VerdictKind = "LANDED" | "LANDED_UNCODED" | "NOT_LANDED_REVISED" | "NOT_LANDED_UNREVISED"
                 | "NOT_IN_SCOPE" | "NOT_ASSESSED_INACTIVE_LISTING" | "UNKNOWN"
type UnknownReason = "NDC_NOT_FOUND" | "SCOPE_UNRESOLVED" | "LABEL_OF_RECORD_NOT_INGESTED"
                   | "NOT_CHECKED" | "ABSENCE_NOT_CONFIRMED" | "DISPUTED"
type CheckResult = "CARRIES_CODED" | "CARRIES_UNCODED" | "ABSENT" | "UNCHECKED"
type VersionRow = { version: number; version_id: string; doc_id: string | null; published: string
                    archive_id: string | null; result: CheckResult; tier: number | null; method: string | null
                    dailymed_url: string }          // drugInfo.cfm?setid=... or getArchivalFile.cfm?archive_id=...
type Party = { party_id: string | null; name: string; role: string; reason: string }
type WhoMustAct = {
  rule: "AUTHORITY_GAP" | "SOURCE_CARRIES" | "SOURCE_LACKS" | "OWN_LABEL"
  primary: Party; secondary: Party[]; oversight: Party        // oversight is always FDA
  authority_gap: boolean; annotations: string[]                // e.g. "REFERENCE_DISCONTINUED: FDA lists ANDA203438 as reference standard"
  rows: { hop: number; product_ndc: string; labeler: string | null; listing_active: boolean; label_set: string | null
          publisher: string | null; application: string | null; application_status: string | null
          application_is_rld: boolean; application_holder: string | null; rld: string | null
          rld_status: string | null; rld_holder: string | null }[]
}
type Upstream = { source_ndc: string; source_labeler: string | null; source_listing_active: boolean
                  source_set_id: string | null; source_first_carry_version: number | null
                  source_first_carry_published: string | null; copy_lag_days: number | null }
type FactResult = {
  fact_id: string; title: string; issued: string; section_code: string; phrase_key: string
  verdict: VerdictKind; unknown_reason: UnknownReason | null; verdict_line: string     // copy from UI "Verdict copy"
  scope: { in_scope: boolean; path: string[]; rels: string[]; proof: { searched: string; targets: string[]; from: string } | null }
  label_of_record: { set_id: string; title: string; dailymed_url: string } | null
  current: VersionRow | null; versions: VersionRow[]
  revisions_after_fact: number; revised_on: string[]; first_carry: VersionRow | null
  upstream: Upstream[]; who_must_act: WhoMustAct | null
  alternatives: { ndc: string; labeler: string; set_id: string; published: string }[]
  explanation: string; explanation_source: "llm" | "template"
  ruling_id: string | null
}
type Landing = {
  ndc: string; product_ndc: string | null; molecule_key: string | null; labeler_name: string | null
  dosage_form: string | null; strength: string | null
  listing: { active: boolean; spl_id: string | null; expiration: string | null } | null
  as_of: string; replay: boolean; gate_skipped: boolean; strict: boolean
  results: FactResult[]; message: string | null                 // message set when results is empty
  cypher: { v1: string; v2: string; v4: string }; params: Record<string, unknown>
  stale: boolean; computed_ms: number
  disclaimer: "Automated screening of public FDA and NLM data. Not medical, legal or regulatory advice. Not endorsed by FDA or NLM."
}
type Queued = { status: "QUEUED"; job_id: string; events_url: string }
```

## Endpoints

### Health, jobs and admin
| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/health` | none | `{ok, falkordb:"up"|"down", graphs:string[], hub:{label_sets, labels_of_record, versions, checks, facts_active}, sources:{dailymed:"ok"|"degraded", openfda:"ok"|"degraded"}, fixture_mode:boolean, version}` |
| POST | `/api/admin/scout` | admin | body `{molecule}` -> 202 `{job_id, events_url}` (F2) |
| GET | `/api/jobs/{job_id}` | none | `{status:"running"|"done"|"failed", counts, error?}` |
| GET | `/api/jobs/{job_id}/events` | none | SSE `{type:"started"|"set"|"version"|"done"|"error", ...}` |
| POST | `/api/admin/checks/resolve` | admin | `{version_id, fact_id, result, tier}` -> P3 result + reopened counts |
| POST | `/api/admin/facts/{fact_id}` | admin | `{phrase_key, section_code}` (ADD3 candidates) |
| GET | `/api/admin/watcher/last` | admin | last Watcher run summary |

### Verdicts and evidence
| Method | Path | Body / query | Response |
|---|---|---|---|
| POST | `/api/landed` | `{ndc, fact_id?, as_of?, strict?, tenant?, stock_item_id?, expected_ruling_id?, person_id?}` | 200 `Landing` or 202 `Queued` |
| GET | `/api/ndc/{ndc}` | `as_of?` | V1 row + `{label_of_record:{set_id, title, current_version, current_published}}` |
| GET | `/api/sets/{set_id}/history` | | `{set_id, title, versions:[{version, version_id, published, doc_id, archive_id, checks:[{fact_id, result, tier, method, disputed}]}], landings:[D6 rows for the set]}` (L1) |
| GET | `/api/products/{ndc}/authority` | `fact_id` | `WhoMustAct` (F4) |
| GET | `/api/products/{ndc}/upstream` | | `{closure:[{kind, id}]}` (W4) |
| GET | `/api/products/{ndc}/proof-path` | `fact_id` | `{in_scope, path, rels, proof}` (V2) |
| GET | `/api/products/{ndc}/alternatives` | `fact_id` | V6 rows |

### Facts and graph-wide views
| Method | Path | Response |
|---|---|---|
| GET | `/api/facts` | `[{fact_id, title, molecule_key, kind, issued, status, verifiers:number, source_url}]` (V3 per molecule, all statuses) |
| GET | `/api/facts/{id}` | one fact with `issued_on:[{application, supplement, approved}]` |
| GET | `/api/facts/{id}/fanout` | `{census:{LANDED, LANDED_UNCODED, NOT_LANDED_REVISED, NOT_LANDED_UNREVISED, UNKNOWN}, rows:[{set_id, title, publisher, version, published, result, verdict}]}` (D1 + V4) |
| GET | `/api/facts/{id}/copy-lag` | D3 rows |
| GET | `/api/facts/{id}/latency` | D4 rows |
| GET | `/api/facts/{id}/landings` | D6 rows |
| GET | `/api/facts/{id}/families` | R1 rows |
| GET | `/api/gaps` | `party_id?`, `fact_id?` -> W3 rows |
| GET | `/api/algo/source-hubs` | A1 rows |
| GET | `/api/algo/chokepoints` | A2 rows |
| GET | `/api/algo/label-families` | A3 rows |

### Compounding
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/api/checks/queue` | none | `fact_id?` | `[{fact_id, set_id, title, publisher, version_id, version, published, result, tier, confirmations, dailymed_url}]` (F8.7) |
| POST | `/api/tenants/{t}/confirm-check` | token/admin | `{version_id, fact_id, result, person_id}` | `{result, tier_before, tier_after, confirmations, disputed, reopened:{tenant: count}}` |
| POST | `/api/facts/{id}/verify` | token/admin | `{tenant, person_id}` | `{status, verifiers, job_id?}` (F16) |

### Organisations, memory and tasks
| Method | Path | Auth | Body / query | Response |
|---|---|---|---|---|
| POST | `/api/sandbox` | none | `{template:"bayview"|"northgate"}` | `{tenant, token, expires_at, template}` |
| GET | `/api/tenants` | none | | `[{name, org, kind:"fixed"|"sandbox", strict}]` (fixed tenants + caller's sandbox) |
| GET | `/api/tenants/{t}/overview` | read: none for fixed, token for sandbox | | `{org, strict, sites:[{id, name, responsible}], people, stock:[T6 rows], formulary:[T15 rows]}` |
| GET | `/api/tenants/{t}/rulings/{ruling_id}/trace` | same | | T7 row |
| POST | `/api/tenants/{t}/decisions` | token/admin | `{ruling_id, entry_id, person_id, kind, value, note}` | `{decision_id, entry_status}` (T14) |
| GET | `/api/tenants/{t}/decisions/{decision_id}/trace` | same as read | | T12 row |
| GET | `/api/tenants/{t}/events` | same as read | `limit=50` | T20 rows |
| GET | `/api/tenants/{t}/tasks` | same as read | `state?` | T16 rows |
| POST | `/api/tasks/{task_id}/claim` | token/admin | `{tenant, agent | person_id}` | `{claimed: bool}` |
| POST | `/api/tasks/{task_id}/approve` | token/admin | `{tenant, person_id}` | `{ruling_id?, draft_ready?}` |
| POST | `/api/tasks/{task_id}/reject` | token/admin | `{tenant, person_id, reason}` | `{ok}` |
| POST | `/api/tenants/{t}/watch` | token/admin | `{stock_item_id}` | `{watching: true}` |
| GET | `/api/tenants/{t}/conversations` | token/admin | | `[{id, channel, started_at, turns:[...]}]` |

### Watcher, replay and drafts
| Method | Path | Auth | Body / query | Response |
|---|---|---|---|---|
| POST | `/api/watch/check` | admin, or token for sets behind the caller's sandbox stock items | `{set_id} | {ndc}` | `{changed, new_version?, landing?, reopened:{tenant: count}}` |
| GET | `/api/replay/{set_id}/timeline` | none | `fact_id` | `{set_id, points:[{as_of, version, verdict, result}], landings:[...]}` (F11.1) |
| POST | `/api/replay/start` | none | `{set_id, from, template}` | `{replay_id, hub, tenant, token, next_version}` (F11.3) |
| POST | `/api/replay/{replay_id}/advance` | token from start | | `{version, landing?, reopened:[ruling_id], tasks:[task_id], done: bool}` |
| POST | `/api/drafts` | token/admin | `{tenant, stock_item_id, fact_id, kind:"LABELER_NOTICE"|"MEDWATCH"|"INTERNAL_MEMO"}` | `{draft_id, task_id, title, body}` (F10) |

### Eval
| Method | Path | Response |
|---|---|---|
| GET | `/api/eval` | `eval/report.json` |

## MCP tools (`/mcp`, streamable HTTP)
Descriptions are written for the calling agent; keep them verbatim in code.

| Tool | Description (verbatim in code) | Input schema | Output |
|---|---|---|---|
| `landed` | "Check whether the label of record for a drug NDC carries the current FDA boxed warning, with the version evidence, the upstream source and who can act. Call this before printing or giving patient information for a dispensed NDC." | `{ndc: string, fact_id?: string, strict?: boolean, as_of?: string, tenant?: string, token?: string, stock_item_id?: string}` | text (FLOWS F5.3) + structured `Landing` |
| `who_must_act` | "For an NDC whose label lacks a current boxed warning, list each party in the chain from the repackaged product up to the reference drug and say who is able to update the label." | `{ndc: string, fact_id?: string}` | `WhoMustAct` |
| `label_history` | "Return every DailyMed version of a label with whether each version carried the boxed warning, and any recorded landing." | `{ndc?: string, set_id?: string}` | history object |
| `open_gaps` | "List labels of record that still lack an active boxed-warning fact, optionally for one labeler or one fact." | `{party_id?: string, fact_id?: string}` | W3 rows |
| `fanout` | "Count every label of record in scope of a safety fact and how many carry it, carry it uncoded, or lack it." | `{fact_id: string}` | census + rows |
| `copy_lag` | "List repackaged labels revised after their source label already carried the warning, yet still lacking it." | `{fact_id: string}` | D3 rows |
| `supply_families` | "Group products into supply families (shared source products and applications) with carrying and lacking counts." | `{fact_id: string}` | R1 rows |
| `source_hubs` | "Rank source products by how many repackaged products copy them (PageRank): a label fix there reaches the most labels." | `{}` | A1 rows |
| `proof_path` | "Shortest typed path from a safety fact's reference drug to an NDC, or proof that the NDC is not in scope." | `{ndc: string, fact_id: string}` | V2 result |
| `alternatives` | "Other active products of the same molecule, form and strength whose label of record carries the boxed warning in a coded section." | `{ndc: string, fact_id: string}` | V6 rows |
| `watch` | "Watch a stock item for this organisation; a new label version reopens its ruling for the owner." | `{tenant: string, token: string, stock_item_id: string}` | `{watching: true}` |
| `confirm_check` | "Record what a pharmacist sees on the rendered DailyMed label version (coded, text only, absent). Two independent organisations raise the check's trust tier for everyone." | `{tenant: string, token: string, person_id: string, version_id: string, fact_id: string, result: "CARRIES_CODED" \| "CARRIES_UNCODED" \| "ABSENT"}` | confirm result |
| `verify_fact` | "Verify a safety fact and its phrase key against the FDA source; the first verification activates it for everyone." | `{tenant: string, token: string, person_id: string, fact_id: string}` | verify result |

Every MCP call with a tenant writes a `Turn` (T11) to the tenant's `Conversation` (persistent conversation history, Track 2).

## Add-on endpoints (BLUEPRINT section 18)
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/tenants/{t}/ask` | `{question}` | `{template, params, rows, cypher, sources, answer_text}` (F18, ADD4) |
| POST | `/api/tenants/{t}/webhooks` | `{url}` (admin-allowlisted) | `{id}` (ADD5) |

Additional MCP tool (ADD4): `ask_org` - "Answer a question about how an organisation holds and decides on drug products (who is responsible, which stock rests on a label, reopened rulings, decisions), from its graph, with sources." Input `{tenant, token, question}`.
