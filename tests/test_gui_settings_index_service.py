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


def test_settings_service_persists_single_backup_root_rules_and_appearance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_path = _rules_file(tmp_path)
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(settings_service.cli, "_default_rules_path", lambda: str(rules_path))
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: runtime)

    backup_root = tmp_path / "backup"
    saved = settings_service.save_settings(
        str(backup_root),
        {"high": ["绝密", "绝密"], "sensitive": ["秘密"], "review": ["方案"]},
        ["DOCX", ".pdf", "pdf"],
        appearance="dark",
    )

    assert saved.backup_root == str(backup_root.resolve())
    assert saved.backup_roots == [str(backup_root.resolve())]
    assert saved.appearance == "dark"
    assert saved.keywords["high"] == ["绝密"]
    assert saved.extensions == ["docx", "pdf"]
    assert backup_root.is_dir()
    persisted = json.loads(rules_path.read_text(encoding="utf-8"))
    assert persisted["keywords"]["review"] == ["方案"]
    assert persisted["extensions"] == ["docx", "pdf"]
    runtime_payload = json.loads((runtime / "settings.json").read_text(encoding="utf-8"))
    assert runtime_payload["backup_root"] == str(backup_root.resolve())
    assert "backup_roots" not in runtime_payload
    assert runtime_payload["appearance"] == "dark"


def test_settings_service_rejects_multiple_backup_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_path = _rules_file(tmp_path)
    monkeypatch.setattr(settings_service.cli, "_default_rules_path", lambda: str(rules_path))
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: tmp_path / "runtime")
    with pytest.raises(RuntimeError, match="只支持一个"):
        settings_service.save_settings(
            [str(tmp_path / "backup-a"), str(tmp_path / "backup-b")],
            {"high": ["机密"], "sensitive": [], "review": []},
            ["txt"],
        )


def test_backup_root_requires_explicit_settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: tmp_path / "runtime")
    assert settings_service.current_backup_root() is None
    assert settings_service.current_backup_roots() == []


def test_legacy_multiple_root_settings_migrate_first_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    first = tmp_path / "backup-a"
    second = tmp_path / "backup-b"
    (runtime / "settings.json").write_text(
        json.dumps({"schema_version": 2, "backup_roots": [str(first), str(second)]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: runtime)
    assert settings_service.current_backup_root() == str(first.resolve())
    assert settings_service.current_backup_roots() == [str(first.resolve())]


def test_save_appearance_does_not_require_backup_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings_service, "runtime_dir", lambda: tmp_path / "runtime")
    assert settings_service.save_appearance("dark") == "dark"
    assert settings_service.current_appearance() == "dark"
    assert settings_service.current_backup_root() is None


def test_gui_index_service_uses_hardened_db_persistence_and_truthful_elapsed_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_service, "current_backup_root", lambda: r"H:\FileCheckBackup")
    captured = {}

    def fake_configure(selected_roots, backup_root, progress=None):
        captured["roots"] = list(selected_roots)
        captured["backup_root"] = backup_root
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

    monkeypatch.setattr(index_service.db_persistence, "configure_and_reindex", fake_configure)
    task = FakeTask()
    result = index_service.run_index_build(["C:\\", "D:\\"], task)

    assert captured["roots"] == ["C:\\", "D:\\"]
    assert captured["backup_root"] == r"H:\FileCheckBackup"
    assert result.selected_roots == ["C:\\", "D:\\"]
    elapsed_updates = [(value, message) for value, message in task.progress if "已运行" in message]
    assert elapsed_updates
    assert all(value is None for value, _message in elapsed_updates)
    assert any("9 秒" in message for _value, message in elapsed_updates)


def test_gui_index_service_rejects_missing_backup_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_service, "current_backup_root", lambda: None)
    with pytest.raises(RuntimeError, match="设置"):
        index_service.run_index_build(["C:\\"], FakeTask())
