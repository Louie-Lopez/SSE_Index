# 【主流程】对照上游关键证据评估「归并+最终决策」叙述是否存在重大矛盾；结果落盘 JSON。
# 调用方：run_mvp.py（``evaluate_run`` / ``format_logs``）。
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .state_types import GoTState
from .support.snapshot_loader import resolved_snapshot_date

_INPUT_NODES: Tuple[str, ...] = ("CNMacroData", "USMacroData", "MacroNews", "MesoNews", "MicroNews")

# 非语义模型：仅作方向张力粗检；不能替代人工或 LLM 复核。
_BULLISH_HINTS: Tuple[str, ...] = (
    "偏多",
    "看涨",
    "上行",
    "乐观",
    "积极",
    "扩张",
    "bullish",
    "支撑",
    "回暖",
    "走强",
)
_BEARISH_HINTS: Tuple[str, ...] = (
    "偏空",
    "看跌",
    "下行",
    "谨慎",
    "悲观",
    "收缩",
    "bearish",
    "压制",
    "回调",
    "走弱",
)


def _polarity_score(text: str) -> int:
    """正数偏多倾向、负数偏空倾向、零为中性或未命中。"""
    t = text.lower()
    s = 0
    for w in _BULLISH_HINTS:
        s += t.count(w.lower()) if w.isascii() else text.count(w)
    for w in _BEARISH_HINTS:
        s -= t.count(w.lower()) if w.isascii() else text.count(w)
    return s


def _collect_upstream_evidence(state: GoTState) -> Tuple[str, List[Dict[str, Any]]]:
    """拼接五输入节点的 evidence，并保留按节点溯源。"""
    parts: list[str] = []
    index: list[dict[str, Any]] = []
    for name in _INPUT_NODES:
        block = state.get("node_outputs", {}).get(name) or {}
        ev = block.get("evidence") or []
        if not isinstance(ev, list):
            continue
        items = [str(x).strip() for x in ev if str(x).strip()]
        if not items:
            continue
        index.append({"node": name, "items": items})
        parts.append(f"【{name}】\n" + "\n".join(f"- {x}" for x in items))
    return "\n\n".join(parts), index


def _merged_final_narrative(state: GoTState) -> str:
    agg = state.get("aggregate") or {}
    fin = state.get("final_output") or state.get("decision") or {}
    a_rep = str(agg.get("report", "")).strip()
    f_rep = str(fin.get("report", "")).strip()
    if a_rep and f_rep:
        return f"{a_rep}\n\n---\n\n{f_rep}"
    return f_rep or a_rep


def _analyze_contradictions(merged_text: str, evidence_blob: str) -> Tuple[bool, List[str], Dict[str, int]]:
    points: list[str] = []
    sm = _polarity_score(merged_text)
    se = _polarity_score(evidence_blob)
    scores = {"merged_polarity_score": sm, "evidence_polarity_score": se}

    # 1) 方向符号相反且两侧都有一定「张力」
    if sm != 0 and se != 0 and (sm > 0) != (se > 0) and min(abs(sm), abs(se)) >= 2:
        points.append(
            "归并+决策叙述与五路「关键证据」汇总在多空关键词上出现反向张力（程序化粗检，非语义等价）。"
        )

    # 2) 决策端极强倾向、证据池接近中性
    if abs(sm) >= 5 and abs(se) <= 1:
        points.append("决策/归并文本多空倾向较强，而证据池关键词近乎中性，存在叙事强于证据支撑的张力。")

    # 3) 证据池较强倾向、决策端接近中性
    if abs(se) >= 5 and abs(sm) <= 1:
        points.append("证据池多空倾向较强，而决策/归并文本关键词近乎中性，存在结论弱于证据张力的现象。")

    major = len(points) > 0
    return major, points, scores


def _evaluation_output_path() -> Path:
    day = resolved_snapshot_date()
    root = Path(__file__).resolve().parent / "data" / "evaluation" / day
    root.mkdir(parents=True, exist_ok=True)
    return root / "contradiction_evaluation.json"


def evaluate_run(state: GoTState) -> Dict[str, Any]:
    decision = state["final_output"] or state["decision"]
    aggregate = state["aggregate"]
    critic = state["critic"]

    assert decision is not None and aggregate is not None and critic is not None

    evidence_blob, evidence_index = _collect_upstream_evidence(state)
    merged = _merged_final_narrative(state)
    major, contradiction_points, scores = _analyze_contradictions(merged, evidence_blob)

    run_id = str(state["meta"].get("run_id", ""))
    day = resolved_snapshot_date()

    record: Dict[str, Any] = {
        "run_id": run_id,
        "snapshot_date": day,
        "method": "keyword_polarity_v1",
        "method_note": "基于中英文多空提示词出现次数之差的粗检，不构成投资建议；重大矛盾应以人工或模型复核为准。",
        "major_contradiction": major,
        "contradiction_points": contradiction_points,
        "polarity_scores": scores,
        "evidence_index": evidence_index,
        "merged_report_excerpt": merged[:8000],
        "critic_need_revision": bool(critic.get("need_revision", False)),
        "revision_count": state["revision_count"],
    }

    out_path = _evaluation_output_path()
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "evaluation_output_path": str(out_path.resolve()),
        "major_contradiction": major,
        "contradiction_points": contradiction_points,
        "polarity_scores": scores,
    }


def format_logs(state: GoTState) -> List[str]:
    return [
        f"[run_id={state['meta']['run_id']}]",
        *state["meta"]["logs"],
    ]
