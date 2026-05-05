# 【工具】A 股上一交易日与 search_news 的 time_start / time_end 推算（依赖 chinesecalendar，无则退化周末跳过）。
# 调用方：无库内 import；由 CLI ``python -m src.got_mvp.support.cn_trading_days`` 人工运行，供 MCP 资讯取数与 meta 对齐。上证/月度窗与默认取数日见 ``snapshot_fetch_context``（prompt_md/取数/*.md §步骤 0）。
"""A 股交易日推算：用于资讯 MCP 的 time_start / time_end 与 meta 对齐。

口径与 `prompt_md/取数/MCP_资讯_取数.md` 一致：
- **取数日**：`data/agent_input/snapshot_*` 目录名后缀 / `meta.snapshot_date`（日历日，可为周末）。
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


def last_trading_day_on_or_before(ref: date) -> date:
    """``ref`` 当日（含）往回的最近一个 A 股交易日；取数日可为周末/假日。

    用于 **上证综指日度** 等「截至取数日已收盘」的锚定；与 ``previous_trading_day_before`` 不同：若 ``ref`` 本身是交易日则返回 ``ref``。
    """
    d = ref
    for _ in range(400):
        if _is_sse_trading_day(d):
            return d
        d -= timedelta(days=1)
    raise ValueError(f"400 日内未找到不晚于 {ref} 的交易日（检查日历数据）")


def n_trading_days_ending_at(anchor: date, n: int) -> list[date]:
    """以 ``anchor`` 为**最近**一日，向前数 ``n`` 个上交所交易日，返回 **旧→新**。"""
    if n < 1:
        raise ValueError("n 须 >= 1")
    out_rev: list[date] = []
    d = anchor
    while len(out_rev) < n:
        if _is_sse_trading_day(d):
            out_rev.append(d)
        d -= timedelta(days=1)
    return list(reversed(out_rev))


def macro_edb_month_compact_span(anchor: date, *, inclusive_months: int = 6) -> tuple[str, str]:
    """月度 EDB ``（YYYYMM-YYYYMM）`` 占位：锚定月为结束月，往前共 ``inclusive_months`` 个自然月（与 MCP_宏观_EDB_取数 示例对齐）。"""
    if inclusive_months < 1:
        raise ValueError("inclusive_months 须 >= 1")
    end_idx = anchor.year * 12 + anchor.month - 1
    start_idx = end_idx - (inclusive_months - 1)
    sy, sm_raw = divmod(start_idx, 12)
    sm = sm_raw + 1
    start_ym = f"{sy:04d}{sm:02d}"
    end_ym = f"{anchor.year:04d}{anchor.month:02d}"
    return start_ym, end_ym


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
