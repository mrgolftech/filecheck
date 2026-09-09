from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

import filecheck.backup as backup_mod
import filecheck.cli as cli
from filecheck.backup import create_backup, read_backup_manifest
from filecheck.scan_guard import filter_protected_backup_items


def _stored_path(batch: Path) -> Path:
    manifest = read_backup_manifest(batch)
    return batch.joinpath(*str(manifest["items"][0]["backup_path"]).split("/"))


def _scan_item(path: Path) -> dict:
    return {
        "path": str(path),
        "directory": str(path.parent),
        "matched_keywords": ["机密"],
        "levels": ["high"],
        "severity": "high",
        "size": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
        "accessible": True,
    }


def test_shared_filter_excludes_renamed_backup_and_keeps_normal_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup_mod, "_is_windows", lambda: False)

    normal = tmp_path / "indexed" / "机密正常文件.txt"
    normal.parent.mkdir(parents=True)
    normal.write_text("normal", encoding="utf-8")

    source = tmp_path / "seed" / "机密历史文件.txt"
    source.parent.mkdir(parents=True)
    source.write_text("old", encoding="utf-8")
    batch = create_backup([source], tmp_path / "legacy-root")
    renamed = batch.with_name("FC-2")
    batch.rename(renamed)
    stored = _stored_path(renamed)

    items, protected_batches = filter_protected_backup_items(
        [_scan_item(normal), _scan_item(stored), {"severity": "review"}]
    )

    assert [row.get("path") for row in items] == [str(normal), None]
    assert protected_batches == [str(renamed.resolve())]


def test_cli_scan_filters_renamed_backup_and_records_protection_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backup_mod, "_is_windows", lambda: False)

    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(
            {"keywords": {"high": ["机密"]}, "extensions": ["txt"]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    indexed_root = tmp_path / "indexed"
    indexed_root.mkdir()
    normal = indexed_root / "机密正常文件.txt"
    normal.write_text("normal", encoding="utf-8")

    source = tmp_path / "seed" / "机密历史文件.txt"
    source.parent.mkdir(parents=True)
    source.write_text("old", encoding="utf-8")
    batch = create_backup([source], indexed_root / "legacy-root")
    renamed = indexed_root / "FC-2"
    batch.rename(renamed)
    stored = _stored_path(renamed)

    output = tmp_path / "scan-results.json"
    monkeypatch.setattr(
        cli,
        "load_index_state",
        lambda required=True: {
            "selected_roots": [str(indexed_root)],
            "excluded_roots": [],
        },
    )
    monkeypatch.setattr(
        cli,
        "ensure_instance",
        lambda *args, **kwargs: SimpleNamespace(
            everything_version="1.4.1.1032",
            es_version="1.1.0.37",
        ),
    )
    monkeypatch.setattr(
        cli,
        "scan_keywords",
        lambda *args, **kwargs: [_scan_item(normal), _scan_item(stored)],
    )

    args = Namespace(
        rules=str(rules_path),
        es=None,
        everything=None,
        match_path=False,
        path=None,
        list_limit=0,
        output=str(output),
    )

    assert cli.cmd_scan(args) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [row["path"] for row in payload["items"]] == [str(normal)]
    assert payload["excluded_backup_items"] == 1
    assert payload["protected_backup_batches"] == [str(renamed.resolve())]

    stdout = capsys.readouterr().out
    assert "已自动排除 1 个" in stdout
    assert str(renamed.resolve()) in stdout
