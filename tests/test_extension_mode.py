from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import filecheck.everything as everything
import filecheck.extension_scan as extension_scan
import filecheck.gui.scan_service as scan_service
from filecheck.cli import build_parser


def test_extension_parser_normalizes_and_deduplicates() -> None:
    assert extension_scan.normalize_extensions(" .PDF;docx，xlsx  .PDF ") == ["pdf", "docx", "xlsx"]
    assert extension_scan.normalize_extensions([".PDF", "docx", ".pdf"]) == ["pdf", "docx"]
    with pytest.raises(ValueError, match="不能为空"):
        extension_scan.normalize_extensions(" , ; ")
    for dangerous in ("*.*", "pdf | exe", "pdf/abc", "pdf:abc"):
        with pytest.raises(ValueError, match="无效扩展名"):
            extension_scan.normalize_extensions(dangerous)


def test_extension_scan_uses_exact_suffix_and_respects_exclusions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "indexed"
    root.mkdir()
    keep = root / "普通文档.PDF"
    keep.write_bytes(b"1234")
    excluded = root / "backup" / "旧副本.pdf"
    excluded.parent.mkdir()
    excluded.write_bytes(b"hidden")
    wrong_ext = root / "photo.pdf.exe"
    wrong_ext.write_bytes(b"exe")
    outside = tmp_path / "elsewhere" / "其他.pdf"
    outside.parent.mkdir()
    outside.write_bytes(b"outside")
    missing = root / "gone.pdf"
    args_seen = []

    monkeypatch.setattr(
        everything, "get_status",
        lambda es=None, instance=None: everything.EverythingStatus(
            "es.exe", "1.1.0.37", "1.4.1.1032", instance
        ),
    )

    def fake_export(es_path, args, **kwargs):
        args_seen.append(args)
        assert args[-1] == "ext:pdf"
        return "\n".join(map(str, [keep, keep, wrong_ext, excluded, outside, missing]))

    monkeypatch.setattr(everything, "_run_export_txt", fake_export)
    items = extension_scan.scan_extensions(
        ".PDF, .pdf", path_prefix=str(root), instance="FileCheck",
        exclude_roots=[excluded.parent],
    )
    assert [x["path"] for x in items] == sorted([str(keep), str(missing)])
    assert len(args_seen) == 1
    assert args_seen[0][:2] == ["-instance", "FileCheck"]
    assert "/a-d" in args_seen[0]
    assert "-path" in args_seen[0]
    assert all(x["matched_keywords"] == [] and x["severity"] == "review" for x in items)
    assert next(x for x in items if x["path"] == str(keep))["size"] == 4
    assert next(x for x in items if x["path"] == str(missing))["accessible"] is False


def test_extension_scan_rejects_truncated_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        everything, "get_status",
        lambda es=None, instance=None: everything.EverythingStatus(
            "es.exe", "1.1.0.37", "1.4.1.1032", instance
        ),
    )
    monkeypatch.setattr(everything, "_run_export_txt", lambda *a, **k: "C:/a.pdf\nC:/b.pdf")
    with pytest.raises(RuntimeError, match="上限"):
        extension_scan.scan_extensions("pdf", max_results_per_extension=2)


def test_gui_extension_mode_bypasses_keywords_and_writes_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps({"keywords": {"high": ["秘密"]}, "extensions": ["txt"],
                    "max_results_per_keyword": 100}, ensure_ascii=False),
        encoding="utf-8",
    )
    file_path = tmp_path / "普通资料.pdf"
    file_path.write_bytes(b"abc")
    output = tmp_path / "scan.json"
    monkeypatch.setattr(scan_service.cli, "_default_rules_path", lambda: str(rules_path))
    monkeypatch.setattr(scan_service.cli, "_default_scan_output", lambda: str(output))
    monkeypatch.setattr(scan_service, "load_index_state", lambda required=True: {
        "selected_roots": [str(tmp_path)], "excluded_roots": [],
        "index_mode": "test", "updated_at": "v1",
    })
    monkeypatch.setattr(scan_service, "current_backup_root", lambda: str(tmp_path / "backup"))
    monkeypatch.setattr(scan_service, "program_dir", lambda: tmp_path / "app")
    monkeypatch.setattr(
        scan_service.db_persistence, "ensure_instance",
        lambda: SimpleNamespace(everything_version="1.4", es_version="1.1"),
    )
    calls = {}

    def fake_extensions(extensions, **kwargs):
        calls["extensions"] = extensions
        calls["kwargs"] = kwargs
        return [{
            "path": str(file_path), "directory": str(tmp_path), "matched_keywords": [],
            "matched_extension": "pdf", "levels": ["review"], "severity": "review",
            "size": 3, "mtime_ns": 1, "accessible": True,
        }]

    monkeypatch.setattr(scan_service, "scan_extensions", fake_extensions)
    monkeypatch.setattr(
        scan_service, "scan_keywords",
        lambda *args, **kwargs: pytest.fail("keyword search must not run in extension mode"),
    )

    class Task:
        def log(self, msg): pass
        def set_progress(self, progress, message=""): pass
        def raise_if_cancelled(self): pass

    result = scan_service.run_scan(
        scan_service.ScanRequest(mode="extensions", extensions=(".PDF", "pdf")), Task()
    )
    assert calls["extensions"] == ["pdf"]
    assert calls["kwargs"]["instance"] == "FileCheck"
    assert str(tmp_path / "backup") in calls["kwargs"]["exclude_roots"]
    assert result.counts["review"] == 1
    assert result.csv_path.is_file()
    assert result.payload["scan_mode"] == "extensions"
    assert result.payload["selected_extensions"] == ["pdf"]
    assert result.payload["items"][0]["matched_keywords"] == []


def test_cli_parser_exposes_both_modes() -> None:
    parser = build_parser()
    old = parser.parse_args(["scan"])
    new = parser.parse_args(["scan", "--mode", "extensions", "--extensions", ".pdf,docx"])
    assert old.mode == "keywords"
    assert new.mode == "extensions"
    assert new.extensions == ".pdf,docx"
