from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from filecheck import cli
from filecheck.portable_everything import load_index_state
from filecheck.util import read_json, runtime_dir, write_json


@dataclass(frozen=True)
class SettingsData:
    backup_root: str
    keywords: Dict[str, List[str]]
    extensions: List[str]
    max_results_per_keyword: int
    rules_path: Path
    settings_path: Path


def settings_path() -> Path:
    return runtime_dir() / "settings.json"


def _read_runtime_settings() -> dict:
    path = settings_path()
    if not path.is_file():
        return {}
    try:
        payload = read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def current_backup_root() -> Optional[str]:
    payload = _read_runtime_settings()
    value = str(payload.get("backup_root") or "").strip()
    if value:
        return value
    try:
        state = load_index_state(required=False) or {}
    except Exception:
        state = {}
    value = str(state.get("backup_root") or "").strip()
    return value or None


def load_settings() -> SettingsData:
    rules_path = Path(cli._default_rules_path()).expanduser().resolve()
    rules = cli._load_rules(rules_path)
    keywords = {
        str(level): [str(value) for value in values]
        for level, values in rules.get("keywords", {}).items()
        if isinstance(values, list)
    }
    for level in ("high", "sensitive", "review"):
        keywords.setdefault(level, [])
    extensions = [str(value).lstrip(".") for value in rules.get("extensions", []) if str(value).strip()]
    return SettingsData(
        backup_root=current_backup_root() or "",
        keywords=keywords,
        extensions=extensions,
        max_results_per_keyword=int(rules.get("max_results_per_keyword", 100000)),
        rules_path=rules_path,
        settings_path=settings_path(),
    )


def _clean_values(values: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def save_settings(
    backup_root: str,
    keywords: Dict[str, List[str]],
    extensions: List[str],
    max_results_per_keyword: int = 100000,
) -> SettingsData:
    root_text = str(backup_root or "").strip()
    if not root_text:
        raise RuntimeError("请设置备份根目录")
    root = Path(root_text).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise RuntimeError(f"备份路径不是有效目录: {root}")

    cleaned_keywords: Dict[str, List[str]] = {}
    for level in ("high", "sensitive", "review"):
        cleaned_keywords[level] = _clean_values(list(keywords.get(level, [])))
    if not any(cleaned_keywords.values()):
        raise RuntimeError("至少需要配置一个扫描关键词")

    cleaned_extensions = [value.lower().lstrip(".") for value in _clean_values(extensions)]
    if not cleaned_extensions:
        raise RuntimeError("至少需要配置一种文件类型")

    rules_path = Path(cli._default_rules_path()).expanduser().resolve()
    write_json(
        rules_path,
        {
            "keywords": cleaned_keywords,
            "extensions": cleaned_extensions,
            "max_results_per_keyword": max(1, int(max_results_per_keyword)),
        },
    )
    write_json(
        settings_path(),
        {
            "schema_version": 1,
            "backup_root": str(root),
        },
    )
    return load_settings()
