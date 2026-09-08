from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
import tkinter as tk

import customtkinter as ctk

from .components import (
    Card,
    EmptyState,
    MetricCard,
    PageHeader,
    PrimaryButton,
    SecondaryButton,
    StatusPill,
)
from .tokens import Layout, Palette, Radius, Spacing, Typography


RESULT_RENDER_LIMIT = 200


def _format_bytes(value: int) -> str:
    size = float(max(0, value))
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{int(value)} B"


class BasePage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)


class HomePage(BasePage):
    def __init__(self, master, on_navigate):
        super().__init__(master)
        PageHeader(
            self,
            "首页",
            "按“扫描 → 备份与迁出 → 恢复”的固定流程完成文件检查和安全迁移。",
        ).grid(row=0, column=0, sticky="ew")

        overview = Card(self)
        overview.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        overview.grid_columnconfigure((0, 1, 2), weight=1, uniform="workflow")

        steps = [
            ("1", "扫描文件", "按统一规则查找目标文件", "scan"),
            ("2", "备份与迁出", "校验备份后再处理源文件", "backup"),
            ("3", "恢复文件", "按清单恢复至原始路径", "restore"),
        ]
        for column, (number, title, description, target) in enumerate(steps):
            cell = ctk.CTkFrame(overview, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="nsew", padx=Layout.CARD_PADDING, pady=Layout.CARD_PADDING)
            StatusPill(cell, f"步骤 {number}", tone="info").pack(anchor="w")
            ctk.CTkLabel(cell, text=title, text_color=Palette.TEXT, font=Typography.CARD_TITLE).pack(
                anchor="w", pady=(Spacing.MD, Spacing.XS)
            )
            ctk.CTkLabel(
                cell,
                text=description,
                text_color=Palette.TEXT_SECONDARY,
                font=Typography.CAPTION,
                anchor="w",
            ).pack(anchor="w")
            SecondaryButton(cell, "进入", command=lambda name=target: on_navigate(name), width=90).pack(
                anchor="w", pady=(Spacing.LG, 0)
            )

        status = Card(self)
        status.grid(row=2, column=0, sticky="ew", pady=(Spacing.MD, 0))
        status.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(status, text="当前状态", text_color=Palette.TEXT, font=Typography.SECTION_TITLE).grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        ctk.CTkLabel(
            status,
            text="GUI 扫描闭环正在接入现有 FileCheck 核心；CLI 仍保留为独立、可回归的操作入口。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))


class ScanPage(BasePage):
    def __init__(self, master, on_start_scan, on_cancel_scan):
        super().__init__(master)
        self.grid_rowconfigure(3, weight=1)
        self.scan_path = tk.StringVar(value="")
        self.match_path = tk.BooleanVar(value=False)
        self._on_start_scan = on_start_scan
        self._on_cancel_scan = on_cancel_scan

        PageHeader(self, "扫描", "核对索引和规则，选择可选的扫描子目录后开始检查。").grid(
            row=0, column=0, sticky="ew"
        )

        context_card = Card(self)
        context_card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        context_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(context_card, text="当前扫描基线", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0,
            column=0,
            sticky="w",
            padx=Layout.CARD_PADDING,
            pady=(Layout.CARD_PADDING, Spacing.SM),
        )
        self.index_label = ctk.CTkLabel(
            context_card,
            text="索引状态：正在读取……",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
        )
        self.index_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        self.rules_label = ctk.CTkLabel(
            context_card,
            text="扫描规则：正在读取……",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.rules_label.grid(row=2, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.XS, 0))
        self.extensions_label = ctk.CTkLabel(
            context_card,
            text="文件类型：正在读取……",
            text_color=Palette.TEXT_MUTED,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.extensions_label.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=Layout.CARD_PADDING,
            pady=(Spacing.XS, Layout.CARD_PADDING),
        )

        scan_card = Card(self)
        scan_card.grid(row=2, column=0, sticky="ew", pady=(Spacing.MD, 0))
        scan_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(scan_card, text="扫描范围", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=Layout.CARD_PADDING,
            pady=(Layout.CARD_PADDING, Spacing.SM),
        )
        self.path_entry = ctk.CTkEntry(
            scan_card,
            textvariable=self.scan_path,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            border_color=Palette.BORDER,
            fg_color=Palette.SURFACE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
            placeholder_text="留空表示扫描全部已索引范围；也可选择其中一个子目录",
        )
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(Layout.CARD_PADDING, Spacing.SM))
        self.browse_button = SecondaryButton(scan_card, "选择目录", command=self._pick_scan_path, width=110)
        self.browse_button.grid(row=1, column=1, padx=(0, Layout.CARD_PADDING))
        self.match_checkbox = ctk.CTkCheckBox(
            scan_card,
            text="关键词同时匹配目录路径（默认关闭，减少误报）",
            variable=self.match_path,
            onvalue=True,
            offvalue=False,
            text_color=Palette.TEXT_SECONDARY,
            fg_color=Palette.PRIMARY,
            hover_color=Palette.PRIMARY_HOVER,
            border_color=Palette.BORDER,
            font=Typography.CAPTION,
        )
        self.match_checkbox.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            padx=Layout.CARD_PADDING,
            pady=(Spacing.SM, Spacing.LG),
        )
        actions = ctk.CTkFrame(scan_card, fg_color="transparent")
        actions.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            padx=Layout.CARD_PADDING,
            pady=(0, Layout.CARD_PADDING),
        )
        self.start_button = PrimaryButton(actions, "开始扫描", command=self._start, width=130)
        self.start_button.pack(side="left")
        self.cancel_button = SecondaryButton(actions, "取消任务", command=self._cancel, width=110, state="disabled")
        self.cancel_button.pack(side="left", padx=(Spacing.SM, 0))

        run_card = Card(self)
        run_card.grid(row=3, column=0, sticky="nsew", pady=(Spacing.MD, 0))
        run_card.grid_columnconfigure(0, weight=1)
        run_card.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(run_card, text="执行状态", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0,
            column=0,
            sticky="w",
            padx=Layout.CARD_PADDING,
            pady=(Layout.CARD_PADDING, Spacing.SM),
        )
        self.progress_label = ctk.CTkLabel(
            run_card,
            text="等待开始扫描",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
        )
        self.progress_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        self.progress_bar = ctk.CTkProgressBar(
            run_card,
            mode="determinate",
            height=8,
            corner_radius=4,
            fg_color=Palette.SURFACE_SUBTLE,
            progress_color=Palette.PRIMARY,
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
        self.log_box.grid(
            row=3,
            column=0,
            sticky="nsew",
            padx=Layout.CARD_PADDING,
            pady=(0, Layout.CARD_PADDING),
        )
        self.log_box.configure(state="disabled")

    def set_context(self, info) -> None:
        if info.selected_roots:
            self.index_label.configure(
                text=f"索引范围：{'、'.join(info.selected_roots)}    模式：{info.index_mode}",
                text_color=Palette.TEXT_SECONDARY,
            )
        else:
            self.index_label.configure(
                text="尚未建立 FileCheck 专用索引，需要先通过 CLI 完成“环境与索引”。",
                text_color=Palette.WARNING,
            )
        groups = []
        labels = {"high": "高风险", "sensitive": "敏感", "review": "复核"}
        for level, values in info.keywords.items():
            groups.append(f"{labels.get(level, level)}：{'、'.join(values)}")
        self.rules_label.configure(text="扫描规则：" + "  |  ".join(groups) + f"\n规则文件：{info.rules_path}")
        self.extensions_label.configure(text="文件类型：" + "、".join(f".{value}" for value in info.extensions))

    def set_busy(self, busy: bool) -> None:
        normal = "disabled" if busy else "normal"
        self.start_button.configure(state=normal)
        self.path_entry.configure(state=normal)
        self.browse_button.configure(state=normal)
        self.match_checkbox.configure(state=normal)
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if busy:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
        else:
            self.progress_bar.stop()

    def begin_task(self) -> None:
        self._clear_log()
        self.set_busy(True)
        self.progress_label.configure(text="扫描任务已启动……", text_color=Palette.PRIMARY)
        self.append_log("GUI 后台任务已启动。")

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

    def finish_success(self, total: int) -> None:
        self.set_busy(False)
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text=f"扫描完成，共发现 {total} 个候选文件", text_color=Palette.SUCCESS)

    def finish_error(self, message: str) -> None:
        self.set_busy(False)
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text=f"扫描失败：{message}", text_color=Palette.DANGER)
        self.append_log(f"错误：{message}")

    def finish_cancelled(self) -> None:
        self.set_busy(False)
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="任务已取消", text_color=Palette.WARNING)
        self.append_log("任务取消请求已生效。")

    def append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _pick_scan_path(self) -> None:
        path = filedialog.askdirectory(title="选择扫描目录")
        if path:
            self.scan_path.set(path)

    def _start(self) -> None:
        scope = self.scan_path.get().strip() or None
        self._on_start_scan(scope, bool(self.match_path.get()))

    def _cancel(self) -> None:
        self.progress_label.configure(text="已请求取消，正在等待当前查询安全结束……", text_color=Palette.WARNING)
        self._on_cancel_scan()


class ResultPage(BasePage):
    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(2, weight=1)
        PageHeader(self, "扫描结果", "先在界面快速浏览候选，再以完整 JSON/CSV 作为人工核对依据。").grid(
            row=0, column=0, sticky="ew"
        )
        self.empty_state = EmptyState(self, "暂无扫描结果", "完成一次扫描后，这里将显示结果摘要和候选文件列表。")
        self.empty_state.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))

        self.result_host = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.result_host.grid(row=1, column=0, rowspan=2, sticky="nsew", pady=(Spacing.LG, 0))
        self.result_host.grid_columnconfigure(0, weight=1)
        self.result_host.grid_rowconfigure(2, weight=1)
        self.result_host.grid_remove()

        metrics = ctk.CTkFrame(self.result_host, fg_color="transparent")
        metrics.grid(row=0, column=0, sticky="ew")
        for column in range(5):
            metrics.grid_columnconfigure(column, weight=1, uniform="metric")
        self.metric_total = MetricCard(metrics, "候选总数", tone="info")
        self.metric_high = MetricCard(metrics, "高风险", tone="danger")
        self.metric_sensitive = MetricCard(metrics, "敏感", tone="warning")
        self.metric_review = MetricCard(metrics, "复核", tone="neutral")
        self.metric_size = MetricCard(metrics, "总容量", tone="neutral")
        for column, card in enumerate(
            [self.metric_total, self.metric_high, self.metric_sensitive, self.metric_review, self.metric_size]
        ):
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else Spacing.XS, 0))

        meta = Card(self.result_host)
        meta.grid(row=1, column=0, sticky="ew", pady=(Spacing.MD, 0))
        meta.grid_columnconfigure(0, weight=1)
        self.meta_label = ctk.CTkLabel(
            meta,
            text="",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.meta_label.grid(row=0, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=Layout.CARD_PADDING)

        list_card = Card(self.result_host)
        list_card.grid(row=2, column=0, sticky="nsew", pady=(Spacing.MD, 0))
        list_card.grid_columnconfigure(0, weight=1)
        list_card.grid_rowconfigure(1, weight=1)
        self.list_title = ctk.CTkLabel(
            list_card,
            text="候选文件",
            text_color=Palette.TEXT,
            font=Typography.CARD_TITLE,
            anchor="w",
        )
        self.list_title.grid(row=0, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        self.rows_host = ctk.CTkScrollableFrame(
            list_card,
            fg_color=Palette.SURFACE_SUBTLE,
            corner_radius=Radius.CONTROL,
            height=300,
        )
        self.rows_host.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=Layout.CARD_PADDING,
            pady=(0, Layout.CARD_PADDING),
        )
        self.rows_host.grid_columnconfigure(1, weight=1)

    def set_result(self, result) -> None:
        self.empty_state.grid_remove()
        self.result_host.grid()
        counts = result.counts
        self.metric_total.set_value(str(counts.get("total", 0)), "info")
        self.metric_high.set_value(str(counts.get("high", 0)), "danger")
        self.metric_sensitive.set_value(str(counts.get("sensitive", 0)), "warning")
        self.metric_review.set_value(str(counts.get("review", 0)))
        self.metric_size.set_value(_format_bytes(result.total_size))

        inaccessible = result.inaccessible_count
        accessibility = f"；其中 {inaccessible} 个当前不可访问" if inaccessible else ""
        self.meta_label.configure(
            text=(
                f"JSON：{result.json_path}\n"
                f"CSV：{result.csv_path}\n"
                f"关键词命中仅表示候选，请人工核对后再进入备份{accessibility}。"
            )
        )

        for child in self.rows_host.winfo_children():
            child.destroy()
        items = result.items
        render_items = items[:RESULT_RENDER_LIMIT]
        self.list_title.configure(
            text=f"候选文件（显示 {len(render_items)} / {len(items)}）"
            if len(items) > len(render_items)
            else f"候选文件（{len(items)}）"
        )
        tone_map = {"high": "danger", "sensitive": "warning", "review": "neutral"}
        name_map = {"high": "高风险", "sensitive": "敏感", "review": "复核"}
        for row, item in enumerate(render_items):
            severity = str(item.get("severity", "review"))
            StatusPill(
                self.rows_host,
                name_map.get(severity, severity),
                tone=tone_map.get(severity, "neutral"),
            ).grid(row=row, column=0, sticky="nw", padx=(Spacing.SM, Spacing.SM), pady=Spacing.XS)
            detail = ctk.CTkFrame(self.rows_host, fg_color="transparent")
            detail.grid(row=row, column=1, sticky="ew", padx=(0, Spacing.SM), pady=Spacing.XS)
            detail.grid_columnconfigure(0, weight=1)
            path = str(item.get("path", ""))
            filename = Path(path).name or path
            ctk.CTkLabel(
                detail,
                text=filename,
                text_color=Palette.TEXT,
                font=Typography.BODY_MEDIUM,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew")
            keywords = "、".join(str(value) for value in item.get("matched_keywords", []))
            size = item.get("size")
            size_text = _format_bytes(int(size)) if isinstance(size, int) else "大小未知"
            ctk.CTkLabel(
                detail,
                text=f"{path}\n命中：{keywords or '-'}    {size_text}",
                text_color=Palette.TEXT_SECONDARY,
                font=Typography.SMALL,
                anchor="w",
                justify="left",
                wraplength=700,
            ).grid(row=1, column=0, sticky="ew", pady=(Spacing.XXS, 0))


class BackupPage(BasePage):
    def __init__(self, master, notify):
        super().__init__(master)
        self.backup_path = tk.StringVar(value="")
        PageHeader(self, "备份与迁出", "确认备份目标、所需空间和校验状态后执行批量备份。").grid(
            row=0, column=0, sticky="ew"
        )
        card = Card(self)
        card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="备份位置", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        ctk.CTkEntry(
            card,
            textvariable=self.backup_path,
            height=Layout.CONTROL_HEIGHT,
            corner_radius=Radius.CONTROL,
            border_color=Palette.BORDER,
            fg_color=Palette.SURFACE,
            text_color=Palette.TEXT,
            font=Typography.BODY,
            placeholder_text="选择备份目标目录",
        ).grid(row=1, column=0, sticky="ew", padx=(Layout.CARD_PADDING, Spacing.SM))
        SecondaryButton(card, "选择目录", command=self._pick_backup_path, width=110).grid(
            row=1, column=1, padx=(0, Layout.CARD_PADDING)
        )
        ctk.CTkLabel(
            card,
            text="下一阶段将接入现有备份核心，并在执行前显示文件数量、总容量、可用空间和校验策略。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, Spacing.LG))
        PrimaryButton(card, "开始备份", command=lambda: notify("备份业务接口将在下一阶段接入", "info"), width=130).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING)
        )

    def _pick_backup_path(self) -> None:
        path = filedialog.askdirectory(title="选择备份目录")
        if path:
            self.backup_path.set(path)


class RestorePage(BasePage):
    def __init__(self, master, notify):
        super().__init__(master)
        PageHeader(self, "恢复", "读取备份清单并将文件恢复到原始路径。").grid(row=0, column=0, sticky="ew")
        card = Card(self)
        card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="恢复清单", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        ctk.CTkLabel(
            card,
            text="正式接入后支持选择 manifest，并先进行完整性校验和冲突预检查。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        SecondaryButton(card, "选择清单", command=lambda: notify("恢复清单选择将在后续阶段完成", "neutral"), width=120).grid(
            row=2, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Spacing.LG, Layout.CARD_PADDING)
        )


class SettingsPage(BasePage):
    def __init__(self, master):
        super().__init__(master)
        PageHeader(self, "设置", "集中管理扫描规则、界面偏好和运行环境信息。").grid(row=0, column=0, sticky="ew")
        card = Card(self)
        card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="界面基线", font=Typography.CARD_TITLE, text_color=Palette.TEXT).grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        ctk.CTkLabel(
            card,
            text="当前采用统一浅色主题。颜色、字体、间距和公共控件由设计系统集中管理。",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.BODY,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))
