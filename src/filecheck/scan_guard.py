from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from .backup import find_containing_backup_batch


def filter_protected_backup_items(
    items: Iterable[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Remove scan candidates that live inside any FileCheck backup batch.

    Backup identity is structural and independent from the outer directory name,
    so this protects moved or renamed historical backups as well as the current
    configured backup root. Items without a usable path are retained so this
    safety filter never silently discards malformed/non-file scan records.
    """
    kept: List[Dict[str, Any]] = []
    protected_batches: set[str] = set()
    cache: dict[str, Path | None] = {}

    for item in items:
        path_text = str(item.get("path") or "").strip()
        if not path_text:
            kept.append(item)
            continue

        batch = find_containing_backup_batch(path_text, cache=cache)
        if batch is None:
            kept.append(item)
        else:
            protected_batches.add(str(batch))

    return kept, sorted(protected_batches, key=str.lower)
