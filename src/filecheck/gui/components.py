from __future__ import annotations

import tkinter as tk
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
        self.description_label = ctk.CTkLabel(
            self,
            text=description,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            anchor="w",
            justify="left",
            wraplength=620,
        )
        self.description_label.grid(row=1, column=0, sticky="ew", pady=(Spacing.XS, 0))
        self.bind("<Configure>", self._resize_description, add="+")

    def _resize_description(self, event) -> None:
        width = max(240, int(getattr(event, "width", 0)) - Spacing.XS)
        self.description_label.configure(wraplength=width)


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
            text_color=Palette.ON_PRIMARY,
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
            text_color=Palette.ON_PRIMARY,
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


class MetricCard(Card):
    def __init__(self, master, label: str, value: str = "-", tone: str = "neutral", **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            text_color=self._value_color(tone),
            font=Typography.SECTION_TITLE,
            anchor="w",
        )
        self.value_label.grid(row=0, column=0, sticky="ew", padx=Spacing.MD, pady=(Spacing.MD, Spacing.XXS))
        ctk.CTkLabel(
            self,
            text=label,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=Spacing.MD, pady=(0, Spacing.MD))

    @staticmethod
    def _value_color(tone: str) -> str:
        return {
            "info": Palette.PRIMARY,
            "success": Palette.SUCCESS,
            "warning": Palette.WARNING,
            "danger": Palette.DANGER,
        }.get(tone, Palette.TEXT)

    def set_value(self, value: str, tone: str = "neutral") -> None:
        self.value_label.configure(text=value, text_color=self._value_color(tone))


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
            wraplength=620,
        ).grid(row=1, column=0, pady=(0, Spacing.XL), padx=Layout.CARD_PADDING)


class DangerConfirmDialog(ctk.CTkToplevel):
    """Modal high-risk confirmation requiring an exact confirmation phrase."""

    def __init__(self, master, title: str, message: str, phrase: str = "DELETE"):
        super().__init__(master)
        self.title(title)
        self.geometry("520x320")
        self.resizable(False, False)
        self.configure(fg_color=Palette.BG)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._phrase = phrase
        self._approved = False
        self._value = tk.StringVar(value="")
        self._value.trace_add("write", self._refresh_confirm_state)

        card = Card(self)
        card.grid(row=0, column=0, sticky="nsew", padx=Spacing.LG, pady=Spacing.LG)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text=title,
            text_color=Palette.DANGER,
            font=Typography.SECTION_TITLE,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        ctk.CTkLabel(
            card,
            text=message,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            anchor="w",
            justify="left",
            wraplength=430,
        ).grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        ctk.CTkLabel(
            card,
            text=f"请输入 {phrase} 以确认：",
            text_color=Palette.TEXT,
            font=Typography.BODY_MEDIUM,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.LG, Spacing.XS))
        self.entry = ctk.CTkEntry(
            card,
            textvariable=self._value,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            border_color=Palette.BORDER,
            fg_color=Palette.SURFACE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
        )
        self.entry.grid(row=3, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="e", padx=Layout.CARD_PADDING, pady=Layout.CARD_PADDING)
        SecondaryButton(actions, "取消", command=self._cancel, width=100).pack(side="left")
        self.confirm_button = DangerButton(actions, "确认删除", command=self._approve, width=120, state="disabled")
        self.confirm_button.pack(side="left", padx=(Spacing.SM, 0))
        self.after(50, self._focus_entry)

    def _focus_entry(self) -> None:
        self.entry.focus_set()

    def _refresh_confirm_state(self, *args) -> None:
        state = "normal" if self._value.get().strip() == self._phrase else "disabled"
        self.confirm_button.configure(state=state)

    def _approve(self) -> None:
        if self._value.get().strip() != self._phrase:
            return
        self._approved = True
        self.destroy()

    def _cancel(self) -> None:
        self._approved = False
        self.destroy()

    def show(self) -> bool:
        self.wait_window()
        return self._approved
