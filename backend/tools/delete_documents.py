"""Remove uploaded documents (vectors, metadata, graph chunks) through the running API.

Use it to undo uploads that should not be in the index, e.g. files an `upload_wave.py` run reported as
the wrong outcome:

    python tools/delete_documents.py high_compression_ratio__zeros.txt
    python tools/delete_documents.py --report C:\\company_corpus\\reports\\run_w3.json --prefix near_duplicates/ --actual ingest
    python tools/delete_documents.py --report run_w3.json --prefix near_duplicates/ --actual ingest --yes

Without --yes it only lists what it would delete.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def names_from_report(report, prefix="", actual=None):
    """File names (as uploaded) of report entries under `prefix` whose observed outcome was `actual`."""
    results = report["results"] if isinstance(report, dict) else report
    out = []
    for r in results:
        if prefix and not r["file"].replace("\\", "/").startswith(prefix):
            continue
        if actual and r.get("actual") != actual:
            continue
        out.append(Path(r["file"].replace("\\", "/")).name)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="file names exactly as they were uploaded")
    ap.add_argument("--report", help="an upload_wave.py report (JSON)")
    ap.add_argument("--prefix", default="", help="with --report: only files whose path starts with this")
    ap.add_argument("--actual", help="with --report: only files whose observed outcome was this (e.g. ingest)")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--yes", action="store_true", help="delete (default is a preview)")
    args = ap.parse_args(argv)

    names = list(args.names)
    if args.report:
        names += names_from_report(json.loads(Path(args.report).read_text(encoding="utf-8")), args.prefix, args.actual)
    if not names:
        ap.error("give file names or --report")
    print(f"{len(names)} documents:")
    for n in names:
        print("  " + n)
    if not args.yes:
        print("Preview only. Add --yes to delete.")
        return 0

    import httpx
    from supabase_.file_upload import safe_filename

    removed = missing = 0
    with httpx.Client(timeout=120) as client:
        for n in names:
            r = client.delete(f"{args.api}/delete-document/{quote(safe_filename(n), safe='')}")
            if r.status_code == 404:
                missing += 1
            else:
                r.raise_for_status()
                removed += 1
    print(f"Deleted {removed}; {missing} were not found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
