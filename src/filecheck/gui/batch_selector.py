from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional

import customtkinter as ctk

from .batch_service import discover_backup_batches
from .components import SecondaryButton
from .tokens import Layout, Palette, Radius, Spacing, Typography


class BackupBatchSelector(ctk.CTkFrame):
    """Compact selector for batches under the single configured backup root."""

    def __init__(self, master, on_select: Callable[[str], None]):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self._on_select = on_select
        self._paths: Dict[str, Path] = {}
        self._current_path: Optional[Path] = None

        self.menu = ctk.CTkOptionMenu(
            self,
            values=["未发现备份批次"],
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
            state="disabled",
        )
        self.menu.grid(row=0, column=0, sticky="ew")
        self.refresh_button = SecondaryButton(self, "刷新", command=self.refresh, width=82)
        self.refresh_button.grid(row=0, column=1, padx=(Spacing.SM, 0))
        self.summary = ctk.CTkLabel(
            self,
            text="",
            text_color=Palette.TEXT_MUTED,
            font=Typography.SMALL,
            anchor="w",
        )
        self.summary.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(Spacing.XXS, 0))

    def refresh(self, preferred: Optional[str] = None, auto_load: bool = True) -> Optional[str]:
        batches = discover_backup_batches()
        self._paths = {batch.name: batch.path for batch in batches}
        if not batches:
            self._current_path = None
            self.menu.configure(values=["未发现备份批次"], state="disabled")
            self.menu.set("未发现备份批次")
            self.summary.configure(text="统一备份根目录下暂无包含 manifest.json 的备份批次。")
            return None

        chosen = batches[0]
        preferred_path = None
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

        previous = self._current_path
        names = [batch.name for batch in batches]
        self.menu.configure(values=names, state="normal" if len(names) > 1 else "disabled")
        self.menu.set(chosen.name)
        self._current_path = chosen.path
        self.summary.configure(
            text=(
                f"发现 {len(names)} 个备份批次；按目录名倒序，默认选择最新批次。"
                if len(names) > 1
                else "发现 1 个备份批次，已自动选择。"
            )
        )
        if auto_load and (previous is None or previous != chosen.path):
            self._on_select(str(chosen.path))
        return str(chosen.path)

    def set_selected_path(self, value: str) -> None:
        try:
            path = Path(value).expanduser().resolve()
        except (OSError, RuntimeError):
            return
        for name, candidate in self._paths.items():
            if candidate == path:
                self._current_path = candidate
                self.menu.set(name)
                return

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.menu.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            return
        self.menu.configure(state="normal" if len(self._paths) > 1 else "disabled")
        self.refresh_button.configure(state="normal")

    def _selected(self, name: str) -> None:
        path = self._paths.get(name)
        if path is None or path == self._current_path:
            return
        self._current_path = path
        self._on_select(str(path))
