"""Shared, safety-preserving source-file deletion for GUI and CLI.

Only the Windows read-only/write-protect bit is cleared before unlinking.
No ownership, ACL or other file attributes are overridden. If unlink fails,
the original read-only state is restored where possible.
"""
from __future__ import annotations

import stat
from pathlib import Path


def unlink_ignoring_readonly(source: Path) -> None:
    """Remove a previously verified source file, including read-only files."""
    original_mode = source.stat().st_mode
    changed_readonly = not bool(original_mode & stat.S_IWRITE)
    if changed_readonly:
        source.chmod(original_mode | stat.S_IWRITE)
    try:
        source.unlink()
    except OSError:
        if changed_readonly:
            try:
                if source.exists():
                    source.chmod(original_mode)
            except OSError:
                pass
        raise
