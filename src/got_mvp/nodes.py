# 【主流程】从 Agent 目录读各节点 JSON，校验后写入 GoTState。
# 调用方：graph.py（StateGraph 节点或 ``run_graph_sequential`` 顺序调用）。
from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Dict

from .state_types import GoTState
from .support.node_output_json import (
    human_input_json_filename,
    load_node_output_json,
    load_optional_human_input,
)
from .support.snapshot_loader import NodeName

_PROMPT_MD_DIR = Path(__file__).resolve().parent / "prompt_md" / "节点"


def prompt_file_uri(stem: str) -> str:
    """observability：标注节点对应的系统说明 md 路径。"""
    return str((_PROMPT_MD_DIR / f"{stem}.md").resolve())


def _add_log(state: GoTState, msg: str) -> None:
    state["meta"]["logs"].append(msg)


def _record_obs(state: GoTState, node: str, start: float, payload_size: int, prompt_stem: str) -> None:
    elapsed_ms = int((perf_counter() - start) * 1000)
    state["meta"]["elapsed_ms"][node] = elapsed_ms
    state["meta"]["token_estimates"][node] = max(40, payload_size // 4)
    state["meta"]["prompt_versions"][node] = prompt_file_uri(prompt_stem)


def _agent_dir(state: GoTState) -> str:
    d = state.get("agent_outputs_dir")
    if not d:
        raise RuntimeError("internal: agent_outputs_dir 未设置")
    return d


def _coerce_risk_flags(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parts = [x.strip() for x in raw.split("\n") if x.strip()]
        return parts if parts else ([raw.strip()] if raw.strip() else [])
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [str(raw).strip()] if str(raw).strip() else []


def _coerce_evidence(raw: Any) -> list[str]:
    """关键证据：短句列表，与 risk_flags 区分（证据偏事实/引用，风险偏疑点）。"""
    return _coerce_risk_flags(raw)


def _coerce_human_input_for_decision(payload: dict[str, Any]) -> dict[str, Any] | None:
    """自 ``HumanInput_{date}.json`` 解析；``human_note`` / ``report`` 与 ``evidence`` 皆空则视为未填写，返回 ``None``。"""
    note = str(payload.get("human_note") or payload.get("report") or "").strip()
    ev: list[str] = []
    if payload.get("evidence") is not None:
        ev = _coerce_evidence(payload["evidence"])
    if not note and not ev:
        return None
    out: dict[str, Any] = {}
    if note:
        out["human_note"] = note
    if ev:
        out["evidence"] = ev
    return out


def _validate_agent_report(payload: dict[str, Any], stem: str) -> dict[str, Any]:
    """各节点 JSON：应有 ``report``、``evidence``、``risk_flags``、``confidence``；其余键原样保留。"""
    if "report" not in payload:
        raise ValueError(f"{stem}.json: 缺少 report（主体分析应放在该字段）")
    if "evidence" not in payload:
        raise ValueError(f"{stem}.json: 缺少 evidence（关键证据列表）")
    if "risk_flags" not in payload:
        raise ValueError(f"{stem}.json: 缺少 risk_flags")
    if "confidence" not in payload:
        raise ValueError(f"{stem}.json: 缺少 confidence")
    out = dict(payload)
    rep = str(out.get("report", "")).strip()
    if not rep:
        raise ValueError(f"{stem}.json: report 不得为空字符串")
    out["report"] = rep
    out["evidence"] = _coerce_evidence(out["evidence"])
    if not out["evidence"]:
        raise ValueError(f"{stem}.json: evidence 至少一条非空短句")
    out["risk_flags"] = _coerce_risk_flags(out["risk_flags"])
    out["confidence"] = max(0.0, min(float(out["confidence"]), 1.0))
    if stem == "CriticNode":
        out["need_revision"] = bool(out.get("need_revision", False))
    return out


def _run_input_node_from_file(state: GoTState, node: NodeName) -> None:
    payload = load_node_output_json(_agent_dir(state), node)
    state["node_outputs"][node] = _validate_agent_report(payload, node)
    state["meta"]["elapsed_ms"][node] = 0
    state["meta"]["token_estimates"][node] = 0
    state["meta"]["prompt_versions"][node] = prompt_file_uri(node)
    _add_log(state, f"{node} loaded from agent JSON.")


def run_cn_macro_node(state: GoTState) -> None:
    _run_input_node_from_file(state, "CNMacroData")


def run_us_macro_node(state: GoTState) -> None:
    _run_input_node_from_file(state, "USMacroData")


def run_macro_news_node(state: GoTState) -> None:
    _run_input_node_from_file(state, "MacroNews")


def run_meso_news_node(state: GoTState) -> None:
    _run_input_node_from_file(state, "MesoNews")


def run_micro_news_node(state: GoTState) -> None:
    _run_input_node_from_file(state, "MicroNews")


def run_aggregate_node(state: GoTState) -> None:
    start = perf_counter()
    outputs = state["node_outputs"]
    payload = load_node_output_json(_agent_dir(state), "AggregateEvidence")
    state["aggregate"] = _validate_agent_report(payload, "AggregateEvidence")
    _record_obs(state, "AggregateEvidence", start, len(str(outputs)), "AggregateEvidence")
    state["meta"]["elapsed_ms"]["AggregateEvidence"] = 0
    state["meta"]["token_estimates"]["AggregateEvidence"] = 0
    _add_log(state, "AggregateEvidence loaded from agent JSON.")


def run_decision_node(state: GoTState) -> None:
    start = perf_counter()
    aggregate = state["aggregate"]
    assert aggregate is not None, "aggregate must exist before decision"
    base = _agent_dir(state)
    raw_human = load_optional_human_input(base)
    if raw_human is None:
        state["human_input_for_decision"] = None
        _add_log(state, f"未找到 {human_input_json_filename()}（首轮跑图后应自动出现占位，可忽略）。")
    else:
        coerced = _coerce_human_input_for_decision(raw_human)
        if coerced is None:
            state["human_input_for_decision"] = None
            _add_log(state, f"{human_input_json_filename()} 已存在但 human_note / evidence 为空，已忽略人类输入。")
        else:
            state["human_input_for_decision"] = coerced
            _add_log(state, f"{human_input_json_filename()} 已载入（非空人类输入）。")

    payload = load_node_output_json(base, "DecisionNode")
    state["decision"] = _validate_agent_report(payload, "DecisionNode")
    _record_obs(state, "DecisionNode", start, len(str(aggregate)), "DecisionNode")
    state["meta"]["elapsed_ms"]["DecisionNode"] = 0
    state["meta"]["token_estimates"]["DecisionNode"] = 0
    _add_log(state, "DecisionNode loaded from agent JSON.")


def run_critic_node(state: GoTState) -> None:
    start = perf_counter()
    aggregate = state["aggregate"]
    decision = state["decision"]
    assert aggregate is not None and decision is not None

    payload = load_node_output_json(_agent_dir(state), "CriticNode")
    critic = _validate_agent_report(payload, "CriticNode")
    need_revision = bool(critic.get("need_revision")) and state["revision_count"] < 1
    critic["need_revision"] = need_revision
    state["critic"] = critic
    _record_obs(state, "CriticNode", start, len(str(decision)), "CriticNode")
    state["meta"]["elapsed_ms"]["CriticNode"] = 0
    state["meta"]["token_estimates"]["CriticNode"] = 0
    _add_log(state, f"CriticNode loaded from agent JSON; need_revision={need_revision}.")
