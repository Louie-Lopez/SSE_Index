# 【工具】从 ``got_mvp/data/snapshot_{YYYY-MM-DD}/`` 分片合并为 LangGraph 用的 ``snapshot_inputs``；含 Agent 输出目录解析。
# 调用方：graph.py（``build_initial_state``：``load_snapshot_inputs``、``resolved_agent_outputs_dir``）。
"""从磁盘加载分片快照目录，规范为 LangGraph 使用的 ``snapshot_inputs`` 字典。

- **路径**：``got_mvp/data/snapshot_{YYYY-MM-DD}/``（``meta.json`` + 五类业务 JSON + **SSEIndex.json** 上证基线块）。
- **入口**：``read_snapshot_inputs()`` 与 ``load_snapshot_inputs()`` 等价，纯读盘。
- **图状态**：结果写入 ``GoTState["snapshot_inputs"]``（见 ``state_types.GoTState``）；其中 **``SSEIndex``** 与 **``CNMacroData``** 分键存放，加载器**不**把上证序列合并进中国宏观块。
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Literal

NodeName = Literal["CNMacroData", "USMacroData", "MacroNews", "MesoNews", "MicroNews"]

_GOT_MVP_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _GOT_MVP_DIR / "data"

# 五类输入节点对应快照；上证日度基线单独文件，见 _SSE_INDEX_KEY。
_REQUIRED_BLOCK_KEYS = ("CNMacroData", "USMacroData", "MacroNews", "MesoNews", "MicroNews")
_SSE_INDEX_KEY = "SSEIndex"
_SNAPSHOT_JSON_STEMS = (*_REQUIRED_BLOCK_KEYS, _SSE_INDEX_KEY)
_SSE_INDEX_REQUIRED_FIELDS = (
    "sse_index_close_last10",
    "sse_index_dates_last10",
    "sse_index_trace_summary",
)


def resolved_snapshot_date() -> str:
    """本次运行使用的快照日期（ISO：`YYYY-MM-DD`）。可由 GOT_SNAPSHOT_DATE 指定。"""
    raw = os.getenv("GOT_SNAPSHOT_DATE", "").strip()
    if raw:
        try:
            datetime.strptime(raw, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"GOT_SNAPSHOT_DATE 须为 YYYY-MM-DD，当前: {raw!r}") from e
        return raw
    return date.today().isoformat()


def resolved_snapshot_dir() -> Path:
    """分片快照目录：`data/snapshot_{YYYY-MM-DD}/`（每模块独立 JSON + meta.json）。"""
    return _DATA_DIR / f"snapshot_{resolved_snapshot_date()}"


def resolved_agent_outputs_dir(base: str) -> str:
    """解析为 ``base/YYYY-MM-DD/``，其中日期与 ``resolved_snapshot_date()`` 一致。"""
    s = base.strip()
    if not s:
        return ""
    root = Path(s).expanduser()
    day = resolved_snapshot_date()
    return str((root / day).resolve())


def read_snapshot_inputs() -> Dict[str, Dict[str, str]]:
    """从磁盘读取当前解析日的分片快照目录。"""
    return _load_edb_snapshot()


def _coerce_snapshot_field_value(v: Any) -> str:
    """分片快照字段多为字符串；资讯类文件允许 string[]，每条为「日期 | 标题」一行，加载时拼成换行串。"""
    if isinstance(v, list):
        parts: list[str] = []
        for x in v:
            s = str(x).strip()
            if s:
                parts.append(s)
        return "\n".join(parts)
    return str(v)


def _normalize_sse_index_block(obj: Dict[str, Any], source_label: str) -> Dict[str, str]:
    missing = [f for f in _SSE_INDEX_REQUIRED_FIELDS if f not in obj or not str(obj.get(f, "")).strip()]
    if missing:
        raise ValueError(
            f"{_SSE_INDEX_KEY}.json 须含非空字段: {', '.join(_SSE_INDEX_REQUIRED_FIELDS)}；缺: {', '.join(missing)}（{source_label}）"
        )
    return {k: _coerce_snapshot_field_value(v) for k, v in obj.items()}


def _normalize_block_objects(raw: Dict[str, Any], source_label: str) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for key in _REQUIRED_BLOCK_KEYS:
        if key not in raw or not isinstance(raw[key], dict):
            raise ValueError(
                f"快照须包含五段对象: {', '.join(_REQUIRED_BLOCK_KEYS)}，缺或无效: {key!r}（{source_label}）"
            )
        out[key] = {k: _coerce_snapshot_field_value(v) for k, v in raw[key].items()}
    sse = raw.get(_SSE_INDEX_KEY)
    if not isinstance(sse, dict):
        raise ValueError(f"快照须含 {_SSE_INDEX_KEY}.json 对应对象（{source_label}）")
    out[_SSE_INDEX_KEY] = _normalize_sse_index_block(sse, source_label)
    return out


def _validate_meta_snapshot_date(meta: Dict[str, Any], day: str, source_label: str) -> None:
    sd = str(meta.get("snapshot_date", "")).strip()
    if not sd:
        raise ValueError(f"meta.snapshot_date 必填（YYYY-MM-DD），{source_label}")
    if sd != day:
        raise ValueError(
            f"当前使用日期 {day}，但 {source_label} 内 meta.snapshot_date={sd!r}。"
            "请调整 GOT_SNAPSHOT_DATE 或修正 meta.json。"
        )


def _load_split_snapshot(day: str, dir_path: Path) -> Dict[str, Dict[str, str]]:
    meta_path = dir_path / "meta.json"
    if not meta_path.is_file():
        raise FileNotFoundError(
            f"分片快照目录缺少 meta.json: {meta_path}\n"
            "请在该目录补全 meta.json（含 snapshot_date 与取数说明字段）。"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ValueError(f"meta.json 须为 JSON 对象: {meta_path}")
    _validate_meta_snapshot_date(meta, day, str(meta_path))

    combined: Dict[str, Any] = {"meta": meta}
    missing: list[str] = []
    for key in _SNAPSHOT_JSON_STEMS:
        p = dir_path / f"{key}.json"
        if not p.is_file():
            missing.append(p.name)
            continue
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError(f"{p.name} 须为 JSON 对象（文件: {p}）")
        if key == "CNMacroData":
            bad_sse = [k for k in obj if str(k).startswith("sse_index")]
            if bad_sse:
                raise ValueError(
                    f"{p.name} 不得包含上证基线字段 {bad_sse}；请写入 {_SSE_INDEX_KEY}.json（见 MCP_宏观_EDB_取数.md）。"
                )
        combined[key] = obj
    if missing:
        raise ValueError(
            f"分片快照目录 {dir_path} 缺少文件: {', '.join(missing)}。"
            f"须含 meta.json 与 {', '.join(f'{k}.json' for k in _SNAPSHOT_JSON_STEMS)}。"
        )
    return _normalize_block_objects(combined, str(dir_path))


def _load_edb_snapshot() -> Dict[str, Dict[str, str]]:
    day = resolved_snapshot_date()
    split_dir = resolved_snapshot_dir()
    if not split_dir.is_dir():
        raise FileNotFoundError(
            f"缺少分片快照目录: {split_dir}\n"
            f"当前解析日期为 {day}。请按 src/got_mvp/prompt_md/取数/MCP_宏观_EDB_取数.md 与 MCP_资讯_取数.md 写入该目录"
            f"（meta.json + CNMacroData.json … MicroNews.json + SSEIndex.json），或调整 GOT_SNAPSHOT_DATE 与目录名一致。"
        )
    return _load_split_snapshot(day, split_dir)


def load_snapshot_inputs() -> Dict[str, Dict[str, str]]:
    """供 ``graph.build_initial_state`` 使用；与 ``read_snapshot_inputs`` 相同实现。"""
    return read_snapshot_inputs()


def node_order() -> list[NodeName]:
    return ["CNMacroData", "USMacroData", "MacroNews", "MesoNews", "MicroNews"]
