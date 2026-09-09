from __future__ import annotations

import webbrowser

import customtkinter as ctk

from .tokens import Palette, Typography


REPOSITORY_URL = "https://github.com/mrgolftech/filecheck"


class RepositoryLink(ctk.CTkLabel):
    """Compact text-only hyperlink to the FileCheck GitHub repository."""

    def __init__(self, master):
        super().__init__(
            master,
            text="GitHub",
            text_color=Palette.PRIMARY,
            font=Typography.SMALL,
            anchor="w",
            cursor="hand2",
        )
        self.bind("<Button-1>", self._open_repository)

    @staticmethod
    def _open_repository(_event=None) -> None:
        webbrowser.open_new_tab(REPOSITORY_URL)
