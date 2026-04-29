from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import uuid


LIST_FILES = {
    "easylist": "easylist.txt",
    "easyprivacy": "easyprivacy.txt",
}

DEFAULT_BASE_URL = "https://easylist.to/easylist/"
DEFAULT_FETCH_DIR = "sources/easylist"

DEFAULT_BLOCK_OUTPUTS = {
    "easylist": "dist/easylist-block-rules.json",
    "easyprivacy": "dist/easyprivacy-block-rules.json",
}

DEFAULT_DISABLED_BLOCK_OUTPUTS = {
    "easylist": "dist/easylist-block-rules-disabled.json",
    "easyprivacy": "dist/easyprivacy-block-rules-disabled.json",
}

DEFAULT_COSMETIC_OUTPUTS = {
    "easylist": "dist/easylist-cosmetic-rules.json",
    "easyprivacy": "dist/easyprivacy-cosmetic-rules.json",
}

DEFAULT_SUMMARY_OUTPUT = "dist/easylist-summary.json"

QUARANTINED_SOURCE_RULES: tuple[str, ...] = ()

RULE_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://github.com/amandaradara55/ios-web-blocker-filter/easylist",
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


def list_url(base_url: str, filename: str) -> str:
    return urljoin(normalize_base_url(base_url), filename)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(repo_root()))
    except ValueError:
        return str(path)


def validate_list_names(names: list[str] | None) -> list[str]:
    if not names:
        return list(LIST_FILES.keys())
    unknown = [name for name in names if name not in LIST_FILES]
    if unknown:
        joined = ", ".join(sorted(set(unknown)))
        raise ValueError(f"unknown EasyList names: {joined}")
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered
