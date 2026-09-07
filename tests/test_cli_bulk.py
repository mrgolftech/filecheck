from __future__ import annotations

import json
from pathlib import Path

from filecheck.cli import _rules_metadata, _sources_from_scan, build_parser
from filecheck.util import sha256_file


def _write_scan(path: Path, files: list[Path]) -> None:
    payload = {
        "schema_version": 1,
        "items": [
            {
                "path": str(file.resolve()),
                "directory": str(file.parent.resolve()),
                "matched_keywords": ["测试"],
                "levels": ["review"],
                "severity": "review",
                "size": file.stat().st_size,
                "mtime_ns": file.stat().st_mtime_ns,
                "accessible": True,
            }
            for file in files
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_from_scan_defaults_to_all_candidates(tmp_path: Path) -> None:
    files = []
    for index in range(6):
        file = tmp_path / f"目录 {index % 2}" / f"候选-{index}.txt"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(str(index), encoding="utf-8")
        files.append(file)
    scan = tmp_path / "scan-results.json"
    _write_scan(scan, files)

    resolved = _sources_from_scan(scan)
    assert resolved == [str(file.resolve()) for file in files]


def test_from_scan_selection_remains_optional_advanced_filter(tmp_path: Path) -> None:
    files = []
    for index in range(5):
        file = tmp_path / f"f-{index}.txt"
        file.write_text(str(index), encoding="utf-8")
        files.append(file)
    scan = tmp_path / "scan-results.json"
    _write_scan(scan, files)

    assert _sources_from_scan(scan, "1,3-4") == [
        str(files[0].resolve()),
        str(files[2].resolve()),
        str(files[3].resolve()),
    ]


def test_rules_metadata_uses_filename_and_hash_not_absolute_path(tmp_path: Path) -> None:
    rules = tmp_path / "private-parent" / "rules.local.json"
    rules.parent.mkdir()
    rules.write_text('{"keywords": {}, "extensions": ["txt"]}', encoding="utf-8")

    metadata = _rules_metadata(rules)
    assert metadata == {
        "file": "rules.local.json",
        "sha256": sha256_file(rules),
    }
    assert str(tmp_path) not in json.dumps(metadata)


def test_parser_accepts_bulk_backup_and_migrate_without_select() -> None:
    parser = build_parser()
    backup = parser.parse_args(["backup", "--from-scan", "scan-results.json", "--dest", "D:/backup"])
    migrate = parser.parse_args(
        ["migrate", "--from-scan", "scan-results.json", "--dest", "D:/backup", "--yes"]
    )
    assert backup.select is None
    assert migrate.select is None
    assert migrate.yes is True
