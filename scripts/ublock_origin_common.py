from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import uuid


ROOT_LIST_FILES = {
    "ads": "filters.txt",
    "mobile": "filters-mobile.txt",
}

FLATTEN_PROFILES = {
    "ads": {
        "root": "filters.txt",
        "defines": {
            "cap_html_filtering": False,
            "env_chromium": False,
            "env_firefox": False,
            "env_mobile": False,
            "env_safari": True,
            "ext_ubol": False,
        },
    },
    "mobile-effective": {
        "root": "filters.txt",
        "defines": {
            "cap_html_filtering": False,
            "env_chromium": False,
            "env_firefox": False,
            "env_mobile": True,
            "env_safari": True,
            "ext_ubol": False,
        },
    },
    "mobile-standalone": {
        "root": "filters-mobile.txt",
        "defines": {
            "cap_html_filtering": False,
            "env_chromium": False,
            "env_firefox": False,
            "env_mobile": True,
            "env_safari": True,
            "ext_ubol": False,
        },
    },
}

DEFAULT_BASE_URL = "https://ublockorigin.github.io/uAssets/filters/"
DEFAULT_FETCH_DIR = "sources/ublock-origin"
DEFAULT_RAW_DIR = f"{DEFAULT_FETCH_DIR}/raw"
DEFAULT_FLAT_DIR = f"{DEFAULT_FETCH_DIR}/flat"

DEFAULT_ADS_DISABLED_BLOCK_OUTPUT = "dist/ublock-ads-block-rules-disabled.json"
DEFAULT_ADS_MERGED_OUTPUT = "dist/ublock-ads.json"
DEFAULT_MOBILE_DISABLED_BLOCK_OUTPUT = "dist/ublock-mobile-block-rules-disabled.json"
DEFAULT_MOBILE_MERGED_OUTPUT = "dist/ublock-mobile.json"
LEGACY_ADS_BLOCK_OUTPUT = "dist/ublock-ads-block-rules.json"
LEGACY_ADS_COSMETIC_OUTPUT = "dist/ublock-ads-cosmetic-rules.json"
LEGACY_MOBILE_BLOCK_OUTPUT = "dist/ublock-mobile-block-rules.json"
LEGACY_MOBILE_COSMETIC_OUTPUT = "dist/ublock-mobile-cosmetic-rules.json"
DEFAULT_SUMMARY_OUTPUT = "dist/ublock-origin-summary.json"

RULE_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://github.com/amandaradara55/ios-web-blocker-filter/ublock-origin",
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


def validate_root_names(names: list[str] | None) -> list[str]:
    if not names:
        return list(ROOT_LIST_FILES.keys())
    unknown = [name for name in names if name not in ROOT_LIST_FILES]
    if unknown:
        joined = ", ".join(sorted(set(unknown)))
        raise ValueError(f"unknown root list names: {joined}")
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def validate_profile_names(names: list[str] | None) -> list[str]:
    if not names:
        return list(FLATTEN_PROFILES.keys())
    unknown = [name for name in names if name not in FLATTEN_PROFILES]
    if unknown:
        joined = ", ".join(sorted(set(unknown)))
        raise ValueError(f"unknown flatten profile names: {joined}")
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered
