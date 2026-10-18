# AGENTS.md: rules for every coding agent working on Landfall

Read `BLUEPRINT.md` section 0 (document map) before writing code. The binding documents are AGENTS.md, BLUEPRINT.md, docs/GOALS.md, docs/FLOWS.md, docs/API.md, docs/UI.md, docs/queries.cypher and docs/REQUIREMENTS.md; this file is the short list of rules. When the spec and your instinct disagree, follow the spec and leave a note in `docs/TASKS.md` under "Questions for the owner".

## Deadline and priorities
- Submissions close Sunday 18 Oct 2026, 11:59 PM IST. Work through `docs/GOALS.md` top to bottom (140 goals with acceptance tests); `docs/TASKS.md` is the hour-by-hour summary. Do not stop until every goal is done or explicitly struck through with a reason.
- The hour-8 core (type an NDC, get a verdict with path, versions, source and who can act, deployed: G035-G054) must never break. Every later feature is additive.
- If you are behind, cut in the order listed in BLUEPRINT.md section 14 (core) and section 18 (add-ons). Never cut the core, the README requirements or the eval.

## Product rules (do not break)
1. Verdicts come from FalkorDB (`docs/queries.cypher`): identity and gate (V1), scope (V2), the verdict class (V4, a Cypher CASE). Never compute scope, timelines or classes in Python and only mirror them into the graph.
2. Deterministic code decides carries (section code `34066-1` + phrase key). An LLM may only phrase explanations and drafts from evidence it is given, or pick an Ask template. With no LLM key, templates are used and everything still works.
3. Landfall never sends anything outward (no email, fax, posting or form submission). Drafts become "ready to copy" after an authenticated human approves. Internal tenant actions also need a named person's click.
4. Label versions, landing events, rulings, bases, decisions, events and turns are append-only. A changed answer is a new ruling that supersedes the old one. Only a check's tier, confirmers and dispute flag change in place (I10, P1, P3).
5. Wording: "the DailyMed label of record (version N, date) lacks a coded boxed-warning section", "carries the text but not as a coded section", "revised after the warning was added without it", "the party able to update this label". Never "non-compliant", "violation", "illegal", "negligent", "failed to", "unsafe", "dangerous" or anything accusing a named labeler or person. Every verdict shows "Automated screening of public FDA and NLM data. Not medical, legal or regulatory advice. Not endorsed by FDA or NLM."
6. Red verdicts only for the label of record behind an active NDC Directory listing (the listing gate in V1). Strict mode needs a pharmacist-confirmed absence (tier >= 2).
7. Never store label text in the repo or the graph: identifiers, dates, section codes, phrase keys and results only. Test fixtures for SPL parsing are synthetic files we write.
8. The hub never stores which organisation holds which NDC. Confirmations and fact verifications reach the hub only as salted hashes through the Publisher.
9. Demo organisations and people are fictional and labelled "(fictional)". Do not write `eval/labels.json`: a human writes it (G080).

## Engineering rules
- FalkorDB is the heart of the product (sponsor constraint): every answer and every memory write goes through FalkorDB; caches may hold raw DailyMed and openFDA HTTP responses only, never answers.
- Python 3.12, FastAPI, pydantic v2, httpx (async), lxml, `falkordb` client, `mcp>=1.10,<2` (mcp 2.x renamed FastMCP; do not upgrade). Next.js App Router with TypeScript for the web app.
- All Cypher lives in `services/api/app/graph/queries.py`, generated from `docs/queries.cypher` by the `// @query` markers, parameterised. No string-built Cypher with user input.
- Bounded variable-length paths only (`*0..3`, `*1..3`, `*1..5`). No unbounded `*`.
- Use `ro_query` for reads. Use MERGE on ids for idempotent ingest writes. X6 runs only on graphs whose name starts with `hubr_`.
- Every DailyMed and openFDA call goes through `app/sources/http.py`: per-host limiter, cache, 15 s timeout, retries with backoff on 429/5xx, a clear error when a source is down, `OPENFDA_API_KEY` when set.
- Every endpoint validates input (NDC, set id, fact id, date patterns in API "Conventions"), returns typed errors, and logs with a request id. No secrets or tokens in logs.
- Tests: pytest against a FalkorDB service container with the golden fixture `data/fixtures/hub_montelukast.json`; golden tests in `services/api/tests/golden/` must stay green. Add a test for every bug fixed.
- Do not commit secrets. `.env` is git-ignored; `.env.example` lists every variable.
- Git: conventional commits (`feat(api): ...`, `fix(web): ...`), one logical change per commit, stage only the files the task touched. Commit after each completed goal. Never push: humans decide when to push.

## Definition of done for any task
- Build passes, tests pass, the deployed `/api/health` is green.
- The README section affected is updated (data model, queries, setup, tracks, AI disclosure).
- The acceptance criteria in `docs/GOALS.md` are met and ticked (and `docs/TASKS.md`).
