from __future__ import annotations

import ctypes
import os
from tkinter import messagebox

import customtkinter as ctk

from .app import FileCheckApp
from .settings_service import current_appearance


def is_windows_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _install_admin_guards(is_admin: bool) -> None:
    if is_admin or getattr(FileCheckApp, "_filecheck_admin_guards", False):
        return

    original_index = FileCheckApp._start_index_build
    original_remove = FileCheckApp._start_removal
    original_resume = FileCheckApp._resume_removal
    original_restore = FileCheckApp._start_restore

    def guarded_index(self, selected_roots) -> None:
        self.set_status("创建 NTFS 快速索引需要管理员权限，请以管理员身份重新运行 FileCheck", "danger")
        page = self._pages.get("scan")
        if page is not None and hasattr(page, "finish_error"):
            page.finish_error("当前不是管理员模式，无法创建/更新 NTFS 快速索引。请以管理员身份重新运行。")

    def guarded_remove(self, value: str) -> None:
        self.set_status("源文件删除需要管理员权限，请以管理员身份重新运行 FileCheck", "danger")
        page = self._pages.get("migration")
        if page is not None and hasattr(page, "finish_error"):
            page.finish_error("当前不是管理员模式，已阻止源文件删除。")

    def guarded_resume(self, value: str) -> None:
        self.set_status("继续源文件删除需要管理员权限，请以管理员身份重新运行 FileCheck", "danger")
        page = self._pages.get("migration")
        if page is not None and hasattr(page, "finish_error"):
            page.finish_error("当前不是管理员模式，已阻止继续删除。")

    def guarded_restore(self, value: str, conflict: str) -> None:
        if str(conflict).strip().lower() == "overwrite":
            self.set_status("覆盖恢复需要管理员权限，请以管理员身份重新运行 FileCheck", "danger")
            page = self._pages.get("restore")
            if page is not None and hasattr(page, "finish_error"):
                page.finish_error("当前不是管理员模式，已阻止覆盖已有文件。可改用“跳过”或“重命名”，或重新以管理员身份运行。")
            return
        original_restore(self, value, conflict)

    # Patch before FileCheckApp is instantiated so page callbacks capture the
    # guarded methods instead of the original bound methods.
    FileCheckApp._start_index_build = guarded_index
    FileCheckApp._start_removal = guarded_remove
    FileCheckApp._resume_removal = guarded_resume
    FileCheckApp._start_restore = guarded_restore
    FileCheckApp._filecheck_admin_guards = True
    FileCheckApp._filecheck_original_admin_methods = (
        original_index,
        original_remove,
        original_resume,
        original_restore,
    )


def create_app() -> FileCheckApp:
    admin = is_windows_admin()
    _install_admin_guards(admin)
    app = FileCheckApp()
    ctk.set_appearance_mode(current_appearance())
    app._filecheck_is_admin = admin
    base_title = app.title()
    app.title(f"{base_title} [{'管理员' if admin else '非管理员'}]")
    if admin:
        app.set_status("管理员模式已检测，索引/删除/覆盖恢复权限可用", "success")
    else:
        app.set_status("当前为非管理员模式：索引创建、源文件删除和覆盖恢复已禁用", "warning")

        def show_warning() -> None:
            try:
                messagebox.showwarning(
                    "FileCheck 权限提示",
                    "当前 FileCheck 未以管理员身份运行。\n\n"
                    "可继续查看、扫描已有索引、备份以及使用非覆盖恢复；\n"
                    "创建/更新 NTFS 索引、源文件删除和覆盖恢复已被禁用。\n\n"
                    "需要完整功能时，请关闭程序后右键 FileCheck-GUI.exe，选择“以管理员身份运行”。",
                    parent=app,
                )
            except Exception:
                pass

        app.after(250, show_warning)
    return app


def main() -> int:
    app = create_app()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
