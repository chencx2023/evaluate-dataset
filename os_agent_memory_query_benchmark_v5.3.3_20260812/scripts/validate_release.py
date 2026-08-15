#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path, PurePosixPath


MANIFEST_NAME = "RELEASE_MANIFEST.csv"
MUTABLE_POLICY = "review_mutable"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        files[relative] = path
    return files


def read_manifest(root: Path) -> dict[str, dict[str, str]]:
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(f"missing {MANIFEST_NAME}")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"path", "size_bytes", "sha256", "integrity_policy"}
        if set(reader.fieldnames or []) != required:
            raise RuntimeError(f"invalid {MANIFEST_NAME} columns")
        records: dict[str, dict[str, str]] = {}
        for row in reader:
            relative = row["path"]
            pure = PurePosixPath(relative)
            if not relative or pure.is_absolute() or ".." in pure.parts or relative == MANIFEST_NAME:
                raise RuntimeError(f"unsafe manifest path: {relative!r}")
            if relative in records:
                raise RuntimeError(f"duplicate manifest path: {relative}")
            if row["integrity_policy"] not in {"immutable", MUTABLE_POLICY}:
                raise RuntimeError(f"invalid integrity policy for {relative}")
            records[relative] = row
    return records


def verify_release(root: Path, strict_mutable: bool = False) -> dict[str, int]:
    root = root.resolve()
    records = read_manifest(root)
    actual = release_files(root)
    missing = sorted(set(records) - set(actual))
    unexpected = sorted(set(actual) - set(records))
    if missing or unexpected:
        raise RuntimeError(f"release file set mismatch; missing={missing[:5]}, unexpected={unexpected[:5]}")

    mutable_count = 0
    for relative, record in records.items():
        path = actual[relative]
        mutable = record["integrity_policy"] == MUTABLE_POLICY
        mutable_count += int(mutable)
        if mutable and not strict_mutable:
            continue
        expected_size = int(record["size_bytes"])
        if path.stat().st_size != expected_size:
            raise RuntimeError(f"release size mismatch: {relative}")
        if file_sha256(path) != record["sha256"]:
            raise RuntimeError(f"release SHA256 mismatch: {relative}")
    return {
        "files": len(records),
        "immutable_files": len(records) - mutable_count,
        "review_mutable_files": mutable_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a published Agent or Judge release before use.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--strict-mutable",
        action="store_true",
        help="also verify the initial hashes of review files that are expected to change after human review",
    )
    args = parser.parse_args()
    result = verify_release(args.root, strict_mutable=args.strict_mutable)
    print(
        "release integrity passed: "
        f"{result['files']} files, {result['immutable_files']} immutable, "
        f"{result['review_mutable_files']} review-mutable"
    )


if __name__ == "__main__":
    main()
