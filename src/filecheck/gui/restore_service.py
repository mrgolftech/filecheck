from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from filecheck import backup
from filecheck.util import sha256_file, write_text

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
    skipped_error: int
    skipped_report: Optional[Path]
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
        task.raise_if_cancelled()
        if current == 1 or current == total or current % 25 == 0:
            task.log(f"验证 {current}/{total}: {path}")

    manifest = backup.verify_backup(backup_path, progress=progress)
    task.raise_if_cancelled()
    items = manifest["items"]
    backup._preflight_restore_targets(items)

    task.set_progress(0.85, "正在检查原始路径冲突……")
    task.raise_if_cancelled()
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
        "overwrite": "尝试覆盖已有文件；被占用或无权限的目标会安全跳过并记录",
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


def _finish_atomic_restore_for_gui(temp: Path, target: Path, item: dict, allow_blocked_skip: bool) -> Optional[str]:
    if temp.stat().st_size != item["size"] or sha256_file(temp) != item["sha256"]:
        raise backup.BackupError(f"恢复临时文件校验失败，未替换目标文件: {target}")
    mtime_ns = item.get("mtime_ns")
    if isinstance(mtime_ns, int) and mtime_ns >= 0:
        try:
            os.utime(temp, ns=(mtime_ns, mtime_ns))
        except OSError:
            pass
    try:
        os.replace(temp, target)
    except OSError as exc:
        if allow_blocked_skip:
            return str(exc)
        raise

    # Once os.replace succeeds, do not downgrade later failures to "skipped".
    # The destination has changed, so any sync/hash error must remain fatal.
    backup._sync_file(target)
    if target.stat().st_size != item["size"] or sha256_file(target) != item["sha256"]:
        raise backup.BackupError(f"恢复后最终 SHA-256 校验失败: {target}")
    return None


def _restore_files(backup_path: Path, manifest: dict, mode: str, task: TaskContext) -> List[dict]:
    items = manifest["items"]
    backup._preflight_restore_targets(items)
    results: List[dict] = []
    total = len(items)
    for index, item in enumerate(items, start=1):
        source_target = Path(str(item["source_path"]))
        existed_before = _target_exists(source_target)
        target = backup._resolve_conflict(source_target, mode)
        if target is None:
            results.append({"target": item["source_path"], "state": "skipped", "reason": "target exists"})
            task.set_progress(0.45 + 0.55 * (index / max(1, total)), f"正在恢复文件：{index}/{total}")
            if task.is_cancelled():
                raise TaskCancelled("恢复已在当前文件完成后的安全点停止；已完成项不会回滚")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        stored = backup_path / Path(str(item["backup_path"]).replace("/", os.sep))
        temp = backup._restore_temp_path(target)
        blocked_reason: Optional[str] = None
        try:
            try:
                shutil.copy2(stored, temp)
                backup._sync_file(temp)
            except OSError as exc:
                if mode == "overwrite" and existed_before:
                    blocked_reason = str(exc)
                else:
                    raise
            if blocked_reason is None:
                blocked_reason = _finish_atomic_restore_for_gui(
                    temp,
                    target,
                    item,
                    allow_blocked_skip=bool(mode == "overwrite" and existed_before),
                )
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

        if blocked_reason is not None:
            results.append({"target": str(target), "state": "skipped_error", "reason": blocked_reason})
            task.log(f"无法覆盖，已跳过: {target}；原因: {blocked_reason}")
        else:
            results.append({"target": str(target), "state": "restored"})

        task.set_progress(0.45 + 0.55 * (index / max(1, total)), f"正在恢复文件：{index}/{total}")
        if index == 1 or index == total or index % 25 == 0:
            task.log(f"正在恢复文件：{index}/{total}  {target}")
        if task.is_cancelled():
            raise TaskCancelled("恢复已在当前文件完成最终校验后的安全点停止；已完成项不会回滚")
    return results


def _write_skipped_report(backup_path: Path, rows: List[dict]) -> Optional[Path]:
    blocked = [row for row in rows if row.get("state") == "skipped_error"]
    if not blocked:
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report = backup_path / f"restore-skipped-{stamp}.txt"
    lines = [
        "FileCheck 恢复跳过文件清单",
        "",
        f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"跳过数量: {len(blocked)}",
        "",
    ]
    for row in blocked:
        lines.append(str(row.get("target", "")))
        lines.append(f"  原因: {row.get('reason', 'unknown error')}")
    write_text(report, "\n".join(lines))
    return report


def run_restore(value: str | Path, conflict: str, task: TaskContext) -> RestoreResult:
    backup_path = Path(value).expanduser().resolve()
    mode = _validate_conflict(conflict)
    manifest_preview = backup.read_backup_manifest(backup_path)
    file_count = len(manifest_preview["items"])

    task.log("正式恢复开始。写入任何目标文件前会再次验证整个备份。")
    task.set_progress(0.0, "正在再次验证备份完整性……")
    task.raise_if_cancelled()

    def verify_progress(stage: str, current: int, total: int, path: str) -> None:
        ratio = max(0.0, min(1.0, float(current) / float(max(1, total))))
        task.set_progress(0.45 * ratio, f"正式恢复前再次验证备份：{current}/{total}")
        if current == 1 or current == total or current % 25 == 0:
            task.log(f"正式恢复前再次验证备份：{current}/{total}  {path}")
        if task.is_cancelled():
            raise TaskCancelled("恢复已在写入任何目标文件之前取消")

    started = time.perf_counter()
    manifest = backup.verify_backup(backup_path, progress=verify_progress)
    task.raise_if_cancelled()
    results = _restore_files(backup_path, manifest, mode, task)
    elapsed = max(0.0, time.perf_counter() - started)
    restored = sum(1 for row in results if row.get("state") == "restored")
    skipped = sum(1 for row in results if row.get("state") == "skipped")
    skipped_error = sum(1 for row in results if row.get("state") == "skipped_error")
    report = _write_skipped_report(backup_path, results)

    if skipped_error:
        task.log(f"恢复完成：restored={restored}, skipped={skipped}, blocked={skipped_error}")
        if report is not None:
            task.log(f"无法覆盖文件清单: {report}")
        task.set_progress(1.0, f"恢复完成，但有 {skipped_error} 个文件无法覆盖")
    else:
        task.log(f"恢复完成：restored={restored}, skipped={skipped}")
        task.set_progress(1.0, "恢复完成并通过最终 SHA-256 校验")

    return RestoreResult(
        backup_path=backup_path,
        conflict=mode,
        file_count=file_count,
        restored=restored,
        skipped=skipped,
        skipped_error=skipped_error,
        skipped_report=report,
        elapsed_seconds=elapsed,
    )
