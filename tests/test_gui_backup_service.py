from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from filecheck.backup import verify_backup
from filecheck.gui import backup_service
from filecheck.gui.scan_service import ScanResult
from filecheck.gui.task_runner import TaskContext, TaskRunner


class FakeTask:
    def __init__(self) -> None:
        self.logs = []
        self.progress = []

    def log(self, message: str) -> None:
        self.logs.append(message)

    def set_progress(self, progress, message: str = "") -> None:
        self.progress.append((progress, message))

    def raise_if_cancelled(self) -> None:
        return None


def _scan_result(tmp_path: Path, *, inaccessible: bool = False) -> ScanResult:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    first = source_dir / "机密报告.txt"
    second = source_dir / "方案.pdf"
    first.write_bytes(b"abc")
    second.write_bytes(b"defgh")
    json_path = tmp_path / "scan.json"
    csv_path = tmp_path / "scan.csv"
    json_path.write_text("{}", encoding="utf-8")
    csv_path.write_text("", encoding="utf-8")
    items = [
        {
            "path": str(first),
            "directory": str(source_dir),
            "matched_keywords": ["机密"],
            "severity": "high",
            "size": 3,
            "accessible": not inaccessible,
        },
        {
            "path": str(second),
            "directory": str(source_dir),
            "matched_keywords": ["方案"],
            "severity": "review",
            "size": 5,
            "accessible": True,
        },
    ]
    return ScanResult(
        json_path=json_path,
        csv_path=csv_path,
        payload={"items": items},
        counts={"total": 2, "high": 1, "sensitive": 0, "review": 1},
        total_size=8,
        inaccessible_count=1 if inaccessible else 0,
    )


def test_backup_preflight_and_run_reuse_verified_core(tmp_path: Path) -> None:
    result = _scan_result(tmp_path)
    destination = tmp_path / "backup-root"
    request = backup_service.BackupRequest(result, str(destination))
    task = FakeTask()

    preflight = backup_service.preflight_backup(request, task)
    assert preflight.destination_root == destination.resolve()
    assert preflight.file_count == 2
    assert preflight.source_bytes == 8
    assert preflight.required_bytes > preflight.source_bytes
    assert preflight.free_bytes is None or preflight.free_bytes >= preflight.required_bytes
    assert any("SHA-256" in line for line in task.logs)

    backup_result = backup_service.run_backup(request, task)
    assert backup_result.file_count == 2
    assert backup_result.total_bytes == 8
    assert backup_result.backup_path.is_dir()
    manifest = verify_backup(backup_result.backup_path)
    assert len(manifest["items"]) == 2
    assert (backup_result.backup_path / "manifest.json").is_file()
    assert any("全量 SHA-256 校验" in line for line in task.logs)


def test_backup_preflight_rejects_inaccessible_scan_items(tmp_path: Path) -> None:
    result = _scan_result(tmp_path, inaccessible=True)
    request = backup_service.BackupRequest(result, str(tmp_path / "backup-root"))
    with pytest.raises(RuntimeError, match="当前不可访问"):
        backup_service.preflight_backup(request, FakeTask())


def test_task_runner_does_not_misreport_durable_success_as_cancelled() -> None:
    runner = TaskRunner()
    ready = threading.Event()
    finish = threading.Event()

    def worker(task: TaskContext):
        ready.set()
        finish.wait(timeout=2)
        return "durable-result"

    assert runner.start("durable", worker) is True
    assert ready.wait(timeout=2)
    runner.cancel()
    finish.set()

    events = []
    deadline = time.time() + 2
    while time.time() < deadline:
        events.extend(runner.drain_events())
        if any(event.kind in ("success", "cancelled", "error") for event in events):
            break
        time.sleep(0.01)

    assert any(event.kind == "success" and event.payload == "durable-result" for event in events)
    assert not any(event.kind == "cancelled" for event in events)
