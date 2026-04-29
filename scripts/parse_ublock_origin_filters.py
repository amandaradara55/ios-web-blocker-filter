#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections import Counter
from pathlib import Path

from ublock_origin_common import (
    DEFAULT_ADS_BLOCK_OUTPUT,
    DEFAULT_ADS_COSMETIC_OUTPUT,
    DEFAULT_ADS_DISABLED_BLOCK_OUTPUT,
    DEFAULT_FLAT_DIR,
    DEFAULT_MOBILE_BLOCK_OUTPUT,
    DEFAULT_MOBILE_COSMETIC_OUTPUT,
    DEFAULT_MOBILE_DISABLED_BLOCK_OUTPUT,
    DEFAULT_SUMMARY_OUTPUT,
    RULE_NAMESPACE,
    display_path,
    resolve_repo_path,
    utc_now_iso,
)


DOMAIN_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PURE_DOMAIN_RULE_RE = re.compile(
    r"^\|\|(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})\^?$"
)
DOMAIN_WITH_PATH_RE = re.compile(
    r"^\|\|(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?P<suffix>/.+)$"
)
RAW_REGEX_RULE_RE = re.compile(r"^/(.*)/(?:\$(?P<options>.+))?$")

ALLOWLIST_MARKERS = ("@@", "#@#", "#@?#", "#@$#", "#@%#")
ADVANCED_MARKERS = ("#?#", "#$#", "#%#", "$$")
UNSUPPORTED_SELECTOR_TOKENS = (
    ":has(",
    ":has-text(",
    ":contains(",
    ":matches-css",
    ":matches-attr(",
    ":matches-media(",
    ":matches-path(",
    ":matches-property(",
    ":min-text-length(",
    ":others(",
    ":remove(",
    ":remove-",
    ":style(",
    ":upward(",
    ":watch-attr(",
    ":xpath(",
    "[-ext-",
    "xpath(",
)

QUARANTINED_SOURCE_RULES = (
    ".com/Zen?",
    ".jp/Zen?",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse flattened uBlock Origin lists into JSON rules."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_FLAT_DIR,
        help="Directory containing flattened uBlock Origin files.",
    )
    parser.add_argument(
        "--ads-input",
        default="ads.txt",
        help="Flattened ads input filename.",
    )
    parser.add_argument(
        "--mobile-effective-input",
        default="mobile-effective.txt",
        help="Flattened mobile-effective input filename.",
    )
    parser.add_argument(
        "--ads-block-output",
        default=DEFAULT_ADS_BLOCK_OUTPUT,
        help="Output JSON path for ads block rules.",
    )
    parser.add_argument(
        "--ads-disabled-block-output",
        default=DEFAULT_ADS_DISABLED_BLOCK_OUTPUT,
        help="Output JSON path for ads disabled block rules.",
    )
    parser.add_argument(
        "--ads-cosmetic-output",
        default=DEFAULT_ADS_COSMETIC_OUTPUT,
        help="Output JSON path for ads cosmetic rules.",
    )
    parser.add_argument(
        "--mobile-block-output",
        default=DEFAULT_MOBILE_BLOCK_OUTPUT,
        help="Output JSON path for mobile-only block rules.",
    )
    parser.add_argument(
        "--mobile-disabled-block-output",
        default=DEFAULT_MOBILE_DISABLED_BLOCK_OUTPUT,
        help="Output JSON path for mobile-only disabled block rules.",
    )
    parser.add_argument(
        "--mobile-cosmetic-output",
        default=DEFAULT_MOBILE_COSMETIC_OUTPUT,
        help="Output JSON path for mobile-only cosmetic rules.",
    )
    parser.add_argument(
        "--summary-output",
        default=DEFAULT_SUMMARY_OUTPUT,
        help="Output JSON path for parse summary.",
    )
    return parser.parse_args()


def make_rule_id(list_name: str, kind: str, normalized_rule: str) -> str:
    seed = f"{list_name}:{kind}:{normalized_rule}"
    return str(uuid.uuid5(RULE_NAMESPACE, seed))


def split_pattern_and_options(rule: str) -> tuple[str, list[str]]:
    if "$" not in rule:
        return rule, []
    pattern, options_text = rule.split("$", 1)
    options = [token.strip() for token in options_text.split(",") if token.strip()]
    return pattern, options


def has_unsupported_selector_features(selector: str) -> bool:
    return any(token in selector for token in UNSUPPORTED_SELECTOR_TOKENS)


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
        "id": make_rule_id(list_name, "block", normalized_rule),
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
        "id": make_rule_id(list_name, "cosmetic", normalized_rule),
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
    match = RAW_REGEX_RULE_RE.fullmatch(rule)
    if not match:
        return None, None

    pattern = match.group(1)
    options_text = match.group("options")
    if options_text:
        return None, "unsupported_modifier"
    if "|" in pattern:
        return None, "unsupported_regex_disjunction"
    try:
        re.compile(pattern)
    except re.error:
        return None, "invalid_regex"

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
    parsed, error = parse_raw_regex_rule(list_name, rule)
    if parsed is not None or error is not None:
        return parsed, error or ""

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


def maybe_quarantine_block_rule(list_name: str, rule: str) -> dict | None:
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


def load_rules(path: Path) -> list[str]:
    rules: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("!"):
            continue
        rules.append(stripped)
    return rules


def block_signature(rule: dict) -> tuple:
    return (
        rule["scope"],
        rule["matchKind"],
        rule["pattern"],
        rule.get("literalOperator"),
        rule["action"],
        rule["isEnabled"],
    )


def cosmetic_signature(rule: dict) -> tuple:
    return (
        rule["selector"],
        tuple(rule["domains"]),
        rule["isEnabled"],
    )


def parse_flat_rules(list_name: str, path: Path) -> dict:
    rules = load_rules(path)
    summary = {
        "inputRules": len(rules),
        "acceptedBlockRules": 0,
        "acceptedCosmeticRules": 0,
        "quarantinedBlockRules": 0,
        "duplicateRules": 0,
        "skipped": {},
    }
    skip_counter: Counter[str] = Counter()

    block_rules: list[dict] = []
    disabled_block_rules: list[dict] = []
    cosmetic_rules: list[dict] = []

    seen_block: set[tuple] = set()
    seen_disabled_block: set[tuple] = set()
    seen_cosmetic: set[tuple] = set()

    for rule in rules:
        quarantined = maybe_quarantine_block_rule(list_name, rule)
        if quarantined is not None:
            signature = block_signature(quarantined)
            if signature in seen_disabled_block:
                summary["duplicateRules"] += 1
                continue
            seen_disabled_block.add(signature)
            disabled_block_rules.append(quarantined)
            summary["quarantinedBlockRules"] += 1
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
                summary["duplicateRules"] += 1
                continue
            seen_cosmetic.add(signature)
            cosmetic_rules.append(cosmetic_rule)
            summary["acceptedCosmeticRules"] += 1
            continue
        if cosmetic_error is not None:
            skip_counter[cosmetic_error] += 1
            continue

        block_rule, block_error = parse_block_rule(list_name, rule)
        if block_rule is not None:
            signature = block_signature(block_rule)
            if signature in seen_block:
                summary["duplicateRules"] += 1
                continue
            seen_block.add(signature)
            block_rules.append(block_rule)
            summary["acceptedBlockRules"] += 1
            continue

        skip_counter[block_error or "unsupported_rule"] += 1

    summary["skipped"] = dict(sorted(skip_counter.items()))
    return {
        "blockRules": block_rules,
        "disabledBlockRules": disabled_block_rules,
        "cosmeticRules": cosmetic_rules,
        "summary": summary,
    }


def filter_mobile_delta(mobile_rules: list[dict], ads_signatures: set[tuple], signature_fn) -> list[dict]:
    delta: list[dict] = []
    for rule in mobile_rules:
        if signature_fn(rule) in ads_signatures:
            continue
        delta.append(rule)
    return delta


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def summary_input_dir_label(input_dir: Path, input_dir_arg: str) -> str:
    if Path(input_dir_arg).is_absolute():
        return DEFAULT_FLAT_DIR
    return display_path(input_dir)


def main() -> int:
    args = parse_args()

    input_dir = resolve_repo_path(args.input_dir)
    ads_input = input_dir / args.ads_input
    mobile_effective_input = input_dir / args.mobile_effective_input

    required = [ads_input, mobile_effective_input]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print(f"missing flattened input files: {', '.join(missing)}", file=sys.stderr)
        return 1

    ads_result = parse_flat_rules("ublock-ads", ads_input)
    mobile_effective_result = parse_flat_rules("ublock-mobile", mobile_effective_input)

    ads_block_signatures = {block_signature(rule) for rule in ads_result["blockRules"]}
    ads_disabled_signatures = {
        block_signature(rule) for rule in ads_result["disabledBlockRules"]
    }
    ads_cosmetic_signatures = {
        cosmetic_signature(rule) for rule in ads_result["cosmeticRules"]
    }

    mobile_block_rules = filter_mobile_delta(
        mobile_effective_result["blockRules"],
        ads_block_signatures,
        block_signature,
    )
    mobile_disabled_rules = filter_mobile_delta(
        mobile_effective_result["disabledBlockRules"],
        ads_disabled_signatures,
        block_signature,
    )
    mobile_cosmetic_rules = filter_mobile_delta(
        mobile_effective_result["cosmeticRules"],
        ads_cosmetic_signatures,
        cosmetic_signature,
    )

    ads_block_output = resolve_repo_path(args.ads_block_output)
    ads_disabled_block_output = resolve_repo_path(args.ads_disabled_block_output)
    ads_cosmetic_output = resolve_repo_path(args.ads_cosmetic_output)
    mobile_block_output = resolve_repo_path(args.mobile_block_output)
    mobile_disabled_block_output = resolve_repo_path(args.mobile_disabled_block_output)
    mobile_cosmetic_output = resolve_repo_path(args.mobile_cosmetic_output)
    summary_output = resolve_repo_path(args.summary_output)

    write_json(ads_block_output, ads_result["blockRules"])
    write_json(ads_disabled_block_output, ads_result["disabledBlockRules"])
    write_json(ads_cosmetic_output, ads_result["cosmeticRules"])
    write_json(mobile_block_output, mobile_block_rules)
    write_json(mobile_disabled_block_output, mobile_disabled_rules)
    write_json(mobile_cosmetic_output, mobile_cosmetic_rules)
    write_json(
        summary_output,
        {
            "generatedAt": utc_now_iso(),
            "inputDir": summary_input_dir_label(input_dir, args.input_dir),
            "profiles": {
                "ads": ads_result["summary"],
                "mobileEffective": mobile_effective_result["summary"],
                "mobileDelta": {
                    "blockRules": len(mobile_block_rules),
                    "disabledBlockRules": len(mobile_disabled_rules),
                    "cosmeticRules": len(mobile_cosmetic_rules),
                },
            },
        },
    )

    print(f"ads block rules: {len(ads_result['blockRules'])} -> {ads_block_output}")
    print(
        f"ads disabled block rules: {len(ads_result['disabledBlockRules'])} -> {ads_disabled_block_output}"
    )
    print(f"ads cosmetic rules: {len(ads_result['cosmeticRules'])} -> {ads_cosmetic_output}")
    print(f"mobile block rules: {len(mobile_block_rules)} -> {mobile_block_output}")
    print(
        "mobile disabled block rules: "
        f"{len(mobile_disabled_rules)} -> {mobile_disabled_block_output}"
    )
    print(
        f"mobile cosmetic rules: {len(mobile_cosmetic_rules)} -> {mobile_cosmetic_output}"
    )
    print(f"summary: {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
