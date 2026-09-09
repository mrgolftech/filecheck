from __future__ import annotations

from types import SimpleNamespace

from filecheck import __version__
from filecheck.gui import entry


def test_product_identity_tracks_package_release_version() -> None:
    assert entry.PRODUCT_LABEL == f"FileCheck v{__version__}"
    assert entry.DESIGN_CREDIT == "Designed by David © 2026"
    assert entry.REPOSITORY_URL == "https://github.com/mrgolftech/filecheck"


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
