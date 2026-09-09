from __future__ import annotations

from filecheck.gui import path_widgets


def test_reveal_path_opens_exact_containing_folder_on_windows(tmp_path, monkeypatch) -> None:
    batch = tmp_path / "FC-20260909-120000-demo"
    batch.mkdir()
    state_file = batch / "source-removal.json"
    state_file.write_text("{}", encoding="utf-8")

    opened = []
    monkeypatch.setattr(path_widgets, "_is_windows", lambda: True)
    monkeypatch.setattr(path_widgets.os, "startfile", lambda value: opened.append(value), raising=False)

    path_widgets.reveal_path(str(state_file))

    assert opened == [str(batch.resolve())]


def test_repository_link_has_no_embedded_icon() -> None:
    from filecheck.gui import repository_link

    assert not hasattr(repository_link, "_GITHUB_ICON_PNG")
