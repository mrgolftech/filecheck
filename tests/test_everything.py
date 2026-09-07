from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import filecheck.everything as everything


def test_search_keyword_builds_query_and_filters_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inside = tmp_path / "scope" / "机密 测试.txt"
    outside = tmp_path / "outside" / "机密 其他.txt"
    inside.parent.mkdir()
    outside.parent.mkdir()
    inside.write_text("a", encoding="utf-8")
    outside.write_text("b", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_run_export_txt(
        es_path: Path,
        args: list[str],
        timeout: int = 60,
        *,
        argv_mode: bool = True,
    ) -> str:
        captured["args"] = args
        captured["argv_mode"] = argv_mode
        return f"{inside}\n{outside}\n"

    monkeypatch.setattr(everything, "_run_export_txt", fake_run_export_txt)
    result = everything.search_keyword(
        Path("es.exe"),
        "机密",
        ["txt", ".docx"],
        match_path=True,
        path_prefix=str(inside.parent),
    )

    assert result == [inside]
    args = captured["args"]
    assert isinstance(args, list)
    assert captured["argv_mode"] is True
    assert "-p" in args
    assert "-path" in args
    assert "/a-d" in args
    assert "-full-path-and-name" in args
    assert '"机密" ext:txt;docx' in args


def test_run_argv_mode_places_switch_first(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_subprocess_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(everything.subprocess, "run", fake_subprocess_run)
    output = everything._run(Path("es.exe"), ["-path", r"C:\Test", "机密 ext:txt"], argv_mode=True)
    assert output == "ok"
    command = captured["command"]
    assert command[0] == "es.exe"
    assert command[1] == "-argv"
    assert command[2:] == ["-path", r"C:\Test", "机密 ext:txt"]


def test_utf8_export_preserves_nonbreaking_space_and_unicode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = tmp_path / "HSMD1算法芯片数据手册\u00a0V2.4-兴唐通信科技有限公司.pdf"
    captured: dict[str, object] = {}

    def fake_subprocess_run(command, **kwargs):
        captured["command"] = command
        export_index = command.index("-export-txt")
        export_path = Path(command[export_index + 1])
        export_path.write_bytes(("\ufeff" + str(expected) + "\r\n").encode("utf-8"))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(everything.subprocess, "run", fake_subprocess_run)
    output = everything._run_export_txt(
        Path("es.exe"),
        ["-full-path-and-name", '"算法" ext:pdf'],
        argv_mode=True,
    )

    assert output == str(expected)
    command = captured["command"]
    assert command[0] == "es.exe"
    assert command[1] == "-argv"
    assert "-export-txt" in command
    assert "-utf8-bom" in command
    assert "?" not in output
    assert "\u00a0" in output


def test_search_keyword_returns_exact_unicode_export_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = tmp_path / "HSMD1算法芯片数据手册\u00a0V2.4-兴唐通信科技有限公司.pdf"
    monkeypatch.setattr(everything, "_run_export_txt", lambda *args, **kwargs: str(expected))

    result = everything.search_keyword(Path("es.exe"), "算法", ["pdf"])

    assert result == [expected]
    assert result[0].name == "HSMD1算法芯片数据手册\u00a0V2.4-兴唐通信科技有限公司.pdf"


def test_scan_keywords_deduplicates_and_uses_highest_severity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = tmp_path / "机密密码.txt"
    file.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        everything,
        "get_status",
        lambda es=None: everything.EverythingStatus("es.exe", "1.1.0.37", "1.4.1.1032"),
    )
    monkeypatch.setattr(everything, "search_keyword", lambda *args, **kwargs: [file])

    items = everything.scan_keywords(
        {"high": ["机密"], "sensitive": ["密码"]},
        ["txt"],
    )
    assert len(items) == 1
    assert set(items[0]["matched_keywords"]) == {"机密", "密码"}
    assert items[0]["severity"] == "high"
    assert items[0]["accessible"] is True


def test_get_status_rejects_non_14(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    es = tmp_path / "es.exe"
    es.write_bytes(b"")
    monkeypatch.setattr(everything, "find_es", lambda explicit=None: es)

    def fake_run(es_path: Path, args: list[str], timeout: int = 30, *, argv_mode: bool = False) -> str:
        if args == ["-version"]:
            return "1.1.0.37"
        return "1.5.0.1423b"

    monkeypatch.setattr(everything, "_run", fake_run)
    with pytest.raises(everything.EverythingError, match="1.4.x"):
        everything.get_status()


def test_get_status_rejects_old_es(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    es = tmp_path / "es.exe"
    es.write_bytes(b"")
    monkeypatch.setattr(everything, "find_es", lambda explicit=None: es)

    def fake_run(es_path: Path, args: list[str], timeout: int = 30, *, argv_mode: bool = False) -> str:
        if args == ["-version"]:
            return "1.1.0.36"
        return "1.4.1.877"

    monkeypatch.setattr(everything, "_run", fake_run)
    with pytest.raises(everything.EverythingError, match="1.1.0.37"):
        everything.get_status()


def test_keyword_with_quote_is_rejected() -> None:
    with pytest.raises(ValueError):
        everything._safe_keyword('bad"query')


def test_indexed_but_inaccessible_result_is_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "indexed-but-currently-unavailable.txt"
    monkeypatch.setattr(everything, "_run_export_txt", lambda *args, **kwargs: str(missing))
    result = everything.search_keyword(Path("es.exe"), "unavailable", ["txt"])
    assert result == [missing]
