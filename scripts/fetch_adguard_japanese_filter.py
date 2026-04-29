#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen

from adguard_japanese_filter_common import (
    DEFAULT_BASE_URL,
    DEFAULT_FETCH_DIR,
    repo_root,
    resolve_repo_path,
    section_url,
    utc_now_iso,
    validate_sections,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch AdGuard JapaneseFilter section files into sources/."
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_FETCH_DIR,
        help="Directory to store fetched section files.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL for section files. Defaults to GitHub raw content.",
    )
    parser.add_argument(
        "--section",
        action="append",
        dest="sections",
        help="Fetch only the named section. Repeat to fetch multiple sections.",
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


def write_manifest(output_dir: Path, manifest: dict) -> None:
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(repo_root()))
    except ValueError:
        return str(path)


def main() -> int:
    args = parse_args()

    try:
        sections = validate_sections(args.sections)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    output_dir = resolve_repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fetched_at = utc_now_iso()
    manifest_sections: list[dict] = []

    for section_name in sections:
        url = section_url(args.base_url, section_name)
        try:
            text = fetch_text(url, args.timeout)
        except Exception as error:
            print(f"failed to fetch {section_name} from {url}: {error}", file=sys.stderr)
            return 1
        section_path = output_dir / section_name
        section_path.write_text(text, encoding="utf-8")

        line_count = len(text.splitlines())
        bytes_count = len(text.encode("utf-8"))
        digest = sha256_text(text)

        manifest_sections.append(
            {
                "name": section_name,
                "url": url,
                "path": display_path(section_path),
                "sha256": digest,
                "bytes": bytes_count,
                "lines": line_count,
            }
        )

        print(f"fetched {section_name} -> {section_path}")

    write_manifest(
        output_dir,
        {
            "fetchedAt": fetched_at,
            "baseUrl": args.base_url,
            "sections": manifest_sections,
        },
    )

    print(
        f"wrote manifest -> {output_dir / 'manifest.json'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
