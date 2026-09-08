from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from filecheck import cli, db_persistence
from filecheck.everything import FILECHECK_INSTANCE, scan_keywords
from filecheck.portable_everything import load_index_state
from filecheck.util import now_iso, write_json

from .task_runner import TaskContext


@dataclass(frozen=True)
class ScanContextInfo:
    rules_path: Path
    keywords: Dict[str, List[str]]
    extensions: List[str]
    selected_roots: List[str]
    excluded_roots: List[str]
    index_mode: str


@dataclass(frozen=True)
class ScanRequest:
    path_prefix: Optional[str] = None
    match_path: bool = False


@dataclass(frozen=True)
class ScanResult:
    json_path: Path
    csv_path: Path
    payload: Dict[str, Any]
    counts: Dict[str, int]
    total_size: int
    inaccessible_count: int

    @property
    def items(self) -> List[Dict[str, Any]]:
        return list(self.payload.get("items", []))


def load_context() -> ScanContextInfo:
    rules_path = Path(cli._default_rules_path()).expanduser().resolve()
    rules = cli._load_rules(rules_path)
    state = load_index_state(required=False) or {}
    keywords = {
        str(level): [str(value) for value in values]
        for level, values in rules.get("keywords", {}).items()
        if isinstance(values, list)
    }
    extensions = [str(value).lstrip(".") for value in rules.get("extensions", []) if str(value).strip()]
    return ScanContextInfo(
        rules_path=rules_path,
        keywords=keywords,
        extensions=extensions,
        selected_roots=[str(value) for value in state.get("selected_roots", [])],
        excluded_roots=[str(value) for value in state.get("excluded_roots", [])],
        index_mode=str(state.get("index_mode", "未建立索引")),
    )


def _path_is_under(candidate: str, root: str) -> bool:
    try:
        child = os.path.normcase(os.path.abspath(os.path.expanduser(candidate)))
        parent = os.path.normcase(os.path.abspath(os.path.expanduser(root)))
        return os.path.commonpath([child, parent]) == parent
    except (OSError, ValueError):
        return False


def _validate_scope(path_prefix: Optional[str], selected_roots: List[str]) -> Optional[str]:
    if not path_prefix or not path_prefix.strip():
        return None
    path = str(Path(path_prefix).expanduser().resolve())
    if not Path(path).is_dir():
        raise RuntimeError(f"扫描目录不存在或不可访问: {path}")
    if selected_roots and not any(_path_is_under(path, root) for root in selected_roots):
        joined = "、".join(selected_roots)
        raise RuntimeError(f"所选目录不在 FileCheck 已索引范围内。当前索引范围: {joined}")
    return path


def run_scan(request: ScanRequest, task: TaskContext) -> ScanResult:
    task.log("正在读取扫描规则和专用索引状态……")
    rules_path = Path(cli._default_rules_path()).expanduser().resolve()
    rules = cli._load_rules(rules_path)
    state = load_index_state(required=True)
    task.raise_if_cancelled()

    selected_roots = [str(value) for value in state.get("selected_roots", [])]
    exclusions = [str(value) for value in state.get("excluded_roots", [])]
    scope = _validate_scope(request.path_prefix, selected_roots)

    task.log("索引范围: " + ("、".join(selected_roots) if selected_roots else "未记录"))
    if scope:
        task.log(f"本次扫描范围: {scope}")
    else:
        task.log("本次扫描范围: 全部已索引目录")
    task.log(f"规则文件: {rules_path}")
    task.set_progress(None, "正在连接 FileCheck 专用 Everything 实例……")

    status = db_persistence.ensure_instance()
    task.raise_if_cancelled()
    task.log(f"Everything {status.everything_version} / ES {status.es_version}")
    task.set_progress(None, "正在按关键词查询专用索引……")

    items = scan_keywords(
        rules["keywords"],
        rules["extensions"],
        max_results_per_keyword=int(rules.get("max_results_per_keyword", 100000)),
        match_path=bool(request.match_path),
        path_prefix=scope,
        instance=FILECHECK_INSTANCE,
        exclude_roots=exclusions,
    )
    task.raise_if_cancelled()
    task.log(f"关键词查询完成，共发现 {len(items)} 个候选文件。")
    task.set_progress(0.85, "正在生成 JSON / CSV 扫描结果……")

    output = Path(cli._default_scan_output())
    payload: Dict[str, Any] = {
        "schema_version": 1,
        "created_at": now_iso(),
        "engine": "everything-1.4-portable",
        "instance": FILECHECK_INSTANCE,
        "everything_version": status.everything_version,
        "selected_roots": selected_roots,
        "excluded_roots": exclusions,
        "match_path": bool(request.match_path),
        "path_filter": scope,
        "rules": cli._rules_metadata(rules_path),
        "items": items,
    }
    write_json(output, payload)
    csv_path = cli._write_scan_csv(output, items)

    counts = Counter(str(item.get("severity", "review")) for item in items)
    total_size = sum(int(item.get("size") or 0) for item in items)
    inaccessible_count = sum(1 for item in items if not item.get("accessible", False))
    task.log(f"扫描 JSON: {output.resolve()}")
    task.log(f"人工核对 CSV: {csv_path.resolve()}")
    task.set_progress(1.0, "扫描完成")

    return ScanResult(
        json_path=output.resolve(),
        csv_path=csv_path.resolve(),
        payload=payload,
        counts={
            "total": len(items),
            "high": counts.get("high", 0),
            "sensitive": counts.get("sensitive", 0),
            "review": counts.get("review", 0),
        },
        total_size=total_size,
        inaccessible_count=inaccessible_count,
    )
