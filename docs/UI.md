# Landfall web app specification

Next.js (App Router, TypeScript, Tailwind) deployed on Vercel. Calls the API at `NEXT_PUBLIC_API_URL`. Every page works at 375 px wide. Every verdict view shows the disclaimer: "Automated screening of public FDA and NLM data. Not medical, legal or regulatory advice. Not endorsed by FDA or NLM."

## Visual language
- Background near-black slate `#0f1419`, surface `#161d25`, text `#e6ebf0`, muted `#98a3b1`, one accent teal `#43c2cb`. Light mode optional.
- Verdict colours (semantic): LANDED green `#2fbf71`; LANDED_UNCODED teal-green `#7fcf9a` with a dashed border; NOT_LANDED_REVISED red `#f0605a`; NOT_LANDED_UNREVISED orange `#f08a4b`; NOT_IN_SCOPE slate `#6b7785`; NOT_ASSESSED_INACTIVE_LISTING and UNKNOWN grey `#9aa3ae`; QUEUED blue `#5aa9f0`.
- Path graph: nodes by kind (Package/Product circle, Application square, reference drug square with a star); edges labelled with their type (UNDER, REFERENCES, SOURCED_FROM); the held product on the left, the reference drug on the right.
- Timeline: one dot per version on a date axis; filled green = CARRIES_CODED, hollow green = CARRIES_UNCODED, red = ABSENT, grey = unchecked; a vertical line at the fact date and a shaded 30-day grace window.
- Typeface: Inter Tight for headings, Inter for body, JetBrains Mono for NDCs, set ids and Cypher.

## Wording rules (enforced by G052)
- Say: "label of record", "lacks a coded boxed-warning section", "carries the boxed-warning text but not as a coded section", "was revised after the warning was added to the reference label without it", "not revised since", "the party able to update this label", "the regulator".
- Never say (forbidden words, case-insensitive, checked by a test): "non-compliant", "noncompliant", "violation", "violating", "illegal", "negligent", "failed to", "unsafe", "dangerous", "stale label", "fraud", "endorsed by FDA", "FDA-approved label" (when describing a repackager label).
- Always attach the version number and date to a claim about a named labeler. Never say "the bottle lacks"; say "the DailyMed label of record lacks".
- Organisations and people are shown with "(fictional)". Errors say what went wrong and how to fix it, without apologies.

## Global layout
- Top bar: logo "Landfall", nav: Check an NDC, Facts, Replay, Organisations, Checks, MCP, Eval, How it works. A status dot reads `/api/health` (green up, amber degraded sources, red down with the banner "The graph database is restarting. Try again in a minute.").
- Fixture-mode badge when `fixture_mode` is true: "Offline snapshot of 16 Oct 2026".
- Footer: "Built for Graph Hacks with FalkorDB · Data: DailyMed (NLM) and openFDA (FDA) public data · Automated screening, not medical, legal or regulatory advice · Not endorsed by FDA or NLM · Organisations shown are fictional."

## Verdict copy (exact strings; `{}` are fields)
| Verdict | Badge | One-line reason |
|---|---|---|
| LANDED | LANDED | "The DailyMed label of record (version {v}, {date}) carries the boxed warning in a coded boxed-warning section." |
| LANDED_UNCODED | LANDED (TEXT ONLY) | "The DailyMed label of record (version {v}, {date}) contains the boxed-warning text, but not as a coded boxed-warning section. Machine readers such as openFDA may not see it." |
| NOT_LANDED_REVISED | NOT LANDED (REVISED WITHOUT IT) | "The DailyMed label of record (version {v}, {date}) lacks a coded boxed-warning section and the boxed-warning text. It was revised {n} time(s) after FDA approved the warning on {issued}." |
| NOT_LANDED_UNREVISED | NOT LANDED (NOT REVISED SINCE) | "The DailyMed label of record (version {v}, {date}) predates the boxed warning approved on {issued} and has not been revised since (30-day grace window)." |
| NOT_IN_SCOPE | NOT IN SCOPE | "No path from this safety fact to this product: it is not affected. Searched {searched} from {from} to {targets}." |
| NOT_ASSESSED_INACTIVE_LISTING | NOT ASSESSED | "No active NDC Directory listing points to this label, so Landfall does not assess it." |
| UNKNOWN (NDC_NOT_FOUND) | UNKNOWN | "This NDC is not in the NDC Directory or DailyMed. Check the dashed NDC printed on the label." |
| UNKNOWN (SCOPE_UNRESOLVED) | UNKNOWN | "Landfall could not resolve this product's application yet, so it will not guess." |
| UNKNOWN (LABEL_OF_RECORD_NOT_INGESTED) | UNKNOWN | "The label this listing points to is not ingested yet. Try again in a minute." |
| UNKNOWN (NOT_CHECKED) | UNKNOWN | "This label version has not been checked yet." |
| UNKNOWN (ABSENCE_NOT_CONFIRMED) | UNKNOWN | "Strict mode: the absence has not been confirmed by a pharmacist yet." |
| UNKNOWN (DISPUTED) | UNKNOWN | "Pharmacists disagree about this label version; it is under review." |
| no fact | NO VERIFIED FACT | "No verified safety fact for {molecule} in Landfall yet." |

## Who can act (exact role strings)
- AUTHORITY_GAP primary: role "holder of {application} per Drugs@FDA", reason "No active DailyMed label of record was found upstream of this product to update from." Oversight: "FDA - the regulator; can require safety labeling changes."
- SOURCE_CARRIES primary: role "labeler of record for this repackaged product", reason "Its source label ({source_ndc}) carries the warning since {date}."
- SOURCE_LACKS primary: role "labeler of the source product {source_ndc}", reason "The source label also lacks the warning."; secondary: the repackager labeler.
- OWN_LABEL primary: role "labeler of record", reason "This label is published by the labeler itself."; secondary (if different): "holder of {application}".
- LANDED_UNCODED action line: "Re-code the boxed warning as a boxed-warning section so machine readers see it."
- REFERENCE_DISCONTINUED annotation: "The reference drug {rld} is discontinued; FDA lists {application} ({holder}) as the reference standard."
- Party names are shown exactly as in the source data (labeler name from SPL, holder name from Drugs@FDA). Never a person.

## Pages

### `/` Check an NDC
- Heading: "Did the warning land?" Sub: "Type the NDC printed on a drug label. Landfall follows the real chain from FDA's labeling change to the label of record for that NDC in FalkorDB, and tells you whether the boxed warning is there and who can fix it if not."
- Input `ndc` (placeholder `68071-3355-9`), example chips: `68071-3355-9` (NuCare), `63187-626-30` (Proficient Rx), `42291-622-30` (AvKARE), `31722-726-90` (Camber), `16729-119-15` (Accord). Toggle "Strict mode (only pharmacist-confirmed absences)" (off). Button "Check". Navigates to `/ndc/<ndc>?strict=0`.
- Census strip (from `/api/facts/montelukast_bw_2020/fanout`): "Montelukast boxed warning (FDA, 29 Apr 2020): {LANDED} carry it · {LANDED_UNCODED} text only · {NOT_LANDED_REVISED} revised without it · {NOT_LANDED_UNREVISED} not revised since · of {total} labels of record." Link "See all" -> `/facts/montelukast_bw_2020`.

### `/ndc/[ndc]` Verdict
States:
- Loading (< 8 s): skeleton with "Following the chain in FalkorDB…".
- Queued (202): progress list from SSE ("Ingested DailyMed set 549f1d1a…", "Checked version 5…"), then automatic re-request.
- Error: envelope message + hint + "Try again".
- Empty results: the "no fact" copy and a link to `/checks` ("Verify a fact").
Content when done, one card per fact result:
1. Badge + one-line reason (Verdict copy). Under it: "Fact: {title}, approved {issued} ({supplements})". Replay banner when `replay`: "Replay as of {as_of}: listing gate skipped (listing history is not public)."
2. Product line: "{ndc} · {labeler_name} · {dosage_form} {strength} · listing active until {expiration}".
3. Path graph (react-force-graph-2d) from `scope.path`/`scope.rels`; clicking an application opens its Drugs@FDA page; clicking the product opens its DailyMed label.
4. Timeline of `versions` with the fact line and grace window; each dot links to `dailymed_url` (current or archived version).
5. Upstream card (when `upstream` non-empty): "Source {source_ndc} ({source_labeler}) carries the warning since version {n}, {date}." plus, when `copy_lag_days`, "This label was revised {copy_lag_days} days after its source already carried it." Source with inactive listing: "Source {source_ndc} has no active NDC Directory listing."
6. Who can act (copy above), with the W1 rows in a collapsible "Chain" table.
7. Alternatives (NOT_LANDED_* and LANDED_UNCODED): "Alternatives in Landfall's catalogue with a coded boxed warning (same molecule, form and strength)"; empty -> "No alternative with a coded boxed warning in Landfall's catalogue."
8. "How we decided" collapsible: the three Cypher texts (V1, V2, V4) with parameters, `computed_ms`, the tier legend ("tier 1 automated check · tier 2 confirmed by a pharmacist · tier 3 confirmed by two organisations"), and the Upstream closure from `/api/products/{ndc}/upstream` (W4, algo.BFS).
9. Actions: "Save as a ruling for an organisation" (tenant picker; creates a sandbox if needed; asks for the stock item), "Confirm what you see on DailyMed" (links to `/checks?version_id=`), "Draft a note" (tenant context, only when the check is tier >= 2; otherwise disabled with "Confirm the check first"), "Copy MCP command".
10. Disclaimer.

### `/facts/[id]`
- Header: title, issued date, supplements (application + number + date), source link, status pill (ACTIVE / UNVERIFIED), "verified by {n} organisations".
- Census bar (D1 + V4) and table (set, publisher, version, date, verdict) with filters.
- Copy lag table (D3): labeler, NDC, source NDC, source first carry, revisions without it, max lag days.
- Latency (D4): bar chart per publisher (median days); landing ledger (D6) list.
- Supply families (R1): cards "Family of {n} products: {carrying} carry, {lacking} lack" with sample NDCs.
- Source hubs (A1) and chokepoints (A2) tables; label families (A3) if shipped.
- Open gaps (W3) grouped by publisher with versions and dates.

### `/replay`
- Preset buttons: "Accord (ANDA holder): lacking in v12 (5 Mar 2021), coded in v14 (21 May 2021)", "AvKARE: lacking v17-v20, text only in v21 (17 Nov 2025)", "Bryant Ranch", "American Health Packaging".
- Scrubber over `/api/replay/{set_id}/timeline` points: badge and one-line reason change at each point; the landing ledger entry appears at the landing point ("Landed after {latency_days} days").
- "Run the Watcher on this history" (if G100 shipped): starts a replay (`/api/replay/start`, template picker Bayview or Northgate), shows "Next version" button, and lists reopened rulings and tasks in the replay sandbox.
- Footer note: "Live: the Watcher polls DailyMed every {WATCH_INTERVAL_MINUTES} minutes for the labels with open gaps."

### `/orgs`
- Two columns: Bayview Community Pharmacy Group (fictional, pharmacy chain) and Northgate Health System (fictional, hospital, strict mode); plus "Your sandbox" column if one exists.
- Per organisation: sites with responsible pharmacist; stock table (NDC, display name, latest verdict pill, decided at, "trace" link); formulary entries with owner and last decision (T15) and a "Record decision" button (sandbox); open tasks with Claim / Approve / Reject (sandbox) and playbook steps; events timeline (T20).
- Button "Try it as this organisation" -> `POST /api/sandbox` -> token in sessionStorage -> the column switches to the sandbox.
- Trace drawer (T7): verdict; bases (set id, version, date with DailyMed link, section code, check result and tier, scope path); events with signer. Decision trace drawer (T12): decision, who decided, ruling, bases, signers.

### `/checks`
- Section "Confirm what you see": the queue from `/api/checks/queue`: set title, publisher, version, date, Landfall's automated result, tier, confirmations, "Open on DailyMed" link, and three buttons "Coded boxed warning", "Text only", "Absent" (enabled in a sandbox or with admin). After a click: "Thanks. Tier {before} -> {after}. {n} rulings reopened in other organisations." Never names other organisations.
- Section "Verify a fact": UNVERIFIED facts with source link, supplements and phrase key; button "I verified this fact against the FDA source" (sandbox or admin). After a click: "Fact activated. Landfall is checking {molecule} labels now." with job progress.

### `/mcp`
- Command block: `claude mcp add --transport http landfall https://<api-host>/mcp` with copy button; Cursor config JSON; tool table from `docs/API.md`; the pharmacy agent command `python examples/pharmacy_agent/agent.py --api https://<api-host>` and its sample output; the recording.

### `/eval`
- Labels hash (from `eval/labels.sha256`), metric cards (verdict accuracy, false-red count, gate false-red count, who-can-act accuracy, UNKNOWN rate, replay accuracy), comparison table vs the openFDA field script, openFDA text grep and (if present) LLM baselines, the "cannot do" columns, per-case table with filters, held-out section if present.

### `/how-it-works`
- Diagram of the graphs on one FalkorDB instance (hub, tenants, sandboxes, replay hubs); the hub schema (BLUEPRINT 5.1) with arrows pointing upstream; the verdict path and the V4 decision; tiers and the privacy rule; the agents and their handoffs; the algorithms used and why; the wording rules; link to the repo and `docs/queries.cypher`.

## Add-on UI (BLUEPRINT section 18)
- `/orgs`: "Ask this organisation" box with example chips ("Who is responsible for Bayview Pharmacy #12?", "Which stock items rest on DailyMed set 549f1d1a…?", "Which rulings reopened today?"), the answer table, the Cypher used, sources (ADD4).
- `/checks`: candidate facts from the Drugs@FDA watch with "needs a phrase key" (ADD3).
