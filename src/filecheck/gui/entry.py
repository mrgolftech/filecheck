from __future__ import annotations

import ctypes
import os
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from filecheck import __version__

from .app import FileCheckApp
from .settings_service import current_appearance
from .tokens import Palette, Spacing, Typography


REPOSITORY_URL = "https://github.com/mrgolftech/filecheck"
PRODUCT_LABEL = f"FileCheck v{__version__}"
DESIGN_CREDIT = "Designed by David © 2026"


def is_windows_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _invalidate_scan_basis(app: FileCheckApp, message: str) -> None:
    app._last_scan_result = None
    app._last_backup_preflight = None
    result_page = app._pages.get("results")
    if result_page is not None and hasattr(result_page, "clear_result"):
        result_page.clear_result(message)
    backup_page = app._pages.get("backup")
    if backup_page is not None and hasattr(backup_page, "clear_scan_result"):
        backup_page.clear_scan_result(message)
    try:
        app.event_generate("<<FileCheckScanBasisChanged>>", when="tail")
    except Exception:
        pass


def _walk_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk_widgets(child)


def _apply_product_identity(app: FileCheckApp) -> None:
    """Keep visible version/credit in sync with the packaged FileCheck version."""
    app.title(f"{PRODUCT_LABEL} 文件检查与备份工具")
    footer = None
    for widget in _walk_widgets(app):
        if not isinstance(widget, ctk.CTkLabel):
            continue
        try:
            text = str(widget.cget("text"))
        except Exception:
            continue
        if text == "FileCheckV0.1":
            widget.configure(text=PRODUCT_LABEL)
            footer = widget.master
        elif text == "Design By David @ 2026":
            widget.configure(text=DESIGN_CREDIT)
            footer = widget.master
    if footer is None:
        return
    repository_label = ctk.CTkLabel(
        footer,
        text="github.com/mrgolftech/filecheck",
        text_color=Palette.PRIMARY,
        font=Typography.SMALL,
        anchor="w",
        cursor="hand2",
    )
    repository_label.pack(anchor="w", pady=(Spacing.XXS, 0))
    repository_label.bind("<Button-1>", lambda _event: webbrowser.open_new_tab(REPOSITORY_URL))


def _install_runtime_policy(is_admin: bool) -> None:
    if getattr(FileCheckApp, "_filecheck_runtime_policy", False):
        return

    original_save = FileCheckApp._save_settings
    original_handle = FileCheckApp._handle_task_event
    original_index = FileCheckApp._start_index_build
    original_remove = FileCheckApp._start_removal
    original_resume = FileCheckApp._resume_removal
    original_restore = FileCheckApp._start_restore

    def wrapped_save(self, backup_root, keywords, extensions) -> None:
        original_save(self, backup_root, keywords, extensions)
        _invalidate_scan_basis(self, "扫描设置或备份目录已变化，旧扫描结果已失效。请重新扫描。")

    def wrapped_handle(self, event) -> None:
        active_before = self._active_task
        original_handle(self, event)
        if event.kind == "success" and active_before == "index":
            _invalidate_scan_basis(self, "索引已重新创建，旧扫描结果已失效。请重新扫描。")
        if event.kind == "success" and active_before == "restore":
            blocked = int(getattr(event.payload, "skipped_error", 0) or 0)
            if blocked:
                report = getattr(event.payload, "skipped_report", None)
                suffix = f"；清单：{report}" if report else ""
                self.set_status(f"恢复完成，但有 {blocked} 个文件无法覆盖并已跳过{suffix}", "warning")

    FileCheckApp._save_settings = wrapped_save
    FileCheckApp._handle_task_event = wrapped_handle

    if not is_admin:
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

        FileCheckApp._start_index_build = guarded_index
        FileCheckApp._start_removal = guarded_remove
        FileCheckApp._resume_removal = guarded_resume
        FileCheckApp._start_restore = guarded_restore

    FileCheckApp._filecheck_runtime_policy = True
    FileCheckApp._filecheck_original_runtime_methods = (
        original_save,
        original_handle,
        original_index,
        original_remove,
        original_resume,
        original_restore,
    )


def create_app() -> FileCheckApp:
    admin = is_windows_admin()
    _install_runtime_policy(admin)
    app = FileCheckApp()
    _apply_product_identity(app)
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
