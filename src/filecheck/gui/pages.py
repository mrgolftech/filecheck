from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from .components import Card, EmptyState, PageHeader, PrimaryButton, SecondaryButton, StatusPill
from .tokens import Layout, Palette, Radius, Spacing, Typography


class BasePage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)


class HomePage(BasePage):
    def __init__(self, master, on_navigate):
        super().__init__(master)
        PageHeader(
            self,
            "首页",
            "按“扫描 → 备份与迁出 → 恢复”的固定流程完成文件检查和安全迁移。",
        ).grid(row=0, column=0, sticky="ew")

        overview = Card(self)
        overview.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        overview.grid_columnconfigure((0, 1, 2), weight=1, uniform="workflow")

        steps = [
            ("1", "扫描文件", "按统一规则查找目标文件", "scan"),
            ("2", "备份与迁出", "校验备份后再处理源文件", "backup"),
            ("3", "恢复文件", "按清单恢复至原始路径", "restore"),
        ]
        for column, (number, title, description, target) in enumerate(steps):
            cell = ctk.CTkFrame(overview, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="nsew", padx=Layout.CARD_PADDING, pady=Layout.CARD_PADDING)
            StatusPill(cell, f"步骤 {number}", tone="info").pack(anchor="w")
            ctk.CTkLabel(cell, text=title, text_color=Palette.TEXT, font=Typography.CARD_TITLE).pack(
                anchor="w", pady=(Spacing.MD, Spacing.XS)
            )
            ctk.CTkLabel(
                cell,
                text=description,
                text_color=Palette.TEXT_SECONDARY,
                font=Typography.CAPTION,
                anchor="w",
            ).pack(anchor="w")
            SecondaryButton(cell, "进入", command=lambda name=target: on_navigate(name), width=90).pack(
                anchor="w", pady=(Spacing.LG, 0)
            )

        status = Card(self)
        status.grid(row=2, column=0, sticky="ew", pady=(Spacing.MD, 0))
        status.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(status, text="当前状态", text_color=Palette.TEXT, font=Typography.SECTION_TITLE).grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        ctk.CTkLabel(
            status,
            text="GUI 基础框架已建立。后续核心业务接入时继续复用现有 CLI 模块，不复制扫描、备份和恢复逻辑。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))


class ScanPage(BasePage):
    def __init__(self, master, notify):
        super().__init__(master)
        self.scan_path = ctk.StringVar(value="")
        PageHeader(self, "扫描", "选择扫描范围并核对规则后开始检查。").grid(row=0, column=0, sticky="ew")

        card = Card(self)
        card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="扫描范围", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        self.path_entry = ctk.CTkEntry(
            card,
            textvariable=self.scan_path,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            border_color=Palette.BORDER,
            fg_color=Palette.SURFACE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
            placeholder_text="选择需要检查的磁盘或目录",
        )
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(Layout.CARD_PADDING, Spacing.SM))
        SecondaryButton(card, "选择目录", command=self._pick_scan_path, width=110).grid(
            row=1, column=1, padx=(0, Layout.CARD_PADDING)
        )
        ctk.CTkLabel(
            card,
            text="扫描规则由 config/rules.json 统一管理，正式接入后将在此显示生效的关键词组和文件类型。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Spacing.LG))
        PrimaryButton(card, "开始扫描", command=lambda: notify("扫描业务接口待接入", "info"), width=130).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING)
        )

    def _pick_scan_path(self) -> None:
        path = filedialog.askdirectory(title="选择扫描目录")
        if path:
            self.scan_path.set(path)


class ResultPage(BasePage):
    def __init__(self, master):
        super().__init__(master)
        PageHeader(self, "扫描结果", "集中查看命中文件数量、容量、路径和匹配规则。").grid(row=0, column=0, sticky="ew")
        EmptyState(self, "暂无扫描结果", "完成一次扫描后，这里将显示结果摘要和文件列表。").grid(
            row=1, column=0, sticky="ew", pady=(Spacing.LG, 0)
        )


class BackupPage(BasePage):
    def __init__(self, master, notify):
        super().__init__(master)
        self.backup_path = ctk.StringVar(value="")
        PageHeader(self, "备份与迁出", "确认备份目标、所需空间和校验状态后执行批量备份。").grid(
            row=0, column=0, sticky="ew"
        )
        card = Card(self)
        card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="备份位置", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        ctk.CTkEntry(
            card,
            textvariable=self.backup_path,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            border_color=Palette.BORDER,
            fg_color=Palette.SURFACE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
            placeholder_text="选择备份目标目录",
        ).grid(row=1, column=0, sticky="ew", padx=(Layout.CARD_PADDING, Spacing.SM))
        SecondaryButton(card, "选择目录", command=self._pick_backup_path, width=110).grid(
            row=1, column=1, padx=(0, Layout.CARD_PADDING)
        )
        ctk.CTkLabel(
            card,
            text="后续接入核心模块后，将在执行前显示文件数量、总容量、可用空间和 SHA-256 校验策略。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Spacing.LG))
        PrimaryButton(card, "开始备份", command=lambda: notify("备份业务接口待接入", "info"), width=130).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING)
        )

    def _pick_backup_path(self) -> None:
        path = filedialog.askdirectory(title="选择备份目录")
        if path:
            self.backup_path.set(path)


class RestorePage(BasePage):
    def __init__(self, master, notify):
        super().__init__(master)
        PageHeader(self, "恢复", "读取备份清单并将文件恢复到原始路径。").grid(row=0, column=0, sticky="ew")
        card = Card(self)
        card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="恢复清单", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        ctk.CTkLabel(
            card,
            text="正式接入后支持选择 manifest，并先进行完整性校验和冲突预检查。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        SecondaryButton(card, "选择清单", command=lambda: notify("恢复清单选择将在业务接入阶段完成", "neutral"), width=120).grid(
            row=2, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Spacing.LG, Layout.CARD_PADDING)
        )


class SettingsPage(BasePage):
    def __init__(self, master):
        super().__init__(master)
        PageHeader(self, "设置", "集中管理扫描规则、界面偏好和运行环境信息。").grid(row=0, column=0, sticky="ew")
        card = Card(self)
        card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="界面基线", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        ctk.CTkLabel(
            card,
            text="当前采用统一浅色主题。颜色、字体、间距和公共控件由设计系统集中管理。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))
