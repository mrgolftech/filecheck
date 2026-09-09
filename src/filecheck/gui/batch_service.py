from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .settings_service import current_backup_root


@dataclass(frozen=True)
class BackupBatchOption:
    name: str
    path: Path


def discover_backup_batches(root: Optional[str] = None) -> List[BackupBatchOption]:
    """Return direct child backup batches, newest-looking folder name first.

    Discovery is intentionally lightweight: a directory qualifies when it is a
    direct child of the configured backup root and contains manifest.json.
    Full manifest/SHA-256 validation remains the responsibility of the removal
    or restore preflight for the selected batch.
    """
    root_text = str(root or current_backup_root() or "").strip()
    if not root_text:
        return []
    backup_root = Path(root_text).expanduser()
    try:
        if not backup_root.is_dir():
            return []
        candidates = [
            child
            for child in backup_root.iterdir()
            if child.is_dir() and (child / "manifest.json").is_file()
        ]
    except OSError:
        return []

    candidates.sort(key=lambda value: value.name.lower(), reverse=True)
    return [BackupBatchOption(name=path.name, path=path.resolve()) for path in candidates]


def latest_backup_batch(root: Optional[str] = None) -> Optional[Path]:
    batches = discover_backup_batches(root)
    return batches[0].path if batches else None
