from __future__ import annotations

import json
from pathlib import Path

import pytest

import filecheck.backup as backup_mod
import filecheck.cli as cli_mod
from filecheck.backup import create_backup, read_backup_manifest, verify_backup
from filecheck.util import sha256_file


def test_atomic_backup_reads_source_payload_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(256)) * 4096)
    target = tmp_path / "staging" / "source.bin"

    real_open = Path.open
    source_reads = 0

    def counting_open(self: Path, mode: str = "r", *args, **kwargs):
        nonlocal source_reads
        if self == source and mode == "rb":
            source_reads += 1
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    digest, stat_result = backup_mod._atomic_copy_to_backup(source, target)

    assert source_reads == 1
    assert stat_result.st_size == source.stat().st_size
    assert digest == sha256_file(source)
    assert sha256_file(target) == digest


@pytest.mark.parametrize("zip_mode", [False, True])
def test_create_backup_performs_one_full_verify_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    zip_mode: bool,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for index in range(5):
        (source / f"file-{index}.bin").write_bytes(bytes([index]) * 8192)

    real_verify = backup_mod.verify_backup
    verify_calls: list[Path] = []

    def counting_verify(path, *, progress=None):
        verify_calls.append(Path(path))
        return real_verify(path, progress=progress)

    monkeypatch.setattr(backup_mod, "verify_backup", counting_verify)
    result = create_backup([source], tmp_path / "backup", zip_mode=zip_mode)

    assert len(verify_calls) == 1
    manifest = read_backup_manifest(result)
    assert manifest["copy_strategy"] == "single-pass-sha256-v1"
    assert len(manifest["items"]) == 5
    # A later explicit verify remains fully available and independent.
    real_verify(result)


def test_cli_backup_does_not_add_second_full_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    scan = tmp_path / "scan-results.json"
    scan.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "path": str(source.resolve()),
                        "directory": str(source.parent.resolve()),
                        "matched_keywords": ["测试"],
                        "levels": ["review"],
                        "severity": "review",
                        "size": source.stat().st_size,
                        "mtime_ns": source.stat().st_mtime_ns,
                        "accessible": True,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def unexpected_cli_verify(*args, **kwargs):
        raise AssertionError("cmd_backup must not re-hash an already verified batch")

    monkeypatch.setattr(cli_mod, "verify_backup", unexpected_cli_verify)
    code = cli_mod.main(
        [
            "backup",
            "--from-scan",
            str(scan),
            "--dest",
            str(tmp_path / "backup"),
        ]
    )
    assert code == 0
