# Landfall in two minutes (every team member must be able to say this)

**The problem.** In April 2020 FDA added a boxed warning (its strongest) to montelukast for serious neuropsychiatric events. FDA changes the reference drug's label; generic makers follow; repackagers copy a source product's label onto their own. Nobody checks the last hop. Today, of 69 montelukast labels of record behind active listings, 13 still lack the warning (9 of them were revised after April 2020 without it) and 2 carry the text but not as a coded section that machines read.

**What we built.** An agent system on FalkorDB that answers "does the label for this NDC carry the current boxed warning, and if not, who can fix it?", shows the path and the version evidence, remembers every ruling per organisation, shares pharmacist-confirmed checks without revealing who holds what, and reopens rulings when DailyMed publishes a new version.

**The graph model.**
- `hub` (public): `Package -[:PACKAGE_OF]-> Product -[:UNDER]-> Application -[:REFERENCES]-> Application (reference drug) <-[:ISSUED_ON]- SafetyFact`; `Product -[:SOURCED_FROM]-> Product` (repackager to source); `LabelSet -[:DESCRIBES]-> Product`, `LabelSet -[:HAS_VERSION]-> LabelVersion -[:CHECKED {result, tier}]-> SafetyFact`; `Party -[:HOLDS {from, to}]-> Application`, `Party -[:PUBLISHES]-> LabelSet`; `LandingEvent`.
- One graph per organisation, plus sandboxes: `Site`, `Person`, `StockItem`, `FormularyEntry`, `Ruling -[:RESTS_ON]-> Basis`, `Decision`, `Event`, `Task`, `Playbook`, `Conversation`.
- Check tiers: 1 automated (section code + phrase key), 2 confirmed by a pharmacist, 3 confirmed by two organisations.

**The queries you must be able to explain.**
- **V1** turns an NDC into its product and its label of record: the SPL that an active NDC Directory listing points to. That gate stops old SPLs from producing false alarms.
- **V2** is the scope proof: the shortest typed path from the product up to the application FDA changed; no path means "not affected".
- **V4** is the verdict, decided in Cypher: it orders the label's versions up to a date, takes the current one, counts revisions after the fact, and returns LANDED, LANDED_UNCODED, NOT_LANDED_REVISED or NOT_LANDED_UNREVISED.
- **V5 and D3** walk to the source product a repackager copies and compare timelines: "this label was revised 1,147 days after its source already carried the warning".
- **W1** walks the chain of holders and labels to say who can act, and finds the authority gap where no upstream label exists to copy.
- **D1** fans a fact out to every label of record in scope; **R1** (WCC) groups supply families; **A1** (PageRank) finds the source labels most copied; **A2** (betweenness) finds chokepoint applications; **W4** (BFS) shows a product's upstream.
- **P1** records a salted hash of each confirming organisation on a check; a confirmation raises its tier for everyone.
- **T3** finds every ruling in an organisation that rests on a changed label; **T4** reopens it as a task for the responsible pharmacist.

**Why FalkorDB, and why it is load-bearing.** The verdict itself is a Cypher query; stop FalkorDB and `/api/landed` returns 503. One instance holds the public hub, each organisation's private graph, visitor sandboxes and replay copies (`GRAPH.COPY`). Traversals are fast enough to run inside every agent call over MCP.

**Decisions and trade-offs.**
- The graph decides; the LLM only phrases explanations and drafts, and the product works without it.
- No label text is stored: section codes and a phrase key decide; the UI links to DailyMed.
- Red verdicts only behind active listings, always with version and date, never accusing anyone; Landfall never sends notices.
- Strict mode: an absence must be confirmed by a pharmacist before it is red.

**What we would do next.** More facts (every boxed-warning change), real pharmacy inventories via file upload, DailyMed change feeds instead of polling, the aviation adapter.
