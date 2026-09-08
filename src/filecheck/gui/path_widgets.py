from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from .components import SecondaryButton
from .tokens import Palette, Spacing, Typography


def reveal_path(value: str) -> None:
    """Open the containing folder for a file/directory and select the file on Windows when possible."""
    text = str(value or "").strip()
    if not text:
        return
    path = Path(text).expanduser()
    try:
        path = path.resolve()
    except (OSError, RuntimeError):
        pass

    if os.name == "nt":
        try:
            if path.exists() and path.is_file():
                creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
                subprocess.Popen(
                    ["explorer.exe", f"/select,{path}"],
                    creationflags=creationflags,
                )
                return
            folder = path if path.is_dir() else path.parent
            if folder.exists():
                os.startfile(str(folder))  # type: ignore[attr-defined]
                return
        except (OSError, ValueError):
            return

    folder = path if path.is_dir() else path.parent
    try:
        if os.name == "posix":
            command = ["open", str(folder)] if os.uname().sysname == "Darwin" else ["xdg-open", str(folder)]
            subprocess.Popen(command)
    except (AttributeError, OSError, ValueError):
        return


class FileLocationRow(ctk.CTkFrame):
    """Compact file-path row with filename-only display and a fixed aligned action button."""

    def __init__(self, master, label: str, button_text: str = "打开位置"):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(1, weight=1)
        self._path: Optional[str] = None

        self.kind_label = ctk.CTkLabel(
            self,
            text=label,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            width=86,
        )
        self.kind_label.grid(row=0, column=0, sticky="w")

        self.name_label = ctk.CTkLabel(
            self,
            text="-",
            text_color=Palette.TEXT,
            font=Typography.SMALL,
            anchor="w",
        )
        self.name_label.grid(row=0, column=1, sticky="ew", padx=(Spacing.SM, Spacing.SM))

        self.open_button = SecondaryButton(
            self,
            button_text,
            command=self._open,
            width=96,
            state="disabled",
        )
        self.open_button.grid(row=0, column=2, sticky="e")

    def set_path(self, value) -> None:
        text = str(value or "").strip()
        self._path = text or None
        if not self._path:
            self.name_label.configure(text="-")
            self.open_button.configure(state="disabled")
            return
        path = Path(self._path)
        self.name_label.configure(text=path.name or str(path))
        self.open_button.configure(state="normal")

    def clear(self) -> None:
        self.set_path(None)

    def _open(self) -> None:
        if self._path:
            reveal_path(self._path)
