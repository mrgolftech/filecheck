from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from .batch_service import BackupBatchOption, discover_backup_batches
from .components import Card, SecondaryButton, StatusPill
from .tokens import Layout, Palette, Radius, Spacing, Typography


class BackupBatchSelector(Card):
    """Persistent selector for batches inside the single configured backup root."""

    def __init__(self, master, on_select: Callable[[str], None]):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self._on_select = on_select
        self._paths: Dict[str, Path] = {}
        self._current_path: Optional[Path] = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.XS))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="备份批次",
            text_color=Palette.TEXT,
            font=Typography.CARD_TITLE,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.state = StatusPill(header, "未发现", tone="neutral")
        self.state.grid(row=0, column=1, sticky="e")

        self.description = ctk.CTkLabel(
            self,
            text="从设置中的统一备份根目录自动查找包含 manifest.json 的备份批次。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
        )
        self.description.grid(row=1, column=0, columnspan=3, sticky="ew", padx=Layout.CARD_PADDING)

        self.menu = ctk.CTkOptionMenu(
            self,
            values=[""],
            command=self._selected,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            fg_color=Palette.SURFACE_SUBTLE,
            button_color=Palette.PRIMARY,
            button_hover_color=Palette.PRIMARY_HOVER,
            text_color=Palette.TEXT,
            dropdown_fg_color=Palette.SURFACE,
            dropdown_text_color=Palette.TEXT,
            dropdown_hover_color=Palette.PRIMARY_SOFT,
            font=Typography.BODY,
            dropdown_font=Typography.BODY,
            width=360,
        )
        self.menu.grid(row=2, column=0, sticky="w", padx=(Layout.CARD_PADDING, Spacing.SM), pady=(Spacing.SM, Layout.CARD_PADDING))
        SecondaryButton(self, "刷新批次", command=self.refresh, width=105).grid(
            row=2, column=1, sticky="w", padx=(0, Spacing.SM), pady=(Spacing.SM, Layout.CARD_PADDING)
        )
        self.path_label = ctk.CTkLabel(
            self,
            text="",
            text_color=Palette.TEXT_MUTED,
            font=Typography.SMALL,
            anchor="w",
        )
        self.path_label.grid(row=2, column=2, sticky="ew", padx=(0, Layout.CARD_PADDING), pady=(Spacing.SM, Layout.CARD_PADDING))
        self.grid_columnconfigure(2, weight=1)

    def refresh(self, preferred: Optional[str] = None, auto_load: bool = True) -> Optional[str]:
        batches = discover_backup_batches()
        return self.set_batches(batches, preferred=preferred, auto_load=auto_load)

    def set_batches(
        self,
        batches: List[BackupBatchOption],
        *,
        preferred: Optional[str] = None,
        auto_load: bool = True,
    ) -> Optional[str]:
        self._paths = {batch.name: batch.path for batch in batches}
        if not batches:
            self._current_path = None
            self.menu.configure(values=["未发现备份批次"], state="disabled")
            self.menu.set("未发现备份批次")
            self.path_label.configure(text="")
            self.state.set_tone("warning", "无批次")
            self.description.configure(text="当前备份根目录下没有发现包含 manifest.json 的一级子目录。")
            return None

        chosen = batches[0]
        if preferred:
            try:
                preferred_path = Path(preferred).expanduser().resolve()
            except (OSError, RuntimeError):
                preferred_path = None
            if preferred_path is not None:
                for batch in batches:
                    if batch.path == preferred_path:
                        chosen = batch
                        break

        names = [batch.name for batch in batches]
        self.menu.configure(values=names, state="normal" if len(names) > 1 else "disabled")
        self.menu.set(chosen.name)
        self._current_path = chosen.path
        self.path_label.configure(text=str(chosen.path))
        if len(names) > 1:
            self.state.set_tone("info", f"{len(names)} 个批次")
            self.description.configure(text="发现多个备份批次，已按目录名选择最新一个；可通过下拉框切换。")
        else:
            self.state.set_tone("success", "1 个批次")
            self.description.configure(text="发现 1 个有效备份批次，已自动选择。")

        if auto_load:
            self._on_select(str(chosen.path))
        return str(chosen.path)

    def _selected(self, name: str) -> None:
        path = self._paths.get(name)
        if path is None or path == self._current_path:
            return
        self._current_path = path
        self.path_label.configure(text=str(path))
        self._on_select(str(path))


def attach_backup_batch_selector(page, on_select: Callable[[str], None]) -> BackupBatchSelector:
    """Insert the selector above an existing removal/restore page without rewriting it."""
    direct_children = list(page.winfo_children())
    for child in direct_children:
        try:
            info = child.grid_info()
            row = int(info.get("row", 0))
        except (ValueError, TypeError):
            continue
        if row >= 1:
            child.grid_configure(row=row + 1)

    selector = BackupBatchSelector(page, on_select)
    selector.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
    page._filecheck_batch_selector = selector

    def refresh_on_map(_event=None) -> None:
        preferred = ""
        backup_var = getattr(page, "backup_path", None)
        if backup_var is not None:
            try:
                preferred = str(backup_var.get() or "")
            except Exception:
                preferred = ""
        selector.refresh(preferred=preferred or None, auto_load=True)

    page.bind("<Map>", refresh_on_map, add="+")
    page.after_idle(lambda: selector.refresh(auto_load=True))
    return selector
