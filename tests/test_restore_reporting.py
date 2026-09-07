from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import filecheck.restore_reporting as restore_reporting
import filecheck.resume_ui as resume_ui
from filecheck.backup import create_backup


def test_restore_default_skip_writes_txt_report_for_existing_target(tmp_path: Path) -> None:
    source = tmp_path / "source" / "报告.txt"
    source.parent.mkdir(parents=True)
    source.write_text("original backup content", encoding="utf-8")
    backup = create_backup([source], tmp_path / "backup")

    source.write_text("manual newer content", encoding="utf-8")
    args = SimpleNamespace(backup=str(backup), conflict="skip")
    assert restore_reporting.cmd_restore(args) == 0

    assert source.read_text(encoding="utf-8") == "manual newer content"
    report = backup / "restore-skipped.txt"
    assert report.is_file()
    text = report.read_text(encoding="utf-8-sig")
    assert str(source) in text
    assert "默认 skip 策略未覆盖" in text


def test_restore_skip_report_marks_identical_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "source" / "same.txt"
    source.parent.mkdir(parents=True)
    source.write_text("same payload", encoding="utf-8")
    backup = create_backup([source], tmp_path / "backup")

    args = SimpleNamespace(backup=str(backup), conflict="skip")
    assert restore_reporting.cmd_restore(args) == 0
    text = (backup / "restore-skipped.txt").read_text(encoding="utf-8-sig")
    assert "内容与备份一致" in text


def test_restore_with_no_skip_removes_stale_report(tmp_path: Path) -> None:
    source = tmp_path / "source" / "restore.txt"
    source.parent.mkdir(parents=True)
    source.write_text("payload", encoding="utf-8")
    backup = create_backup([source], tmp_path / "backup")
    source.unlink()
    stale = backup / "restore-skipped.txt"
    stale.write_text("stale", encoding="utf-8")

    args = SimpleNamespace(backup=str(backup), conflict="skip")
    assert restore_reporting.cmd_restore(args) == 0
    assert source.read_text(encoding="utf-8") == "payload"
    assert not stale.exists()


def test_resume_menu_returns_without_manual_path_when_no_task(monkeypatch) -> None:
    monkeypatch.setattr(resume_ui, "discover_operation_states", lambda include_completed=False: [])
    assert resume_ui.menu_resume_flow() == 0
