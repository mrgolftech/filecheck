from __future__ import annotations

from pathlib import Path

import pytest

from filecheck.backup import create_backup
from filecheck.gui.restore_service import (
    inspect_restore_target,
    run_restore,
    run_restore_preflight,
)
from filecheck.gui.task_runner import TaskCancelled


class FakeTask:
    def __init__(
        self,
        cancel_after_first_restore: bool = False,
        cancel_during_verify: bool = False,
    ) -> None:
        self.logs = []
        self.progress = []
        self.cancelled = False
        self.cancel_after_first_restore = cancel_after_first_restore
        self.cancel_during_verify = cancel_during_verify

    def log(self, message: str) -> None:
        self.logs.append(message)

    def set_progress(self, progress, message: str = "") -> None:
        self.progress.append((progress, message))
        if self.cancel_after_first_restore and message.startswith("正在恢复文件：1/"):
            self.cancelled = True
        if self.cancel_during_verify and message.startswith("正式恢复前再次验证备份：1/"):
            self.cancelled = True

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise TaskCancelled("cancelled")

    def is_cancelled(self) -> bool:
        return self.cancelled


def test_restore_preflight_reports_conflicts_and_skip_plan(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("backup-version", encoding="utf-8")
    backup_path = create_backup([source], tmp_path / "backup")
    source.write_text("local-version", encoding="utf-8")

    info = inspect_restore_target(backup_path)
    assert info.file_count == 1
    assert info.total_bytes == len("backup-version")

    result = run_restore_preflight(backup_path, "skip", FakeTask())
    assert result.conflicts == 1
    assert result.missing_targets == 0
    assert result.expected_restored == 0
    assert result.expected_skipped == 1


def test_restore_service_supports_skip_rename_and_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("backup-version", encoding="utf-8")
    backup_path = create_backup([source], tmp_path / "backup")

    source.write_text("local-version", encoding="utf-8")
    skip = run_restore(backup_path, "skip", FakeTask())
    assert skip.restored == 0
    assert skip.skipped == 1
    assert source.read_text(encoding="utf-8") == "local-version"

    rename_preflight = run_restore_preflight(backup_path, "rename", FakeTask())
    assert rename_preflight.expected_restored == 1
    rename = run_restore(backup_path, "rename", FakeTask())
    assert rename.restored == 1
    candidates = [path for path in tmp_path.iterdir() if path.is_file() and path != source]
    assert any(path.read_text(encoding="utf-8") == "backup-version" for path in candidates)
    assert source.read_text(encoding="utf-8") == "local-version"

    overwrite_preflight = run_restore_preflight(backup_path, "overwrite", FakeTask())
    assert overwrite_preflight.conflicts == 1
    overwrite = run_restore(backup_path, "overwrite", FakeTask())
    assert overwrite.restored == 1
    assert overwrite.skipped == 0
    assert source.read_text(encoding="utf-8") == "backup-version"


def test_restore_cancel_during_verify_touches_no_target(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("backup-version", encoding="utf-8")
    backup_path = create_backup([source], tmp_path / "backup")
    source.unlink()

    with pytest.raises(TaskCancelled, match="写入任何目标文件之前"):
        run_restore(backup_path, "skip", FakeTask(cancel_during_verify=True))

    assert not source.exists()


def test_restore_cancel_stops_after_completed_file_and_skip_can_resume(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first-backup", encoding="utf-8")
    second.write_text("second-backup", encoding="utf-8")
    backup_path = create_backup([first, second], tmp_path / "backup")
    first.unlink()
    second.unlink()

    with pytest.raises(TaskCancelled, match="安全点停止"):
        run_restore(backup_path, "skip", FakeTask(cancel_after_first_restore=True))

    assert sum(path.exists() for path in (first, second)) == 1

    preflight = run_restore_preflight(backup_path, "skip", FakeTask())
    assert preflight.conflicts == 1
    assert preflight.expected_restored == 1
    assert preflight.expected_skipped == 1
    resumed = run_restore(backup_path, "skip", FakeTask())
    assert resumed.restored == 1
    assert resumed.skipped == 1
    assert first.read_text(encoding="utf-8") == "first-backup"
    assert second.read_text(encoding="utf-8") == "second-backup"
