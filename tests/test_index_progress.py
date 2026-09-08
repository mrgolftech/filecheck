from __future__ import annotations

from pathlib import Path

import filecheck.everything as everything


class _FakePopen:
    def __init__(self, *args, **kwargs):
        self.returncode = 0
        self.calls = 0

    def communicate(self, timeout=None):
        self.calls += 1
        if self.calls == 1:
            raise everything.subprocess.TimeoutExpired(cmd="es", timeout=timeout)
        return b"", b""

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9


def test_reindex_reports_live_progress(monkeypatch, tmp_path: Path) -> None:
    es = tmp_path / "es.exe"
    es.write_bytes(b"")
    monkeypatch.setattr(everything, "find_es", lambda explicit=None: es)
    monkeypatch.setattr(everything.subprocess, "Popen", _FakePopen)

    values: list[float] = []
    everything.reindex(instance="FileCheck", timeout=10, interval=0.01, progress=values.append)

    assert len(values) >= 2
    assert all(value >= 0 for value in values)
