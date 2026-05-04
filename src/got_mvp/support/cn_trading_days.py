# 【工具】A 股上一交易日与 search_news 的 time_start / time_end 推算（依赖 chinesecalendar，无则退化周末跳过）。
# 调用方：无库内 import；由 CLI ``python -m src.got_mvp.support.cn_trading_days`` 人工运行，供 MCP 资讯取数与 meta 对齐（见 prompt_md/取数/MCP_资讯_取数.md）。
"""A 股交易日推算：用于资讯 MCP 的 time_start / time_end 与 meta 对齐。

口径与 `prompt_md/取数/MCP_资讯_取数.md` 一致：
- **取数日**：快照目录名 / `meta.snapshot_date`（日历日，可为周末）。
- **上一交易日**：严格早于取数日 0 点的、最近一次上交所交易日（含调休工作日）。
- **search_news**：`time_start` = 上一交易日 `YYYY-MM-DD`，`time_end` = 取数日 `YYYY-MM-DD`
  （工具仅支持日期时，语义为「上一交易日自然日～取数日自然日」闭区间）。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

try:
    import chinese_calendar as _cc

    def _is_sse_trading_day(d: date) -> bool:
        return bool(_cc.is_workday(d))

except ImportError:  # pragma: no cover - 无依赖时退化

    def _is_sse_trading_day(d: date) -> bool:
        return d.weekday() < 5


def previous_trading_day_before(ref: date) -> date:
    """严格早于 ``ref`` 的最近一个 A 股交易日（不含 ``ref`` 当天）。"""
    d = ref - timedelta(days=1)
    while not _is_sse_trading_day(d):
        d -= timedelta(days=1)
    return d


@dataclass(frozen=True)
class NewsMcpDateWindow:
    snapshot_date: date
    previous_trading_day: date
    time_start: str
    time_end: str

    def as_meta_fields(self) -> dict[str, Any]:
        return {
            "news_previous_trading_day": self.previous_trading_day.isoformat(),
            "news_time_start": self.time_start,
            "news_time_end": self.time_end,
            "news_window": (
                f"search_news 闭区间日期：time_start={self.time_start}（上一交易日，"
                f"相对 snapshot_date={self.time_end} 推算），time_end={self.time_end}（取数日）；"
                f"语义：上一交易日收盘后增量至取数日当前（MCP 仅日期粒度）。"
            ),
        }

    def as_json_dict(self) -> dict[str, Any]:
        return {
            "snapshot_date": self.time_end,
            "previous_trading_day": self.previous_trading_day.isoformat(),
            "search_news": {
                "time_start": self.time_start,
                "time_end": self.time_end,
            },
        }


def news_mcp_date_window(snapshot_date: date) -> NewsMcpDateWindow:
    prev = previous_trading_day_before(snapshot_date)
    return NewsMcpDateWindow(
        snapshot_date=snapshot_date,
        previous_trading_day=prev,
        time_start=prev.isoformat(),
        time_end=snapshot_date.isoformat(),
    )


def _parse_iso(s: str) -> date:
    return date.fromisoformat(s.strip())


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(
            "用法: python -m src.got_mvp.support.cn_trading_days YYYY-MM-DD\n"
            "输出 JSON：search_news 的 time_start / time_end 及上一交易日。",
            file=sys.stderr,
        )
        sys.exit(2)
    snap = _parse_iso(argv[0])
    w = news_mcp_date_window(snap)
    print(json.dumps(w.as_json_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
