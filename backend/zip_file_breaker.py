import os
import zipfile
from io import BytesIO

from fastapi import UploadFile

from app_config import MAX_ZIP_DEPTH, MAX_ZIP_MEMBER_BYTES, MAX_ZIP_RATIO, MAX_ZIP_UNCOMPRESSED_BYTES


def _is_junk(name: str) -> bool:
    base = os.path.basename(name)
    return (
        name.endswith("/")
        or "__MACOSX/" in name
        or base.startswith((".", "~$"))
        or base == "Thumbs.db"
    )


def _zip_prefix(zip_name: str) -> str:
    """Short, stable label for a ZIP: its document ref ('LS-ZIP-2021-0001__pack.zip' -> 'LS-ZIP-2021-0001')."""
    stem = os.path.splitext(os.path.basename((zip_name or "archive").replace("\\", "/")))[0]
    return (stem.split("__")[0] if "__" in stem else stem)[:60] or "archive"


def outcome_of(result: dict) -> str:
    """One word for the whole archive: ingest, partial, duplicate or reject."""
    good, dup = bool(result["ingested_files"]), bool(result["duplicate_files"])
    bad = bool(result["failed_files"] or result["skipped_files"])
    if good:
        return "partial" if bad else "ingest"
    if dup and not bad:
        return "duplicate"
    return "partial" if (dup or result["skipped_files"]) else "reject"


def _suspicious(info) -> str | None:
    """Why a member should not be expanded (a tiny file that unpacks to megabytes is a decompression bomb)."""
    if info.file_size > MAX_ZIP_MEMBER_BYTES:
        return f"Member expands to {info.file_size} bytes, over the {MAX_ZIP_MEMBER_BYTES} byte limit."
    if info.file_size > 1024 * 1024 and info.file_size > MAX_ZIP_RATIO * max(info.compress_size, 1):
        return f"Compression ratio over {MAX_ZIP_RATIO}:1; skipped as a possible decompression bomb."
    return None


def zip_file_breaker(zip_upload, ingest, depth=0, prefix=None):
    result = _break(zip_upload, ingest, depth, prefix)
    if depth == 0:
        result["outcome"] = outcome_of(result)
    return result


def _break(zip_upload, ingest, depth=0, prefix=None):
    """Ingest every file inside a ZIP (nested ZIPs up to MAX_ZIP_DEPTH).

    `ingest` takes an UploadFile and returns a result dict with a 'status'.
    Files are read in memory and never written to disk, so member paths cannot
    escape anywhere. Members are stored as '<zip label>__<member name>': different archives
    often hold files with the same name (Lessons_learned.txt), and without the label they would
    overwrite each other as "new versions" of one document.
    """
    prefix = prefix or _zip_prefix(zip_upload.filename)
    ingested, duplicates, failed, skipped = [], [], [], []

    def record(name, result):
        entry = {"filename": name, "result": result}
        status = result.get("status")
        if status == "duplicate":
            duplicates.append(entry)
        elif status == "failed":
            failed.append(entry)
        else:
            ingested.append(entry)

    zip_upload.file.seek(0)
    # Copy into memory: on older Pythons SpooledTemporaryFile has no `seekable`, which zipfile needs.
    raw = zip_upload.file.read()
    try:
        archive = zipfile.ZipFile(BytesIO(raw))
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        return {
            "ingested_files": [],
            "duplicate_files": [],
            "failed_files": [
                {"filename": zip_upload.filename, "error": f"Not a valid ZIP file ({type(exc).__name__}: {exc})."}
            ],
            "skipped_files": [],
        }

    with archive:
        total = sum(info.file_size for info in archive.infolist())
        if total > MAX_ZIP_UNCOMPRESSED_BYTES:
            return {
                "ingested_files": [],
                "duplicate_files": [],
                "failed_files": [
                    {
                        "filename": zip_upload.filename,
                        "error": f"Archive expands to {total} bytes, over the {MAX_ZIP_UNCOMPRESSED_BYTES} byte limit.",
                    }
                ],
                "skipped_files": [],
            }

        for info in archive.infolist():
            name = info.filename
            if _is_junk(name):
                continue
            base = os.path.basename(name)
            problem = _suspicious(info)
            if problem:
                skipped.append({"filename": name, "reason": problem})
                continue
            try:
                data = archive.read(info)
                if base.lower().endswith(".zip"):
                    upload = UploadFile(filename=base, file=BytesIO(data))
                    if depth + 1 >= MAX_ZIP_DEPTH:
                        skipped.append({"filename": name, "reason": "ZIP nested too deeply."})
                        continue
                    nested = _break(upload, ingest, depth + 1, f"{prefix}__{_zip_prefix(base)}")
                    ingested.extend(nested["ingested_files"])
                    duplicates.extend(nested["duplicate_files"])
                    failed.extend(nested["failed_files"])
                    skipped.extend(nested["skipped_files"])
                else:
                    upload = UploadFile(filename=f"{prefix}__{base}", file=BytesIO(data))
                    record(name, ingest(upload))
            except Exception as exc:  # noqa: BLE001 - one bad member must not stop the rest
                failed.append({"filename": name, "error": f"{type(exc).__name__}: {exc}"})

    return {
        "ingested_files": ingested,
        "duplicate_files": duplicates,
        "failed_files": failed,
        "skipped_files": skipped,
    }
