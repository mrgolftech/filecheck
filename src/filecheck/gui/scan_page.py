from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List

import customtkinter as ctk

from .components import Card, PageHeader, PrimaryButton, SecondaryButton, StatusPill
from .tokens import Layout, Palette, Radius, Spacing, Typography


class ScanPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_build_index: Callable[[List[str]], None],
        on_start_scan: Callable[[], None],
        on_cancel: Callable[[], None],
        on_open_settings: Callable[[], None],
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._on_build_index = on_build_index
        self._on_start_scan = on_start_scan
        self._on_cancel = on_cancel
        self._on_open_settings = on_open_settings
        self._drive_vars: Dict[str, tk.BooleanVar] = {}
        self._drive_checks = []
        self._index_ready = False
        self._busy = False

        PageHeader(
            self,
            "扫描",
            "先选择需要检查的磁盘并创建 FileCheck 专用索引；索引完成后直接执行关键词扫描。",
        ).grid(row=0, column=0, sticky="ew")

        index_card = Card(self)
        index_card.grid(row=1, column=0, sticky="ew", pady=(Spacing.LG, 0))
        index_card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(index_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="1. 选择磁盘并创建索引", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(row=0, column=0, sticky="w")
        self.index_state = StatusPill(header, "未建立索引", tone="warning")
        self.index_state.grid(row=0, column=1, sticky="e")

        self.drives_host = ctk.CTkFrame(index_card, fg_color="transparent")
        self.drives_host.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        self.drives_host.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="drive")
        self.no_drive_label = ctk.CTkLabel(
            self.drives_host,
            text="正在读取 Windows 磁盘信息……",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
        )
        self.no_drive_label.grid(row=0, column=0, columnspan=4, sticky="w")

        self.index_detail = ctk.CTkLabel(
            index_card,
            text="",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.SMALL,
            anchor="w",
            justify="left",
            wraplength=840,
        )
        self.index_detail.grid(row=2, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Spacing.SM, 0))
        index_actions = ctk.CTkFrame(index_card, fg_color="transparent")
        index_actions.grid(row=3, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Spacing.MD, Layout.CARD_PADDING))
        self.index_button = SecondaryButton(index_actions, "创建 / 更新索引", command=self._build_index, width=150)
        self.index_button.pack(side="left")

        rules_card = Card(self)
        rules_card.grid(row=2, column=0, sticky="ew", pady=(Spacing.MD, 0))
        rules_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(rules_card, text="2. 确认扫描规则并开始扫描", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        self.rules_label = ctk.CTkLabel(
            rules_card,
            text="正在读取关键词和文件类型……",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
            wraplength=840,
        )
        self.rules_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING)
        actions = ctk.CTkFrame(rules_card, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Spacing.MD, Layout.CARD_PADDING))
        SecondaryButton(actions, "修改扫描设置", command=self._on_open_settings, width=130).pack(side="left")
        self.scan_button = PrimaryButton(actions, "开始扫描", command=self._start_scan, width=130, state="disabled")
        self.scan_button.pack(side="left", padx=(Spacing.SM, 0))
        self.cancel_button = SecondaryButton(actions, "取消任务", command=self._cancel_task, width=110, state="disabled")
        self.cancel_button.pack(side="left", padx=(Spacing.SM, 0))

        run_card = Card(self)
        run_card.grid(row=3, column=0, sticky="nsew", pady=(Spacing.MD, 0))
        run_card.grid_columnconfigure(0, weight=1)
        run_card.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(run_card, text="执行状态", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM)
        )
        self.progress_label = ctk.CTkLabel(
            run_card,
            text="等待创建索引或开始扫描",
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

    def set_context(self, scan_info, index_info) -> None:
        current = set(str(value).lower() for value in index_info.selected_roots)
        self._index_ready = bool(index_info.selected_roots)
        for widget in self._drive_checks:
            widget.destroy()
        self._drive_checks = []
        self._drive_vars = {}
        self.no_drive_label.grid_remove()

        if not index_info.drives:
            self.no_drive_label.configure(text="未检测到可选择的 Windows 固定磁盘或可移动磁盘。")
            self.no_drive_label.grid()
        else:
            for idx, drive in enumerate(index_info.drives):
                selected = drive.root.lower() in current if current else drive.kind == "fixed"
                var = tk.BooleanVar(value=selected)
                self._drive_vars[drive.root] = var
                kind = "固定盘" if drive.kind == "fixed" else "可移动盘"
                check = ctk.CTkCheckBox(
                    self.drives_host,
                    text=f"{drive.root}  {kind} · {drive.filesystem}",
                    variable=var,
                    onvalue=True,
                    offvalue=False,
                    text_color=Palette.TEXT_SECONDARY,
                    fg_color=Palette.PRIMARY,
                    hover_color=Palette.PRIMARY_HOVER,
                    border_color=Palette.BORDER,
                    font=Typography.CAPTION,
                )
                check.grid(row=idx // 4, column=idx % 4, sticky="w", padx=(0, Spacing.SM), pady=Spacing.XS)
                self._drive_checks.append(check)

        if self._index_ready:
            self.index_state.set_tone("success", "索引已就绪")
            self.index_detail.configure(
                text=(
                    f"当前索引范围：{'、'.join(index_info.selected_roots)}    模式：{index_info.index_mode}\n"
                    f"索引数据库：{index_info.database_path or '-'}"
                ),
                text_color=Palette.TEXT_SECONDARY,
            )
        else:
            self.index_state.set_tone("warning", "需要创建索引")
            backup_tip = index_info.backup_root or "尚未设置，请先进入设置"
            self.index_detail.configure(
                text=f"尚未建立 FileCheck 专用索引。当前备份目录：{backup_tip}",
                text_color=Palette.WARNING,
            )

        labels = {"high": "高风险", "sensitive": "敏感", "review": "复核"}
        groups = []
        for level, values in scan_info.keywords.items():
            groups.append(f"{labels.get(level, level)}：{'、'.join(values)}")
        self.rules_label.configure(
            text=(
                "关键词：" + "  |  ".join(groups) + "\n"
                "文件类型：" + "、".join(f".{value}" for value in scan_info.extensions)
            )
        )
        self._refresh_controls()

    def selected_roots(self) -> List[str]:
        return [root for root, var in self._drive_vars.items() if bool(var.get())]

    def begin_index(self) -> None:
        self.winfo_toplevel().event_generate("<<FileCheckScanBasisChanged>>", when="tail")
        self._begin("正在创建 FileCheck 专用索引……")
        self.append_log("索引任务已启动。NTFS 快速索引需要管理员权限。")

    def finish_index(self, result) -> None:
        self._busy = False
        self._index_ready = True
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="索引创建完成，可以开始扫描", text_color=Palette.SUCCESS)
        self.index_state.set_tone("success", "索引已就绪")
        self.index_detail.configure(
            text=f"当前索引范围：{'、'.join(result.selected_roots)}\n索引数据库：{result.database_path}",
            text_color=Palette.TEXT_SECONDARY,
        )
        self._refresh_controls()

    def begin_scan(self) -> None:
        self._begin("正在扫描索引……")
        self.append_log("扫描任务已启动。扫描完成后会自动生成 JSON 和 CSV 供人工核对。")

    def finish_scan(self, total: int) -> None:
        self._busy = False
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text=f"扫描完成，共发现 {total} 个候选文件", text_color=Palette.SUCCESS)
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
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text=f"任务失败：{message}", text_color=Palette.DANGER)
        self.append_log(f"错误：{message}")
        self._refresh_controls()

    def finish_cancelled(self) -> None:
        self._busy = False
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="任务已取消", text_color=Palette.WARNING)
        self.append_log("取消请求已生效。")
        self._refresh_controls()

    def append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _begin(self, label: str) -> None:
        self._busy = True
        self._clear_log()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.progress_label.configure(text=label, text_color=Palette.PRIMARY)
        self._refresh_controls()

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _refresh_controls(self) -> None:
        state = "disabled" if self._busy else "normal"
        for check in self._drive_checks:
            check.configure(state=state)
        self.index_button.configure(state=state)
        self.scan_button.configure(state="normal" if self._index_ready and not self._busy else "disabled")
        self.cancel_button.configure(state="normal" if self._busy else "disabled")

    def _build_index(self) -> None:
        self._on_build_index(self.selected_roots())

    def _start_scan(self) -> None:
        self._on_start_scan()

    def _cancel_task(self) -> None:
        self.progress_label.configure(text="已请求取消，正在等待安全检查点……", text_color=Palette.WARNING)
        self._on_cancel()
