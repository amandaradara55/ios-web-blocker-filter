#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path
from urllib.request import urlopen

from ublock_origin_common import (
    DEFAULT_BASE_URL,
    DEFAULT_FETCH_DIR,
    DEFAULT_RAW_DIR,
    ROOT_LIST_FILES,
    display_path,
    list_url,
    resolve_repo_path,
    utc_now_iso,
    validate_root_names,
)


INCLUDE_RE = re.compile(r"^!#include\s+([A-Za-z0-9._-]+)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch uBlock Origin distribution filter files into sources/."
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_FETCH_DIR,
        help="Directory to store fetched files and manifest.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL for uBlock Origin distribution files.",
    )
    parser.add_argument(
        "--list",
        action="append",
        dest="lists",
        help="Fetch only the named root list. Repeat for multiple values.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args()


def fetch_text(url: str, timeout: float) -> str:
    with urlopen(url, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_includes(text: str) -> list[str]:
    includes: list[str] = []
    for line in text.splitlines():
        match = INCLUDE_RE.fullmatch(line.strip())
        if match is None:
            continue
        includes.append(match.group(1))
    return includes


def write_manifest(output_dir: Path, manifest: dict) -> None:
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()

    try:
        root_names = validate_root_names(args.lists)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    output_dir = resolve_repo_path(args.output_dir)
    raw_dir = resolve_repo_path(DEFAULT_RAW_DIR)
    if args.output_dir != DEFAULT_FETCH_DIR:
        raw_dir = output_dir / "raw"

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    queue: deque[str] = deque(ROOT_LIST_FILES[name] for name in root_names)
    fetched: dict[str, dict] = {}

    while queue:
        filename = queue.popleft()
        if filename in fetched:
            continue

        url = list_url(args.base_url, filename)
        try:
            text = fetch_text(url, args.timeout)
        except Exception as error:
            print(f"failed to fetch {filename} from {url}: {error}", file=sys.stderr)
            return 1

        includes = extract_includes(text)
        file_path = raw_dir / filename
        file_path.write_text(text, encoding="utf-8")

        fetched[filename] = {
            "name": filename,
            "url": url,
            "path": display_path(file_path),
            "sha256": sha256_text(text),
            "bytes": len(text.encode("utf-8")),
            "lines": len(text.splitlines()),
            "includes": includes,
        }

        for include_name in includes:
            if include_name not in fetched:
                queue.append(include_name)

        print(f"fetched {filename} -> {file_path}")

    manifest = {
        "fetchedAt": utc_now_iso(),
        "baseUrl": args.base_url,
        "roots": [
            {
                "name": root_name,
                "file": ROOT_LIST_FILES[root_name],
                "url": list_url(args.base_url, ROOT_LIST_FILES[root_name]),
            }
            for root_name in root_names
        ],
        "files": [fetched[name] for name in sorted(fetched)],
    }
    write_manifest(output_dir, manifest)
    print(f"wrote manifest -> {output_dir / 'manifest.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
