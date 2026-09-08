from __future__ import annotations

import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from .batch_selector import BackupBatchSelector
from .components import (
    Card,
    DangerButton,
    DangerConfirmDialog,
    MetricCard,
    PageHeader,
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


class MigrationPage(ctk.CTkFrame):
    def __init__(self, master, on_load, on_preflight, on_remove, on_resume, on_cancel):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.backup_path = tk.StringVar(value="")
        self._on_load = on_load
        self._on_preflight = on_preflight
        self._on_remove = on_remove
        self._on_resume = on_resume
        self._on_cancel = on_cancel
        self._info = None
        self._preflight = None
        self._busy = False

        PageHeader(
            self,
            "源文件删除",
            "这是独立的高风险步骤：从统一备份根目录选择一个已验证批次，复核全部源文件后再明确确认删除。",
        ).grid(row=0, column=0, sticky="ew")

        target_card = Card(self)
        target_card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        target_card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(target_card, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="已验证备份批次", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(row=0, column=0, sticky="w")
        self.state_pill = StatusPill(header, "等待载入", tone="neutral")
        self.state_pill.grid(row=0, column=1, sticky="e")

        self.batch_selector = BackupBatchSelector(target_card, self._select_discovered_batch)
        self.batch_selector.grid(row=1, column=0, sticky="ew", padx=(Layout.CARD_PADDING, Spacing.SM))
        self.browse_button = SecondaryButton(target_card, "手动选择其他目录", command=self._pick_backup, width=145)
        self.browse_button.grid(row=1, column=1, sticky="n", padx=(0, Layout.CARD_PADDING))

        self.target_label = ctk.CTkLabel(
            target_card,
            text="将自动扫描设置中的统一备份根目录；若存在多个含 manifest.json 的批次，默认选择目录名最新的一个。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.target_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Layout.CARD_PADDING))

        safety_card = Card(self)
        safety_card.grid(row=2, column=0, sticky="ew", pady=(Spacing.MD, 0))
        safety_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(safety_card, text="安全状态", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        metrics = ctk.CTkFrame(safety_card, fg_color="transparent")
        metrics.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        for column in range(4):
            metrics.grid_columnconfigure(column, weight=1, uniform="migration_metric")
        self.metric_files = MetricCard(metrics, "文件数")
        self.metric_size = MetricCard(metrics, "源数据")
        self.metric_deleted = MetricCard(metrics, "已删除", tone="success")
        self.metric_failed = MetricCard(metrics, "未完成/异常", tone="danger")
        for column, metric in enumerate([self.metric_files, self.metric_size, self.metric_deleted, self.metric_failed]):
            metric.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else Spacing.XS, 0))
        self.safety_label = ctk.CTkLabel(
            safety_card,
            text="载入备份后才能执行删除前复核。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.safety_label.grid(row=2, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Spacing.MD))
        actions = ctk.CTkFrame(safety_card, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))
        self.preflight_button = SecondaryButton(actions, "执行删除前复核", command=self._preflight_action, width=140, state="disabled")
        self.preflight_button.pack(side="left")
        self.remove_button = DangerButton(actions, "删除源文件", command=self._remove_action, width=120, state="disabled")
        self.remove_button.pack(side="left", padx=(Spacing.SM, 0))
        self.resume_button = DangerButton(actions, "继续未完成删除", command=self._resume_action, width=140, state="disabled")
        self.resume_button.pack(side="left", padx=(Spacing.SM, 0))
        self.cancel_button = SecondaryButton(actions, "取消任务", command=self._cancel_action, width=110, state="disabled")
        self.cancel_button.pack(side="left", padx=(Spacing.SM, 0))

        run_card = Card(self)
        run_card.grid(row=3, column=0, sticky="nsew", pady=(Spacing.MD, 0))
        run_card.grid_columnconfigure(0, weight=1)
        run_card.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(run_card, text="执行状态", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        self.progress_label = ctk.CTkLabel(run_card, text="等待操作", text_color=Palette.TEXT_SECONDARY, font=Typography.CAPTION, anchor="w")
        self.progress_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        self.progress_bar = ctk.CTkProgressBar(
            run_card,
            mode="determinate",
            height=8,
            corner_radius=Radius.SMALL,
            fg_color=Palette.SURFACE_SUBTLE,
            progress_color=Palette.DANGER,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.XS, Spacing.SM))
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
        self.log_box.grid(row=3, column=0, sticky="nsew", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))
        self.log_box.configure(state="disabled")
        self.bind("<Map>", self._page_mapped, add="+")
        self.after_idle(self._refresh_batches)

    def _page_mapped(self, _event=None) -> None:
        self._refresh_batches()

    def _refresh_batches(self) -> None:
        preferred = str(self._info.backup_path) if self._info is not None else None
        self.batch_selector.refresh(preferred=preferred, auto_load=True)

    def _select_discovered_batch(self, value: str) -> None:
        self.backup_path.set(value)
        self._info = None
        self._preflight = None
        self._on_load(value)

    def set_target(self, value) -> None:
        text = str(value) if value else ""
        self.backup_path.set(text)
        self._info = None
        self._preflight = None
        if text:
            self.batch_selector.refresh(preferred=text, auto_load=False)
        self._refresh_controls()

    def set_info(self, info) -> None:
        self._info = info
        self._preflight = None
        self.backup_path.set(str(info.backup_path))
        self.batch_selector.set_selected_path(str(info.backup_path))
        self.metric_files.set_value(str(info.file_count))
        self.metric_size.set_value(_format_bytes(info.total_bytes))
        self.metric_deleted.set_value(str(info.deleted), "success")
        self.metric_failed.set_value(str(info.failed + info.pending), "danger" if info.failed or info.pending else "success")
        if not info.has_state:
            self.state_pill.set_tone("info", "待安全复核")
            self.target_label.configure(text=f"批次：{info.batch_id}\n目录：{info.backup_path}\n尚未创建 source-removal.json；当前未删除任何源文件。")
            self.safety_label.configure(
                text="下一步会先再次验证备份，并对 manifest 中全部源文件重新计算 SHA-256。任何不一致都会阻止整批删除。",
                text_color=Palette.TEXT_SECONDARY,
            )
        elif info.status == "completed":
            self.state_pill.set_tone("success", "删除完成")
            self.target_label.configure(text=f"批次：{info.batch_id}\n目录：{info.backup_path}\n删除状态：{info.state_path}")
            self.safety_label.configure(text="该批次源文件删除已经完成。", text_color=Palette.SUCCESS)
        else:
            tone = "danger" if info.failed else "warning"
            self.state_pill.set_tone(tone, "存在未完成项")
            self.target_label.configure(text=f"批次：{info.batch_id}\n目录：{info.backup_path}\n删除状态：{info.state_path}")
            self.safety_label.configure(
                text=(
                    f"已有删除状态：已删除 {info.deleted}，已不存在 {info.already_absent}，"
                    f"异常 {info.failed}，可继续删除 {info.pending}。"
                ),
                text_color=Palette.WARNING,
            )
        self._refresh_controls()

    def load_error(self, message: str) -> None:
        self._info = None
        self._preflight = None
        self.state_pill.set_tone("danger", "载入失败")
        self.target_label.configure(text=message, text_color=Palette.DANGER)
        self._refresh_controls()

    def begin_preflight(self) -> None:
        self._busy = True
        self._preflight = None
        self._clear_log()
        self.progress_label.configure(text="正在验证备份并复核全部源文件……", text_color=Palette.PRIMARY)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.append_log("删除前安全复核已启动；当前不会删除任何文件。")
        self._refresh_controls()

    def finish_preflight(self, result) -> None:
        self._busy = False
        self._preflight = result
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text=f"安全复核通过：{result.file_count} 个源文件均与备份一致", text_color=Palette.SUCCESS)
        self.safety_label.configure(
            text="备份及全部源文件 SHA-256 复核通过。删除按钮已解锁；删除前仍需输入 DELETE 二次确认。",
            text_color=Palette.SUCCESS,
        )
        self._refresh_controls()

    def begin_removal(self, resume: bool = False) -> None:
        self._busy = True
        self._clear_log()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        text = "正在继续未完成删除……" if resume else "正在删除已复核源文件……"
        self.progress_label.configure(text=text, text_color=Palette.DANGER)
        self.append_log("危险操作已确认；删除结果将持续写入 source-removal.json。")
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

    def finish_result(self, result) -> None:
        self._busy = False
        self._preflight = None
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        if result.status == "completed":
            self.progress_label.configure(text="源文件删除完成", text_color=Palette.SUCCESS)
            self.append_log(f"删除完成：deleted={result.deleted}, already_absent={result.already_absent}")
        else:
            self.progress_label.configure(text="源文件删除已结束，但存在未完成项", text_color=Palette.WARNING)
            self.append_log(f"当前状态：deleted={result.deleted}, failed={result.failed}, pending={result.pending}")
            if result.failed_report:
                self.append_log(f"未删除清单：{result.failed_report}")
        self._refresh_controls()

    def finish_error(self, message: str) -> None:
        self._busy = False
        self._preflight = None
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text=f"任务失败：{message}", text_color=Palette.DANGER)
        self.append_log(f"错误：{message}")
        self._refresh_controls()

    def finish_cancelled(self) -> None:
        self._busy = False
        self._preflight = None
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="已在安全检查点停止，可稍后继续", text_color=Palette.WARNING)
        self.append_log("取消已生效；已完成删除的文件状态已写入 source-removal.json。")
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

    def _refresh_controls(self) -> None:
        self.batch_selector.set_busy(self._busy)
        self.browse_button.configure(state="disabled" if self._busy else "normal")
        if self._busy:
            self.preflight_button.configure(state="disabled")
            self.remove_button.configure(state="disabled")
            self.resume_button.configure(state="disabled")
            self.cancel_button.configure(state="normal")
            return
        info = self._info
        new_ready = bool(info and not info.has_state)
        self.preflight_button.configure(state="normal" if new_ready else "disabled")
        approved = bool(self._preflight and info and self._preflight.backup_path == info.backup_path)
        self.remove_button.configure(state="normal" if approved else "disabled")
        self.resume_button.configure(state="normal" if info and info.can_resume else "disabled")
        self.cancel_button.configure(state="disabled")

    def _pick_backup(self) -> None:
        path = filedialog.askdirectory(title="手动选择 FileCheck 备份批次目录")
        if path:
            self.backup_path.set(path)
            self._info = None
            self._preflight = None
            self._on_load(path)

    def _preflight_action(self) -> None:
        if self._info:
            self._on_preflight(str(self._info.backup_path))

    def _remove_action(self) -> None:
        if not self._info or not self._preflight:
            return
        dialog = DangerConfirmDialog(
            self.winfo_toplevel(),
            "确认删除源文件",
            f"将删除 manifest 中 {self._preflight.file_count} 个已复核源文件。备份不会被删除。该操作不可撤销。",
        )
        if dialog.show():
            self._on_remove(str(self._info.backup_path))

    def _resume_action(self) -> None:
        if not self._info or not self._info.can_resume:
            return
        dialog = DangerConfirmDialog(
            self.winfo_toplevel(),
            "确认继续源文件删除",
            f"将继续删除 {self._info.pending} 个 pending/failed 项。已删除文件不会再次删除；重新出现的路径会被保护。",
        )
        if dialog.show():
            self._on_resume(str(self._info.backup_path))

    def _cancel_action(self) -> None:
        self.progress_label.configure(text="已请求停止，等待当前文件处理并写入安全检查点……", text_color=Palette.WARNING)
        self._on_cancel()
