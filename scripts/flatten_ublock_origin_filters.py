#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ublock_origin_common import (
    DEFAULT_FETCH_DIR,
    DEFAULT_FLAT_DIR,
    DEFAULT_RAW_DIR,
    FLATTEN_PROFILES,
    display_path,
    resolve_repo_path,
    utc_now_iso,
    validate_profile_names,
)


IF_RE = re.compile(r"^!#if\s+(.+?)\s*$")
ELSE_RE = re.compile(r"^!#else\s*$")
ENDIF_RE = re.compile(r"^!#endif\s*$")
INCLUDE_RE = re.compile(r"^!#include\s+([A-Za-z0-9._-]+)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flatten uBlock Origin distribution files by resolving includes and simple preprocessor directives."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_FETCH_DIR,
        help="Directory containing fetched uBlock Origin files.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_FLAT_DIR,
        help="Directory to store flattened outputs.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        dest="profiles",
        help="Flatten only the named profile. Repeat for multiple values.",
    )
    parser.add_argument(
        "--define",
        action="append",
        dest="defines",
        help="Override a profile define, e.g. env_mobile=true. Repeat as needed.",
    )
    return parser.parse_args()


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def parse_define_overrides(items: list[str] | None) -> dict[str, bool]:
    overrides: dict[str, bool] = {}
    if not items:
        return overrides
    for item in items:
        if "=" not in item:
            raise ValueError(f"invalid define override: {item}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid define override: {item}")
        overrides[key] = parse_bool(raw_value)
    return overrides


def evaluate_condition(expression: str, variables: dict[str, bool]) -> tuple[bool, list[str]]:
    unknown: list[str] = []
    parts = [part.strip() for part in expression.split("&&")]
    result = True
    for part in parts:
        if not part:
            result = False
            continue
        negate = part.startswith("!")
        name = part[1:].strip() if negate else part
        value = variables.get(name)
        if value is None:
            unknown.append(name)
            value = False
        result = result and ((not value) if negate else value)
    return result, unknown


def expand_file(
    raw_dir: Path,
    filename: str,
    variables: dict[str, bool],
    include_stack: list[str],
    visited_files: list[str],
    unknown_symbols: set[str],
) -> list[str]:
    path = raw_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"missing fetched file: {path}")
    if filename in include_stack:
        cycle = " -> ".join(include_stack + [filename])
        raise ValueError(f"include cycle detected: {cycle}")

    include_stack.append(filename)
    if filename not in visited_files:
        visited_files.append(filename)

    output: list[str] = []
    condition_stack: list[dict[str, bool]] = []
    active = True

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        include_match = INCLUDE_RE.fullmatch(stripped)
        if include_match is not None:
            if active:
                output.extend(
                    expand_file(
                        raw_dir=raw_dir,
                        filename=include_match.group(1),
                        variables=variables,
                        include_stack=include_stack,
                        visited_files=visited_files,
                        unknown_symbols=unknown_symbols,
                    )
                )
            continue

        if_match = IF_RE.fullmatch(stripped)
        if if_match is not None:
            parent_active = active
            condition_result, unknown = evaluate_condition(if_match.group(1), variables)
            unknown_symbols.update(unknown)
            frame = {
                "parent_active": parent_active,
                "condition_result": condition_result,
                "in_else": False,
            }
            condition_stack.append(frame)
            active = parent_active and condition_result
            continue

        if ELSE_RE.fullmatch(stripped) is not None:
            if not condition_stack:
                raise ValueError(f"!#else without !#if in {filename}")
            frame = condition_stack[-1]
            if frame["in_else"]:
                raise ValueError(f"duplicate !#else in {filename}")
            frame["in_else"] = True
            active = frame["parent_active"] and (not frame["condition_result"])
            continue

        if ENDIF_RE.fullmatch(stripped) is not None:
            if not condition_stack:
                raise ValueError(f"!#endif without !#if in {filename}")
            frame = condition_stack.pop()
            active = frame["parent_active"]
            continue

        if active:
            output.append(line)

    if condition_stack:
        raise ValueError(f"unclosed !#if block in {filename}")

    include_stack.pop()
    return output


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()

    try:
        profiles = validate_profile_names(args.profiles)
        define_overrides = parse_define_overrides(args.defines)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    input_dir = resolve_repo_path(args.input_dir)
    raw_dir = resolve_repo_path(DEFAULT_RAW_DIR)
    if args.input_dir != DEFAULT_FETCH_DIR:
        raw_dir = input_dir / "raw"
    output_dir = resolve_repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_profiles: list[dict] = []

    for profile_name in profiles:
        profile = FLATTEN_PROFILES[profile_name]
        variables = dict(profile["defines"])
        variables.update(define_overrides)

        visited_files: list[str] = []
        unknown_symbols: set[str] = set()
        try:
            lines = expand_file(
                raw_dir=raw_dir,
                filename=profile["root"],
                variables=variables,
                include_stack=[],
                visited_files=visited_files,
                unknown_symbols=unknown_symbols,
            )
        except Exception as error:
            print(f"failed to flatten {profile_name}: {error}", file=sys.stderr)
            return 1

        output_path = output_dir / f"{profile_name}.txt"
        write_text(output_path, "\n".join(lines) + "\n")

        manifest_profiles.append(
            {
                "name": profile_name,
                "root": profile["root"],
                "path": display_path(output_path),
                "defines": variables,
                "inputFiles": visited_files,
                "unknownSymbolsDefaultedFalse": sorted(unknown_symbols),
                "lines": len(lines),
            }
        )
        print(f"flattened {profile_name} -> {output_path}")

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generatedAt": utc_now_iso(),
                "inputDir": display_path(raw_dir),
                "profiles": manifest_profiles,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote manifest -> {manifest_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
