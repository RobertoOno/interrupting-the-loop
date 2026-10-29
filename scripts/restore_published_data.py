#!/usr/bin/env python3
"""Restore data from the versioned public evidence deposits; never overwrite code."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECORDS = {"programs": "22713807", "papers": "23163299", "report": "23562924"}


def destination(name: str, deposit: str) -> Path | None:
    """Map an archive member to data only; reject traversal even in ignored paths."""
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError("unsafe archive path")
    parts = p.parts[1:]
    if not parts:
        return None
    if deposit != "report":
        return Path(*parts) if parts[0] in {"docs", "runs", "worlds"} else None
    mappings = {
        ("evidence", "r1_replay"): ("docs", "r1", "evidence_v1"),
        ("evidence", "r2_pilots"): ("docs", "r2", "pilot_evidence_v1"),
        ("review", "round0_2026-10-08"): ("docs", "r1", "report_review_v1"),
        ("review", "rounds_2026-10-15_onward"): ("docs", "r1", "report_review_v2"),
    }
    if parts == ("evidence", "reference_set_v1.jsonl"):
        return Path("docs/r1/reference_set_v1.jsonl")
    for prefix, target in mappings.items():
        if parts[:len(prefix)] == prefix:
            return Path(*target, *parts[len(prefix):])
    if parts[0] == "frozen":
        return Path("runs/r1", *parts)
    return None


def write_data(root: Path, rel: Path, data: bytes) -> bool:
    target = root / rel
    # Data may not be redirected through symlinked parents or targets.
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink blocks restoration: {rel}")
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError(f"existing file differs; preserve it and restore in a fresh clone: {rel}")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as out:
        out.write(data)
    return True


def restore(archive: Path, deposit: str, root: Path) -> int:
    written = 0
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                rel = destination(item.filename, deposit)
                if rel is not None and not item.is_dir():
                    if (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError("archive symlink")
                    written += write_data(root, rel, z.read(item))
    else:
        with tarfile.open(archive) as tf:
            for item in tf:
                rel = destination(item.name, deposit)
                if rel is not None:
                    if item.issym() or item.islnk():
                        raise ValueError("archive link")
                    if item.isfile():
                        written += write_data(root, rel, tf.extractfile(item).read())
    return written


def verified_download(url: str, target: Path, checksum: str) -> None:
    algorithm, expected = checksum.split(":", 1)
    if algorithm != "md5":
        raise ValueError("unsupported Zenodo checksum")
    if not target.exists():
        partial = target.with_name(target.name + ".partial")
        with urllib.request.urlopen(url, timeout=180) as response, partial.open("wb") as out:
            while block := response.read(1024 * 1024):
                out.write(block)
        if hashlib.md5(partial.read_bytes()).hexdigest() != expected:
            raise ValueError(f"checksum mismatch: {target.name}")
        partial.replace(target)
    if hashlib.md5(target.read_bytes()).hexdigest() != expected:
        raise ValueError(f"checksum mismatch: {target.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deposit", choices=RECORDS, required=True)
    ap.add_argument("--download-dir", type=Path, default=ROOT / ".reproduction-data/downloads")
    args = ap.parse_args()
    record = RECORDS[args.deposit]
    with urllib.request.urlopen(f"https://zenodo.org/api/records/{record}", timeout=60) as response:
        metadata = json.load(response)
    args.download_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for item in metadata["files"]:
        if not item["key"].endswith((".tar.gz", ".zip")) or item["key"] == "preregistrations.tar.gz":
            continue
        # File keys must remain a single filename inside the cache directory.
        if Path(item["key"]).name != item["key"] or "\\" in item["key"]:
            raise ValueError("unsafe download filename")
        archive = args.download_dir / f"{record}-{item['key']}"
        verified_download(item["links"]["self"], archive, item["checksum"])
        count = restore(archive, args.deposit, ROOT)
        total += count
        print(f"Verified {item['key']}: restored {count} data files", flush=True)
    print(f"Restored {total} new files from doi:10.5281/zenodo.{record}")


if __name__ == "__main__":
    main()
