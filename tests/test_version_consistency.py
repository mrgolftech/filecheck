from __future__ import annotations

import re
from pathlib import Path

from filecheck import __version__


def test_pyproject_version_matches_package_version() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"(?ms)^\[project\]\s*$.*?^version\s*=\s*\"([^\"]+)\"\s*$", pyproject)
    assert match is not None
    assert match.group(1) == __version__
