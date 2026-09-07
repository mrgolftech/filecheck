from __future__ import annotations

from pathlib import Path

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

    def fake_run(es_path: Path, args: list[str], timeout: int = 30) -> str:
        captured["args"] = args
        return f"{inside}\n{outside}\n"

    monkeypatch.setattr(everything, "_run", fake_run)
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
    assert "-p" in args
    assert "-path" in args
    assert "/a-d" in args
    assert "-full-path" in args
    assert '"机密" ext:txt;docx' in args


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

    def fake_run(es_path: Path, args: list[str], timeout: int = 30) -> str:
        if args == ["-version"]:
            return "1.1.0.37"
        return "1.5.0.1423b"

    monkeypatch.setattr(everything, "_run", fake_run)
    with pytest.raises(everything.EverythingError, match="1.4.x"):
        everything.get_status()


def test_keyword_with_quote_is_rejected() -> None:
    with pytest.raises(ValueError):
        everything._safe_keyword('bad"query')


def test_indexed_but_inaccessible_result_is_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "indexed-but-currently-unavailable.txt"
    monkeypatch.setattr(everything, "_run", lambda *args, **kwargs: str(missing))
    result = everything.search_keyword(Path("es.exe"), "unavailable", ["txt"])
    assert result == [missing]
