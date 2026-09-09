from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from filecheck import cli
from filecheck.util import read_json, runtime_dir, write_json


@dataclass(frozen=True)
class SettingsData:
    backup_root: str
    keywords: Dict[str, List[str]]
    extensions: List[str]
    max_results_per_keyword: int
    appearance: str
    rules_path: Path
    settings_path: Path

    @property
    def backup_roots(self) -> List[str]:
        """Compatibility view for services written during the GUI branch.

        FileCheck has exactly one configured backup root.  Returning a
        singleton list keeps older call sites harmless while preserving that
        invariant.
        """
        return [self.backup_root] if self.backup_root else []


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


def _normalize_backup_root(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return str(Path(text).expanduser().resolve())


def current_backup_root() -> Optional[str]:
    payload = _read_runtime_settings()
    value = str(payload.get("backup_root") or "").strip()
    if value:
        return _normalize_backup_root(value)

    # Compatibility with the brief development build that stored multiple
    # roots.  Migrate deterministically by accepting the first non-empty entry
    # only; the product model remains a single backup root.
    configured = payload.get("backup_roots")
    if isinstance(configured, list):
        for item in configured:
            value = str(item or "").strip()
            if value:
                return _normalize_backup_root(value)
    return None


def current_backup_roots() -> List[str]:
    """Compatibility helper: always returns zero or one configured root."""
    root = current_backup_root()
    return [root] if root else []


def current_appearance() -> str:
    value = str(_read_runtime_settings().get("appearance") or "light").strip().lower()
    return value if value in ("light", "dark") else "light"


def save_appearance(appearance: str) -> str:
    mode = str(appearance or "light").strip().lower()
    if mode not in ("light", "dark"):
        raise RuntimeError("界面主题只能选择浅色或暗色")
    payload = _read_runtime_settings()
    root = current_backup_root() or ""
    write_json(
        settings_path(),
        {
            "schema_version": 3,
            "backup_root": root,
            "appearance": mode,
        },
    )
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
        backup_root=current_backup_root() or "",
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


def _coerce_single_backup_root(value: Union[str, List[str]]) -> str:
    if isinstance(value, list):
        non_empty = [str(item).strip() for item in value if str(item).strip()]
        if len(non_empty) > 1:
            raise RuntimeError("FileCheck 只支持一个统一备份根目录")
        return non_empty[0] if non_empty else ""
    text = str(value or "").strip()
    if "\n" in text or "\r" in text or ";" in text or "；" in text:
        raise RuntimeError("FileCheck 只支持一个统一备份根目录")
    return text


def save_settings(
    backup_root: Union[str, List[str]],
    keywords: Dict[str, List[str]],
    extensions: List[str],
    max_results_per_keyword: int = 100000,
    appearance: Optional[str] = None,
) -> SettingsData:
    root_text = _coerce_single_backup_root(backup_root)
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
            "schema_version": 3,
            "backup_root": str(root),
            "appearance": mode,
        },
    )
    return load_settings()
