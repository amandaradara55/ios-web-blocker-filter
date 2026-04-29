#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from easylist_common import (
    DEFAULT_BASE_URL,
    DEFAULT_FETCH_DIR,
    LIST_FILES,
    display_path,
    list_url,
    resolve_repo_path,
    utc_now_iso,
    validate_list_names,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch EasyList distribution files into sources/."
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_FETCH_DIR,
        help="Directory to store fetched list files and manifest.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL for EasyList distribution files.",
    )
    parser.add_argument(
        "--list",
        action="append",
        dest="lists",
        help="Fetch only the named list. Repeat for multiple values.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args()


def fetch_text(url: str, timeout: float) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "ios-web-blocker-filter/1.0 "
                "(https://github.com/amandaradara55/ios-web-blocker-filter)"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_manifest(output_dir: Path, manifest: dict) -> None:
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()

    try:
        list_names = validate_list_names(args.lists)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    output_dir = resolve_repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fetched_lists: list[dict] = []

    for list_name in list_names:
        filename = LIST_FILES[list_name]
        url = list_url(args.base_url, filename)

        try:
            text = fetch_text(url, args.timeout)
        except Exception as error:
            print(f"failed to fetch {list_name} from {url}: {error}", file=sys.stderr)
            return 1

        list_path = output_dir / filename
        list_path.write_text(text, encoding="utf-8")

        fetched_lists.append(
            {
                "name": list_name,
                "file": filename,
                "url": url,
                "path": display_path(list_path),
                "sha256": sha256_text(text),
                "bytes": len(text.encode("utf-8")),
                "lines": len(text.splitlines()),
            }
        )

        print(f"fetched {list_name} -> {list_path}")

    write_manifest(
        output_dir,
        {
            "fetchedAt": utc_now_iso(),
            "baseUrl": args.base_url,
            "lists": fetched_lists,
        },
    )
    print(f"wrote manifest -> {output_dir / 'manifest.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
