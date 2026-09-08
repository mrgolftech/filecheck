from __future__ import annotations

import tkinter as tk
import webbrowser

import customtkinter as ctk

from .tokens import Palette, Typography


REPOSITORY_URL = "https://github.com/mrgolftech/filecheck"
_GITHUB_ICON_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAAXklEQVR42mNgGPQgpaT7PznqmMgxDJs8C6Uuw+sicsAgN4jUcEFWz0SuIVhdRKkhDAwMDEwwQ+b0lDJSYhALpQZgDWxSDUVWz4RPklhDcKYjQoZhk2ciRTE+caqlbAAxICgj9glX9gAAAABJRU5ErkJggg=="
)


class RepositoryLink(ctk.CTkButton):
    """Compact GitHub icon/text link without exposing the raw repository URL."""

    def __init__(self, master):
        self._github_icon = tk.PhotoImage(data=_GITHUB_ICON_PNG)
        super().__init__(
            master,
            text="GitHub",
            image=self._github_icon,
            compound="left",
            command=self._open_repository,
            width=92,
            height=28,
            anchor="w",
            fg_color="transparent",
            hover_color=Palette.SURFACE_SUBTLE,
            text_color=Palette.PRIMARY,
            font=Typography.SMALL,
            border_width=0,
            corner_radius=6,
        )

    @staticmethod
    def _open_repository() -> None:
        webbrowser.open_new_tab(REPOSITORY_URL)
