# 【主流程】LangGraph 构图、初始状态与各节点编排；未安装 langgraph 时同序执行；``decision_only`` 时仅走决策链读盘（无批判回流）。
# 调用方：run_mvp.py（``run_graph``）；``build_initial_state`` 内可对 ``HumanInput_{D}.json`` 写占位（仅当文件不存在时）。
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from .support.node_output_json import ensure_human_input_stub
from .support.snapshot_loader import load_snapshot_inputs, resolved_agent_outputs_dir, resolved_snapshot_date
from .nodes import (
    run_aggregate_node,
    run_cn_macro_node,
    run_critic_node,
    run_decision_node,
    run_macro_news_node,
    run_meso_news_node,
    run_micro_news_node,
    run_us_macro_node,
)
from .state_types import GoTState

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:
    END = "__END__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


def build_initial_state(agent_outputs_dir: Optional[str] = None) -> GoTState:
    run_id = f"got-mvp-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid4())[:8]}"
    explicit = agent_outputs_dir.strip() if agent_outputs_dir else ""
    env_dir = os.getenv("GOT_AGENT_OUTPUT_DIR", "").strip()
    agent_raw = explicit or env_dir
    agent_abs = resolved_agent_outputs_dir(agent_raw) if agent_raw else None
    snapshot_inputs = load_snapshot_inputs()
    if agent_abs:
        ensure_human_input_stub(agent_abs)
    return {
        "snapshot_inputs": snapshot_inputs,
        "node_outputs": {},
        "aggregate": None,
        "decision": None,
        "critic": None,
        "revision_count": 0,
        "final_output": None,
        "human_input_for_decision": None,
        "agent_outputs_dir": agent_abs,
        "skip_revision_loop": bool(agent_abs),
        "meta": {
            "run_id": run_id,
            "prompt_versions": {},
            "elapsed_ms": {},
            "token_estimates": {},
            "logs": [],
        },
    }


def _cn_node(state: GoTState) -> GoTState:
    run_cn_macro_node(state)
    return state


def _us_node(state: GoTState) -> GoTState:
    run_us_macro_node(state)
    return state


def _macro_node(state: GoTState) -> GoTState:
    run_macro_news_node(state)
    return state


def _meso_node(state: GoTState) -> GoTState:
    run_meso_news_node(state)
    return state


def _micro_node(state: GoTState) -> GoTState:
    run_micro_news_node(state)
    return state


def _aggregate_node(state: GoTState) -> GoTState:
    run_aggregate_node(state)
    return state


def _decision_node(state: GoTState) -> GoTState:
    run_decision_node(state)
    return state


def _critic_node(state: GoTState) -> GoTState:
    run_critic_node(state)
    return state


def _route_after_critic(state: GoTState) -> str:
    assert state["critic"] is not None
    if state.get("skip_revision_loop"):
        state["final_output"] = state["decision"]
        return END
    if state["critic"]["need_revision"]:
        state["revision_count"] += 1
        return "AggregateEvidence"
    state["final_output"] = state["decision"]
    return END


def build_langgraph() -> Any:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("langgraph is not installed. Use run_graph_sequential() or install dependencies.")

    graph = StateGraph(GoTState)
    graph.add_node("CNMacroData", _cn_node)
    graph.add_node("USMacroData", _us_node)
    graph.add_node("MacroNews", _macro_node)
    graph.add_node("MesoNews", _meso_node)
    graph.add_node("MicroNews", _micro_node)
    graph.add_node("AggregateEvidence", _aggregate_node)
    graph.add_node("DecisionNode", _decision_node)
    graph.add_node("CriticNode", _critic_node)

    graph.set_entry_point("CNMacroData")

    graph.add_edge("CNMacroData", "USMacroData")
    graph.add_edge("USMacroData", "MacroNews")
    graph.add_edge("MacroNews", "MesoNews")
    graph.add_edge("MesoNews", "MicroNews")
    graph.add_edge("MicroNews", "AggregateEvidence")
    graph.add_edge("AggregateEvidence", "DecisionNode")
    graph.add_edge("DecisionNode", "CriticNode")
    graph.add_conditional_edges("CriticNode", _route_after_critic, {"AggregateEvidence": "AggregateEvidence", END: END})

    return graph.compile()


def _run_decision_only_pipeline(state: GoTState) -> GoTState:
    """读盘五路→归并→决策（含人类输入）→批判；不经过 LangGraph、不触发批判回流。用于上游不变、仅改决策侧后重跑。"""
    run_cn_macro_node(state)
    run_us_macro_node(state)
    run_macro_news_node(state)
    run_meso_news_node(state)
    run_micro_news_node(state)
    run_aggregate_node(state)
    run_decision_node(state)
    run_critic_node(state)
    state["final_output"] = state["decision"]
    day = resolved_snapshot_date()
    state["meta"]["logs"].append(
        f"[decision-only] 已顺序读盘五路、归并、决策（含 HumanInput_{day}.json）、批判；"
        f"未走批判回流。请事先仅更新 HumanInput_{day}.json 与/或 DecisionNode.json。"
    )
    return state


def run_graph_sequential(state: GoTState) -> GoTState:
    run_cn_macro_node(state)
    run_us_macro_node(state)
    run_macro_news_node(state)
    run_meso_news_node(state)
    run_micro_news_node(state)

    while True:
        run_aggregate_node(state)
        run_decision_node(state)
        run_critic_node(state)
        if state.get("skip_revision_loop"):
            state["final_output"] = state["decision"]
            break
        if state["critic"] and state["critic"]["need_revision"] and state["revision_count"] < 1:
            state["revision_count"] += 1
            continue
        state["final_output"] = state["decision"]
        break

    return state


def run_graph(agent_outputs_dir: Optional[str] = None, *, decision_only: bool = False) -> GoTState:
    state = build_initial_state(agent_outputs_dir)
    if not state.get("agent_outputs_dir"):
        raise RuntimeError(
            "未设置 Agent 输出父目录。请将各节点 JSON 放在 {父目录}/{YYYY-MM-DD}/（与 GOT_SNAPSHOT_DATE 一致），"
            "然后设置 GOT_AGENT_OUTPUT_DIR 或使用:\n"
            "  python -m src.got_mvp.run_mvp --agent-dir 父目录路径\n"
        )
    if decision_only:
        return _run_decision_only_pipeline(state)
    if LANGGRAPH_AVAILABLE:
        app = build_langgraph()
        result: Dict[str, Any] = app.invoke(state)
        return result  # type: ignore[return-value]
    return run_graph_sequential(state)
