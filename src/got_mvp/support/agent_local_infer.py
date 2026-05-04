# 【Agent 落盘 · 本地推理】每节点一次：节点 ``.md`` 全文 + 结构化 JSON 上下文 → 子进程 → 解析 JSON → 契约校验。
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from ..nodes import _validate_agent_report
from .local_infer_runner import LocalInferRunner, extract_first_json_object, redact_argv_for_meta

_OUTPUT_WRAPPER = """\
你只执行流水线中的**一个节点**。必须严格遵守「节点说明」Markdown 中的隔离、记忆与输出字段约定。

=== 节点说明（Markdown，权威）===
{prompt_md}

=== 本轮输入（JSON 对象，你唯一允许引用的事实材料；不得编造未出现的键值）===
{context_json}

=== 输出要求（必须遵守）===
1. 只输出**一个** JSON 对象到 stdout，前后不要 Markdown 围栏、不要解释性文字。
2. 顶层必须包含：`report`（非空字符串）、`evidence`（非空字符串数组）、`risk_flags`（字符串数组）、`confidence`（0～1 数字）。
3. 若节点为 CriticNode，还须包含 `need_revision`（布尔）。
4. 不要输出 `_generator` 键（由主程序附加）。
"""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _attach_infer_meta(
    payload: dict[str, Any],
    *,
    stem: str,
    prompt_text: str,
    snapshot_date: str,
    runner_argv: list[str],
) -> None:
    payload["_generator"] = {
        "engine": "local_infer",
        "node": stem,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "snapshot_date": snapshot_date,
        "prompt_md_sha256": _sha256(prompt_text),
        "infer_argv": redact_argv_for_meta(runner_argv),
    }


def _build_user_message(prompt_md: str, context: dict[str, Any]) -> str:
    ctx_txt = json.dumps(context, ensure_ascii=False, indent=2)
    return _OUTPUT_WRAPPER.format(prompt_md=prompt_md, context_json=ctx_txt)


def _run_one(
    stem: str,
    prompt_md: str,
    context: dict[str, Any],
    runner: LocalInferRunner,
    snapshot_date: str,
) -> dict[str, Any]:
    msg = _build_user_message(prompt_md, context)
    stdout = runner.run(msg)
    obj = extract_first_json_object(stdout)
    obj.pop("_generator", None)
    validated = _validate_agent_report(obj, stem)
    _attach_infer_meta(
        validated,
        stem=stem,
        prompt_text=prompt_md,
        snapshot_date=snapshot_date,
        runner_argv=runner.argv,
    )
    return validated


def _upstream_slice(node_outputs: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        k: {
            "report": node_outputs[k].get("report", ""),
            "evidence": node_outputs[k].get("evidence", []),
            "risk_flags": node_outputs[k].get("risk_flags", []),
            "confidence": node_outputs[k].get("confidence"),
        }
        for k in ("CNMacroData", "USMacroData", "MacroNews", "MesoNews", "MicroNews")
        if k in node_outputs
    }


def generate_all_via_local_infer(
    snapshot_inputs: Mapping[str, Mapping[str, str]],
    *,
    snapshot_meta: Mapping[str, Any],
    prompt_texts: Mapping[str, str],
    snapshot_date: str,
    human_input: Optional[dict[str, Any]],
    runner: LocalInferRunner,
) -> dict[str, dict[str, Any]]:
    """
    顺序跑 8 个节点；每节点一次子进程调用，上下文仅含该步所需 JSON + 节点 .md。
    """
    snap = {k: dict(v) for k, v in snapshot_inputs.items()}
    meta = dict(snapshot_meta)
    prompts = dict(prompt_texts)
    out: dict[str, dict[str, Any]] = {}

    out["CNMacroData"] = _run_one(
        "CNMacroData",
        prompts["CNMacroData"],
        {"node": "CNMacroData", "snapshot_date": snapshot_date, "CNMacroData": snap["CNMacroData"], "meta": meta},
        runner,
        snapshot_date,
    )
    out["USMacroData"] = _run_one(
        "USMacroData",
        prompts["USMacroData"],
        {"node": "USMacroData", "snapshot_date": snapshot_date, "USMacroData": snap["USMacroData"], "meta": meta},
        runner,
        snapshot_date,
    )
    out["MacroNews"] = _run_one(
        "MacroNews",
        prompts["MacroNews"],
        {"node": "MacroNews", "snapshot_date": snapshot_date, "MacroNews": snap["MacroNews"], "meta": meta},
        runner,
        snapshot_date,
    )
    out["MesoNews"] = _run_one(
        "MesoNews",
        prompts["MesoNews"],
        {"node": "MesoNews", "snapshot_date": snapshot_date, "MesoNews": snap["MesoNews"], "meta": meta},
        runner,
        snapshot_date,
    )
    out["MicroNews"] = _run_one(
        "MicroNews",
        prompts["MicroNews"],
        {"node": "MicroNews", "snapshot_date": snapshot_date, "MicroNews": snap["MicroNews"], "meta": meta},
        runner,
        snapshot_date,
    )

    out["AggregateEvidence"] = _run_one(
        "AggregateEvidence",
        prompts["AggregateEvidence"],
        {
            "node": "AggregateEvidence",
            "snapshot_date": snapshot_date,
            "meta": meta,
            "SSEIndex": snap["SSEIndex"],
            "upstream_node_outputs": _upstream_slice(out),
        },
        runner,
        snapshot_date,
    )

    out["DecisionNode"] = _run_one(
        "DecisionNode",
        prompts["DecisionNode"],
        {
            "node": "DecisionNode",
            "snapshot_date": snapshot_date,
            "meta": meta,
            "SSEIndex": snap["SSEIndex"],
            "AggregateEvidence": {
                "report": out["AggregateEvidence"]["report"],
                "evidence": out["AggregateEvidence"]["evidence"],
                "risk_flags": out["AggregateEvidence"]["risk_flags"],
                "confidence": out["AggregateEvidence"]["confidence"],
            },
            "HumanInput": human_input if human_input is not None else {},
            "upstream_node_outputs": _upstream_slice(out),
        },
        runner,
        snapshot_date,
    )

    out["CriticNode"] = _run_one(
        "CriticNode",
        prompts["CriticNode"],
        {
            "node": "CriticNode",
            "snapshot_date": snapshot_date,
            "meta": meta,
            "AggregateEvidence": {
                "report": out["AggregateEvidence"]["report"],
                "evidence": out["AggregateEvidence"]["evidence"],
                "risk_flags": out["AggregateEvidence"]["risk_flags"],
                "confidence": out["AggregateEvidence"]["confidence"],
            },
            "DecisionNode": {
                "report": out["DecisionNode"]["report"],
                "evidence": out["DecisionNode"]["evidence"],
                "risk_flags": out["DecisionNode"]["risk_flags"],
                "confidence": out["DecisionNode"]["confidence"],
            },
            "HumanInput": human_input if human_input is not None else {},
        },
        runner,
        snapshot_date,
    )

    return out
