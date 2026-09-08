from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
from typing import Callable, Dict, List

import customtkinter as ctk

from .components import Card, PageHeader, PrimaryButton, SecondaryButton, StatusPill
from .settings_service import save_appearance
from .tokens import Layout, Palette, Radius, Spacing, Typography


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, on_save: Callable[[str, Dict[str, List[str]], List[str]], None]):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._on_save = on_save
        self.backup_root = tk.StringVar(value="")
        self.appearance = tk.StringVar(value="浅色")

        PageHeader(
            self,
            "设置",
            "统一管理备份根目录、扫描关键词、文件类型和界面主题；保存后扫描与备份直接使用这里的配置。",
        ).grid(row=0, column=0, sticky="ew")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=1)

        backup_card = Card(top)
        backup_card.grid(row=0, column=0, sticky="nsew", padx=(0, Spacing.SM))
        backup_card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(backup_card, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="统一备份根目录", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(row=0, column=0, sticky="w")
        self.save_state = StatusPill(header, "未修改", tone="neutral")
        self.save_state.grid(row=0, column=1, sticky="e")

        self.backup_entry = ctk.CTkEntry(
            backup_card,
            textvariable=self.backup_root,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            border_color=Palette.BORDER,
            fg_color=Palette.SURFACE_SUBTLE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
            placeholder_text="例如 H:\\FileCheckBackup",
        )
        self.backup_entry.grid(row=1, column=0, sticky="ew", padx=(Layout.CARD_PADDING, Spacing.SM))
        SecondaryButton(backup_card, "选择目录", command=self._pick_backup, width=105).grid(
            row=1, column=1, padx=(0, Layout.CARD_PADDING)
        )
        ctk.CTkLabel(
            backup_card,
            text="FileCheck 只使用一个统一备份根目录。每次备份会在该目录下生成一个独立的 FC-... 批次子目录；索引会自动排除整个备份根目录。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
            wraplength=650,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Layout.CARD_PADDING))

        theme_card = Card(top)
        theme_card.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(theme_card, text="界面主题", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        self.theme_control = ctk.CTkSegmentedButton(
            theme_card,
            values=["浅色", "暗色"],
            variable=self.appearance,
            command=self._theme_changed,
            selected_color=Palette.PRIMARY,
            selected_hover_color=Palette.PRIMARY_HOVER,
            unselected_color=Palette.SURFACE_SUBTLE,
            unselected_hover_color=Palette.PRIMARY_SOFT,
            text_color=Palette.TEXT,
            font=Typography.CAPTION,
        )
        self.theme_control.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        ctk.CTkLabel(
            theme_card,
            text="保留统一蓝色品牌色，仅切换浅色 / 暗色外观。主题选择立即生效并自动保存。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
            wraplength=230,
        ).grid(row=2, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Layout.CARD_PADDING))

        rules_card = Card(self)
        rules_card.grid(row=2, column=0, sticky="nsew", pady=(Spacing.MD, 0))
        rules_card.grid_columnconfigure((0, 1, 2), weight=1, uniform="keyword_group")
        rules_card.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(rules_card, text="扫描关键词", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.XS)
        )
        ctk.CTkLabel(
            rules_card,
            text="每行一个关键词，也可以用逗号分隔。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=Layout.CARD_PADDING, pady=(0, Spacing.SM))

        self.keyword_boxes = {}
        groups = [("high", "高风险"), ("sensitive", "敏感"), ("review", "人工复核")]
        for column, (key, title) in enumerate(groups):
            cell = ctk.CTkFrame(rules_card, fg_color="transparent")
            cell.grid(
                row=2,
                column=column,
                sticky="nsew",
                padx=(Layout.CARD_PADDING if column == 0 else Spacing.XS, Layout.CARD_PADDING if column == 2 else Spacing.XS),
            )
            cell.grid_rowconfigure(1, weight=1)
            cell.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(cell, text=title, text_color=Palette.TEXT, font=Typography.BODY_MEDIUM, anchor="w").grid(
                row=0, column=0, sticky="w", pady=(0, Spacing.XS)
            )
            box = ctk.CTkTextbox(
                cell,
                fg_color=Palette.SURFACE_SUBTLE,
                border_width=1,
                border_color=Palette.BORDER,
                corner_radius=Radius.CONTROL,
                text_color=Palette.TEXT,
                font=Typography.BODY,
                wrap="word",
                height=145,
            )
            box.grid(row=1, column=0, sticky="nsew")
            self.keyword_boxes[key] = box

        ext_row = ctk.CTkFrame(rules_card, fg_color="transparent")
        ext_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.MD, 0))
        ext_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ext_row, text="文件类型", text_color=Palette.TEXT, font=Typography.BODY_MEDIUM, anchor="w").grid(row=0, column=0, sticky="w")
        self.extensions_entry = ctk.CTkEntry(
            ext_row,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            border_color=Palette.BORDER,
            fg_color=Palette.SURFACE_SUBTLE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
            placeholder_text="doc, docx, xls, xlsx, pdf, txt ...",
        )
        self.extensions_entry.grid(row=1, column=0, sticky="ew", pady=(Spacing.XS, 0))

        actions = ctk.CTkFrame(rules_card, fg_color="transparent")
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", padx=Layout.CARD_PADDING, pady=Layout.CARD_PADDING)
        actions.grid_columnconfigure(0, weight=1)
        self.rules_path_label = ctk.CTkLabel(
            actions,
            text="",
            text_color=Palette.TEXT_MUTED,
            font=Typography.SMALL,
            anchor="w",
        )
        self.rules_path_label.grid(row=0, column=0, sticky="w")
        PrimaryButton(actions, "保存设置", command=self._save, width=120).grid(row=0, column=1, sticky="e")

    def set_values(self, data) -> None:
        self.backup_root.set(data.backup_root)
        for level, box in self.keyword_boxes.items():
            box.delete("1.0", "end")
            box.insert("1.0", "\n".join(data.keywords.get(level, [])))
        self.extensions_entry.delete(0, "end")
        self.extensions_entry.insert(0, ", ".join(data.extensions))
        self.appearance.set("暗色" if data.appearance == "dark" else "浅色")
        self.rules_path_label.configure(text=f"规则文件：{data.rules_path}", text_color=Palette.TEXT_MUTED)
        self.save_state.set_tone("success", "已载入")

    def saved(self, data) -> None:
        self.set_values(data)
        self.save_state.set_tone("success", "已保存")

    def save_error(self, message: str) -> None:
        self.save_state.set_tone("danger", "保存失败")
        self.rules_path_label.configure(text=message, text_color=Palette.DANGER)

    @staticmethod
    def _split_values(text: str) -> List[str]:
        normalized = text.replace("，", ",").replace("\r", "\n")
        values: List[str] = []
        for line in normalized.split("\n"):
            values.extend(part.strip() for part in line.split(",") if part.strip())
        return values

    def _pick_backup(self) -> None:
        path = filedialog.askdirectory(title="选择统一备份根目录")
        if path:
            self.backup_root.set(path)
            self.save_state.set_tone("warning", "待保存")

    def _theme_changed(self, value: str) -> None:
        mode = "dark" if value == "暗色" else "light"
        ctk.set_appearance_mode(mode)
        try:
            save_appearance(mode)
        except Exception as exc:
            self.save_error(f"主题保存失败：{exc}")
            return
        self.save_state.set_tone("success", "主题已保存")

    def _save(self) -> None:
        keywords = {
            level: self._split_values(box.get("1.0", "end"))
            for level, box in self.keyword_boxes.items()
        }
        extensions = self._split_values(self.extensions_entry.get())
        self._on_save(self.backup_root.get().strip(), keywords, extensions)
