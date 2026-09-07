from __future__ import annotations

import json
from pathlib import Path

import filecheck.menu as menu


def _payload(sizes: list[int | None], *, path_filter: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "path_filter": path_filter,
        "items": [
            {
                "path": f"C:/test/f-{index}.txt",
                "directory": "C:/test",
                "matched_keywords": ["测试"],
                "levels": ["review"],
                "severity": "review",
                "size": size,
                "mtime_ns": 1 if size is not None else None,
                "accessible": size is not None,
            }
            for index, size in enumerate(sizes)
        ],
    }


def test_capacity_summary_matches_current_backup_formula() -> None:
    payload = _payload([10 * 1024 * 1024, 20 * 1024 * 1024, None])
    metrics = menu._capacity_from_scan(payload)

    assert metrics["files"] == 3
    assert metrics["accessible"] == 2
    assert metrics["unknown"] == 1
    assert metrics["payload_bytes"] == 30 * 1024 * 1024
    # 5% would be below the 16 MiB minimum reserve.
    assert metrics["directory_required"] == 46 * 1024 * 1024
    assert metrics["zip_required"] == 76 * 1024 * 1024


def test_format_bytes_is_human_readable() -> None:
    assert menu._format_bytes(0) == "0 B"
    assert menu._format_bytes(1024) == "1.00 KiB"
    assert menu._format_bytes(1024**3) == "1.00 GiB"


def test_launcher_delegates_existing_subcommands(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(menu.cli, "_configure_console_streams", lambda: None)
    monkeypatch.setattr(menu.cli, "main", lambda argv: calls.append(list(argv)) or 7)

    assert menu.main(["doctor"]) == 7
    assert calls == [["doctor"]]


def test_menu_can_exit_without_running_subcommands(monkeypatch) -> None:
    monkeypatch.setattr(menu.cli, "_configure_console_streams", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt: "0")
    assert menu.main([]) == 0


def test_scan_flow_passes_user_selected_path(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "scan-results.json"
    calls: list[list[str]] = []

    answers = iter(["2", r"D:\\Engineering", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(menu, "_default_scan_output", lambda: output)

    def fake_cli_main(argv: list[str]) -> int:
        calls.append(list(argv))
        output.write_text(json.dumps(_payload([123], path_filter=r"D:\\Engineering")), encoding="utf-8")
        return 0

    monkeypatch.setattr(menu.cli, "main", fake_cli_main)
    result = menu._run_scan_flow()

    assert result is not None
    assert calls
    command = calls[0]
    assert command[0] == "scan"
    assert "--path" in command
    assert r"D:\\Engineering" in command
    assert "--match-path" not in command


def test_bulk_backup_menu_never_requires_per_file_selection(tmp_path: Path, monkeypatch) -> None:
    scan = tmp_path / "scan-results.json"
    payload = _payload([100, 200])
    scan.write_text(json.dumps(payload), encoding="utf-8")
    destination = tmp_path / "backup"

    calls: list[list[str]] = []
    answers = iter([str(destination), ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(menu.cli, "main", lambda argv: calls.append(list(argv)) or 0)

    rc = menu._process_scan(scan, payload, fixed_action="1")
    assert rc == 0
    assert calls == [["backup", "--from-scan", str(scan), "--dest", str(destination)]]
    assert "--select" not in calls[0]


def test_migrate_menu_keeps_destructive_yes_confirmation_in_cli(tmp_path: Path, monkeypatch) -> None:
    scan = tmp_path / "scan-results.json"
    payload = _payload([100])
    destination = tmp_path / "backup"

    calls: list[list[str]] = []
    answers = iter([str(destination), ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(menu.cli, "main", lambda argv: calls.append(list(argv)) or 0)

    rc = menu._process_scan(scan, payload, fixed_action="3")
    assert rc == 0
    assert calls[0][0] == "migrate"
    assert "--yes" not in calls[0]
