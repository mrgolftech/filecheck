from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from filecheck import backup

from .task_runner import TaskCancelled, TaskContext


_ALLOWED_CONFLICTS = {"skip", "rename", "overwrite"}


@dataclass(frozen=True)
class RestoreTargetInfo:
    backup_path: Path
    batch_id: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class RestorePreflight:
    backup_path: Path
    batch_id: str
    conflict: str
    file_count: int
    total_bytes: int
    conflicts: int
    missing_targets: int
    expected_restored: int
    expected_skipped: int


@dataclass(frozen=True)
class RestoreResult:
    backup_path: Path
    conflict: str
    file_count: int
    restored: int
    skipped: int
    elapsed_seconds: float


def _validate_conflict(value: str) -> str:
    conflict = str(value or "").strip().lower()
    if conflict not in _ALLOWED_CONFLICTS:
        raise RuntimeError(f"未知恢复冲突策略: {value}")
    return conflict


def _target_exists(path: Path) -> bool:
    try:
        return path.exists() or path.is_symlink()
    except OSError:
        return True


def inspect_restore_target(value: str | Path) -> RestoreTargetInfo:
    backup_path = Path(value).expanduser().resolve()
    manifest = backup.read_backup_manifest(backup_path)
    items = manifest["items"]
    return RestoreTargetInfo(
        backup_path=backup_path,
        batch_id=str(manifest.get("batch_id", "-")),
        file_count=len(items),
        total_bytes=sum(int(item["size"]) for item in items),
    )


def run_restore_preflight(value: str | Path, conflict: str, task: TaskContext) -> RestorePreflight:
    backup_path = Path(value).expanduser().resolve()
    mode = _validate_conflict(conflict)
    task.log("正在全量验证备份，并检查原始恢复路径和文件冲突……")
    task.set_progress(0.0, "正在逐文件验证备份 SHA-256……")

    def progress(stage: str, current: int, total: int, path: str) -> None:
        task.raise_if_cancelled()
        ratio = current / total if total else 0.0
        task.set_progress(0.75 * ratio, f"正在验证备份：{current}/{total}")
        if current == 1 or current == total or current % 25 == 0:
            task.log(f"验证 {current}/{total}: {path}")

    manifest = backup.verify_backup(backup_path, progress=progress)
    task.raise_if_cancelled()
    items = manifest["items"]
    backup._preflight_restore_targets(items)

    task.set_progress(0.85, "正在检查原始路径冲突……")
    conflicts = sum(1 for item in items if _target_exists(Path(str(item["source_path"]))))
    missing = len(items) - conflicts
    if mode == "skip":
        expected_restored = missing
        expected_skipped = conflicts
    else:
        expected_restored = len(items)
        expected_skipped = 0

    task.log(f"恢复批次: {manifest.get('batch_id', '-')}")
    task.log(f"文件总数: {len(items)}；目标已存在: {conflicts}；目标不存在: {missing}")
    labels: Dict[str, str] = {
        "skip": "跳过已有文件，绝不覆盖",
        "rename": "已有文件保留，恢复副本使用新文件名",
        "overwrite": "已有文件将被备份内容覆盖",
    }
    task.log(f"冲突策略: {labels[mode]}")
    task.set_progress(1.0, "恢复预检通过")
    return RestorePreflight(
        backup_path=backup_path,
        batch_id=str(manifest.get("batch_id", "-")),
        conflict=mode,
        file_count=len(items),
        total_bytes=sum(int(item["size"]) for item in items),
        conflicts=conflicts,
        missing_targets=missing,
        expected_restored=expected_restored,
        expected_skipped=expected_skipped,
    )


def run_restore(value: str | Path, conflict: str, task: TaskContext) -> RestoreResult:
    backup_path = Path(value).expanduser().resolve()
    mode = _validate_conflict(conflict)
    manifest = backup.read_backup_manifest(backup_path)
    file_count = len(manifest["items"])

    task.log("正式恢复开始。核心会在写入任何目标文件前再次验证整个备份。")
    task.set_progress(0.0, "正在再次验证备份完整性……")
    last_reported = {"verify": 0, "restore": 0}

    def progress(stage: str, current: int, total: int, path: str) -> None:
        total_safe = max(1, int(total))
        ratio = max(0.0, min(1.0, float(current) / float(total_safe)))
        if stage == "verify":
            value = 0.45 * ratio
            label = f"正式恢复前再次验证备份：{current}/{total}"
            if task.is_cancelled():
                raise TaskCancelled("恢复已在写入任何目标文件之前取消")
        else:
            value = 0.45 + 0.55 * ratio
            label = f"正在恢复文件：{current}/{total}"
        task.set_progress(value, label)

        previous = last_reported.get(stage, 0)
        if current == 1 or current == total or current - previous >= 25:
            last_reported[stage] = current
            task.log(f"{label}  {path}")

        if stage == "restore" and task.is_cancelled():
            raise TaskCancelled("恢复已在当前文件完成最终校验后的安全点停止；已完成项不会回滚")

    started = time.perf_counter()
    results = backup.restore_backup(backup_path, conflict=mode, progress=progress)
    elapsed = max(0.0, time.perf_counter() - started)
    restored = sum(1 for row in results if row.get("state") == "restored")
    skipped = sum(1 for row in results if row.get("state") == "skipped")
    task.log(f"恢复完成：restored={restored}, skipped={skipped}")
    task.set_progress(1.0, "恢复完成并通过最终 SHA-256 校验")
    return RestoreResult(
        backup_path=backup_path,
        conflict=mode,
        file_count=file_count,
        restored=restored,
        skipped=skipped,
        elapsed_seconds=elapsed,
    )
