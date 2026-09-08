from __future__ import annotations

import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from .components import (
    Card,
    DangerButton,
    DangerConfirmDialog,
    MetricCard,
    PageHeader,
    PrimaryButton,
    SecondaryButton,
    StatusPill,
)
from .tokens import Layout, Palette, Radius, Spacing, Typography


def _format_bytes(value: int) -> str:
    size = float(max(0, int(value)))
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{int(value)} B"


class RestorePage(ctk.CTkFrame):
    def __init__(self, master, on_load, on_preflight, on_restore, on_cancel):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.backup_path = tk.StringVar(value="")
        self.conflict = tk.StringVar(value="skip")
        self._on_load = on_load
        self._on_preflight = on_preflight
        self._on_restore = on_restore
        self._on_cancel = on_cancel
        self._info = None
        self._preflight = None
        self._busy = False
        self.backup_path.trace_add("write", self._input_changed)
        self.conflict.trace_add("write", self._input_changed)

        PageHeader(
            self,
            "恢复",
            "选择已验证备份，先检查原始路径和冲突，再按指定策略恢复并执行最终 SHA-256 校验。",
        ).grid(row=0, column=0, sticky="ew")

        target_card = Card(self)
        target_card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        target_card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(target_card, fg_color="transparent")
        header.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=Layout.CARD_PADDING,
            pady=(Layout.CARD_PADDING, Spacing.SM),
        )
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="备份批次",
            text_color=Palette.TEXT,
            font=Typography.CARD_TITLE,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.state_pill = StatusPill(header, "等待载入", tone="neutral")
        self.state_pill.grid(row=0, column=1, sticky="e")

        self.path_entry = ctk.CTkEntry(
            target_card,
            textvariable=self.backup_path,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            border_color=Palette.BORDER,
            fg_color=Palette.SURFACE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
            placeholder_text="选择包含 manifest.json 的备份批次目录",
        )
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(Layout.CARD_PADDING, Spacing.SM))
        self.browse_button = SecondaryButton(target_card, "选择目录", command=self._pick_backup, width=100)
        self.browse_button.grid(row=1, column=1, padx=(0, Spacing.SM))
        self.load_button = SecondaryButton(target_card, "载入备份", command=self._load, width=100)
        self.load_button.grid(row=1, column=2, padx=(0, Layout.CARD_PADDING))
        self.target_label = ctk.CTkLabel(
            target_card,
            text="可使用刚完成的备份，也可选择以前的 FileCheck 目录备份。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.target_label.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=Layout.CARD_PADDING,
            pady=(Spacing.SM, Layout.CARD_PADDING),
        )

        preflight_card = Card(self)
        preflight_card.grid(row=2, column=0, sticky="ew", pady=(Spacing.MD, 0))
        preflight_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            preflight_card,
            text="恢复策略与预检",
            text_color=Palette.TEXT,
            font=Typography.CARD_TITLE,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))

        choices = ctk.CTkFrame(preflight_card, fg_color="transparent")
        choices.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        self.skip_radio = self._radio(
            choices,
            "跳过已有文件（推荐）",
            "skip",
        )
        self.skip_radio.pack(side="left")
        self.rename_radio = self._radio(
            choices,
            "保留并重命名恢复",
            "rename",
        )
        self.rename_radio.pack(side="left", padx=(Spacing.LG, 0))
        self.overwrite_radio = self._radio(
            choices,
            "覆盖已有文件",
            "overwrite",
        )
        self.overwrite_radio.pack(side="left", padx=(Spacing.LG, 0))

        self.strategy_label = ctk.CTkLabel(
            preflight_card,
            text="跳过：目标已存在时保持原文件不动；仅恢复当前不存在的文件。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.strategy_label.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=Layout.CARD_PADDING,
            pady=(Spacing.SM, Spacing.MD),
        )

        metrics = ctk.CTkFrame(preflight_card, fg_color="transparent")
        metrics.grid(row=3, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        for column in range(4):
            metrics.grid_columnconfigure(column, weight=1, uniform="restore_metric")
        self.metric_files = MetricCard(metrics, "文件数")
        self.metric_size = MetricCard(metrics, "备份数据")
        self.metric_conflicts = MetricCard(metrics, "目标冲突", tone="warning")
        self.metric_action = MetricCard(metrics, "预计恢复/跳过")
        for column, metric in enumerate(
            [self.metric_files, self.metric_size, self.metric_conflicts, self.metric_action]
        ):
            metric.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else Spacing.XS, 0))

        actions = ctk.CTkFrame(preflight_card, fg_color="transparent")
        actions.grid(
            row=4,
            column=0,
            sticky="w",
            padx=Layout.CARD_PADDING,
            pady=(Spacing.MD, Layout.CARD_PADDING),
        )
        self.preflight_button = SecondaryButton(
            actions,
            "验证备份与目标",
            command=self._preflight_action,
            width=140,
            state="disabled",
        )
        self.preflight_button.grid(row=0, column=0)
        self.start_button = PrimaryButton(
            actions,
            "开始恢复",
            command=self._restore_action,
            width=120,
            state="disabled",
        )
        self.start_button.grid(row=0, column=1, padx=(Spacing.SM, 0))
        self.overwrite_button = DangerButton(
            actions,
            "覆盖并恢复",
            command=self._restore_action,
            width=120,
            state="disabled",
        )
        self.overwrite_button.grid(row=0, column=1, padx=(Spacing.SM, 0))
        self.overwrite_button.grid_remove()
        self.cancel_button = SecondaryButton(
            actions,
            "取消任务",
            command=self._cancel_action,
            width=110,
            state="disabled",
        )
        self.cancel_button.grid(row=0, column=2, padx=(Spacing.SM, 0))

        run_card = Card(self)
        run_card.grid(row=3, column=0, sticky="nsew", pady=(Spacing.MD, 0))
        run_card.grid_columnconfigure(0, weight=1)
        run_card.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(
            run_card,
            text="执行状态",
            text_color=Palette.TEXT,
            font=Typography.CARD_TITLE,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        self.progress_label = ctk.CTkLabel(
            run_card,
            text="等待操作",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
        )
        self.progress_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        self.progress_bar = ctk.CTkProgressBar(
            run_card,
            mode="determinate",
            height=8,
            corner_radius=Radius.SMALL,
            fg_color=Palette.SURFACE_SUBTLE,
            progress_color=Palette.PRIMARY,
        )
        self.progress_bar.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=Layout.CARD_PADDING,
            pady=(Spacing.XS, Spacing.SM),
        )
        self.progress_bar.set(0)
        self.log_box = ctk.CTkTextbox(
            run_card,
            fg_color=Palette.SURFACE_SUBTLE,
            border_width=0,
            corner_radius=Radius.CONTROL,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            wrap="word",
            height=120,
        )
        self.log_box.grid(
            row=3,
            column=0,
            sticky="nsew",
            padx=Layout.CARD_PADDING,
            pady=(0, Layout.CARD_PADDING),
        )
        self.log_box.configure(state="disabled")
        self._refresh_controls()

    def _radio(self, master, text: str, value: str):
        return ctk.CTkRadioButton(
            master,
            text=text,
            variable=self.conflict,
            value=value,
            text_color=Palette.TEXT_SECONDARY,
            fg_color=Palette.PRIMARY,
            hover_color=Palette.PRIMARY_HOVER,
            border_color=Palette.BORDER,
            font=Typography.CAPTION,
        )

    def set_target(self, value) -> None:
        self.backup_path.set(str(value) if value else "")
        self._info = None
        self._preflight = None
        self._reset_metrics()
        self._refresh_controls()

    def set_info(self, info) -> None:
        self._info = info
        self._preflight = None
        self.backup_path.set(str(info.backup_path))
        self.state_pill.set_tone("info", "已载入")
        self.target_label.configure(
            text=(
                f"批次：{info.batch_id}    文件数：{info.file_count}    数据量：{_format_bytes(info.total_bytes)}\n"
                "下一步执行全量备份校验并检查原始恢复路径冲突。"
            ),
            text_color=Palette.TEXT_SECONDARY,
        )
        self.metric_files.set_value(str(info.file_count))
        self.metric_size.set_value(_format_bytes(info.total_bytes))
        self.metric_conflicts.set_value("-")
        self.metric_action.set_value("-")
        self._refresh_controls()

    def load_error(self, message: str) -> None:
        self._info = None
        self._preflight = None
        self.state_pill.set_tone("danger", "载入失败")
        self.target_label.configure(text=message, text_color=Palette.DANGER)
        self._reset_metrics()
        self._refresh_controls()

    def begin_preflight(self) -> None:
        self._busy = True
        self._preflight = None
        self._clear_log()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="正在验证备份与恢复目标……", text_color=Palette.PRIMARY)
        self.append_log("恢复预检已启动；此阶段不会修改任何原始路径文件。")
        self._refresh_controls()

    def finish_preflight(self, result) -> None:
        self._busy = False
        self._preflight = result
        self.metric_files.set_value(str(result.file_count))
        self.metric_size.set_value(_format_bytes(result.total_bytes))
        self.metric_conflicts.set_value(
            str(result.conflicts),
            "warning" if result.conflicts else "success",
        )
        self.metric_action.set_value(f"{result.expected_restored}/{result.expected_skipped}")
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="恢复预检通过，可以开始恢复", text_color=Palette.SUCCESS)
        if result.conflict == "overwrite" and result.conflicts:
            self.strategy_label.configure(
                text=f"警告：将覆盖 {result.conflicts} 个当前已存在目标。正式执行前必须输入 OVERWRITE 二次确认。",
                text_color=Palette.DANGER,
            )
        elif result.conflict == "rename" and result.conflicts:
            self.strategy_label.configure(
                text=f"将保留 {result.conflicts} 个现有文件，并为对应备份内容生成新的恢复文件名。",
                text_color=Palette.WARNING,
            )
        elif result.conflict == "skip":
            self.strategy_label.configure(
                text=f"将恢复 {result.expected_restored} 个缺失文件，跳过 {result.expected_skipped} 个已有目标。",
                text_color=Palette.SUCCESS,
            )
        self._refresh_controls()

    def begin_restore(self) -> None:
        self._busy = True
        self._clear_log()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.progress_label.configure(text="正在再次校验备份并恢复文件……", text_color=Palette.PRIMARY)
        self.append_log("正式恢复已启动；每个恢复文件落盘后都会执行最终 SHA-256 校验。")
        self._refresh_controls()

    def finish_result(self, result) -> None:
        self._busy = False
        self._preflight = None
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.progress_label.configure(
            text=f"恢复完成：恢复 {result.restored}，跳过 {result.skipped}",
            text_color=Palette.SUCCESS,
        )
        self.append_log(
            f"恢复完成：restored={result.restored}, skipped={result.skipped}, elapsed={result.elapsed_seconds:.1f}s"
        )
        self._refresh_controls()

    def update_progress(self, progress, message: str = "") -> None:
        if message:
            self.progress_label.configure(text=message, text_color=Palette.TEXT_SECONDARY)
        if progress is None:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            return
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(max(0.0, min(1.0, float(progress))))

    def finish_error(self, message: str) -> None:
        self._busy = False
        self._preflight = None
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text=f"恢复任务失败：{message}", text_color=Palette.DANGER)
        self.append_log(f"错误：{message}")
        self._refresh_controls()

    def finish_cancelled(self) -> None:
        self._busy = False
        self._preflight = None
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="恢复已在文件级安全点停止", text_color=Palette.WARNING)
        self.append_log("已完成恢复的文件不会回滚。重新执行前建议重新载入并执行恢复预检。")
        if self.conflict.get() == "rename":
            self.append_log("重命名策略中断后请先核对已生成副本，避免再次执行时产生重复命名副本。")
        self._refresh_controls()

    def append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _reset_metrics(self) -> None:
        self.metric_files.set_value("-")
        self.metric_size.set_value("-")
        self.metric_conflicts.set_value("-")
        self.metric_action.set_value("-")

    def _invalidate_preflight(self) -> None:
        self._preflight = None
        if self._info:
            self.metric_files.set_value(str(self._info.file_count))
            self.metric_size.set_value(_format_bytes(self._info.total_bytes))
        self.metric_conflicts.set_value("-")
        self.metric_action.set_value("-")

    def _input_changed(self, *args) -> None:
        if self._busy:
            return
        self._invalidate_preflight()
        mode = self.conflict.get()
        descriptions = {
            "skip": ("跳过：目标已存在时保持原文件不动；仅恢复当前不存在的文件。", Palette.TEXT_SECONDARY),
            "rename": ("重命名：保留当前文件，把备份内容恢复为新的不冲突文件名。", Palette.WARNING),
            "overwrite": ("覆盖：使用备份内容替换当前已有文件。该策略可能丢失现有修改。", Palette.DANGER),
        }
        text, color = descriptions.get(mode, descriptions["skip"])
        self.strategy_label.configure(text=text, text_color=color)
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        if self._busy:
            self.path_entry.configure(state="disabled")
            self.browse_button.configure(state="disabled")
            self.load_button.configure(state="disabled")
            self.skip_radio.configure(state="disabled")
            self.rename_radio.configure(state="disabled")
            self.overwrite_radio.configure(state="disabled")
            self.preflight_button.configure(state="disabled")
            self.start_button.configure(state="disabled")
            self.overwrite_button.configure(state="disabled")
            self.cancel_button.configure(state="normal")
            return

        self.path_entry.configure(state="normal")
        self.browse_button.configure(state="normal")
        self.load_button.configure(state="normal" if self.backup_path.get().strip() else "disabled")
        self.skip_radio.configure(state="normal")
        self.rename_radio.configure(state="normal")
        self.overwrite_radio.configure(state="normal")
        self.preflight_button.configure(state="normal" if self._info else "disabled")
        approved = bool(
            self._preflight
            and self._info
            and self._preflight.backup_path == self._info.backup_path
            and self._preflight.conflict == self.conflict.get()
        )
        if self.conflict.get() == "overwrite":
            self.start_button.grid_remove()
            self.overwrite_button.grid()
            self.overwrite_button.configure(state="normal" if approved else "disabled")
        else:
            self.overwrite_button.grid_remove()
            self.start_button.grid()
            self.start_button.configure(state="normal" if approved else "disabled")
        self.cancel_button.configure(state="disabled")

    def _pick_backup(self) -> None:
        path = filedialog.askdirectory(title="选择 FileCheck 备份批次目录")
        if path:
            self.backup_path.set(path)
            self._info = None
            self._preflight = None
            self._reset_metrics()
            self._refresh_controls()

    def _load(self) -> None:
        self._on_load(self.backup_path.get().strip())

    def _preflight_action(self) -> None:
        if self._info:
            self._on_preflight(str(self._info.backup_path), self.conflict.get())

    def _restore_action(self) -> None:
        if not self._info or not self._preflight:
            return
        mode = self.conflict.get()
        if mode == "overwrite" and self._preflight.conflicts:
            dialog = DangerConfirmDialog(
                self.winfo_toplevel(),
                "确认覆盖恢复",
                f"将覆盖 {self._preflight.conflicts} 个当前已存在文件，并使用已验证备份内容替换它们。该操作不可自动撤销。",
                phrase="OVERWRITE",
            )
            dialog.confirm_button.configure(text="确认覆盖恢复")
            if not dialog.show():
                return
        self._on_restore(str(self._info.backup_path), mode)

    def _cancel_action(self) -> None:
        self.progress_label.configure(text="已请求停止，等待当前文件完成最终校验……", text_color=Palette.WARNING)
        self._on_cancel()
