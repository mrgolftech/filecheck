from __future__ import annotations

from typing import Dict

import customtkinter as ctk

from filecheck import __version__

from .app import FileCheckApp
from .backup_page import BackupPage
from .components import SidebarButton, StatusPill
from .home_page import HomePage
from .migration_page import MigrationPage
from .pages import ResultPage
from .repository_link import RepositoryLink
from .restore_page import RestorePage
from .scan_page import ScanPage
from .settings_page import SettingsPage
from .tokens import Layout, Palette, Spacing, Typography


class RuntimeFileCheckApp(FileCheckApp):
    """Production GUI shell with responsive footer identity and per-page vertical scrolling."""

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
        ctk.CTkLabel(
            brand,
            text="FileCheck",
            text_color=Palette.TEXT,
            font=Typography.SECTION_TITLE,
            anchor="w",
        ).pack(anchor="w")
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
            text=f"FileCheck v{__version__}",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            footer,
            text="Designed by David © 2026",
            text_color=Palette.TEXT_MUTED,
            font=Typography.SMALL,
            anchor="w",
        ).pack(anchor="w", pady=(Spacing.XXS, 0))
        RepositoryLink(footer).pack(anchor="w", pady=(Spacing.XS, 0))

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=Palette.BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        page_host = ctk.CTkFrame(self.content, fg_color="transparent", corner_radius=0)
        page_host.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=Layout.PAGE_PADDING,
            pady=(Layout.PAGE_PADDING, Spacing.MD),
        )
        page_host.grid_rowconfigure(0, weight=1)
        page_host.grid_columnconfigure(0, weight=1)

        self._page_shells: Dict[str, ctk.CTkScrollableFrame] = {}

        def shell(name: str) -> ctk.CTkScrollableFrame:
            value = ctk.CTkScrollableFrame(
                page_host,
                fg_color="transparent",
                corner_radius=0,
                scrollbar_button_color=Palette.BORDER,
                scrollbar_button_hover_color=Palette.TEXT_MUTED,
            )
            value.grid(row=0, column=0, sticky="nsew")
            value.grid_columnconfigure(0, weight=1)
            value.grid_remove()
            self._page_shells[name] = value
            return value

        home_shell = shell("home")
        scan_shell = shell("scan")
        results_shell = shell("results")
        backup_shell = shell("backup")
        migration_shell = shell("migration")
        restore_shell = shell("restore")
        settings_shell = shell("settings")

        self._pages = {
            "home": HomePage(home_shell, self.show_page),
            "scan": ScanPage(
                scan_shell,
                self._start_index_build,
                self._start_scan,
                self._cancel_task,
                lambda: self.show_page("settings"),
            ),
            "results": ResultPage(results_shell),
            "backup": BackupPage(
                backup_shell,
                self._start_backup_preflight,
                self._start_backup,
                self._cancel_task,
                lambda: self.show_page("settings"),
            ),
            "migration": MigrationPage(
                migration_shell,
                self._load_removal_target,
                self._start_removal_preflight,
                self._start_removal,
                self._resume_removal,
                self._cancel_task,
            ),
            "restore": RestorePage(
                restore_shell,
                self._load_restore_target,
                self._start_restore_preflight,
                self._start_restore,
                self._cancel_task,
            ),
            "settings": SettingsPage(settings_shell, self._save_settings),
        }
        for page in self._pages.values():
            # The shell owns vertical scrolling. Let the page use its natural
            # content height rather than forcing it to the viewport height.
            page.grid(row=0, column=0, sticky="ew", padx=(0, Spacing.XS), pady=(0, Spacing.MD))

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

        for page_name, shell in self._page_shells.items():
            if page_name == name:
                shell.grid()
                try:
                    shell._parent_canvas.yview_moveto(0)  # CustomTkinter 5.2.x
                except Exception:
                    pass
            else:
                shell.grid_remove()

        for page_name, button in self._nav_buttons.items():
            button.set_active(page_name == name)
        self.set_status(f"当前页面：{self.PAGE_TITLES[name]}", "neutral")
