# 【编排】LangGraph 运行态 TypedDict；各节点 JSON 必填字段由 ``nodes._validate_agent_report`` 与 ``prompt_md/节点`` 约定。
# 调用方：graph.py、nodes.py、evaluation.py。
"""GoT MVP 图状态容器；各节点 JSON 字段契约见 ``nodes`` 与 ``prompt_md/节点``。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class RunMeta(TypedDict):
    run_id: str
    prompt_versions: Dict[str, str]
    elapsed_ms: Dict[str, int]
    token_estimates: Dict[str, int]
    logs: List[str]


class GoTState(TypedDict):
    snapshot_inputs: Dict[str, Dict[str, str]]
    node_outputs: Dict[str, Dict[str, Any]]
    aggregate: Optional[Dict[str, Any]]
    decision: Optional[Dict[str, Any]]
    critic: Optional[Dict[str, Any]]
    revision_count: int
    final_output: Optional[Dict[str, Any]]
    human_input_for_decision: Optional[Dict[str, Any]]
    meta: RunMeta
    agent_outputs_dir: Optional[str]
    skip_revision_loop: bool
