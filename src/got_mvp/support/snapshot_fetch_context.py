"""一次性生成「取数上下文」JSON：系统/指定取数日 → 上证锚定、近交易日、月度区间、资讯时间窗。

与 ``MCP_宏观_EDB_取数.md``、``MCP_资讯_取数.md`` 步骤 0 对齐；可由 Agent 先运行本模块再调 MCP。

用法::

    python -m src.got_mvp.support.snapshot_fetch_context
    python -m src.got_mvp.support.snapshot_fetch_context 2026-05-05
    python -m src.got_mvp.support.snapshot_fetch_context --write
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone

from src.got_mvp.support.cn_trading_days import (
    last_trading_day_on_or_before,
    macro_edb_month_compact_span,
    n_trading_days_ending_at,
    news_mcp_date_window,
)
from src.got_mvp.support.snapshot_loader import snapshot_dir_for_date


def _parse_iso_date(s: str) -> date:
    return date.fromisoformat(s.strip())


def build_fetch_context(snapshot_calendar_date: date) -> dict:
    """``snapshot_calendar_date``：取数日（可为非交易日，如系统今日周末）。"""
    sse_anchor = last_trading_day_on_or_before(snapshot_calendar_date)
    ten = n_trading_days_ending_at(sse_anchor, 10)
    d0, d9 = ten[0], ten[-1]
    compact_sse = f"{d0.strftime('%Y%m%d')}-{d9.strftime('%Y%m%d')}"
    start_ym, end_ym = macro_edb_month_compact_span(sse_anchor, inclusive_months=6)
    macro_compact = f"（{start_ym}-{end_ym}）"
    macro_monthly_suffix_zh = f"{macro_compact}每月数值"
    news = news_mcp_date_window(snapshot_calendar_date)
    news_compat = news.as_json_dict()
    meta_patch = {
        "snapshot_date": snapshot_calendar_date.isoformat(),
        **news.as_meta_fields(),
    }
    return {
        "snapshot_calendar_date": snapshot_calendar_date.isoformat(),
        "sse_anchor_last_trading_day_on_or_before_snapshot": sse_anchor.isoformat(),
        "sse_ten_trading_days_oldest_first": [d.isoformat() for d in ten],
        "edb_sse_daily_compact_span": compact_sse,
        "edb_sse_query_zh_template": (
            f"上证综指收盘价 日度 （{compact_sse}）每日数值"
        ),
        "macro_monthly_compact_span": macro_compact,
        "macro_monthly_query_segment_zh": macro_monthly_suffix_zh,
        "macro_monthly_start_ym": start_ym,
        "macro_monthly_end_ym": end_ym,
        "search_news": news_compat["search_news"],
        "news_calendar_context": {
            "snapshot_date": news_compat["snapshot_date"],
            "previous_trading_day": news_compat["previous_trading_day"],
        },
        "cn_trading_days_json_compat": news_compat,
        "meta_patch_suggested_fields": meta_patch,
    }


def default_snapshot_calendar_date(cli_arg: str | None) -> date:
    """无参数则用本机日历今日（UTC+8 由用户会话决定；此处为 Python ``date.today()``）。"""
    if cli_arg and cli_arg.strip():
        return _parse_iso_date(cli_arg)
    return date.today()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="根据取数日生成 fetch_context JSON（上证 10 交易日、月度 EDB 区间、search_news）。"
    )
    p.add_argument(
        "snapshot_date",
        nargs="?",
        default=None,
        help="取数日 YYYY-MM-DD；省略则用 date.today()",
    )
    p.add_argument(
        "--write",
        action="store_true",
        help="写入 data/agent_input/snapshot_{D}/fetch_context.json（目录不存在则创建）",
    )
    ns = p.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    snap = default_snapshot_calendar_date(ns.snapshot_date)
    ctx = build_fetch_context(snap)
    ctx["generated_at_iso"] = datetime.now(timezone.utc).isoformat()
    payload = ctx

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))

    if ns.write:
        snap_dir = snapshot_dir_for_date(snap.isoformat())
        snap_dir.mkdir(parents=True, exist_ok=True)
        path = snap_dir / "fetch_context.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
