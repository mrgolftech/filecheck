from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
from typing import Callable, Dict, List

import customtkinter as ctk

from .components import Card, PageHeader, PrimaryButton, SecondaryButton, StatusPill
from .tokens import Layout, Palette, Radius, Spacing, Typography


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, on_save: Callable[[str, Dict[str, List[str]], List[str]], None]):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._on_save = on_save
        self.backup_root = tk.StringVar(value="")

        PageHeader(
            self,
            "设置",
            "统一管理备份根目录、扫描关键词和文件类型；保存后后续扫描与备份直接使用这里的配置。",
        ).grid(row=0, column=0, sticky="ew")

        backup_card = Card(self)
        backup_card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
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
            fg_color=Palette.SURFACE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
            placeholder_text="例如 H:\\FileCheckBackup",
        )
        self.backup_entry.grid(row=1, column=0, sticky="ew", padx=(Layout.CARD_PADDING, Spacing.SM))
        SecondaryButton(backup_card, "选择目录", command=self._pick_backup, width=110).grid(row=1, column=1, padx=(0, Layout.CARD_PADDING))
        ctk.CTkLabel(
            backup_card,
            text="备份页面不再临时选择路径；这里保存的目录同时用于索引排除和正式备份。修改后建议重新创建索引。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Layout.CARD_PADDING))

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
            cell.grid(row=2, column=column, sticky="nsew", padx=(Layout.CARD_PADDING if column == 0 else Spacing.XS, Layout.CARD_PADDING if column == 2 else Spacing.XS))
            cell.grid_rowconfigure(1, weight=1)
            cell.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(cell, text=title, text_color=Palette.TEXT, font=Typography.BODY_MEDIUM, anchor="w").grid(row=0, column=0, sticky="w", pady=(0, Spacing.XS))
            box = ctk.CTkTextbox(
                cell,
                fg_color=Palette.SURFACE_SUBTLE,
                border_width=1,
                border_color=Palette.BORDER,
                corner_radius=Radius.CONTROL,
                text_color=Palette.TEXT,
                font=Typography.BODY,
                wrap="word",
                height=150,
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
        self.rules_path_label.configure(text=f"规则文件：{data.rules_path}")
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

    def _save(self) -> None:
        keywords = {
            level: self._split_values(box.get("1.0", "end"))
            for level, box in self.keyword_boxes.items()
        }
        extensions = self._split_values(self.extensions_entry.get())
        self._on_save(self.backup_root.get().strip(), keywords, extensions)
