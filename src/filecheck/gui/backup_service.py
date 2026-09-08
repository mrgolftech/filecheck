from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from filecheck import backup

from .scan_service import ScanResult
from .settings_service import current_backup_root
from .task_runner import TaskContext


@dataclass(frozen=True)
class BackupRequest:
    scan_result: ScanResult
    destination_root: str


@dataclass(frozen=True)
class BackupPreflight:
    destination_root: Path
    file_count: int
    source_bytes: int
    required_bytes: int
    free_bytes: Optional[int]
    reserve_bytes: int


@dataclass(frozen=True)
class BackupResult:
    backup_path: Path
    manifest: Dict[str, Any]
    file_count: int
    total_bytes: int
    elapsed_seconds: float
    throughput_mib_s: Optional[float]


def suggested_destination() -> Optional[str]:
    return current_backup_root()


def _source_paths(scan_result: ScanResult) -> List[str]:
    items = scan_result.items
    if not items:
        raise RuntimeError("当前扫描结果没有可备份文件")
    inaccessible = [str(item.get("path", "")) for item in items if not item.get("accessible", False)]
    if inaccessible:
        examples = "；".join(inaccessible[:3])
        extra = f"；另有 {len(inaccessible) - 3} 个" if len(inaccessible) > 3 else ""
        raise RuntimeError(
            f"扫描结果中有 {len(inaccessible)} 个文件当前不可访问，不能执行整批备份。"
            f"请重新扫描或先处理这些文件：{examples}{extra}"
        )
    sources = [str(item.get("path", "")).strip() for item in items]
    if any(not value for value in sources):
        raise RuntimeError("扫描结果中存在无效源文件路径")
    return sources


def _resolve_destination(value: str) -> Path:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError("尚未设置备份根目录，请先到“设置”中配置")
    destination = Path(text).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if not destination.is_dir():
        raise RuntimeError(f"备份目标不是有效目录: {destination}")
    return destination


def preflight_backup(request: BackupRequest, task: TaskContext) -> BackupPreflight:
    task.log("正在检查扫描结果和备份目标……")
    task.set_progress(0.15, "正在解析待备份文件……")
    sources = _source_paths(request.scan_result)
    destination = _resolve_destination(request.destination_root)
    task.raise_if_cancelled()

    task.set_progress(0.45, "正在统计文件容量和目标磁盘可用空间……")
    files = backup._collect_files(sources, destination)
    source_bytes, required_bytes, free_bytes = backup._ensure_destination_capacity(destination, files)
    task.raise_if_cancelled()

    reserve_bytes = max(0, required_bytes - source_bytes)
    task.log(f"待备份文件: {len(files)} 个")
    task.log(f"源文件总容量: {source_bytes} 字节")
    task.log(f"空间需求估算: {required_bytes} 字节（含安全余量 {reserve_bytes} 字节）")
    if free_bytes is None:
        task.log("目标磁盘可用空间无法读取；正式备份时仍会再次执行容量检查。")
    else:
        task.log(f"目标磁盘当前可用空间: {free_bytes} 字节")
    task.log("备份策略: 单次复制同步计算 SHA-256，复制完成后再对备份执行全量 SHA-256 校验。")
    task.set_progress(1.0, "备份预检通过")

    return BackupPreflight(
        destination_root=destination,
        file_count=len(files),
        source_bytes=source_bytes,
        required_bytes=required_bytes,
        free_bytes=free_bytes,
        reserve_bytes=reserve_bytes,
    )


def run_backup(request: BackupRequest, task: TaskContext) -> BackupResult:
    sources = _source_paths(request.scan_result)
    destination = _resolve_destination(request.destination_root)
    task.raise_if_cancelled()
    task.log(f"开始创建目录备份，目标根目录: {destination}")
    task.log("备份过程中不会删除任何源文件。")

    last_reported = {"copy": 0, "verify": 0}

    def on_progress(stage: str, current: int, total: int, path: str) -> None:
        task.raise_if_cancelled()
        total_safe = max(1, int(total))
        ratio = max(0.0, min(1.0, float(current) / float(total_safe)))
        if stage == "copy":
            progress = 0.05 + 0.60 * ratio
            label = f"正在复制并计算 SHA-256：{current}/{total}"
        elif stage == "verify":
            progress = 0.65 + 0.35 * ratio
            label = f"正在全量校验备份：{current}/{total}"
        else:
            progress = None
            label = f"{stage}：{current}/{total}"
        task.set_progress(progress, label)

        previous = last_reported.get(stage, 0)
        if current == 1 or current == total or current - previous >= 25:
            last_reported[stage] = current
            task.log(f"{label}  {path}")

    started = time.perf_counter()
    backup_path = backup.create_backup(sources, destination, progress=on_progress)
    elapsed = max(0.0, time.perf_counter() - started)
    manifest = backup.read_backup_manifest(backup_path)
    total_bytes = int(
        manifest.get(
            "source_bytes_total",
            sum(int(item.get("size", 0)) for item in manifest.get("items", [])),
        )
    )
    file_count = len(manifest.get("items", []))
    throughput = None
    if total_bytes > 0 and elapsed > 0:
        throughput = total_bytes / (1024.0 * 1024.0) / elapsed

    task.log("目录备份完成，并已通过全量 SHA-256 校验。")
    task.log(f"备份批次: {backup_path}")
    task.log(f"manifest: {backup_path / 'manifest.json'}")
    task.set_progress(1.0, "备份完成并校验通过")

    return BackupResult(
        backup_path=backup_path.resolve(),
        manifest=manifest,
        file_count=file_count,
        total_bytes=total_bytes,
        elapsed_seconds=elapsed,
        throughput_mib_s=throughput,
    )
