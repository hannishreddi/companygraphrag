"""Wave deltas: row preparation, endpoint resolution, safe expiry and idempotent writes."""
import csv

import pytest

from knowledge_graph import apply_delta as ad

HEADER = ["op", "label", "src_or_node_id", "rel", "dst_id", "valid_from", "valid_to", "provenance_doc_id"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


@pytest.fixture
def gold(tmp_path):
    with open(tmp_path / "nodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_key", "label", "id", "name", "props_json"])
        w.writerow(["Person:LS00001", "Person", "LS00001", "Meenakshi Iyer", "{}"])
        w.writerow(["Client:CL-001", "Client", "CL-001", "Deccan Freight Logistics", "{}"])
        w.writerow(["Team:ENG-DATA", "Team", "ENG-DATA", "Data", "{}"])
    (tmp_path / "deltas").mkdir()
    write_csv(tmp_path / "deltas" / "wave_1_delta.csv", [
        ["add_node", "Document", "LS-PRS-2026-0001", "", "", "", "", "LS-PRS-2026-0001"],
        ["add_edge", "", "LS-PRS-2026-0001", "MENTIONS", "CL-001", "", "", "LS-PRS-2026-0001"],
        ["add_edge", "", "LS-PRS-2026-0001", "AUTHORED_BY", "LS00001", "", "", "LS-PRS-2026-0001"],
        ["add_edge", "", "LS-PRS-2026-0001", "MENTIONS", "NOPE-1", "", "", "LS-PRS-2026-0001"],
        ["expire_edge", "", "LS00001", "MEMBER_OF", "ENG-DATA", "", "2026-11-01", "LS-ORG-2026-0004"],
        ["expire_edge", "", "LS00001", "MEMBER_OF", "ENG-DATA", "", "", "LS-ORG-2026-0004"],
        ["expire_node", "Person", "LS00001", "", "", "", "2026-12-10", "LS-LTR-2026-0024"],
    ])
    return tmp_path


def test_prepare_resolves_endpoint_labels_and_skips_unknown_ones(gold):
    ids = ad.label_map(str(gold), [1])
    prepared, skipped = ad.prepare(ad.read_rows(ad.delta_path(str(gold), 1)), ids, 1)
    assert [n["uid"] for n in prepared["add_node"]] == ["Document:LS-PRS-2026-0001"]
    assert prepared["add_node"][0]["name"] == "LS-PRS-2026-0001"
    edge = prepared["add_edge"][0]
    assert (edge["src"], edge["rel"], edge["dst"]) == ("Document:LS-PRS-2026-0001", "MENTIONS", "Client:CL-001")
    assert skipped["unresolved_endpoint"] == 1 and skipped["bad_date"] == 1
    assert len(prepared["expire_edge"]) == 1 and prepared["expire_edge"][0]["valid_to"] == "2026-11-01"
    assert prepared["expire_node"][0]["uid"] == "Person:LS00001"


def test_edge_ids_are_stable_and_depend_on_the_wave(gold):
    ids = ad.label_map(str(gold), [1])
    rows = ad.read_rows(ad.delta_path(str(gold), 1))
    a, _ = ad.prepare(rows, ids, 1)
    b, _ = ad.prepare(rows, ids, 1)
    c, _ = ad.prepare(rows, ids, 2)
    assert a["add_edge"][0]["eid"] == b["add_edge"][0]["eid"] != c["add_edge"][0]["eid"]


def test_unsafe_relationship_types_never_reach_cypher(gold):
    ids = {"A": "Person", "B": "Person"}
    row = dict(zip(ad.csv.DictReader(open(gold / "deltas" / "wave_1_delta.csv")).fieldnames,
                   ["add_edge", "", "A", "X) DETACH DELETE (n", "B", "", "", "d"]))
    with pytest.raises(ValueError):
        ad.prepare([row], ids, 1)


def test_new_documents_get_an_id_alias(gold):
    ids = ad.label_map(str(gold), [1])
    prepared, _ = ad.prepare(ad.read_rows(ad.delta_path(str(gold), 1)), ids, 1)
    aliases = ad.alias_rows(prepared["add_node"])
    assert aliases[0]["norm"] == "ls prs 2026 0001" and aliases[0]["uid"] == "Document:LS-PRS-2026-0001"


def test_write_uses_merge_and_guards_expiry(gold):
    ids = ad.label_map(str(gold), [1])
    prepared, _ = ad.prepare(ad.read_rows(ad.delta_path(str(gold), 1)), ids, 1)
    calls = []
    ad.write(prepared, lambda q, **p: calls.append(q))
    text = "\n".join(calls)
    assert "MERGE (n:Entity:Document {uid: row.uid})" in text and "ON CREATE SET" in text
    assert "MERGE (a)-[r:MENTIONS {eid: row.eid}]->(b)" in text
    assert "WHERE r.valid_to IS NULL SET r.valid_to" in text
    assert "DELETE" not in text


def test_latest_date_picks_the_newest_validity_date(gold):
    ids = ad.label_map(str(gold), [1])
    prepared, _ = ad.prepare(ad.read_rows(ad.delta_path(str(gold), 1)), ids, 1)
    assert ad.latest_date(prepared) == "2026-12-10"
