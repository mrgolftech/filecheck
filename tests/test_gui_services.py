from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import filecheck.gui.scan_service as scan_service
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


def test_task_runner_emits_log_and_success() -> None:
    runner = TaskRunner()

    def worker(task: TaskContext):
        task.log("hello")
        return 42

    assert runner.start("unit", worker) is True
    deadline = time.time() + 2
    events = []
    while time.time() < deadline:
        events.extend(runner.drain_events())
        if any(event.kind == "success" for event in events):
            break
        time.sleep(0.01)

    assert any(event.kind == "started" for event in events)
    assert any(event.kind == "log" and event.message == "hello" for event in events)
    success = next(event for event in events if event.kind == "success")
    assert success.payload == 42


def test_scan_service_reuses_core_and_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(
            {
                "keywords": {"high": ["机密"], "review": ["报告"]},
                "extensions": ["txt", "pdf"],
                "max_results_per_keyword": 100,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    scope = tmp_path / "scope"
    scope.mkdir()
    output = tmp_path / "scan-results.json"
    item_path = scope / "机密报告.txt"
    item_path.write_text("abc", encoding="utf-8")

    monkeypatch.setattr(scan_service.cli, "_default_rules_path", lambda: str(rules_path))
    monkeypatch.setattr(scan_service.cli, "_default_scan_output", lambda: str(output))
    monkeypatch.setattr(
        scan_service,
        "load_index_state",
        lambda required=True: {
            "selected_roots": [str(scope)],
            "excluded_roots": [],
            "index_mode": "portable-folder-index",
        },
    )
    monkeypatch.setattr(
        scan_service.db_persistence,
        "ensure_instance",
        lambda: SimpleNamespace(everything_version="1.4.1.1032", es_version="1.1.0.37"),
    )
    captured = {}

    def fake_scan_keywords(keywords, extensions, **kwargs):
        captured["keywords"] = keywords
        captured["extensions"] = extensions
        captured["kwargs"] = kwargs
        return [
            {
                "path": str(item_path),
                "directory": str(scope),
                "matched_keywords": ["机密", "报告"],
                "levels": ["high", "review"],
                "severity": "high",
                "size": 3,
                "mtime_ns": 1,
                "accessible": True,
            }
        ]

    monkeypatch.setattr(scan_service, "scan_keywords", fake_scan_keywords)
    task = FakeTask()
    result = scan_service.run_scan(scan_service.ScanRequest(path_prefix=str(scope), match_path=False), task)

    assert result.counts == {"total": 1, "high": 1, "sensitive": 0, "review": 0}
    assert result.total_size == 3
    assert result.json_path == output.resolve()
    assert result.csv_path.is_file()
    assert captured["keywords"]["high"] == ["机密"]
    assert captured["extensions"] == ["txt", "pdf"]
    assert captured["kwargs"]["path_prefix"] == str(scope.resolve())
    assert captured["kwargs"]["instance"] == "FileCheck"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["items"][0]["severity"] == "high"
    assert any("关键词查询完成" in line for line in task.logs)


def test_scan_scope_must_be_inside_indexed_roots(tmp_path: Path) -> None:
    indexed = tmp_path / "indexed"
    outside = tmp_path / "outside"
    indexed.mkdir()
    outside.mkdir()

    try:
        scan_service._validate_scope(str(outside), [str(indexed)])
    except RuntimeError as exc:
        assert "不在 FileCheck 已索引范围内" in str(exc)
    else:
        raise AssertionError("outside scan scope should be rejected")
