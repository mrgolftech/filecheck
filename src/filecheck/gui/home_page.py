from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from .components import Card, PageHeader, SecondaryButton, StatusPill
from .tokens import Layout, Palette, Spacing, Typography


class HomePage(ctk.CTkFrame):
    def __init__(self, master, on_navigate: Callable[[str], None]):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self._on_navigate = on_navigate

        PageHeader(
            self,
            "首页",
            "按准备检查、扫描、人工核对、备份、源文件删除和恢复的顺序完成终端文件自查。",
        ).grid(row=0, column=0, sticky="ew")

        prep = Card(self)
        prep.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        prep.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(prep, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="正式扫描前建议先人工准备",
            text_color=Palette.TEXT,
            font=Typography.CARD_TITLE,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        StatusPill(header, "不会自动清理", tone="warning").grid(row=0, column=1, sticky="e")

        preparation_text = (
            "1. 清空 Windows 回收站\n"
            "2. Win + R → %temp%：删除当前用户临时文件，占用中的文件可跳过\n"
            "3. Win + R → C:\\Windows\\Temp：删除系统临时文件，占用中的文件可跳过\n"
            "4. Win + R → recent：清理最近使用快捷方式\n"
            "5. 清理 %APPDATA%\\Microsoft\\Windows\\Recent\\AutomaticDestinations\n"
            "6. 清理 %APPDATA%\\Microsoft\\Windows\\Recent\\CustomDestinations"
        )
        ctk.CTkLabel(
            prep,
            text=preparation_text,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            anchor="w",
            justify="left",
            wraplength=860,
        ).grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        ctk.CTkLabel(
            prep,
            text="FileCheck 本身不会自动执行这些 Windows 清理操作；请确认相关记录不再需要，并按本单位制度执行。",
            text_color=Palette.WARNING,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
            wraplength=860,
        ).grid(row=2, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Layout.CARD_PADDING))

        shortcuts = Card(self)
        shortcuts.grid(row=2, column=0, sticky="ew", pady=(Spacing.MD, 0))
        shortcuts.grid_columnconfigure((0, 1, 2), weight=1, uniform="home_shortcut")
        items = [
            ("扫描", "选择磁盘、创建索引并执行关键词扫描", "scan"),
            ("备份", "查看当前扫描摘要并备份到统一配置目录", "backup"),
            ("恢复", "校验备份并按原路径安全恢复文件", "restore"),
        ]
        for column, (title, description, target) in enumerate(items):
            cell = ctk.CTkFrame(shortcuts, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="nsew", padx=Layout.CARD_PADDING, pady=Layout.CARD_PADDING)
            ctk.CTkLabel(cell, text=title, text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").pack(anchor="w")
            ctk.CTkLabel(
                cell,
                text=description,
                text_color=Palette.TEXT_SECONDARY,
                font=Typography.CAPTION,
                anchor="w",
                justify="left",
                wraplength=240,
            ).pack(anchor="w", pady=(Spacing.XS, 0))
            SecondaryButton(cell, f"进入{title}", command=lambda name=target: self._on_navigate(name), width=110).pack(
                anchor="w", pady=(Spacing.MD, 0)
            )

        state = Card(self)
        state.grid(row=3, column=0, sticky="ew", pady=(Spacing.MD, 0))
        state.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(state, text="当前配置状态", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        self.state_label = ctk.CTkLabel(
            state,
            text="正在读取配置……",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
            wraplength=860,
        )
        self.state_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))

    def set_context(
        self,
        backup_root: Optional[str],
        selected_roots,
        keyword_count: int,
        extension_count: int,
    ) -> None:
        backup = backup_root or "未设置（请先进入设置）"
        index = "、".join(selected_roots) if selected_roots else "尚未建立索引（请进入扫描页选择磁盘并创建）"
        self.state_label.configure(
            text=(
                f"备份目录：{backup}\n"
                f"当前索引范围：{index}\n"
                f"扫描规则：{keyword_count} 个关键词 / {extension_count} 种文件类型"
            )
        )
