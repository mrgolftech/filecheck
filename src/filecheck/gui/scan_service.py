from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from filecheck import cli, db_persistence
from filecheck.everything import FILECHECK_INSTANCE, scan_keywords
from filecheck.portable_everything import load_index_state
from filecheck.scan_guard import filter_protected_backup_items
from filecheck.util import now_iso, program_dir, write_json

from .settings_service import current_backup_root
from .task_runner import TaskContext


@dataclass(frozen=True)
class ScanContextInfo:
    rules_path: Path
    keywords: Dict[str, List[str]]
    extensions: List[str]
    selected_roots: List[str]
    excluded_roots: List[str]
    index_mode: str
    backup_root: str


@dataclass(frozen=True)
class ScanRequest:
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
    exclusions = [str(value) for value in state.get("excluded_roots", [])]
    backup_root = current_backup_root() or ""
    if backup_root and backup_root not in exclusions:
        exclusions.append(backup_root)
    return ScanContextInfo(
        rules_path=rules_path,
        keywords=keywords,
        extensions=extensions,
        selected_roots=[str(value) for value in state.get("selected_roots", [])],
        excluded_roots=exclusions,
        index_mode=str(state.get("index_mode", "未建立索引")),
        backup_root=backup_root,
    )


def run_scan(request: ScanRequest, task: TaskContext) -> ScanResult:
    task.log("正在读取扫描规则和专用索引状态……")
    rules_path = Path(cli._default_rules_path()).expanduser().resolve()
    rules = cli._load_rules(rules_path)
    state = load_index_state(required=True)
    backup_root = current_backup_root()
    if not backup_root:
        raise RuntimeError("尚未在“设置”中配置备份目录，请先完成设置后再扫描")
    task.raise_if_cancelled()

    selected_roots = [str(value) for value in state.get("selected_roots", [])]
    if not selected_roots:
        raise RuntimeError("尚未建立 FileCheck 专用索引，请先选择磁盘并创建索引")
    exclusions = [str(value) for value in state.get("excluded_roots", [])]
    for extra in (str(program_dir()), backup_root):
        if extra and extra not in exclusions:
            exclusions.append(extra)

    task.log("索引范围: " + "、".join(selected_roots))
    task.log("本次扫描范围: 全部已索引磁盘")
    task.log(f"当前备份目录排除: {backup_root}")
    task.log("历史 FileCheck 备份即使已搬移或更换备份根目录，也会在候选结果阶段自动识别并排除。")
    task.log(f"规则文件: {rules_path}")
    task.set_progress(None, "正在连接 FileCheck 专用 Everything 实例……")

    status = db_persistence.ensure_instance()
    task.raise_if_cancelled()
    task.log(f"Everything {status.everything_version} / ES {status.es_version}")
    task.set_progress(None, "正在按关键词查询专用索引……")

    raw_items = list(
        scan_keywords(
            rules["keywords"],
            rules["extensions"],
            max_results_per_keyword=int(rules.get("max_results_per_keyword", 100000)),
            match_path=bool(request.match_path),
            path_prefix=None,
            instance=FILECHECK_INSTANCE,
            exclude_roots=exclusions,
        )
    )
    task.raise_if_cancelled()
    items, protected_batches = filter_protected_backup_items(raw_items)
    excluded_backup_items = len(raw_items) - len(items)
    task.log(f"关键词查询完成，共发现 {len(raw_items)} 个原始候选文件。")
    if excluded_backup_items:
        task.log(
            f"已自动排除 {excluded_backup_items} 个位于历史 FileCheck 备份中的候选文件，"
            f"涉及 {len(protected_batches)} 个备份批次。"
        )
        for batch_path in protected_batches[:5]:
            task.log(f"保护的历史备份: {batch_path}")
        if len(protected_batches) > 5:
            task.log(f"另有 {len(protected_batches) - 5} 个历史备份批次已保护。")
    task.log(f"最终保留 {len(items)} 个候选文件。")
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
        "protected_backup_batches": protected_batches,
        "excluded_backup_items": excluded_backup_items,
        "index_updated_at": state.get("updated_at"),
        "backup_root": backup_root,
        "match_path": bool(request.match_path),
        "path_filter": None,
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
