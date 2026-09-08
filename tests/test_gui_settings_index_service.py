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


def _rules_file(tmp_path: Path) -> Path:
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
    return rules_path


def test_settings_service_persists_multiple_backup_roots_rules_and_appearance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_path = _rules_file(tmp_path)
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(settings_service.cli, "_default_rules_path", lambda: str(rules_path))
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: runtime)

    backup_a = tmp_path / "backup-a"
    backup_b = tmp_path / "backup-b"
    saved = settings_service.save_settings(
        [str(backup_a), str(backup_b), str(backup_a)],
        {"high": ["绝密", "绝密"], "sensitive": ["秘密"], "review": ["方案"]},
        ["DOCX", ".pdf", "pdf"],
        appearance="dark",
    )

    assert saved.backup_roots == [str(backup_a.resolve()), str(backup_b.resolve())]
    assert saved.backup_root == str(backup_a.resolve())
    assert saved.appearance == "dark"
    assert saved.keywords["high"] == ["绝密"]
    assert saved.extensions == ["docx", "pdf"]
    persisted = json.loads(rules_path.read_text(encoding="utf-8"))
    assert persisted["keywords"]["review"] == ["方案"]
    assert persisted["extensions"] == ["docx", "pdf"]
    runtime_payload = json.loads((runtime / "settings.json").read_text(encoding="utf-8"))
    assert runtime_payload["backup_roots"] == [str(backup_a.resolve()), str(backup_b.resolve())]
    assert runtime_payload["appearance"] == "dark"


def test_backup_roots_require_explicit_settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: tmp_path / "runtime")
    assert settings_service.current_backup_roots() == []
    assert settings_service.current_backup_root() is None


def test_save_appearance_does_not_require_backup_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: tmp_path / "runtime")
    assert settings_service.save_appearance("dark") == "dark"
    assert settings_service.current_appearance() == "dark"
    assert settings_service.current_backup_roots() == []


def test_gui_index_service_uses_all_backup_roots_and_truthful_elapsed_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_service, "current_backup_roots", lambda: [r"H:\FileCheckBackup", r"I:\FileCheckBackup"])
    captured = {}

    def fake_configure(selected_roots, backup_root, additional_excluded_roots=(), progress=None):
        captured["roots"] = list(selected_roots)
        captured["backup_root"] = backup_root
        captured["additional"] = list(additional_excluded_roots)
        if progress is not None:
            progress(3.2)
            progress(8.7)
        return SimpleNamespace(
            selected_roots=["C:\\", "D:\\"],
            ntfs_roots=["C:\\", "D:\\"],
            folder_roots=[],
            database_path=Path("C:\\FileCheck\\runtime\\everything\\Everything-FileCheck.db"),
            config_path=Path("C:\\FileCheck\\runtime\\everything\\Everything.ini"),
            status=SimpleNamespace(everything_version="1.4.1.1032", es_version="1.1.0.37"),
        )

    monkeypatch.setattr(index_service, "configure_and_reindex", fake_configure)
    task = FakeTask()
    result = index_service.run_index_build(["C:\\", "D:\\"], task)

    assert captured["roots"] == ["C:\\", "D:\\"]
    assert captured["backup_root"] == r"H:\FileCheckBackup"
    assert captured["additional"] == [r"I:\FileCheckBackup"]
    assert result.selected_roots == ["C:\\", "D:\\"]
    elapsed_updates = [(value, message) for value, message in task.progress if "已运行" in message]
    assert elapsed_updates
    assert all(value is None for value, _message in elapsed_updates)
    assert any("9 秒" in message for _value, message in elapsed_updates)


def test_gui_index_service_rejects_missing_backup_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_service, "current_backup_roots", lambda: [])
    with pytest.raises(RuntimeError, match="设置"):
        index_service.run_index_build(["C:\\"], FakeTask())
