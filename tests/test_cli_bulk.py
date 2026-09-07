from __future__ import annotations

import json
from pathlib import Path

import pytest

from filecheck.backup import restore_backup, verify_backup
from filecheck.cli import _rules_metadata, _sources_from_scan, build_parser, main
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


def _fixture_files(root: Path, count: int = 6) -> tuple[list[Path], dict[str, str]]:
    files: list[Path] = []
    hashes: dict[str, str] = {}
    for index in range(count):
        file = root / f"目录 {index % 2}" / f"候选-{index}.txt"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f"payload-{index}-中文", encoding="utf-8")
        files.append(file)
        hashes[str(file.resolve())] = sha256_file(file)
    return files, hashes


def test_from_scan_defaults_to_all_candidates(tmp_path: Path) -> None:
    files, _ = _fixture_files(tmp_path, 6)
    scan = tmp_path / "scan-results.json"
    _write_scan(scan, files)

    resolved = _sources_from_scan(scan)
    assert resolved == [str(file.resolve()) for file in files]


def test_from_scan_selection_remains_optional_advanced_filter(tmp_path: Path) -> None:
    files, _ = _fixture_files(tmp_path, 5)
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


def test_cli_backup_from_scan_processes_all_without_select(tmp_path: Path) -> None:
    source = tmp_path / "source"
    files, hashes = _fixture_files(source, 8)
    scan = tmp_path / "scan-results.json"
    backup_root = tmp_path / "backup"
    _write_scan(scan, files)

    code = main(["backup", "--from-scan", str(scan), "--dest", str(backup_root)])
    assert code == 0

    batches = [path for path in backup_root.iterdir() if path.is_dir() and path.name.startswith("FC-")]
    assert len(batches) == 1
    manifest = verify_backup(batches[0])
    assert len(manifest["items"]) == 8
    # backup is always non-destructive
    assert all(Path(raw).exists() and sha256_file(Path(raw)) == digest for raw, digest in hashes.items())


@pytest.mark.parametrize("zip_mode", [False, True])
def test_cli_migrate_from_scan_end_to_end(tmp_path: Path, zip_mode: bool) -> None:
    source = tmp_path / "source"
    files, hashes = _fixture_files(source, 10)
    scan = tmp_path / "scan-results.json"
    backup_root = tmp_path / "backup"
    _write_scan(scan, files)

    argv = [
        "migrate",
        "--from-scan",
        str(scan),
        "--dest",
        str(backup_root),
        "--yes",
    ]
    if zip_mode:
        argv.append("--zip")

    code = main(argv)
    assert code == 0
    assert all(not Path(raw).exists() for raw in hashes)

    if zip_mode:
        backups = list(backup_root.glob("FC-*.zip"))
    else:
        backups = [path for path in backup_root.iterdir() if path.is_dir() and path.name.startswith("FC-")]
    states = list(backup_root.glob("*.migration.json"))
    assert len(backups) == 1
    assert len(states) == 1

    verify_backup(backups[0])
    restore_backup(backups[0])
    assert all(sha256_file(Path(raw)) == digest for raw, digest in hashes.items())
