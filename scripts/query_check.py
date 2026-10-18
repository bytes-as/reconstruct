# Spec-time query check used on 18 Oct 2026 to test every block of docs/queries.cypher with redis-cli inside a FalkorDB container.
# usage: docker run -d --rm --name lf-test falkordb/falkordb:latest; python3 -I scripts/query_check.py . lf-test all
# It loads data/fixtures/hub_montelukast.json through the I-queries, loads both demo tenants, then runs every named query.
# The production test suite (G011, golden tests) replaces it; keep it as a quick independent check.
"""Load the Landfall fixture into FalkorDB through the I-queries and run every named query with test params.

usage: python3 -I qtest.py <landfall_dir> <container> [load|test|all] [only_names...]
"""
import json, os, re, subprocess, sys, time

root, container = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "all"
only = set(sys.argv[4:])
HUB, TEN_A, TEN_B = "hub_test", "tenant_bayview", "tenant_northgate"


def parse(path):
    qs, schema, cur, name, kind = {}, {"hub": [], "tenant": []}, [], None, None
    def flush():
        if name and kind == "query":
            q = " ".join(l.strip() for l in cur if l.strip()).rstrip(";")
            qs[name] = q
    for line in open(path):
        s = line.rstrip("\n")
        m = re.match(r"// @query (\w+)", s)
        sm = re.match(r"// @schema (\w+)", s)
        if m or sm or s.startswith("// ====="):
            flush()
            cur, name, kind = [], None, None
            if m:
                name, kind = m.group(1), "query"
            elif sm:
                name, kind = sm.group(1), "schema"
            continue
        if s.startswith("//"):
            continue
        if kind == "schema" and s.strip():
            schema[name].append(s.strip().rstrip(";"))
        elif kind == "query":
            cur.append(s)
    flush()
    return qs, schema


def lit(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if isinstance(v, list):
        return "[" + ", ".join(lit(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {lit(x)}" for k, x in v.items()) + "}"
    raise TypeError(type(v))


def cmdline(graph, q, params):
    pre = "CYPHER " + " ".join(f"{k}={lit(v)}" for k, v in params.items()) + " " if params else ""
    full = pre + q
    return f'GRAPH.QUERY {graph} "' + full.replace("\\", "\\\\").replace('"', '\\"') + '"'


def pipe(lines):
    p = subprocess.run(["docker", "exec", "-i", container, "redis-cli"], input="\n".join(lines) + "\n",
                       capture_output=True, text=True)
    return p.stdout


def run(graph, q, params):
    line = cmdline(graph, q, params)
    p = subprocess.run(["docker", "exec", "-i", container, "redis-cli", "--json"], input=line + "\n",
                       capture_output=True, text=True)
    out = p.stdout.strip()
    try:
        return json.loads(out)
    except Exception:
        return {"error": out[:500]}


Q, SCHEMA = parse(os.path.join(root, "docs/queries.cypher"))
FX = json.load(open(os.path.join(root, "data/fixtures/hub_montelukast.json")))
NOW = 1792200000000
TODAY_D = FX["as_of_d"]

if mode in ("load", "all"):
    pipe([f"GRAPH.DELETE {g}" for g in (HUB, TEN_A, TEN_B)])
    lines = [f'GRAPH.QUERY {HUB} "{s}"' for s in SCHEMA["hub"]]
    for m in FX["molecules"]:
        lines.append(cmdline(HUB, Q["I1"], m))
    for a in FX["applications"]:
        lines.append(cmdline(HUB, Q["I2"], {**a, "now": NOW}))
    for h in FX["holders"]:
        lines.append(cmdline(HUB, Q["I3"], {**h, "today_d": TODAY_D}))
    for s in FX["label_sets"]:
        lines.append(cmdline(HUB, Q["I4"], {**s, "now": NOW}))
    for v in sorted(FX["versions"], key=lambda v: (v["set_id"], v["version"])):
        lines.append(cmdline(HUB, Q["I5"], {**v, "now": NOW}))
    for p in FX["products"]:
        lines.append(cmdline(HUB, Q["I6"], {**p, "now": NOW}))
    for d in FX["describes"]:
        lines.append(cmdline(HUB, Q["I7"], d))
    for k in FX["packages"]:
        lines.append(cmdline(HUB, Q["I8"], k))
    for e in FX["sourced_from"]:
        lines.append(cmdline(HUB, Q["I9"], {**e, "now": NOW}))
    for f in FX["facts"]:
        lines.append(cmdline(HUB, Q["I11"], f))
    lines.append(cmdline(HUB, Q["I12"], {"molecule_key": "montelukast"}))
    for c in FX["checks"]:
        lines.append(cmdline(HUB, Q["I10"], {**c, "now": NOW}))
    lines.append(cmdline(HUB, Q["I13"], {"molecule_key": "montelukast", "today_d": TODAY_D}))
    t0 = time.time()
    out = pipe(lines)
    errs = [l for l in out.splitlines() if "error" in l.lower() or "ERR" in l]
    print(f"loaded {len(lines)} commands in {time.time()-t0:.1f}s, error lines: {len(errs)}")
    for e in errs[:10]:
        print("  ", e)
    # tenants
    for g, f in ((TEN_A, "data/demo_tenants/bayview.cypher"), (TEN_B, "data/demo_tenants/northgate.cypher")):
        path = os.path.join(root, f)
        if not os.path.exists(path):
            print("missing", f); continue
        stmts = [s.strip() for s in re.split(r";\s*\n", "\n".join(l for l in open(path) if not l.strip().startswith("//"))) if s.strip()]
        tl = [f'GRAPH.QUERY {g} "{s}"' for s in SCHEMA["tenant"]]
        tl += [f'GRAPH.QUERY {g} "' + " ".join(st.split()).rstrip(";").replace('"', '\\"') + '"' for st in stmts]
        out = pipe(tl)
        errs = [l for l in out.splitlines() if "error" in l.lower()]
        print(f"tenant {g}: {len(tl)} statements, error lines {len(errs)}", errs[:5])
    print("counts", run(HUB, "MATCH (n) RETURN labels(n)[0] AS l, count(*) AS c ORDER BY c DESC", {}))

AS = TODAY_D
F = "montelukast_bw_2020"
NUC_SET = "549f1d1a-81f5-29f5-e054-00144ff8d46c"
ACC_SET = "6eea668f-a2fa-447f-b2d5-4c754d13d9fa"
TESTS = {
  # name: (graph, params)
  "V1": (HUB, {"ndc": "68071-3355-9", "as_of_d": AS}),
  "V2": (HUB, {"fact_id": F, "product_ndc": "68071-3355"}),
  "V3": (HUB, {"molecule_key": "montelukast", "include_unverified": False}),
  "V4": (HUB, {"fact_id": F, "set_id": NUC_SET, "as_of_d": AS, "min_tier": 1, "grace_days": 30}),
  "V5": (HUB, {"product_ndc": "68071-3355", "fact_id": F, "as_of_d": AS}),
  "V6": (HUB, {"product_ndc": "68071-3355", "fact_id": F, "as_of_d": AS}),
  "W1": (HUB, {"product_ndc": "63187-626", "as_of_d": AS}),
  "W2": (HUB, {"molecule_key": "montelukast", "dosage_form": "GRANULE"}),
  "W3": (HUB, {"party_id": None, "as_of_d": AS, "min_tier": 1}),
  "W4": (HUB, {"product_ndc": "68071-3355"}),
  "D1": (HUB, {"fact_id": F, "as_of_d": AS, "min_tier": 1}),
  "D2": (HUB, {"set_id": ACC_SET}),
  "D3": (HUB, {"fact_id": F, "as_of_d": AS, "min_tier": 1}),
  "D4": (HUB, {"fact_id": F}),
  "L1": (HUB, {"set_id": NUC_SET}),
  "L2": (HUB, {"set_ids": [NUC_SET, ACC_SET]}),
  "L3": (HUB, {"limit": 5}),
  "R1": (HUB, {"fact_id": F, "as_of_d": AS}),
  "A1": (HUB, {}), "A2": (HUB, {}), "A3": (HUB, {}),
  "X1": (HUB, {"name": "tenant_bayview"}),
  "X2": (HUB, {"name": "sbx_0a1b2c3d", "expires_at": NOW + 7200000, "template": "bayview"}),
  "X3": (HUB, {"now": NOW + 9000000}),
  "X4": (HUB, {"name": "sbx_0a1b2c3d"}),
  "X5": (HUB, {"id": "fan_test", "now": NOW, "trigger": "test", "fact_id": F, "set_id": None, "summary_json": "{}"}),
}

def show(name, res, maxrows=8):
    if isinstance(res, dict):
        print(f"[{name}] ERROR {res['error']}"); return False
    if len(res) == 1 or (isinstance(res[0], str)):
        print(f"[{name}] OK (no result set) {res}"); return True
    hdr, rows = res[0], res[1]
    print(f"[{name}] OK rows={len(rows)} cols={hdr}")
    for r in rows[:maxrows]:
        print("     ", json.dumps(r)[:330])
    return True

if mode in ("test", "all"):
    bad = []
    for name in TESTS:
        if only and name not in only:
            continue
        g, p = TESTS[name]
        if not show(name, run(g, Q[name], p)):
            bad.append(name)
    print("FAILED:", bad)

NV = NUC_SET + "#v5"
BASIS = [{"id": "bas_1", "kind": "TARGET_VERSION", "fact_id": F, "set_id": NUC_SET, "version_id": NV,
          "doc_id": "1ce908ef-4d89-b74f-e063-6394a90a80f0", "published": "2024-07-11", "section_code": "34066-1",
          "check_result": "ABSENT", "check_tier": 1, "path": ["68071-3355", "ANDA202717", "NDA020829"]},
         {"id": "bas_2", "kind": "SOURCE_VERSION", "fact_id": F, "set_id": ACC_SET, "version_id": ACC_SET + "#v14",
          "doc_id": None, "published": "2021-05-21", "section_code": "34066-1", "check_result": "CARRIES_CODED",
          "check_tier": 1, "path": ["68071-3355", "16729-119"]}]
TT = [
  ("T8", TEN_A, {}),
  ("T1", TEN_A, {"stock_item_id": "bay_si_1", "ruling_id": "rul_a", "verdict": "NOT_LANDED_REVISED", "fact_id": F, "set_id": NUC_SET,
                 "strict": False, "now": NOW, "as_of_d": AS, "explanation": "t", "who_must_act": "NuCare", "basis": BASIS}),
  ("T1", TEN_A, {"stock_item_id": "bay_si_1", "ruling_id": "rul_b", "verdict": "NOT_LANDED_REVISED", "fact_id": F, "set_id": NUC_SET,
                 "strict": True, "now": NOW + 1, "as_of_d": AS, "explanation": "t2", "who_must_act": "NuCare", "basis": [dict(BASIS[0], id="bas_3")]}),
  ("T2", TEN_A, {"new_id": "rul_b", "old_id": "rul_a"}),
  ("T3", TEN_A, {"set_ids": [NUC_SET]}),
  ("T4", TEN_A, {"ruling_id": "rul_b", "owner_id": "bay_ruth", "event_id": "evt_1", "task_id": "task_1", "now": NOW + 2,
                 "reason": "new SPL version", "agent": "watcher"}),
  ("T5", TEN_A, {"task_id": "task_1", "now": NOW + 3, "agent": "prover"}),
  ("T10", TEN_A, {"prev_task_id": "task_1", "owner_id": "bay_ruth", "ruling_id": "rul_b", "proposed_verdict": "LANDED",
                  "proposed_ruling_json": "{}", "task_id": "task_2", "now": NOW + 4}),
  ("T13", TEN_A, {"ruling_id": "rul_b", "person_id": "bay_ruth", "event_id": "evt_2", "kind": "APPROVED", "now": NOW + 5, "reason": "ok"}),
  ("T14", TEN_A, {"ruling_id": "rul_b", "person_id": "bay_aisha", "entry_id": "bay_fe_montelukast_10", "decision_id": "dec_1",
                  "kind": "FORMULARY_STATUS", "value": "HOLD", "now": NOW + 6, "note": "prefer a supplier whose label carries the coded warning"}),
  ("T6", TEN_A, {}),
  ("T7", TEN_A, {"ruling_id": "rul_b"}),
  ("T12", TEN_A, {"decision_id": "dec_1"}),
  ("T15", TEN_A, {}),
  ("T16", TEN_A, {"state": None}),
  ("T17", TEN_A, {"task_id": "task_2", "now": NOW + 7, "outcome": "APPROVED"}),
  ("T19", TEN_A, {"assignee_id": "bay_aisha", "task_id": "task_3", "kind": "APPROVE_NOTICE", "agent": "notifier", "now": NOW + 8,
                  "payload_json": "{}", "ruling_id": "rul_b"}),
  ("T18", TEN_A, {"task_id": "task_3", "draft_id": "drf_1", "kind": "LABELER_NOTICE", "to_party": "NuCare Pharmaceuticals, Inc.",
                  "title": "t", "body": "b", "now": NOW + 9}),
  ("T11", TEN_A, {"conversation_id": "conv_1", "channel": "mcp", "now": NOW + 10, "turn_id": "turn_1", "tool": "landed",
                  "args_json": "{}", "verdict": "NOT_LANDED_REVISED", "ruling_id": "rul_b"}),
  ("T21", TEN_A, {"task_id": "task_3", "now": NOW + 11}),
  ("T9", TEN_A, {"fact_ids": [F]}),
  ("T20", TEN_A, {"limit": 10}),
  ("K1", TEN_A, {"site_id": "bay_site_12"}),
  ("K2", TEN_A, {"set_id": NUC_SET}),
  ("K3", TEN_A, {"since": NOW}),
  ("K4", TEN_A, {"entry_id": "bay_fe_montelukast_10"}),
  ("K5", TEN_A, {}),
  ("K6", TEN_A, {"person_id": "bay_aisha"}),
  ("K7", TEN_A, {"version_id": NV}),
  ("K8", TEN_A, {"tool": "landed"}),
  ("P1", HUB, {"version_id": NV, "fact_id": F, "result": "ABSENT", "org_hash": "h_bayview"}),
  ("P1", HUB, {"version_id": NV, "fact_id": F, "result": "ABSENT", "org_hash": "h_bayview"}),
  ("P1", HUB, {"version_id": NV, "fact_id": F, "result": "ABSENT", "org_hash": "h_northgate"}),
  ("I10", HUB, {"version_id": NV, "fact_id": F, "result": "CARRIES_CODED", "method": "matcher_xml", "tier": 1, "phrase_key_version": 1, "now": NOW}),
  ("P1", HUB, {"version_id": ACC_SET + "#v14", "fact_id": F, "result": "ABSENT", "org_hash": "h_bayview"}),
  ("P3", HUB, {"version_id": ACC_SET + "#v14", "fact_id": F, "result": "CARRIES_CODED", "tier": 2, "now": NOW}),
  ("P2", HUB, {"fact_id": F, "org_hash": "h_bayview", "now": NOW}),
  ("D5", HUB, {"set_id": ACC_SET, "version_id": ACC_SET + "#v14", "fact_id": F, "event_id": "land_1", "kind": "LANDED", "now": NOW, "observed": "history"}),
  ("D6", HUB, {"fact_id": F}),
  ("X6", "hubr_test", {"set_id": ACC_SET, "from_d": 18697}),
]
if mode in ("tenant", "all"):
    pipe(["GRAPH.DELETE hubr_test", f"GRAPH.COPY {HUB} hubr_test"])
    bad = []
    for name, g, p in TT:
        if only and name not in only:
            continue
        if not show(name, run(g, Q[name], p), 6):
            bad.append(name)
    print("TENANT FAILED:", bad)
    print("not tested:", sorted(set(Q) - set(TESTS) - {n for n, _, _ in TT} - {f"I{i}" for i in range(1, 14)}))
