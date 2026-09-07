from __future__ import annotations

from pathlib import Path

import filecheck.everything as everything


def test_frozen_release_prefers_bundled_es_next_to_executable(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "FileCheck-win64"
    tools = package / "tools"
    tools.mkdir(parents=True)
    bundled = tools / "es.exe"
    bundled.write_bytes(b"placeholder")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv("FILECHECK_ES", raising=False)
    monkeypatch.setattr(everything.sys, "frozen", True, raising=False)
    monkeypatch.setattr(everything.sys, "executable", str(package / "FileCheck.exe"))
    monkeypatch.setattr(everything.shutil, "which", lambda _name: None)

    assert everything.find_es() == bundled
