from __future__ import annotations

import ctypes
import os
import sys

from . import cli as legacy_cli
from . import db_persistence
from . import fast_index
from . import menu
from . import resilient_cli
from . import restore_reporting
from . import resume_ui


# Install the Everything database-path/persistence fix before routing commands.
# The dedicated named instance stores its DB in runtime\everything and flushes
# the database to disk after a successful rebuild.
db_persistence.install()

# Route command execution and resume handling through the hardened v0.1.1
# implementations while keeping menu.py as the coherent user-facing workflow.
fast_index.configure_and_reindex = db_persistence.configure_and_reindex
legacy_cli.ensure_instance = db_persistence.ensure_instance
legacy_cli.cmd_index = fast_index.cmd_index
legacy_cli.cmd_restore = restore_reporting.cmd_restore
menu.cli = resilient_cli
menu._environment_and_index_flow = fast_index.environment_and_index_flow
menu._resume_flow = resume_ui.menu_resume_flow

# A blank ENTER at the top-level menu must not silently choose item 1.  Rebuild
# is destructive to the current in-memory index state and can take noticeable
# time; requiring an explicit menu number also prevents an error -> ENTER ->
# rebuild cycle from looking like an indexing loop.
_original_menu_ask_choice = menu._ask_choice


def _safe_menu_choice(prompt: str, allowed: set[str], *, default: str | None = None) -> str:
    if prompt == "请选择功能" and default == "1":
        default = None
    return _original_menu_ask_choice(prompt, allowed, default=default)


menu._ask_choice = _safe_menu_choice


def _is_windows_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _require_admin_for_interactive_start(argv: list[str]) -> bool:
    """Guard the normal double-click/menu workflow before file operations.

    Advanced subcommands (for example ``--help`` and ``selftest``) stay callable
    without elevation so diagnostics and CI can still run headlessly.
    """
    if argv or os.name != "nt" or _is_windows_admin():
        return True

    print()
    print("=" * 62)
    print("FileCheck 需要使用管理员权限运行")
    print("=" * 62)
    print("原因：NTFS 快速索引需要读取 MFT / USN，源文件删除与恢复也可能")
    print("涉及受保护目录。为避免索引不完整或操作失败，请使用管理员权限启动。")
    print()
    print("请关闭本窗口，然后：")
    print("  右键 FileCheck.exe -> 以管理员身份运行")
    print()
    try:
        input("按回车键退出...")
    except (EOFError, KeyboardInterrupt):
        pass
    return False


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if not _require_admin_for_interactive_start(effective_argv):
        return 5
    return menu.main(effective_argv)


if __name__ == "__main__":
    raise SystemExit(main())
