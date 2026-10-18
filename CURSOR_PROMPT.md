# Prompt to paste into Cursor (Agent mode)

You are building Landfall for the Graph Hacks hackathon (WeMakeDevs x FalkorDB). Submissions close Sunday 18 Oct 2026, 11:59 PM IST. Landfall proves whether an FDA boxed warning actually landed on the label of record for a drug NDC, and who can act if it did not.

Before writing any code, read these files in this order and treat them as binding:
1. `AGENTS.md` (rules)
2. `BLUEPRINT.md` section 0 (document map and precedence), then the rest of BLUEPRINT.md
3. `docs/GOALS.md` (140 numbered goals with acceptance tests: your work list)
4. `docs/FLOWS.md`, `docs/API.md`, `docs/UI.md`, `docs/queries.cypher`, `docs/REQUIREMENTS.md`
5. `data/*` (especially `data/fixtures/hub_montelukast.json`) and `docs/OPEN_POINTS.md`

How to work:
- Work through `docs/GOALS.md` from G001 in order. For each goal: implement it, run its Verify step, and only then tick it with the date. Do not start the next milestone while any goal in the current one fails its Accept condition. Exception: G080 (human eval labels) happens in Block 1, owned by a human.
- FalkorDB is the heart of the product. Every answer and every memory write goes through FalkorDB using the Cypher in `docs/queries.cypher` (generate `services/api/app/graph/queries.py` from the `// @query` markers; never edit queries only in Python). The verdict class comes from query V4; never recompute it in Python.
- Build golden tests on the fixture first: load it with the fixture loader (G016) and assert the numbers in GOALS (54 / 2 / 9 / 4, the hero path, the 1,147-day copy lag). They are the regression net for the H8 core.
- Pin `mcp>=1.10,<2`. Mount MCP exactly as BLUEPRINT section 3 describes.
- Never store label text in the repo or the graph. SPL parser tests use synthetic XML files you write. Recorded openFDA responses must have label text fields removed before committing.
- Landfall never sends anything outward. Drafts are "ready to copy" after human approval.
- Wording rules in `docs/UI.md` are enforced by a test (G052). Never accuse a named labeler.
- Do not write `eval/labels.json` yourself. A human writes it (G080). Stop and ask when you reach that point if it is missing.
- If two documents disagree, follow the precedence order in BLUEPRINT section 0 and write the conflict under "Questions for the owner" in `docs/TASKS.md`.
- If something in the docs is impossible or wrong (for example DailyMed changed a response shape), do not improvise silently: write it under "Questions for the owner" and continue with the next goal you can do.
- Protect the hour-8 core (G035-G054). Never break it while building later goals.
- If time runs short, cut only goals marked *(cuttable)*, in the order of BLUEPRINT section 14 and section 18, and strike them through with a reason.
- Commit after each completed goal with a conventional commit message (`feat(api): ...`, `fix(web): ...`), staging only the files that goal touched. Never push; the owner pushes.

At the end of every milestone (M1 to M8), stop and post a short report: goals done, goals failing with the exact error output, anything cut, and questions for the owner.

Start now with G001.
