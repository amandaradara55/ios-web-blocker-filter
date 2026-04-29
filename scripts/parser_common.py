from __future__ import annotations

import re


WEBKIT_UNSUPPORTED_REGEX_TOKENS = (
    (r"\b", "unsupported_webkit_regex_word_boundary"),
    (r"\B", "unsupported_webkit_regex_word_boundary"),
    ("(?=", "unsupported_webkit_regex_lookaround"),
    ("(?!", "unsupported_webkit_regex_lookaround"),
    ("(?<=", "unsupported_webkit_regex_lookaround"),
    ("(?<!", "unsupported_webkit_regex_lookaround"),
    ("(?i", "unsupported_webkit_regex_inline_flag"),
    ("(?m", "unsupported_webkit_regex_inline_flag"),
    ("(?s", "unsupported_webkit_regex_inline_flag"),
    ("(?x", "unsupported_webkit_regex_inline_flag"),
    ("(?u", "unsupported_webkit_regex_inline_flag"),
    ("(?L", "unsupported_webkit_regex_inline_flag"),
    ("(?-", "unsupported_webkit_regex_inline_flag"),
    (r"\k<", "unsupported_webkit_regex_backreference"),
)

WEBKIT_UNSUPPORTED_QUANTIFIER_RE = re.compile(r"(?<!\\)(?:\\\\)*\{(?:\d+(?:,\d*)?)\}")
UNICODE_PROPERTY_ESCAPE_RE = re.compile(r"\\[pP]\{[^}]+\}")


def parse_raw_regex_components(rule: str) -> tuple[str, str | None] | None:
    if not rule.startswith("/"):
        return None

    escaped = False
    for index in range(1, len(rule)):
        char = rule[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char != "/":
            continue

        if index == len(rule) - 1:
            return rule[1:index], None
        if rule[index + 1] == "$":
            return rule[1:index], rule[index + 2 :]
        return None

    return None


def regex_parse_error(pattern: str) -> str | None:
    if "|" in pattern:
        return "unsupported_regex_disjunction"

    for token, error in WEBKIT_UNSUPPORTED_REGEX_TOKENS:
        if token in pattern:
            return error

    if WEBKIT_UNSUPPORTED_QUANTIFIER_RE.search(pattern):
        return "unsupported_webkit_regex_brace_quantifier"

    sanitized = UNICODE_PROPERTY_ESCAPE_RE.sub("A", pattern)

    try:
        re.compile(sanitized)
    except re.error:
        return "invalid_regex"

    return None


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
