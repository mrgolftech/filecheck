from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from .tokens import Layout, Palette, Radius, Spacing, Typography


class PageHeader(ctk.CTkFrame):
    def __init__(self, master, title: str, description: str):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=title,
            text_color=Palette.TEXT,
            font=Typography.PAGE_TITLE,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            self,
            text=description,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(Spacing.XS, 0))


class Card(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=Palette.SURFACE,
            border_width=1,
            border_color=Palette.BORDER,
            corner_radius=Radius.CARD,
            **kwargs,
        )


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, text: str, command: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            height=Layout.BUTTON_HEIGHT,
            corner_radius=Radius.CONTROL,
            fg_color=Palette.PRIMARY,
            hover_color=Palette.PRIMARY_HOVER,
            text_color="#FFFFFF",
            font=Typography.BODY_MEDIUM,
            **kwargs,
        )


class SecondaryButton(ctk.CTkButton):
    def __init__(self, master, text: str, command: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            height=Layout.BUTTON_HEIGHT,
            corner_radius=Radius.CONTROL,
            fg_color=Palette.SURFACE,
            hover_color=Palette.SURFACE_SUBTLE,
            border_width=1,
            border_color=Palette.BORDER,
            text_color=Palette.TEXT,
            font=Typography.BODY_MEDIUM,
            **kwargs,
        )


class DangerButton(ctk.CTkButton):
    def __init__(self, master, text: str, command: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            height=Layout.BUTTON_HEIGHT,
            corner_radius=Radius.CONTROL,
            fg_color=Palette.DANGER,
            hover_color=Palette.DANGER_HOVER,
            text_color="#FFFFFF",
            font=Typography.BODY_MEDIUM,
            **kwargs,
        )


class SidebarButton(ctk.CTkButton):
    def __init__(self, master, text: str, command: Callable[[], None], **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            height=42,
            anchor="w",
            corner_radius=Radius.CONTROL,
            fg_color="transparent",
            hover_color=Palette.SURFACE_SUBTLE,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY_MEDIUM,
            **kwargs,
        )

    def set_active(self, active: bool) -> None:
        if active:
            self.configure(fg_color=Palette.PRIMARY_SOFT, text_color=Palette.PRIMARY)
        else:
            self.configure(fg_color="transparent", text_color=Palette.TEXT_SECONDARY)


class StatusPill(ctk.CTkLabel):
    _COLORS = {
        "neutral": (Palette.SURFACE_SUBTLE, Palette.TEXT_SECONDARY),
        "info": (Palette.PRIMARY_SOFT, Palette.PRIMARY),
        "success": (Palette.SUCCESS_SOFT, Palette.SUCCESS),
        "warning": (Palette.WARNING_SOFT, Palette.WARNING),
        "danger": (Palette.DANGER_SOFT, Palette.DANGER),
    }

    def __init__(self, master, text: str, tone: str = "neutral", **kwargs):
        bg, fg = self._COLORS.get(tone, self._COLORS["neutral"])
        super().__init__(
            master,
            text=text,
            fg_color=bg,
            text_color=fg,
            corner_radius=Radius.SMALL,
            font=Typography.SMALL,
            height=26,
            **kwargs,
        )

    def set_tone(self, tone: str, text: Optional[str] = None) -> None:
        bg, fg = self._COLORS.get(tone, self._COLORS["neutral"])
        updates = {"fg_color": bg, "text_color": fg}
        if text is not None:
            updates["text"] = text
        self.configure(**updates)


class EmptyState(Card):
    def __init__(self, master, title: str, description: str):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=title,
            text_color=Palette.TEXT,
            font=Typography.CARD_TITLE,
        ).grid(row=0, column=0, pady=(Spacing.XL, Spacing.XS))
        ctk.CTkLabel(
            self,
            text=description,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            justify="center",
        ).grid(row=1, column=0, pady=(0, Spacing.XL), padx=Layout.CARD_PADDING)
