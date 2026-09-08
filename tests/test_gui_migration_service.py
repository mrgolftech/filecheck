from __future__ import annotations

from pathlib import Path

from filecheck.backup import create_backup
from filecheck.gui.migration_service import (
    inspect_removal_target,
    run_removal_preflight,
    run_resume_removal,
    run_source_removal,
)
from filecheck.migration import remove_verified_sources, resume_migration
from filecheck.util import read_json


class FakeTask:
    def __init__(self) -> None:
        self.logs = []
        self.progress = []
        self.cancelled = False

    def log(self, message: str) -> None:
        self.logs.append(message)

    def set_progress(self, progress, message: str = "") -> None:
        self.progress.append((progress, message))

    def is_cancelled(self) -> bool:
        return self.cancelled

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeError("cancelled")


def _make_backup(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    first = source / "a.txt"
    second = source / "b.txt"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")
    backup_root = tmp_path / "backup"
    backup = create_backup([first, second], backup_root)
    return first, second, backup


def test_safe_cancel_is_checkpointed_before_return(tmp_path: Path) -> None:
    first, second, backup = _make_backup(tmp_path)
    cancel = {"value": False}

    def progress(stage, current, total, path):
        if current == 1:
            cancel["value"] = True

    state_path, state = remove_verified_sources(
        backup,
        preflight=False,
        progress=progress,
        should_cancel=lambda: cancel["value"],
    )

    persisted = read_json(state_path)
    assert persisted["deleted"] == 1
    assert persisted["status"] == "removing"
    assert first.exists() is False
    assert second.exists() is True

    _, resumed = resume_migration(state_path)
    assert resumed["status"] == "completed"
    assert second.exists() is False


def test_gui_removal_preflight_and_complete_remove(tmp_path: Path) -> None:
    first, second, backup = _make_backup(tmp_path)
    info = inspect_removal_target(backup)
    assert info.has_state is False
    assert info.file_count == 2

    task = FakeTask()
    preflight = run_removal_preflight(backup, task)
    assert preflight.file_count == 2
    assert first.exists() and second.exists()

    result = run_source_removal(backup, task)
    assert result.status == "completed"
    assert result.deleted == 2
    assert first.exists() is False
    assert second.exists() is False

    final_info = inspect_removal_target(backup)
    assert final_info.status == "completed"
    assert final_info.deleted == 2
    assert final_info.can_resume is False


def test_resume_service_finishes_checkpointed_operation(tmp_path: Path) -> None:
    first, second, backup = _make_backup(tmp_path)
    cancel = {"value": False}

    def progress(stage, current, total, path):
        if current == 1:
            cancel["value"] = True

    remove_verified_sources(
        backup,
        preflight=False,
        progress=progress,
        should_cancel=lambda: cancel["value"],
    )
    info = inspect_removal_target(backup)
    assert info.can_resume is True
    assert info.deleted == 1

    task = FakeTask()
    result = run_resume_removal(backup, task)
    assert result.status == "completed"
    assert result.deleted == 2
    assert second.exists() is False
