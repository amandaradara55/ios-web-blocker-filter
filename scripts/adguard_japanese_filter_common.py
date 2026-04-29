from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import uuid


SECTION_NAMES = (
    "adservers.txt",
    "adservers_firstparty.txt",
    "allowlist.txt",
    "antiadblock.txt",
    "general_elemhide.txt",
    "general_extensions.txt",
    "general_url.txt",
    "specific.txt",
)

DEFAULT_EXCLUDED_PARSE_SECTIONS = (
    "allowlist.txt",
    "antiadblock.txt",
    "general_extensions.txt",
)

DEFAULT_BASE_URL = (
    "https://raw.githubusercontent.com/"
    "AdguardTeam/AdguardFilters/master/JapaneseFilter/sections/"
)

DEFAULT_FETCH_DIR = "sources/adguard-japanese"
DEFAULT_BLOCK_OUTPUT = "dist/adguard-japanese-block-rules.json"
DEFAULT_DISABLED_BLOCK_OUTPUT = "dist/adguard-japanese-block-rules-disabled.json"
DEFAULT_COSMETIC_OUTPUT = "dist/adguard-japanese-cosmetic-rules.json"
DEFAULT_SUMMARY_OUTPUT = "dist/adguard-japanese-summary.json"

QUARANTINED_SOURCE_RULES = (
    ".com/Zen?",
    ".jp/Zen?",
)

RULE_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://github.com/amandaradara55/ios-web-blocker-filter/adguard-japanese",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repo_root() / path


def normalize_base_url(base_url: str) -> str:
    if base_url.endswith("/"):
        return base_url
    return f"{base_url}/"


def section_url(base_url: str, section_name: str) -> str:
    return urljoin(normalize_base_url(base_url), section_name)


def validate_sections(sections: list[str] | None) -> list[str]:
    if not sections:
        return list(SECTION_NAMES)

    seen: set[str] = set()
    valid: list[str] = []
    unknown = [name for name in sections if name not in SECTION_NAMES]
    if unknown:
        joined = ", ".join(sorted(set(unknown)))
        raise ValueError(f"unknown section names: {joined}")

    for name in sections:
        if name in seen:
            continue
        seen.add(name)
        valid.append(name)
    return valid
