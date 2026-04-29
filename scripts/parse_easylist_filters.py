#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections import Counter
from pathlib import Path

from easylist_common import (
    DEFAULT_BLOCK_OUTPUTS,
    DEFAULT_COSMETIC_OUTPUTS,
    DEFAULT_DISABLED_BLOCK_OUTPUTS,
    DEFAULT_FETCH_DIR,
    DEFAULT_SUMMARY_OUTPUT,
    LIST_FILES,
    QUARANTINED_SOURCE_RULES,
    RULE_NAMESPACE,
    resolve_repo_path,
    utc_now_iso,
    validate_list_names,
)
from parser_common import (
    block_signature,
    cosmetic_signature,
    parse_raw_regex_components,
    regex_parse_error,
)


DOMAIN_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PURE_DOMAIN_RULE_RE = re.compile(
    r"^\|\|(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})\^?$"
)
DOMAIN_WITH_PATH_RE = re.compile(
    r"^\|\|(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?P<suffix>/.+)$"
)

ALLOWLIST_MARKERS = ("@@", "#@#", "#@?#", "#@$#", "#@%#")
ADVANCED_MARKERS = ("#?#", "#$#", "#%#", "$$")
UNSUPPORTED_SELECTOR_TOKENS = (
    ":has(",
    ":-abp-properties(",
    ":contains(",
    ":matches-css",
    ":matches-attr(",
    ":matches-media(",
    ":matches-path(",
    ":matches-property(",
    ":min-text-length(",
    ":style(",
    "xpath(",
    ":xpath(",
    ":upward(",
    ":nth-ancestor(",
    ":remove(",
    ":remove-",
    ":watch-attr(",
    ":if(",
    ":has-text(",
    "[-ext-",
)
UNSUPPORTED_SELECTOR_CHARS = ("{", "}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse fetched EasyList distribution files into JSON rules."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_FETCH_DIR,
        help="Directory containing fetched EasyList distribution files.",
    )
    parser.add_argument(
        "--list",
        action="append",
        dest="lists",
        help="Parse only the named list. Repeat to parse multiple lists.",
    )
    parser.add_argument(
        "--summary-output",
        default=DEFAULT_SUMMARY_OUTPUT,
        help="Output JSON path for parse summary.",
    )
    return parser.parse_args()


def make_rule_id(kind: str, list_name: str, normalized_rule: str) -> str:
    seed = f"{kind}:{list_name}:{normalized_rule}"
    return str(uuid.uuid5(RULE_NAMESPACE, seed))


def split_pattern_and_options(rule: str) -> tuple[str, list[str]]:
    if "$" not in rule:
        return rule, []
    pattern, options_text = rule.split("$", 1)
    options = [token.strip() for token in options_text.split(",") if token.strip()]
    return pattern, options


def has_unsupported_selector_features(selector: str) -> bool:
    return any(token in selector for token in UNSUPPORTED_SELECTOR_TOKENS) or any(
        char in selector for char in UNSUPPORTED_SELECTOR_CHARS
    )


def is_allowlist_rule(rule: str) -> bool:
    return rule.startswith(ALLOWLIST_MARKERS[0]) or any(
        marker in rule for marker in ALLOWLIST_MARKERS[1:]
    )


def is_advanced_rule(rule: str) -> bool:
    if any(marker in rule for marker in ADVANCED_MARKERS):
        return True
    if "+js(" in rule or "scriptlet(" in rule:
        return True
    return False


def parse_domains(prefix: str) -> tuple[list[str] | None, str | None]:
    domains: list[str] = []
    for token in prefix.split(","):
        domain = token.strip()
        if not domain:
            return None, "malformed_domain_list"
        if domain.startswith("~"):
            return None, "negated_domain"
        if not DOMAIN_RE.fullmatch(domain):
            return None, "unsupported_domain_scope"
        if domain not in domains:
            domains.append(domain)
    return domains, None


def make_block_rule(
    list_name: str,
    normalized_rule: str,
    name: str,
    scope: str,
    match_kind: str,
    pattern: str,
    literal_operator: str | None = None,
) -> dict:
    rule = {
        "id": make_rule_id("block", list_name, normalized_rule),
        "name": name,
        "scope": scope,
        "matchKind": match_kind,
        "pattern": pattern,
        "isEnabled": True,
        "rank": 0,
        "action": "block",
        "note": "",
    }
    if literal_operator is not None:
        rule["literalOperator"] = literal_operator
    return rule


def make_cosmetic_rule(
    list_name: str,
    normalized_rule: str,
    selector: str,
    domains: list[str],
) -> dict:
    return {
        "id": make_rule_id("cosmetic", list_name, normalized_rule),
        "name": selector,
        "selector": selector,
        "domains": domains,
        "isEnabled": True,
        "rank": 0,
        "note": "",
    }


def parse_cosmetic_rule(list_name: str, rule: str) -> tuple[dict | None, str | None]:
    selector = ""
    domains: list[str] = []

    if rule.startswith("##"):
        selector = rule[2:].strip()
    elif "##" in rule:
        domain_prefix, selector_text = rule.split("##", 1)
        selector = selector_text.strip()
        domains, error = parse_domains(domain_prefix)
        if error:
            return None, error
    else:
        return None, None

    if not selector:
        return None, "empty_selector"
    if has_unsupported_selector_features(selector):
        return None, "unsupported_cosmetic_selector"

    normalized = f"{','.join(domains)}##{selector}"
    return make_cosmetic_rule(list_name, normalized, selector, domains), None


def parse_domain_rule(
    list_name: str,
    pattern: str,
    options: list[str],
) -> tuple[dict | None, str | None]:
    match = PURE_DOMAIN_RULE_RE.fullmatch(pattern)
    if not match:
        return None, None
    if any(option != "third-party" for option in options):
        return None, "unsupported_modifier"
    domain = match.group("domain")
    return (
        make_block_rule(
            list_name=list_name,
            normalized_rule=f"{pattern}${','.join(options)}",
            name=domain,
            scope="fqdn",
            match_kind="literal",
            pattern=domain,
            literal_operator="exact",
        ),
        None,
    )


def parse_domain_path_rule(
    list_name: str,
    pattern: str,
    options: list[str],
) -> tuple[dict | None, str | None]:
    if options:
        return None, "unsupported_modifier"

    match = DOMAIN_WITH_PATH_RE.fullmatch(pattern)
    if not match:
        return None, None

    domain = match.group("domain")
    suffix = match.group("suffix")
    if any(char in suffix for char in "*^|"):
        return None, "unsupported_url_pattern"

    regex = (
        r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^/]+\.)?"
        f"{re.escape(domain)}"
        r"(?::[0-9]+)?"
        f"{re.escape(suffix)}"
    )
    return (
        make_block_rule(
            list_name=list_name,
            normalized_rule=pattern,
            name=f"{domain}{suffix}",
            scope="url",
            match_kind="regex",
            pattern=regex,
        ),
        None,
    )


def parse_raw_regex_rule(
    list_name: str,
    rule: str,
) -> tuple[dict | None, str | None]:
    parsed = parse_raw_regex_components(rule)
    if parsed is None:
        return None, None

    pattern, options_text = parsed
    if options_text:
        return None, "unsupported_modifier"
    regex_error = regex_parse_error(pattern)
    if regex_error is not None:
        return None, regex_error

    return (
        make_block_rule(
            list_name=list_name,
            normalized_rule=rule,
            name=pattern,
            scope="url",
            match_kind="regex",
            pattern=pattern,
        ),
        None,
    )

def translate_pattern_to_regex(pattern: str) -> str | None:
    if "^" in pattern:
        return None

    body = pattern
    prefix = ""

    if body.startswith("||"):
        prefix = r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^/]+\.)?"
        body = body[2:]
    elif body.startswith("|"):
        prefix = "^"
        body = body[1:]

    suffix = ""
    if body.endswith("|"):
        body = body[:-1]
        suffix = "$"

    if "|" in body:
        return None

    pieces: list[str] = [prefix]
    for char in body:
        if char == "*":
            pieces.append(".*")
        else:
            pieces.append(re.escape(char))
    pieces.append(suffix)
    return "".join(pieces)


def parse_literal_or_translated_pattern(
    list_name: str,
    pattern: str,
    options: list[str],
) -> tuple[dict | None, str | None]:
    if options:
        return None, "unsupported_modifier"

    if not pattern:
        return None, "empty_rule"

    if all(char not in pattern for char in "*^|"):
        return (
            make_block_rule(
                list_name=list_name,
                normalized_rule=pattern,
                name=pattern,
                scope="url",
                match_kind="literal",
                pattern=pattern,
                literal_operator="contains",
            ),
            None,
        )

    translated = translate_pattern_to_regex(pattern)
    if translated is None:
        return None, "unsupported_url_pattern"

    return (
        make_block_rule(
            list_name=list_name,
            normalized_rule=pattern,
            name=pattern,
            scope="url",
            match_kind="regex",
            pattern=translated,
        ),
        None,
    )


def parse_block_rule(list_name: str, rule: str) -> tuple[dict | None, str]:
    parsed_regex, error = parse_raw_regex_rule(list_name, rule)
    if parsed_regex is not None or error is not None:
        return parsed_regex, error or ""

    pattern, options = split_pattern_and_options(rule)

    parsed, error = parse_domain_rule(list_name, pattern, options)
    if parsed is not None or error is not None:
        return parsed, error or ""

    parsed, error = parse_domain_path_rule(list_name, pattern, options)
    if parsed is not None or error is not None:
        return parsed, error or ""

    parsed, error = parse_literal_or_translated_pattern(list_name, pattern, options)
    if parsed is not None:
        return parsed, ""
    return None, error or "unsupported_rule"


def maybe_quarantine_block_rule(
    list_name: str,
    rule: str,
) -> dict | None:
    if rule not in QUARANTINED_SOURCE_RULES:
        return None

    disabled_rule = make_block_rule(
        list_name=list_name,
        normalized_rule=f"quarantined:{rule}",
        name=rule,
        scope="url",
        match_kind="literal",
        pattern=rule,
        literal_operator="contains",
    )
    disabled_rule["isEnabled"] = False
    disabled_rule["note"] = "quarantined broad generic substring rule"
    return disabled_rule


def load_rules(list_path: Path) -> list[str]:
    lines: list[str] = []
    for line in list_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[Adblock") and stripped.endswith("]"):
            continue
        if stripped.startswith("!"):
            continue
        lines.append(stripped)
    return lines


def build_summary_section(rule_count: int) -> dict:
    return {
        "inputRules": rule_count,
        "acceptedBlockRules": 0,
        "quarantinedBlockRules": 0,
        "acceptedCosmeticRules": 0,
        "duplicateRules": 0,
        "skipped": {},
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()

    try:
        list_names = validate_list_names(args.lists)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    input_dir = resolve_repo_path(args.input_dir)
    summary_output = resolve_repo_path(args.summary_output)

    missing = [
        LIST_FILES[list_name]
        for list_name in list_names
        if not (input_dir / LIST_FILES[list_name]).exists()
    ]
    if missing:
        joined = ", ".join(missing)
        print(f"missing fetched list files: {joined}", file=sys.stderr)
        return 1

    summary_lists: dict[str, dict] = {}
    total_skips: Counter[str] = Counter()

    for list_name in list_names:
        block_rules: list[dict] = []
        disabled_block_rules: list[dict] = []
        cosmetic_rules: list[dict] = []
        skip_counter: Counter[str] = Counter()
        seen_block: set[tuple] = set()
        seen_disabled_block: set[tuple] = set()
        seen_cosmetic: set[tuple] = set()

        rules = load_rules(input_dir / LIST_FILES[list_name])
        summary_lists[list_name] = build_summary_section(len(rules))

        for rule in rules:
            quarantined_rule = maybe_quarantine_block_rule(list_name, rule)
            if quarantined_rule is not None:
                signature = block_signature(quarantined_rule)
                if signature in seen_disabled_block:
                    summary_lists[list_name]["duplicateRules"] += 1
                    continue
                seen_disabled_block.add(signature)
                disabled_block_rules.append(quarantined_rule)
                summary_lists[list_name]["quarantinedBlockRules"] += 1
                continue

            if is_allowlist_rule(rule):
                skip_counter["allowlist"] += 1
                continue

            if is_advanced_rule(rule):
                skip_counter["advanced_rule"] += 1
                continue

            cosmetic_rule, cosmetic_error = parse_cosmetic_rule(list_name, rule)
            if cosmetic_rule is not None:
                signature = cosmetic_signature(cosmetic_rule)
                if signature in seen_cosmetic:
                    summary_lists[list_name]["duplicateRules"] += 1
                    continue
                seen_cosmetic.add(signature)
                cosmetic_rules.append(cosmetic_rule)
                summary_lists[list_name]["acceptedCosmeticRules"] += 1
                continue
            if cosmetic_error is not None:
                skip_counter[cosmetic_error] += 1
                continue

            block_rule, block_error = parse_block_rule(list_name, rule)
            if block_rule is not None:
                signature = block_signature(block_rule)
                if signature in seen_block:
                    summary_lists[list_name]["duplicateRules"] += 1
                    continue
                seen_block.add(signature)
                block_rules.append(block_rule)
                summary_lists[list_name]["acceptedBlockRules"] += 1
                continue
            skip_counter[block_error or "unsupported_rule"] += 1

        summary_lists[list_name]["skipped"] = dict(sorted(skip_counter.items()))
        total_skips.update(skip_counter)

        write_json(resolve_repo_path(DEFAULT_BLOCK_OUTPUTS[list_name]), block_rules)
        write_json(
            resolve_repo_path(DEFAULT_DISABLED_BLOCK_OUTPUTS[list_name]),
            disabled_block_rules,
        )
        write_json(
            resolve_repo_path(DEFAULT_COSMETIC_OUTPUTS[list_name]),
            cosmetic_rules,
        )

        print(
            "wrote "
            f"{DEFAULT_BLOCK_OUTPUTS[list_name]}, "
            f"{DEFAULT_DISABLED_BLOCK_OUTPUTS[list_name]}, "
            f"{DEFAULT_COSMETIC_OUTPUTS[list_name]}"
        )

    write_json(
        summary_output,
        {
            "generatedAt": utc_now_iso(),
            "lists": summary_lists,
            "totals": {
                "acceptedBlockRules": sum(
                    section["acceptedBlockRules"] for section in summary_lists.values()
                ),
                "quarantinedBlockRules": sum(
                    section["quarantinedBlockRules"]
                    for section in summary_lists.values()
                ),
                "acceptedCosmeticRules": sum(
                    section["acceptedCosmeticRules"] for section in summary_lists.values()
                ),
                "duplicateRules": sum(
                    section["duplicateRules"] for section in summary_lists.values()
                ),
                "skipped": dict(sorted(total_skips.items())),
            },
        },
    )
    print(f"summary: {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
