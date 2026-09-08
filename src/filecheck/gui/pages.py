from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from .components import Card, EmptyState, MetricCard, PageHeader, StatusPill
from .tokens import Layout, Palette, Radius, Spacing, Typography


RESULT_RENDER_LIMIT = 200


def _format_bytes(value: int) -> str:
    size = float(max(0, value))
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{int(value)} B"


class ResultPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        PageHeader(
            self,
            "扫描结果",
            "先查看结果摘要，再以完整 JSON/CSV 作为人工核对依据；关键词命中仅表示候选。",
        ).grid(row=0, column=0, sticky="ew")
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
        for column, card in enumerate([self.metric_total, self.metric_high, self.metric_sensitive, self.metric_review, self.metric_size]):
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else Spacing.XS, 0))

        meta = Card(self.result_host)
        meta.grid(row=1, column=0, sticky="ew", pady=(Spacing.MD, 0))
        meta.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(meta, text="人工核对文件", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.XS)
        )
        self.meta_label = ctk.CTkLabel(
            meta,
            text="",
            text_color=Palette.TEXT_SECONDARY,
            font=Typography.CAPTION,
            anchor="w",
            justify="left",
            wraplength=850,
        )
        self.meta_label.grid(row=1, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))

        list_card = Card(self.result_host)
        list_card.grid(row=2, column=0, sticky="nsew", pady=(Spacing.MD, 0))
        list_card.grid_columnconfigure(0, weight=1)
        list_card.grid_rowconfigure(1, weight=1)
        self.list_title = ctk.CTkLabel(list_card, text="候选文件", text_color=Palette.TEXT, font=Typography.CARD_TITLE, anchor="w")
        self.list_title.grid(row=0, column=0, sticky="ew", padx=Layout.CARD_PADDING, pady=(Layout.CARD_PADDING, Spacing.SM))
        self.rows_host = ctk.CTkScrollableFrame(
            list_card,
            fg_color=Palette.SURFACE_SUBTLE,
            corner_radius=Radius.CONTROL,
            height=300,
        )
        self.rows_host.grid(row=1, column=0, sticky="nsew", padx=Layout.CARD_PADDING, pady=(0, Layout.CARD_PADDING))
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
        accessibility = f"\n注意：其中 {inaccessible} 个文件当前不可访问，整批备份会拒绝继续。" if inaccessible else ""
        self.meta_label.configure(
            text=(
                f"JSON：{result.json_path}\n"
                f"CSV：{result.csv_path}\n"
                f"请人工核对 JSON/CSV 后再进入“备份”。{accessibility}"
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
