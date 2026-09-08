from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from filecheck.gui import index_service, settings_service


class FakeTask:
    def __init__(self) -> None:
        self.logs = []
        self.progress = []
        self.cancelled = False

    def log(self, message: str) -> None:
        self.logs.append(message)

    def set_progress(self, progress, message: str = "") -> None:
        self.progress.append((progress, message))

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeError("cancelled")


def test_settings_page_service_persists_backup_root_and_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    rules_path = config_dir / "rules.json"
    rules_path.write_text(
        json.dumps(
            {
                "keywords": {"high": ["机密"], "sensitive": ["秘密"], "review": ["项目"]},
                "extensions": ["docx", "pdf"],
                "max_results_per_keyword": 100000,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(settings_service.cli, "_default_rules_path", lambda: str(rules_path))
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: runtime)
    monkeypatch.setattr(settings_service, "load_index_state", lambda required=False: None)

    backup_root = tmp_path / "backup"
    saved = settings_service.save_settings(
        str(backup_root),
        {"high": ["绝密", "绝密"], "sensitive": ["秘密"], "review": ["方案"]},
        ["DOCX", ".pdf", "pdf"],
    )

    assert saved.backup_root == str(backup_root.resolve())
    assert saved.keywords["high"] == ["绝密"]
    assert saved.extensions == ["docx", "pdf"]
    assert backup_root.is_dir()
    persisted = json.loads(rules_path.read_text(encoding="utf-8"))
    assert persisted["keywords"]["review"] == ["方案"]
    assert persisted["extensions"] == ["docx", "pdf"]
    runtime_payload = json.loads((runtime / "settings.json").read_text(encoding="utf-8"))
    assert runtime_payload["backup_root"] == str(backup_root.resolve())


def test_current_backup_root_falls_back_to_existing_index_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: runtime)
    monkeypatch.setattr(
        settings_service,
        "load_index_state",
        lambda required=False: {"backup_root": r"H:\FileCheckBackup"},
    )
    assert settings_service.current_backup_root() == r"H:\FileCheckBackup"


def test_gui_index_service_uses_settings_and_reports_truthful_elapsed_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_service, "current_backup_root", lambda: r"H:\FileCheckBackup")
    captured = {}

    def fake_configure(selected_roots, backup_root, progress=None):
        captured["roots"] = list(selected_roots)
        captured["backup_root"] = backup_root
        if progress is not None:
            progress(3.2)
            progress(8.7)
        return SimpleNamespace(
            selected_roots=[r"C:\", r"D:\"],
            ntfs_roots=[r"C:\", r"D:\"],
            folder_roots=[],
            database_path=Path(r"C:\FileCheck\runtime\everything\Everything-FileCheck.db"),
            config_path=Path(r"C:\FileCheck\runtime\everything\Everything.ini"),
            status=SimpleNamespace(everything_version="1.4.1.1032", es_version="1.1.0.37"),
        )

    monkeypatch.setattr(index_service, "configure_and_reindex", fake_configure)
    task = FakeTask()
    result = index_service.run_index_build([r"C:\", r"D:\"], task)

    assert captured["roots"] == [r"C:\", r"D:\"]
    assert captured["backup_root"] == r"H:\FileCheckBackup"
    assert result.selected_roots == [r"C:\", r"D:\"]
    elapsed_updates = [(value, message) for value, message in task.progress if "已运行" in message]
    assert elapsed_updates
    assert all(value is None for value, _message in elapsed_updates)
    assert any("9 秒" in message for _value, message in elapsed_updates)
