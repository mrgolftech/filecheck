from __future__ import annotations

import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from .components import Card, MetricCard, PageHeader, PrimaryButton, SecondaryButton, StatusPill
from .tokens import Layout, Palette, Radius, Spacing, Typography


def _format_bytes(value: int) -> str:
    size = float(max(0, int(value)))
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{int(value)} B"


class BackupPage(ctk.CTkFrame):
    def __init__(self, master, on_preflight, on_start_backup, on_cancel, on_open_settings=None):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.destination = tk.StringVar(value="")
        self._on_preflight = on_preflight
        self._on_start_backup = on_start_backup
        self._on_cancel = on_cancel
        self._on_open_settings = on_open_settings
        self._scan_ready = False
        self._busy = False
        self._approved_destination = None

        PageHeader(
            self,
            "备份",
            "备份当前扫描结果到“设置”中指定的统一目录；执行前先核对扫描摘要和空间条件。",
        ).grid(row=0, column=0, sticky="ew")

        source_card = Card(self)
        source_card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        source_card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(source_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="待备份扫描结果", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(row=0, column=0, sticky="w")
        self.source_state = StatusPill(header, "等待扫描", tone="neutral")
        self.source_state.grid(row=0, column=1, sticky="e")
        self.source_label = ctk.CTkLabel(
            source_card,
            text="请先完成扫描。扫描摘要、JSON 和 CSV 路径会自动带入这里。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
            wraplength=860,
        )
        self.source_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))

        target_card = Card(self)
        target_card.grid(row=2, column=0, sticky="ew", pady=(Spacing.MD, 0))
        target_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(target_card, text="备份目录与预检", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        self.destination_label = ctk.CTkLabel(
            target_card,
            text="备份目录：未设置",
            text_color=Palette.WARNING,
            font=Typography.BODY_MEDIUM,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.destination_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        if self._on_open_settings is not None:
            SecondaryButton(target_card, "打开设置", command=self._on_open_settings, width=110).grid(
                row=1, column=1, padx=(Spacing.SM, Layout.CARD_PADDING)
            )

        metrics = ctk.CTkFrame(target_card, fg_color="transparent")
        metrics.grid(row=2, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.MD, 0))
        for column in range(4):
            metrics.grid_columnconfigure(column, weight=1, uniform="backup_metric")
        self.metric_files = MetricCard(metrics, "文件数")
        self.metric_source = MetricCard(metrics, "源数据")
        self.metric_required = MetricCard(metrics, "预计需求", tone="warning")
        self.metric_free = MetricCard(metrics, "目标盘可用", tone="success")
        for column, metric in enumerate([self.metric_files, self.metric_source, self.metric_required, self.metric_free]):
            metric.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else Spacing.XS, 0))

        self.strategy_label = ctk.CTkLabel(
            target_card,
            text="复制时计算 SHA-256，复制完成后对备份再次执行全量 SHA-256 校验；备份本身不会删除源文件。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
        )
        self.strategy_label.grid(row=3, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, 0))
        actions = ctk.CTkFrame(target_card, fg_color="transparent")
        actions.grid(row=4, column=0, columnspan=2, sticky="w", padx=Layout.CARD_PADDING, pady=(Spacing.MD, Layout.CARD_PADDING))
        self.preflight_button = SecondaryButton(actions, "检查备份条件", command=self._start_preflight, width=130, state="disabled")
        self.preflight_button.pack(side="left")
        self.start_button = PrimaryButton(actions, "开始备份", command=self._start_backup, width=130, state="disabled")
        self.start_button.pack(side="left", padx=(Spacing.SM, 0))
        self.cancel_button = SecondaryButton(actions, "取消任务", command=self._cancel_task, width=110, state="disabled")
        self.cancel_button.pack(side="left", padx=(Spacing.SM, 0))

        run_card = Card(self)
        run_card.grid(row=3, column=0, sticky="nsew", pady=(Spacing.MD, 0))
        run_card.grid_columnconfigure(0, weight=1)
        run_card.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(run_card, text="执行状态", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        self.progress_label = ctk.CTkLabel(
            run_card, text="等待备份预检", text_color=Palette.TEXT_SECONDARY, font=Typography.CAPTION, anchor="w"
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
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.XS, Spacing.SM))
        self.progress_bar.set(0)
        self.result_label = ctk.CTkLabel(
            run_card,
            text="",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
            wraplength=860,
        )
        self.result_label.grid(row=3, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(0, Spacing.XS))
        self.log_box = ctk.CTkTextbox(
            run_card,
            fg_color=Palette.SURFACE_SUBTLE,
            border_width=0,
            corner_radius=Radius.CONTROL,
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            wrap="word",
            height=110,
        )
        self.log_box.grid(row=4, column=0, sticky="nsew", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))
        self.log_box.configure(state="disabled")

    def set_scan_result(self, result) -> None:
        count = int(result.counts.get("total", 0))
        self._scan_ready = count > 0
        inaccessible = int(result.inaccessible_count)
        if count:
            tone = "warning" if inaccessible else "success"
            self.source_state.set_tone(tone, "需处理" if inaccessible else "已就绪")
            warning = f"；其中 {inaccessible} 个当前不可访问" if inaccessible else ""
            self.source_label.configure(
                text=(
                    f"候选：{count} 个    高风险：{result.counts.get('high', 0)}    "
                    f"敏感：{result.counts.get('sensitive', 0)}    复核：{result.counts.get('review', 0)}\n"
                    f"总容量：{_format_bytes(result.total_size)}{warning}\n"
                    f"JSON：{result.json_path}\nCSV：{result.csv_path}"
                ),
                text_color=Palette.TEXT_SECONDARY,
            )
        else:
            self.source_state.set_tone("warning", "无候选")
            self.source_label.configure(text="当前扫描结果没有候选文件。", text_color=Palette.WARNING)
        self._invalidate_preflight()
        self._refresh_controls()

    def set_suggested_destination(self, value) -> None:
        self.destination.set(str(value) if value else "")
        if value:
            self.destination_label.configure(text=f"备份目录：{value}", text_color=Palette.TEXT_SECONDARY)
        else:
            self.destination_label.configure(text="备份目录：未设置，请先到“设置”中配置", text_color=Palette.WARNING)
        self._invalidate_preflight()
        self._refresh_controls()

    def begin_preflight(self) -> None:
        self._approved_destination = None
        self._clear_log()
        self.result_label.configure(text="")
        self._busy = True
        self._refresh_controls()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="正在检查备份条件……", text_color=Palette.PRIMARY)
        self.append_log("备份预检任务已启动。")

    def finish_preflight(self, result) -> None:
        self._approved_destination = str(result.destination_root)
        self.metric_files.set_value(str(result.file_count))
        self.metric_source.set_value(_format_bytes(result.source_bytes))
        self.metric_required.set_value(_format_bytes(result.required_bytes), "warning")
        free_text = _format_bytes(result.free_bytes) if result.free_bytes is not None else "未知"
        self.metric_free.set_value(free_text, "success" if result.free_bytes is not None else "neutral")
        self._busy = False
        self._refresh_controls()
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="备份预检通过，可以开始备份", text_color=Palette.SUCCESS)
        self.result_label.configure(text=f"目标目录：{result.destination_root}\n安全余量：{_format_bytes(result.reserve_bytes)}")

    def begin_backup(self) -> None:
        self._clear_log()
        self._busy = True
        self._refresh_controls()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="正在创建并校验备份……", text_color=Palette.PRIMARY)
        self.result_label.configure(text="")
        self.append_log("正式备份任务已启动；该步骤不会删除源文件。")

    def finish_backup(self, result) -> None:
        self._approved_destination = None
        self._busy = False
        self._refresh_controls()
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="备份完成并通过全量 SHA-256 校验", text_color=Palette.SUCCESS)
        throughput = f"    平均处理吞吐：{result.throughput_mib_s:.1f} MiB/s" if result.throughput_mib_s is not None else ""
        self.result_label.configure(
            text=(
                f"备份批次：{result.backup_path}\n"
                f"文件数：{result.file_count}    总容量：{_format_bytes(result.total_bytes)}"
                f"    耗时：{result.elapsed_seconds:.1f} 秒{throughput}\n"
                f"manifest：{Path(result.backup_path) / 'manifest.json'}"
            ),
            text_color=Palette.SUCCESS,
        )
        self.append_log("备份已安全完成。需要时可进入“源文件删除”进行独立高风险操作。")

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
        self._approved_destination = None
        self._busy = False
        self._refresh_controls()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text=f"任务失败：{message}", text_color=Palette.DANGER)
        self.result_label.configure(text="请处理错误后重新执行备份预检。", text_color=Palette.DANGER)
        self.append_log(f"错误：{message}")

    def finish_cancelled(self) -> None:
        self._approved_destination = None
        self._busy = False
        self._refresh_controls()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="任务已安全取消", text_color=Palette.WARNING)
        self.result_label.configure(text="如需继续，请重新执行备份预检。", text_color=Palette.WARNING)
        self.append_log("任务取消请求已在安全检查点生效。")

    def append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _invalidate_preflight(self) -> None:
        self._approved_destination = None
        self.metric_files.set_value("-")
        self.metric_source.set_value("-")
        self.metric_required.set_value("-")
        self.metric_free.set_value("-")

    def _refresh_controls(self) -> None:
        destination_ready = bool(self.destination.get().strip())
        self.preflight_button.configure(state="normal" if self._scan_ready and destination_ready and not self._busy else "disabled")
        approved = self._approved_destination and self._approved_destination == self.destination.get().strip()
        self.start_button.configure(state="normal" if approved and not self._busy else "disabled")
        self.cancel_button.configure(state="normal" if self._busy else "disabled")

    def _start_preflight(self) -> None:
        self._on_preflight(self.destination.get().strip())

    def _start_backup(self) -> None:
        self._on_start_backup(self.destination.get().strip())

    def _cancel_task(self) -> None:
        self.progress_label.configure(text="已请求取消，正在等待当前文件安全结束……", text_color=Palette.WARNING)
        self._on_cancel()
