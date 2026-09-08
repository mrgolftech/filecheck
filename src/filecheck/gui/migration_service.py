from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from filecheck.backup import read_backup_manifest
from filecheck.migration import (
    failed_report_path,
    migration_state_path,
    preflight_migration,
    remove_verified_sources,
    resume_migration,
)
from filecheck.util import read_json

from .task_runner import TaskCancelled, TaskContext


@dataclass(frozen=True)
class RemovalTargetInfo:
    backup_path: Path
    batch_id: str
    file_count: int
    total_bytes: int
    has_state: bool
    state_path: Optional[Path]
    status: str
    deleted: int
    already_absent: int
    failed: int
    pending: int
    can_resume: bool


@dataclass(frozen=True)
class RemovalPreflight:
    backup_path: Path
    batch_id: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class RemovalResult:
    backup_path: Path
    state_path: Path
    status: str
    total: int
    deleted: int
    already_absent: int
    failed: int
    pending: int
    failed_report: Optional[Path]


def _count_states(rows) -> Dict[str, int]:
    counts = {"deleted": 0, "already_absent": 0, "failed": 0, "reappeared": 0, "pending": 0}
    for row in rows:
        state = str(row.get("state", "pending"))
        if state in counts:
            counts[state] += 1
    return counts


def inspect_removal_target(value: str | Path) -> RemovalTargetInfo:
    backup_path = Path(value).expanduser().resolve()
    manifest = read_backup_manifest(backup_path)
    rows = manifest["items"]
    state_path = migration_state_path(backup_path)
    if not state_path.is_file():
        return RemovalTargetInfo(
            backup_path=backup_path,
            batch_id=str(manifest.get("batch_id", "-")),
            file_count=len(rows),
            total_bytes=sum(int(item["size"]) for item in rows),
            has_state=False,
            state_path=None,
            status="ready_for_preflight",
            deleted=0,
            already_absent=0,
            failed=0,
            pending=len(rows),
            can_resume=False,
        )

    state = read_json(state_path)
    if not isinstance(state, dict) or state.get("kind") != "filecheck-source-removal":
        raise RuntimeError(f"source-removal.json 格式无效: {state_path}")
    if state.get("batch_id") != manifest.get("batch_id"):
        raise RuntimeError("source-removal.json 与当前备份批次不匹配")
    state_rows = state.get("items")
    if not isinstance(state_rows, list) or len(state_rows) != len(rows):
        raise RuntimeError("source-removal.json 文件集合与 manifest 不一致")
    counts = _count_states(state_rows)
    failed = counts["failed"] + counts["reappeared"]
    pending = counts["pending"] + counts["failed"]
    status = str(state.get("status", "removing"))
    return RemovalTargetInfo(
        backup_path=backup_path,
        batch_id=str(manifest.get("batch_id", "-")),
        file_count=len(rows),
        total_bytes=sum(int(item["size"]) for item in rows),
        has_state=True,
        state_path=state_path,
        status=status,
        deleted=counts["deleted"],
        already_absent=counts["already_absent"],
        failed=failed,
        pending=pending,
        can_resume=pending > 0 and status != "completed",
    )


def run_removal_preflight(value: str | Path, task: TaskContext) -> RemovalPreflight:
    backup_path = Path(value).expanduser().resolve()
    state_path = migration_state_path(backup_path)
    if state_path.exists():
        raise RuntimeError("该备份已经存在源文件删除状态，请使用“继续处理”而不是重新开始。")
    task.log("正在验证备份完整性并重新计算全部源文件 SHA-256……")
    task.set_progress(None, "正在验证备份并复核源文件……")

    def progress(stage: str, current: int, total: int, path: str) -> None:
        task.raise_if_cancelled()
        ratio = current / total if total else 0.0
        task.set_progress(ratio, f"正在复核源文件：{current}/{total}")
        if current == 1 or current == total or current % 25 == 0:
            task.log(f"复核 {current}/{total}: {path}")

    summary = preflight_migration(backup_path, progress=progress)
    task.raise_if_cancelled()
    task.set_progress(1.0, "删除前安全复核通过")
    task.log("备份和全部源文件 SHA-256 复核通过；尚未删除任何源文件。")
    return RemovalPreflight(
        backup_path=backup_path,
        batch_id=str(summary.get("batch_id", "-")),
        file_count=int(summary["files"]),
        total_bytes=int(summary["bytes"]),
    )


def _result_from_state(state_path: Path, state: dict) -> RemovalResult:
    rows = state.get("items", [])
    counts = _count_states(rows)
    pending = counts["pending"] + counts["failed"]
    failed = counts["failed"] + counts["reappeared"]
    report = failed_report_path(state_path.parent)
    return RemovalResult(
        backup_path=state_path.parent,
        state_path=state_path,
        status=str(state.get("status", "removing")),
        total=int(state.get("total", len(rows))),
        deleted=counts["deleted"],
        already_absent=counts["already_absent"],
        failed=failed,
        pending=pending,
        failed_report=report if report.is_file() else None,
    )


def _removal_progress(task: TaskContext):
    def progress(stage: str, current: int, total: int, path: str) -> None:
        ratio = current / total if total else 0.0
        task.set_progress(ratio, f"正在处理源文件：{current}/{total}")
        if current == 1 or current == total or current % 25 == 0:
            task.log(f"处理 {current}/{total}: {path}")
    return progress


def run_source_removal(value: str | Path, task: TaskContext) -> RemovalResult:
    backup_path = Path(value).expanduser().resolve()
    task.log("开始源文件删除；每个文件删除前都会再次核对 SHA-256。")
    state_path, state = remove_verified_sources(
        backup_path,
        preflight=False,
        progress=_removal_progress(task),
        should_cancel=task.is_cancelled,
    )
    result = _result_from_state(state_path, state)
    if task.is_cancelled() and result.status != "completed":
        task.log(f"取消已在安全检查点生效，状态已写入: {state_path}")
        raise TaskCancelled("源文件处理已在安全检查点停止，可稍后继续")
    task.set_progress(1.0, "源文件处理完成")
    return result


def run_resume_removal(value: str | Path, task: TaskContext) -> RemovalResult:
    backup_path = Path(value).expanduser().resolve()
    state_path = migration_state_path(backup_path)
    task.log(f"正在验证备份并继续处理删除状态: {state_path}")
    state_path, state = resume_migration(
        state_path,
        progress=_removal_progress(task),
        should_cancel=task.is_cancelled,
    )
    result = _result_from_state(state_path, state)
    if task.is_cancelled() and result.status != "completed":
        task.log(f"取消已在安全检查点生效，状态已写入: {state_path}")
        raise TaskCancelled("继续处理已在安全检查点停止，可稍后再次继续")
    task.set_progress(1.0, "继续处理完成")
    return result
