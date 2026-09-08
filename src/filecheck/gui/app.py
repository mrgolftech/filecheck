from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import customtkinter as ctk

from .backup_page import BackupPage
from .backup_service import BackupPreflight, BackupRequest, BackupResult, preflight_backup, run_backup, suggested_destination
from .components import SidebarButton, StatusPill
from .home_page import HomePage
from .index_service import IndexBuildResult, load_index_context, run_index_build
from .migration_page import MigrationPage
from .migration_service import (
    RemovalPreflight,
    RemovalResult,
    inspect_removal_target,
    run_removal_preflight,
    run_resume_removal,
    run_source_removal,
)
from .pages import ResultPage
from .restore_page import RestorePage
from .restore_service import RestorePreflight, RestoreResult, inspect_restore_target, run_restore, run_restore_preflight
from .scan_page import ScanPage
from .scan_service import ScanRequest, ScanResult, load_context, run_scan
from .settings_page import SettingsPage
from .settings_service import load_settings, save_settings
from .task_runner import TaskEvent, TaskRunner
from .tokens import Layout, Palette, Spacing, Typography


class FileCheckApp(ctk.CTk):
    PAGE_TITLES = {
        "home": "首页",
        "scan": "扫描",
        "results": "扫描结果",
        "backup": "备份",
        "migration": "源文件删除",
        "restore": "恢复",
        "settings": "设置",
    }

    def __init__(self):
        ctk.set_appearance_mode("light")
        super().__init__()
        self.title("FileCheck 文件检查与备份工具")
        self.geometry(f"{Layout.WINDOW_WIDTH}x{Layout.WINDOW_HEIGHT}")
        self.minsize(Layout.MIN_WIDTH, Layout.MIN_HEIGHT)
        self.configure(fg_color=Palette.BG)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._nav_buttons: Dict[str, SidebarButton] = {}
        self._pages: Dict[str, ctk.CTkFrame] = {}
        self._task_runner = TaskRunner()
        self._active_task: Optional[str] = None
        self._last_scan_result: Optional[ScanResult] = None
        self._last_backup_preflight: Optional[BackupPreflight] = None
        self._last_backup_result: Optional[BackupResult] = None
        self._last_removal_preflight: Optional[RemovalPreflight] = None
        self._last_restore_preflight: Optional[RestorePreflight] = None

        self._build_sidebar()
        self._build_content()
        self._refresh_all_contexts()
        self.show_page("home")
        self.after(100, self._poll_task_events)

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(
            self,
            width=Layout.SIDEBAR_WIDTH,
            fg_color=Palette.SURFACE,
            corner_radius=0,
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(8, weight=1)
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=Spacing.LG, pady=(Spacing.LG, Spacing.XL))
        ctk.CTkLabel(brand, text="FileCheck", text_color=Palette.TEXT, font=Typography.SECTION_TITLE, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="文件检查与备份工具",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
        ).pack(anchor="w", pady=(Spacing.XXS, 0))
        for row, (name, title) in enumerate(self.PAGE_TITLES.items(), start=1):
            button = SidebarButton(sidebar, title, command=lambda page=name: self.show_page(page))
            button.grid(row=row, column=0, sticky="ew", padx=Spacing.SM, pady=Spacing.XXS)
            self._nav_buttons[name] = button

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=9, column=0, sticky="sew", padx=Spacing.LG, pady=Spacing.LG)
        ctk.CTkLabel(
            footer,
            text="FileCheckV0.1",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            footer,
            text="Design By David @ 2026",
            text_color=Palette.TEXT_MUTED,
            font=Typography.SMALL,
            anchor="w",
        ).pack(anchor="w", pady=(Spacing.XXS, 0))

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=Palette.BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        page_host = ctk.CTkFrame(self.content, fg_color="transparent", corner_radius=0)
        page_host.grid(row=0, column=0, sticky="nsew", padx=Layout.PAGE_PADDING, pady=(Layout.PAGE_PADDING, Spacing.MD))
        page_host.grid_rowconfigure(0, weight=1)
        page_host.grid_columnconfigure(0, weight=1)

        self._pages = {
            "home": HomePage(page_host, self.show_page),
            "scan": ScanPage(
                page_host,
                self._start_index_build,
                self._start_scan,
                self._cancel_task,
                lambda: self.show_page("settings"),
            ),
            "results": ResultPage(page_host),
            "backup": BackupPage(
                page_host,
                self._start_backup_preflight,
                self._start_backup,
                self._cancel_task,
                lambda: self.show_page("settings"),
            ),
            "migration": MigrationPage(
                page_host,
                self._load_removal_target,
                self._start_removal_preflight,
                self._start_removal,
                self._resume_removal,
                self._cancel_task,
            ),
            "restore": RestorePage(
                page_host,
                self._load_restore_target,
                self._start_restore_preflight,
                self._start_restore,
                self._cancel_task,
            ),
            "settings": SettingsPage(page_host, self._save_settings),
        }
        for page in self._pages.values():
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()

        status_bar = ctk.CTkFrame(self.content, fg_color="transparent", corner_radius=0)
        status_bar.grid(row=1, column=0, sticky="ew", padx=Layout.PAGE_PADDING, pady=(0, Spacing.MD))
        status_bar.grid_columnconfigure(0, weight=1)
        self.status_text = ctk.CTkLabel(
            status_bar,
            text="界面已就绪",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
        )
        self.status_text.grid(row=0, column=0, sticky="w")
        self.status_pill = StatusPill(status_bar, "就绪", tone="success")
        self.status_pill.grid(row=0, column=1, sticky="e")

    def _refresh_all_contexts(self) -> None:
        self._refresh_settings_context()
        self._refresh_scan_context()
        self._refresh_backup_context()
        self._refresh_home_context()

    def _refresh_settings_context(self) -> None:
        page = self._pages.get("settings")
        if not isinstance(page, SettingsPage):
            return
        try:
            page.set_values(load_settings())
        except Exception as exc:
            page.save_error(f"设置读取失败：{exc}")

    def _refresh_scan_context(self) -> None:
        page = self._pages.get("scan")
        if not isinstance(page, ScanPage):
            return
        try:
            page.set_context(load_context(), load_index_context())
        except Exception as exc:
            page.finish_error(f"扫描环境读取失败：{exc}")

    def _refresh_backup_context(self) -> None:
        page = self._pages.get("backup")
        if isinstance(page, BackupPage):
            try:
                page.set_suggested_destination(suggested_destination())
            except Exception:
                page.set_suggested_destination(None)

    def _refresh_home_context(self) -> None:
        page = self._pages.get("home")
        if not isinstance(page, HomePage):
            return
        try:
            settings = load_settings()
            index = load_index_context()
            page.set_context(
                settings.backup_root or None,
                index.selected_roots,
                sum(len(values) for values in settings.keywords.values()),
                len(settings.extensions),
            )
        except Exception:
            pass

    def _save_settings(self, backup_root, keywords, extensions) -> None:
        page = self._pages.get("settings")
        if not isinstance(page, SettingsPage):
            return
        try:
            data = save_settings(backup_root, keywords, extensions)
        except Exception as exc:
            page.save_error(str(exc))
            self.set_status(f"设置保存失败：{exc}", "danger")
            return
        page.saved(data)
        self._last_backup_preflight = None
        self._refresh_scan_context()
        self._refresh_backup_context()
        self._refresh_home_context()
        self.set_status("设置已保存；若备份目录发生变化，建议重新创建索引", "success")

    def _busy(self) -> bool:
        return self._task_runner.busy or self._active_task is not None

    def _start_index_build(self, selected_roots) -> None:
        page = self._pages.get("scan")
        if not isinstance(page, ScanPage):
            return
        if self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        if not selected_roots:
            page.finish_error("请至少选择一个需要扫描的磁盘")
            self.set_status("请选择需要扫描的磁盘", "warning")
            return
        self._active_task = "index"
        if not self._task_runner.start("创建索引", lambda task: run_index_build(list(selected_roots), task)):
            self._active_task = None
            return
        page.begin_index()
        self.set_status("正在创建 FileCheck 专用索引", "info")

    def _start_scan(self) -> None:
        page = self._pages.get("scan")
        if not isinstance(page, ScanPage) or self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        self._active_task = "scan"
        if not self._task_runner.start("扫描", lambda task: run_scan(ScanRequest(), task)):
            self._active_task = None
            return
        page.begin_scan()
        self.set_status("扫描任务正在后台运行", "info")

    def _start_backup_preflight(self, destination: str) -> None:
        page = self._pages.get("backup")
        if not isinstance(page, BackupPage) or self._last_scan_result is None:
            self.set_status("请先完成一次扫描，再执行备份预检", "warning")
            return
        if self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        request = BackupRequest(scan_result=self._last_scan_result, destination_root=destination)
        self._last_backup_preflight = None
        self._active_task = "backup_preflight"
        if not self._task_runner.start("备份预检", lambda task: preflight_backup(request, task)):
            self._active_task = None
            return
        page.begin_preflight()
        self.set_status("正在检查备份条件", "info")

    def _start_backup(self, destination: str) -> None:
        page = self._pages.get("backup")
        if not isinstance(page, BackupPage) or self._last_scan_result is None or self._last_backup_preflight is None:
            self.set_status("请先完成备份预检", "warning")
            return
        if self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        try:
            resolved = Path(destination).expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            page.finish_error(str(exc))
            return
        if resolved != self._last_backup_preflight.destination_root:
            self._last_backup_preflight = None
            page.finish_error("备份目标已变化，请重新执行预检")
            return
        request = BackupRequest(scan_result=self._last_scan_result, destination_root=destination)
        self._active_task = "backup"
        if not self._task_runner.start("创建备份", lambda task: run_backup(request, task)):
            self._active_task = None
            return
        page.begin_backup()
        self.set_status("正在创建并校验备份", "info")

    def _load_removal_target(self, value: str, quiet: bool = False) -> None:
        page = self._pages.get("migration")
        if not isinstance(page, MigrationPage):
            return
        try:
            info = inspect_removal_target(value)
        except Exception as exc:
            page.load_error(str(exc))
            if not quiet:
                self.set_status(f"载入备份失败：{exc}", "danger")
            return
        self._last_removal_preflight = None
        page.set_info(info)
        if not quiet:
            self.set_status(f"已载入备份批次：{info.batch_id}", "success")

    def _start_removal_preflight(self, value: str) -> None:
        page = self._pages.get("migration")
        if not isinstance(page, MigrationPage) or self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        self._last_removal_preflight = None
        self._active_task = "removal_preflight"
        if not self._task_runner.start("删除前复核", lambda task: run_removal_preflight(value, task)):
            self._active_task = None
            return
        page.begin_preflight()
        self.set_status("正在执行删除前安全复核", "info")

    def _start_removal(self, value: str) -> None:
        page = self._pages.get("migration")
        if not isinstance(page, MigrationPage) or self._last_removal_preflight is None:
            self.set_status("请先完成删除前安全复核", "warning")
            return
        if self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        if Path(value).expanduser().resolve() != self._last_removal_preflight.backup_path:
            self._last_removal_preflight = None
            page.finish_error("备份目标已变化，请重新执行删除前复核")
            return
        self._active_task = "removal"
        if not self._task_runner.start("删除源文件", lambda task: run_source_removal(value, task)):
            self._active_task = None
            return
        page.begin_removal(False)
        self.set_status("正在安全删除源文件", "info")

    def _resume_removal(self, value: str) -> None:
        page = self._pages.get("migration")
        if not isinstance(page, MigrationPage) or self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        self._last_removal_preflight = None
        self._active_task = "removal_resume"
        if not self._task_runner.start("继续源文件删除", lambda task: run_resume_removal(value, task)):
            self._active_task = None
            return
        page.begin_removal(True)
        self.set_status("正在继续源文件删除", "info")

    def _load_restore_target(self, value: str, quiet: bool = False) -> None:
        page = self._pages.get("restore")
        if not isinstance(page, RestorePage):
            return
        try:
            info = inspect_restore_target(value)
        except Exception as exc:
            page.load_error(str(exc))
            if not quiet:
                self.set_status(f"载入恢复备份失败：{exc}", "danger")
            return
        self._last_restore_preflight = None
        page.set_info(info)
        if not quiet:
            self.set_status(f"已载入恢复批次：{info.batch_id}", "success")

    def _start_restore_preflight(self, value: str, conflict: str) -> None:
        page = self._pages.get("restore")
        if not isinstance(page, RestorePage) or self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        self._last_restore_preflight = None
        self._active_task = "restore_preflight"
        if not self._task_runner.start("恢复预检", lambda task: run_restore_preflight(value, conflict, task)):
            self._active_task = None
            return
        page.begin_preflight()
        self.set_status("正在验证备份和恢复目标", "info")

    def _start_restore(self, value: str, conflict: str) -> None:
        page = self._pages.get("restore")
        if not isinstance(page, RestorePage) or self._last_restore_preflight is None:
            self.set_status("请先完成恢复预检", "warning")
            return
        if self._busy():
            self.set_status("已有后台任务正在运行", "warning")
            return
        resolved = Path(value).expanduser().resolve()
        if resolved != self._last_restore_preflight.backup_path or conflict != self._last_restore_preflight.conflict:
            self._last_restore_preflight = None
            page.finish_error("恢复备份或冲突策略已变化，请重新执行恢复预检")
            return
        self._active_task = "restore"
        if not self._task_runner.start("恢复文件", lambda task: run_restore(value, conflict, task)):
            self._active_task = None
            return
        page.begin_restore()
        self.set_status("正在恢复并校验文件", "info")

    def _cancel_task(self) -> None:
        if self._task_runner.busy:
            self._task_runner.cancel()
            self.set_status("已请求取消当前任务", "warning")

    def _poll_task_events(self) -> None:
        try:
            for event in self._task_runner.drain_events():
                self._handle_task_event(event)
        finally:
            self.after(100, self._poll_task_events)

    def _handle_task_event(self, event: TaskEvent) -> None:
        active = self._active_task
        scan_page = self._pages.get("scan")
        backup_page = self._pages.get("backup")
        migration_page = self._pages.get("migration")
        restore_page = self._pages.get("restore")

        if event.kind == "started":
            labels = {
                "index": "索引创建正在执行",
                "scan": "扫描任务正在执行",
                "backup_preflight": "备份预检正在执行",
                "backup": "备份任务正在执行",
                "removal_preflight": "删除前安全复核正在执行",
                "removal": "源文件删除正在执行",
                "removal_resume": "源文件继续删除正在执行",
                "restore_preflight": "恢复预检正在执行",
                "restore": "文件恢复正在执行",
            }
            self.set_status(labels.get(active, "后台任务正在执行"), "info")
            return

        if event.kind == "log":
            if active in ("index", "scan") and isinstance(scan_page, ScanPage):
                scan_page.append_log(event.message)
            elif active in ("backup_preflight", "backup") and isinstance(backup_page, BackupPage):
                backup_page.append_log(event.message)
            elif active in ("removal_preflight", "removal", "removal_resume") and isinstance(migration_page, MigrationPage):
                migration_page.append_log(event.message)
            elif active in ("restore_preflight", "restore") and isinstance(restore_page, RestorePage):
                restore_page.append_log(event.message)
            return

        if event.kind == "progress":
            if active in ("index", "scan") and isinstance(scan_page, ScanPage):
                scan_page.update_progress(event.progress, event.message)
            elif active in ("backup_preflight", "backup") and isinstance(backup_page, BackupPage):
                backup_page.update_progress(event.progress, event.message)
            elif active in ("removal_preflight", "removal", "removal_resume") and isinstance(migration_page, MigrationPage):
                migration_page.update_progress(event.progress, event.message)
            elif active in ("restore_preflight", "restore") and isinstance(restore_page, RestorePage):
                restore_page.update_progress(event.progress, event.message)
            return

        if event.kind == "success":
            if active == "index" and isinstance(event.payload, IndexBuildResult):
                if isinstance(scan_page, ScanPage):
                    scan_page.finish_index(event.payload)
                self._refresh_scan_context()
                self._refresh_home_context()
                self.set_status(f"索引创建完成：{'、'.join(event.payload.selected_roots)}", "success")
            elif active == "scan" and isinstance(event.payload, ScanResult):
                result = event.payload
                self._last_scan_result = result
                self._last_backup_preflight = None
                if isinstance(scan_page, ScanPage):
                    scan_page.finish_scan(result.counts.get("total", 0))
                result_page = self._pages.get("results")
                if isinstance(result_page, ResultPage):
                    result_page.set_result(result)
                if isinstance(backup_page, BackupPage):
                    backup_page.set_scan_result(result)
                self.show_page("results")
                self.set_status(f"扫描完成：{result.counts.get('total', 0)} 个候选文件", "success")
            elif active == "backup_preflight" and isinstance(event.payload, BackupPreflight):
                self._last_backup_preflight = event.payload
                if isinstance(backup_page, BackupPage):
                    backup_page.finish_preflight(event.payload)
                self.set_status(f"备份预检通过：{event.payload.file_count} 个文件", "success")
            elif active == "backup" and isinstance(event.payload, BackupResult):
                self._last_backup_result = event.payload
                self._last_backup_preflight = None
                if isinstance(backup_page, BackupPage):
                    backup_page.finish_backup(event.payload)
                if isinstance(migration_page, MigrationPage):
                    migration_page.set_target(event.payload.backup_path)
                    self._load_removal_target(str(event.payload.backup_path), quiet=True)
                if isinstance(restore_page, RestorePage):
                    restore_page.set_target(event.payload.backup_path)
                    self._load_restore_target(str(event.payload.backup_path), quiet=True)
                self.set_status(f"备份完成并校验通过：{event.payload.file_count} 个文件", "success")
            elif active == "removal_preflight" and isinstance(event.payload, RemovalPreflight):
                self._last_removal_preflight = event.payload
                if isinstance(migration_page, MigrationPage):
                    migration_page.finish_preflight(event.payload)
                self.set_status(f"删除前安全复核通过：{event.payload.file_count} 个文件", "success")
            elif active in ("removal", "removal_resume") and isinstance(event.payload, RemovalResult):
                self._last_removal_preflight = None
                if isinstance(migration_page, MigrationPage):
                    migration_page.finish_result(event.payload)
                    self._load_removal_target(str(event.payload.backup_path), quiet=True)
                tone = "success" if event.payload.status == "completed" else "warning"
                self.set_status(f"源文件删除：deleted={event.payload.deleted}, failed={event.payload.failed}", tone)
            elif active == "restore_preflight" and isinstance(event.payload, RestorePreflight):
                self._last_restore_preflight = event.payload
                if isinstance(restore_page, RestorePage):
                    restore_page.finish_preflight(event.payload)
                self.set_status(
                    f"恢复预检通过：冲突 {event.payload.conflicts} 个",
                    "success" if not event.payload.conflicts else "warning",
                )
            elif active == "restore" and isinstance(event.payload, RestoreResult):
                self._last_restore_preflight = None
                if isinstance(restore_page, RestorePage):
                    restore_page.finish_result(event.payload)
                self.set_status(f"恢复完成：restored={event.payload.restored}, skipped={event.payload.skipped}", "success")
            self._active_task = None
            return

        if event.kind == "cancelled":
            if active in ("index", "scan") and isinstance(scan_page, ScanPage):
                scan_page.finish_cancelled()
                self._refresh_scan_context()
            elif active in ("backup_preflight", "backup") and isinstance(backup_page, BackupPage):
                backup_page.finish_cancelled()
                self._last_backup_preflight = None
            elif active in ("removal_preflight", "removal", "removal_resume") and isinstance(migration_page, MigrationPage):
                migration_page.finish_cancelled()
                self._last_removal_preflight = None
                target = migration_page.backup_path.get().strip()
                if target:
                    self._load_removal_target(target, quiet=True)
            elif active in ("restore_preflight", "restore") and isinstance(restore_page, RestorePage):
                restore_page.finish_cancelled()
                self._last_restore_preflight = None
            self.set_status(event.message or "任务已安全取消", "warning")
            self._active_task = None
            return

        if event.kind == "error":
            message = event.message or "未知错误"
            if active in ("index", "scan") and isinstance(scan_page, ScanPage):
                scan_page.finish_error(message)
                self._refresh_scan_context()
            elif active in ("backup_preflight", "backup") and isinstance(backup_page, BackupPage):
                backup_page.finish_error(message)
                self._last_backup_preflight = None
            elif active in ("removal_preflight", "removal", "removal_resume") and isinstance(migration_page, MigrationPage):
                migration_page.finish_error(message)
                self._last_removal_preflight = None
                target = migration_page.backup_path.get().strip()
                if target:
                    self._load_removal_target(target, quiet=True)
            elif active in ("restore_preflight", "restore") and isinstance(restore_page, RestorePage):
                restore_page.finish_error(message)
                self._last_restore_preflight = None
            self.set_status(f"任务失败：{message}", "danger")
            self._active_task = None

    def show_page(self, name: str) -> None:
        if name not in self._pages:
            return
        if name == "home":
            self._refresh_home_context()
        elif name == "scan":
            self._refresh_scan_context()
        elif name == "backup":
            self._refresh_backup_context()
        elif name == "settings":
            self._refresh_settings_context()
        for page_name, page in self._pages.items():
            if page_name == name:
                page.grid()
                page.tkraise()
            else:
                page.grid_remove()
        for page_name, button in self._nav_buttons.items():
            button.set_active(page_name == name)
        self.set_status(f"当前页面：{self.PAGE_TITLES[name]}", "neutral")

    def set_status(self, message: str, tone: str = "neutral") -> None:
        self.status_text.configure(text=message)
        labels = {"neutral": "就绪", "info": "执行中", "success": "完成", "warning": "注意", "danger": "异常"}
        self.status_pill.set_tone(tone, labels.get(tone, "就绪"))


def main() -> int:
    app = FileCheckApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
