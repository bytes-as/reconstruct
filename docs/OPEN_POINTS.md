# Open points

## Resolved before handoff (18 Oct 2026)
| Point | Resolution | Evidence |
|---|---|---|
| Scope: one domain or two | Drugs only (final panels). Montelukast hero, zolpidem second molecule activated by fact verification; aviation is add-on ADD6, cut first | BLUEPRINT 1, 18 |
| Is the montelukast finding real? | Yes. Drugs@FDA NDA020829 S-073 LABELING approved 2020-04-29 (also NDA020830 S-075, NDA021409 S-051). openFDA: 64 labels, 15 without `boxed_warning`; 13 without the boxed-warning header text (Proficient Rx 10, NuCare 3); AvKARE and AvPAK carry the text uncoded | BLUEPRINT 4 "Verified demo facts" |
| Gate on active listings | The label of record is the SPL whose current document id equals the NDC Directory `spl_id` with a future `listing_expiration_date`. DailyMed lists 116 montelukast sets; 69 pass the gate; the 13 lacking labels all pass (expiration 2026-12-31 or 2027-12-31); 47 SPLs are not labels of record (e.g. Aurobindo 2014 set 7636a692) | V1, I13, fixture |
| openFDA vs DailyMed coverage | openFDA has 64 of the 69 labels of record; 5 DailyMed-only labels (published Sep 2026) all carry the coded section. DailyMed is the source of truth | BLUEPRINT 4 |
| A real "version N lacks, N+1 carries" loop | Accord set 6eea668f: v12 (2021-03-05) ABSENT, v14 (2021-05-21) CARRIES_CODED. Also AvKARE v20 -> v21 (text only), AvPAK v7 -> v8, Bryant Ranch 3ff4100f v1 -> v2, American Health Packaging fb1b2e4e v5 -> v6, Preferred 09b0bc9e v1 -> v2 | archived SPL ZIPs via `getArchivalFile.cfm` |
| Where DailyMed keeps old versions | `history.json` gives versions and dates; the HTML `drugInfo.cfm?setid=` lists `getArchivalFile.cfm?archive_id=N` per version; the archive is a ZIP with the SPL XML. `spls/{setid}.xml?version=` is ignored | FLOWS F2.5 |
| How repackagers reference sources | SPL `asEquivalentEntity/definingMaterialKind/code` (NDC code system) per product; openFDA exposes the label-level union as `openfda.original_packager_product_ndc`. Multi-product labels must use the SPL per-product mapping (AvKARE 42291-622 -> 62175-204, 42291-623 -> 62175-205) | spl.py, fixture |
| Who must act when the chain is broken | Proficient Rx 63187-626 -> West-Ward 0143-9650 (SPL 2015, no active listing); Drugs@FDA holder of ANDA203037 is now PHARMOBEDIENT, which has no DailyMed montelukast label -> AUTHORITY_GAP. Granules: RLD NDA021409 Discontinued, reference standard ANDA203438 (Ajanta) | W1, W2 |
| Drugs@FDA search gaps | Generic-name search misses ANDA203037, ANDA204290, ANDA208621, ANDA204604 (no `openfda` block); fetch every application number referenced by a product | FLOWS F2.3 |
| Licensing | openFDA: CC0 for content unless noted (verified on open.fda.gov/license); openFDA terms warn some works come from private entities. NLM web policy: users determine copyright for non-public-domain material. Decision: store no label text; link to DailyMed; disclaimer; no endorsement implied | BLUEPRINT 2.6 |
| Rate limits | openFDA 240/min and 1,000/day per IP without a key, 120,000/day with a free key (verified). DailyMed: none published; self-cap 2 rps | BLUEPRINT 4 |
| GitHub crowding | 0 repos for `falkordb` + drug label / dailymed / openfda / boxed warning / repackager / pharmacovigilance / drug safety / fda / ndc. Nearest: shortagebridge-falkordb (drug shortage), RecallRX (repurposing memory), firstdomino (prescribing cascades) | `gh api search/repositories`, 18 Oct |
| Strict mode semantics | Strict requires tier >= 2 only for ABSENT results (a red verdict needs a pharmacist); carrying results count from tier 1 | V4 comment, BLUEPRINT 5.1 |
| Betweenness repeatability | `samplingSize: 2000` (above the node count) makes A2 exact and repeatable at our scale (ANDA202843 24, ANDA200405 20, ANDA204093 12) | A2 |
| Zolpidem fact date | Ambien NDA019908 S-046 LABELING approved 2019-08-18; Ambien SPL v16 (Feb 2019) has no boxed warning, v17 (published 2019-09-03, effective 2019-08-29) has a coded section with the phrase. Shipped UNVERIFIED on purpose (F16 demo) | facts.seed.json |
| FalkorDB facts | Data path `/var/lib/falkordb/data`; `REDIS_ARGS`; `FALKORDB_ARGS` default `TIMEOUT 1000` -> set 5000; no password by default -> `requirepass`; GRAPH.COPY fails if destination exists | BLUEPRINT 3 |
| MCP mount | mcp 1.30.0: `FastMCP(..., stateless_http=True)`, `app.mount("/", mcp.streamable_http_app())` after routes, lifespan runs `mcp.session_manager.run()`; pin `mcp>=1.10,<2` (verified during the ModelBrain build; pip on the spec author's host is broken, so it was not re-run for Landfall) | BLUEPRINT 3 |

## Query test log (18 Oct 2026, falkordb/falkordb:latest, module 42201)
Method (reproduce with `scripts/query_check.py`): `docker run -d --rm --name lf-test falkordb/falkordb:latest`; the fixture `data/fixtures/hub_montelukast.json` was loaded into graph `hub_test` **through the I-queries themselves** (1,278 commands, 0 errors); both tenant files were loaded into `tenant_bayview` and `tenant_northgate` (0 errors); every named query was then run with `redis-cli --json GRAPH.QUERY <graph> "CYPHER k=v ... <query>"`. All 76 blocks ran without error. Key results:
- V1 `68071-3355-9` -> record set 549f1d1a; `65862-574-10` -> record set ba42b0a9 (old set 7636a692 excluded); unknown NDC -> no row.
- V2 hero path `[68071-3355, ANDA202717, NDA020829]` rels `[UNDER, REFERENCES]`; bulk `65862-843` -> `no_path = true` on all 3 rows.
- V4 over the 69 D1 sets: LANDED 54, LANDED_UNCODED 2, NOT_LANDED_REVISED 9, NOT_LANDED_UNREVISED 4. As-of: Accord 2020-06-01 UNREVISED, 2021-03-10 REVISED, 2021-06-01 LANDED; AvKARE 2025-11-01 REVISED, 2025-11-20 LANDED_UNCODED; Preferred 2020-05-15 UNREVISED, 2021-09-01 LANDED. Strict hero -> UNKNOWN; NuCare 56429f04 strict UNKNOWN -> after one P1 confirmation NOT_LANDED_REVISED.
- V5 hero source 16729-119 first carry v14 2021-05-21. V6 hero 8 alternatives. W1 63187-626: hop 1 0143-9650 inactive, no label set, holder PHARMOBEDIENT. W2 granules -> ANDA203438 (AJANTA). W3 13 rows. W4 BFS closure: Molecule, NDA020829, ANDA202717, Product 16729-119.
- D1 69 rows; D2 Accord downstream 6 products; D3 14 rows (AvKARE 1,697 days max; hero 1,147); D4 17 publishers (Aurobindo 19 days fastest); D5/D6 ledger write and read (Accord 387 days).
- R1 families (Accord family 7 products: 4 carrying, 3 lacking); A1 top 31722-726 (8 repackagers); A2 top ANDA202843; A3 20 communities.
- P1 idempotent per org; tier 2 at one org, 3 at two; a later conflicting I10 marks the check disputed; P3 resolves; P2 activates a fact.
- T1-T21, K1-K8, X1-X6 all return the expected rows (ruling with 2 bases, supersede, reopen, lease claim, handoff, sign, decision, traces, tasks with playbook steps, draft, conversation turn, ask templates, registry, sandbox records, replay hide).
- Bugs found and fixed during testing: D3 mixed an aggregate with a non-grouped variable (null lag) -> split into two WITH steps; D4 lost the fact variable after aggregation -> carried it in the grouping; A2 sampled betweenness was not repeatable -> samplingSize 2000.

## Deferred to the end (safe to leave until the build is done)
| Point | Why it can wait | When | Owner |
|---|---|---|---|
| Re-verify the MCP mount with the pinned SDK in the API container | Verified in the ModelBrain build; same code | Block 3, G068 | A |
| SPL `<approval>` element path for application numbers | NDC Directory `application_number` already gives the application per product; the SPL path is a cross-check | Block 1, G023 | A |
| NLM copyright page (JS-rendered, not fully read) | We store no label text either way | Block 7 | B |
| Zolpidem SPL set count and gaps on DailyMed (openFDA shows 116 labels, 17 without the phrase) | Only needed if G104 ships | Block 5 | A |
| Ambien S-046 letter content (PDF fetch redirected to HTML) | Label history already shows the boxed warning landing at the RLD on 2019-09-03 | Before G104 | B |
| Whether DailyMed publishes new versions for any of the 13 open gaps before judging | The Watcher records it if it happens; G049 compares live vs fixture | Judging day | A |
| Repository licence and ownership (rule 15) | Needed only at submission | Block 7, G125 | Team |
| Blog post (side prize) | After submission is fine | After G131 | B |

## Not open (decided; do not revisit)
See BLUEPRINT section 16.5.
