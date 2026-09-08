from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from filecheck import db_persistence
from filecheck.portable_everything import DriveInfo, PortableIndexResult, list_windows_drives, load_index_state

from .settings_service import current_backup_root
from .task_runner import TaskContext


@dataclass(frozen=True)
class IndexContext:
    drives: List[DriveInfo]
    selected_roots: List[str]
    index_mode: str
    database_path: str
    backup_root: Optional[str]

    @property
    def ready(self) -> bool:
        return bool(self.selected_roots) and bool(self.backup_root)

    @property
    def backup_ready(self) -> bool:
        return bool(self.backup_root)


@dataclass(frozen=True)
class IndexBuildResult:
    selected_roots: List[str]
    ntfs_roots: List[str]
    folder_roots: List[str]
    database_path: str
    config_path: str
    everything_version: str
    es_version: str


def load_index_context() -> IndexContext:
    try:
        state = load_index_state(required=False) or {}
    except Exception:
        state = {}
    return IndexContext(
        drives=list_windows_drives(),
        selected_roots=[str(value) for value in state.get("selected_roots", [])],
        index_mode=str(state.get("index_mode", "未建立索引")),
        database_path=str(state.get("database_path", "")),
        backup_root=current_backup_root(),
    )


def run_index_build(selected_roots: List[str], task: TaskContext) -> IndexBuildResult:
    roots = [str(value).strip() for value in selected_roots if str(value).strip()]
    if not roots:
        raise RuntimeError("请至少选择一个需要建立索引的磁盘")
    backup_root = current_backup_root()
    if not backup_root:
        raise RuntimeError("尚未设置备份目录，请先到“设置”中配置后再创建索引")

    task.log("开始创建 FileCheck 专用 Everything 索引。")
    task.log("索引范围: " + "、".join(roots))
    task.log(f"统一备份根目录将自动排除: {backup_root}")
    task.set_progress(None, "正在配置专用 Everything 实例……")

    def progress(elapsed_seconds: float) -> None:
        task.raise_if_cancelled()
        elapsed = max(0.0, float(elapsed_seconds))
        task.set_progress(None, f"正在创建索引，已运行 {elapsed:.0f} 秒……")

    # Always use the hardened persistence wrapper.  It pins the dedicated
    # FileCheck database path and explicitly flushes the completed Everything
    # index to disk; GUI indexing must never bypass this path.
    result: PortableIndexResult = db_persistence.configure_and_reindex(
        roots,
        backup_root,
        progress=progress,
    )
    task.raise_if_cancelled()
    task.set_progress(1.0, "索引创建完成")
    task.log(f"索引数据库: {result.database_path}")
    task.log(f"Everything {result.status.everything_version} / ES {result.status.es_version}")
    return IndexBuildResult(
        selected_roots=list(result.selected_roots),
        ntfs_roots=list(result.ntfs_roots),
        folder_roots=list(result.folder_roots),
        database_path=str(result.database_path),
        config_path=str(result.config_path),
        everything_version=result.status.everything_version,
        es_version=result.status.es_version,
    )
