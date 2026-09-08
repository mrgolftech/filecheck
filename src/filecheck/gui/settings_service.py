from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from filecheck import cli
from filecheck.portable_everything import load_index_state
from filecheck.util import read_json, runtime_dir, write_json


@dataclass(frozen=True)
class SettingsData:
    backup_roots: List[str]
    keywords: Dict[str, List[str]]
    extensions: List[str]
    max_results_per_keyword: int
    appearance: str
    rules_path: Path
    settings_path: Path

    @property
    def backup_root(self) -> str:
        return self.backup_roots[0] if self.backup_roots else ""


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


def _normalize_backup_roots(values: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        root = Path(text).expanduser().resolve()
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(str(root))
    return result


def current_backup_roots() -> List[str]:
    payload = _read_runtime_settings()
    configured = payload.get("backup_roots")
    if isinstance(configured, list):
        roots = _normalize_backup_roots([str(value) for value in configured])
        if roots:
            return roots
    legacy = str(payload.get("backup_root") or "").strip()
    if legacy:
        return _normalize_backup_roots([legacy])

    try:
        state = load_index_state(required=False) or {}
    except Exception:
        state = {}
    indexed = state.get("backup_roots")
    if isinstance(indexed, list):
        roots = _normalize_backup_roots([str(value) for value in indexed])
        if roots:
            return roots
    legacy = str(state.get("backup_root") or "").strip()
    return _normalize_backup_roots([legacy]) if legacy else []


def current_backup_root() -> Optional[str]:
    roots = current_backup_roots()
    return roots[0] if roots else None


def current_appearance() -> str:
    value = str(_read_runtime_settings().get("appearance") or "light").strip().lower()
    return value if value in ("light", "dark") else "light"


def save_appearance(appearance: str) -> str:
    mode = str(appearance or "light").strip().lower()
    if mode not in ("light", "dark"):
        raise RuntimeError("界面主题只能选择浅色或暗色")
    payload = _read_runtime_settings()
    roots = current_backup_roots()
    payload.update(
        {
            "schema_version": 2,
            "backup_roots": roots,
            "backup_root": roots[0] if roots else "",
            "appearance": mode,
        }
    )
    write_json(settings_path(), payload)
    return mode


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
    extensions = _normalize_extensions([str(value) for value in rules.get("extensions", [])])
    return SettingsData(
        backup_roots=current_backup_roots(),
        keywords=keywords,
        extensions=extensions,
        max_results_per_keyword=int(rules.get("max_results_per_keyword", 100000)),
        appearance=current_appearance(),
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


def _normalize_extensions(values: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for raw in values:
        value = str(raw).strip().lower().lstrip(".")
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _split_backup_roots(value: Union[str, List[str]]) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    normalized = str(value or "").replace("；", "\n").replace(";", "\n")
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def save_settings(
    backup_roots: Union[str, List[str]],
    keywords: Dict[str, List[str]],
    extensions: List[str],
    max_results_per_keyword: int = 100000,
    appearance: Optional[str] = None,
) -> SettingsData:
    roots = _normalize_backup_roots(_split_backup_roots(backup_roots))
    if not roots:
        raise RuntimeError("请至少设置一个备份根目录")
    for value in roots:
        root = Path(value)
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise RuntimeError(f"备份路径不是有效目录: {root}")

    cleaned_keywords: Dict[str, List[str]] = {}
    for level in ("high", "sensitive", "review"):
        cleaned_keywords[level] = _clean_values(list(keywords.get(level, [])))
    if not any(cleaned_keywords.values()):
        raise RuntimeError("至少需要配置一个扫描关键词")

    cleaned_extensions = _normalize_extensions(extensions)
    if not cleaned_extensions:
        raise RuntimeError("至少需要配置一种文件类型")

    mode = current_appearance() if appearance is None else str(appearance).strip().lower()
    if mode not in ("light", "dark"):
        raise RuntimeError("界面主题只能选择浅色或暗色")

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
            "schema_version": 2,
            "backup_roots": roots,
            "backup_root": roots[0],
            "appearance": mode,
        },
    )
    return load_settings()
