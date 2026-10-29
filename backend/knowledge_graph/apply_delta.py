"""Apply the expected graph change of a wave (gold/deltas/wave_N_delta.csv) to the domain graph.

The deltas say what the graph learns from the documents of each wave:
  add_node     a new entity (the delta carries only label and id, so name = id until a better name is known)
  add_edge     a new relationship (endpoint labels are looked up from the gold nodes and earlier deltas)
  expire_edge  sets valid_to on the current edge; nothing is deleted
  expire_node  sets valid_to (and status 'former' for people) on the node

Every write is a MERGE or guarded by `valid_to IS NULL`, so re-running a wave is safe.
Apply waves in order, and before uploading that wave's documents, so the uploaded documents
link to their Document nodes and the entity names in the text are recognised.

    python -m knowledge_graph.apply_delta --gold-dir C:\\company_corpus\\gold --wave 1 --dry-run
    python -m knowledge_graph.apply_delta --gold-dir C:\\company_corpus\\gold --wave 1 2 3
"""
import argparse
import csv
import json
import os
import re
from collections import Counter

from .loader import LABEL_RE, REL_RE, _digest, normalize, uid

OPS = {"add_node", "add_edge", "expire_edge", "expire_node"}
ALIASED_LABELS = {"Document", "PolicyVersion", "Contract", "Project", "Policy", "Role", "Person"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def delta_path(gold_dir, wave):
    return os.path.join(gold_dir, "deltas", f"wave_{wave}_delta.csv")


def label_map(gold_dir, waves):
    """id -> label, from the gold nodes (wave 0) and the add_node rows of the requested waves."""
    ids = {}
    for r in read_rows(os.path.join(gold_dir, "nodes.csv")):
        ids[r["id"]] = r["label"]
    for wave in waves:
        path = delta_path(gold_dir, wave)
        if os.path.exists(path):
            for r in read_rows(path):
                if r["op"] == "add_node":
                    ids[r["src_or_node_id"]] = r["label"]
    return ids


def prepare(rows, ids, wave):
    """Group the delta rows by operation. Rows that cannot be placed are counted, not guessed."""
    out = {"add_node": [], "add_edge": [], "expire_edge": [], "expire_node": []}
    skipped = Counter()
    for r in rows:
        op = r["op"]
        if op not in OPS:
            skipped["unknown_op"] += 1
            continue
        prov = r["provenance_doc_id"] or None
        if op in ("add_node", "expire_node"):
            label, node_id = r["label"], r["src_or_node_id"]
            if not LABEL_RE.match(label):
                raise ValueError(f"Unsafe node label: {label!r}")
            row = {"uid": uid(label, node_id), "id": node_id, "label": label, "prov": prov, "wave": wave}
            if op == "add_node":
                row["name"] = node_id
            else:
                row["valid_to"] = r["valid_to"] or None
                if not row["valid_to"] or not DATE.match(row["valid_to"]):
                    skipped["bad_date"] += 1
                    continue
            out[op].append(row)
            continue
        rel, src_id, dst_id = r["rel"], r["src_or_node_id"], r["dst_id"]
        if not REL_RE.match(rel):
            raise ValueError(f"Unsafe relationship type: {rel!r}")
        if src_id not in ids or dst_id not in ids:
            skipped["unresolved_endpoint"] += 1
            continue
        src, dst = uid(ids[src_id], src_id), uid(ids[dst_id], dst_id)
        vf, vt = r["valid_from"] or None, r["valid_to"] or None
        if op == "add_edge":
            eid = _digest(src, rel, dst, vf or "", vt or "", f"w{wave}")
            out[op].append({"rel": rel, "src": src, "dst": dst, "eid": eid, "valid_from": vf, "valid_to": vt,
                            "prov": prov, "wave": wave})
        else:
            if not vt or not DATE.match(vt):
                skipped["bad_date"] += 1
                continue
            out[op].append({"rel": rel, "src": src, "dst": dst, "valid_to": vt, "prov": prov, "wave": wave})
    return out, skipped


def alias_rows(nodes):
    """New entities can be found by their id (document numbers, policy versions...)."""
    out = []
    for n in nodes:
        if n["label"] in ALIASED_LABELS and normalize(n["id"]):
            out.append({"uid": n["uid"], "aid": _digest(n["uid"], n["id"], "derived_id"), "alias": n["id"],
                        "norm": normalize(n["id"]), "alias_type": "derived_id", "valid_from": None,
                        "valid_to": None, "ambiguous": False, "ambiguous_with": []})
    return out


def latest_date(prepared):
    dates = [v for rows in prepared.values() for r in rows for v in (r.get("valid_from"), r.get("valid_to")) if v]
    return max(dates) if dates else None


def summary(prepared, skipped):
    return {**{op: len(rows) for op, rows in prepared.items()}, "skipped": dict(skipped),
            "edges_by_rel": dict(Counter(r["rel"] for r in prepared["add_edge"]).most_common(8))}


# --------------------------------- Neo4j I/O ---------------------------------
def _batches(items, size=1000):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def write(prepared, run):
    by_label = {}
    for n in prepared["add_node"]:
        by_label.setdefault(n["label"], []).append(n)
    for label, rows in by_label.items():
        query = (f"UNWIND $rows AS row MERGE (n:Entity:{label} {{uid: row.uid}}) "
                 "ON CREATE SET n.id = row.id, n.name = row.name, n.source_doc = row.prov, n.wave = row.wave")
        for batch in _batches(rows):
            run(query, rows=batch)

    alias_query = ("UNWIND $rows AS row MATCH (e:Entity {uid: row.uid}) MERGE (a:Alias {aid: row.aid}) "
                   "SET a.alias = row.alias, a.norm = row.norm, a.alias_type = row.alias_type, "
                   "a.ambiguous = row.ambiguous, a.ambiguous_with = row.ambiguous_with MERGE (a)-[:ALIAS_OF]->(e)")
    for batch in _batches(alias_rows(prepared["add_node"])):
        run(alias_query, rows=batch)

    by_rel = {}
    for e in prepared["add_edge"]:
        by_rel.setdefault(e["rel"], []).append(e)
    for rel, rows in by_rel.items():
        query = ("UNWIND $rows AS row MATCH (a:Entity {uid: row.src}) MATCH (b:Entity {uid: row.dst}) "
                 f"MERGE (a)-[r:{rel} {{eid: row.eid}}]->(b) "
                 "SET r.valid_from = row.valid_from, r.valid_to = row.valid_to, r.source_doc = row.prov, r.wave = row.wave")
        for batch in _batches(rows):
            run(query, rows=batch)

    by_rel = {}
    for e in prepared["expire_edge"]:
        by_rel.setdefault(e["rel"], []).append(e)
    for rel, rows in by_rel.items():
        query = ("UNWIND $rows AS row MATCH (a:Entity {uid: row.src})-[r:" + rel + "]->(b:Entity {uid: row.dst}) "
                 "WHERE r.valid_to IS NULL SET r.valid_to = row.valid_to, r.expired_by = row.prov")
        for batch in _batches(rows):
            run(query, rows=batch)

    for batch in _batches(prepared["expire_node"]):
        run("UNWIND $rows AS row MATCH (n:Entity {uid: row.uid}) WHERE n.valid_to IS NULL "
            "SET n.valid_to = row.valid_to, n.expired_by = row.prov, "
            "n.status = CASE WHEN n:Person THEN 'former' ELSE n.status END", rows=batch)


def record(run, wave, as_of, counts):
    run("MERGE (m:GraphMeta {name: 'domain'}) "
        "SET m.applied_waves = [w IN coalesce(m.applied_waves, []) WHERE w <> $wave] + [$wave], "
        "m.as_of = CASE WHEN $as_of IS NOT NULL AND (m.as_of IS NULL OR $as_of > m.as_of) THEN $as_of ELSE m.as_of END, "
        "m.last_delta = $last", wave=wave, as_of=as_of, last=json.dumps(counts, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply gold/deltas/wave_N_delta.csv to the company graph.")
    parser.add_argument("--gold-dir", default=os.getenv("CORPUS_GOLD_DIR"), help="folder with nodes.csv and deltas/")
    parser.add_argument("--wave", type=int, nargs="+", required=True, help="waves to apply, in order")
    parser.add_argument("--dry-run", action="store_true", help="parse and count only; no Neo4j needed")
    parser.add_argument("--keep-as-of", action="store_true", help="do not move GraphMeta.as_of to the latest delta date")
    args = parser.parse_args(argv)
    if not args.gold_dir:
        parser.error("--gold-dir is required (or set CORPUS_GOLD_DIR)")
    waves = sorted(set(args.wave))
    ids = label_map(args.gold_dir, range(1, max(waves) + 1))

    plans = []
    for wave in waves:
        path = delta_path(args.gold_dir, wave)
        if not os.path.exists(path):
            parser.error(f"No delta file for wave {wave}: {path}")
        prepared, skipped = prepare(read_rows(path), ids, wave)
        plans.append((wave, prepared, skipped))
        print(f"wave {wave}: {json.dumps(summary(prepared, skipped))}")
    if args.dry_run:
        print("Dry run only. Nothing was written.")
        return 0

    from knowledge_graph.db import close_driver, run

    try:
        for wave, prepared, skipped in plans:
            write(prepared, run)
            as_of = None if args.keep_as_of else latest_date(prepared)
            record(run, wave, as_of, summary(prepared, skipped))
            print(f"wave {wave} applied" + (f"; as_of moved to {as_of} if later" if as_of else ""))
        meta = run("MATCH (m:GraphMeta {name: 'domain'}) RETURN m.applied_waves AS waves, m.as_of AS as_of")
        print("GraphMeta:", meta[0] if meta else None)
    finally:
        close_driver()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
