# 【工具】从运行目录读取 Agent 写入的 ``{节点名}.json``（与 ``prompt_md/节点/{节点名}.md`` 对应）。
# 调用方：nodes.py（各 run_* 节点内 ``load_node_output_json``）。
"""从运行目录读取各节点产出的 `{节点名}.json`（与 `prompt_md/节点/{节点名}.md` 对应）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .snapshot_loader import resolved_snapshot_date


def human_input_json_filename() -> str:
    """与 ``GOT_SNAPSHOT_DATE`` 对齐的人类输入文件名（含 ``.json``）。"""
    return f"HumanInput_{resolved_snapshot_date()}.json"


def human_input_json_path(run_dir: str | Path) -> Path:
    return Path(run_dir).resolve() / human_input_json_filename()


def ensure_human_input_stub(agent_dir: str | Path) -> None:
    """若当日 ``HumanInput_{YYYY-MM-DD}.json`` 尚不存在则写入占位；**已存在则绝不覆盖**。"""
    base = Path(agent_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    path = human_input_json_path(base)
    if path.is_file():
        return
    stub = (
        "{\n"
        '  "_instruction": "可选：填写 human_note 作为决策补充；无需补充可保持为空字符串。",\n'
        '  "human_note": ""\n'
        "}\n"
    )
    path.write_text(stub, encoding="utf-8")


def load_optional_human_input(run_dir: str | Path) -> dict[str, Any] | None:
    """读取 ``HumanInput_{YYYY-MM-DD}.json``；不存在则 ``None``。"""
    path = human_input_json_path(run_dir)
    if not path.is_file():
        return None
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"人类输入文件须为 JSON 对象: {path}")
    return obj


def node_output_json_path(run_dir: Path, stem: str) -> Path:
    return run_dir / f"{stem}.json"


def load_node_output_json(run_dir: str | Path, stem: str) -> dict[str, Any]:
    base = Path(run_dir).resolve()
    path = node_output_json_path(base, stem)
    if not path.is_file():
        raise FileNotFoundError(
            f"缺少节点输出文件: {path}\n"
            f"请按 src/got_mvp/prompt_md/节点/{stem}.md 要求，由 Agent 生成同名 JSON（仅此一轮、无跨节点记忆）。"
        )
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def load_optional_node_json(run_dir: str | Path, stem: str) -> dict[str, Any] | None:
    """若存在 ``{stem}.json`` 则读取为对象；不存在则返回 ``None``。"""
    base = Path(run_dir).resolve()
    path = node_output_json_path(base, stem)
    if not path.is_file():
        return None
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{stem}.json 须为 JSON 对象: {path}")
    return obj
