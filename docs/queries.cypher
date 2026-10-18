// Landfall: every Cypher query the product runs, for FalkorDB.
// Graph "hub" holds public facts (DailyMed, openFDA NDC Directory, Drugs@FDA, verified safety facts).
// Graphs "tenant_<slug>" and "sbx_<id>" hold one organisation each (fictional demo tenants).
//
// FORMAT (machine-read by tests/test_queries_in_sync.py): every query starts with a line
//   // @query <NAME> <one-line description>
// followed by optional comment lines and exactly ONE Cypher statement ending with ';'.
// Schema blocks start with "// @schema hub" or "// @schema tenant" and hold one index statement per line.
// Copy each block verbatim into services/api/app/graph/queries.py as a named constant.
// Names: SCHEMA_*, I (ingest), V (verdict), W (who must act), D (fan-out, reopen, latency), L (label history),
// P (publisher), R1 (WCC), A (algorithms), T (tenant), K (ask templates, add-on), X (registry, sandboxes).
// No query name starts with F, G, H or S, so names never clash with flows (F0-F19), goals (G001-G140)
// or requirement rows (H1-H20, S1-S27).
//
// Dates: every comparable date is an integer day number (days since 1970-01-01 UTC) in a property ending "_d";
// the ISO string ("2020-04-29") sits next to it for display. All parameters are passed with falkordb-py:
// graph.query(q, params) / graph.ro_query(q, params). Never build Cypher strings from user input.
//
// VERIFIED on 18 Oct 2026 against falkordb/falkordb:latest (module version 42201) with
// `docker exec lf-test redis-cli GRAPH.QUERY <graph> "CYPHER k=v ... <query>"`, loading the real
// montelukast fixture (data/fixtures/hub_montelukast.json through the I-queries) and the two demo tenants:
//   every block below parses and runs and returns the expected rows (see docs/OPEN_POINTS.md "Query test log");
//   bounded variable-length paths over several relationship types (SOURCED_FROM|UNDER|REFERENCES*1..5) work;
//   shortestPath over several relationship types works and returns NULL when no path exists;
//   algo.BFS(node, depth, NULL) follows every outgoing relationship type; algo.WCC, algo.pageRank,
//   algo.betweenness, algo.labelPropagation work with the config maps below; percentileDisc works;
//   GRAPH.COPY works (destination must not exist); MERGE ... ON CREATE / ON MATCH works; FOREACH with
//   CASE for conditional writes works; indexing an empty list returns null.
// Known FalkorDB caveat: do not bind relationship aliases you never use.

// ===========================================================================
// SCHEMA
// ===========================================================================
// @schema hub
CREATE INDEX FOR (m:Molecule) ON (m.key);
CREATE INDEX FOR (a:Application) ON (a.id);
CREATE INDEX FOR (p:Party) ON (p.id);
CREATE INDEX FOR (s:LabelSet) ON (s.set_id);
CREATE INDEX FOR (v:LabelVersion) ON (v.id);
CREATE INDEX FOR (p:Product) ON (p.ndc);
CREATE INDEX FOR (k:Package) ON (k.ndc);
CREATE INDEX FOR (f:SafetyFact) ON (f.id);
CREATE INDEX FOR (e:LandingEvent) ON (e.id);

// @schema tenant
CREATE INDEX FOR (si:StockItem) ON (si.id);
CREATE INDEX FOR (r:Ruling) ON (r.id);
CREATE INDEX FOR (b:Basis) ON (b.set_id);
CREATE INDEX FOR (t:Task) ON (t.id);
CREATE INDEX FOR (p:Person) ON (p.id);
CREATE INDEX FOR (d:Decision) ON (d.id);
CREATE INDEX FOR (fe:FormularyEntry) ON (fe.id);

// ===========================================================================
// INGEST (Scout, Matcher) - hub
// ===========================================================================

// @query I1 upsert a molecule
MERGE (m:Molecule {key: $key})
SET m.name = $name, m.unii = $unii
RETURN m.key AS key;

// @query I2 upsert an application from Drugs@FDA and link its molecule
MERGE (a:Application {id: $id})
SET a.kind = $kind, a.sponsor = $sponsor, a.dosage_forms = $dosage_forms,
    a.marketing_status = $marketing_status, a.reference_drug = $reference_drug,
    a.reference_standard = $reference_standard, a.updated_at = $now
WITH a
MATCH (m:Molecule {key: $molecule_key})
MERGE (a)-[:CONTAINS]->(m)
RETURN a.id AS id;

// @query I3 record the current holder of an application; any other open holding is closed (holder succession)
MATCH (a:Application {id: $application_id})
MERGE (p:Party {id: $party_id})
ON CREATE SET p.name = $party_name, p.kind = 'SPONSOR'
WITH a, p
OPTIONAL MATCH (other:Party)-[old:HOLDS]->(a)
WHERE other.id <> p.id AND old.to_d IS NULL
SET old.to_d = $today_d
WITH DISTINCT a, p
MERGE (p)-[h:HOLDS]->(a)
ON CREATE SET h.from_d = $from_d, h.source = $source
RETURN p.id AS holder, h.from_d AS from_d;

// @query I4 upsert an SPL set (DailyMed setid) and the labeler that publishes it
MERGE (s:LabelSet {set_id: $set_id})
SET s.title = $title, s.molecule_key = $molecule_key, s.current_version = $current_version,
    s.current_doc_id = $current_doc_id, s.current_published = $current_published,
    s.current_published_d = $current_published_d, s.ingested_at = $now
WITH s
MERGE (p:Party {id: $labeler_id})
ON CREATE SET p.name = $labeler_name, p.kind = 'LABELER'
MERGE (p)-[pb:PUBLISHES]->(s)
ON CREATE SET pb.from_version = $current_version
SET pb.to_version = $current_version
RETURN s.set_id AS set_id;

// @query I5 record one SPL version (append-only; a version is never edited after it is observed)
MATCH (s:LabelSet {set_id: $set_id})
MERGE (v:LabelVersion {id: $version_id})
ON CREATE SET v.set_id = $set_id, v.version = $version, v.doc_id = $doc_id, v.effective = $effective,
              v.published = $published, v.published_d = $published_d, v.archive_id = $archive_id,
              v.labeler_name = $labeler_name, v.observed_at = $now
MERGE (s)-[:HAS_VERSION]->(v)
RETURN v.id AS id;

// @query I6 upsert a product NDC from the NDC Directory (or from SPL only) and link it to its application
MERGE (p:Product {ndc: $ndc})
SET p.labeler_name = $labeler_name, p.molecule_key = $molecule_key, p.dosage_form = $dosage_form,
    p.strength = $strength, p.marketing_category = $marketing_category, p.listing_spl_id = $listing_spl_id,
    p.listing_expiration_d = $listing_expiration_d, p.in_ndc_directory = $in_ndc_directory, p.updated_at = $now
FOREACH (_ IN CASE WHEN $application_id IS NULL THEN [] ELSE [1] END |
  MERGE (a:Application {id: $application_id})
  MERGE (p)-[:UNDER]->(a))
RETURN p.ndc AS ndc;

// @query I7 an SPL set describes a product (from the NDC list of its current version)
MATCH (s:LabelSet {set_id: $set_id})
MERGE (p:Product {ndc: $ndc})
MERGE (s)-[:DESCRIBES]->(p)
RETURN s.set_id AS set_id, p.ndc AS ndc;

// @query I8 upsert a package NDC (what is printed on the bottle) under its product
MATCH (p:Product {ndc: $product_ndc})
MERGE (k:Package {ndc: $package_ndc})
SET k.description = $description
MERGE (k)-[:PACKAGE_OF]->(p)
RETURN k.ndc AS ndc;

// @query I9 a repackaged product names its source product (SPL asEquivalentEntity / openFDA original_packager_product_ndc)
MATCH (r:Product {ndc: $ndc})
MERGE (s:Product {ndc: $source_ndc})
MERGE (r)-[e:SOURCED_FROM]->(s)
ON CREATE SET e.source = $source, e.observed_at = $now
RETURN r.ndc AS ndc, s.ndc AS source_ndc;

// @query I10 write the Matcher's result for one (label version, safety fact); a human-confirmed result (tier >= 2) is never overwritten, a disagreement marks it disputed
MATCH (v:LabelVersion {id: $version_id}), (f:SafetyFact {id: $fact_id})
MERGE (v)-[c:CHECKED]->(f)
ON CREATE SET c.result = $result, c.method = $method, c.tier = $tier, c.phrase_key_version = $phrase_key_version,
              c.at = $now, c.confirmations = 0, c.confirmers = [], c.disputed = false
ON MATCH SET c.disputed = CASE WHEN c.tier >= 2 AND c.result <> $result THEN true ELSE c.disputed END,
             c.result = CASE WHEN c.tier >= 2 THEN c.result ELSE $result END,
             c.method = CASE WHEN c.tier >= 2 THEN c.method ELSE $method END,
             c.tier = CASE WHEN c.tier >= 2 THEN c.tier ELSE $tier END,
             c.phrase_key_version = $phrase_key_version, c.at = $now
RETURN c.result AS result, c.tier AS tier, c.disputed AS disputed;

// @query I11 upsert a safety fact (from data/facts.seed.json) and the reference applications it was issued on
MERGE (f:SafetyFact {id: $id})
SET f.molecule_key = $molecule_key, f.kind = $kind, f.title = $title, f.issued = $issued, f.issued_d = $issued_d,
    f.section_code = $section_code, f.phrase_key = $phrase_key, f.phrase_key_version = $phrase_key_version,
    f.source_url = $source_url, f.status = coalesce(f.status, $status)
WITH f
MATCH (m:Molecule {key: $molecule_key})
MERGE (f)-[:ABOUT]->(m)
WITH f
UNWIND $issued_on AS io
MATCH (a:Application {id: io.application_id})
MERGE (f)-[e:ISSUED_ON]->(a)
SET e.supplement = io.supplement, e.approved = io.approved
RETURN f.id AS id, f.status AS status, count(e) AS applications;

// @query I12 derive ANDA -> reference listed drug edges (same molecule, shared dosage form, RLD flag from Drugs@FDA)
MATCH (anda:Application {kind: 'ANDA'})-[:CONTAINS]->(m:Molecule {key: $molecule_key})<-[:CONTAINS]-(rld:Application)
WHERE rld.reference_drug = true AND any(df IN anda.dosage_forms WHERE df IN rld.dosage_forms)
MERGE (anda)-[r:REFERENCES]->(rld)
ON CREATE SET r.source = 'derived_same_molecule_and_form'
RETURN anda.id AS anda, rld.id AS rld;

// @query I13 mark which SPL sets are the label of record for an active NDC Directory listing (the listing gate)
MATCH (s:LabelSet {molecule_key: $molecule_key})
OPTIONAL MATCH (s)-[:DESCRIBES]->(p:Product)
WITH s, collect(p) AS ps
SET s.label_of_record = any(x IN ps WHERE x.listing_spl_id = s.current_doc_id AND coalesce(x.listing_expiration_d, 0) >= $today_d)
RETURN s.set_id AS set_id, s.label_of_record AS label_of_record;

// ===========================================================================
// VERDICT (Prover) - hub, read-only. The verdict class is decided inside V4.
// ===========================================================================

// @query V1 resolve an NDC (package or product) to its product, listing status and label of record
OPTIONAL MATCH (k:Package {ndc: $ndc})-[:PACKAGE_OF]->(pk:Product)
OPTIONAL MATCH (pp:Product {ndc: $ndc})
WITH coalesce(pk, pp) AS p
WHERE p IS NOT NULL
OPTIONAL MATCH (s:LabelSet)-[:DESCRIBES]->(p)
WITH p, collect(DISTINCT {set_id: s.set_id, is_record: s.current_doc_id = p.listing_spl_id}) AS sets
RETURN p.ndc AS product_ndc, p.molecule_key AS molecule_key, p.labeler_name AS labeler_name,
       p.dosage_form AS dosage_form, p.strength AS strength, p.listing_spl_id AS listing_spl_id,
       p.listing_expiration_d AS listing_expiration_d,
       coalesce(p.listing_expiration_d, 0) >= $as_of_d AS listing_active,
       [x IN sets WHERE x.is_record = true | x.set_id] AS record_sets,
       [x IN sets WHERE x.set_id IS NOT NULL | x.set_id] AS all_sets;

// @query V2 scope proof: shortest upstream path from the product to an application the fact was issued on; no_path = true on every row means NOT_IN_SCOPE
MATCH (f:SafetyFact {id: $fact_id})-[:ISSUED_ON]->(rld:Application)
MATCH (p:Product {ndc: $product_ndc})
WITH rld, shortestPath((p)-[:SOURCED_FROM|UNDER|REFERENCES*1..5]->(rld)) AS sp
RETURN rld.id AS rld, sp IS NULL AS no_path,
       CASE WHEN sp IS NULL THEN [] ELSE [n IN nodes(sp) | coalesce(n.ndc, n.id)] END AS path,
       CASE WHEN sp IS NULL THEN [] ELSE [r IN relationships(sp) | type(r)] END AS rels
ORDER BY no_path ASC, size(path) ASC;

// @query V3 facts that apply to a molecule (active facts only, unless include_unverified)
MATCH (f:SafetyFact {molecule_key: $molecule_key})
WHERE f.status = 'ACTIVE' OR ($include_unverified = true AND f.status = 'UNVERIFIED')
RETURN f.id AS fact_id, f.title AS title, f.kind AS kind, f.issued AS issued, f.issued_d AS issued_d,
       f.section_code AS section_code, f.phrase_key AS phrase_key, f.status AS status, f.source_url AS source_url
ORDER BY issued_d ASC;

// @query V4 the verdict for one (fact, label set) as of a date: timeline of versions, current version, revisions after the fact, verdict class
// $min_tier is the minimum tier for an ABSENT result to count (1 default, 2 strict); CARRIES results count from tier 1; disputed checks never count.
MATCH (f:SafetyFact {id: $fact_id})
MATCH (s:LabelSet {set_id: $set_id})-[:HAS_VERSION]->(v:LabelVersion)
WHERE v.published_d <= $as_of_d
OPTIONAL MATCH (v)-[c:CHECKED]->(f)
WITH f, s, v, c ORDER BY v.version ASC
WITH f, s, collect({version: v.version, version_id: v.id, doc_id: v.doc_id, published: v.published,
       published_d: v.published_d, archive_id: v.archive_id, tier: c.tier, method: c.method,
       result: CASE WHEN c IS NULL OR c.disputed = true OR c.tier < 1 OR (c.result = 'ABSENT' AND c.tier < $min_tier) THEN 'UNCHECKED' ELSE c.result END}) AS vs
WITH f, s, vs, CASE WHEN size(vs) = 0 THEN null ELSE vs[size(vs) - 1] END AS cur
WITH f, s, vs, cur, [x IN vs WHERE x.published_d >= f.issued_d + $grace_days] AS after
RETURN s.set_id AS set_id, f.issued AS fact_issued, f.section_code AS section_code, cur AS current, vs AS versions,
       size(after) AS revisions_after_fact, [x IN after | x.published] AS revised_on,
       [x IN vs WHERE x.result IN ['CARRIES_CODED', 'CARRIES_UNCODED']][0] AS first_carry,
       CASE
         WHEN cur IS NULL THEN 'UNKNOWN'
         WHEN cur.result = 'CARRIES_CODED' THEN 'LANDED'
         WHEN cur.result = 'CARRIES_UNCODED' THEN 'LANDED_UNCODED'
         WHEN cur.result = 'ABSENT' AND size(after) > 0 THEN 'NOT_LANDED_REVISED'
         WHEN cur.result = 'ABSENT' THEN 'NOT_LANDED_UNREVISED'
         ELSE 'UNKNOWN'
       END AS verdict;

// @query V5 upstream sources of a held product (1..3 hops) with each source's label of record and its first version carrying the fact
MATCH (p:Product {ndc: $product_ndc})-[:SOURCED_FROM*1..3]->(src:Product)
OPTIONAL MATCH (ss:LabelSet)-[:DESCRIBES]->(src)
WHERE ss.current_doc_id = src.listing_spl_id
OPTIONAL MATCH (ss)-[:HAS_VERSION]->(sv:LabelVersion)-[c:CHECKED]->(f:SafetyFact {id: $fact_id})
WHERE c.result IN ['CARRIES_CODED', 'CARRIES_UNCODED'] AND c.tier >= 1 AND c.disputed = false AND sv.published_d <= $as_of_d
WITH src, ss, sv ORDER BY sv.published_d ASC
WITH src, ss, collect(sv) AS carrying
RETURN src.ndc AS source_ndc, src.labeler_name AS source_labeler,
       coalesce(src.listing_expiration_d, 0) >= $as_of_d AS source_listing_active,
       ss.set_id AS source_set_id,
       carrying[0].version AS source_first_carry_version, carrying[0].published AS source_first_carry_published,
       carrying[0].published_d AS source_first_carry_d;

// @query V6 alternatives: other active products of the same molecule, dosage form and strength whose label of record carries the fact in a coded section
MATCH (p:Product {ndc: $product_ndc})
MATCH (alt:Product)<-[:DESCRIBES]-(s:LabelSet)-[:HAS_VERSION]->(v:LabelVersion)-[c:CHECKED]->(f:SafetyFact {id: $fact_id})
WHERE alt.ndc <> p.ndc AND alt.molecule_key = p.molecule_key AND alt.dosage_form = p.dosage_form
  AND alt.strength = p.strength AND s.current_doc_id = alt.listing_spl_id
  AND coalesce(alt.listing_expiration_d, 0) >= $as_of_d AND v.version = s.current_version
  AND c.result = 'CARRIES_CODED' AND c.tier >= 1 AND c.disputed = false
RETURN alt.ndc AS ndc, alt.labeler_name AS labeler, s.set_id AS set_id, v.published AS published
ORDER BY published DESC
LIMIT 8;

// ===========================================================================
// WHO MUST ACT (authority) - hub, read-only
// ===========================================================================

// @query W1 authority chain: every hop from the held product up through its sources to the application and reference drug, with current holders
MATCH path = (p:Product {ndc: $product_ndc})-[:SOURCED_FROM*0..3]->(q:Product)
OPTIONAL MATCH (ls:LabelSet)-[:DESCRIBES]->(q)
WHERE ls.current_doc_id = q.listing_spl_id
OPTIONAL MATCH (pub:Party)-[:PUBLISHES]->(ls)
OPTIONAL MATCH (q)-[:UNDER]->(app:Application)
OPTIONAL MATCH (holder:Party)-[h:HOLDS]->(app)
WHERE h.to_d IS NULL
OPTIONAL MATCH (app)-[:REFERENCES]->(rld:Application)
OPTIONAL MATCH (rh:Party)-[rhh:HOLDS]->(rld)
WHERE rhh.to_d IS NULL
RETURN length(path) AS hop, q.ndc AS product_ndc, q.labeler_name AS labeler,
       coalesce(q.listing_expiration_d, 0) >= $as_of_d AS listing_active, ls.set_id AS label_set, pub.name AS publisher,
       app.id AS application, app.marketing_status AS application_status, coalesce(app.reference_drug, false) AS application_is_rld,
       holder.name AS application_holder, rld.id AS rld, rld.marketing_status AS rld_status, rh.name AS rld_holder
ORDER BY hop ASC;

// @query W2 reference standard for a molecule and dosage form (who FDA lists as the standard when the reference drug is discontinued)
MATCH (a:Application)-[:CONTAINS]->(:Molecule {key: $molecule_key})
WHERE a.reference_standard = true AND $dosage_form IN a.dosage_forms
OPTIONAL MATCH (holder:Party)-[h:HOLDS]->(a)
WHERE h.to_d IS NULL
RETURN a.id AS application, a.kind AS kind, a.marketing_status AS marketing_status, holder.name AS holder;

// @query W3 open gaps across every active fact, optionally for one publishing labeler: labels of record whose current version lacks the fact
MATCH (f:SafetyFact {status: 'ACTIVE'})-[:ISSUED_ON]->(rld:Application)
MATCH (rld)<-[:SOURCED_FROM|UNDER|REFERENCES*1..5]-(p:Product)<-[:DESCRIBES]-(s:LabelSet)
WHERE s.current_doc_id = p.listing_spl_id AND coalesce(p.listing_expiration_d, 0) >= $as_of_d
WITH DISTINCT f, s
MATCH (pub:Party)-[:PUBLISHES]->(s)
WHERE $party_id IS NULL OR pub.id = $party_id
MATCH (s)-[:HAS_VERSION]->(v:LabelVersion)-[c:CHECKED]->(f)
WHERE v.version = s.current_version AND c.result = 'ABSENT' AND c.tier >= $min_tier AND c.disputed = false
RETURN f.id AS fact_id, pub.id AS party_id, pub.name AS publisher, s.set_id AS set_id, s.title AS title,
       v.version AS version, v.published AS published
ORDER BY fact_id, publisher, published;

// @query W4 upstream closure of a held product with FalkorDB algo.BFS (sources, applications, reference drugs, molecule)
MATCH (p:Product {ndc: $product_ndc})
CALL algo.BFS(p, 5, NULL) YIELD nodes
UNWIND nodes AS n
RETURN labels(n)[0] AS kind, coalesce(n.ndc, n.id, n.key) AS id;

// ===========================================================================
// FAN-OUT, COPY LAG, LATENCY, LOOP CLOSURE (Watcher) - hub
// ===========================================================================

// @query D1 fan-out of a fact: every label of record in scope (any number of sources and applications deep, bounded), with its current check
MATCH (f:SafetyFact {id: $fact_id})-[:ISSUED_ON]->(rld:Application)
MATCH (rld)<-[:SOURCED_FROM|UNDER|REFERENCES*1..5]-(p:Product)<-[:DESCRIBES]-(s:LabelSet)
WHERE s.current_doc_id = p.listing_spl_id AND coalesce(p.listing_expiration_d, 0) >= $as_of_d
WITH DISTINCT f, s
MATCH (s)-[:HAS_VERSION]->(v:LabelVersion)
WHERE v.version = s.current_version
OPTIONAL MATCH (v)-[c:CHECKED]->(f)
OPTIONAL MATCH (pub:Party)-[:PUBLISHES]->(s)
RETURN s.set_id AS set_id, s.title AS title, pub.name AS publisher, v.id AS version_id, v.version AS version,
       v.published AS published, v.archive_id AS archive_id, c.tier AS tier,
       CASE WHEN c IS NULL OR c.disputed = true OR c.tier < 1 OR (c.result = 'ABSENT' AND c.tier < $min_tier) THEN 'UNCHECKED' ELSE c.result END AS result
ORDER BY result ASC, publisher ASC;

// @query D2 downstream of a changed label set: products sourced (1..3 hops) from products this set describes, with their label of record
MATCH (s:LabelSet {set_id: $set_id})-[:DESCRIBES]->(src:Product)
MATCH (down:Product)-[:SOURCED_FROM*1..3]->(src)
OPTIONAL MATCH (ds:LabelSet)-[:DESCRIBES]->(down)
WHERE ds.current_doc_id = down.listing_spl_id
RETURN DISTINCT down.ndc AS ndc, down.labeler_name AS labeler, ds.set_id AS set_id;

// @query D3 copy lag: repackaged labels revised after their source label already carried the fact, yet lacking it
MATCH (f:SafetyFact {id: $fact_id})
MATCH (rs:LabelSet)-[:DESCRIBES]->(rp:Product)-[:SOURCED_FROM]->(sp:Product)<-[:DESCRIBES]-(ss:LabelSet)
WHERE rs.current_doc_id = rp.listing_spl_id AND ss.current_doc_id = sp.listing_spl_id
  AND coalesce(rp.listing_expiration_d, 0) >= $as_of_d
MATCH (ss)-[:HAS_VERSION]->(sv:LabelVersion)-[sc:CHECKED]->(f)
WHERE sc.result IN ['CARRIES_CODED', 'CARRIES_UNCODED'] AND sc.tier >= 1 AND sc.disputed = false
WITH f, rs, rp, sp, ss, min(sv.published_d) AS source_first_carry_d, min(sv.published) AS source_first_carry
MATCH (rs)-[:HAS_VERSION]->(rv:LabelVersion)-[rc:CHECKED]->(f)
WHERE rc.result = 'ABSENT' AND rc.tier >= $min_tier AND rc.disputed = false AND rv.published_d > source_first_carry_d
WITH rs, rp, sp, ss, source_first_carry, source_first_carry_d, collect(rv.published) AS revised_without_it,
     max(rv.published_d) AS last_revised_d
RETURN rs.set_id AS set_id, rp.ndc AS ndc, rp.labeler_name AS labeler, sp.ndc AS source_ndc, ss.set_id AS source_set_id,
       source_first_carry, revised_without_it, last_revised_d - source_first_carry_d AS max_lag_days
ORDER BY max_lag_days DESC;

// @query D4 landing latency per publisher: days from the fact to the first carrying version, for label sets that existed before the fact
MATCH (f:SafetyFact {id: $fact_id})
MATCH (pub:Party)-[:PUBLISHES]->(s:LabelSet)-[:HAS_VERSION]->(pre:LabelVersion)
WHERE pre.published_d < f.issued_d
WITH DISTINCT f, pub, s
MATCH (s)-[:HAS_VERSION]->(v:LabelVersion)-[c:CHECKED]->(f)
WHERE c.result IN ['CARRIES_CODED', 'CARRIES_UNCODED'] AND c.tier >= 1 AND c.disputed = false AND v.published_d >= f.issued_d
WITH pub, s, f, min(v.published_d) AS first_carry_d
WITH pub, s, first_carry_d - f.issued_d AS latency_days
RETURN pub.name AS publisher, count(s) AS label_sets, percentileDisc(latency_days, 0.5) AS median_latency_days,
       max(latency_days) AS max_latency_days
ORDER BY median_latency_days DESC;

// @query D5 record an observed landing (append-only loop-closure record; observed = 'live' or 'history')
MATCH (s:LabelSet {set_id: $set_id})-[:HAS_VERSION]->(v:LabelVersion {id: $version_id})
MATCH (f:SafetyFact {id: $fact_id})
MERGE (e:LandingEvent {id: $event_id})
ON CREATE SET e.kind = $kind, e.at = $now, e.published = v.published, e.latency_days = v.published_d - f.issued_d,
              e.observed = $observed
MERGE (e)-[:FOR_SET]->(s)
MERGE (e)-[:OF_FACT]->(f)
MERGE (e)-[:AT_VERSION]->(v)
RETURN e.id AS id, e.latency_days AS latency_days;

// @query D6 landing events for a fact (the loop-closure ledger), newest first
MATCH (e:LandingEvent)-[:OF_FACT]->(f:SafetyFact {id: $fact_id})
MATCH (e)-[:FOR_SET]->(s:LabelSet)
OPTIONAL MATCH (pub:Party)-[:PUBLISHES]->(s)
RETURN e.id AS id, e.kind AS kind, s.set_id AS set_id, pub.name AS publisher, e.published AS published,
       e.latency_days AS latency_days, e.observed AS observed
ORDER BY published DESC;

// ===========================================================================
// LABEL HISTORY - hub
// ===========================================================================

// @query L1 version timeline of one SPL set with every check on every version
MATCH (s:LabelSet {set_id: $set_id})-[:HAS_VERSION]->(v:LabelVersion)
OPTIONAL MATCH (v)-[c:CHECKED]->(f:SafetyFact)
RETURN v.version AS version, v.id AS version_id, v.published AS published, v.doc_id AS doc_id, v.archive_id AS archive_id,
       collect(CASE WHEN f IS NULL THEN null ELSE {fact_id: f.id, result: c.result, tier: c.tier, method: c.method, disputed: c.disputed} END) AS checks
ORDER BY version ASC;

// @query L2 watcher state: last known version and document id per watched set
MATCH (s:LabelSet)
WHERE s.set_id IN $set_ids
RETURN s.set_id AS set_id, s.current_version AS current_version, s.current_doc_id AS current_doc_id,
       s.current_published AS current_published;

// @query L3 label sets in scope of active facts that the Watcher must poll (capped, rotated by the caller)
MATCH (f:SafetyFact {status: 'ACTIVE'})-[:ISSUED_ON]->(rld:Application)
MATCH (rld)<-[:SOURCED_FROM|UNDER|REFERENCES*1..5]-(p:Product)<-[:DESCRIBES]-(s:LabelSet)
WHERE s.label_of_record = true
RETURN DISTINCT s.set_id AS set_id
ORDER BY set_id ASC
LIMIT $limit;

// ===========================================================================
// COMPOUNDING (Publisher) - hub
// ===========================================================================

// @query P1 an organisation's pharmacist confirms a check; agreement raises the tier (2 at one organisation, 3 at two), disagreement marks it disputed
MATCH (v:LabelVersion {id: $version_id})-[c:CHECKED]->(f:SafetyFact {id: $fact_id})
WITH c, coalesce(c.confirmers, []) AS cs0, c.result = $result AS agrees
WITH c, agrees, CASE WHEN $org_hash IN cs0 THEN cs0 ELSE cs0 + [$org_hash] END AS cs
SET c.confirmers = CASE WHEN agrees THEN cs ELSE c.confirmers END,
    c.confirmations = CASE WHEN agrees THEN size(cs) ELSE c.confirmations END,
    c.tier = CASE WHEN NOT agrees THEN c.tier WHEN size(cs) >= 2 THEN 3 WHEN c.tier < 2 THEN 2 ELSE c.tier END,
    c.disputed = CASE WHEN agrees THEN c.disputed ELSE true END,
    c.dispute_result = CASE WHEN agrees THEN c.dispute_result ELSE $result END
RETURN c.result AS result, c.tier AS tier, c.confirmations AS confirmations, c.disputed AS disputed;

// @query P2 an organisation verifies a safety fact and its phrase key; the first verification activates it
MATCH (f:SafetyFact {id: $fact_id})
WITH f, coalesce(f.verifiers, []) AS vs0
WITH f, CASE WHEN $org_hash IN vs0 THEN vs0 ELSE vs0 + [$org_hash] END AS vs
SET f.verifiers = vs, f.verified_at = $now,
    f.status = CASE WHEN f.status = 'UNVERIFIED' THEN 'ACTIVE' ELSE f.status END
RETURN f.id AS fact_id, f.status AS status, size(vs) AS verifiers;

// @query P3 resolve a dispute (admin): set the agreed result and tier, clear the dispute
MATCH (v:LabelVersion {id: $version_id})-[c:CHECKED]->(f:SafetyFact {id: $fact_id})
SET c.result = $result, c.tier = $tier, c.method = 'human', c.disputed = false, c.resolved_at = $now
RETURN c.result AS result, c.tier AS tier;

// ===========================================================================
// GRAPH ALGORITHMS AS AGENT TOOLS - hub (read-only)
// ===========================================================================

// @query R1 supply families: connected components over source and application edges (algo.WCC), with carrying and lacking counts for one fact
CALL algo.WCC({nodeLabels: ['Product', 'Application'], relationshipTypes: ['SOURCED_FROM', 'UNDER']})
YIELD node, componentId
WITH componentId, node
WHERE 'Product' IN labels(node)
OPTIONAL MATCH (s:LabelSet)-[:DESCRIBES]->(node)
WHERE s.current_doc_id = node.listing_spl_id AND coalesce(node.listing_expiration_d, 0) >= $as_of_d
OPTIONAL MATCH (s)-[:HAS_VERSION]->(v:LabelVersion)-[c:CHECKED]->(f:SafetyFact {id: $fact_id})
WHERE v.version = s.current_version
WITH componentId, node, c
WITH componentId, collect(DISTINCT node.ndc) AS products,
     sum(CASE WHEN c.result = 'ABSENT' THEN 1 ELSE 0 END) AS lacking,
     sum(CASE WHEN c.result IN ['CARRIES_CODED', 'CARRIES_UNCODED'] THEN 1 ELSE 0 END) AS carrying
WHERE size(products) > 1
RETURN componentId, size(products) AS product_count, carrying, lacking, products[0..20] AS sample
ORDER BY lacking DESC, product_count DESC
LIMIT 50;

// @query A1 source hubs: products copied by the most repackagers (algo.pageRank over SOURCED_FROM); a fix here reaches the most labels
CALL algo.pageRank('Product', 'SOURCED_FROM') YIELD node, score
WITH node, score
OPTIONAL MATCH (down:Product)-[:SOURCED_FROM]->(node)
WITH node, score, count(down) AS direct_repackagers
WHERE direct_repackagers > 0
RETURN node.ndc AS source_ndc, node.labeler_name AS labeler, score, direct_repackagers
ORDER BY score DESC
LIMIT 20;

// @query A2 chokepoints: products and applications on the most label-to-reference paths (algo.betweenness; samplingSize above the node count makes it exact and repeatable at our scale)
CALL algo.betweenness({nodeLabels: ['Product', 'Application'], relationshipTypes: ['SOURCED_FROM', 'UNDER', 'REFERENCES'], samplingSize: 2000})
YIELD node, score
WITH node, score
WHERE score > 0
RETURN labels(node)[0] AS kind, coalesce(node.ndc, node.id) AS id, coalesce(node.labeler_name, node.sponsor) AS party, score
ORDER BY score DESC
LIMIT 20;

// @query A3 label families: community detection over source and application edges (algo.labelPropagation)
CALL algo.labelPropagation({nodeLabels: ['Product', 'Application'], relationshipTypes: ['SOURCED_FROM', 'UNDER'], maxIterations: 10})
YIELD node, communityId
WITH communityId, collect(coalesce(node.ndc, node.id)) AS members
WHERE size(members) > 1
RETURN communityId, size(members) AS size, members[0..10] AS sample
ORDER BY size DESC
LIMIT 50;

// ===========================================================================
// TENANT GRAPHS (Prover, Watcher, Notifier, task handoffs)
// ===========================================================================

// @query T1 write a ruling for a stock item and the basis it rests on (append-only; never update a ruling)
MATCH (si:StockItem {id: $stock_item_id})
CREATE (r:Ruling {id: $ruling_id, verdict: $verdict, fact_id: $fact_id, set_id: $set_id, strict: $strict,
                  created_at: $now, as_of_d: $as_of_d, explanation: $explanation, who_must_act: $who_must_act})
CREATE (r)-[:FOR]->(si)
WITH r
UNWIND $basis AS b
CREATE (x:Basis {id: b.id, kind: b.kind, fact_id: b.fact_id, set_id: b.set_id, version_id: b.version_id,
                 doc_id: b.doc_id, published: b.published, section_code: b.section_code,
                 check_result: b.check_result, check_tier: b.check_tier, path: b.path})
CREATE (r)-[:RESTS_ON]->(x)
RETURN r.id AS ruling_id, count(x) AS basis;

// @query T2 link a new ruling to the one it replaces
MATCH (new:Ruling {id: $new_id}), (old:Ruling {id: $old_id})
CREATE (new)-[:SUPERSEDES]->(old)
RETURN new.id AS new_id, old.id AS old_id;

// @query T3 active rulings that rest on any changed label set, with the pharmacist responsible for the site
MATCH (r:Ruling)-[:RESTS_ON]->(b:Basis)
WHERE b.set_id IN $set_ids
OPTIONAL MATCH (newer:Ruling)-[:SUPERSEDES]->(r)
WITH r, b, newer
WHERE newer IS NULL
MATCH (r)-[:FOR]->(si:StockItem)-[:AT]->(site:Site)<-[rf:RESPONSIBLE_FOR]-(owner:Person)
WHERE rf.until IS NULL
RETURN r.id AS ruling_id, si.id AS stock_item_id, si.ndc AS ndc, owner.id AS owner_id,
       collect(DISTINCT b.set_id) AS affected_sets;

// @query T4 reopen a ruling and hand a review task to its owner
MATCH (r:Ruling {id: $ruling_id}), (p:Person {id: $owner_id})
CREATE (e:Event {id: $event_id, kind: 'REOPENED', at: $now, reason: $reason})
CREATE (e)-[:ON]->(r)
CREATE (t:Task {id: $task_id, kind: 'REVIEW_RULING', state: 'OPEN', created_by_agent: $agent, created_at: $now})
CREATE (t)-[:ABOUT]->(r)
CREATE (t)-[:ASSIGNED_TO]->(p)
WITH t
OPTIONAL MATCH (pb:Playbook {kind: 'REVIEW_RULING'})
FOREACH (_ IN CASE WHEN pb IS NULL THEN [] ELSE [1] END | CREATE (t)-[:FOLLOWS]->(pb))
RETURN t.id AS task_id;

// @query T5 claim a task with a 2-minute lease (stale leases return to the pool)
MATCH (t:Task {id: $task_id})
WHERE t.state = 'OPEN' OR (t.state = 'CLAIMED' AND t.lease_until < $now)
SET t.state = 'CLAIMED', t.lease_until = $now + 120000, t.claimed_by = $agent
RETURN t.id AS claimed;

// @query T6 latest ruling per stock item (the current-knowledge view)
MATCH (site:Site)<-[:AT]-(si:StockItem)<-[:FOR]-(r:Ruling)
OPTIONAL MATCH (newer:Ruling)-[:SUPERSEDES]->(r)
WITH site, si, r, newer
WHERE newer IS NULL
OPTIONAL MATCH (site)<-[rf:RESPONSIBLE_FOR]-(owner:Person)
WHERE rf.until IS NULL
RETURN site.id AS site_id, site.name AS site, si.id AS stock_item_id, si.ndc AS ndc, si.display_name AS display_name,
       r.fact_id AS fact_id, r.verdict AS verdict, r.created_at AS decided_at, owner.name AS owner, r.id AS ruling_id
ORDER BY site ASC, ndc ASC;

// @query T7 ruling trace: what the ruling rests on (label version, section, check tier, path) and who signed what
MATCH (r:Ruling {id: $ruling_id})-[:RESTS_ON]->(b:Basis)
OPTIONAL MATCH (e:Event)-[:ON]->(r)
OPTIONAL MATCH (signer:Person)-[:SIGNED]->(e)
RETURN r.id AS ruling_id, r.verdict AS verdict, r.fact_id AS fact_id, r.created_at AS created_at, r.who_must_act AS who_must_act,
       collect(DISTINCT {kind: b.kind, set_id: b.set_id, version_id: b.version_id, doc_id: b.doc_id, published: b.published,
                         section_code: b.section_code, check_result: b.check_result, check_tier: b.check_tier, path: b.path}) AS basis,
       collect(DISTINCT CASE WHEN e IS NULL THEN null ELSE {kind: e.kind, at: e.at, reason: e.reason, by: signer.name} END) AS events;

// @query T8 holdings: every stock item with its site (seeds rulings and the watch list)
MATCH (si:StockItem)-[:AT]->(site:Site)
RETURN si.id AS stock_item_id, si.ndc AS ndc, si.display_name AS display_name, site.id AS site_id
ORDER BY stock_item_id ASC;

// @query T9 active rulings that rest on a changed or retired safety fact
MATCH (r:Ruling)-[:RESTS_ON]->(b:Basis)
WHERE b.fact_id IN $fact_ids
OPTIONAL MATCH (newer:Ruling)-[:SUPERSEDES]->(r)
WITH r, newer
WHERE newer IS NULL
MATCH (r)-[:FOR]->(si:StockItem)-[:AT]->(site:Site)<-[rf:RESPONSIBLE_FOR]-(owner:Person)
WHERE rf.until IS NULL
RETURN DISTINCT r.id AS ruling_id, si.id AS stock_item_id, owner.id AS owner_id;

// @query T10 handoff: the Prover proposes a verdict on a review task and hands an approval task to the owner
MATCH (prev:Task {id: $prev_task_id}), (p:Person {id: $owner_id}), (r:Ruling {id: $ruling_id})
SET prev.state = 'AWAITING_APPROVAL', prev.proposed_verdict = $proposed_verdict, prev.proposed_ruling_json = $proposed_ruling_json
CREATE (t:Task {id: $task_id, kind: 'APPROVE_RULING', state: 'OPEN', created_by_agent: 'prover', created_at: $now})
CREATE (t)-[:HANDED_OFF_FROM]->(prev)
CREATE (t)-[:ABOUT]->(r)
CREATE (t)-[:ASSIGNED_TO]->(p)
WITH t
OPTIONAL MATCH (pb:Playbook {kind: 'APPROVE_RULING'})
FOREACH (_ IN CASE WHEN pb IS NULL THEN [] ELSE [1] END | CREATE (t)-[:FOLLOWS]->(pb))
RETURN t.id AS task_id;

// @query T11 persistent conversation history: one turn per MCP call or web check with a tenant
MERGE (c:Conversation {id: $conversation_id})
ON CREATE SET c.channel = $channel, c.started_at = $now
CREATE (t:Turn {id: $turn_id, tool: $tool, args_json: $args_json, verdict: $verdict, at: $now})
CREATE (c)-[:HAS_TURN]->(t)
WITH t
OPTIONAL MATCH (r:Ruling {id: $ruling_id})
FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | CREATE (t)-[:PRODUCED]->(r))
RETURN t.id AS turn_id;

// @query T12 decision trace: a formulary decision -> the ruling -> label version and section -> who decided and who signed
MATCH (d:Decision {id: $decision_id})-[:BASED_ON]->(r:Ruling)-[:RESTS_ON]->(b:Basis)
OPTIONAL MATCH (who:Person)-[:DECIDED]->(d)
OPTIONAL MATCH (d)-[:ON]->(fe:FormularyEntry)
OPTIONAL MATCH (e:Event)-[:ON]->(r)
OPTIONAL MATCH (signer:Person)-[:SIGNED]->(e)
RETURN d.id AS decision_id, d.kind AS kind, d.value AS value, d.at AS decided_at, who.name AS decided_by,
       fe.id AS formulary_entry, r.id AS ruling_id, r.verdict AS verdict,
       collect(DISTINCT {kind: b.kind, set_id: b.set_id, version_id: b.version_id, published: b.published,
                         section_code: b.section_code, check_result: b.check_result, check_tier: b.check_tier}) AS basis,
       collect(DISTINCT CASE WHEN e IS NULL THEN null ELSE {kind: e.kind, at: e.at, by: signer.name} END) AS events;

// @query T13 a person signs an event on a ruling (APPROVED, REJECTED, CONFIRMED_CHECK, NOTICE_APPROVED)
MATCH (r:Ruling {id: $ruling_id}), (p:Person {id: $person_id})
CREATE (e:Event {id: $event_id, kind: $kind, at: $now, reason: $reason})
CREATE (e)-[:ON]->(r)
CREATE (p)-[:SIGNED]->(e)
RETURN e.id AS event_id;

// @query T14 record a formulary decision based on a ruling (Track 3: decisions traced to label version and section)
MATCH (r:Ruling {id: $ruling_id}), (p:Person {id: $person_id}), (fe:FormularyEntry {id: $entry_id})
CREATE (d:Decision {id: $decision_id, kind: $kind, value: $value, at: $now, note: $note})
CREATE (d)-[:BASED_ON]->(r)
CREATE (d)-[:ON]->(fe)
CREATE (p)-[:DECIDED]->(d)
SET fe.status = CASE WHEN $kind = 'FORMULARY_STATUS' THEN $value ELSE fe.status END
RETURN d.id AS decision_id, fe.status AS entry_status;

// @query T15 who owns which formulary decision: current owner and the latest decision per formulary entry
MATCH (fe:FormularyEntry)<-[o:OWNS]-(p:Person)
WHERE o.until IS NULL
OPTIONAL MATCH (d:Decision)-[:ON]->(fe)
WITH fe, p, d ORDER BY d.at DESC
WITH fe, p, collect(d) AS ds
RETURN fe.id AS entry_id, fe.molecule_key AS molecule, fe.status AS status, p.name AS owner,
       ds[0].id AS last_decision_id, ds[0].kind AS last_decision, ds[0].at AS last_decided_at
ORDER BY entry_id ASC;

// @query T16 open and in-flight tasks with assignee, playbook steps and handoff source
MATCH (t:Task)-[:ASSIGNED_TO]->(p:Person)
WHERE $state IS NULL OR t.state = $state
OPTIONAL MATCH (t)-[:ABOUT]->(r:Ruling)
OPTIONAL MATCH (t)-[:FOLLOWS]->(pb:Playbook)
OPTIONAL MATCH (t)-[:HANDED_OFF_FROM]->(prev:Task)
RETURN t.id AS task_id, t.kind AS kind, t.state AS state, t.created_at AS created_at, t.created_by_agent AS created_by_agent,
       t.proposed_verdict AS proposed_verdict, p.id AS assignee_id, p.name AS assignee, r.id AS ruling_id,
       pb.steps AS playbook_steps, prev.id AS handed_off_from
ORDER BY created_at DESC;

// @query T17 complete a task (DONE) after approve or reject
MATCH (t:Task {id: $task_id})
SET t.state = 'DONE', t.done_at = $now, t.outcome = $outcome
RETURN t.id AS task_id, t.state AS state;

// @query T18 store a draft notice for an approval task (never sent by the system)
MATCH (t:Task {id: $task_id})
CREATE (d:Draft {id: $draft_id, kind: $kind, to_party: $to_party, title: $title, body: $body, created_at: $now, ready_to_copy: false})
CREATE (d)-[:FOR_TASK]->(t)
RETURN d.id AS draft_id;

// @query T19 create a task that is not a reopen (APPROVE_NOTICE, CONFIRM_CHECK, PHARMACIST_REVIEW)
MATCH (p:Person {id: $assignee_id})
CREATE (t:Task {id: $task_id, kind: $kind, state: 'OPEN', created_by_agent: $agent, created_at: $now, payload_json: $payload_json})
CREATE (t)-[:ASSIGNED_TO]->(p)
WITH t
OPTIONAL MATCH (r:Ruling {id: $ruling_id})
FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | CREATE (t)-[:ABOUT]->(r))
WITH t
OPTIONAL MATCH (pb:Playbook {kind: $kind})
FOREACH (_ IN CASE WHEN pb IS NULL THEN [] ELSE [1] END | CREATE (t)-[:FOLLOWS]->(pb))
RETURN t.id AS task_id;

// @query T21 mark a draft ready to copy after approval (the only update a draft ever gets)
MATCH (d:Draft)-[:FOR_TASK]->(t:Task {id: $task_id})
SET d.ready_to_copy = true, d.approved_at = $now
RETURN d.id AS draft_id, d.ready_to_copy AS ready_to_copy;

// @query T20 events newest first (timeline)
MATCH (e:Event)-[:ON]->(r:Ruling)
OPTIONAL MATCH (p:Person)-[:SIGNED]->(e)
RETURN e.id AS event_id, e.kind AS kind, e.at AS at, e.reason AS reason, r.id AS ruling_id, p.name AS signed_by
ORDER BY at DESC
LIMIT $limit;

// ===========================================================================
// ASK THE ORGANISATION (add-on): eight read-only templates over a tenant graph. The LLM only picks one.
// ===========================================================================

// @query K1 who is responsible for a site
MATCH (site:Site {id: $site_id})<-[rf:RESPONSIBLE_FOR]-(p:Person)
WHERE rf.until IS NULL
RETURN site.name AS site, p.name AS person, p.role AS role;

// @query K2 which stock items rest on a given SPL set
MATCH (r:Ruling)-[:RESTS_ON]->(b:Basis {set_id: $set_id})
MATCH (r)-[:FOR]->(si:StockItem)
RETURN DISTINCT si.id AS stock_item_id, si.ndc AS ndc, r.id AS ruling_id, r.verdict AS verdict;

// @query K3 which rulings were reopened since a time (epoch ms)
MATCH (e:Event {kind: 'REOPENED'})-[:ON]->(r:Ruling)
WHERE e.at >= $since
RETURN r.id AS ruling_id, r.verdict AS verdict, e.at AS reopened_at, e.reason AS reason
ORDER BY reopened_at DESC;

// @query K4 who decided a formulary entry and when
MATCH (p:Person)-[:DECIDED]->(d:Decision)-[:ON]->(fe:FormularyEntry {id: $entry_id})
RETURN p.name AS decided_by, d.kind AS kind, d.value AS value, d.at AS decided_at
ORDER BY decided_at DESC;

// @query K5 which stock items currently have a not-landed verdict
MATCH (si:StockItem)<-[:FOR]-(r:Ruling)
WHERE r.verdict IN ['NOT_LANDED_REVISED', 'NOT_LANDED_UNREVISED']
OPTIONAL MATCH (newer:Ruling)-[:SUPERSEDES]->(r)
WITH si, r, newer
WHERE newer IS NULL
RETURN si.id AS stock_item_id, si.ndc AS ndc, r.verdict AS verdict, r.fact_id AS fact_id;

// @query K6 open tasks for one person
MATCH (t:Task)-[:ASSIGNED_TO]->(p:Person {id: $person_id})
WHERE t.state <> 'DONE'
RETURN t.id AS task_id, t.kind AS kind, t.state AS state, t.created_at AS created_at
ORDER BY created_at DESC;

// @query K7 decisions traced to one label version
MATCH (d:Decision)-[:BASED_ON]->(r:Ruling)-[:RESTS_ON]->(b:Basis {version_id: $version_id})
OPTIONAL MATCH (p:Person)-[:DECIDED]->(d)
RETURN d.id AS decision_id, d.kind AS kind, d.value AS value, p.name AS decided_by, r.verdict AS verdict;

// @query K8 the latest conversation turns for one tool
MATCH (c:Conversation)-[:HAS_TURN]->(t:Turn)
WHERE t.tool = $tool
RETURN c.id AS conversation_id, t.args_json AS args_json, t.verdict AS verdict, t.at AS at
ORDER BY at DESC
LIMIT 20;

// ===========================================================================
// REGISTRY AND SANDBOXES - hub (names only; no tenant usage data ever enters the hub)
// ===========================================================================

// @query X1 register a fixed tenant graph name
MERGE (t:TenantRegistry {name: $name})
RETURN t.name AS name;

// @query X2 record a sandbox (no token stored)
MERGE (s:Sandbox {name: $name})
SET s.expires_at = $expires_at, s.template = $template
RETURN s.name AS name;

// @query X3 expired sandboxes to delete
MATCH (s:Sandbox)
WHERE s.expires_at < $now
RETURN s.name AS name;

// @query X4 forget a deleted sandbox
MATCH (s:Sandbox {name: $name})
DELETE s
RETURN count(*) AS deleted;

// @query X5 record a fan-out run (audit)
CREATE (r:FanOut {id: $id, at: $now, trigger: $trigger, fact_id: $fact_id, set_id: $set_id, summary_json: $summary_json})
RETURN r.id AS id;

// @query X6 replay only (graph name must start with hubr_): hide one set's versions published after a date and point the set at the latest remaining version
MATCH (s:LabelSet {set_id: $set_id})-[:HAS_VERSION]->(v:LabelVersion)
WHERE v.published_d > $from_d
WITH s, collect(v) AS hidden
FOREACH (h IN hidden | DETACH DELETE h)
WITH s, size(hidden) AS hidden_count
MATCH (s)-[:HAS_VERSION]->(r:LabelVersion)
WITH s, hidden_count, r ORDER BY r.version DESC
WITH s, hidden_count, collect(r) AS remaining
SET s.current_version = remaining[0].version, s.current_doc_id = remaining[0].doc_id,
    s.current_published = remaining[0].published, s.current_published_d = remaining[0].published_d
RETURN s.set_id AS set_id, hidden_count, s.current_version AS current_version;
