"""Remove predictions that were produced while Neo4j was down or the run was cut off, so they get re-run.

    python -m evaluation.prune --name final            # list the affected questions
    python -m evaluation.prune --name final --yes      # drop them (a .bak copy of every file is kept)

A question is affected when any of its rows fell back to documents although the route needed the graph, or
recorded a connection / quota error. All modes of that question are removed together, so the rerun is consistent.
Finished questions and cached LLM calls are untouched; run the evaluation again afterwards.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def affected_qids(rows_by_mode, is_degraded):
    return sorted({p["qid"] for rows in rows_by_mode.values() for p in rows if is_degraded(p)})


def main(argv=None):
    from evaluation.run_eval import degraded, read_jsonl

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="main")
    ap.add_argument("--yes", action="store_true", help="remove them (default is a preview)")
    args = ap.parse_args(argv)

    run_dir = Path(__file__).resolve().parent / "runs" / args.name
    files = sorted(p for p in run_dir.glob("*.jsonl") if p.name != "llm_cache.jsonl")
    rows_by_mode = {p.stem: read_jsonl(p) for p in files}
    bad = affected_qids(rows_by_mode, degraded)
    print(f"{len(bad)} questions were answered without a working graph or were cut off: {', '.join(bad) or '-'}")
    if not bad or not args.yes:
        print("Preview only. Add --yes to remove them." if bad else "Nothing to remove.")
        return 0
    drop = set(bad)
    for path in files:
        shutil.copy(path, path.with_suffix(".jsonl.bak"))
        kept = [p for p in rows_by_mode[path.stem] if p["qid"] not in drop]
        path.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in kept), encoding="utf-8")
    print(f"Removed {len(bad)} questions from {len(files)} files. Run the evaluation again to redo them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
