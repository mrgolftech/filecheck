from __future__ import annotations

from types import SimpleNamespace

from filecheck.gui import entry


def test_admin_detection_returns_true_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(entry.os, "name", "posix")
    assert entry.is_windows_admin() is True


def test_admin_detection_uses_windows_shell32(monkeypatch) -> None:
    monkeypatch.setattr(entry.os, "name", "nt")
    monkeypatch.setattr(
        entry.ctypes,
        "windll",
        SimpleNamespace(shell32=SimpleNamespace(IsUserAnAdmin=lambda: 1)),
        raising=False,
    )
    assert entry.is_windows_admin() is True

    monkeypatch.setattr(
        entry.ctypes,
        "windll",
        SimpleNamespace(shell32=SimpleNamespace(IsUserAnAdmin=lambda: 0)),
        raising=False,
    )
    assert entry.is_windows_admin() is False
