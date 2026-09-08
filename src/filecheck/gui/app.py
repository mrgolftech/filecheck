from __future__ import annotations

import customtkinter as ctk

from .components import SidebarButton, StatusPill
from .pages import BackupPage, HomePage, RestorePage, ResultPage, ScanPage, SettingsPage
from .tokens import Layout, Palette, Spacing, Typography


class FileCheckApp(ctk.CTk):
    PAGE_TITLES = {
        "home": "首页",
        "scan": "扫描",
        "results": "扫描结果",
        "backup": "备份与迁出",
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

        self._nav_buttons: dict[str, SidebarButton] = {}
        self._pages: dict[str, ctk.CTkFrame] = {}

        self._build_sidebar()
        self._build_content()
        self.show_page("home")

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
        ctk.CTkLabel(brand, text="FileCheck", text_color=Palette.TEXT, font=Typography.SECTION_TITLE, anchor="w").pack(
            anchor="w"
        )
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
        ctk.CTkLabel(footer, text="GUI v0.1 基础框架", text_color=Palette.TEXT_MUTED, font=Typography.SMALL).pack(
            anchor="w"
        )

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
            "scan": ScanPage(page_host, self.set_status),
            "results": ResultPage(page_host),
            "backup": BackupPage(page_host, self.set_status),
            "restore": RestorePage(page_host, self.set_status),
            "settings": SettingsPage(page_host),
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

    def show_page(self, name: str) -> None:
        if name not in self._pages:
            return
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
        labels = {
            "neutral": "就绪",
            "info": "提示",
            "success": "完成",
            "warning": "注意",
            "danger": "异常",
        }
        self.status_pill.set_tone(tone, labels.get(tone, "就绪"))


def main() -> int:
    app = FileCheckApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
